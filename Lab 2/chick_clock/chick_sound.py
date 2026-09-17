"""Short sounds for the Chick Clock.

A peep marks each finished minute.  On the hour the clock strikes, and
speaks the time if espeak is installed.  A tap on B asks the time the same
way.  Missing speakers fail quietly so the clock never dies over audio.

Announcements are exclusive: while one is playing, further announce_time
calls are ignored so repeated B taps cannot stack.
"""

import math
import os
import shutil
import struct
import subprocess
import tempfile
import threading
import wave
from datetime import datetime
from typing import List, Optional

_RATE = 22050
_chirp_path: Optional[str] = None
_chime_path: Optional[str] = None
_player: Optional[str] = None
_speaker: Optional[str] = None
_looked = False
# Held for the whole strike + speech.  Non-blocking acquire means a second
# B tap is dropped instead of layering another aplay/espeak on top.
_announce_lock = threading.Lock()


def _which(names) -> Optional[str]:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def _discover() -> None:
    global _player, _speaker, _looked
    if _looked:
        return
    _looked = True
    _player = _which(("aplay", "paplay", "ffplay"))
    _speaker = _which(("espeak-ng", "espeak"))


def _tone_frames(freq: float, ms: int, volume: float = 0.32) -> bytes:
    n = int(_RATE * ms / 1000.0)
    fade = max(1, int(_RATE * 0.012))
    frames = []
    for i in range(n):
        envelope = min(1.0, i / fade, (n - 1 - i) / fade)
        sample = int(
            32767 * volume * envelope * math.sin(2 * math.pi * freq * i / _RATE)
        )
        frames.append(struct.pack("<h", sample))
    return b"".join(frames)


def _silence(ms: int) -> bytes:
    return b"\x00\x00" * int(_RATE * ms / 1000.0)


def _write_wav(path: str, payload: bytes) -> None:
    with wave.open(path, "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(_RATE)
        wav.writeframes(payload)


def _cached_wav(holder: str, writer) -> str:
    path = globals()[holder]
    if path and os.path.isfile(path):
        return path
    handle = tempfile.NamedTemporaryFile(
        prefix="chick_snd_", suffix=".wav", delete=False
    )
    handle.close()
    writer(handle.name)
    globals()[holder] = handle.name
    return handle.name


def _write_chirp(path: str) -> None:
    _write_wav(path, _tone_frames(1320.0, 90, 0.28))


def _write_chime(path: str) -> None:
    """Two lower notes: clearly an hour strike, not the minute peep."""
    payload = (
        _tone_frames(523.25, 220, 0.36)
        + _silence(90)
        + _tone_frames(392.00, 420, 0.36)
    )
    _write_wav(path, payload)


def _play_command(path: str) -> Optional[tuple]:
    _discover()
    if not _player:
        return None
    if _player.endswith("ffplay"):
        return (_player, "-nodisp", "-autoexit", "-loglevel", "quiet", path)
    if _player.endswith("paplay"):
        return (_player, path)
    return (_player, "-q", path)


def _play(path: str) -> Optional[subprocess.Popen]:
    command = _play_command(path)
    if not command:
        return None
    try:
        return subprocess.Popen(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except OSError:
        return None


def is_announcing() -> bool:
    """True while a strike or spoken time from announce_time is still playing."""
    return _announce_lock.locked()


def minute_chirp() -> None:
    """One peep when the chick completes a one-minute round trip."""
    if is_announcing():
        return
    _play(_cached_wav("_chirp_path", _write_chirp))


_DONG_MS = 180
_GAP_MS = 280
_strike_paths = {}


def hour_count(hour: int) -> int:
    """12-hour strike count: 8am and 8pm are both eight, midnight is twelve."""
    n = hour % 12
    return 12 if n == 0 else n


def strike_seconds(count: int) -> float:
    count = max(1, min(12, count))
    return (count * (_DONG_MS + _GAP_MS) - _GAP_MS) / 1000.0 + 0.4


def _write_strikes(path: str, count: int) -> None:
    dong = _tone_frames(392.00, _DONG_MS, 0.40)
    gap = _silence(_GAP_MS)
    payload = (dong + gap) * (count - 1) + dong
    _write_wav(path, payload)


def _strike_wav(count: int) -> str:
    count = max(1, min(12, count))
    path = _strike_paths.get(count)
    if not path or not os.path.isfile(path):
        handle = tempfile.NamedTemporaryFile(
            prefix="chick_strike_%d_" % count, suffix=".wav", delete=False
        )
        handle.close()
        _write_strikes(handle.name, count)
        path = handle.name
        _strike_paths[count] = path
    return path


def hour_strikes(count: int) -> float:
    """Play `count` dongs (1-12) and return how long they last."""
    count = max(1, min(12, count))
    _play(_strike_wav(count))
    return strike_seconds(count)


def _speech_seconds(phrase: str, speed: str) -> float:
    # espeak -s is words-per-minute-ish; pad so the lock outlasts the voice.
    try:
        wpm = float(speed)
    except ValueError:
        wpm = 145.0
    words = max(1, len(phrase.split()))
    return words * 60.0 / max(80.0, wpm) + 0.6


def _run_announce(wav_path: str, phrase: Optional[str], speed: str) -> None:
    """Play strike and optional speech, then release the announce lock."""
    procs: List[subprocess.Popen] = []
    try:
        strike = _play(wav_path)
        if strike is not None:
            procs.append(strike)
        if phrase and _speaker:
            try:
                procs.append(
                    subprocess.Popen(
                        (_speaker, "-a", "140", "-s", speed, "--", phrase),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                )
            except OSError:
                pass
        for proc in procs:
            proc.wait()
    finally:
        _announce_lock.release()


def announce_time(when: datetime, sleepy: bool = False) -> float:
    """Strike the 12-hour count.  Speech is extra if espeak exists.

    Returns 0 if a previous announcement is still playing, so callers can
    leave their UI timers alone instead of stacking another strike.
    """
    if not _announce_lock.acquire(blocking=False):
        return 0.0

    count = hour_count(when.hour)
    duration = strike_seconds(count)
    wav_path = _strike_wav(count)

    _discover()
    phrase: Optional[str] = None
    speed = "105" if sleepy else "145"
    if _speaker:
        if when.minute == 0:
            phrase = "the time is %d o'clock" % count
        else:
            phrase = "the time is %d %02d" % (when.hour, when.minute)
        duration = max(duration, _speech_seconds(phrase, speed))

    worker = threading.Thread(
        target=_run_announce,
        args=(wav_path, phrase, speed),
        daemon=True,
    )
    worker.start()
    return duration
