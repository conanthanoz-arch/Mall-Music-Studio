"""CLI sidecar: YouTube URL → stems → emulated synth presets."""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.sound_profiler import (
    find_best_sample_region,
    fit_emulated_preset,
)
from tools.stem_separator import separate_stems
from tools.youtube_import import download_youtube_audio
from waveform_utils import load_wav_mono

from instrument_presets import save_user_preset


def write_progress(job_dir: str, stage: str, detail: str = "") -> None:
    path = os.path.join(job_dir, "progress.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"stage": stage, "detail": detail, "time": time.time()}, f)


def _default_analyze_window(stem_name: str, max_download_sec: float) -> float:
    if stem_name.lower() in ("drums", "drum"):
        return min(30.0, max(max_download_sec * 0.35, 15.0))
    return min(25.0, max(max_download_sec * 0.35, 12.0))


def _stem_display_label(stem_name: str) -> str:
    names = {
        "drums": "Drums",
        "bass": "Bass",
        "vocals": "Vocals",
        "other": "Other",
    }
    return names.get(stem_name.lower(), stem_name.replace("_", " ").title())


def fit_emulated_preset_for_stem(
    stem_wav: str,
    stem_name: str,
    analyze_start_sec: Optional[float] = None,
    analyze_sec: float = 30.0,
    preset_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyze region and save emulated synth preset. Raises on silent region."""
    full = load_wav_mono(stem_wav)
    if analyze_start_sec is None:
        analyze_start_sec = find_best_sample_region(full, window_sec=analyze_sec)

    preset, err = fit_emulated_preset(
        stem_wav,
        stem_name,
        analyze_start_sec=float(analyze_start_sec),
        analyze_sec=analyze_sec,
        preset_id=preset_id,
    )
    if err == "region_silent":
        raise ValueError(
            "Selected region is too quiet. Scrub the timeline to a section with audible audio."
        )
    if err or not preset:
        raise ValueError(err or "Could not fit emulated preset")

    save_user_preset(preset)
    return {
        "stem": stem_name,
        "label": _stem_display_label(stem_name),
        "preset_id": preset["id"],
        "preset_label": preset["label"],
        "engine": preset.get("engine", "va_voice"),
        "wav": stem_wav,
        "analyze_start_sec": round(float(analyze_start_sec), 3),
        "analyze_sec": round(float(analyze_sec), 3),
        "built": True,
    }


def run_import(
    url: str,
    library_dir: str,
    max_download_sec: float = 120.0,
    user_confirmed: bool = False,
) -> dict:
    """Download + Demucs only; user fits emulated presets from UI."""
    work_dir = os.path.join(library_dir, "import_jobs")
    os.makedirs(work_dir, exist_ok=True)
    job_dir = os.path.join(work_dir, "latest")
    os.makedirs(job_dir, exist_ok=True)

    write_progress(job_dir, "downloading", "Fetching audio from YouTube…")
    download_dir = os.path.join(job_dir, "download")
    os.makedirs(download_dir, exist_ok=True)
    meta = download_youtube_audio(
        url, download_dir, max_duration_sec=max_download_sec, user_confirmed=user_confirmed
    )

    write_progress(job_dir, "separating", "Running Demucs stem separation (may take several minutes)…")
    stems_dir = os.path.join(job_dir, "stems")
    stems = separate_stems(meta["wav_path"], stems_dir)

    results: List[Dict[str, Any]] = []
    for stem in stems:
        stem_name = stem["name"]
        stem_wav = stem["wav"]
        window = _default_analyze_window(stem_name, max_download_sec)
        full = load_wav_mono(stem_wav)
        start = find_best_sample_region(full, window_sec=window)
        results.append(
            {
                "stem": stem_name,
                "label": _stem_display_label(stem_name),
                "preset_id": None,
                "preset_label": "",
                "engine": "drum_kit" if stem_name.lower() in ("drums", "drum") else "va_voice",
                "wav": stem_wav,
                "analyze_start_sec": round(start, 3),
                "analyze_sec": round(window, 3),
                "built": False,
            }
        )

    manifest = {
        "duration_sec": meta.get("duration_sec", 0),
        "stems": results,
        "copyright_notice": "Audio analyzed temporarily to derive synth settings. No samples stored.",
    }
    manifest_path = os.path.join(job_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    write_progress(job_dir, "done", f"Separated {len(results)} stems — scrub and fit emulated sounds")
    return manifest


def update_manifest_stem(library_dir: str, stem_name: str, entry: Dict[str, Any]) -> dict:
    path = os.path.join(library_dir, "import_jobs", "latest", "manifest.json")
    with open(path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    for i, s in enumerate(manifest.get("stems") or []):
        if s.get("stem") == stem_name:
            manifest["stems"][i] = {**s, **entry}
            break
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Import stems from YouTube URL")
    parser.add_argument("url")
    parser.add_argument("--library-dir", required=True)
    parser.add_argument("--max-download-sec", type=float, default=120.0)
    parser.add_argument("--manifest-out", default="")
    parser.add_argument("--user-confirmed", action="store_true")
    args = parser.parse_args()
    try:
        manifest = run_import(
            args.url,
            args.library_dir,
            max_download_sec=args.max_download_sec,
            user_confirmed=args.user_confirmed,
        )
    except Exception as exc:
        job_dir = os.path.join(args.library_dir, "import_jobs", "latest")
        write_progress(job_dir, "error", str(exc))
        raise
    out = args.manifest_out or os.path.join(args.library_dir, "import_jobs", "latest", "manifest.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
