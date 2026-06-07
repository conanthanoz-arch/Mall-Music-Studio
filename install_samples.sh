#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "Mall Music Studio — install CC0 sample packs"
echo

if [[ ! -d .venv ]]; then
  echo "Run ./install.sh first."
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

python tools/fetch_sample_packs.py "$@"

echo
echo "Sample packs installed under licensed_library/"
echo "Optional: export FREESOUND_API_KEY for full-quality Freesound downloads."
