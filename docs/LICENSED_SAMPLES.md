# Licensed CC0 Sample Packs (v0.13)

Mall Music Studio can play **royalty-free CC0 samples** alongside procedural synth voices. Audio files are **not committed to git** — run the install script to download them locally.

## Install

**Windows**

```bat
install_samples.bat
```

**Linux**

```bash
chmod +x install_samples.sh
./install_samples.sh
```

Optional: set `FREESOUND_API_KEY` in `.env` (or environment) for reliable Freesound CC0 downloads. Get a key at [freesound.org/apiv2/apply](https://freesound.org/apiv2/apply).

## Sources (all CC0 or user-original)

| Pack | License | Purpose |
|------|---------|---------|
| [HoliznaCC0 Happy Lo-Fi](https://opengameart.org/content/happy-lo-fi-lofi-collection) | CC0 | Lo-fi loops |
| [open-lofi](https://github.com/btahir/open-lofi) | CC0 | Full-track loops |
| [OpenGameArt Fantasy Drum Loops](https://opengameart.org/content/fantasy-music-and-drum-loops-pack) | CC0 | Drum loops / one-shots |
| Freesound (curated IDs, optional API key) | CC0 only | Piano loop, vinyl crackle |

**Not auto-downloaded:** [Sonniss GDC bundles](https://sonniss.com/gameaudiogdc/) — you may use them locally in projects, but **do not redistribute raw files** in this repo.

## After install

- `licensed_library/manifest.json` — sample registry
- `licensed_library/LICENSES/` — per-pack license notes
- `instrument_presets/samples/` — starter `sample_kit` / `sample_loop` presets

In the UI, mix track presets include **CC0 Foley Drums**, **CC0 Holizna Piano Loop**, **CC0 Vinyl Bed** (when downloads succeeded).

## User loops

Use **Register user loop…** in Mix tracks to copy your own WAV into `licensed_library/user_loops/` and create a `sample_loop` preset (`license: user_original`).

## Rebuild manifest only

If downloads already exist:

```bat
python tools\fetch_sample_packs.py --skip-download
```

## PyInstaller builds

Run `install_samples.bat` before `build_music_studio.bat` to bundle samples next to the EXE, or ship manifest-only and document post-install fetch.
