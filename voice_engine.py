"""Virtual-analog voice renderer driven by instrument preset JSON."""

from typing import Any, Dict, List, Optional

import numpy as np

from music_theory import SAMPLE_RATE, midi_to_hz


def _adsr(n: int, attack_ms: float, decay_ms: float, sustain: float, release_ms: float) -> np.ndarray:
    if n <= 0:
        return np.array([], dtype=np.float64)
    attack = max(1, int(SAMPLE_RATE * attack_ms / 1000.0))
    decay = max(1, int(SAMPLE_RATE * decay_ms / 1000.0))
    release = max(1, int(SAMPLE_RATE * release_ms / 1000.0))
    sustain = float(np.clip(sustain, 0.0, 1.0))

    env = np.zeros(n, dtype=np.float64)
    pos = 0
    seg = min(attack, n - pos)
    if seg > 0:
        env[pos : pos + seg] = np.linspace(0.0, 1.0, seg) ** 0.6
        pos += seg
    seg = min(decay, n - pos)
    if seg > 0:
        env[pos : pos + seg] = np.linspace(1.0, sustain, seg)
        pos += seg
    hold = max(0, n - pos - release)
    if hold > 0:
        env[pos : pos + hold] = sustain
        pos += hold
    seg = n - pos
    if seg > 0:
        start = env[pos - 1] if pos > 0 else sustain
        env[pos:] = np.linspace(start, 0.0, seg)
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


def _osc_wave(wave: str, phase: np.ndarray) -> np.ndarray:
    if wave == "sine":
        return np.sin(phase)
    if wave == "triangle":
        return (2.0 / np.pi) * np.arcsin(np.sin(phase))
    if wave == "saw":
        return 2.0 * (phase / (2.0 * np.pi) - np.floor(phase / (2.0 * np.pi) + 0.5))
    if wave == "square":
        return np.sign(np.sin(phase))
    return np.sin(phase)


def _apply_filter(data: np.ndarray, filt: Optional[Dict[str, Any]]) -> np.ndarray:
    if not filt or len(data) == 0:
        return data
    ftype = filt.get("type", "lp")
    if ftype == "lp":
        return _one_pole_lowpass(data, float(filt.get("cutoff_hz", 8000)))
    if ftype == "bandpass":
        hp = float(filt.get("hp_hz", 400))
        lp = float(filt.get("lp_hz", 6000))
        return _one_pole_lowpass(_one_pole_highpass(data, hp), lp)
    return data


def _apply_chorus(data: np.ndarray, mix: float) -> np.ndarray:
    if len(data) == 0 or mix <= 0:
        return data
    delay = int(SAMPLE_RATE * 0.018)
    wet = np.zeros_like(data)
    if delay < len(data):
        wet[delay:] = data[:-delay] * 0.85
        wet[:delay] = data[:delay] * 0.4
    return data * (1.0 - mix) + wet * mix


def _apply_fx_chain(data: np.ndarray, chain: Optional[List[Dict[str, Any]]]) -> np.ndarray:
    if not chain:
        return data
    out = data
    for fx in chain:
        if fx.get("type") == "chorus":
            out = _apply_chorus(out, float(fx.get("mix", 0.3)))
    return out


def render_voice(
    preset: Dict[str, Any],
    midi_note: float,
    duration: float,
    volume: float = 1.0,
    rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """Render one note from a va_voice preset."""
    if duration <= 0:
        return np.array([], dtype=np.float64)

    rng = rng or np.random.default_rng()
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    freq = midi_to_hz(midi_note)

    vibrato = preset.get("vibrato") or {}
    v_rate = float(vibrato.get("rate_hz", 0))
    v_depth = float(vibrato.get("depth_cents", 0))
    if v_rate > 0 and v_depth > 0:
        vib = np.sin(2 * np.pi * v_rate * t) * (v_depth / 1200.0)
        phase_inc = 2 * np.pi * freq * t * (1.0 + vib)
    else:
        phase_inc = 2 * np.pi * freq * t

    oscs = preset.get("oscillators") or [{"wave": "sine", "level": 1.0}]
    wave = np.zeros(n, dtype=np.float64)
    for osc in oscs:
        detune = float(osc.get("detune_cents", 0)) / 1200.0
        level = float(osc.get("level", 0.5))
        phase = phase_inc * (2 ** detune) if detune else phase_inc
        wave += _osc_wave(osc.get("wave", "sine"), phase) * level

    fm = preset.get("fm")
    if fm:
        ratio = float(fm.get("ratio", 2.0))
        index = float(fm.get("index", 1.0))
        mod = np.sin(2 * np.pi * freq * ratio * t) * index
        carrier = np.sin(2 * np.pi * freq * t + mod)
        wave = wave * 0.35 + carrier * 0.65

    env_cfg = preset.get("envelope") or {}
    env = _adsr(
        n,
        float(env_cfg.get("attack_ms", 5)),
        float(env_cfg.get("decay_ms", 120)),
        float(env_cfg.get("sustain", 0.5)),
        float(env_cfg.get("release_ms", 80)),
    )
    wave *= env

    breath = float(preset.get("breath_noise", 0))
    if breath > 0:
        noise = rng.standard_normal(n)
        breath_env = env * np.exp(-t * 18)
        wave += noise * breath * breath_env * 0.35

    wave = _apply_filter(wave, preset.get("filter"))

    sat = float(preset.get("saturation", 0))
    if sat > 0:
        wave = np.tanh(wave * (1.0 + sat * 3.0)) / (1.0 + sat)

    wave = _apply_fx_chain(wave, preset.get("fx_chain"))

    preset_vol = float(preset.get("volume", 1.0))
    peak = np.max(np.abs(wave))
    if peak > 0:
        wave = wave / peak
    return wave * volume * preset_vol
