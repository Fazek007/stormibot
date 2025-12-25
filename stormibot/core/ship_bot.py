import random
import threading
from random import randint
from time import sleep
import os
import sys
import keyboard
import cv2
import numpy as np
import pyautogui
import time
import traceback
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

from stormibot.core.discord_updater import doUpdateOnDiscord, send_screenshot_async
from stormibot.core.scheduled_task import ScheduledTask
from stormibot.core.screenshot_capturer import ScreenshotCapturer
from stormibot.core.coordinate_recognizer import CoordinateRecognizer
from stormibot.core.bot_stats import BotStats

SCREENCENTER = (960, 555)

def use_powerups():
    sleep(2)
    pyautogui.leftClick(700, 700)
    keyboard.press_and_release('7')
    keyboard.press_and_release('7')
    sleep(2)
    keyboard.press_and_release('8')
    keyboard.press_and_release('8')
    sleep(2)
    keyboard.press_and_release('9')
    keyboard.press_and_release('9')


def project_path(relative_path):
    """ Get absolute path to resource, works in dev and PyInstaller """
    try:
        # PyInstaller stores data files in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        # Dev: relative to current file
        base_path = Path(__file__).resolve().parent.parent
    return str(base_path / relative_path)

class ShipBot(QObject):
    bot_died = pyqtSignal(str)
    ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

    def __init__(self, region=(500, 120, 900, 760), confidence_threshold=0.7):
        super().__init__()
        self.level_image_map = {
            "all"  : [self.ASSETS_DIR / 'lvl_aggro.png', self.ASSETS_DIR / 'lvl.png'],  # experimental
            "10-19": [self.ASSETS_DIR / 'lvl1x_aggro.png', self.ASSETS_DIR / 'lvl1x.png'],
            "20-29": [self.ASSETS_DIR / 'lvl2x_aggro.png', self.ASSETS_DIR / 'lvl2x.png'],
            "30-39": [self.ASSETS_DIR / 'lvl3x_aggro.png', self.ASSETS_DIR / 'lvl3x.png']
        }

        self.tasks = []
        self.enemy_targets = []

        self.chest_skin_paths = [
            self.ASSETS_DIR / "winterchest1.png",
            self.ASSETS_DIR / "winterchest2.png",
            self.ASSETS_DIR / "winterchest3.png"
        ]
        self.movement_target_path = self.ASSETS_DIR / "movement_target.png"
        self.leave_harbour_path = self.ASSETS_DIR / "set_sail.png"
        self.respawn_path = self.ASSETS_DIR / "respawn.png"
        self.bm_sea_path = self.ASSETS_DIR / "sea_40x40.png"
        self.attack_symbol_path = self.ASSETS_DIR / "attack_symbol.png"
        self.gold_repair_symbol_path = self.ASSETS_DIR / "gold_rep_snow.png"
        self.green_hp_path = self.ASSETS_DIR / "green_hp.png"
        self.burning_player_ship_path = self.ASSETS_DIR / "ship_burning_uniform.png"
        self.npc_icon_path = self.ASSETS_DIR / "npc_icon.png"
        self.reconnect_button_path = self.ASSETS_DIR / "reconnect_button.png"
        self.x_button_path = self.ASSETS_DIR / "x_button.png"
        self.daily_login_path = self.ASSETS_DIR / "daily_login_bonus_text.png"

        self.isMoving = False
        self.isAttacking = False
        self.isChestFound = False
        self.isRecovering = False
        self.isMovingForChest = False
        self.stop_flag = False

        # Region of the screen to capture for recognition
        self.region = region
        self.confidence_threshold = confidence_threshold
        self.latest_screenshot = None
        self.screenshot_lock = threading.Lock()
        self.keep_capturing = True
        self.attack_start_time = None

        # Start the screenshot capture thread
        self.screenshot_capturer = ScreenshotCapturer(region)
        self.coordinate_recognizer = CoordinateRecognizer()

        # Load template images
        self.chest_targets = [self.load_image(path) for path in self.chest_skin_paths]
        self.movement_target = self.load_image(self.movement_target_path)
        self.leave_harbour_button = self.load_image(self.leave_harbour_path)
        self.respawn_button = self.load_image(self.respawn_path)
        self.bm_sea = self.load_image(self.bm_sea_path)
        self.attack_symbol = self.load_image(self.attack_symbol_path)
        self.gold_repair_symbol = self.load_image(self.gold_repair_symbol_path)
        self.green_hp = self.load_image(self.green_hp_path)
        self.player_low_hp = self.load_image(self.burning_player_ship_path)
        self.npc_icon = self.load_image(self.npc_icon_path)
        self.reconnect_button = self.load_image(self.reconnect_button_path)
        self.x_button = self.load_image(self.x_button_path)
        self.daily_login = self.load_image(self.daily_login_path)

        # Template dimensions
        self.leave_harbour_button_h, self.leave_harbour_button_w = self.leave_harbour_button.shape[:2]
        self.respawn_button_h, self.respawn_button_w = self.respawn_button.shape[:2]
        self.chest_targets_h, self.chest_targets_w = self.chest_targets[0].shape[:2]

        self.statistics = BotStats()

    def set_attack_levels(self, levels: list[str]):
        self.enemy_targets = []
        for level in levels:
            for path in self.level_image_map.get(level, []):
                self.enemy_targets.append(self.load_image(path))

    def stop_program(self):
        self.stop_flag = True
        print("The program has been stopped by the user")

    def load_image(self, relative_path):
        """Load an image from project assets folder. Returns None if not found."""
        full_path = project_path(relative_path)  # makes it work in exe + dev
        image = cv2.imread(full_path, cv2.IMREAD_COLOR)

        if image is None:
            print(f"[ERROR] Could not load image: {full_path}")
        return image


    def calculate_distance(self, x, y):
        dx = x - SCREENCENTER[0]
        dy = y - SCREENCENTER[1]
        return (dx**2 + dy**2)**0.5

    def ship_recognition_v2(self, screenshot):
        if self.isAttacking:
            return False

        if self.isRecovering:
            print("The ship is currently recovering. Skipping ship recognition.")
            return False
        gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        self.save_screenshot(gray_screenshot, "temp_scr")
        for target in self.enemy_targets:
            gray_target = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)

            # Timer for template matching
            result = cv2.matchTemplate(gray_screenshot, gray_target, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val >= 0.90:
                match_x, match_y = max_loc
                center_x = match_x + 60
                center_y = match_y + 30
                final_x = self.region[0] + center_x
                final_y = self.region[1] + center_y

                pyautogui.click(final_x, final_y)
                if self.npc_recognition():
                    keyboard.press('f')
                    self.isAttacking = True
                    self.attack_start_time = time.time()


        print("Ship not found on the screen.")
        return False




    def npc_recognition(self):
        screenshot = self.screenshot_capturer.capture_screenshot_specific(280, 60, 50, 50)
        result = cv2.matchTemplate(screenshot, self.npc_icon, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.92:
            return True
        else:
            return False

    def disconnected_recognition(self):
        screenshot = self.screenshot_capturer.get_latest_screenshot()
        result = cv2.matchTemplate(screenshot, self.reconnect_button, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.9:
            # The dimensions of the disconnect_button are 110x24
            self.clickCenter(110,24, max_loc)
            print("The connection has been lost")
            return True
        else:
            print("The game is running fine")
            return False

    def x_recognition(self):
        screenshot = self.screenshot_capturer.get_latest_screenshot()
        result = cv2.matchTemplate(screenshot, self.x_button, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.9:
            # The dimensions of the x_button are 28x28
            self.clickCenter(28,28, max_loc)
            print("There is a window to close")
            return True
        else:
            print("There are no closable windows")
            return False

    def daily_bonus_recognition(self):
        screenshot = self.screenshot_capturer.get_latest_screenshot()
        self.save_screenshot(screenshot, 'temp')
        result = cv2.matchTemplate(screenshot, self.daily_login, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.8:
            result = cv2.matchTemplate(screenshot, self.daily_login, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            # The dimensions of the accept_button are 80x20
            self.clickCenter(80,20, max_loc)

            print("Daily rewards accepted")
            return True
        else:
            print("There is no daily login bonus")
            return False

    def high_hp_recognition(self):
        if not self.isRecovering:
            return True

        screenshot = self.screenshot_capturer.capture_screenshots_specific(250, 70, 20, 20)
        result = cv2.matchTemplate(screenshot, self.green_hp, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # Check if the match exceeds the confidence threshold
        if max_val >= 0.7:
            print(f"The hp bar is quite filled: ({max_loc})")
            self.isRecovering = False
            return True
        else:
            print("Hit points are low")

    def chest_recognition(self, screenshot):
        if self.isRecovering or self.isMovingForChest:
            #print("The ship is currently moving. Skipping chest recognition.")
            return False

        for chest_target in self.chest_targets:
            result = cv2.matchTemplate(screenshot, chest_target, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            # Check if the match exceeds the confidence threshold
            if max_val >= self.confidence_threshold:
                # Calculate the center of the matched area
                match_x, match_y = max_loc
                center_x = match_x + self.chest_targets_w / 2
                center_y = match_y + self.chest_targets_h / 2

                # Apply the region offset and return the final position
                final_x = self.region[0] + center_x
                final_y = self.region[1] + center_y
                print(f"Found chest at: ({final_x}, {final_y})")
                pyautogui.click(final_x, final_y)  # Click the chest
                self.isMoving = True
                self.isMovingForChest = True
                return True
            else:
                print("No chest found on the screen.")

    def movement_recognition(self, screenshot):
        result = cv2.matchTemplate(screenshot, self.movement_target, cv2.TM_CCOEFF_NORMED)
        self.save_screenshot(screenshot, "temp")
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # Check if the match exceeds the confidence threshold
        if max_val >= self.confidence_threshold:
            print("The ship is moving.")
            self.isMoving = True  # Update the movement state
            self.isMovingForChest = True
            return True
        else:
            #sleep(0.3) # If the ships front covers the target buoy it immediately starts doing something else, so this lets it get to the chest.
            print("The ship is stationary.")
            self.isMoving = False  # Reset the movement state
            self.isMovingForChest = False
            return False

    def repair_recognition(self):
        screenshot = self.screenshot_capturer.capture_screenshot_specific( 1060, 915, 40, 40)
        result = cv2.matchTemplate(screenshot, self.gold_repair_symbol, cv2.TM_CCOEFF_NORMED)
        _,max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.6:
            print(f"Currently repairing ({max_loc})")
            return True
        else:
            print("Currently not repairing")
            return False

    def low_hp_recogniton(self):
        screenshot = self.screenshot_capturer.capture_screenshots_specific(918, 510, 80, 75)
        result = cv2.matchTemplate(screenshot, self.player_low_hp, cv2.TM_CCOEFF_NORMED)
        _,max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.65:
            print(f"Player is low hp ({max_loc})")
            self.isRecovering = True
            return True

    def repair(self):
       if not self.repair_recognition():
         keyboard.press_and_release('0')
         keyboard.press_and_release('1')
         self.press_ctrl_with_key('2')


    def inHarbour(self, screenshot):
        result = cv2.matchTemplate(screenshot, self.leave_harbour_button, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # Check if the match exceeds the confidence threshold
        if max_val >= self.confidence_threshold:
            print("The ship is in harbour.")
            self.repair()
            sleep(5)
            self.clickCenter(self.leave_harbour_button_w, self.leave_harbour_button_h, max_loc)

    def clickCenter(self, width, height, max_loc):
        match_x, match_y = max_loc
        center_x = (match_x + width // 2)
        center_y = (match_y + height // 2)

        # Apply the region offset and return the final position
        final_x = self.region[0] + center_x
        final_y = self.region[1] + center_y

        pyautogui.click(final_x, final_y)  # Click the chest

    def respawn(self, screenshot):
        result = cv2.matchTemplate(screenshot, self.respawn_button, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # Check if the match exceeds the confidence threshold
        if max_val >= 0.85:
            self.statistics.deaths += 1
            self.bot_died.emit("Bot has been killed")
            self.clickCenter(self.respawn_button_w, self.respawn_button_h * 2, max_loc)
            sleep(5)
            pyautogui.leftClick(700, 700)
            self.repair()
            use_powerups()
            sleep(90)
            newscreenshot = pyautogui.screenshot(region=self.region)
            newscreenshot = cv2.cvtColor(np.array(newscreenshot), cv2.COLOR_RGB2BGR)
            self.inHarbour(newscreenshot)
            return True
        else:
            print("Ship is going strong")

    def random_movement(self):
        if self.isMoving or self.isAttacking:
            return
        left_x = self.region[0]
        top_y = self.region[1]
        width = self.region[2]
        height = self.region[3]

        # Randomly decide whether to generate a coordinate along the horizontal or vertical border
        if random.choice(["horizontal", "vertical"]) == "horizontal":
            # Horizontal border: Top or Bottom edge
            random_x = random.randint(left_x, left_x + width)  # Full width range
            random_y = random.choice([
                random.randint(top_y, top_y + 150),                      # Top border
                random.randint(top_y + height - 150, top_y + height)    # Bottom border, only 150 so it cant accidentally click on diamond respawn
            ])
        else:
            # Vertical border: Left or Right edge
            random_x = random.choice([
                random.randint(left_x, left_x + 150),                   # Left border
                random.randint(left_x + width - 150, left_x + width)    # Right border
            ])
            random_y = random.randint(top_y, top_y + height)  # Full height range

        # Perform the click at the random position
        print(f"Clicking at: ({random_x}, {random_y})")
        self.isMoving = True
        pyautogui.click(random_x, random_y)

    def sea_movement(self, coordinates, border_width = 150):
        if self.isMoving or self.isAttacking:
            #print("Skipping sea movement")
            return False

        x_min, y_min, width, height = self.region
        x_max = x_min + width
        y_max = y_min + height
        roi = None

        choices = ["left", "right", "top", "bottom"]
        if coordinates >= 12:
            choices = ["top"]

        if coordinates <= 2:
            choices = ["bottom"]

        # Randomly choose an edge to focus on
        edge = random.choice(choices)

        # Define the region of interest (ROI) based on the chosen edge
        if edge == "top":
            roi = self.screenshot_capturer.capture_screenshot_specific(x_min, y_min, width, border_width)
            offset_x, offset_y = x_min, y_min
        elif edge == "bottom":
            roi = self.screenshot_capturer.capture_screenshot_specific(x_min, y_max - border_width, width, border_width)
            offset_x, offset_y = x_min, y_max - border_width
        elif edge == "left":
            roi = self.screenshot_capturer.capture_screenshot_specific(x_min, y_min, border_width, height)
            offset_x, offset_y = x_min, y_min
        elif edge == "right":
            roi = self.screenshot_capturer.capture_screenshot_specific(x_max - border_width, y_min, border_width, height)
            offset_x, offset_y = x_max - border_width, y_min

        # Perform template matching in the grayscale region
        result = cv2.matchTemplate(roi, self.bm_sea, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # Check if the match is valid
        if max_val >= 0.25:  # Confidence threshold
            match_x, match_y = max_loc
            travel_x = offset_x + match_x + self.bm_sea.shape[1] // 2
            travel_y = offset_y + match_y + self.bm_sea.shape[0] // 2

            print(f"Found sea at ({travel_x}, {travel_y}) on {edge} edge.")
            pyautogui.click(travel_x, travel_y)
            self.isMoving = True
            return True
        else:
            print("No valid sea region found on {edge} edge or match below confidence threshold.")

        print("Failed to find a valid travel point after multiple attempts.")
        return False

    def create_distance(self, ship_x, ship_y, distance=250, retries=20,):

        x_min, y_min, width, height = self.region
        x_max = x_min + width
        y_max = y_min + height
        screenshot = self.get_latest_screenshot()
        mask = np.zeros(screenshot.shape[:2], dtype=np.uint8)  # Initialize mask to exclude previous matches

        for attempt in range(retries):
            # Apply the mask to the screenshot to exclude previously detected regions
            masked_screenshot = cv2.addWeighted(screenshot, 1, cv2.merge([mask, mask, mask]), -1, 0)

            # Find regions of the sea using template matching
            result = cv2.matchTemplate(masked_screenshot, self.bm_sea, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            # Check if the best match is above the confidence threshold
            if max_val >= 0.7:  # Confidence threshold for detecting the sea
                match_x, match_y = max_loc
                travel_x = x_min + match_x + self.bm_sea.shape[1] // 2
                travel_y = y_min + match_y + self.bm_sea.shape[0] // 2

                # Check if the calculated travel point is within bounds
                if x_min <= travel_x < x_max and y_min <= travel_y < y_max:
                    # Calculate the Euclidean distance from the ship
                    actual_distance = ((travel_x - ship_x) ** 2 + (travel_y - ship_y) ** 2) ** 0.5
                    if distance <= actual_distance <= distance + 150:
                        print(f"Attempt {attempt + 1}: Found sea at ({travel_x}, {travel_y}), distance: {actual_distance:.2f}")
                        pyautogui.click(travel_x, travel_y)

                        # Wait briefly to see if the ship starts moving
                        time.sleep(0.1)
                        if self.movement_recognition(self.get_latest_screenshot()):
                            print(f"Ship is moving to: ({travel_x}, {travel_y})")
                            return True
                        else:
                            print("Ship did not start moving.")
                    else:
                        print(f"Attempt {attempt + 1}: Point too close to the ship (distance: {actual_distance:.2f}).")
                else:
                    print(f"Attempt {attempt + 1}: Point ({travel_x}, {travel_y}) is out of bounds.")

                # Update the mask to exclude the current detected region
                top_left = match_x, match_y
                bottom_right = (match_x + self.bm_sea.shape[1], match_y + self.bm_sea.shape[0])
                cv2.rectangle(mask, top_left, bottom_right, 255, -1)  # Mark the region as masked

            else:
                print(f"Attempt {attempt + 1}: No valid sea region found or match below confidence threshold.")

            # If no valid travel point is found, retry
            print(f"Attempt {attempt + 1}: Retrying...")

        print("Failed to find a valid travel point after multiple attempts.")
        return False

    def attack_recognition(self):
        screenshot = pyautogui.screenshot(region=(810,910,50,50))
        screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        result = cv2.matchTemplate(screenshot, self.attack_symbol, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        current_time = time.time()
        # Check if the match exceeds the confidence threshold
        if max_val >= 0.9:
            if not self.isAttacking:
                self.attack_start_time = time.time()

            if current_time - self.attack_start_time >= 15:
                print("Attack too long, reset")
                keyboard.press('z')
                self.isAttacking = False
                return False

            self.isAttacking = True  # Update the movement state
            return True
        else:
            self.isAttacking = False  # Reset the movement state
            return False

    def random_click_loop(self):
        last_key_press_time = time.time()
        try:
            while True:  # Run the loop indefinitely
                # 1. item
                #pyautogui.click(420, 340)
                # 2. item
                sleep(random.uniform(0,2))
                pyautogui.click(420, 390)
                # 3. item
                #sleep(random.uniform(0,0.2))
                #pyautogui.click(420, 440)
                #print("Clicked at (420, 340)")

                pyautogui.click(950, 585)
                wait_time = random.uniform(5, 10)
                print(f"Waiting for {wait_time:.2f} seconds...")
                time.sleep(wait_time)
                if keyboard.is_pressed('q'):
                    break

        except KeyboardInterrupt:
            print("Click loop stopped by user.")

    def save_screenshot(self, screenshot, name):
        if screenshot is not None:
            cv2.imwrite(f"screenshots/{name}.png", screenshot)

    def press_ctrl_with_key(self, key: str):
        if len(key) != 1:
            raise ValueError("The key parameter must be a single character.")
        pyautogui.hotkey('ctrl', key)
        print(f"Pressed Ctrl + {key}")

    def setup_scheduled_tasks(self):
        self.tasks = [
            ScheduledTask(lambda: randint(30, 45), lambda: self.respawn(self.screenshot_capturer.get_latest_screenshot())),
            ScheduledTask(lambda: randint(40, 50), lambda: self.inHarbour(self.screenshot_capturer.get_latest_screenshot())),
            ScheduledTask(lambda: randint(5, 8), self.repair),
            ScheduledTask(lambda: 1800, lambda: send_screenshot_async(
                self.screenshot_capturer.capture_screenshot_specific(0, 65, 1920, 1015)
            ), immediate=True),
            ScheduledTask(lambda: 600, self.disconnected_recognition),
            ScheduledTask(lambda: 500, self.x_recognition),
        ]
    def run(self):
        self.stop_flag = False
        self.screenshot_capturer.start_capturing()
        self.setup_scheduled_tasks()
        sleep(5)

        """ Main loop of the bot. """
        try:
            while not self.stop_flag:
                sleep(0.3)
                self.screenshot_capturer.new_screenshot_event.clear() # setting event to false
                self.screenshot_capturer.new_screenshot_event.wait(10.0) # setting "gate", wont start before a very new screenshot is taken

                frame = self.screenshot_capturer.get_latest_screenshot()
                self.movement_recognition(frame)
                self.attack_recognition()
                self.chest_recognition(frame)

                self.screenshot_capturer.new_screenshot_event.clear() # setting event to false
                self.screenshot_capturer.new_screenshot_event.wait(10.0) # setting "gate", wont start before a very new screenshot is taken

                self.ship_recognition_v2(self.screenshot_capturer.get_latest_screenshot())
                self.random_movement()

                 # --- Periodic tasks ---
                current_time = time.time()
                for task in self.tasks:
                    task.maybe_run(current_time)

        except Exception as e:
            print(f"An error occurred: {e}")
            traceback.print_exc()
        finally:
            self.screenshot_capturer.stop_capturing()