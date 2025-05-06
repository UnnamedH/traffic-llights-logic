#!/usr/bin/env python3

import os
import time
import subprocess
import json
from datetime import datetime
import RPi.GPIO as GPIO
from twilio.rest import Client
from google.cloud import storage
from google.oauth2 import service_account

try:
    import config
    print("Configuration loaded successfully!")
except ImportError:
    print("config file not found. Please create it using the template.")
    exit(1)

os.makedirs(config.IMAGE_FOLDER, exist_ok=True)

def setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(config.PIN_1, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(config.PIN_2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = config.GCS_CREDENTIALS_PATH

    try:
        credentials = service_account.Credentials.from_service_account_file(
            config.GCS_CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        print("Google Cloud credentials loaded successfully")
    except Exception as e:
        print(f"Could not verify Google Cloud credentials: {e}")
        print("Upload to cloud storage may fail")

def take_snapshot():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = f"{config.IMAGE_FOLDER}/snapshot_{timestamp}.jpg"

    try:
        width, height = config.CAMERA_RESOLUTION
        cmd = [
            'libcamera-still',
            '-o', image_path,
            '--width', str(width),
            '--height', str(height),
            '--nopreview',
            '--immediate',
            '--shutter', '10000',
            '--gain', '5.0',
            '--awbgains', '1.5,1.5'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"Snapshot saved to {image_path}")
        return image_path
    except subprocess.CalledProcessError as e:
        print(f"Error capturing image: {e}")
        print(f"Command output: {e.output}")
        print(f"Command stderr: {e.stderr}")
        return None
    except Exception as e:
        print(f"Unexpected error capturing image: {e}")
        return None

def upload_to_gcs(local_file_path):
    try:
        filename = os.path.basename(local_file_path)

        storage_client = storage.Client()

        bucket = storage_client.bucket(config.GCS_BUCKET_NAME)

        blob = bucket.blob(filename)
        blob.upload_from_filename(local_file_path)

        blob.make_public()

        public_url = f"{config.GCS_BASE_URL}/{filename}"
        print(f"File uploaded to {public_url}")

        return public_url
    except Exception as e:
        print(f"Error uploading to Google Cloud Storage: {e}")
        return None

def sendWhatsappMessage(image_url):
    try:
        client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)

        message = client.messages.create(
            body=config.NOTIFICATION_MESSAGE + str(datetime.now())[0:-7],
            from_=config.TWILIO_WHATSAPP_NUMBER,
            to=config.DESTINATION_WHATSAPP_NUMBER,
            media_url=[image_url]
        )

        print(f"WhatsApp image notification sent! SID: {message.sid}")
        return True
    except Exception as e:
        print(f"Error sending WhatsApp notification: {e}")
        print(f"Verify your Twilio credentials in config.py")
        return False

def monitor_pins():
    last_trigger_time = 0
    camera_ready = True

    while True:
        try:
            if GPIO.input(config.PIN_1) == 0 and GPIO.input(config.PIN_2) == 0:
                current_time = time.time()

                if current_time - last_trigger_time > config.COOLDOWN_PERIOD and camera_ready:
                    camera_ready = False

                    print("PINS LOW! Capturing...")

                    image_path = take_snapshot()

                    if image_path:
                        print("Snapshot captured! Uploading in background...")
                        last_trigger_time = current_time

                        import threading
                        def process_image():
                            nonlocal camera_ready
                            try:
                                image_url = upload_to_gcs(image_path)
                                if image_url:
                                    sendWhatsappMessage(image_url)
                            finally:
                                camera_ready = True

                        thread = threading.Thread(target=process_image)
                        thread.daemon = True
                        thread.start()
                    else:
                        print("Failed to capture image")
                        camera_ready = True

            # if needed
            # time.sleep(0.001)

        except Exception as e:
            print(f"Error: {e}")
            print(f"Restarting monitoring in 5 seconds...")
            camera_ready = True
            time.sleep(5)

def main():
    while True:
        try:
            setup()

            print("Monitoring Traffic light and Sensor pins for triggers...")
            print(f"Waiting for pins {config.PIN_1} and {config.PIN_2} to be LOW")

            monitor_pins()

        except KeyboardInterrupt:
            print("\nProgram interrupted by user")
            break
        except Exception as e:
            print(f"Critical error: {e}")
            print("Restarting the main loop in 5 seconds...")
            time.sleep(5)
        finally:
            try:
                GPIO.cleanup()
                print("GPIO cleanup complete")
            except:
                pass

if __name__ == "__main__":
    main()
