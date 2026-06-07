#!/usr/bin/env bash
# Optional YouTube import deps (PyTorch + Demucs — large download)
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source .venv/bin/activate
pip install yt-dlp demucs soundfile
echo "Import tools installed."
