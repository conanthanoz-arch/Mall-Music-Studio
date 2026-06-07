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
if [[ -d licensed_library ]]; then
  mkdir -p "$PKG/licensed_library"
  [[ -f licensed_library/manifest.json ]] && cp licensed_library/manifest.json "$PKG/licensed_library/"
  [[ -d licensed_library/LICENSES ]] && cp -r licensed_library/LICENSES "$PKG/licensed_library/"
  [[ -d licensed_library/kenney_foley ]] && cp -r licensed_library/kenney_* "$PKG/licensed_library/" 2>/dev/null || true
  [[ -d licensed_library/holizna_happy_lofi ]] && cp -r licensed_library/holizna_happy_lofi "$PKG/licensed_library/" 2>/dev/null || true
  [[ -d licensed_library/open_lofi ]] && cp -r licensed_library/open_lofi "$PKG/licensed_library/" 2>/dev/null || true
  [[ -d licensed_library/freesound ]] && cp -r licensed_library/freesound "$PKG/licensed_library/" 2>/dev/null || true
fi
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
