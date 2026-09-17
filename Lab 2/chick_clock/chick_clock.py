#!/usr/bin/env python3
"""Chick Clock -- a Lab 2 PiClock for the Adafruit Mini PiTFT.

Controls
    A (GPIO23) tap        start or stop the 30 minute focus timer
    B (GPIO24) tap        strike the hour (8am and 8pm both ring eight)
    B (GPIO24) hold       show the exact time, date and school-year progress
    A + B press           step through the scene preview: one day from dawn
                          to nightcap, then every growth stage.  Press again
                          for the next scene; one more press after the last
                          one returns to the clock, as does leaving it alone
                          for 10 seconds.

Run `sudo systemctl stop piscreen.service --now` first, otherwise the boot
script is already holding the display.
"""

import argparse
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import adafruit_rgb_display.st7789 as st7789
import board
import digitalio

from chick_scene import (
    PREVIEW_SCENES,
    UiState,
    is_bedtime,
    preview_datetime,
    render_frame,
)
from chick_sound import announce_time, hour_count, is_announcing, minute_chirp

ROTATION = 90
BAUDRATE = 64000000

CHORD_SETTLE = 0.05     # both lines down this long counts as an A+B chord
TAP_LIMIT = 1.0         # an A press longer than this is not a tap
HOLD_LIMIT = 0.40       # B down this long is the detail screen, not a tap


PISCREEN = "piscreen.service"


def _piscreen_active() -> bool:
    try:
        return subprocess.run(
            ["systemctl", "is-active", "--quiet", PISCREEN], check=False
        ).returncode == 0
    except FileNotFoundError:
        return False


def stop_piscreen() -> bool:
    """Release the display from the boot script.

    piscreen.service drives the same SPI bus and GPIO pins we need, and it is
    installed with Restart=always and enabled at boot.  Without this the clock
    dies with lgpio 'GPIO busy' after every single reboot.
    """
    if not _piscreen_active():
        return False
    try:
        subprocess.run(
            ["sudo", "-n", "systemctl", "stop", PISCREEN],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print("Could not stop %s automatically (%s)." % (PISCREEN, exc))
        print("Run this yourself, then start the clock again:")
        print("    sudo systemctl stop %s --now" % PISCREEN)
        return False
    # systemctl stop is synchronous, but give lgpio a moment to drop the lines.
    time.sleep(0.3)
    return True


def start_piscreen() -> None:
    try:
        subprocess.run(
            ["sudo", "-n", "systemctl", "start", PISCREEN],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        pass


def make_display() -> st7789.ST7789:
    cs_pin = digitalio.DigitalInOut(board.D5)
    dc_pin = digitalio.DigitalInOut(board.D25)
    return st7789.ST7789(
        board.SPI(),
        cs=cs_pin,
        dc=dc_pin,
        # Must stay None.  GPIO24 is button B, and image.py's reset_pin=D24
        # would quietly break it.
        rst=None,
        baudrate=BAUDRATE,
        width=135,
        height=240,
        x_offset=53,
        y_offset=40,
    )


@dataclass
class ButtonEvents:
    a_tap: bool = False
    b_tap: bool = False
    b_held: bool = False
    preview_next: bool = False


class Buttons:
    """The two MiniPiTFT buttons, with debounce, hold and chord detection."""

    def __init__(self):
        self._a = digitalio.DigitalInOut(board.D23)
        self._b = digitalio.DigitalInOut(board.D24)
        self._a.switch_to_input(pull=digitalio.Pull.UP)
        self._b.switch_to_input(pull=digitalio.Pull.UP)
        self._a_down_at: Optional[float] = None
        self._b_down_at: Optional[float] = None
        self._a_saw_b = False
        self._b_saw_a = False
        self._both_at: Optional[float] = None
        self._both_fired = False

    def poll(self) -> ButtonEvents:
        now = time.monotonic()
        # Internal pull-ups mean a pressed button reads low.
        a = not self._a.value
        b = not self._b.value
        events = ButtonEvents()

        if a and b:
            if self._both_at is None:
                self._both_at = now
            # Fires on the press, not on a long hold: stepping through the
            # scene preview means pressing A+B over and over, and a two
            # second hold per step made that unusable.
            if not self._both_fired and now - self._both_at >= CHORD_SETTLE:
                events.preview_next = True
                self._both_fired = True
        else:
            self._both_at = None
            if not a and not b:
                self._both_fired = False

        if a and self._a_down_at is None:
            self._a_down_at = now
            self._a_saw_b = b
        if b and self._a_down_at is not None:
            self._a_saw_b = True
        if not a and self._a_down_at is not None:
            duration = now - self._a_down_at
            if not self._a_saw_b and not self._both_fired and duration < TAP_LIMIT:
                events.a_tap = True
            self._a_down_at = None
            self._a_saw_b = False

        if b and self._b_down_at is None:
            self._b_down_at = now
            self._b_saw_a = a
        if a and self._b_down_at is not None:
            self._b_saw_a = True
        if not b and self._b_down_at is not None:
            duration = now - self._b_down_at
            if (not self._b_saw_a and not self._both_fired
                    and duration < HOLD_LIMIT):
                events.b_tap = True
            self._b_down_at = None
            self._b_saw_a = False
        # `not self._both_fired` stops the detail screen from flashing up when
        # a chord is released A first, B second.  HOLD_LIMIT is long enough
        # that a tap meant to hear the time does not also open the overlay.
        events.b_held = (
            not a
            and not self._both_fired
            and self._b_down_at is not None
            and now - self._b_down_at >= HOLD_LIMIT
        )
        return events


PREVIEW_IDLE = 10.0      # no press for this long and the real clock returns
PREVIEW_REENTRY = 0.4    # ignore a bounce that would re-enter on the same press


class ScenePreview:
    """A+B steps through fixed moments, then hands the clock back.

    Pressing past the last scene returns to real time, as does going quiet
    for PREVIEW_IDLE seconds, so there are two ways out and neither needs
    waiting.

    Only the datetime handed to the renderer changes, so a preview is the
    real clock code drawing a real moment, not a separate demo path that
    could drift away from what ships.  Seconds stay live so the chick keeps
    pacing out the minute while the sky and the growth stage hold still.
    """

    def __init__(self):
        self._index = 0
        self._pressed_at = 0.0
        self._closed_at = 0.0
        self.active = False

    def advance(self, mono: float) -> None:
        if not self.active:
            # A chord that closes the last scene can bounce: first fire
            # leaves, second fire would immediately reopen scene 1.  Ignore
            # that until the buttons have had time to come back up.
            if mono - self._closed_at < PREVIEW_REENTRY:
                return
            self._index = 0
            self.active = True
        elif self._index + 1 >= len(PREVIEW_SCENES):
            self._index = 0
            self.active = False
            self._closed_at = mono
            return
        else:
            self._index += 1
        self._pressed_at = mono

    def tick(self, mono: float) -> None:
        if self.active and mono - self._pressed_at >= PREVIEW_IDLE:
            self.active = False

    @property
    def label(self) -> Optional[str]:
        if not self.active:
            return None
        scene = PREVIEW_SCENES[self._index]
        return "%d/%d %s" % (self._index + 1, len(PREVIEW_SCENES), scene.label)

    @property
    def caption_month(self) -> bool:
        return self.active and PREVIEW_SCENES[self._index].caption_month

    def now(self) -> datetime:
        real = datetime.now()
        if not self.active:
            return real
        return preview_datetime(PREVIEW_SCENES[self._index], real)


def main() -> None:
    parser = argparse.ArgumentParser(description="Chick Clock")
    parser.add_argument("--fps", type=float, default=14.0)
    parser.add_argument("--focus-minutes", type=float, default=30.0)
    parser.add_argument(
        "--keep-piscreen",
        action="store_true",
        help="do not touch piscreen.service (expect 'GPIO busy' if it is up)",
    )
    args = parser.parse_args()

    took_over = False if args.keep_piscreen else stop_piscreen()

    # Every one of these claims a GPIO line and can fail with 'GPIO busy'.
    # They have to be inside the try: acquiring the display and then dying on
    # the button pins used to leave the panel lit on a dead process and
    # piscreen.service stopped, so the screen showed nothing and never went
    # back to displaying the Pi's IP either.
    display = None
    backlight = None

    try:
        display = make_display()
        backlight = digitalio.DigitalInOut(board.D22)
        backlight.switch_to_output()
        backlight.value = True

        buttons = Buttons()
        preview = ScenePreview()
        ui = UiState(focus_total=args.focus_minutes * 60.0)

        focus_until: Optional[float] = None
        celebrate_from: Optional[float] = None
        last_second: Optional[int] = None
        strike_until: Optional[float] = None
        frame_time = 1.0 / max(1.0, args.fps)

        while True:
            started = time.monotonic()
            events = buttons.poll()

            if events.preview_next:
                preview.advance(started)
            elif events.a_tap:
                focus_until = None if focus_until else started + ui.focus_total
                celebrate_from = None

            if focus_until is not None:
                remaining = focus_until - started
                if remaining <= 0:
                    focus_until = None
                    celebrate_from = started
                    ui.focus_remaining = None
                else:
                    ui.focus_remaining = remaining
            else:
                ui.focus_remaining = None

            if celebrate_from is not None:
                elapsed = started - celebrate_from
                if elapsed < ui.celebrate_total:
                    ui.celebrate = elapsed
                else:
                    ui.celebrate = None
                    celebrate_from = None
            else:
                ui.celebrate = None

            preview.tick(started)
            ui.detail = events.b_held
            ui.demo_label = preview.label
            ui.show_month = preview.caption_month
            ui.step = int(started * 4) % 2

            shown = preview.now()
            sleepy = is_bedtime(shown.hour + shown.minute / 60.0)
            # Drop B taps (and the top-of-hour strike) while audio is busy so
            # repeated presses cannot stack another aplay/espeak on top.
            if events.b_tap and not is_announcing():
                duration = announce_time(shown, sleepy=sleepy)
                if duration > 0:
                    strike_until = started + duration
                    ui.hour_strike = hour_count(shown.hour)
            if last_second == 59 and shown.second == 0:
                if shown.minute == 0 and not is_announcing():
                    duration = announce_time(shown, sleepy=sleepy)
                    if duration > 0:
                        strike_until = started + duration
                        ui.hour_strike = hour_count(shown.hour)
                elif shown.minute != 0:
                    minute_chirp()
            last_second = shown.second

            if strike_until is not None and started >= strike_until:
                ui.hour_strike = None
                strike_until = None

            display.image(render_frame(shown, ui), ROTATION)

            spare = frame_time - (time.monotonic() - started)
            if spare > 0:
                time.sleep(spare)
    except KeyboardInterrupt:
        pass
    except Exception:
        print()
        print("Startup failed.  If this says 'GPIO busy', something else is")
        print("holding the display or button pins.  Find it with:")
        print("    systemctl is-active %s" % PISCREEN)
        print("    ps -eo pid,cmd | grep -E 'screen_boot|chick_clock'")
        raise
    finally:
        # Clearing alone leaves a lit black panel, which looks like a failure
        # rather than a clean stop, so drop the backlight too.  If we took the
        # display from the boot script, hand it back: the screen returns to
        # showing the Pi's IP instead of going dark.  Guarded, because we can
        # get here with either one still unclaimed.
        if display is not None:
            display.fill(0)
        if backlight is not None:
            backlight.value = False
        if took_over:
            start_piscreen()


if __name__ == "__main__":
    main()
