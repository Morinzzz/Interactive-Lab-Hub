#!/usr/bin/env bash
# Greet Morin by name using Piper (neural TTS).
# Favorite engine: Piper, streamed with --output-raw so speech starts sooner.

set -euo pipefail
VOICES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/voices"

python3 -m piper \
  --model en_US-lessac-medium \
  --data-dir "$VOICES_DIR" \
  --output-raw \
  -- "Hi Morin. Welcome back." \
  | aplay -r 22050 -f S16_LE -t raw -
