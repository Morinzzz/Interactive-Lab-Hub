"""Speech recognizers behind one interface: transcribe(float32 16 kHz audio) -> text.

    parakeet   NVIDIA Parakeet TDT 0.6B v2 (int8) via sherpa-onnx. Default.
               Most accurate here, and non-autoregressive, so it does not loop
               ("I can't talk about it. I can't talk about it...") on noisy audio.
    whisper    faster-whisper, as in Part 1 (--whisper-model tiny.en, base.en, ...).

On our Pi 5, Parakeet ran at ~0.1x real time and whisper tiny.en at ~0.2x.
The Parakeet model is fetched by get_asr_models.sh.
"""

from pathlib import Path

import numpy as np

SAMPLE_RATE = 16000
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
PARAKEET_DIR = MODELS_DIR / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"
ENGINES = ("parakeet", "whisper")


class ParakeetRecognizer:
    def __init__(self, threads: int = 4) -> None:
        if not PARAKEET_DIR.is_dir():
            raise SystemExit(f"{PARAKEET_DIR.name} not found in {MODELS_DIR}. "
                             "Run ./get_asr_models.sh in Lab 3/wizard first.")
        import sherpa_onnx
        self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(PARAKEET_DIR / "encoder.int8.onnx"),
            decoder=str(PARAKEET_DIR / "decoder.int8.onnx"),
            joiner=str(PARAKEET_DIR / "joiner.int8.onnx"),
            tokens=str(PARAKEET_DIR / "tokens.txt"),
            model_type="nemo_transducer",
            num_threads=threads,
        )

    def transcribe(self, audio: np.ndarray) -> str:
        stream = self.recognizer.create_stream()
        stream.accept_waveform(SAMPLE_RATE, audio)
        self.recognizer.decode_stream(stream)
        return stream.result.text.strip()


class WhisperRecognizer:
    def __init__(self, model: str) -> None:
        from faster_whisper import WhisperModel
        self.model = WhisperModel(model, device="cpu", compute_type="int8")

    def transcribe(self, audio: np.ndarray) -> str:
        segments, _ = self.model.transcribe(audio, beam_size=1)
        return " ".join(s.text.strip() for s in segments).strip()


def make_recognizer(engine: str = "parakeet", whisper_model: str = "tiny.en"):
    if engine == "whisper":
        return WhisperRecognizer(whisper_model)
    return ParakeetRecognizer()
