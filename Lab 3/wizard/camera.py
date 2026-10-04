"""Webcam reader for the wizard: live preview plus a simple motion hint.

Frames live only in memory. The latest one is JPEG-encoded for the wizard's
browser preview and then overwritten; nothing is written to disk.

Motion is plain frame differencing against a slowly updated background. It is
a hint for the wizard ("someone is in view"), not person detection: a moving
curtain or a lighting change will also trigger it.
"""

import threading
import time
from collections import deque

import cv2

WARMUP_FRAMES = 45        # ~1.5 s at 30 fps while exposure settles
SUSTAINED_WINDOW = 15     # frames (~0.5 s)
SUSTAINED_NEEDED = 8      # moving frames within the window


def parse_source(source: str):
    """'0' -> 0 (device index), '/dev/video2' -> '/dev/video2'."""
    return int(source) if source.isdigit() else source


class Camera(threading.Thread):
    def __init__(self, source: str, width: int = 640, height: int = 480,
                 motion_fraction: float = 0.02, hold_seconds: float = 2.0) -> None:
        super().__init__(daemon=True)
        self.source = parse_source(source)
        self.width, self.height = width, height
        self.motion_fraction = motion_fraction
        self.hold_seconds = hold_seconds

        self.lock = threading.Lock()
        self.jpeg = None
        self.ok = False
        self.error = ""
        self.motion_score = 0.0
        self.last_motion = 0.0
        self._recent = deque(maxlen=SUSTAINED_WINDOW)
        self._running = True

    @property
    def someone_in_view(self) -> bool:
        return time.monotonic() - self.last_motion < self.hold_seconds

    @property
    def sustained_motion(self) -> bool:
        """Motion in most of the last ~0.5 s: steadier than a single-frame blip."""
        return sum(self._recent) >= SUSTAINED_NEEDED

    def latest_jpeg(self):
        with self.lock:
            return self.jpeg

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        cap = cv2.VideoCapture(self.source, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            self.error = f"could not open camera {self.source!r}"
            print(f"[camera] {self.error}")
            return

        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        print(f"[camera] {self.source!r} opened at "
              f"{int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
              f"{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

        background = None
        failures = 0
        frame_count = 0
        while self._running:
            grabbed, frame = cap.read()
            if not grabbed:
                failures += 1
                self.ok = failures < 10
                if not self.ok:
                    self.error = "camera stopped returning frames"
                time.sleep(0.1)
                continue
            failures, self.ok, self.error = 0, True, ""

            small = cv2.resize(frame, (160, 120))
            gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (9, 9), 0)
            if background is None:
                background = gray.astype("float")
            diff = cv2.absdiff(gray, cv2.convertScaleAbs(background))
            cv2.accumulateWeighted(gray, background, 0.05)
            _, mask = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
            self.motion_score = cv2.countNonZero(mask) / mask.size
            frame_count += 1
            moving = (frame_count > WARMUP_FRAMES
                      and self.motion_score > self.motion_fraction)
            self._recent.append(moving)
            if moving:
                self.last_motion = time.monotonic()

            encoded, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if encoded:
                with self.lock:
                    self.jpeg = buf.tobytes()

        cap.release()
