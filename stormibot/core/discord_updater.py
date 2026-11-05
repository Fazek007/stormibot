import os
import threading

import cv2
import requests
from datetime import datetime
import pytz
from io import BytesIO

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
europe_timezone = pytz.timezone("Europe/Paris")

def doUpdateOnDiscord(image_array):
    """
    Sends an image to Discord using a webhook.

    :param image_array:
    """
    if not WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL is not set; skipping screenshot upload.")
        return

    if image_array is None:
        print("No image to send!")
        return

    success, encoded_image = cv2.imencode('.png', image_array)
    if not success:
        print("Failed to encode image!")
        return

    image_bytes = BytesIO(encoded_image.tobytes())

    current_time = datetime.now(europe_timezone).strftime("%Y-%m-%d %H:%M:%S")
    # Files should be sent as multipart form data
    files = {
        "file": ("screenshot.png", image_bytes, "image/png")
    }
    payload = {"content": f"Here's the {current_time} screenshot!"}
    response = requests.post(WEBHOOK_URL, data=payload, files=files)

    if response.status_code == 200:
        print("Screenshot sent successfully!")
    else:
        print(f"Failed to send screenshot: {response.status_code} - {response.text}")

def send_screenshot_async(image_file):
    """
    Runs the screenshot upload in a separate thread.

    :param image_file: Image file to be uploaded.
    """
    thread = threading.Thread(target=doUpdateOnDiscord, args=(image_file,))
    thread.start()
    print("Screenshot upload started in a separate thread.")