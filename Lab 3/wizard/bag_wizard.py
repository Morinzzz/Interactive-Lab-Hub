#!/usr/bin/env python3
"""One More Thing Bag: Wizard of Oz prototype for Lab 3 Part 2.

The Pi runs everything: webcam preview, microphone + VAD + speech recognition, Piper
speech, the participant's status screen, and a small web page for the hidden
wizard. Open the wizard page from a laptop on the same network:

    python bag_wizard.py                       # then browse to http://<pi-ip>:5000
    python bag_wizard.py --min-silence 1.0     # wait longer before ending a turn
    python bag_wizard.py --camera /dev/video0 --no-screen
    python bag_wizard.py --buttons --auto-start   # start without the laptop

Sensed automatically: motion in the webcam view (shown to the wizard as a hint,
or used to start with --auto-start), end of the participant's turn (Silero
VAD), and the transcript (Parakeet by default; see asr.py).
Wizard decides: when to start (unless --auto-start or --buttons), what the bag
says next, and when to stop.

Privacy: webcam frames and microphone audio stay in memory only. Mic audio is
only analyzed while the state is LISTENING; while the bag is speaking (plus a
short guard afterwards) the samples are discarded, so the bag never transcribes
its own voice.
"""

import argparse
import logging
import os
import signal
import socket
import sys
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np
import sherpa_onnx
import sounddevice as sd
from flask import Flask, Response, jsonify, render_template, request
from piper import PiperVoice

import dialogue
from asr import ENGINES, make_recognizer
from status_screen import StatusScreen

SAMPLE_RATE = 16000
LAB_DIR = Path(__file__).resolve().parent.parent
DEFAULT_VAD = LAB_DIR / "models" / "silero_vad.onnx"
DEFAULT_VOICE = LAB_DIR / "voices" / "en_US-lessac-medium.onnx"


def audio_device(value):
    """sounddevice accepts an index or a substring of the device name."""
    if value is None:
        return None
    return int(value) if value.isdigit() else value


def lan_ip() -> str:
    """The address other machines on the network can reach this Pi at."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))  # no packet is sent for UDP connect
            return s.getsockname()[0]
        except OSError:
            return "<pi-ip>"


def build_vad(model_path: Path, min_silence: float, min_speech: float):
    config = sherpa_onnx.VadModelConfig()
    config.silero_vad.model = str(model_path)
    config.silero_vad.min_silence_duration = min_silence
    config.silero_vad.min_speech_duration = min_speech
    config.sample_rate = SAMPLE_RATE
    detector = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=30)
    return detector, config.silero_vad.window_size


class Speaker:
    """Piper through the output device, interruptible between chunks."""

    def __init__(self, voice_path: Path, device) -> None:
        self.voice = PiperVoice.load(str(voice_path))
        self.device = device
        self.generation = 0

    def say(self, text: str) -> bool:
        """Returns False if stop() was called before the text finished."""
        generation = self.generation
        for chunk in self.voice.synthesize(text):
            if self.generation != generation:
                return False
            audio = np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16)
            sd.play(audio, samplerate=chunk.sample_rate, device=self.device)
            sd.wait()
        return self.generation == generation

    def stop(self) -> None:
        self.generation += 1
        sd.stop()


class Bag:
    """Holds the interaction state. Every state change goes to the screen."""

    def __init__(self, args, screen: StatusScreen, speaker: Speaker,
                 recognizer) -> None:
        self.args = args
        self.screen = screen
        self.speaker = speaker
        self.recognizer = recognizer
        self.min_silence = args.min_silence

        self.lock = threading.Lock()
        self.state = "READY"
        self.history = deque(maxlen=40)
        self.last_line = None          # (text, listen_after) for Repeat
        self.speaking = False
        self.speak_token = 0
        self.transcribing = False
        self.listen_generation = 0     # bumped every time LISTENING starts
        self.listen_open_at = 0.0      # echo guard: ignore mic until this time
        self.auto_start = args.auto_start
        self.ready_since = time.monotonic()

        self._screen_state = threading.Condition()
        self._screen_pending = "READY"
        threading.Thread(target=self._screen_worker, daemon=True).start()

    # --- state -------------------------------------------------------------

    def set_state(self, state: str) -> None:
        with self.lock:
            self.state = state
            if state == "LISTENING":
                self.listen_generation += 1
                self.listen_open_at = time.monotonic() + self.args.echo_guard
            elif state == "READY":
                self.ready_since = time.monotonic()
        with self._screen_state:
            self._screen_pending = state
            self._screen_state.notify()

    def _screen_worker(self) -> None:
        shown = None
        while True:
            with self._screen_state:
                while self._screen_pending == shown:
                    self._screen_state.wait()
                shown = self._screen_pending
            self.screen.show(shown)

    def log(self, who: str, text: str) -> None:
        self.history.append({"who": who, "text": text,
                             "time": time.strftime("%H:%M:%S")})

    # --- speaking ----------------------------------------------------------

    def speak(self, text: str, listen_after: bool) -> bool:
        with self.lock:
            if self.speaking:
                return False
            self.speaking = True
            self.speak_token += 1
            token = self.speak_token
        self.last_line = (text, listen_after)
        self.log("bag", text)
        self.set_state("SPEAKING")
        threading.Thread(target=self._speak_worker, args=(text, listen_after, token),
                         daemon=True).start()
        return True

    def _speak_worker(self, text: str, listen_after: bool, token: int) -> None:
        try:
            finished = self.speaker.say(text)
        except Exception as exc:
            self.log("system", f"speech output failed: {exc}")
            finished = True
        with self.lock:
            if token != self.speak_token:
                return  # Stop was pressed; reset() already took over
            self.speaking = False
        if finished:
            self.set_state("LISTENING" if listen_after else "READY")

    def reset(self, clear_history: bool = False) -> None:
        with self.lock:
            self.speak_token += 1
            self.speaking = False
            if clear_history:
                self.history.clear()
                self.last_line = None
        self.speaker.stop()
        self.set_state("READY")

    def start(self) -> bool:
        line = dialogue.BY_ID[dialogue.OPENING_ID]
        return self.speak(line["text"], line["listen"])

    # --- optional local triggers -------------------------------------------

    def auto_start_loop(self, camera) -> None:
        """Start by itself when READY, after a cooldown, if motion is sustained."""
        while True:
            time.sleep(0.1)
            if (self.auto_start and self.state == "READY" and not self.speaking
                    and time.monotonic() - self.ready_since > self.args.auto_start_cooldown
                    and camera.ok and camera.sustained_motion):
                self.log("system", "auto-start: motion in view")
                self.start()

    def button_loop(self) -> None:
        """PiTFT buttons (active low, as in Lab 2): A = Start, B = Stop / Reset."""
        try:
            import board
            import digitalio
            buttons = {}
            for name, pin in (("A", board.D23), ("B", board.D24)):
                button = digitalio.DigitalInOut(pin)
                button.switch_to_input(pull=digitalio.Pull.UP)
                buttons[name] = button
        except Exception as exc:
            print(f"[buttons] unavailable: {exc}")
            self.log("system", f"PiTFT buttons unavailable: {exc}")
            return

        was_pressed = {name: False for name in buttons}
        while True:
            for name, button in buttons.items():
                pressed = not button.value
                if pressed and not was_pressed[name]:
                    if name == "A":
                        self.log("system", "button A: start")
                        self.start()
                    else:
                        self.log("system", "button B: stop")
                        self.reset()
                was_pressed[name] = pressed
            time.sleep(0.05)

    # --- listening ---------------------------------------------------------

    def mic_loop(self) -> None:
        try:
            self._mic_loop()
        except Exception as exc:
            print(f"[mic] stopped: {exc}")
            self.log("system", f"microphone stopped: {exc}. Restart bag_wizard.py.")

    def _mic_loop(self) -> None:
        """Runs forever. Only feeds the VAD while LISTENING (after the guard)."""
        samples_per_read = int(0.1 * SAMPLE_RATE)
        buffer = np.empty(0, dtype=np.float32)
        vad, window, generation, started = None, 0, -1, 0.0

        with sd.InputStream(device=self.args.mic, channels=1, dtype="float32",
                            samplerate=SAMPLE_RATE) as stream:
            while True:
                chunk, _ = stream.read(samples_per_read)

                with self.lock:
                    listening = (self.state == "LISTENING"
                                 and time.monotonic() >= self.listen_open_at)
                    current = self.listen_generation
                if not listening:
                    buffer = np.empty(0, dtype=np.float32)
                    continue

                if current != generation:
                    vad, window = build_vad(self.args.vad_model, self.min_silence,
                                            self.args.min_speech)
                    buffer = np.empty(0, dtype=np.float32)
                    generation, started = current, time.monotonic()

                buffer = np.concatenate([buffer, chunk.reshape(-1)])
                while len(buffer) > window:
                    vad.accept_waveform(buffer[:window])
                    buffer = buffer[window:]

                if not vad.empty():
                    utterance = np.array(vad.front.samples, dtype=np.float32)
                    vad.pop()
                    self._handle_utterance(utterance)
                elif (time.monotonic() - started > self.args.listen_timeout
                      and not vad.is_speech_detected()):
                    self.log("system", f"no speech heard for {self.args.listen_timeout:.0f}s")
                    self.set_state("THINKING")

    def _handle_utterance(self, utterance: np.ndarray) -> None:
        self.set_state("THINKING")
        self.transcribing = True
        t0 = time.perf_counter()
        text = self.recognizer.transcribe(utterance)
        elapsed = time.perf_counter() - t0
        self.transcribing = False

        if not text:
            if self.state == "THINKING":
                self.set_state("LISTENING")  # noise, not words: keep listening
            return
        self.log("participant", text)
        self.log("system", f"{len(utterance) / SAMPLE_RATE:.1f}s speech, "
                           f"{elapsed:.2f}s to transcribe ({self.args.asr})")

    def status(self, camera) -> dict:
        cam = {"enabled": camera is not None}
        if camera is not None:
            cam.update(ok=camera.ok, error=camera.error,
                       in_view=camera.someone_in_view,
                       motion=round(camera.motion_score, 3))
        return {
            "state": self.state,
            "transcribing": self.transcribing,
            "min_silence": self.min_silence,
            "last_line": self.last_line[0] if self.last_line else None,
            "history": list(self.history),
            "camera": cam,
            "auto_start": self.auto_start,
            "buttons": self.args.buttons,
        }


def make_app(bag: Bag, camera) -> Flask:
    app = Flask(__name__)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    groups = {}
    for line in dialogue.LINES:
        groups.setdefault(line["group"], []).append(line)

    @app.get("/")
    def controller():
        return render_template("controller.html", groups=groups,
                               opening=dialogue.OPENING_ID)

    @app.get("/video.mjpg")
    def video():
        def frames():
            while True:
                jpeg = camera.latest_jpeg() if camera else None
                if jpeg:
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                           + jpeg + b"\r\n")
                time.sleep(0.1)
        return Response(frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.get("/api/status")
    def status():
        return jsonify(bag.status(camera))

    @app.post("/api/say")
    def say():
        body = request.get_json(force=True)
        if "id" in body:
            line = dialogue.BY_ID.get(body["id"])
            if line is None:
                return jsonify(error=f"unknown line {body['id']!r}"), 404
            text, listen_after = line["text"], line["listen"]
        else:
            text = str(body.get("text", "")).strip()
            listen_after = bool(body.get("listen", True))
            if not text:
                return jsonify(error="empty reply"), 400
        if not bag.speak(text, listen_after):
            return jsonify(error="still speaking; press Stop first"), 409
        return jsonify(ok=True)

    @app.post("/api/repeat")
    def repeat():
        if bag.last_line is None:
            return jsonify(error="nothing to repeat yet"), 400
        if not bag.speak(*bag.last_line):
            return jsonify(error="still speaking; press Stop first"), 409
        return jsonify(ok=True)

    @app.post("/api/listen")
    def listen():
        if bag.speaking:
            return jsonify(error="still speaking; press Stop first"), 409
        bag.set_state("LISTENING")
        return jsonify(ok=True)

    @app.post("/api/reset")
    def reset():
        bag.reset(clear_history=True)
        return jsonify(ok=True)

    @app.post("/api/settings")
    def settings():
        body = request.get_json(force=True)
        value = float(body.get("min_silence", bag.min_silence))
        bag.min_silence = min(max(value, 0.1), 3.0)
        if "auto_start" in body:
            if camera is None and body["auto_start"]:
                return jsonify(error="auto-start needs the camera"), 400
            bag.auto_start = bool(body["auto_start"])
        return jsonify(ok=True, min_silence=bag.min_silence, auto_start=bag.auto_start)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-silence", type=float, default=0.8,
                        help="seconds of silence that end the participant's turn (default: 0.8)")
    parser.add_argument("--min-speech", type=float, default=0.25,
                        help="ignore speech bursts shorter than this (default: 0.25)")
    parser.add_argument("--listen-timeout", type=float, default=12.0,
                        help="tell the wizard if nobody speaks for this long (default: 12)")
    parser.add_argument("--echo-guard", type=float, default=0.3,
                        help="seconds to keep ignoring the mic after the bag stops talking")
    parser.add_argument("--asr", choices=ENGINES, default="parakeet",
                        help="speech recognizer (default: parakeet; see asr.py)")
    parser.add_argument("--whisper-model", default="tiny.en",
                        help="whisper model size, only with --asr whisper")
    parser.add_argument("--vad-model", type=Path, default=DEFAULT_VAD)
    parser.add_argument("--voice", type=Path, default=DEFAULT_VOICE)
    parser.add_argument("--mic", type=audio_device, default=None,
                        help="input device index or name (default: system default)")
    parser.add_argument("--speaker", type=audio_device, default=None,
                        help="output device index or name (default: system default)")
    parser.add_argument("--camera", default="0",
                        help="webcam index or path, e.g. 0 or /dev/video0 (default: 0)")
    parser.add_argument("--no-camera", action="store_true", help="run without the webcam")
    parser.add_argument("--no-screen", action="store_true",
                        help="print states instead of using the PiTFT")
    parser.add_argument("--buttons", action="store_true",
                        help="PiTFT button A starts the conversation, button B stops it")
    parser.add_argument("--auto-start", action="store_true",
                        help="start by itself when the camera sees sustained motion")
    parser.add_argument("--auto-start-cooldown", type=float, default=15.0,
                        help="seconds in READY before auto-start may fire again (default: 15)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    for path, what in [(args.vad_model, "VAD model"), (args.voice, "Piper voice")]:
        if not path.is_file():
            sys.exit(f"{what} not found at {path}. Run speech-scripts/setup.sh first.")

    screen = StatusScreen(enabled=not args.no_screen)
    screen.show("THINKING")

    camera = None
    if not args.no_camera:
        from camera import Camera
        camera = Camera(args.camera)
        camera.start()

    print(f"Loading {args.asr} and Piper...", flush=True)
    recognizer = make_recognizer(args.asr, args.whisper_model)
    speaker = Speaker(args.voice, args.speaker)

    if args.auto_start and camera is None:
        sys.exit("--auto-start needs the camera; drop --no-camera.")
    bag = Bag(args, screen, speaker, recognizer)
    bag.set_state("READY")
    threading.Thread(target=bag.mic_loop, daemon=True).start()
    if camera is not None:
        threading.Thread(target=bag.auto_start_loop, args=(camera,), daemon=True).start()
    if args.buttons:
        threading.Thread(target=bag.button_loop, daemon=True).start()

    in_dev = sd.query_devices(args.mic, "input")["name"]
    out_dev = sd.query_devices(args.speaker, "output")["name"]
    print(f"Mic: {in_dev}\nSpeaker: {out_dev}")
    print(f"Endpointing after {args.min_silence}s of silence.")
    print(f"Wizard controller: http://{lan_ip()}:{args.port}")

    # `kill` / systemctl stop should also blank the screen, like Ctrl-C does,
    # so a stale READY is never left showing with nothing running behind it.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        make_app(bag, camera).run(host=args.host, port=args.port, threaded=True)
    finally:
        speaker.stop()
        if camera is not None:
            camera.stop()
            camera.join(timeout=2)
        screen.off()
        print("\nStopped.", flush=True)
        # The mic and ASR threads are blocked inside native code; letting the
        # interpreter tear them down segfaults, so leave without that step.
        os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
