#!/usr/bin/env python3
"""Cycle the PiTFT through READY, LISTENING, THINKING, SPEAKING.

    python test_screen.py
    python test_screen.py --save    # also write the four frames as PNGs (no Pi needed)
"""

import argparse
import time

from status_screen import STATES, StatusScreen, render

parser = argparse.ArgumentParser()
parser.add_argument("--seconds", type=float, default=2.0)
parser.add_argument("--save", action="store_true")
args = parser.parse_args()

if args.save:
    for state in STATES:
        render(state).save(f"screen_{state.lower()}.png")
        print(f"wrote screen_{state.lower()}.png")
    raise SystemExit

screen = StatusScreen()
for state in STATES:
    print(state)
    screen.show(state)
    time.sleep(args.seconds)
screen.off()
