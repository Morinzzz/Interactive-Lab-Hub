"""
Lab 2 Part D - the barebones display clock.

Shows the date and time on the MiniPiTFT, updating once a second. This is the
starting point the later voice_clock versions grew out of.

Stop the boot info-screen service first, or the two fight over the display:
    sudo systemctl stop piscreen.service --now
    python screen_clock.py
"""
import time

import board
import digitalio
from PIL import Image, ImageDraw, ImageFont
import adafruit_rgb_display.st7789 as st7789

# The display talks over SPI. CS is on GPIO5 (not CE0, which the SPI kernel
# driver owns) and DC on GPIO25; the backlight is on GPIO22.
cs_pin = digitalio.DigitalInOut(board.D5)
dc_pin = digitalio.DigitalInOut(board.D25)
disp = st7789.ST7789(
    board.SPI(),
    cs=cs_pin,
    dc=dc_pin,
    rst=None,
    baudrate=64000000,
    width=135,
    height=240,
    x_offset=53,
    y_offset=40,
)

backlight = digitalio.DigitalInOut(board.D22)
backlight.switch_to_output()
backlight.value = True

# Swap width/height because we rotate the image 90 degrees to landscape.
width, height = disp.height, disp.width
image = Image.new("RGB", (width, height))
draw = ImageDraw.Draw(image)
rotation = 90

font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)

while True:
    # clear to black
    draw.rectangle((0, 0, width, height), outline=0, fill=(0, 0, 0))

    date_str = time.strftime("%m/%d/%Y")
    time_str = time.strftime("%H:%M:%S")

    # centre each line: (screen width - text width) / 2 is the left edge
    date_w = draw.textlength(date_str, font=font)
    time_w = draw.textlength(time_str, font=font_big)
    draw.text(((width - date_w) / 2, 33), date_str, font=font, fill="#FFFFFF")
    draw.text(((width - time_w) / 2, 60), time_str, font=font_big, fill="#00FF00")

    disp.image(image, rotation)
    time.sleep(1)
