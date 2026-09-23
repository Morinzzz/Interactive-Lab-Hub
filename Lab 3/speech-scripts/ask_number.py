#!/usr/bin/env python3
"""Ask out loud for a number, record the answer, then transcribe it.

Numbers are a stress test: Whisper often writes "oh" for 0, turns a digit
string into words, inserts commas, or drops a digit. Run this before you
design any dialogue that depends on phone numbers, zip codes, or counts.

    python ask_number.py
    python ask_number.py --model base.en
"""

import argparse
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel
from piper import PiperVoice

SAMPLE_RATE = 16000
RECORD_SECONDS = 6
LAB_DIR = Path(__file__).resolve().parent.parent
DEFAULT_VOICE = LAB_DIR / "voices" / "en_US-lessac-medium.onnx"
OUT_WAV = Path(__file__).resolve().parent / "zipcode_answer.wav"

PROMPT = (
    "What is your five digit zip code? "
    "You can make one up. Please say the digits."
)


def say(voice: PiperVoice, text: str) -> None:
    for chunk in voice.synthesize(text):
        audio = np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16)
        sd.play(audio, samplerate=chunk.sample_rate)
        sd.wait()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="tiny.en",
                        help="whisper model size (default: tiny.en)")
    parser.add_argument("--voice", type=Path, default=DEFAULT_VOICE)
    parser.add_argument("--seconds", type=float, default=RECORD_SECONDS,
                        help="how long to record after the question")
    args = parser.parse_args()

    if not args.voice.is_file():
        raise SystemExit(f"Piper voice not found at {args.voice}. Run ./setup.sh first.")

    print("Loading TTS and Whisper...", flush=True)
    voice = PiperVoice.load(str(args.voice))
    recognizer = WhisperModel(args.model, device="cpu", compute_type="int8")

    say(voice, PROMPT)
    print(f"Listening for {args.seconds:.0f}s — say a zip code now.", flush=True)

    recorded = sd.rec(
        int(args.seconds * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
    )
    sd.wait()
    sf.write(OUT_WAV, recorded, SAMPLE_RATE)
    print(f"Saved {OUT_WAV.name}", flush=True)

    t0 = time.perf_counter()
    segments, info = recognizer.transcribe(str(OUT_WAV), beam_size=1)
    text = " ".join(seg.text.strip() for seg in segments)
    t_transcribe = time.perf_counter() - t0
    rtf = t_transcribe / info.duration if info.duration else 0.0

    print(f"\nheard: {text}")
    print(f"model            {args.model}")
    print(f"audio duration   {info.duration:.2f}s")
    print(f"transcription    {t_transcribe:.2f}s")
    print(f"real-time factor {rtf:.2f}x")
    print("\nCompare that string to the digits you actually said.")
    print("Typical errors: oh/zero, missing digits, commas, or the number as words.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
