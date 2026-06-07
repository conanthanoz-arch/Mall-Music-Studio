# Mall Music Studio

Procedural lo-fi music studio with mix tracks, **CC0 licensed sample playback**, MIDI patterns, master FX (vinyl/tape), YouTube stem analysis (synth emulation), and a Qt **Arrangement Studio** timeline for building 6-hour master loops.

## Install

### Requirements

- **Python 3.9+** (3.10+ recommended)
- **[FFmpeg](https://ffmpeg.org/download.html)** on PATH (export MP3, stream preview)
- **Git** (optional, for clone)
- **Windows 10/11** or **Linux** (Ubuntu 22.04+ recommended for builds)

### Windows

```powershell
git clone https://github.com/conanthanoz-arch/Mall-Music-Studio.git
cd Mall-Music-Studio
install.bat
run_music_studio.bat
```

Build EXE: `build_and_run.bat` → `dist\MallMusicStudio.exe`

### Linux

```bash
git clone https://github.com/conanthanoz-arch/Mall-Music-Studio.git
cd Mall-Music-Studio
chmod +x install.sh build_music_studio.sh run_music_studio.sh
./install.sh
./build_music_studio.sh
```

Or download a CI-built tarball — see [docs/BUILD_LINUX.md](docs/BUILD_LINUX.md).

### Quick install (Windows)

Optional — CC0 sample packs (~150–300 MB):

```powershell
install_samples.bat
```

Optional — YouTube import (large download: PyTorch + Demucs):

```powershell
pip install yt-dlp demucs soundfile
# or
install_import_tools.bat
```

### Run

```powershell
# From source (Python)
run_music_studio.bat

# Or build windowed EXE (no console)
build_and_run.bat
```

Double-click **`run_music_studio.vbs`** to launch the EXE without a command window flash.

### First-time workflow

1. **Mall Music Studio** — tune BPM, mix tracks, preview loops, save tracks to `music_library/`
2. **Open Arrangement Studio** — horizontal timeline, session grid, export master loop
3. **compile_music.bat** — concat library to `lofi_music.mp3` (optional)
4. **preview_stream.bat** — local visual stream test (no YouTube)

See [docs/LICENSED_SAMPLES.md](docs/LICENSED_SAMPLES.md) for CC0 packs and [docs/YOUTUBE_IMPORT.md](docs/YOUTUBE_IMPORT.md) for synth-only YouTube emulation (own-content allowlist).

## Project layout

```
Mall-Music-Studio/
├── music_tuner_ui.py       # Main Tk UI (sound design)
├── arrangement_daw/        # PySide6 Arrangement Studio
├── music_library/          # Your saved WAV + JSON (gitignored contents)
├── licensed_library/       # CC0 samples (manifest in git; WAVs local)
├── instrument_presets/     # Built-in + samples + user presets
├── tools/                  # YouTube import, stem separation
├── docs/
├── requirements.txt
├── build_music_studio.bat
└── run_music_studio.bat
```

## Build

| Platform | Command | Output |
|----------|---------|--------|
| Windows | `build_music_studio.bat` | `dist\MallMusicStudio.exe` |
| Linux | `./build_music_studio.sh` | `dist/MallMusicStudio` + `.tar.gz` |
| GitHub CI | Actions → **Build Linux** | Artifact `MallMusicStudio-linux-x64.tar.gz` |

Close any running app before rebuilding on Windows.

## Build EXE (Windows)

Close any running `MallMusicStudio.exe`, then:

```powershell
build_music_studio.bat
```

Output: `dist\MallMusicStudio.exe` (bundles PySide6 + pygame + numpy).

## Stream engine (optional)

When visuals and audio are ready:

1. `python generate_placeholders.py`
2. Edit `config.py` TRACKLIST from arrangement export
3. Set `STREAM_KEY` in `start_stream.bat`
4. `start_stream.bat`

## License

Personal / project use. Respect copyright for YouTube import (analysis-only, synth presets).
