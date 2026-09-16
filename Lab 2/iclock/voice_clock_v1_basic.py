"""
Voice Clock - VERSION 1 (initial prototype).

The first working version, kept to show where the project started.

  - the screen shows a plain digital clock (date + time)
  - the time is spoken by espeak-ng, a formant synthesizer (no neural model)
  - the tone of voice changes with the time of day, using nothing but
    espeak's own speed (-s) and pitch (-p) flags
  - no LLM, no network, no Piper: everything here runs offline

Press either button on the MiniPiTFT to hear the time.

Later versions replace the digital display with an animated face, swap
espeak for the Piper neural voice, and add LLM-written quips.
Run with piscreen.service stopped:
    sudo systemctl stop piscreen.service --now
    python voice_clock_v1_basic.py
"""
import os
import subprocess
import time
from datetime import datetime

import board
import digitalio
from PIL import Image, ImageDraw, ImageFont
import adafruit_rgb_display.st7789 as st7789

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")

# ---- Voice ----
# espeak-ng has no model and no training data - it synthesizes speech from
# rules. Speed and pitch are direct synthesis parameters, which is why the
# tone can be changed for free and instantly.
#   hour_start, hour_end, label, speed (words/min), pitch (0-99), voice
TONES = [
    (0,  5,  "late night",  105, 15, "en-us+m3"),
    (5,  12, "morning",     165, 75, "en-us"),
    (12, 18, "afternoon",   150, 50, "en-us"),
    (18, 24, "evening",     125, 30, "en-us"),
]


def tone_for(now):
    for lo, hi, label, speed, pitch, voice in TONES:
        if lo <= now.hour < hi:
            return label, speed, pitch, voice
    return TONES[-1][2:]


def pick_sink():
    """Prefer a USB speaker if one is plugged in, else the system default."""
    try:
        out = subprocess.run(["pactl", "list", "short", "sinks"],
                             capture_output=True, text=True, timeout=4).stdout
        for line in out.splitlines():
            if "alsa_output.usb" in line:
                return line.split()[1]
    except Exception:
        pass
    return None


def speak(now):
    """Render with espeak-ng, then play it through PipeWire.

    espeak writes to ALSA's default device if you let it play directly, which
    on a Pi 5 is HDMI - silent with nothing plugged in. Rendering to a wav and
    playing it with paplay keeps it on the real speaker.
    """
    label, speed, pitch, voice = tone_for(now)
    text = f"It is {now.strftime('%-I:%M %p')}."
    subprocess.run(["espeak-ng", "-v", voice, "-s", str(speed), "-p", str(pitch),
                    "-w", "/tmp/v1.wav", text], check=False)
    sink = pick_sink()
    cmd = ["paplay"] + (["--device", sink] if sink else []) + ["/tmp/v1.wav"]
    subprocess.run(cmd, check=False)
    return label, text


# ---- Display ----
cs_pin = digitalio.DigitalInOut(board.D5)      # GPIO5, not CE0 - CE0 belongs
dc_pin = digitalio.DigitalInOut(board.D25)     # to the SPI kernel driver
disp = st7789.ST7789(board.SPI(), cs=cs_pin, dc=dc_pin, rst=None,
                     baudrate=64000000, width=135, height=240,
                     x_offset=53, y_offset=40)

backlight = digitalio.DigitalInOut(board.D22)
backlight.switch_to_output()
backlight.value = True
buttonA = digitalio.DigitalInOut(board.D23)
buttonB = digitalio.DigitalInOut(board.D24)
buttonA.switch_to_input(pull=digitalio.Pull.UP)
buttonB.switch_to_input(pull=digitalio.Pull.UP)

width, height = disp.height, disp.width        # 240 x 135, landscape
image = Image.new("RGB", (width, height))
draw = ImageDraw.Draw(image)
font_small = ImageFont.truetype(FONT, 18)
font_big = ImageFont.truetype(FONT, 34)
rotation = 90


def show(now, status=""):
    """A plain digital clock: date above, time below, both centred."""
    draw.rectangle((0, 0, width, height), outline=0, fill=(0, 0, 0))
    date_str = now.strftime("%m/%d/%Y")
    time_str = now.strftime("%H:%M:%S")
    date_w = draw.textlength(date_str, font=font_small)
    time_w = draw.textlength(time_str, font=font_big)
    draw.text(((width - date_w) / 2, 33), date_str, font=font_small, fill="#FFFFFF")
    draw.text(((width - time_w) / 2, 60), time_str, font=font_big, fill="#00FF00")
    if status:
        status_w = draw.textlength(status, font=font_small)
        draw.text(((width - status_w) / 2, height - 26), status,
                  font=font_small, fill="#FFD000")
    disp.image(image, rotation)


print("Voice clock v1 (digital display + espeak-ng). Press A or B. Ctrl-C to quit.")
try:
    while True:
        now = datetime.now()
        show(now)
        if not buttonA.value or not buttonB.value:      # buttons are active-low
            label, text = speak(datetime.now())
            print(f"[{label}] {text}")
            show(datetime.now(), status=text)
            while not buttonA.value or not buttonB.value:
                time.sleep(0.05)
        time.sleep(0.1)
except KeyboardInterrupt:
    draw.rectangle((0, 0, width, height), outline=0, fill=(0, 0, 0))
    disp.image(image, rotation)
    print("\nstopped.")
