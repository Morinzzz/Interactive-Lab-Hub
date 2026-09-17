#!/usr/bin/env python3
"""Render Chick Clock frames without a Raspberry Pi.

    python chick_preview.py                 # contact sheet of every state
    python chick_preview.py --carousel      # the A+B scene preview, in order
    python chick_preview.py --at 2026-03-04T17:25 --scale 4

Only Pillow is needed, so this runs on a laptop and makes it possible to check
"what does March at 2am look like" in one second instead of waiting five
months.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

_HERE = Path(__file__).resolve().parent


def _find_lab2(start: Path) -> Path:
    for path in (start, start.parent, start.parent / "Lab 2"):
        if (path / "cli_clock.py").is_file() or (path / "requirements.txt").is_file():
            return path
    return start


_LAB2 = _find_lab2(_HERE)
for _path in (_HERE, _LAB2):
    _s = str(_path)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from PIL import Image

from chick_art import render_text
from chick_scene import (
    HEIGHT,
    PREVIEW_SCENES,
    WIDTH,
    UiState,
    preview_datetime,
    render_frame,
)

Scene = Tuple[str, datetime, UiState]

SCENES: List[Scene] = [
    ("SEP 08:25 EGG", datetime(2025, 9, 18, 8, 25, 12), UiState()),
    ("OCT 12:40 CRACKING", datetime(2025, 10, 14, 12, 40, 22), UiState()),
    ("NOV 17:25 HATCHLING", datetime(2025, 11, 6, 17, 25, 40), UiState()),
    ("JAN 10:07 CHICK", datetime(2026, 1, 20, 10, 7, 8), UiState()),
    ("MAR 15:52 FLEDGLING", datetime(2026, 3, 12, 15, 52, 44), UiState()),
    ("MAY 23:30 BEDTIME", datetime(2026, 5, 8, 23, 30, 18), UiState()),
    ("JUN 11:15 GRADUATE", datetime(2026, 6, 4, 11, 15, 30), UiState()),
    ("FEB 02:10 DEEP NIGHT", datetime(2026, 2, 11, 2, 10, 5), UiState()),
    (
        "FOCUS MODE",
        datetime(2026, 4, 9, 14, 12, 0),
        UiState(focus_remaining=22 * 60 + 17),
    ),
    ("TIME DETAILS", datetime(2026, 4, 9, 14, 12, 9), UiState(detail=True)),
    (
        "FOCUS DONE",
        datetime(2026, 4, 9, 14, 42, 0),
        UiState(celebrate=0.9),
    ),
    (
        "SCENE PREVIEW",
        datetime(2026, 3, 22, 9, 30, 0),
        UiState(demo_label="12/14 FLEDGLING", show_month=True),
    ),
]


def preview_carousel_scenes() -> List[Scene]:
    """Every frame the A+B scene preview steps through, as it looks on the Pi."""
    now = datetime.now()
    scenes: List[Scene] = []
    for index, scene in enumerate(PREVIEW_SCENES, 1):
        ui = UiState(
            demo_label="%d/%d %s" % (index, len(PREVIEW_SCENES), scene.label),
            show_month=scene.caption_month,
        )
        scenes.append((scene.label, preview_datetime(scene, now), ui))
    return scenes


def contact_sheet(scenes: List[Scene], columns: int = 3, scale: int = 2) -> Image.Image:
    gap = 8
    label_height = 16
    cell_w = WIDTH * scale
    cell_h = HEIGHT * scale + label_height
    rows = (len(scenes) + columns - 1) // columns
    sheet = Image.new(
        "RGB",
        (columns * cell_w + (columns + 1) * gap, rows * cell_h + (rows + 1) * gap),
        (24, 24, 30),
    )
    for index, (title, when, ui) in enumerate(scenes):
        frame = render_frame(when, ui)
        if scale != 1:
            frame = frame.resize((WIDTH * scale, HEIGHT * scale), Image.NEAREST)
        column, row = index % columns, index // columns
        x = gap + column * (cell_w + gap)
        y = gap + row * (cell_h + gap)
        sheet.paste(frame, (x, y))
        label = render_text(title, 2, (232, 232, 240), (16, 16, 22))
        sheet.paste(label, (x + 2, y + HEIGHT * scale + 3), label)
    return sheet


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview Chick Clock frames")
    parser.add_argument("--at", help="ISO timestamp for a single frame")
    parser.add_argument("--scale", type=int, default=2)
    parser.add_argument("--focus", type=float, help="focus seconds remaining")
    parser.add_argument("--detail", action="store_true")
    parser.add_argument("--carousel", action="store_true",
                        help="sheet of the A+B scene preview, in press order")
    parser.add_argument("--out", default="preview_chick_clock.png")
    args = parser.parse_args()

    if args.at:
        ui = UiState(focus_remaining=args.focus, detail=args.detail)
        frame = render_frame(datetime.fromisoformat(args.at), ui)
        if args.scale != 1:
            frame = frame.resize(
                (WIDTH * args.scale, HEIGHT * args.scale), Image.NEAREST
            )
        frame.save(args.out)
    elif args.carousel:
        contact_sheet(preview_carousel_scenes(), scale=args.scale).save(args.out)
    else:
        contact_sheet(SCENES, scale=args.scale).save(args.out)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
