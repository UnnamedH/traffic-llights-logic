# Traffic Monitor Camera System

This program was written to run on the **Raspberry Pi 4**. It was joined with an already functional TTL circuit that was controlling a traffic light intersection.

It is set to take a picture when:
1. The light is red on the corresponding road.
2. The Object sensor detects something in front of it (a car crossing the crosswalk)

It uses **Twilio** and **Google Cloud** to send a picture of the car the passes the red light!
