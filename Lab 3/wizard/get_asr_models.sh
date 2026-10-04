#!/usr/bin/env bash
# Download the Parakeet speech recognition model used by asr.py into Lab 3/models.
# It is ~630 MB, so this takes a few minutes.
set -euo pipefail

MODELS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/models"
NAME=sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8
URL=https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/$NAME.tar.bz2

mkdir -p "$MODELS_DIR"
cd "$MODELS_DIR"
if [[ -d "$NAME" ]]; then
  echo "==> $NAME already present, skipping"
else
  echo "==> Downloading $NAME"
  wget -q --show-progress "$URL" -O "$NAME.tar.bz2"
  tar xjf "$NAME.tar.bz2"
  rm "$NAME.tar.bz2"
fi
echo "Model is in $MODELS_DIR"
