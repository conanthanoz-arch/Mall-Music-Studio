"""Playlist arrangement persistence and master-loop export."""

import json
import os
import subprocess
import wave
from typing import Any, Dict, List, Optional

import numpy as np

from music_theory import SAMPLE_RATE
from waveform_utils import load_wav_mono

SIX_HOUR_SEC = 6 * 60 * 60
FRAME_RATE = 30


def playlist_path(library_dir: str) -> str:
    return os.path.join(library_dir, "playlist.json")


def load_library_metas(library_dir: str) -> List[Dict[str, Any]]:
    metas = []
    if not os.path.isdir(library_dir):
        return metas
    for name in sorted(os.listdir(library_dir)):
        if not name.endswith(".json") or name == "playlist.json":
            continue
        path = os.path.join(library_dir, name)
        try:
            with open(path, encoding="utf-8") as f:
                meta = json.load(f)
            wav = meta.get("wav_file") or os.path.join(
                library_dir, name.replace(".json", ".wav")
            )
            if os.path.exists(wav):
                meta["wav_file"] = wav
                meta["_json_path"] = path
                metas.append(meta)
        except (json.JSONDecodeError, OSError):
            pass
    return metas


def load_playlist(library_dir: str) -> List[Dict[str, Any]]:
    path = playlist_path(library_dir)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("tracks", [])


def save_playlist(library_dir: str, tracks: List[Dict[str, Any]]) -> str:
    os.makedirs(library_dir, exist_ok=True)
    path = playlist_path(library_dir)
    payload = {"tracks": tracks}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


def resolve_playlist_entries(
    library_dir: str, entries: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Fill missing fields from library JSON by wav_file match."""
    library = {m["wav_file"]: m for m in load_library_metas(library_dir)}
    resolved = []
    for entry in entries:
        wav = entry.get("wav_file")
        if not wav or not os.path.exists(wav):
            continue
        base = dict(library.get(wav, {}))
        base.update(entry)
        base["wav_file"] = wav
        if "duration_sec" not in base or not base["duration_sec"]:
            try:
                data = load_wav_mono(wav)
                base["duration_sec"] = len(data) / SAMPLE_RATE
            except (wave.Error, OSError):
                continue
        resolved.append(base)
    return resolved


def arrangement_duration_sec(tracks: List[Dict[str, Any]]) -> float:
    return sum(float(t.get("duration_sec", 0)) for t in tracks)


def concat_wavs(tracks: List[Dict[str, Any]]) -> np.ndarray:
    parts = []
    for track in tracks:
        data = load_wav_mono(track["wav_file"])
        trim_in = int(float(track.get("trim_in_sec", 0) or 0) * SAMPLE_RATE)
        trim_out = track.get("trim_out_sec")
        if trim_out is not None:
            end = int(float(trim_out) * SAMPLE_RATE)
        else:
            end = len(data)
        end = min(max(trim_in, end), len(data))
        trim_in = max(0, min(trim_in, len(data)))
        parts.append(data[trim_in:end])
    if not parts:
        return np.array([], dtype=np.float64)
    return np.concatenate(parts)


def save_master_wav(buffer: np.ndarray, path: str) -> None:
    clipped = np.clip(buffer, -1.0, 1.0)
    pcm = (clipped * 32767).astype(np.int16)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())


def export_master_mp3(wav_path: str, mp3_path: str) -> bool:
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                wav_path,
                "-ar",
                "44100",
                "-b:a",
                "192k",
                mp3_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def build_tracklist_snippet(tracks: List[Dict[str, Any]], fps: int = FRAME_RATE) -> str:
    lines = ["TRACKLIST = ["]
    for t in tracks:
        title = t.get("title", "Untitled")
        artist = t.get("artist", "Mall Music Studio")
        dur = float(t.get("duration_sec", 0))
        lines.append(
            f'    {{"title": {title!r}, "artist": {artist!r}, "duration_sec": {dur:.3f}}},'
        )
    lines.append("]")
    total = arrangement_duration_sec(tracks)
    frames = sum(int(float(t.get("duration_sec", 0)) * fps) for t in tracks)
    lines.append("")
    lines.append(f"# Total: {total:.1f}s ({total/3600:.2f}h), {frames} frames @ {fps} FPS")
    return "\n".join(lines)


def format_duration(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    if h:
        return f"{h}:{m:02d}:{s:05.2f}"
    return f"{m}:{s:05.2f}"
