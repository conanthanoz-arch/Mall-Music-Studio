"""Analyze stem audio regions and fit VA / drum_kit presets (no samples stored)."""

import os
import sys
import uuid
from typing import Any, Dict, Optional, Tuple

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from music_theory import SAMPLE_RATE
from waveform_utils import load_wav_mono

STEM_SLOT = {
    "drums": "drums",
    "drum": "drums",
    "bass": "bass",
    "vocals": "lead",
    "other": "layer",
    "guitar": "layer",
    "piano": "chords",
}

SILENCE_PEAK = 0.008


def _frame_energy(data: np.ndarray, frame: int, hop: int) -> np.ndarray:
    n = max(1, (len(data) - frame) // hop)
    out = np.zeros(n, dtype=np.float64)
    for i in range(n):
        start = i * hop
        chunk = data[start : start + frame]
        out[i] = np.sqrt(np.mean(chunk * chunk))
    return out


def find_best_sample_region(
    data: np.ndarray,
    window_sec: float = 30.0,
    sr: int = SAMPLE_RATE,
) -> float:
    """Find start time (seconds) of the loudest window."""
    window = int(window_sec * sr)
    if len(data) <= window:
        return 0.0
    hop = max(1, int(sr * 1.5))
    frame = int(sr * 0.08)
    best_start = 0
    best_score = -1.0
    for start in range(0, len(data) - window, hop):
        seg = data[start : start + window]
        env = _frame_energy(seg, frame, max(1, frame // 2))
        if len(env) == 0:
            continue
        score = float(np.mean(env) + np.percentile(env, 88) * 0.65)
        if score > best_score:
            best_score = score
            best_start = start
    return best_start / sr


def slice_region(
    data: np.ndarray,
    analyze_start_sec: float,
    analyze_sec: float,
    sr: int = SAMPLE_RATE,
) -> np.ndarray:
    start = max(0, int(analyze_start_sec * sr))
    end = min(len(data), start + int(analyze_sec * sr))
    if end <= start:
        end = min(len(data), start + int(sr))
    return data[start:end]


def _spectral_centroid(seg: np.ndarray, sr: int = SAMPLE_RATE) -> float:
    if len(seg) < 256:
        return 1000.0
    window = np.hanning(len(seg))
    spec = np.abs(np.fft.rfft(seg.astype(np.float64) * window))
    freqs = np.fft.rfftfreq(len(seg), 1.0 / sr)
    total = np.sum(spec)
    if total < 1e-12:
        return 1000.0
    return float(np.sum(freqs * spec) / total)


def _band_energy(seg: np.ndarray, sr: int, lo: float, hi: float) -> float:
    if len(seg) < 32:
        return 0.0
    window = np.hanning(len(seg))
    spec = np.abs(np.fft.rfft(seg.astype(np.float64) * window))
    freqs = np.fft.rfftfreq(len(seg), 1.0 / sr)
    mask = (freqs >= lo) & (freqs < hi)
    if not np.any(mask):
        return 0.0
    return float(np.sum(spec[mask] ** 2))


def _attack_ms(seg: np.ndarray, sr: int = SAMPLE_RATE) -> float:
    env = np.abs(seg[: min(len(seg), int(sr * 3))])
    if len(env) < 64:
        return 12.0
    peak = float(np.max(env))
    if peak < 1e-9:
        return 12.0
    idx = int(np.argmax(env > peak * 0.55))
    return max(3.0, 1000.0 * idx / sr)


def _trim_leading_silence(seg: np.ndarray, sr: int = SAMPLE_RATE) -> np.ndarray:
    peak = float(np.max(np.abs(seg))) if len(seg) else 0.0
    if peak < 1e-9:
        return seg
    floor = peak * 0.04
    start = 0
    for i, v in enumerate(np.abs(seg)):
        if v >= floor:
            start = max(0, i - int(sr * 0.003))
            break
    return seg[start:]


def _descriptor(centroid: float, low_ratio: float, attack: float) -> str:
    if low_ratio > 0.55:
        return "Sub"
    if centroid > 4500:
        return "Bright"
    if centroid > 2500:
        return "Crisp"
    if attack > 35:
        return "Soft"
    if attack < 12:
        return "Punchy"
    return "Warm"


def make_emulated_preset_id(descriptor: str, stem_role: str) -> str:
    slug = descriptor.lower().replace(" ", "_")
    role = stem_role.lower().replace(" ", "_")[:12]
    suffix = uuid.uuid4().hex[:4]
    return f"emu_{slug}_{role}_{suffix}"


def make_emulated_label(descriptor: str, stem_role: str) -> str:
    role = stem_role.replace("_", " ").title()
    if stem_role.lower() in ("drums", "drum"):
        return f"{descriptor} {role} Kit (emulated)"
    return f"{descriptor} {role} (emulated)"


def analyze_region(
    stem_wav: str,
    stem_name: str,
    analyze_start_sec: float,
    analyze_sec: float,
) -> Tuple[np.ndarray, Dict[str, float], Optional[str]]:
    """Return (segment, metrics, error_code). error_code is 'region_silent' if too quiet."""
    full = load_wav_mono(stem_wav)
    seg = slice_region(full, analyze_start_sec, analyze_sec)
    seg = _trim_leading_silence(seg)
    peak = float(np.max(np.abs(seg))) if len(seg) else 0.0
    if peak < SILENCE_PEAK:
        return seg, {"peak": peak}, "region_silent"

    low = _band_energy(seg, SAMPLE_RATE, 35, 220)
    mid = _band_energy(seg, SAMPLE_RATE, 220, 5000)
    high = _band_energy(seg, SAMPLE_RATE, 5000, 14000)
    total = low + mid + high + 1e-12
    centroid = _spectral_centroid(seg)
    attack = _attack_ms(seg)
    metrics = {
        "peak": peak,
        "centroid": centroid,
        "low_ratio": low / total,
        "mid_ratio": mid / total,
        "high_ratio": high / total,
        "attack_ms": attack,
        "rms": float(np.sqrt(np.mean(seg ** 2))),
    }
    return seg, metrics, None


def fit_emulated_preset(
    stem_wav: str,
    stem_name: str,
    analyze_start_sec: float,
    analyze_sec: float,
    preset_id: Optional[str] = None,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Build a va_voice or drum_kit preset from a stem region.
    Returns (preset_dict, error_code).
    """
    _seg, metrics, err = analyze_region(stem_wav, stem_name, analyze_start_sec, analyze_sec)
    if err:
        return {}, err

    stem_key = stem_name.lower()
    slot = STEM_SLOT.get(stem_key, "layer")
    centroid = metrics["centroid"]
    low_ratio = metrics["low_ratio"]
    high_ratio = metrics["high_ratio"]
    attack = metrics["attack_ms"]
    descriptor = _descriptor(centroid, low_ratio, attack)
    preset_id = preset_id or make_emulated_preset_id(descriptor, stem_key)
    label = make_emulated_label(descriptor, STEM_SLOT.get(stem_key, stem_key))

    base: Dict[str, Any] = {
        "id": preset_id,
        "label": label,
        "slot": slot,
        "engine": "va_voice",
        "volume": 1.0,
        "fidelity_hint": "emulated",
        "source_stem": stem_key,
    }

    if stem_key in ("drums", "drum"):
        kick_type = "808" if low_ratio > 0.45 else ("tight" if attack < 15 else "lofi")
        snare_type = "crisp" if high_ratio > 0.15 else ("808_clap" if centroid > 3000 else "lofi")
        hat_closed = "808_hat" if high_ratio > 0.12 else "lofi_closed"
        hat_open = "808_hat_open" if high_ratio > 0.12 else "lofi_open"
        kick_vol = min(0.65, 0.42 + low_ratio * 0.5)
        snare_vol = min(1.1, 0.75 + metrics["mid_ratio"] * 0.6)
        hat_vol = min(1.0, 0.6 + high_ratio * 1.2)
        base.update(
            {
                "slot": "drums",
                "engine": "drum_kit",
                "kick": {"type": kick_type, "volume": round(kick_vol, 3)},
                "snare": {"type": snare_type, "volume": round(snare_vol, 3)},
                "hihat_closed": {"type": hat_closed, "volume": round(hat_vol, 3)},
                "hihat_open": {"type": hat_open, "volume": round(hat_vol * 0.85, 3)},
            }
        )
        return base, None

    if stem_key == "bass" or (slot == "bass" or low_ratio > 0.5 or centroid < 400):
        wave = "sine" if centroid < 220 else "saw"
        base.update(
            {
                "slot": "bass",
                "oscillators": [{"wave": wave, "level": 1.0}],
                "filter": {"type": "lp", "cutoff_hz": max(220, min(950, centroid * 1.1))},
                "envelope": {
                    "attack_ms": max(8.0, min(25.0, attack)),
                    "decay_ms": 180,
                    "sustain": 0.65,
                    "release_ms": 60,
                },
            }
        )
        return base, None

    if stem_key == "vocals" or (attack > 25 and centroid < 2800):
        base.update(
            {
                "slot": "lead",
                "oscillators": [
                    {"wave": "sine", "level": 0.55, "detune_cents": -5},
                    {"wave": "triangle", "level": 0.4, "detune_cents": 5},
                ],
                "breath_noise": 0.12 if high_ratio > 0.08 else 0.06,
                "filter": {"type": "bandpass", "hp_hz": 400, "lp_hz": min(6000, centroid * 2.2)},
                "envelope": {
                    "attack_ms": max(10.0, min(45.0, attack)),
                    "decay_ms": 220,
                    "sustain": 0.45,
                    "release_ms": 120,
                },
                "vibrato": {"rate_hz": 5.0, "depth_cents": 8},
            }
        )
        return base, None

    if attack > 22 or stem_key in ("other", "piano", "guitar"):
        base.update(
            {
                "slot": "chords" if stem_key == "piano" else slot,
                "oscillators": [
                    {"wave": "sine", "level": 0.42, "detune_cents": -6},
                    {"wave": "sine", "level": 0.42, "detune_cents": 6},
                ],
                "filter": {"type": "lp", "cutoff_hz": max(800, min(5200, centroid * 1.4))},
                "envelope": {
                    "attack_ms": max(12.0, min(50.0, attack)),
                    "decay_ms": 380,
                    "sustain": 0.72,
                    "release_ms": 200,
                },
                "fx_chain": [{"type": "chorus", "mix": 0.28}],
            }
        )
        return base, None

    base.update(
        {
            "slot": "lead",
            "oscillators": [{"wave": "triangle" if attack < 18 else "saw", "level": 0.88}],
            "filter": {"type": "lp", "cutoff_hz": max(600, min(6200, centroid * 1.6))},
            "envelope": {
                "attack_ms": max(8.0, min(35.0, attack)),
                "decay_ms": 220,
                "sustain": 0.38,
                "release_ms": 100,
            },
        }
    )
    return base, None
