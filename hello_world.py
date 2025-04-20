import math
import queue
import random
import threading
from random import randint
from time import sleep

from PIL import Image
import keyboard
import cv2
import numpy as np
import pyautogui
import time
import pytesseract
from pip._vendor.tomli._parser import Key

import DiscordUpdater
from screenshot_capturer import ScreenshotCapturer
from coordinate_recognizer import CoordinateRecognizer

SCREENCENTER = (960, 555)
stop_flag = False

def stop_program():
    global stop_flag
    stop_flag = True

keyboard.add_hotkey('q', stop_program)
pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'

class ShipBot:
    def __init__(self, region=(500, 120, 900, 770), confidence_threshold=0.7):
        # Paths to the target images
        self.target_level_paths = ['assets/lvl_aggro.png', 'assets/lvl.png']
        self.chest_skin_paths = ['assets/dragon_chest1.png', 'assets/dragon_chest2.png', 'assets/dragon_chest3.png']
        self.movement_target_path = 'assets/movement_target.png'
        self.leave_harbour_path = 'assets/set_sail.png'
        self.respawn_path = 'assets/respawn.png'
        self.bm_sea_path = 'assets/sea_40x40.png'
        self.attack_symbol_path = 'assets/attack_symbol.png'
        self.gold_repair_symbol_path = 'assets/gold_rep_snow.png'
        self.green_hp_path = 'assets/green_hp.png'
        self.burning_player_ship = 'assets/ship_burning_uniform.png'

        self.isMoving = False
        self.isAttacking = False
        self.isChestFound = False
        self.isRecovering = False
        self.isMovingForChest = False

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
        self.enemy_targets = [self.load_image(path) for path in self.target_level_paths]
        self.chest_targets = [self.load_image(path) for path in self.chest_skin_paths]
        self.movement_target = self.load_image(self.movement_target_path)
        self.leave_harbour_button = self.load_image(self.leave_harbour_path)
        self.respawn_button = self.load_image(self.respawn_path)
        self.bm_sea = self.load_image(self.bm_sea_path)
        self.attack_symbol = self.load_image(self.attack_symbol_path)
        self.gold_repair_symbol = self.load_image(self.gold_repair_symbol_path)
        self.green_hp = self.load_image(self.green_hp_path)
        self.player_low_hp = self.load_image(self.burning_player_ship)

        # Template dimensions
        self.template_h, self.template_w = self.enemy_targets[0].shape[:2]
        self.leave_harbour_button_h, self.leave_harbour_button_w = self.leave_harbour_button.shape[:2]
        self.respawn_button_h, self.respawn_button_w = self.respawn_button.shape[:2]

    def load_image(self, image_path):
        """ Load an image and return it, or None if there's an error. """
        image = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if image is None:
            print(f"Error loading image: {image_path}")
        return image

    def calculate_distance(self, x, y):
        dx = x - SCREENCENTER[0]
        dy = y - SCREENCENTER[1]
        return (dx**2 + dy**2)**0.5

    def ship_to_enemy_halfway_point(self, enemy_coords):

        ship_x, ship_y = SCREENCENTER
        enemy_x, enemy_y = enemy_coords

        halfway_x = (ship_x + enemy_x) / 2
        halfway_y = (ship_y + enemy_y) / 2

        return halfway_x, halfway_y

    def ship_recognition(self, screenshot):
        if self.isAttacking:  # Skip ship recognition if the ship is already moving
            #print("The ship is currently attacking. Skipping ship recognition.")
            return False

        if self.isRecovering:
            print("The ship is currently recovering. Skipping ship recognition.")
            return False

        for target in self.enemy_targets:

            # Perform template matching using the images
            result = cv2.matchTemplate(screenshot, target, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            # Check if the match exceeds the confidence threshold
            if max_val >= 0.85:
                # Calculate the center of the matched area
                match_x, match_y = max_loc
                center_x = (match_x + self.template_w // 2) + 36
                center_y = (match_y + self.template_h // 2) + 30

                # Apply the region offset and return the final position
                final_x = self.region[0] + center_x
                final_y = self.region[1] + center_y
                print(f"Found ship at: ({final_x}, {final_y})")

                pyautogui.doubleClick(final_x, final_y)
                # TODO distance based actions
                if not self.isMoving:
                    distance = self.calculate_distance(final_x, final_y)
                    if distance >= 300:
                        final_x, final_y = self.ship_to_enemy_halfway_point((final_x, final_y))
                        pyautogui.click(final_x, final_y)
                return True  # Recognition and action were successful

        print("Ship not found on the screen.")
        return False  # No ships were found

    #def bm_ship_recognition(self, screenshot, prev_frame=None):

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
        #TODO movement recogniton type of shit
        if self.isRecovering or self.isMovingForChest:
            print("The ship is currently moving. Skipping chest recognition.")
            return False

        for chest_target in self.chest_targets:
            result = cv2.matchTemplate(screenshot, chest_target, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            # Check if the match exceeds the confidence threshold
            if max_val >= self.confidence_threshold:
                # Calculate the center of the matched area
                match_x, match_y = max_loc
                center_x = (match_x + self.template_w // 2)
                center_y = (match_y + self.template_h // 2)

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
            sleep(0.3) # If the ships front covers the target buoy it immediately starts doing something else, so this lets it get to the chest.
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
            print("The ship is destroyed.")
            self.clickCenter(self.respawn_button_w, self.respawn_button_h * 2, max_loc)
            sleep(5)
            pyautogui.leftClick(700, 700)
            self.repair()
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
                pyautogui.click(420, 340)
                # 2. item
                sleep(random.uniform(0,2))
                pyautogui.click(420, 390)
                # 3. item
                #sleep(random.uniform(0,0.2))
                #pyautogui.click(420, 440)
                print("Clicked at (420, 340)") 

                wait_time = random.uniform(0.1, 4)
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


    def run(self):
        self.screenshot_capturer.start_capturing()
        #self.coordinate_recognizer.start_coordinate_recognition()
        sleep(5)
        """ Main loop of the bot. """
        last_respawn_time = time.time()
        last_harbour_time = time.time()
        last_repair_time = time.time()
        last_low_hp_time = time.time()
        last_screenshot_time = time.time()
        last_direction_change_time = time.time()

        try:
            while not stop_flag:
                self.movement_recognition(self.screenshot_capturer.get_latest_screenshot())
                self.attack_recognition()

                self.chest_recognition(self.screenshot_capturer.get_latest_screenshot())
                self.ship_recognition(self.screenshot_capturer.get_latest_screenshot())

                #self.sea_movement(self.coordinate_recognizer.get_latest_result())
                self.random_movement()
                # Periodic tasks
                current_time = time.time()
               # if current_time - last_low_hp_time >= randint(5,7):
               #     self.low_hp_recogniton()
               #     self.high_hp_recognition()

                if current_time - last_respawn_time >= randint(30, 40):
                    last_respawn_time = current_time
                    if self.respawn(self.screenshot_capturer.get_latest_screenshot()):
                        keyboard.press('7')
                        sleep(1)
                        keyboard.press('8')
                        sleep(1)
                        keyboard.press('9')

                        last_harbour_time = current_time

                if current_time - last_harbour_time >= randint(40, 50):
                    self.inHarbour(self.screenshot_capturer.get_latest_screenshot())
                    last_harbour_time = current_time

                if current_time - last_repair_time >= randint(5,10):
                    self.repair()
                    self.press_ctrl_with_key('2')
                    last_repair_time = current_time

                if current_time - last_screenshot_time >= 1800:
                    self.save_screenshot(self.screenshot_capturer.capture_screenshot_specific(0, 65, 1920, 1015),"riches")
                    DiscordUpdater.send_screenshot_async("screenshots/riches.png")
                    last_screenshot_time = current_time
                if current_time - last_direction_change_time >= 5:
                    #print(self.coordinate_recognizer.get_latest_result())
                    last_direction_change_time = current_time


        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            self.screenshot_capturer.stop_capturing()
            #self.coordinate_recognizer.stop()

    def bm_run(self):
        sleep(5)
        prev_frame = None

        try:
            while not keyboard.is_pressed('q'):  # Run until 'q' is pressed
              self.sea_movement(3)
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            self.stop_capturing()


if __name__ == "__main__":

    # Instantiate the bot and start it
    try:
        bot = ShipBot()
        #bot.random_click_loop()
        bot.run()
    except ValueError as e:
        print(f"Error: {e}")
