import threading
import time

import cv2
import pytesseract
from PIL import Image, ImageEnhance

from screenshot_capturer import ScreenshotCapturer

class CoordinateRecognizer:
    def __init__(self, region=(1827,840, 20, 20), interval=0.3):
        self.region = region
        self.interval = interval
        self.latest_result = None
        self.running = False
        self.thread = None
        self.screenshot_capturer = ScreenshotCapturer()
        # Configure Tesseract path if necessary
        pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'

    def extract_number_from_screenshot(self):
        while self.running:
            try:
                number_screenshot = self.screenshot_capturer.capture_screenshot_specific(1827, 840, 20, 20)
                #letter_screenshot = self.screenshot_capturer.capture_screenshot_specific(1800, 840, 30, 20)

                #self.save_screenshot(letter_screenshot,"temp")

                # Szöveg kinyerése a képből
                text = pytesseract.image_to_string(number_screenshot, config='--psm 10')

                # Csak számokat tartalmazó szövegre szűrés
                number = int(''.join(filter(str.isdigit, text)))

                #letter = pytesseract.image_to_string(letter_screenshot, config='--psm 10 -l eng -c tessedit_char_whitelist=ABCDEFGHIJKLMNO')

                print(number)
                self.latest_result = number
            except ValueError:
                print("Nem talált számot a képen.")
                self.latest_result = None
            except Exception as e:
                print(f"Hiba történt: {e}")
                self.latest_result = None

    def start_coordinate_recognition(self):
        """Start the OCR process in a separate thread."""
        self.running = True
        self.thread = threading.Thread(target=self.extract_number_from_screenshot, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the OCR process."""
        self.running = False
        if self.thread:
            self.thread.join()

    def get_latest_result(self):
        """Return the latest detected result."""
        return self.latest_result

    def save_screenshot(self, screenshot, name):
        if screenshot is not None:
            cv2.imwrite(f"screenshots/{name}.png", screenshot)
