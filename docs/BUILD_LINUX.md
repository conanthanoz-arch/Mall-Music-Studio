# Building Mall Music Studio on Linux

## From GitHub (no local Linux machine)

1. Open [Actions → Build Linux](https://github.com/conanthanoz-arch/Mall-Music-Studio/actions/workflows/build-linux.yml)
2. Click **Run workflow** (or push to `master` / tag `v*`)
3. When finished, download **MallMusicStudio-linux-x64** from Artifacts
4. Extract and run:

```bash
mkdir -p ~/MallMusicStudio && tar -xzf MallMusicStudio-linux-x64.tar.gz -C ~/MallMusicStudio
cd ~/MallMusicStudio
chmod +x MallMusicStudio
./MallMusicStudio
```

The tarball includes `tools/` and `instrument_presets/` next to the binary (required for YouTube import and presets).

## Build locally on Ubuntu/Debian

```bash
git clone https://github.com/conanthanoz-arch/Mall-Music-Studio.git
cd Mall-Music-Studio
chmod +x install.sh build_music_studio.sh run_music_studio.sh
./install.sh
./build_music_studio.sh
```

Output:

- `dist/MallMusicStudio` — single-file binary
- `MallMusicStudio-linux-x86_64.tar.gz` — portable folder tarball

## Run from source (no build)

```bash
./install.sh
./run_music_studio.sh
```

## Optional: YouTube import

```bash
./install_import_tools.sh
```

Requires FFmpeg on PATH (`sudo apt install ffmpeg`).

## Notes

- **Tkinter** needs `python3-tk` (installed by `install.sh` on apt systems)
- **Arrangement Studio** (PySide6) needs X11 or Wayland display
- **PyInstaller** bundle is large (~200MB+) due to Qt; first CI build may take several minutes
- Tag a release (`git tag v0.12 && git push origin v0.12`) to attach the Linux tarball to a GitHub Release automatically
