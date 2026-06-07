# YouTube Sound Emulator (optional)

YouTube audio is used **only as a temporary analysis reference** to derive synth presets. The engine never loads or plays imported WAV zones. Saved instruments are JSON synth presets with **generic descriptive names** (no artist or song titles).

## Own-content policy (v0.13+)

Import is restricted to URLs you own or explicitly allow:

1. Copy `import_allowlist.example.json` → `import_allowlist.json`
2. Add your **channel ID** (`UC…`) and/or **video IDs**
3. In the UI, check **I own the rights to this URL** when using without an allowlist entry

Developers can set `MMS_IMPORT_UNRESTRICTED=1` to bypass checks locally.

Metadata is fetched with yt-dlp before download; blocked URLs fail with a clear error.

## Install import tools

```bat
.venv\Scripts\activate.bat
pip install yt-dlp demucs soundfile
```

Demucs pulls in PyTorch (~2GB). First run also downloads separation models. FFmpeg must be on PATH.

## CLI (stems only)

```bat
run_import_worker.bat "https://www.youtube.com/watch?v=VIDEO_ID"
```

This downloads audio, runs Demucs, and writes a manifest under `music_library/import_jobs/latest/`. Fit emulated presets from the Mall Music Studio UI (or call `fit_emulated_preset_for_stem()` from Python).

## In Mall Music Studio

1. Open **Import from YouTube**
2. Paste URL → confirm rights / allowlist → **Analyze stems**
3. Select a stem → scrub **Sample from** to the loud section (fixes silent intros)
4. **Fit emulated sound** → preview synthesized kick/note (not the stem WAV)
5. Tweak synth sliders → **Apply edits**
6. **Add as instrument** (mix track)

Presets are saved to `instrument_presets/user/` as `va_voice` or `drum_kit` JSON. Labels look like `Warm Sub Bass (emulated)` — never song or artist names.

For **licensed sample playback** (CC0 packs, your own loops), see [LICENSED_SAMPLES.md](LICENSED_SAMPLES.md).

## Copyright

Use only on content you have rights to analyze. Stems live temporarily under `music_library/import_jobs/latest/` for scrub/preview. Respect copyright and YouTube Terms of Service. No multisample WAV storage from third-party tracks.

## Output layout

```
music_library/import_jobs/latest/
  manifest.json
  stems/drums.wav
  stems/bass.wav
  ...

instrument_presets/user/
  emu_warm_sub_bass_a3f2.json
  emu_punchy_drums_kit_b1c4.json
```

Emulated presets appear in mix track preset dropdowns alongside built-in kits, CC0 samples, and VA voices.
