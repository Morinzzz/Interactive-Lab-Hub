#!/usr/bin/env python3
"""Show a live input level, then transcribe one utterance. Nothing is saved.

    python test_mic.py
    python test_mic.py --mic 2 --min-silence 0.8
    python test_mic.py --asr whisper      # compare with the Part 1 recognizer
"""

import argparse
import time

import numpy as np
import sounddevice as sd
from asr import ENGINES, make_recognizer
from bag_wizard import DEFAULT_VAD, SAMPLE_RATE, audio_device, build_vad

parser = argparse.ArgumentParser()
parser.add_argument("--mic", type=audio_device, default=None)
parser.add_argument("--min-silence", type=float, default=0.8)
parser.add_argument("--asr", choices=ENGINES, default="parakeet")
parser.add_argument("--level-seconds", type=float, default=5.0)
parser.add_argument("--timeout", type=float, default=15.0,
                    help="give up if no utterance is detected within this many seconds")
args = parser.parse_args()

print("Input devices:")
for i, d in enumerate(sd.query_devices()):
    if d["max_input_channels"] > 0:
        print(f"  [{i}] {d['name']}")
print(f"Using: {sd.query_devices(args.mic, 'input')['name']}\n")

print(f"Speak for {args.level_seconds:.0f}s to see the level:")
with sd.InputStream(device=args.mic, channels=1, dtype="float32",
                    samplerate=SAMPLE_RATE) as stream:
    end = time.monotonic() + args.level_seconds
    while time.monotonic() < end:
        chunk, _ = stream.read(int(0.1 * SAMPLE_RATE))
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        print(f"\r  {'#' * min(50, int(rms * 100)):<50} {rms:.3f}", end="", flush=True)
print("\n  (near 0.000 while talking means muted or wrong device;"
      " above ~0.1 while nobody talks means the room or the mic gain is too loud)\n")

recognizer = make_recognizer(args.asr)
vad, window = build_vad(DEFAULT_VAD, args.min_silence, 0.25)
print(f"Now say one sentence and pause for {args.min_silence}s...")
buffer = np.empty(0, dtype=np.float32)
with sd.InputStream(device=args.mic, channels=1, dtype="float32",
                    samplerate=SAMPLE_RATE) as stream:
    end = time.monotonic() + args.timeout
    while vad.empty():
        if time.monotonic() > end:
            raise SystemExit(f"No speech detected in {args.timeout:.0f}s.")
        chunk, _ = stream.read(int(0.1 * SAMPLE_RATE))
        buffer = np.concatenate([buffer, chunk.reshape(-1)])
        while len(buffer) > window:
            vad.accept_waveform(buffer[:window])
            buffer = buffer[window:]
utterance = np.array(vad.front.samples, dtype=np.float32)
t0 = time.perf_counter()
text = recognizer.transcribe(utterance)
print(f"heard ({args.asr}, {time.perf_counter() - t0:.2f}s): {text}")
