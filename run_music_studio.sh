#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ -x dist/MallMusicStudio ]]; then
  exec ./dist/MallMusicStudio "$@"
fi

if [[ ! -f .venv/bin/activate ]]; then
  echo "No build found. Run ./install.sh then ./run_music_studio.sh"
  echo "Or build first: ./build_music_studio.sh"
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate
exec python music_tuner_ui.py "$@"
