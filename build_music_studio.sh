#!/usr/bin/env bash
# Build MallMusicStudio Linux binary + release tarball
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .venv/bin/activate ]]; then
  echo "Run ./install.sh first"
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

pip install -q pyinstaller

echo "Building dist/MallMusicStudio ..."
pyinstaller --noconfirm --clean build_music_studio.spec

PKG=dist/package
rm -rf "$PKG"
mkdir -p "$PKG/music_library"
cp dist/MallMusicStudio "$PKG/"
cp -r tools instrument_presets "$PKG/"
touch "$PKG/music_library/.gitkeep"

ARCH="$(uname -m)"
TARBALL="MallMusicStudio-linux-${ARCH}.tar.gz"
tar -czvf "$TARBALL" -C "$PKG" .

echo
echo "Built:"
echo "  Binary:   dist/MallMusicStudio"
echo "  Package:  $TARBALL"
echo
echo "Extract and run:"
echo "  tar -xzf $TARBALL -C ~/MallMusicStudio"
echo "  cd ~/MallMusicStudio && ./MallMusicStudio"
