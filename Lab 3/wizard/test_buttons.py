#!/usr/bin/env python3
"""Print PiTFT button presses (A = GPIO23, B = GPIO24, active low as in Lab 2).

    python test_buttons.py
"""

import argparse
import time

import board
import digitalio

parser = argparse.ArgumentParser()
parser.add_argument("--seconds", type=float, default=15.0)
args = parser.parse_args()

buttons = {}
for name, pin in (("A", board.D23), ("B", board.D24)):
    button = digitalio.DigitalInOut(pin)
    button.switch_to_input(pull=digitalio.Pull.UP)
    buttons[name] = button

print(f"Press A and B within {args.seconds:.0f}s...")
was_pressed = {name: False for name in buttons}
end = time.monotonic() + args.seconds
while time.monotonic() < end:
    for name, button in buttons.items():
        pressed = not button.value
        if pressed and not was_pressed[name]:
            print(f"button {name} pressed")
        was_pressed[name] = pressed
    time.sleep(0.05)
print("Done.")
