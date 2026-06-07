"""Licensed sample playback: one-shots and bar loops."""

import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict

import numpy as np

from licensed_library import resolve_sample_path
from music_theory import SAMPLE_RATE
from waveform_utils import load_wav_mono

_sample_cache: Dict[str, np.ndarray] = {}


def _ffmpeg_load_mono(path: str) -> np.ndarray:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError(f"ffmpeg required to load {path}")
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    try:
        proc = subprocess.run(
            [ffmpeg, "-y", "-i", path, "-ac", "1", "-ar", str(SAMPLE_RATE), tmp.name],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise ValueError(proc.stderr[:300] or "ffmpeg failed")
        return load_wav_mono(tmp.name)
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass


def _load_cached(path: str) -> np.ndarray:
    if path not in _sample_cache:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".wav":
            _sample_cache[path] = load_wav_mono(path)
        elif ext in (".mp3", ".ogg", ".flac", ".m4a"):
            _sample_cache[path] = _ffmpeg_load_mono(path)
        else:
            raise ValueError(f"Unsupported sample format: {path}")
    return _sample_cache[path]


def clear_sample_cache() -> None:
    _sample_cache.clear()


def _resample(data: np.ndarray, target_len: int) -> np.ndarray:
    if target_len <= 0:
        return np.array([], dtype=np.float64)
    if len(data) == target_len:
        return data.astype(np.float64)
    if len(data) == 0:
        return np.zeros(target_len, dtype=np.float64)
    x_old = np.linspace(0.0, 1.0, len(data))
    x_new = np.linspace(0.0, 1.0, target_len)
    return np.interp(x_new, x_old, data.astype(np.float64))


def _normalize_peak(data: np.ndarray, peak: float = 0.95) -> np.ndarray:
    if len(data) == 0:
        return data
    mx = float(np.max(np.abs(data)))
    if mx < 1e-9:
        return data
    return data / mx * peak


def render_one_shot(
    relative_path: str,
    volume: float = 1.0,
    pitch_semitones: float = 0.0,
) -> np.ndarray:
    path = resolve_sample_path(relative_path)
    if not os.path.isfile(path):
        return np.array([], dtype=np.float64)
    data = _load_cached(path)
    if pitch_semitones:
        factor = 2.0 ** (pitch_semitones / 12.0)
        new_len = max(1, int(len(data) / factor))
        data = _resample(data, new_len)
    data = _normalize_peak(data) * volume
    return data.astype(np.float64)


def render_loop_for_measure(
    relative_path: str,
    measure_samples: int,
    loop_bpm: float,
    target_bpm: float,
    bars: float = 1.0,
    volume: float = 1.0,
) -> np.ndarray:
    path = resolve_sample_path(relative_path)
    if not os.path.isfile(path) or measure_samples <= 0:
        return np.zeros(max(0, measure_samples), dtype=np.float64)

    data = _load_cached(path)
    if loop_bpm > 0 and target_bpm > 0:
        stretch = (target_bpm / loop_bpm) * (bars / 1.0)
        desired = max(1, int(len(data) / stretch))
        data = _resample(data, desired)

    out = np.zeros(measure_samples, dtype=np.float64)
    if len(data) == 0:
        return out

    pos = 0
    while pos < measure_samples:
        end = min(measure_samples, pos + len(data))
        chunk_len = end - pos
        out[pos:end] += data[:chunk_len] * volume
        pos += len(data)
    return _normalize_peak(out, peak=min(0.98, volume * 0.95 + 0.05))


def render_sample_kit_hit(
    preset: Dict[str, Any],
    role: str,
    closed_hat: bool = True,
    volume: float = 1.0,
) -> np.ndarray:
    key = role
    if role == "hihat":
        key = "hihat_closed" if closed_hat else "hihat_open"
    hit = preset.get(key) or preset.get(role) or {}
    rel = hit.get("path") or preset.get("path")
    if not rel:
        return np.array([], dtype=np.float64)
    vol = float(hit.get("volume", preset.get("volume", 1.0))) * volume
    pitch = float(hit.get("pitch_semitones", 0))
    return render_one_shot(rel, volume=vol, pitch_semitones=pitch)


def render_sample_loop_preset(
    preset: Dict[str, Any],
    measure_samples: int,
    target_bpm: float,
    volume: float = 1.0,
) -> np.ndarray:
    rel = preset.get("loop_path") or preset.get("path")
    if not rel:
        return np.zeros(max(0, measure_samples), dtype=np.float64)
    loop_bpm = float(preset.get("loop_bpm", target_bpm))
    bars = float(preset.get("bars", 1.0))
    vol = float(preset.get("volume", 1.0)) * volume
    return render_loop_for_measure(
        rel, measure_samples, loop_bpm, target_bpm, bars=bars, volume=vol
    )
