import threading
import requests
from datetime import datetime
import pytz

WEBHOOK_URL = "https://discord.com/api/webhooks/1329435238149128232/4dSqMMpFtk-VVvBGqmK8HRi_wsbkLP0mT1rnLK0fBedM9zLCjhpDSpIlzfWZHlGaOp1D"
europe_timezone = pytz.timezone("Europe/Paris")

def doUpdateOnDiscord(image_path):
    """
    Sends an image to Discord using a webhook.

    :param image_path: Path to the image file to be uploaded.
    """
    with open(image_path, "rb") as image_file:
        current_time = datetime.now(europe_timezone).strftime("%Y-%m-%d %H:%M:%S")
        # Files should be sent as multipart form data
        files = {"file": image_file}
        payload = {"content": f"Here's the {current_time} screenshot!"}
        response = requests.post(WEBHOOK_URL, data=payload, files=files)

        if response.status_code == 204:
            print("Screenshot sent successfully!")
        else:
            print(f"Failed to send screenshot: {response.status_code} - {response.text}")

def send_screenshot_async(image_path):
    """
    Runs the screenshot upload in a separate thread.

    :param image_path: Path to the image file to be uploaded.
    """
    thread = threading.Thread(target=doUpdateOnDiscord, args=(image_path,))
    thread.start()
    print("Screenshot upload started in a separate thread.")