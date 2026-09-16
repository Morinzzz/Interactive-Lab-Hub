"""
Voice Clock - Lab 2 Part E.

A clock that speaks the time instead of showing it, with a personality that
shifts through the day. Press a button on the MiniPiTFT and it tells you the
time out loud, followed by a short quip written fresh by an LLM.

Design idea, in one line each:
  - the time itself is always built by code (strftime), never by the LLM
  - the quip is written by an LLM, so it is different every time
  - the mood (voice pace, expressiveness, and the face on screen) follows
    the time of day
  - if the network or API is down, it falls back to a small local phrase bank,
    so it never goes silent

Buttons:  A = tell the time    B = say that again    A+B = cycle mood (demo)

Run it with the boot info-screen service stopped, or they fight over the display:
    sudo systemctl stop piscreen.service --now
    python voice_clock.py
"""
import itertools
import math
import os
import queue
import random
import re
import subprocess
import threading
import time
import wave
from collections import deque
from datetime import datetime

import board
import digitalio
from PIL import Image, ImageDraw, ImageFont
import adafruit_rgb_display.st7789 as st7789
from piper import PiperVoice, SynthesisConfig
from openai import OpenAI

VOICE_MODEL = "/home/pi/piper_voices/en_US-lessac-high.onnx"   # best-sounding Piper voice
LLM_MODEL = "inclusionai/ling-3.0-flash-vl:free"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# PipeWire (the audio server) is reached through this path; a service won't
# have it set the way a login shell does, so set it ourselves.
os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")


# ---- Moods --------------------------------------------------------------
# Six time-of-day moods. Each sets how the voice sounds and holds a couple of
# offline fallback lines. lessac-high is a single voice, so the contrast comes
# from pace (length) and expressiveness (noise / noise_w). Nothing is faster
# than 1.02, so even the brisk morning voice stays clear.
#   start_hour, end_hour, name, voice_settings, persona, fallback_quips
MOODS = [
    (0,  5,  "late night",    dict(length=1.45, noise=0.38, noise_w=0.40),
     "barely awake; gently alarmed they are still up",
     ["Nothing good happens at this hour.", "Even I want to go to bed."]),
    (5,  9,  "early morning", dict(length=1.32, noise=0.45, noise_w=0.45),
     "sleepy, slowly waking up, not quite ready",
     ["Let us both pretend to be awake.", "Coffee first, decisions later."]),
    (9,  12, "late morning",  dict(length=1.02, noise=0.72, noise_w=0.62),
     "brisk and alert; nagging them about being late",
     ["You are late for something, probably.", "The day started without you."]),
    (12, 17, "afternoon",     dict(length=1.14, noise=0.60, noise_w=0.52),
     "matter of fact, slightly bored, mid-day lull",
     ["The afternoon is doing its best.", "Still Tuesday somewhere."]),
    (17, 21, "evening",       dict(length=1.26, noise=0.52, noise_w=0.48),
     "winding down, warm, relaxed",
     ["You have done enough for today.", "The hard part of the day is over."]),
    (21, 24, "night",         dict(length=1.38, noise=0.42, noise_w=0.42),
     "quiet; hinting they should sleep soon",
     ["Consider winding down.", "Tomorrow starts sooner than you think."]),
]

TIME_SLOWDOWN = 1.18   # the time is spoken a bit slower than the quip, for clarity
PAUSE_SEC = 0.40       # gap between the time and the quip


def mood_for(now):
    """The mood tuple (name, voice_settings, persona, fallback) for this hour."""
    for start, end, name, voice, persona, fallback in MOODS:
        if start <= now.hour < end:
            return name, voice, persona, fallback
    return MOODS[-1][2:]


# ---- Saying the time ----------------------------------------------------
# The time is turned into words in code so the voice pronounces it correctly
# every time ("two forty five", never "2:45"). This is the part that must
# always be right, so the LLM never touches it.
ONES = ["twelve", "one", "two", "three", "four", "five",
        "six", "seven", "eight", "nine", "ten", "eleven"]
TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty"}
TEENS = {10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen",
         15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen"}

TIME_TEMPLATES = ["It is {t}.", "{t}.", "The time is {t}."]


def minutes_in_words(m):
    if m == 0:
        return ""
    if m < 10:
        return "oh " + ONES[m]
    if m < 20:
        return TEENS[m]
    tens, ones = divmod(m, 10)
    return TENS[tens] + ((" " + ONES[ones]) if ones else "")


def time_in_words(now):
    """A 12-hour time as words, e.g. 'ten thirty' or 'nine o'clock'."""
    hour = ONES[now.hour % 12]
    minute = minutes_in_words(now.minute)
    return f"{hour} {minute}".strip() if minute else f"{hour} o'clock"


def time_phrase(now):
    """The full spoken time line. The wording varies through the day but stays
    the same within a minute, so the rendered audio can be cached and reused."""
    template = TIME_TEMPLATES[(now.hour * 60 + now.minute) % len(TIME_TEMPLATES)]
    return template.format(t=time_in_words(now))


# ---- Writing the quip (LLM) ---------------------------------------------
QUIP_PROMPT = (
    "You write one very short pun or quip for a talking clock. "
    "The clock ALREADY says the time out loud; your line comes straight after it. "
    "So NEVER state, repeat, imply or allude to the time, the hour, the minutes, "
    "or the day. Write at most 10 words reacting to the mood you are given. "
    "Never name the mood. Output ONLY the quip: no quotes, no emoji, "
    "no reasoning, no preamble, no labels."
)

recent_quips = deque(maxlen=5)   # so the model stops repeating itself ("Tick-tock...")


def load_api_key():
    """Read the OpenRouter key. A missing key isn't fatal - the clock just
    runs on its local phrase bank instead of the LLM."""
    try:
        for line in open(os.path.expanduser("~/.voiceclock.env")):
            if line.startswith("OPENROUTER_API_KEY="):
                key = line.split("=", 1)[1].strip()
                if key:
                    return key
    except OSError:
        pass
    print("[no OPENROUTER_API_KEY - running on the local phrase bank only]")
    return None


api_key = load_api_key()
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key) if api_key else None


def clean_text(s):
    """espeak/Piper and the Pi's console choke on smart punctuation, so map the
    common characters to plain ASCII. (Escapes, so it survives any locale.)"""
    for fancy, plain in (("—", " - "), ("–", "-"), ("…", "..."),
                         ("’", "'"), ("‘", "'"),
                         ("“", ""), ("”", ""), (" ", " ")):
        s = s.replace(fancy, plain)
    s = re.sub(r"[^\x20-\x7E]", "", s)
    s = re.sub(r"\s{2,}", " ", s)
    # models sometimes echo the mood back as a prefix ("Brisk and alert: ...")
    s = re.sub(r"^[A-Za-z ,]{3,40}:\s+(?=[A-Z0-9])", "", s)
    return s.strip().strip('"').strip()


def llm_quip(persona):
    """Ask the model for a fresh quip. Returns None on any failure."""
    if client is None:
        return None
    avoid = ""
    if recent_quips:
        avoid = " Do NOT reuse the wording or opening of any of these: " + " / ".join(recent_quips)
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL, max_tokens=80, temperature=1.2,
            extra_body={"reasoning": {"enabled": False}},   # else it burns the tokens thinking
            messages=[{"role": "system", "content": QUIP_PROMPT},
                      {"role": "user", "content": f"Mood: {persona}. Write the quip only." + avoid}],
            timeout=8,
        )
        quip = clean_text(response.choices[0].message.content or "")
        return quip if 3 < len(quip) < 160 else None
    except Exception as e:
        print(f"  [llm failed: {type(e).__name__}] falling back")
        return None


def make_phrase(now, force_mood=None):
    """Pick the mood, then get a quip (LLM, or local fallback).
    force_mood overrides the time of day (used by the mood-demo button).
    Returns (time_line, quip, voice_settings, mood_name, source)."""
    if force_mood is None:
        name, voice, persona, fallback = mood_for(now)
    else:
        _, _, name, voice, persona, fallback = MOODS[force_mood % len(MOODS)]

    time_line = time_phrase(now)

    quip = llm_quip(persona)
    source = "llm"
    if quip is None:
        quip = random.choice([q for q in fallback if q not in recent_quips] or fallback)
        source = "local"

    # if the model slipped a time or clock word into the quip, drop it rather
    # than let it contradict the real time we just said
    if re.search(r"\d|o.clock|past|quarter|half\b", quip, re.I):
        quip = random.choice(fallback)
        source = "local(guard)"

    recent_quips.append(quip)
    return time_line, quip, voice, name, source


# ---- Speech (Piper) -----------------------------------------------------
try:
    voice = PiperVoice.load(VOICE_MODEL)
except Exception as e:
    raise SystemExit(f"cannot load Piper voice {VOICE_MODEL}: {e}")

# Piper (via onnxruntime) is not thread-safe, and both the prefetch thread and
# the main loop synthesize audio, so all synthesis goes through this lock.
render_lock = threading.Lock()

# Spoken-time clips are cached on disk. The same minute recurs every day, so
# each one is synthesized at most once per mood.
CACHE_DIR = "/home/pi/.cache/voiceclock"
CACHE_MAX = 400        # ~30 MB
os.makedirs(CACHE_DIR, exist_ok=True)


def synth(text, voice_settings, path, slower=1.0):
    """Render text to a wav file with the given voice settings."""
    cfg = SynthesisConfig(length_scale=voice_settings["length"] * slower,
                          noise_scale=voice_settings["noise"],
                          noise_w_scale=voice_settings["noise_w"])
    with render_lock:
        with wave.open(path, "wb") as w:
            voice.synthesize_wav(text, w, syn_config=cfg)


def read_wav(path):
    with wave.open(path) as w:
        return w.getparams(), w.readframes(w.getnframes())


def prune_cache():
    """Keep the time-clip cache from growing forever - drop the oldest files."""
    try:
        files = [os.path.join(CACHE_DIR, f) for f in os.listdir(CACHE_DIR)]
        for f in sorted(files, key=os.path.getmtime)[:len(files) - CACHE_MAX]:
            try:
                os.remove(f)
            except OSError:
                pass
    except OSError:
        pass


def render_quip(quip, voice_settings, path):
    """Render a quip to a wav. Quips never mention the time, so they keep
    forever - the prefetch thread renders them ahead of the button press."""
    synth(quip, voice_settings, path)
    return path


def time_clip(time_line, voice_settings, mood_name):
    """The wav for this minute's time line, from cache or freshly rendered."""
    key = re.sub(r"[^a-z0-9]+", "_", f"{mood_name}_{time_line}".lower()).strip("_")
    path = os.path.join(CACHE_DIR, key + ".wav")
    if not os.path.exists(path):
        synth(time_line, voice_settings, path, slower=TIME_SLOWDOWN)
        prune_cache()
    return path


def join_wavs(time_path, quip_path, out_path):
    """Splice time + a short pause + quip into one wav. This is a byte copy,
    so it's instant - the slow synthesis already happened."""
    params, time_frames = read_wav(time_path)
    _, quip_frames = read_wav(quip_path)
    silence = b"\x00" * int(params.framerate * PAUSE_SEC) * params.sampwidth * params.nchannels
    with wave.open(out_path, "wb") as out:
        out.setparams(params)
        out.writeframes(time_frames + silence + quip_frames)
    return out_path


def build_utterance(now, quip_path, voice_settings, mood_name, out_path):
    """Combine the CURRENT time with an already-rendered quip."""
    time_line = time_phrase(now)
    join_wavs(time_clip(time_line, voice_settings, mood_name), quip_path, out_path)
    return out_path, time_line


# ---- Audio output -------------------------------------------------------
def find_speaker():
    """Prefer a USB speaker; fall back to whatever the default sink is.
    Checked on every play, so unplugging the speaker degrades gracefully."""
    try:
        sinks = subprocess.run(["pactl", "list", "short", "sinks"],
                               capture_output=True, text=True, timeout=4).stdout
        for line in sinks.splitlines():
            if "alsa_output.usb" in line:
                return line.split()[1]
    except Exception:
        pass
    return None


def play_command(path):
    speaker = find_speaker()
    return ["paplay"] + (["--device", speaker] if speaker else []) + [path]


# ---- Prefetch thread ----------------------------------------------------
# The high-quality voice takes ~2s to synthesize, so we do the LLM call and
# the audio render ahead of time. A button press then just plays a finished wav.
ready = queue.Queue(maxsize=2)
quip_buffers = itertools.cycle([f"/tmp/vc_{i}.wav" for i in range(5)])
mood_override = None            # None = follow the real clock
drain_requested = threading.Event()   # set when the mood changes, to toss stale renders


def prefetch_loop():
    while True:
        try:
            if drain_requested.is_set():
                while not ready.empty():
                    try:
                        ready.get_nowait()
                    except queue.Empty:
                        break
                drain_requested.clear()

            if not ready.full():
                _, quip, voice_settings, mood_name, source = make_phrase(datetime.now(), mood_override)
                path = render_quip(quip, voice_settings, next(quip_buffers))
                ready.put((path, quip, voice_settings, mood_name, source))

            # keep this minute's time clip warm, so pressing A is a pure splice
            now = datetime.now()
            if mood_override is None:
                mood_name, voice_settings, _, _ = mood_for(now)
            else:
                mood_name, voice_settings = MOODS[mood_override][2], MOODS[mood_override][3]
            time_clip(time_phrase(now), voice_settings, mood_name)
        except Exception as e:
            print(f"[prefetch error: {type(e).__name__}: {e}]")
            time.sleep(1)
        time.sleep(0.3)


threading.Thread(target=prefetch_loop, daemon=True).start()


# ---- Display: the face --------------------------------------------------
# No digits on screen - the time is spoken, not shown. The display carries the
# mood: a simple face on a background colour that drifts through the day.
cs_pin = digitalio.DigitalInOut(board.D5)     # GPIO5, not CE0 (that's the SPI driver's)
dc_pin = digitalio.DigitalInOut(board.D25)
disp = st7789.ST7789(board.SPI(), cs=cs_pin, dc=dc_pin, rst=None, baudrate=64000000,
                     width=135, height=240, x_offset=53, y_offset=40)
backlight = digitalio.DigitalInOut(board.D22)
backlight.switch_to_output()
backlight.value = True
button_a = digitalio.DigitalInOut(board.D23)
button_b = digitalio.DigitalInOut(board.D24)
button_a.switch_to_input(pull=digitalio.Pull.UP)
button_b.switch_to_input(pull=digitalio.Pull.UP)

SCREEN_W, SCREEN_H = disp.height, disp.width   # 240 x 135, landscape
canvas = Image.new("RGB", (SCREEN_W, SCREEN_H))
draw = ImageDraw.Draw(canvas)
font = ImageFont.truetype(FONT_PATH, 13)

# How each mood's face looks and moves:
#   bg/fg     background and face colour
#   eye       resting eye openness (0 shut .. 1 wide)
#   mouth     resting mouth curve (-1 frown .. +1 smile)
#   lid       droopy upper eyelid (0 none .. 1 heavy) - carries sleepiness
#   talk_amp  how wide the mouth opens while speaking
#   talk_rate how fast the mouth flaps
#   mouth_w   mouth width in pixels
# A sleepy clock mumbles; an alert one enunciates.
FACE = {
    "late night":    dict(bg=(10, 12, 34),    fg=(120, 140, 210), eye=0.18, mouth=-0.45,
                          lid=0.55, talk_amp=0.30, talk_rate=0.55, mouth_w=40),
    "early morning": dict(bg=(46, 34, 60),    fg=(226, 170, 150), eye=0.40, mouth=-0.15,
                          lid=0.35, talk_amp=0.45, talk_rate=0.70, mouth_w=46),
    "late morning":  dict(bg=(120, 175, 225), fg=(20, 40, 70),    eye=1.00, mouth=+0.75,
                          lid=0.00, talk_amp=1.00, talk_rate=1.45, mouth_w=64),
    "afternoon":     dict(bg=(150, 190, 210), fg=(25, 45, 65),    eye=0.82, mouth=+0.30,
                          lid=0.05, talk_amp=0.80, talk_rate=1.05, mouth_w=56),
    "evening":       dict(bg=(196, 110, 60),  fg=(45, 25, 20),    eye=0.62, mouth=+0.45,
                          lid=0.15, talk_amp=0.65, talk_rate=0.90, mouth_w=52),
    "night":         dict(bg=(26, 28, 62),    fg=(150, 165, 225), eye=0.34, mouth=+0.05,
                          lid=0.45, talk_amp=0.40, talk_rate=0.65, mouth_w=44),
}


def draw_face(mood_name, mouth_open=0.0, blink=False, subtitle="", banner=""):
    """Draw the face. mouth_open (0..1) animates the mouth while speaking;
    blink briefly shuts the eyes."""
    look = FACE.get(mood_name, FACE["afternoon"])
    bg, fg = look["bg"], look["fg"]
    draw.rectangle((0, 0, SCREEN_W, SCREEN_H), fill=bg)

    cx, cy = SCREEN_W // 2, SCREEN_H // 2 - 14
    eye_dx, eye_r = 44, 19
    # the eyes lift a little while talking - the clock perks up as it speaks
    openness = 0.06 if blink else min(1.0, look["eye"] + 0.18 * mouth_open)
    for side in (-1, 1):
        ex = cx + side * eye_dx
        eh = max(3, int(eye_r * 2 * openness))
        draw.ellipse((ex - eye_r, cy - eh // 2, ex + eye_r, cy + eh // 2), fill=fg)
        if openness > 0.35 and not blink:                       # pupil highlight
            draw.ellipse((ex - 5, cy - 5, ex + 5, cy + 5), fill=bg)
        if look["lid"] > 0.01 and not blink:                    # droopy eyelid
            draw.rectangle((ex - eye_r - 1, cy - eh // 2 - 1,
                            ex + eye_r + 1, cy - eh // 2 + int(eh * look["lid"])), fill=bg)

    # mouth: a curved arc at rest, an opening ellipse while speaking
    mouth_w = look["mouth_w"]
    my = cy + 30
    if mouth_open > 0.04:
        mh = int(5 + 28 * mouth_open)
        draw.ellipse((cx - mouth_w // 2, my - mh // 2, cx + mouth_w // 2, my + mh // 2), fill=fg)
    else:
        smiling = look["mouth"] >= 0
        draw.arc((cx - mouth_w // 2, my - 16, cx + mouth_w // 2, my + 16),
                 start=(20 if smiling else 200), end=(160 if smiling else 340),
                 fill=fg, width=4)

    if banner:
        draw.text(((SCREEN_W - draw.textlength(banner, font=font)) / 2, 6),
                  banner, font=font, fill=fg)
    if subtitle:
        for i, line in enumerate(subtitle.split("\n")[:2]):
            draw.text(((SCREEN_W - draw.textlength(line, font=font)) / 2, SCREEN_H - 30 + i * 15),
                      line, font=font, fill=fg)
    disp.image(canvas, 90)


def wrap(text, width=34):
    """Wrap a quip to at most two lines for the subtitle."""
    lines, current = [], ""
    for word in text.split():
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    lines.append(current)
    return "\n".join(lines[:2])


def wav_seconds(path):
    with wave.open(path) as w:
        return w.getnframes() / float(w.getframerate())


def speak(path, mood_name, subtitle=""):
    """Play a wav and animate the mouth for exactly as long as it lasts."""
    look = FACE.get(mood_name, FACE["afternoon"])
    amp, rate = look["talk_amp"], look["talk_rate"]
    duration = wav_seconds(path)
    player = subprocess.Popen(play_command(path))
    start = time.time()
    while player.poll() is None:
        t = time.time() - start
        # two overlapping sines look more like speech than a steady flap;
        # the mood sets how wide the mouth opens and how fast
        flap = 0.5 + 0.5 * math.sin(t * 17.0 * rate) * math.sin(t * 5.3 * rate)
        draw_face(mood_name, mouth_open=amp * max(0.0, flap), subtitle=subtitle)
        time.sleep(0.05)
        if t > duration + 2:
            break
    draw_face(mood_name, mouth_open=0.0, subtitle=subtitle)


# ---- Buttons ------------------------------------------------------------
COMBO_WINDOW = 0.28   # window to catch A and B pressed together


def buttons_down():
    return (not button_a.value), (not button_b.value)   # buttons are active-low


def read_gesture():
    """Wait for a press to settle and return 'A', 'B', 'AB', or None."""
    a, b = buttons_down()
    if not (a or b):
        return None
    start = time.time()
    while time.time() - start < COMBO_WINDOW:   # give the other button a chance to join
        na, nb = buttons_down()
        a, b = a or na, b or nb
        if a and b:
            break
        time.sleep(0.02)
    while any(buttons_down()):                   # wait for release
        time.sleep(0.03)
    return "AB" if (a and b) else ("A" if a else "B")


def current_mood_name():
    if mood_override is not None:
        return MOODS[mood_override][2]
    return mood_for(datetime.now())[0]


# ---- Main loop ----------------------------------------------------------
last_utterance = None    # (path, time_line, quip, mood) - for the repeat button
next_blink = time.time() + random.uniform(2, 6)

print("Voice clock running (no digits on screen - the time is spoken).")
print("  A     = tell me the time")
print("  B     = say that again")
print("  A + B = cycle mood (demo)")
try:
    while True:
        mood_name = current_mood_name()

        # idle face, with the occasional blink
        blink = time.time() >= next_blink
        if blink:
            next_blink = time.time() + random.uniform(2.5, 7.0)
        banner = "" if mood_override is None else f"demo: {mood_name}"
        draw_face(mood_name, blink=blink, banner=banner)
        if blink:
            time.sleep(0.12)

        gesture = read_gesture()
        try:
            if gesture == "A":
                # A also drops out of demo mood, back to the real clock
                if mood_override is not None:
                    mood_override = None
                    drain_requested.set()
                    while not ready.empty():
                        try:
                            ready.get_nowait()
                        except queue.Empty:
                            break
                if ready.empty():
                    _, quip, voice_settings, mood_name, source = make_phrase(datetime.now(), mood_override)
                    quip_path = render_quip(quip, voice_settings, next(quip_buffers))
                else:
                    quip_path, quip, voice_settings, mood_name, source = ready.get()
                path, time_line = build_utterance(datetime.now(), quip_path, voice_settings,
                                                  mood_name, "/tmp/vc_out.wav")
                last_utterance = (path, time_line, quip, mood_name)
                print(f"[{mood_name}/{source}] {time_line} {quip}")
                speak(path, mood_name, wrap(quip))

            elif gesture == "B":
                if last_utterance is None:
                    draw_face(mood_name, banner="nothing to repeat")
                    time.sleep(0.9)
                else:
                    path, time_line, quip, mood = last_utterance
                    print(f"[repeat] {time_line} {quip}")
                    speak(path, mood, wrap(quip))

            elif gesture == "AB":
                # step through the moods, then back to the real clock
                mood_override = 0 if mood_override is None else mood_override + 1
                if mood_override >= len(MOODS):
                    mood_override = None
                drain_requested.set()
                name = "auto" if mood_override is None else MOODS[mood_override][2]
                print(f"[mood] {name}")
                draw_face(current_mood_name(), banner=f"mood: {name}")
                time.sleep(1.0)
        except Exception as e:
            # one bad press should never kill the clock
            print(f"[error handling {gesture}: {type(e).__name__}: {e}]")
            time.sleep(0.5)

        time.sleep(0.04)
except KeyboardInterrupt:
    draw.rectangle((0, 0, SCREEN_W, SCREEN_H), fill=(0, 0, 0))
    disp.image(canvas, 90)
    print("\nstopped.")
