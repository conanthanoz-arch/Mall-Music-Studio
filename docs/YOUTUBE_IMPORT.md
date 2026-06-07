# YouTube Sound Emulator (optional)

YouTube audio is used **only as a temporary analysis reference** to derive synth presets. The engine never loads or plays imported WAV zones. Saved instruments are JSON synth presets with **generic descriptive names** (no artist or song titles).

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

## In Mall Music Studio (v0.12+)

1. Open **Import from YouTube**
2. Paste URL → **Analyze stems**
3. Select a stem → scrub **Sample from** to the loud section (fixes silent intros)
4. **Fit emulated sound** → preview synthesized kick/note (not the stem WAV)
5. Tweak synth sliders → **Apply edits**
6. **Add as instrument** (mix track)

Presets are saved to `instrument_presets/user/` as `va_voice` or `drum_kit` JSON. Labels look like `Warm Sub Bass (emulated)` — never song or artist names.

## Copyright

For personal/reference use only. Stems live temporarily under `music_library/import_jobs/latest/` for scrub/preview. Respect copyright and YouTube Terms of Service. No multisample WAV storage.

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

Emulated presets appear in mix track preset dropdowns alongside built-in kits and VA voices.
