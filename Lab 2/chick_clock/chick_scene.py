"""Scene composition and time logic for the Chick Clock.

The screen is split into four independent visual channels so the four time
scales never fight for attention:

    minute        the chick's horizontal position (right 30s, left 30s)
    day           sky gradient, sun/moon arc, and the nightcap
    month / year  the chick's growth stage, egg in September to graduate in June
    focus mode    glasses, a book, and a countdown

Everything is derived from a `datetime` that is passed in, which means the
whole renderer is pure and can be driven by a fast virtual clock for demos or
by a fixed timestamp for previews.  No Raspberry Pi imports live here.
"""

import math
import random
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

from chick_art import (
    PixelCanvas,
    STAGES,
    draw_book,
    draw_closed_eyes,
    draw_glasses,
    draw_mortarboard,
    draw_nightcap,
    growth_stage_count,
    light_tint,
    render_text,
    stage_sprite,
)

RGB = Tuple[int, int, int]

# --------------------------------------------------------------------------
# Layout.  The Mini PiTFT is 135x240 and we rotate it to landscape.
# --------------------------------------------------------------------------
WIDTH = 240
HEIGHT = 135
HORIZON_Y = 100          # where the hills meet the ground
FEET_Y = 118             # the chick stands here, in front of the horizon
MARGIN = 8
ARC_TOP = 20             # highest the sun gets
HUD_Y = 7                # the clock sits top left, which keeps it clear of
                         # the sun: the sun is only ever high when it is also
                         # horizontally centred

# The clock is the one thing readable from across a room, so it gets the
# space.  5 puts "23:30" at 85px wide, clearing the top-right preview tag
# (which starts at x=120) with room to spare; 6 would leave only 10px.
CLOCK_SCALE = 5
CLOCK_OUTLINE_WIDTH = 2
# Minimum perceptual distance between the digits and the sky behind them.
# Calibrated against renders: hours that read well scored 314 and up, the
# mushy sunset hours 88 to 163.
CLOCK_MIN_DISTANCE = 280.0

# Ithaca, NY.  Sunrise/sunset come from the standard solar declination
# approximation, so there is no network call and no extra dependency.
ITHACA_LAT = 42.44
ITHACA_LON = -76.50

BEDTIME_START = 23.0
BEDTIME_END = 6.0

# --------------------------------------------------------------------------
# Colour keyframes, interpolated by fractional hour.
# --------------------------------------------------------------------------
SKY_KEYS: List[Tuple[float, Tuple[RGB, RGB]]] = [
    (0.0, ((11, 16, 38), (35, 48, 92))),
    (5.0, ((28, 32, 74), (92, 72, 112))),
    (6.5, ((96, 112, 172), (246, 162, 138))),
    (8.5, ((126, 200, 245), (205, 235, 251))),
    (12.0, ((79, 179, 240), (191, 231, 251))),
    (16.0, ((111, 190, 239), (213, 234, 247))),
    (18.5, ((232, 120, 90), (247, 192, 107))),
    (20.0, ((122, 74, 130), (226, 140, 110))),
    (22.0, ((30, 34, 78), (60, 60, 105))),
    (24.0, ((11, 16, 38), (35, 48, 92))),
]

LIGHT_KEYS: List[Tuple[float, RGB]] = [
    (0.0, (70, 80, 130)),
    (5.0, (92, 96, 140)),
    (6.5, (235, 175, 150)),
    (8.5, (255, 250, 235)),
    (12.0, (255, 255, 255)),
    (16.0, (255, 248, 230)),
    (18.5, (255, 190, 130)),
    (20.0, (198, 138, 120)),
    (22.0, (100, 100, 150)),
    (24.0, (70, 80, 130)),
]

DIGIT_KEYS: List[Tuple[float, RGB]] = [
    (0.0, (150, 170, 255)),
    (5.0, (168, 182, 255)),
    (6.5, (255, 204, 152)),
    (8.5, (255, 232, 92)),
    (12.0, (255, 246, 124)),
    (16.0, (255, 238, 118)),
    (18.5, (255, 152, 122)),
    (20.0, (255, 172, 202)),
    (22.0, (162, 176, 255)),
    (24.0, (150, 170, 255)),
]

DIGIT_OUTLINE = (48, 34, 16)
# Focus mode keeps its own steady cream instead of the hour tint, so the
# countdown reads as a different thing from the wall clock.
FOCUS_DIGITS = (255, 240, 170)

FAR_HILL = (108, 176, 116)
NEAR_HILL = (72, 152, 76)
GROUND = (124, 186, 70)
GROUND_EDGE = (92, 148, 54)
GRASS = (58, 128, 52)

FAR_PEAKS = [(86, 46, 84), (168, 58, 76), (230, 34, 54)]
NEAR_PEAKS = [(38, 26, 96), (140, 20, 92), (216, 24, 72)]
GRASS_TUFTS = [
    (20, 112, 5),
    (54, 126, 4),
    (92, 107, 6),
    (128, 130, 4),
    (160, 114, 5),
    (196, 124, 5),
    (226, 109, 4),
]

CLOUDS = [(30, 24, 1.0), (118, 15, 0.75), (196, 32, 1.2)]

WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
MONTHS = [
    "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
    "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
]

# September is the egg, June is the graduate.  July keeps the graduate around
# and August resets to a fresh egg waiting for the next cohort.
STAGE_BY_MONTH = {9: 0, 10: 1, 11: 2, 12: 2, 1: 3, 2: 3, 3: 4, 4: 4, 5: 5, 6: 6,
                  7: 6, 8: 0}


# --------------------------------------------------------------------------
# Small colour helpers
# --------------------------------------------------------------------------
def _lerp_rgb(a: RGB, b: RGB, t: float) -> RGB:
    t = max(0.0, min(1.0, t))
    return (
        int(round(a[0] + (b[0] - a[0]) * t)),
        int(round(a[1] + (b[1] - a[1]) * t)),
        int(round(a[2] + (b[2] - a[2]) * t)),
    )


def _interp(keys, hour: float, blend):
    hour %= 24.0
    for index in range(len(keys) - 1):
        h0, v0 = keys[index]
        h1, v1 = keys[index + 1]
        if h0 <= hour <= h1:
            t = (hour - h0) / (h1 - h0) if h1 > h0 else 0.0
            return blend(v0, v1, t)
    return keys[-1][1]


def sky_colours(hour: float) -> Tuple[RGB, RGB]:
    def blend(a, b, t):
        return (_lerp_rgb(a[0], b[0], t), _lerp_rgb(a[1], b[1], t))

    return _interp(SKY_KEYS, hour, blend)


def light_colour(hour: float) -> RGB:
    return _interp(LIGHT_KEYS, hour, _lerp_rgb)


def digit_colour(hour: float) -> RGB:
    return _interp(DIGIT_KEYS, hour, _lerp_rgb)


def colour_distance(a: RGB, b: RGB) -> float:
    """Cheap perceptual RGB distance, the "redmean" approximation.

    Brightness alone is the wrong test for legibility here.  Yellow digits on
    a blue noon sky sit only 0.2 apart in luminance yet read perfectly,
    because the hues oppose; salmon digits on a salmon sunset sit 0.12 apart
    and turn to mush.  This metric scores that sunset four times closer than
    the noon sky, which matches what the screen actually looks like.
    """
    rmean = (a[0] + b[0]) / 2.0
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return math.sqrt(
        (2.0 + rmean / 256.0) * dr * dr
        + 4.0 * dg * dg
        + (2.0 + (255.0 - rmean) / 256.0) * db * db
    )


def legible_on(base: RGB, behind: RGB) -> RGB:
    """`base`, but never sunk into what sits behind it.

    The tinted digits are the nicest part of the HUD and the biggest risk to
    it: through the sunset hours the sky and the digits share a hue, and the
    clock goes soft exactly when the screen looks its best.  Rather than
    hand-picking each keyframe away from its own sky, this keeps the colour
    wherever it already reads and only pushes the few hours that do not,
    which also covers the interpolated minutes in between.
    """
    if colour_distance(base, behind) >= CLOCK_MIN_DISTANCE:
        return base
    # Bleach toward white, and only that.  Darkening scores better against a
    # bright sunset, but it turns the digits into a dark blob that swallows
    # its own outline, and against the grey-lavender sky around 17:00 the two
    # strategies trade places -- so the clock would flip from light to dark
    # and back within one evening.  That flicker is worse than a little less
    # contrast, so the HUD stays light all day and takes what it can get.
    best, best_distance = base, colour_distance(base, behind)
    for step in range(1, 11):
        candidate = _lerp_rgb(base, (255, 255, 255), step / 10.0)
        distance = colour_distance(candidate, behind)
        if distance > best_distance:
            best, best_distance = candidate, distance
        if distance >= CLOCK_MIN_DISTANCE:
            return candidate
    return best


def legible_digit_colour(hour: float, behind: RGB) -> RGB:
    return legible_on(digit_colour(hour), behind)


def _apply_light(base: RGB, light: RGB, blend: float = 0.30) -> RGB:
    """Light the terrain by multiplying, then bleed the light colour in.

    The bleed is what turns the same green hills tan at sunset and blue at
    night, so only one set of hill geometry is ever needed.
    """
    out = []
    for index in range(3):
        lit = base[index] * light[index] / 255.0
        value = lit * (1.0 - blend) + light[index] * blend * 0.55
        out.append(max(0, min(255, int(round(value)))))
    return (out[0], out[1], out[2])


def _cloud_colour(light: RGB) -> RGB:
    return (
        min(255, int(round(238 * light[0] / 255.0 + 17))),
        min(255, int(round(238 * light[1] / 255.0 + 17))),
        min(255, int(round(238 * light[2] / 255.0 + 17))),
    )


# --------------------------------------------------------------------------
# Sun and moon
# --------------------------------------------------------------------------
def _utc_offset_hours(when: datetime) -> float:
    """Local UTC offset on `when`, not today.

    Asking the naive datetime itself is what makes this respect daylight
    saving; using datetime.now() would shift every winter date by an hour.
    """
    offset = when.astimezone().utcoffset()
    return offset.total_seconds() / 3600.0 if offset is not None else -5.0


# Sunrise and sunset are defined by the sun's upper limb, which refraction
# puts a little below the geometric horizon.
_HORIZON_ALTITUDE = math.radians(-0.833)


def sun_times(when: datetime) -> Tuple[float, float]:
    """Approximate sunrise and sunset as local clock hours.

    Accurate to within about ten minutes for Ithaca, which is plenty for
    tinting a sky, and needs no network call or extra dependency.
    """
    day = when.timetuple().tm_yday
    angle = math.radians(360.0 / 365.0 * (day - 81))
    declination = math.radians(23.45) * math.sin(angle)

    # Equation of time, in minutes.  Without it sunset drifts by a quarter of
    # an hour across the year.
    equation = (
        9.87 * math.sin(2 * angle)
        - 7.53 * math.cos(angle)
        - 1.5 * math.sin(angle)
    )

    latitude = math.radians(ITHACA_LAT)
    cos_hour_angle = (
        math.sin(_HORIZON_ALTITUDE)
        - math.sin(latitude) * math.sin(declination)
    ) / (math.cos(latitude) * math.cos(declination))
    cos_hour_angle = max(-1.0, min(1.0, cos_hour_angle))
    half_day = math.degrees(math.acos(cos_hour_angle)) / 15.0

    solar_noon = (
        12.0 - ITHACA_LON / 15.0 + _utc_offset_hours(when) - equation / 60.0
    )
    return solar_noon - half_day, solar_noon + half_day


def night_factor(hour: float, sunrise: float, sunset: float) -> float:
    """0 during the day, ramping to 1 about ninety minutes after dark."""
    if sunrise <= hour <= sunset:
        return 0.0
    if hour > sunset:
        distance = min(hour - sunset, 24.0 - hour + sunrise)
    else:
        distance = min(sunrise - hour, hour + 24.0 - sunset)
    return max(0.0, min(1.0, distance / 1.5))


# --------------------------------------------------------------------------
# Calendar
# --------------------------------------------------------------------------
def growth_stage(when: datetime) -> int:
    stage = STAGE_BY_MONTH[when.month]
    return min(stage, growth_stage_count() - 1)


def school_year_start(when: datetime) -> date:
    year = when.year if when.month >= 8 else when.year - 1
    return date(year, 9, 1)


def school_year_end(when: datetime) -> date:
    return date(school_year_start(when).year + 1, 6, 15)


def school_day(when: datetime) -> Tuple[int, int]:
    start = school_year_start(when)
    end = school_year_end(when)
    total = (end - start).days + 1
    index = (when.date() - start).days + 1
    return max(1, min(total, index)), total


def is_bedtime(hour: float) -> bool:
    return hour >= BEDTIME_START or hour < BEDTIME_END


# --------------------------------------------------------------------------
# Scene preview
#
# Fixed moments worth showing on demand: a single day from dawn through to
# the nightcap, then the chick at every growth stage.  These are plain
# datetimes fed to the ordinary renderer, so a preview is the real clock
# drawing a real moment rather than a demo path that could drift from what
# ships.  The growth scenes sit at mid morning to keep the sky out of the way.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PreviewScene:
    label: str
    month: int
    day: int
    hour: int
    minute: int
    caption_month: bool = False


PREVIEW_SCENES: Tuple["PreviewScene", ...] = (
    PreviewScene("BEDTIME", 4, 15, 23, 30),
    # Sunrise is 06:27 and sunset 19:46 on this date, so these sit a little
    # inside both: exactly on the minute the sun is still under the horizon
    # and the shot loses the one thing it is meant to show.
    PreviewScene("DAWN", 4, 15, 6, 40),
    PreviewScene("MORNING", 4, 15, 9, 0),
    PreviewScene("NOON", 4, 15, 12, 0),
    PreviewScene("SUNSET", 4, 15, 19, 15),
    PreviewScene("DUSK", 4, 15, 20, 30),
    PreviewScene("NIGHT", 4, 15, 22, 0),
    PreviewScene("EGG", 9, 15, 9, 30, True),
    PreviewScene("CRACKING", 10, 15, 9, 30, True),
    PreviewScene("HATCHLING", 11, 15, 9, 30, True),
    PreviewScene("CHICK", 1, 15, 9, 30, True),
    PreviewScene("FLEDGLING", 3, 15, 9, 30, True),
    PreviewScene("YOUNG HEN", 5, 15, 9, 30, True),
    PreviewScene("GRADUATE", 6, 10, 9, 30, True),
)


def preview_datetime(scene: PreviewScene, real: datetime) -> datetime:
    """Place a scene in the running school year, keeping live seconds.

    Live seconds matter: the sky and the growth stage hold still, but the
    chick has to keep pacing out the minute or the screen looks frozen.
    """
    start = school_year_start(real)
    year = start.year if scene.month >= 9 else start.year + 1
    return datetime(
        year, scene.month, scene.day, scene.hour, scene.minute,
        real.second, real.microsecond,
    )


def walk_x(when: datetime, sprite_width: int) -> int:
    """Right for the first 30 seconds, back left for the next 30."""
    second = when.second + when.microsecond / 1_000_000.0
    span = max(1, WIDTH - 2 * MARGIN - sprite_width)
    t = second / 30.0 if second < 30.0 else (60.0 - second) / 30.0
    return MARGIN + int(round(max(0.0, min(1.0, t)) * span))


def _hhmm(value: float) -> str:
    value %= 24.0
    hours = int(value)
    minutes = int(round((value - hours) * 60))
    if minutes == 60:
        hours, minutes = (hours + 1) % 24, 0
    return "%02d:%02d" % (hours, minutes)


# --------------------------------------------------------------------------
# Cached background layers
# --------------------------------------------------------------------------
def _profile(peaks) -> List[int]:
    heights = [0] * WIDTH
    for centre, peak, spread in peaks:
        for x in range(WIDTH):
            d = (x - centre) / (spread / 2.0)
            if -1.0 < d < 1.0:
                value = int(round(peak * math.cos(d * math.pi / 2.0) ** 1.6))
                if value > heights[x]:
                    heights[x] = value
    return heights


FAR_PROFILE = _profile(FAR_PEAKS)
NEAR_PROFILE = _profile(NEAR_PEAKS)

_star_rng = random.Random(7)
STARS = [
    (
        _star_rng.randrange(4, WIDTH - 4),
        _star_rng.randrange(3, HORIZON_Y - 36),
        _star_rng.uniform(0.45, 1.0),
    )
    for _ in range(46)
]

_confetti_rng = random.Random(21)
CONFETTI = [
    (
        _confetti_rng.randrange(8, WIDTH - 8),
        _confetti_rng.randrange(0, HEIGHT),
        _confetti_rng.choice(
            [(255, 214, 92), (255, 128, 128), (140, 220, 255), (190, 255, 160)]
        ),
    )
    for _ in range(30)
]

_CACHE_LIMIT = 24
_sky_cache: Dict[tuple, Image.Image] = {}
_terrain_cache: Dict[tuple, Image.Image] = {}


def _quant(colour: RGB, step: int = 6) -> tuple:
    return (colour[0] // step, colour[1] // step, colour[2] // step)


def sky_layer(top: RGB, bottom: RGB) -> Image.Image:
    key = (_quant(top), _quant(bottom))
    cached = _sky_cache.get(key)
    if cached is None:
        image = Image.new("RGB", (WIDTH, HEIGHT), bottom)
        draw = ImageDraw.Draw(image)
        for y in range(HORIZON_Y + 1):
            draw.line(
                (0, y, WIDTH, y), fill=_lerp_rgb(top, bottom, y / float(HORIZON_Y))
            )
        if len(_sky_cache) > _CACHE_LIMIT:
            _sky_cache.clear()
        _sky_cache[key] = image
        cached = image
    return cached.copy()


def terrain_layer(light: RGB) -> Image.Image:
    key = _quant(light, 8)
    cached = _terrain_cache.get(key)
    if cached is not None:
        return cached

    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    far = _apply_light(FAR_HILL, light) + (255,)
    near = _apply_light(NEAR_HILL, light) + (255,)
    ground = _apply_light(GROUND, light) + (255,)
    edge = _apply_light(GROUND_EDGE, light) + (255,)
    grass = _apply_light(GRASS, light) + (255,)

    for x in range(WIDTH):
        height = FAR_PROFILE[x]
        if height:
            draw.line((x, HORIZON_Y - height, x, HORIZON_Y), fill=far)
    for x in range(WIDTH):
        height = NEAR_PROFILE[x]
        if height:
            draw.line((x, HORIZON_Y - height, x, HORIZON_Y), fill=near)
    draw.rectangle((0, HORIZON_Y, WIDTH - 1, HEIGHT - 1), fill=ground)
    draw.line((0, HORIZON_Y, WIDTH - 1, HORIZON_Y), fill=edge)
    for x, y, height in GRASS_TUFTS:
        draw.line((x, y, x, y - height), fill=grass)
        draw.line((x - 2, y, x - 1, y - height + 2), fill=grass)
        draw.line((x + 2, y, x + 1, y - height + 2), fill=grass)

    if len(_terrain_cache) > _CACHE_LIMIT:
        _terrain_cache.clear()
    _terrain_cache[key] = image
    return image


def _draw_stars(canvas: PixelCanvas, night: float) -> None:
    for x, y, brightness in STARS:
        value = int(round(235 * night * brightness))
        canvas.put(x, y, (value, value, min(255, value + 18)))


def _draw_celestial(draw, hour: float, sunrise: float, sunset: float) -> None:
    daytime = sunrise <= hour <= sunset
    if daytime:
        t = (hour - sunrise) / max(0.01, sunset - sunrise)
        radius = 11
        arc = math.sin(math.pi * t)
        body = _lerp_rgb((255, 150, 70), (255, 241, 165), min(1.0, arc * 1.6))
        halo = _lerp_rgb(body, (255, 255, 255), 0.35)
    else:
        night_length = (24.0 - sunset) + sunrise
        t = ((hour - sunset) % 24.0) / max(0.01, night_length)
        radius = 8
        arc = math.sin(math.pi * t)
        body = (238, 238, 226)
        halo = (196, 202, 228)

    x = int(round(20 + t * (WIDTH - 40)))
    y = int(round(HORIZON_Y - 8 - arc * (HORIZON_Y - ARC_TOP - 8)))
    draw.ellipse((x - radius - 2, y - radius - 2, x + radius + 2, y + radius + 2),
                 fill=halo)
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=body)
    if not daytime:
        draw.ellipse((x - 4, y - 3, x - 1, y), fill=(213, 213, 203))
        draw.ellipse((x + 1, y + 1, x + 4, y + 4), fill=(213, 213, 203))


def _draw_clouds(draw, hour: float, light: RGB) -> None:
    colour = _cloud_colour(light)
    for x0, y, scale in CLOUDS:
        x = (x0 + hour * 5.0) % (WIDTH + 90) - 45
        w = int(round(26 * scale))
        h = int(round(11 * scale))
        draw.ellipse((int(x), y, int(x) + w, y + h), fill=colour)
        draw.ellipse(
            (int(x + w * 0.30), int(y - h * 0.45), int(x + w * 0.85), int(y + h * 0.7)),
            fill=colour,
        )
        draw.ellipse(
            (int(x + w * 0.60), int(y + h * 0.10), int(x + w * 1.25), y + h),
            fill=colour,
        )


def background(when: datetime) -> Tuple[Image.Image, dict]:
    hour = when.hour + when.minute / 60.0 + when.second / 3600.0
    top, bottom = sky_colours(hour)
    light = light_colour(hour)
    sunrise, sunset = sun_times(when)
    night = night_factor(hour, sunrise, sunset)

    image = sky_layer(top, bottom)
    if night > 0.02:
        _draw_stars(PixelCanvas(image), night)
    draw = ImageDraw.Draw(image)
    _draw_celestial(draw, hour, sunrise, sunset)
    _draw_clouds(draw, hour, light)
    terrain = terrain_layer(light)
    image.paste(terrain, (0, 0), terrain)

    return image, {
        "hour": hour,
        "light": light,
        "night": night,
        "sunrise": sunrise,
        "sunset": sunset,
        # The clock sits on this, and has to stay readable against it.
        "sky_top": top,
    }


# --------------------------------------------------------------------------
# Frame composition
# --------------------------------------------------------------------------
@dataclass
class UiState:
    focus_remaining: Optional[float] = None
    focus_total: float = 30 * 60.0
    detail: bool = False
    celebrate: Optional[float] = None
    celebrate_total: float = 3.0
    demo_label: Optional[str] = None
    freeze_walk: bool = False
    # Caption the month.  Separate from freeze_walk, because a scene preview
    # wants the caption while the chick keeps pacing.
    show_month: bool = False
    step: int = 0
    # 1-12 while the hour is striking; the overlay then shows 7:00pm, not 19:00.
    hour_strike: Optional[int] = None

    @property
    def celebrate_progress(self) -> float:
        """0 to 1 through the celebration.

        Both the hop and the confetti need this, and both used to divide by
        celebrate_total themselves, which made a caller-supplied 0 a crash
        in two places at once.
        """
        if self.celebrate is None:
            return 0.0
        return max(0.0, min(1.0, self.celebrate / max(0.001, self.celebrate_total)))


def render_frame(when: datetime, ui: Optional[UiState] = None) -> Image.Image:
    ui = ui or UiState()
    image, env = background(when)
    draw = ImageDraw.Draw(image)

    stage_index = growth_stage(when)
    stage = STAGES[stage_index]
    tint = light_tint(env["light"])
    sprite, meta = stage_sprite(stage_index, ui.step, tint)
    sprite_w, sprite_h = sprite.size

    focusing = ui.focus_remaining is not None
    celebrating = ui.celebrate is not None
    bedtime = is_bedtime(env["hour"]) and not focusing

    parked = focusing or celebrating or ui.freeze_walk
    if parked:
        sprite_x = (WIDTH - sprite_w) // 2
    else:
        sprite_x = walk_x(when, sprite_w)
    sprite_y = FEET_Y - sprite_h
    if not parked and not stage.walks:
        # The egg and hatchling stages have no legs, so they rock along by a
        # pixel instead of stepping.  They still have to cross the screen:
        # the minute is the one channel that must never go quiet.
        sprite_y -= ui.step
    if celebrating:
        hop = abs(math.sin(math.pi * ui.celebrate_progress * 6.0))
        sprite_y -= int(round(8 * hop))

    _draw_minute_ticks(draw, when, sprite_w, env["light"])
    image.paste(sprite, (sprite_x, sprite_y), sprite)
    canvas = PixelCanvas(image, tint=tint)

    if stage.has_face:
        if focusing:
            draw_glasses(canvas, meta, sprite_x, sprite_y)
        elif bedtime:
            draw_closed_eyes(canvas, meta, sprite_x, sprite_y)
    if bedtime:
        draw_nightcap(canvas, meta, sprite_x, sprite_y)
    elif stage.name == "GRADUATE":
        draw_mortarboard(canvas, meta, sprite_x, sprite_y)
    if focusing:
        draw_book(canvas, meta, sprite_x, sprite_y)

    if ui.detail:
        _draw_detail(image, when, env, stage)
        if ui.hour_strike:
            _draw_hour_strike(image, when)
        return image

    if focusing:
        _draw_focus_hud(image, draw, ui, env)
    elif celebrating:
        _draw_celebration(image, ui)
    elif not ui.hour_strike:
        label = "%d:%02d" % (when.hour, when.minute)
        glyph = render_text(
            label, CLOCK_SCALE,
            legible_digit_colour(env["hour"], env["sky_top"]), DIGIT_OUTLINE,
            outline_width=CLOCK_OUTLINE_WIDTH,
        )
        image.paste(glyph, (MARGIN - CLOCK_OUTLINE_WIDTH, HUD_Y), glyph)

    if ui.demo_label:
        tag = render_text(ui.demo_label, 2, (255, 214, 92), (50, 32, 12))
        image.paste(tag, (WIDTH - tag.width - 4, 4), tag)
    if ui.show_month or ui.freeze_walk:
        month = render_text(
            "%s %d" % (MONTHS[when.month - 1], when.year), 2, (255, 246, 210),
            (44, 30, 14),
        )
        image.paste(month, ((WIDTH - month.width) // 2, HEIGHT - month.height - 5),
                    month)
    else:
        _draw_stage_caption(image, when, stage)

    if ui.hour_strike:
        _draw_hour_strike(image, when)

    return image


def _draw_minute_ticks(draw, when: datetime, sprite_w: int, light: RGB) -> None:
    """Four marks along the chick's path, one every ten seconds of the outbound.

    The return trip retraces the same marks, so the ground itself is the
    minute: left is :00, right is :30.
    """
    second = when.second + when.microsecond / 1_000_000.0
    outbound = second if second <= 30.0 else 60.0 - second
    nearest = int(round(outbound / 10.0) * 10)
    if nearest > 30:
        nearest = 30
    dim_fill = _apply_light((186, 176, 120), light)
    hot_fill = _apply_light((255, 232, 110), light)
    ink = _apply_light((52, 38, 20), light)
    y = FEET_Y + 2
    for mark in (0, 10, 20, 30):
        dummy = datetime(2000, 1, 1, 0, 0, mark)
        x = walk_x(dummy, sprite_w) + sprite_w // 2
        fill = hot_fill if mark == nearest else dim_fill
        # A 3x3 bead with a dark rim, or the active one is a 5x3 bar so the
        # minute position can be read from across a table.
        if mark == nearest:
            draw.rectangle((x - 3, y, x + 3, y + 3), fill=ink)
            draw.rectangle((x - 2, y + 1, x + 2, y + 2), fill=fill)
        else:
            draw.rectangle((x - 1, y, x + 1, y + 2), fill=ink)
            draw.rectangle((x, y + 1, x, y + 1), fill=fill)


def _draw_stage_caption(image: Image.Image, when: datetime, stage) -> None:
    """Name the year channel without covering the ground."""
    label = "%s / %s" % (MONTHS[when.month - 1][:3], stage.name)
    glyph = render_text(label, 3, (255, 250, 210), (40, 24, 10))
    x = (WIDTH - glyph.width) // 2
    y = HEIGHT - glyph.height - 3
    image.paste(glyph, (x, y), glyph)


def _twelve_hour_parts(when: datetime):
    hour = when.hour % 12 or 12
    suffix = "AM" if when.hour < 12 else "PM"
    return "%d:%02d" % (hour, when.minute), suffix


def _draw_hour_strike(image: Image.Image, when: datetime) -> None:
    """On the hour, spell the time the way people say it: 7:00pm, not 19:00."""
    shade = Image.new("RGBA", (WIDTH, HEIGHT), (18, 12, 8, 170))
    image.paste(shade, (0, 0), shade)
    clock, suffix = _twelve_hour_parts(when)
    num = render_text(
        clock, 7, (255, 236, 130), (48, 28, 10), outline_width=2
    )
    tag = render_text(
        suffix, 4, (255, 246, 210), (40, 24, 10), outline_width=2
    )
    total_h = num.height + 6 + tag.height
    y0 = max(10, (HEIGHT - total_h) // 2 - 6)
    image.paste(num, ((WIDTH - num.width) // 2, y0), num)
    image.paste(tag, ((WIDTH - tag.width) // 2, y0 + num.height + 6), tag)


def _draw_focus_hud(image: Image.Image, draw, ui: UiState, env: dict) -> None:
    remaining = max(0, int(math.ceil(ui.focus_remaining)))
    glyph = render_text(
        "%d:%02d" % (remaining // 60, remaining % 60), CLOCK_SCALE,
        legible_on(FOCUS_DIGITS, env["sky_top"]), DIGIT_OUTLINE,
        outline_width=CLOCK_OUTLINE_WIDTH,
    )
    image.paste(glyph, (MARGIN - CLOCK_OUTLINE_WIDTH, HUD_Y - 1), glyph)

    done = 1.0 - max(0.0, min(1.0, ui.focus_remaining / max(1.0, ui.focus_total)))
    bar_w = 92
    x0 = MARGIN
    y0 = HUD_Y - 1 + glyph.height + 4
    draw.rectangle((x0 - 1, y0 - 1, x0 + bar_w, y0 + 3), fill=(52, 38, 20))
    if done > 0:
        draw.rectangle((x0, y0, x0 + int(bar_w * done), y0 + 2), fill=(255, 214, 92))
    tag = render_text("FOCUS", 2, (255, 244, 200), (52, 38, 20))
    image.paste(tag, (MARGIN, y0 + 7), tag)


def _draw_celebration(image: Image.Image, ui: UiState) -> None:
    t = ui.celebrate_progress
    if t < 0.12:
        alpha = int(round(210 * (1.0 - t / 0.12)))
        flash = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 240))
        image.paste(flash, (0, 0), Image.new("L", (WIDTH, HEIGHT), alpha))
    canvas = PixelCanvas(image)
    for x, y0, colour in CONFETTI:
        y = (y0 + int(t * 190)) % (HEIGHT + 24) - 12
        for dx in range(2):
            for dy in range(3):
                canvas.put(x + dx, y + dy, colour)
    glyph = render_text("DONE!", 4, (255, 244, 180), (60, 40, 16))
    image.paste(glyph, ((WIDTH - glyph.width) // 2, 12), glyph)


def _draw_detail(image: Image.Image, when: datetime, env: dict, stage) -> None:
    shade = Image.new("RGBA", (WIDTH, HEIGHT), (14, 12, 26, 232))
    image.paste(shade, (0, 0), shade)

    big = render_text(
        "%02d:%02d:%02d" % (when.hour, when.minute, when.second), 4,
        (255, 232, 140), (30, 22, 10),
    )
    image.paste(big, ((WIDTH - big.width) // 2, 12), big)

    index, total = school_day(when)
    lines = [
        "%04d / %02d / %02d   %s"
        % (when.year, when.month, when.day, WEEKDAYS[when.weekday()]),
        "DAY %d OF %d" % (index, total),
        "%s - %s" % (stage.name, stage.months),
        "RISE %s   SET %s" % (_hhmm(env["sunrise"]), _hhmm(env["sunset"])),
    ]
    y = 12 + big.height + 8
    for line in lines:
        glyph = render_text(line, 2, (226, 230, 245), (18, 16, 30))
        image.paste(glyph, ((WIDTH - glyph.width) // 2, y), glyph)
        y += glyph.height + 3
