#!/usr/bin/env python3
"""Download CC0 sample packs and build licensed_library/manifest.json."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from licensed_library import licensed_library_dir, save_manifest

PACKS = [
    {
        "id": "holizna_happy_lofi",
        "name": "HoliznaCC0 Happy Lo-Fi Collection",
        "url": "https://opengameart.org/sites/default/files/happy_lo-fi_lofi_collection.zip",
        "license": "CC0 1.0",
        "source_url": "https://opengameart.org/content/happy-lo-fi-lofi-collection",
    },
    {
        "id": "open_lofi",
        "name": "open-lofi CC0 tracks",
        "url": "https://github.com/btahir/open-lofi/releases/latest/download/openlofi.zip",
        "license": "CC0 1.0",
        "source_url": "https://github.com/btahir/open-lofi",
    },
    {
        "id": "oga_fantasy_drums",
        "name": "OpenGameArt Fantasy Drum Loops",
        "url": "https://opengameart.org/sites/default/files/fantasyambience_drumloops.zip",
        "license": "CC0 1.0",
        "source_url": "https://opengameart.org/content/fantasy-music-and-drum-loops-pack",
    },
]

FREESOUND_CURATED = [
    {
        "id": "freesound_holizna_piano",
        "freesound_id": 629172,
        "name": "Holizna Lofi Piano Loop 88 BPM",
        "license": "CC0",
        "source_url": "https://freesound.org/people/holizna/sounds/629172/",
        "slot": "chords",
        "type": "loop",
        "loop_bpm": 88,
        "bars": 1,
        "tags": ["piano", "lofi"],
    },
    {
        "id": "freesound_vinyl_crackle",
        "freesound_id": 567908,
        "name": "Vinyl Crackle Loop",
        "license": "CC0",
        "source_url": "https://freesound.org/people/InspectorJ/sounds/567908/",
        "slot": "layer",
        "type": "loop",
        "loop_bpm": 80,
        "bars": 1,
        "tags": ["vinyl", "crackle"],
    },
]

AUDIO_EXT = {".wav", ".flac", ".ogg", ".mp3", ".m4a", ".opus"}


def _log(msg: str) -> None:
    print(msg, flush=True)


def _download(url: str, dest: str, timeout: int = 600) -> bool:
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "MallMusicStudio/0.13 sample-fetch"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            read = 0
            chunk = 1024 * 256
            with open(dest, "wb") as f:
                while True:
                    block = resp.read(chunk)
                    if not block:
                        break
                    f.write(block)
                    read += len(block)
                    if total and read % (chunk * 20) == 0:
                        _log(f"  ... {read // (1024 * 1024)} MB")
        return os.path.getsize(dest) > 1000
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        _log(f"  download failed: {exc}")
        if os.path.isfile(dest):
            try:
                os.remove(dest)
            except OSError:
                pass
        return False


def _download_pack(pack: Dict[str, Any], zip_path: str) -> bool:
    urls = [pack["url"]] + list(pack.get("fallback_urls") or [])
    for url in urls:
        _log(f"Downloading {pack['name']}...")
        if _download(url, zip_path):
            return True
    return False


def _extract_zip(zip_path: str, dest_dir: str) -> None:
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)


def _walk_audio(root: str) -> List[str]:
    found: List[str] = []
    for dirpath, _, files in os.walk(root):
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext in AUDIO_EXT:
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def _rel_path(abs_path: str, lib_root: str) -> str:
    return os.path.relpath(abs_path, lib_root).replace("\\", "/")


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s[:48] or "sample"


def _classify_drum(name: str) -> Optional[str]:
    n = name.lower()
    if any(k in n for k in ("kick", "bd", "bassdrum", "bass_drum")):
        return "kick"
    if any(k in n for k in ("snare", "clap", "rim")):
        return "snare"
    if any(k in n for k in ("hat", "hihat", "hi_hat", "cymbal")):
        if "open" in n:
            return "hihat_open"
        return "hihat_closed"
    return None


def _write_license(pack: Dict[str, Any]) -> None:
    lic_dir = os.path.join(licensed_library_dir(), "LICENSES")
    os.makedirs(lic_dir, exist_ok=True)
    path = os.path.join(lic_dir, f"{pack['id']}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"Pack: {pack['name']}\n")
        f.write(f"License: {pack['license']}\n")
        f.write(f"Source: {pack.get('source_url', pack.get('url', ''))}\n")
        f.write(f"Fetched: {datetime.now(timezone.utc).isoformat()}\n")


def _fetch_freesound_previews(api_key: Optional[str], lib_root: str) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for item in FREESOUND_CURATED:
        fs_id = item["freesound_id"]
        dest_dir = os.path.join(lib_root, "freesound")
        os.makedirs(dest_dir, exist_ok=True)
        dest_wav = os.path.join(dest_dir, f"{item['id']}.wav")
        if os.path.isfile(dest_wav):
            rel = _rel_path(dest_wav, lib_root)
            entries.append(_freesound_entry(item, rel))
            continue

        preview_url = None
        if api_key:
            try:
                meta_url = (
                    f"https://freesound.org/apiv2/sounds/{fs_id}/"
                    f"?token={api_key}&fields=id,name,license,previews"
                )
                req = urllib.request.Request(meta_url, headers={"User-Agent": "MallMusicStudio/0.13"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    meta = json.loads(resp.read().decode("utf-8"))
                if "Creative Commons 0" not in meta.get("license", ""):
                    _log(f"  Skipping Freesound {fs_id}: not CC0")
                    continue
                previews = meta.get("previews") or {}
                preview_url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")
            except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
                _log(f"  Freesound API {fs_id}: {exc}")

        if not preview_url:
            trial = f"https://freesound.org/data/previews/{fs_id // 1000}/{fs_id}_11527144-hq.mp3"
            tmp = dest_wav + ".mp3"
            if not _download(trial, tmp, timeout=120):
                _log(f"  Could not fetch Freesound {fs_id} (set FREESOUND_API_KEY for reliable download)")
                continue
            preview_url = trial

        tmp_mp3 = dest_wav + ".mp3"
        if preview_url.startswith("http") and not os.path.isfile(tmp_mp3):
            if not _download(preview_url, tmp_mp3, timeout=180):
                continue
        if os.path.isfile(tmp_mp3) and not os.path.isfile(dest_wav):
            if not _ffmpeg_to_wav(tmp_mp3, dest_wav):
                continue
            try:
                os.remove(tmp_mp3)
            except OSError:
                pass

        if os.path.isfile(dest_wav):
            entries.append(_freesound_entry(item, _rel_path(dest_wav, lib_root)))
            _log(f"  + {item['name']}")
    return entries


def _freesound_entry(item: Dict[str, Any], rel: str) -> Dict[str, Any]:
    return {
        "id": item["id"],
        "path": rel,
        "license": item["license"],
        "source_url": item["source_url"],
        "slot": item["slot"],
        "type": item["type"],
        "loop_bpm": item.get("loop_bpm", 80),
        "bars": item.get("bars", 1),
        "tags": item.get("tags", []),
    }


def _ffmpeg_to_wav(src: str, dest: str) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        _log("  ffmpeg not found — cannot convert mp3 preview")
        return False
    import subprocess

    proc = subprocess.run(
        [ffmpeg, "-y", "-i", src, "-ac", "1", "-ar", "44100", dest],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0 and os.path.isfile(dest)


def _index_loops_from_dir(
    pack_id: str,
    subdir: str,
    lib_root: str,
    slot: str,
    max_files: int = 20,
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    base = os.path.join(lib_root, subdir)
    if not os.path.isdir(base):
        return entries
    files = _walk_audio(base)
    for i, path in enumerate(files[:max_files]):
        name = os.path.splitext(os.path.basename(path))[0]
        eid = f"{pack_id}_{_slug(name)}_{i:02d}"
        entries.append(
            {
                "id": eid,
                "path": _rel_path(path, lib_root),
                "license": "CC0 1.0",
                "source_url": PACKS[0]["source_url"] if pack_id == "holizna_happy_lofi" else "",
                "slot": slot,
                "type": "loop",
                "loop_bpm": 80,
                "bars": 2,
                "tags": ["lofi", pack_id],
            }
        )
    return entries


def _prune_open_lofi(lib_root: str, max_tracks: int = 16) -> None:
    """Keep a diverse subset of open-lofi CC0 tracks to limit disk use."""
    base = os.path.join(lib_root, "open_lofi")
    catalog_path = os.path.join(base, "catalog.json")
    keep_paths: set = set()
    if os.path.isfile(catalog_path):
        with open(catalog_path, "r", encoding="utf-8") as f:
            catalog = json.load(f)
        tracks = catalog.get("tracks") or catalog if isinstance(catalog, list) else []
        if isinstance(catalog, dict) and "tracks" not in catalog:
            tracks = catalog.get("entries") or list(catalog.values()) if catalog else []
        step = max(1, len(tracks) // max_tracks) if tracks else 1
        for i, tr in enumerate(tracks[::step][:max_tracks]):
            if isinstance(tr, dict):
                fname = tr.get("file") or tr.get("filename") or tr.get("path")
                if fname:
                    keep_paths.add(os.path.normpath(os.path.join(base, fname)))
    all_audio = _walk_audio(base)
    if not keep_paths:
        keep_paths = set(all_audio[:max_tracks])
    for path in all_audio:
        if os.path.normpath(path) not in keep_paths:
            try:
                os.remove(path)
            except OSError:
                pass


def _index_drum_one_shots(pack_dirs: List[str], lib_root: str, pack_id: str) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    kicks, snares, hats_closed, hats_open = [], [], [], []
    for sub in pack_dirs:
        base = os.path.join(lib_root, sub)
        if not os.path.isdir(base):
            continue
        for path in _walk_audio(base):
            role = _classify_drum(os.path.basename(path))
            if role == "kick":
                kicks.append(path)
            elif role == "snare":
                snares.append(path)
            elif role == "hihat_open":
                hats_open.append(path)
            elif role == "hihat_closed":
                hats_closed.append(path)

    # OGA / foley folders: classify filenames
    if not kicks:
        for sub in pack_dirs:
            base = os.path.join(lib_root, sub)
            for path in _walk_audio(base):
                role = _classify_drum(os.path.basename(path))
                if role == "kick":
                    kicks.append(path)
                elif role == "snare" and len(snares) < 3:
                    snares.append(path)
                elif role == "hihat_closed" and len(hats_closed) < 3:
                    hats_closed.append(path)
                if len(kicks) >= 3 and len(snares) >= 2 and len(hats_closed) >= 2:
                    break

    def pick(lst: List[str], idx: int = 0) -> Optional[str]:
        return lst[idx] if lst else None

    if not kicks:
        pooled: List[str] = []
        for sub in pack_dirs:
            pooled.extend(_walk_audio(os.path.join(lib_root, sub)))
        if pooled:
            kicks = [pooled[0]]
            snares = [pooled[min(1, len(pooled) - 1)]]
            hats_closed = [pooled[min(2, len(pooled) - 1)]]
            hats_open = [pooled[min(3, len(pooled) - 1)]]

    kit_paths = {
        "kick": pick(kicks, 0),
        "snare": pick(snares, 0),
        "hihat_closed": pick(hats_closed, 0),
        "hihat_open": pick(hats_open or hats_closed, 1 if len(hats_closed) > 1 else 0),
    }
    entries: List[Dict[str, Any]] = []
    for role, path in kit_paths.items():
        if path:
            entries.append(
                {
                    "id": f"{pack_id}_{role}",
                    "path": _rel_path(path, lib_root),
                    "license": "CC0 1.0",
                    "slot": "drums",
                    "type": "one_shot",
                    "role": role,
                }
            )
    return entries, {k: _rel_path(v, lib_root) for k, v in kit_paths.items() if v}


def _build_presets(entries: List[Dict[str, Any]], kit_paths: Dict[str, str]) -> List[Dict[str, Any]]:
    presets: List[Dict[str, Any]] = []

    if kit_paths:
        presets.append(
            {
                "id": "cc0_foley_drums",
                "label": "CC0 Foley Drums",
                "slot": "drums",
                "engine": "sample_kit",
                "volume": 1.0,
                "kick": {"path": kit_paths.get("kick", ""), "volume": 0.9},
                "snare": {"path": kit_paths.get("snare", ""), "volume": 1.0},
                "hihat_closed": {"path": kit_paths.get("hihat_closed", ""), "volume": 0.85},
                "hihat_open": {"path": kit_paths.get("hihat_open", ""), "volume": 0.75},
            }
        )

    piano = next((e for e in entries if e.get("id") == "freesound_holizna_piano"), None)
    if not piano:
        piano = next(
            (
                e
                for e in entries
                if e.get("slot") == "chords"
                and e.get("type") == "loop"
                and str(e.get("path", "")).lower().endswith((".ogg", ".wav", ".mp3"))
            ),
            None,
        )
    if piano:
        presets.append(
            {
                "id": "cc0_holizna_piano_loop",
                "label": "CC0 Holizna Piano Loop",
                "slot": "chords",
                "engine": "sample_loop",
                "volume": 0.75,
                "loop_path": piano["path"],
                "loop_bpm": piano.get("loop_bpm", 88),
                "bars": piano.get("bars", 1),
            }
        )

    vinyl = next((e for e in entries if "vinyl" in (e.get("tags") or [])), None)
    if vinyl:
        presets.append(
            {
                "id": "cc0_vinyl_bed",
                "label": "CC0 Vinyl Bed",
                "slot": "layer",
                "engine": "sample_loop",
                "volume": 0.12,
                "loop_path": vinyl["path"],
                "loop_bpm": vinyl.get("loop_bpm", 80),
                "bars": 1,
            }
        )

    return presets


def _write_sample_presets(presets: List[Dict[str, Any]]) -> None:
    out_dir = os.path.join(ROOT, "instrument_presets", "samples")
    os.makedirs(out_dir, exist_ok=True)
    for preset in presets:
        path = os.path.join(out_dir, f"{preset['id']}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(preset, f, indent=2)


def fetch_all(skip_download: bool = False) -> Dict[str, Any]:
    lib_root = licensed_library_dir()
    os.makedirs(lib_root, exist_ok=True)
    tmp_dir = os.path.join(lib_root, "_downloads")
    os.makedirs(tmp_dir, exist_ok=True)

    entries: List[Dict[str, Any]] = []

    if not skip_download:
        for pack in PACKS:
            zip_path = os.path.join(tmp_dir, f"{pack['id']}.zip")
            dest = os.path.join(lib_root, pack["id"])
            if _download_pack(pack, zip_path):
                _extract_zip(zip_path, dest)
                _write_license(pack)
                _log(f"  extracted -> {dest}")
                if pack["id"] == "open_lofi":
                    _prune_open_lofi(lib_root)
            else:
                _log(f"  WARNING: skipped {pack['id']} (download failed)")

    # open-lofi may extract to nested folder
    open_root = os.path.join(lib_root, "open_lofi")
    if os.path.isdir(open_root):
        entries.extend(_index_loops_from_dir("open_lofi", "open_lofi", lib_root, "layer", max_files=16))

    holizna_root = os.path.join(lib_root, "holizna_happy_lofi")
    if os.path.isdir(holizna_root):
        entries.extend(_index_loops_from_dir("holizna_happy_lofi", "holizna_happy_lofi", lib_root, "chords", max_files=12))

    drum_entries, kit_paths = _index_drum_one_shots(
        ["oga_fantasy_drums", "holizna_happy_lofi"],
        lib_root,
        "cc0",
    )
    entries.extend(drum_entries)

    api_key = os.environ.get("FREESOUND_API_KEY", "").strip()
    entries.extend(_fetch_freesound_previews(api_key or None, lib_root))

    # dedupe by id
    seen = set()
    unique: List[Dict[str, Any]] = []
    for e in entries:
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        unique.append(e)

    presets = _build_presets(unique, kit_paths)
    _write_sample_presets(presets)

    manifest = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entries": unique,
        "presets": presets,
    }
    save_manifest(manifest)
    _log(f"\nManifest: {len(unique)} entries, {len(presets)} presets -> {manifest_path()}")
    return manifest


def manifest_path() -> str:
    return os.path.join(licensed_library_dir(), "manifest.json")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Fetch CC0 sample packs for Mall Music Studio")
    parser.add_argument("--skip-download", action="store_true", help="Rebuild manifest from existing files only")
    args = parser.parse_args()
    fetch_all(skip_download=args.skip_download)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
