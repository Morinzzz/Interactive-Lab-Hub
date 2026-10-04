#!/usr/bin/env python3
"""Speak one line through Piper on the chosen output device.

    python test_speaker.py
    python test_speaker.py --speaker 1 --text "Do you have your keys?"
"""

import argparse

import sounddevice as sd

from bag_wizard import DEFAULT_VOICE, Speaker, audio_device

parser = argparse.ArgumentParser()
parser.add_argument("--speaker", type=audio_device, default=None)
parser.add_argument("--text", default="Hi! Before you head out, where are you going today?")
args = parser.parse_args()

print("Output devices:")
for i, d in enumerate(sd.query_devices()):
    if d["max_output_channels"] > 0:
        print(f"  [{i}] {d['name']}")
print(f"Using: {sd.query_devices(args.speaker, 'output')['name']}")
Speaker(DEFAULT_VOICE, args.speaker).say(args.text)
print("Done. If you heard nothing, run wpctl status: if the only sink is 'Dummy Output',\n"
      "the USB speaker is not plugged in or not detected (check lsusb).\n"
      "Otherwise unmute it: wpctl set-mute @DEFAULT_AUDIO_SINK@ 0")
