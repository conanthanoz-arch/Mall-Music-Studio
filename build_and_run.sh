#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
./build_music_studio.sh
./run_music_studio.sh
