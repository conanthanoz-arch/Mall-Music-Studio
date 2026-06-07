"""Drum kit renderer driven by instrument preset JSON."""

from typing import Any, Dict, Optional

import numpy as np

from music_theory import SAMPLE_RATE


def _perc_envelope(n: int, attack_ms: float = 1.5, decay_power: float = 2.8) -> np.ndarray:
    attack = max(1, int(SAMPLE_RATE * attack_ms / 1000.0))
    env = np.linspace(1.0, 0.0, n) ** decay_power
    env[:attack] = np.linspace(0.0, 1.0, attack) ** 0.5
    return env


def _one_pole_lowpass(data: np.ndarray, cutoff_hz: float) -> np.ndarray:
    if len(data) == 0 or cutoff_hz <= 0:
        return data
    alpha = 1.0 - np.exp(-2.0 * np.pi * cutoff_hz / SAMPLE_RATE)
    out = np.empty_like(data)
    out[0] = data[0]
    for i in range(1, len(data)):
        out[i] = out[i - 1] + alpha * (data[i] - out[i - 1])
    return out


def _one_pole_highpass(data: np.ndarray, cutoff_hz: float) -> np.ndarray:
    if len(data) == 0 or cutoff_hz <= 0:
        return data
    alpha = np.exp(-2.0 * np.pi * cutoff_hz / SAMPLE_RATE)
    out = np.empty_like(data)
    out[0] = data[0]
    for i in range(1, len(data)):
        out[i] = alpha * (out[i - 1] + data[i] - data[i - 1])
    return out


def _bandpass(data: np.ndarray, hp_hz: float, lp_hz: float) -> np.ndarray:
    return _one_pole_lowpass(_one_pole_highpass(data, hp_hz), lp_hz)


def _filtered_noise(
    duration: float,
    volume: float,
    rng: np.random.Generator,
    hp_hz: Optional[float] = None,
    lp_hz: Optional[float] = None,
) -> np.ndarray:
    n = int(SAMPLE_RATE * duration)
    if n <= 0:
        return np.array([], dtype=np.float64)
    noise = rng.standard_normal(n)
    if hp_hz or lp_hz:
        noise = _bandpass(noise, hp_hz or 20.0, lp_hz or (SAMPLE_RATE * 0.45))
    env = _perc_envelope(n, attack_ms=0.8, decay_power=3.2)
    peak = np.max(np.abs(noise))
    if peak > 0:
        noise = noise / peak
    return noise * env * volume


def _kick_lofi() -> np.ndarray:
    dur = 0.14
    n = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    freq = 48 + (90 * np.exp(-t * 45))
    wave = np.sin(2 * np.pi * freq * t)
    env = _perc_envelope(n, attack_ms=2.0, decay_power=1.8)
    return np.tanh(wave * 0.9) * env


def _kick_808() -> np.ndarray:
    dur = 0.45
    n = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    freq = 36 + (28 * np.exp(-t * 6))
    wave = np.sin(2 * np.pi * freq * t)
    env = _perc_envelope(n, attack_ms=1.0, decay_power=1.2)
    return np.tanh(wave * 0.95) * env


def _kick_tight() -> np.ndarray:
    dur = 0.09
    n = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    freq = 55 + (70 * np.exp(-t * 60))
    wave = np.sin(2 * np.pi * freq * t)
    env = _perc_envelope(n, attack_ms=1.5, decay_power=2.2)
    return np.tanh(wave * 0.85) * env


def _snare_lofi(rng: np.random.Generator) -> np.ndarray:
    n_body = int(SAMPLE_RATE * 0.09)
    t = np.linspace(0, 0.09, n_body, endpoint=False)
    body = np.sin(2 * np.pi * 200 * t) * np.exp(-t * 35) * 0.35
    tail = _filtered_noise(0.10, 0.22, rng, hp_hz=400, lp_hz=6000)
    n = max(len(body), len(tail))
    out = np.zeros(n, dtype=np.float64)
    out[: len(body)] += body
    out[: len(tail)] += tail
    return out


def _snare_crisp(rng: np.random.Generator) -> np.ndarray:
    n_body = int(SAMPLE_RATE * 0.06)
    t = np.linspace(0, 0.06, n_body, endpoint=False)
    body = np.sin(2 * np.pi * 240 * t) * np.exp(-t * 50) * 0.42
    tail = _filtered_noise(0.07, 0.28, rng, hp_hz=800, lp_hz=9000)
    n = max(len(body), len(tail))
    out = np.zeros(n, dtype=np.float64)
    out[: len(body)] += body
    out[: len(tail)] += tail
    return out


def _snare_808_clap(rng: np.random.Generator) -> np.ndarray:
    return _filtered_noise(0.08, 0.38, rng, hp_hz=600, lp_hz=7500)


def _hat_closed(piece_type: str, rng: np.random.Generator) -> np.ndarray:
    if piece_type == "808_hat":
        return _filtered_noise(0.022, 0.04, rng, hp_hz=7000, lp_hz=13000)
    dur = 0.028
    vol = 0.045
    return _filtered_noise(dur, vol, rng, hp_hz=5500, lp_hz=14000)


def _hat_open(piece_type: str, rng: np.random.Generator) -> np.ndarray:
    if piece_type == "808_hat_open":
        return _filtered_noise(0.08, 0.035, rng, hp_hz=6000, lp_hz=12000)
    dur = 0.055
    vol = 0.035
    return _filtered_noise(dur, vol, rng, hp_hz=5500, lp_hz=14000)


_KICK_RENDER = {
    "lofi": _kick_lofi,
    "808": _kick_808,
    "tight": _kick_tight,
}

_SNARE_RENDER = {
    "lofi": _snare_lofi,
    "crisp": _snare_crisp,
    "808_clap": _snare_808_clap,
}


def render_kick(piece: Dict[str, Any], rng: np.random.Generator) -> np.ndarray:
    fn = _KICK_RENDER.get(piece.get("type", "lofi"), _kick_lofi)
    wave = fn()
    return wave * float(piece.get("volume", 1.0))


def render_snare(piece: Dict[str, Any], rng: np.random.Generator) -> np.ndarray:
    fn = _SNARE_RENDER.get(piece.get("type", "lofi"), _snare_lofi)
    return fn(rng) * float(piece.get("volume", 1.0))


def render_hihat(piece: Dict[str, Any], closed: bool, rng: np.random.Generator) -> np.ndarray:
    ptype = piece.get("type", "lofi_closed")
    if closed:
        wave = _hat_closed(ptype.replace("_open", "_closed") if "open" in ptype else ptype, rng)
    else:
        open_type = ptype.replace("_closed", "_open") if "closed" in ptype else ptype
        if open_type.endswith("_hat") and not open_type.endswith("_open"):
            open_type = "808_hat_open" if "808" in open_type else "lofi_open"
        wave = _hat_open(open_type, rng)
    return wave * float(piece.get("volume", 1.0))


def render_drum_hit(
    kit: Dict[str, Any],
    piece_name: str,
    closed_hat: bool = True,
    rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    rng = rng or np.random.default_rng()
    if piece_name == "kick":
        return render_kick(kit.get("kick", {}), rng)
    if piece_name == "snare":
        return render_snare(kit.get("snare", {}), rng)
    if piece_name == "hihat":
        key = "hihat_closed" if closed_hat else "hihat_open"
        return render_hihat(kit.get(key, kit.get("hihat_closed", {})), closed_hat, rng)
    return np.array([], dtype=np.float64)
