# Color mixing - Pi side
# Reads the APDS-9960 color sensor and sends this player's color over MQTT.
# Run on each Pi:  python color_mix_pi.py --player 1   (use 2 and 3 on the other Pis)
# Add --demo to send fake colors without a sensor.

import argparse
import colorsys
import json
import time

import paho.mqtt.client as mqtt

BROKER = "farlab.infosci.cornell.edu"
PORT = 1883
USER = "idd"
PASSWORD = "device@theFarm"

parser = argparse.ArgumentParser()
parser.add_argument("--player", type=int, required=True, choices=[1, 2, 3])
parser.add_argument("--team", default="morinmig")
parser.add_argument("--demo", action="store_true")
parser.add_argument("--min-prox", type=int, default=40)  # how close an object has to be to count
args = parser.parse_args()

TOPIC = f"IDD/{args.team}/colormix/player{args.player}"


def setup_sensor():
    import board
    import busio
    from adafruit_apds9960.apds9960 import APDS9960

    sensor = APDS9960(busio.I2C(board.SCL, board.SDA))
    sensor.enable_proximity = True
    sensor.enable_color = True
    sensor.color_gain = 1               # 4x
    sensor.color_integration_time = 18  # about 50 ms
    return sensor


def to_8bit(r, g, b):
    # the sensor reads blue low, so boost it, then scale so the biggest value is 255
    r, g, b = r * 1.2, g * 1.2, b * 1.7
    top = max(r, g, b)
    if top <= 0:
        return 0, 0, 0
    return tuple(int(min(255, v * 255 / top)) for v in (r, g, b))


client = mqtt.Client()
client.username_pw_set(USER, PASSWORD)
client.connect(BROKER, PORT, 60)
client.loop_start()

sensor = None if args.demo else setup_sensor()
print("Player", args.player, "sending to", TOPIC)

smooth = None
try:
    while True:
        if sensor:
            r, g, b, _clear = sensor.color_data
            prox = sensor.proximity
            rgb = to_8bit(r, g, b)
            present = prox >= args.min_prox
        else:
            hue = (time.time() / (6 + 5 * args.player)) % 1
            rgb = tuple(int(v * 255) for v in colorsys.hsv_to_rgb(hue, 1, 1))
            prox, present = 255, True

        # blend with the last reading so the color doesn't flicker
        smooth = rgb if smooth is None else tuple(0.6 * s + 0.4 * v for s, v in zip(smooth, rgb))
        r, g, b = (int(v) for v in smooth)

        client.publish(TOPIC, json.dumps({"player": args.player, "r": r, "g": g, "b": b,
                                          "present": present, "prox": prox, "t": round(time.time(), 2)}))
        print(f"RGB({r}, {g}, {b})  prox {prox}  {'holding' if present else '-'}      ", end="\r", flush=True)
        time.sleep(0.1)
except KeyboardInterrupt:
    print()

client.loop_stop()
client.disconnect()
