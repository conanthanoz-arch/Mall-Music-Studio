#!/usr/bin/env bash
# Mall Music Studio — Linux install (Ubuntu/Debian)
set -euo pipefail
cd "$(dirname "$0")"

echo "Mall Music Studio — Linux install"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Install Python 3.9+ first."
  exit 1
fi

if command -v apt-get >/dev/null 2>&1; then
  echo "Installing system packages (Tk, SDL, FFmpeg)..."
  sudo apt-get update
  sudo apt-get install -y \
    python3-venv python3-tk python3-dev \
    ffmpeg libsdl2-2.0-0 \
    libxkbcommon-x11-0 libxcb-cursor0 libxcb-xinerama0 libegl1 \
    || echo "Warning: some optional packages failed (build may still work)"
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

echo
echo "Install complete."
echo "  Run from source:  ./run_music_studio.sh"
echo "  Build binary:     ./build_music_studio.sh"
echo "  YouTube import:   ./install_import_tools.sh"
echo "  CC0 samples:      ./install_samples.sh"
