"""Participant-facing status on the Adafruit Mini PiTFT (ST7789, 240x135).

The pin and panel settings below are the ones every Lab 2 script used on our
Pi (CS moved to GPIO5, DC on GPIO25, backlight on GPIO22). If the screen cannot
be opened, StatusScreen falls back to printing the state, so the rest of the
prototype still runs.
"""

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 240, 135
ROTATION = 90
BAUDRATE = 64000000
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# state -> (background, foreground, headline, instruction lines)
STATES = {
    "READY": ((20, 40, 90), (255, 255, 255), "READY",
              ["Hi! I'm your bag.", "Step up to start."]),
    "LISTENING": ((0, 130, 60), (255, 255, 255), "LISTENING",
                  ["Talk to me now.", "Pause when you're done."]),
    "THINKING": ((200, 130, 0), (0, 0, 0), "THINKING",
                 ["Got it.", "One moment..."]),
    "SPEAKING": ((90, 30, 120), (255, 255, 255), "SPEAKING",
                 ["Listen to me.", "Answer when it's green."]),
}


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default(size=size)


def _fitting_font(draw, path, size, texts, max_width=WIDTH - 10):
    while size > 10:
        font = _font(path, size)
        if all(draw.textlength(t, font=font) <= max_width for t in texts):
            return font
        size -= 1
    return _font(path, size)


def render(state: str) -> Image.Image:
    bg, fg, headline, lines = STATES[state]
    image = Image.new("RGB", (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(image)
    big = _fitting_font(draw, FONT_BOLD, 34, [headline])
    small = _fitting_font(draw, FONT_REGULAR, 18, lines)

    w = draw.textlength(headline, font=big)
    draw.text(((WIDTH - w) / 2, 14), headline, font=big, fill=fg)
    y = 68
    for line in lines:
        w = draw.textlength(line, font=small)
        draw.text(((WIDTH - w) / 2, y), line, font=small, fill=fg)
        y += 26
    return image


class StatusScreen:
    def __init__(self, enabled: bool = True) -> None:
        self.display = None
        if not enabled:
            print("[screen] disabled; printing states instead")
            return
        try:
            import board
            import digitalio
            import adafruit_rgb_display.st7789 as st7789

            self.display = st7789.ST7789(
                board.SPI(),
                cs=digitalio.DigitalInOut(board.D5),
                dc=digitalio.DigitalInOut(board.D25),
                rst=None,
                baudrate=BAUDRATE,
                width=135,
                height=240,
                x_offset=53,
                y_offset=40,
            )
            self.backlight = digitalio.DigitalInOut(board.D22)
            self.backlight.switch_to_output(value=True)
        except Exception as exc:  # no SPI, wrong wiring, not on a Pi, ...
            print(f"[screen] could not open the PiTFT ({exc}); printing states instead")
            self.display = None

    def show(self, state: str) -> None:
        if self.display is None:
            print(f"[screen] {state}")
            return
        self.display.image(render(state), ROTATION)

    def off(self) -> None:
        if self.display is not None:
            self.display.image(Image.new("RGB", (WIDTH, HEIGHT)), ROTATION)
            self.backlight.value = False
