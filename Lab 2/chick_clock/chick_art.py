"""Pixel art for the Chick Clock.

Every sprite here is generated as 1:1 pixel data with hard edges and a clean
alpha channel, which is what keeps it readable on the 240x135 Mini PiTFT.
The two eggs are literal character grids; the chicks are built from ellipse
masks so the seven growth stages stay in the same style without hand-typing
six large grids.

Nothing in this module touches the Raspberry Pi, so it can be imported on a
laptop to preview frames.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from PIL import Image, ImageChops, ImageFilter

RGB = Tuple[int, int, int]
Pixel = Tuple[int, int]

# --------------------------------------------------------------------------
# Palette.  Kept under sixteen colours; "." is transparent.
# --------------------------------------------------------------------------
PALETTE: Dict[str, Optional[RGB]] = {
    ".": None,
    "o": (107, 74, 22),      # outline, a warm dark brown instead of black
    "y": (255, 217, 59),     # chick yellow
    "Y": (233, 184, 38),     # chick yellow, shaded side
    "b": (245, 166, 35),     # beak and feet
    "B": (196, 124, 20),     # beak and feet, shaded
    "w": (255, 246, 229),    # egg shell
    "W": (227, 209, 176),    # egg shell, shaded
    "k": (54, 38, 12),       # eye
    "r": (226, 96, 76),      # comb
    "g": (156, 214, 236),    # glasses lens
    "n": (94, 112, 194),     # nightcap
    "N": (60, 74, 144),      # nightcap, shaded
    "p": (246, 246, 250),    # paper / pompom highlight
    "m": (46, 46, 64),       # mortarboard
    "c": (240, 202, 70),     # tassel
}


class PixelCanvas:
    """Thin wrapper that lets the accessory code set single pixels by name.

    An optional `tint` multiplier keeps accessories lit by the same ambient
    light as the chick they sit on, so a nightcap is not glowing at 2am.
    """

    def __init__(self, image: Image.Image, tint: Optional[RGB] = None):
        self.image = image
        self._px = image.load()
        self.width, self.height = image.size
        self._bands = len(image.getbands())
        self._tint = None if tint in (None, (255, 255, 255)) else tint

    def put(self, x: int, y: int, colour) -> None:
        rgb = PALETTE[colour] if isinstance(colour, str) else colour
        if rgb is None:
            return
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        if self._tint is not None:
            rgb = (
                rgb[0] * self._tint[0] // 255,
                rgb[1] * self._tint[1] // 255,
                rgb[2] * self._tint[2] // 255,
            )
        self._px[x, y] = tuple(rgb) if self._bands == 3 else tuple(rgb) + (255,)

    def get(self, x: int, y: int):
        if not (0 <= x < self.width and 0 <= y < self.height):
            return None
        return self._px[x, y]


# --------------------------------------------------------------------------
# Character-grid sprites
# --------------------------------------------------------------------------
EGG_GRID: List[str] = [
    "........oooo........",
    ".......owwwwo.......",
    "......owwwwwwo......",
    ".....owwwwwwwwo.....",
    "....owwwwwwwwwwo....",
    "....owwwwwwwwwWo....",
    "...owwwwwwwwwwWWo...",
    "...owwwwwwwwwwWWo...",
    "..owwwwwwwwwwwWWWo..",
    "..owwwwwwwwwwwWWWo..",
    "..owwwwwwwwwwwWWWo..",
    ".owwwwwwwwwwwwWWWWo.",
    ".owwwwwwwwwwwwWWWWo.",
    ".owwwwwwwwwwwwWWWWo.",
    ".owwwwwwwwwwwwWWWWo.",
    ".owwwwwwwwwwwwWWWWo.",
    "..owwwwwwwwwwwWWWo..",
    "..owwwwwwwwwwwWWWo..",
    "..owwwwwwwwwwwWWWo..",
    "..owwwwwwwwwwwWWWo..",
    "...owwwwwwwwwwWWo...",
    "....owwwwwwwwwWo....",
    "......owwwwwwo......",
    "........oooo........",
]

# A zigzag running across the shell, plus a short branch heading up.
_CRACK: List[Pixel] = (
    [(x, 12 + (x % 2)) for x in range(2, 18)]
    + [(9, 11), (9, 10), (10, 9), (10, 8)]
    + [(14, 11), (15, 10)]
)


def _overwrite(grid: Sequence[str], pixels: Iterable[Pixel], char: str) -> List[str]:
    rows = [list(row) for row in grid]
    for x, y in pixels:
        if 0 <= y < len(rows) and 0 <= x < len(rows[y]):
            if rows[y][x] != ".":
                rows[y][x] = char
    return ["".join(row) for row in rows]


EGG_CRACKED_GRID: List[str] = _overwrite(EGG_GRID, _CRACK, "o")


def sprite_from_grid(grid: Sequence[str]) -> Image.Image:
    width = len(grid[0])
    for index, row in enumerate(grid):
        if len(row) != width:
            raise ValueError(
                "grid row %d has width %d, expected %d" % (index, len(row), width)
            )
    image = Image.new("RGBA", (width, len(grid)), (0, 0, 0, 0))
    canvas = PixelCanvas(image)
    for y, row in enumerate(grid):
        for x, char in enumerate(row):
            canvas.put(x, y, char)
    return image


# --------------------------------------------------------------------------
# Parametric chick
# --------------------------------------------------------------------------
def _ellipse_rows(width: int, height: int) -> List[Tuple[int, int]]:
    """Inclusive x extents of a hard-edged filled ellipse, one entry per row."""
    if width <= 0 or height <= 0:
        return []
    rx = (width - 1) / 2.0
    ry = (height - 1) / 2.0
    rows = []
    for y in range(height):
        dy = (y - ry) / ry if ry > 0 else 0.0
        inside = 1.0 - dy * dy
        half = rx * math.sqrt(inside) if inside > 0 else 0.0
        rows.append((int(round(rx - half)), int(round(rx + half))))
    return rows


def _ellipse_pixels(ox: int, oy: int, width: int, height: int) -> Set[Pixel]:
    pixels: Set[Pixel] = set()
    for y, (x0, x1) in enumerate(_ellipse_rows(width, height)):
        for x in range(x0, x1 + 1):
            pixels.add((ox + x, oy + y))
    return pixels


def _outline(filled: Set[Pixel]) -> Set[Pixel]:
    edge: Set[Pixel] = set()
    for x, y in filled:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) not in filled:
                edge.add((x, y))
                break
    return edge


def _shaded(filled: Set[Pixel], threshold: float = 0.88) -> Set[Pixel]:
    """Crescent shadow along the far rim, lit from the upper left.

    Testing the distance from an offset light centre gives a curved crescent.
    A straight half-plane test would put a hard diagonal stripe across the
    belly, which reads as markings rather than shading.
    """
    xs = [p[0] for p in filled]
    ys = [p[1] for p in filled]
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    rx = max(1.0, (max(xs) - min(xs)) / 2.0)
    ry = max(1.0, (max(ys) - min(ys)) / 2.0)
    light_x = cx - rx * 0.40
    light_y = cy - ry * 0.40
    shade = set()
    for x, y in filled:
        dx = (x - light_x) / rx
        dy = (y - light_y) / ry
        if math.sqrt(dx * dx + dy * dy) > threshold:
            shade.add((x, y))
    return shade


@dataclass(frozen=True)
class ChickSpec:
    """Front-facing chick, described by the size of its parts."""

    body: Tuple[int, int]
    head: Optional[Tuple[int, int]] = None
    head_overlap: int = 0
    leg: int = 0
    eye: int = 2
    beak: int = 3
    wings: bool = True
    comb: bool = False
    shell: bool = False


_BEAK_GRIDS = {
    3: ["bbb", ".B."],
    4: ["bbbb", ".BB."],
    5: ["bbbbb", ".BBB."],
}

_SHELL_HEIGHT = 13
_SHELL_SINK = 7


def build_chick(spec: ChickSpec, step: int = 0) -> Tuple[Image.Image, dict]:
    """Render one chick sprite and return it with its accessory anchors."""
    body_w, body_h = spec.body
    head_w, head_h = spec.head if spec.head else (0, 0)
    head_rise = max(0, head_h - spec.head_overlap) if spec.head else 0
    comb_h = 3 if spec.comb else 0

    width = body_w + 2
    shell_w = body_w + 4
    shell_extra = 0
    if spec.shell:
        width = max(width, shell_w + 2)
        shell_extra = _SHELL_HEIGHT - _SHELL_SINK
    height = comb_h + head_rise + body_h + spec.leg + shell_extra

    body_x = (width - body_w) // 2
    body_y = comb_h + head_rise
    head_x = (width - head_w) // 2
    head_y = comb_h

    parts = [(body_x, body_y, body_w, body_h)]
    if spec.head:
        parts.append((head_x, head_y, head_w, head_h))
    filled: Set[Pixel] = set()
    for ox, oy, pw, ph in parts:
        filled |= _ellipse_pixels(ox, oy, pw, ph)

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas = PixelCanvas(image)

    shade = _shaded(filled)
    for x, y in filled:
        canvas.put(x, y, "Y" if (x, y) in shade else "y")
    for x, y in _outline(filled):
        canvas.put(x, y, "o")

    # Legs.  One foot is planted and the other lifted, which alternates with
    # `step` to give a two frame walk cycle without moving the body.
    centre_x = width // 2
    if spec.leg and not spec.shell:
        hip_y = body_y + body_h - 2
        floor_y = height - 1
        if step == 0:
            feet = [(centre_x - 4, floor_y), (centre_x + 3, floor_y - 2)]
        else:
            feet = [(centre_x - 3, floor_y - 2), (centre_x + 4, floor_y)]
        for (foot_x, foot_y), hip_x in zip(feet, (centre_x - 3, centre_x + 2)):
            span = max(1, foot_y - hip_y)
            for i in range(span + 1):
                t = i / span
                canvas.put(int(round(hip_x + (foot_x - hip_x) * t)), hip_y + i, "b")
            for dx in (-1, 0, 1):
                canvas.put(foot_x + dx, foot_y, "b")

    # Wings, clipped to the body so they read as folded rather than stuck on.
    if spec.wings:
        wing_w = max(5, body_w // 4)
        wing_h = max(7, body_h // 2)
        wing_y = body_y + (body_h - wing_h) // 2 + 1
        for wing_x in (body_x + 1, body_x + body_w - wing_w - 1):
            wing = _ellipse_pixels(wing_x, wing_y, wing_w, wing_h) & filled
            if not wing:
                continue
            for x, y in wing:
                canvas.put(x, y, "Y")
            for x, y in _outline(wing):
                canvas.put(x, y, "o")

    # Eyes and beak.
    if spec.head:
        eye_cx = head_x + head_w // 2
        eye_cy = head_y + int(head_h * 0.45)
        gap = max(2, head_w // 5)
        face_w = head_w
        face_top = head_y
    else:
        eye_cx = body_x + body_w // 2
        eye_cy = body_y + int(body_h * 0.30)
        gap = max(3, body_w // 6)
        face_w = body_w
        face_top = body_y

    eye = spec.eye
    eyes = [(eye_cx - gap - eye + 1, eye_cy), (eye_cx + gap, eye_cy)]
    for ex, ey in eyes:
        for dx in range(eye):
            for dy in range(eye + 1):
                canvas.put(ex + dx, ey + dy, "k")

    beak_grid = _BEAK_GRIDS[spec.beak]
    beak_x = eye_cx - spec.beak // 2
    beak_y = eye_cy + eye + 2
    for dy, row in enumerate(beak_grid):
        for dx, char in enumerate(row):
            canvas.put(beak_x + dx, beak_y + dy, char)

    if spec.comb:
        for dy, row in enumerate(["ororo", "rrrrr"]):
            for dx, char in enumerate(row):
                canvas.put(eye_cx - 2 + dx, head_y - 2 + dy, char)

    # Broken shell for the hatchling stage, drawn last so it covers the body.
    if spec.shell:
        shell_x = (width - shell_w) // 2
        shell_y = body_y + body_h - _SHELL_SINK
        rows = _ellipse_rows(shell_w, _SHELL_HEIGHT * 2)[_SHELL_HEIGHT:]
        shell: Set[Pixel] = set()
        for dy, (x0, x1) in enumerate(rows):
            for x in range(x0, x1 + 1):
                shell.add((shell_x + x, shell_y + dy))
        shell_shade = _shaded(shell, threshold=1.02)
        for x, y in shell:
            canvas.put(x, y, "W" if (x, y) in shell_shade else "w")
        for x, y in _outline(shell):
            canvas.put(x, y, "o")
        columns: Dict[int, int] = {}
        for x, y in shell:
            columns[x] = min(y, columns.get(x, y))
        for x, top in columns.items():
            jag = ((x - shell_x) // 3) % 2
            for dy in range(1 + jag):
                canvas.put(x, top + dy, "o")

    meta = {
        "eyes": eyes,
        "eye_size": eye,
        "eye_y": eye_cy,
        "head_cx": eye_cx,
        "head_w": face_w,
        "head_top": face_top - comb_h,
        # Where the skull actually starts, comb excluded.  Hats have to sit
        # here: anchoring them to head_top leaves a combed chick wearing its
        # cap three pixels above its own head, with the comb poking through
        # the gap.
        "dome_top": face_top,
        "chest": (body_x + body_w // 2, body_y + int(body_h * 0.62)),
        "size": (width, height),
    }
    return image, meta


# --------------------------------------------------------------------------
# Growth stages
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Stage:
    name: str
    months: str
    grid: Optional[List[str]] = None
    spec: Optional[ChickSpec] = None
    grid_meta: dict = field(default_factory=dict)
    walks: bool = True
    has_face: bool = True


STAGES: List[Stage] = [
    Stage(
        name="EGG",
        months="SEPTEMBER",
        grid=EGG_GRID,
        grid_meta={
            "eyes": [(6, 10), (12, 10)],
            "eye_size": 2,
            "eye_y": 10,
            "head_cx": 9,
            "head_w": 16,
            "head_top": 1,
            "chest": (9, 15),
        },
        walks=False,
        has_face=False,
    ),
    Stage(
        name="CRACKING",
        months="OCTOBER",
        grid=EGG_CRACKED_GRID,
        grid_meta={
            "eyes": [(6, 16), (12, 16)],
            "eye_size": 2,
            "eye_y": 16,
            "head_cx": 9,
            "head_w": 16,
            "head_top": 1,
            "chest": (9, 18),
        },
        walks=False,
        has_face=False,
    ),
    Stage(
        name="HATCHLING",
        months="NOV - DEC",
        spec=ChickSpec(body=(20, 18), leg=0, eye=2, beak=3, wings=False, shell=True),
        walks=False,
    ),
    Stage(
        name="CHICK",
        months="JAN - FEB",
        spec=ChickSpec(body=(24, 22), leg=5, eye=2, beak=3, wings=True),
    ),
    Stage(
        name="FLEDGLING",
        months="MAR - APR",
        spec=ChickSpec(
            body=(28, 21), head=(18, 14), head_overlap=7, leg=7, eye=2, beak=4
        ),
    ),
    Stage(
        name="YOUNG HEN",
        months="MAY",
        spec=ChickSpec(
            body=(32, 23), head=(21, 16), head_overlap=8, leg=9, eye=2, beak=4,
            comb=True,
        ),
    ),
    Stage(
        name="GRADUATE",
        months="JUNE",
        spec=ChickSpec(
            body=(34, 25), head=(22, 17), head_overlap=8, leg=10, eye=2, beak=4,
            comb=True,
        ),
    ),
]

_sprite_cache: Dict[Tuple[int, int], Tuple[Image.Image, dict]] = {}


def growth_stage_count() -> int:
    return len(STAGES)


def light_tint(light: RGB, amount: float = 0.60) -> RGB:
    """Turn an ambient light colour into a gentler multiplier for sprites.

    Multiplying by the raw night light would leave the chick almost black;
    pulling the multiplier back toward white keeps it readable while still
    sitting inside the scene.
    """
    return (
        max(0, min(255, int(round(255 + (light[0] - 255) * amount)))),
        max(0, min(255, int(round(255 + (light[1] - 255) * amount)))),
        max(0, min(255, int(round(255 + (light[2] - 255) * amount)))),
    )


def _tinted(sprite: Image.Image, tint: RGB) -> Image.Image:
    solid = Image.new("RGB", sprite.size, tint)
    out = ImageChops.multiply(sprite.convert("RGB"), solid).convert("RGBA")
    out.putalpha(sprite.getchannel("A"))
    return out


def stage_sprite(
    stage_index: int, step: int = 0, tint: Optional[RGB] = None
) -> Tuple[Image.Image, dict]:
    """Return (sprite, anchors) for a growth stage, cached after first build."""
    stage = STAGES[stage_index]
    step = step if stage.walks else 0
    flat = tint in (None, (255, 255, 255))
    quantised = None if flat else (tint[0] // 8, tint[1] // 8, tint[2] // 8)
    key = (stage_index, step, quantised)
    cached = _sprite_cache.get(key)
    if cached is not None:
        return cached

    base_key = (stage_index, step, None)
    base = _sprite_cache.get(base_key)
    if base is None:
        if stage.grid is not None:
            image = sprite_from_grid(stage.grid)
            meta = dict(stage.grid_meta)
            meta["size"] = image.size
        else:
            image, meta = build_chick(stage.spec, step)
        base = (image, meta)
        _sprite_cache[base_key] = base
    if quantised is None:
        return base

    if len(_sprite_cache) > 96:
        _sprite_cache.clear()
        _sprite_cache[base_key] = base
    result = (_tinted(base[0], tint), base[1])
    _sprite_cache[key] = result
    return result


# --------------------------------------------------------------------------
# Accessories.  These draw straight onto the scene using the sprite anchors,
# so a tall nightcap or mortarboard is never clipped by the sprite bounds.
# --------------------------------------------------------------------------
def draw_glasses(canvas: PixelCanvas, meta: dict, ox: int, oy: int) -> None:
    eye = meta["eye_size"]
    frames = []
    for ex, ey in meta["eyes"]:
        x0, y0 = ox + ex - 2, oy + ey - 2
        x1, y1 = x0 + eye + 3, y0 + eye + 3
        frames.append((x0, y0, x1, y1))
        for x in range(x0 + 1, x1):
            for y in range(y0 + 1, y1):
                canvas.put(x, y, "g")
        for x in range(x0, x1 + 1):
            canvas.put(x, y0, "o")
            canvas.put(x, y1, "o")
        for y in range(y0, y1 + 1):
            canvas.put(x0, y, "o")
            canvas.put(x1, y, "o")
    for ex, ey in meta["eyes"]:
        for dx in range(eye):
            for dy in range(eye + 1):
                canvas.put(ox + ex + dx, oy + ey + dy, "k")
    bridge_y = frames[0][1] + (frames[0][3] - frames[0][1]) // 2
    for x in range(frames[0][2], frames[1][0] + 1):
        canvas.put(x, bridge_y, "o")


def draw_closed_eyes(canvas: PixelCanvas, meta: dict, ox: int, oy: int) -> None:
    eye = meta["eye_size"]
    for ex, ey in meta["eyes"]:
        for dx in range(eye):
            for dy in range(eye + 1):
                canvas.put(ox + ex + dx, oy + ey + dy, "y")
        line_y = oy + ey + eye // 2
        for dx in range(-1, eye + 1):
            canvas.put(ox + ex + dx, line_y, "o")


def _hat_line(meta: dict) -> int:
    """The row a hat rests on: the skull, not the tip of the comb."""
    return meta.get("dome_top", meta["head_top"])


def draw_nightcap(canvas: PixelCanvas, meta: dict, ox: int, oy: int) -> None:
    cx = ox + meta["head_cx"]
    top = oy + _hat_line(meta)
    head_w = meta["head_w"]
    brim = max(3, head_w // 2 - 1)
    for x in range(cx - brim, cx + brim + 1):
        canvas.put(x, top, "N")
        canvas.put(x, top - 1, "n")
    cone = max(5, int(round(head_w * 0.55)))
    lean = head_w * 0.40
    for i in range(cone):
        t = i / max(1, cone - 1)
        y = top - 2 - i
        half = int(round((brim - 1) * (1.0 - t)))
        tip_x = int(round(cx - t * lean))
        for x in range(tip_x - half, tip_x + half + 1):
            canvas.put(x, y, "n" if x <= tip_x else "N")
    pom_x = int(round(cx - lean))
    pom_y = top - 2 - cone
    for dx in range(-1, 1):
        for dy in range(-1, 1):
            canvas.put(pom_x + dx, pom_y + dy, "p")


def draw_mortarboard(canvas: PixelCanvas, meta: dict, ox: int, oy: int) -> None:
    cx = ox + meta["head_cx"]
    top = oy + _hat_line(meta) + 2
    head_w = meta["head_w"]
    board_w = head_w + 8
    # The crown tapers with the skull, so it beds into the dome instead of
    # sitting on it as a flat-bottomed block floating over a round head.
    for offset, y in enumerate(range(top, top - 5, -1)):
        half = head_w // 2 - 1 - max(0, 2 - offset)
        for x in range(cx - half, cx + half + 1):
            canvas.put(x, y, "m")
    for x in range(cx - board_w // 2, cx + board_w // 2 + 1):
        canvas.put(x, top - 5, "m")
        canvas.put(x, top - 6, "m")
    tassel_x = cx + board_w // 2 - 1
    for i in range(7):
        canvas.put(tassel_x, top - 5 + i, "c")
    for dx in (-1, 0):
        canvas.put(tassel_x + dx, top + 2, "c")


def draw_book(canvas: PixelCanvas, meta: dict, ox: int, oy: int) -> None:
    chest_x, chest_y = meta["chest"]
    width, height = 15, 9
    x0 = ox + chest_x - width // 2
    y0 = oy + chest_y
    for dx in range(width):
        for dy in range(height):
            edge = dx in (0, width - 1) or dy in (0, height - 1) or dx == width // 2
            canvas.put(x0 + dx, y0 + dy, "o" if edge else "p")


# --------------------------------------------------------------------------
# 3x5 pixel font.  Using this everywhere means no TTF path to go wrong and
# no anti-aliasing to smear the small screen.
# --------------------------------------------------------------------------
FONT: Dict[str, List[str]] = {
    "0": ["###", "#.#", "#.#", "#.#", "###"],
    "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["##.", "..#", ".#.", "#..", "###"],
    "3": ["##.", "..#", ".#.", "..#", "##."],
    "4": ["#.#", "#.#", "###", "..#", "..#"],
    "5": ["###", "#..", "##.", "..#", "##."],
    "6": [".##", "#..", "###", "#.#", "###"],
    "7": ["###", "..#", ".#.", ".#.", ".#."],
    "8": ["###", "#.#", "###", "#.#", "###"],
    "9": ["###", "#.#", "###", "..#", "##."],
    "A": [".#.", "#.#", "###", "#.#", "#.#"],
    "B": ["##.", "#.#", "##.", "#.#", "##."],
    "C": [".##", "#..", "#..", "#..", ".##"],
    "D": ["##.", "#.#", "#.#", "#.#", "##."],
    "E": ["###", "#..", "##.", "#..", "###"],
    "F": ["###", "#..", "##.", "#..", "#.."],
    "G": [".##", "#..", "#.#", "#.#", ".##"],
    "H": ["#.#", "#.#", "###", "#.#", "#.#"],
    "I": ["###", ".#.", ".#.", ".#.", "###"],
    "J": ["..#", "..#", "..#", "#.#", ".#."],
    "K": ["#.#", "#.#", "##.", "#.#", "#.#"],
    "L": ["#..", "#..", "#..", "#..", "###"],
    "M": ["#.#", "###", "###", "#.#", "#.#"],
    "N": ["#.#", "##.", "###", ".##", "#.#"],
    "O": [".#.", "#.#", "#.#", "#.#", ".#."],
    "P": ["##.", "#.#", "##.", "#..", "#.."],
    "Q": [".#.", "#.#", "#.#", "##.", ".##"],
    "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "S": [".##", "#..", ".#.", "..#", "##."],
    "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "U": ["#.#", "#.#", "#.#", "#.#", ".#."],
    "V": ["#.#", "#.#", "#.#", "#.#", ".#."],
    "W": ["#.#", "#.#", "###", "###", "#.#"],
    "X": ["#.#", "#.#", ".#.", "#.#", "#.#"],
    "Y": ["#.#", "#.#", ".#.", ".#.", ".#."],
    "Z": ["###", "..#", ".#.", "#..", "###"],
    ":": [".", "#", ".", "#", "."],
    ".": [".", ".", ".", ".", "#"],
    ",": [".", ".", ".", "#", "#"],
    "-": ["...", "...", "###", "...", "..."],
    "/": ["..#", "..#", ".#.", "#..", "#.."],
    "!": ["#", "#", "#", ".", "#"],
    "?": ["##.", "..#", ".#.", "...", ".#."],
    "+": ["...", ".#.", "###", ".#.", "..."],
    "%": ["#.#", "..#", ".#.", "#..", "#.#"],
    " ": ["..", "..", "..", "..", ".."],
}

GLYPH_HEIGHT = 5
_text_cache: Dict[tuple, Image.Image] = {}
# The cache key holds the string and the colour, and both move constantly:
# the detail screen stamps seconds into the text, and the clock's tint is
# interpolated from a fractional hour.  On a clock meant to stay up for
# months that is an unbounded dictionary, so it gets a ceiling like every
# other cache here.
_TEXT_CACHE_LIMIT = 512


def text_size(text: str, scale: int = 1) -> Tuple[int, int]:
    width = 0
    for index, char in enumerate(text):
        glyph = FONT.get(char.upper(), FONT["?"])
        width += len(glyph[0])
        if index:
            width += 1
    return width * scale, GLYPH_HEIGHT * scale


def render_text(
    text: str,
    scale: int = 1,
    fill: RGB = (255, 255, 255),
    outline: Optional[RGB] = None,
    outline_width: int = 1,
) -> Image.Image:
    """Render text with the pixel font, optionally with an outline.

    The outline is drawn after the upscale, so its width is in screen pixels,
    not font pixels.  Large text needs a wider one to stay legible: a 1px ring
    around a 5x glyph is proportionally five times thinner than around a 1x
    glyph, which is what makes big digits go soft over a bright sky.
    """
    key = (text, scale, fill, outline, outline_width)
    cached = _text_cache.get(key)
    if cached is not None:
        return cached

    raw_w, raw_h = text_size(text, 1)
    mask = Image.new("L", (max(1, raw_w), raw_h), 0)
    mask_px = mask.load()
    cursor = 0
    for char in text:
        glyph = FONT.get(char.upper(), FONT["?"])
        for y, row in enumerate(glyph):
            for x, cell in enumerate(row):
                if cell == "#":
                    mask_px[cursor + x, y] = 255
        cursor += len(glyph[0]) + 1

    mask = mask.resize((mask.width * scale, mask.height * scale), Image.NEAREST)

    if outline is None:
        out = Image.new("RGBA", mask.size, (0, 0, 0, 0))
        out.paste(Image.new("RGBA", mask.size, tuple(fill) + (255,)), (0, 0), mask)
    else:
        pad = max(1, outline_width)
        padded = Image.new("L", (mask.width + 2 * pad, mask.height + 2 * pad), 0)
        padded.paste(mask, (pad, pad))
        ring = padded.filter(ImageFilter.MaxFilter(2 * pad + 1))
        out = Image.new("RGBA", padded.size, (0, 0, 0, 0))
        out.paste(Image.new("RGBA", padded.size, tuple(outline) + (255,)), (0, 0), ring)
        out.paste(Image.new("RGBA", padded.size, tuple(fill) + (255,)), (0, 0), padded)

    if len(_text_cache) >= _TEXT_CACHE_LIMIT:
        _text_cache.clear()
    _text_cache[key] = out
    return out
