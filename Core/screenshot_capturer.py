import threading
import pyautogui
import cv2
import numpy as np

class ScreenshotCapturer:
    def __init__(self, region=None):
        """
        Initialize the ScreenshotCapturer class.

        Parameters:
            region (tuple): Default screen region to capture (x, y, width, height).
        """
        self.region = region
        self.latest_screenshot = None
        self.keep_capturing = False
        self.screenshot_thread = None
        self.screenshot_lock = threading.Lock()

    def _capture_screenshots(self):
        """Continuously capture screenshots from the specified region."""
        while self.keep_capturing:
            screenshot = pyautogui.screenshot(region=self.region)
            screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            with self.screenshot_lock:
                self.latest_screenshot = screenshot

    def capture_screenshot_specific(self, min_x, min_y, width, height):
        region = (min_x, min_y, width, height)  # Define the region as a tuple
        screenshot = pyautogui.screenshot(region=region)
        screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)  # Convert the screenshot
        return screenshot

    def start_capturing(self, specific=False, min_x=None, min_y=None, width=None, height=None):
        """
        Start the screenshot capture process.

        Parameters:
            specific (bool): Whether to use a specific region or the default region.
            min_x (int): Top-left X coordinate for specific region.
            min_y (int): Top-left Y coordinate for specific region.
            width (int): Width for specific region.
            height (int): Height for specific region.
        """
        if not self.keep_capturing:
            self.keep_capturing = True
            target = self._capture_screenshots if not specific else self.capture_screenshot_specific
            self.screenshot_thread = threading.Thread(
                target=target,
                kwargs={"min_x": min_x, "min_y": min_y, "width": width, "height": height} if specific else {},
                daemon=True
            )
            self.screenshot_thread.start()

    def stop_capturing(self):
        """Stop the screenshot capture process."""
        if self.keep_capturing:
            self.keep_capturing = False
            self.screenshot_thread.join()

    def get_latest_screenshot(self):
        """
        Safely retrieve the latest captured screenshot.

        Returns:
            numpy.ndarray: The latest screenshot image as a NumPy array.
        """
        with self.screenshot_lock:
            return self.latest_screenshot