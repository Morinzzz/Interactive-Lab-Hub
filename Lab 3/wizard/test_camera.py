#!/usr/bin/env python3
"""Open the webcam and print frame rate and motion score. Nothing is saved.

    python test_camera.py                 # device 0
    python test_camera.py --camera /dev/video2

Wave a hand in front of the camera: the motion score should jump above the
threshold (0.02) and "someone_in_view" should turn True for ~2 s.
"""

import argparse
import time

from camera import Camera

parser = argparse.ArgumentParser()
parser.add_argument("--camera", default="0")
parser.add_argument("--seconds", type=float, default=15.0)
args = parser.parse_args()

cam = Camera(args.camera)
cam.start()
start = time.monotonic()
try:
    while time.monotonic() - start < args.seconds:
        time.sleep(0.5)
        if cam.error:
            raise SystemExit(f"camera error: {cam.error}")
        print(f"ok={cam.ok} motion={cam.motion_score:.3f} "
              f"someone_in_view={cam.someone_in_view} sustained={cam.sustained_motion}")
finally:
    cam.stop()
    cam.join(timeout=2)
print("Done. If ok stayed False, check the device with: v4l2-ctl --list-devices")
