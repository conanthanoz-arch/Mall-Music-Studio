"""Procedural lo-fi audio synthesis: drums, bass, chords, melody."""

import random
import wave
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from mix_tracks import default_mix_tracks, migrate_to_mix_tracks, normalize_mix_tracks
from melody_generator import generate_melody_steps
from music_theory import SAMPLE_RATE, THEME_PROFILES, chord_tones
from track_renderer import MeasureContext, aggregate_stem_buckets, render_mix_track

KICK_PROB = [1.0, 0.0, 0.1, 0.0, 0.0, 0.0, 0.2, 0.8, 0.1, 0.9, 0.0, 0.2, 0.0, 0.0, 0.1, 0.0]
SNARE_PROB = [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.1]
HIHAT_PROB = [1.0, 0.2, 0.9, 0.3, 1.0, 0.2, 0.9, 0.3, 1.0, 0.2, 0.9, 0.3, 1.0, 0.2, 0.9, 0.7]

_numpy_rng: Optional[np.random.Generator] = None


def set_synthesis_seed(seed: Optional[int]) -> None:
    """Seed Python random + NumPy for fully reproducible tracks."""
    global _numpy_rng
    if seed is not None:
        random.seed(seed)
        _numpy_rng = np.random.default_rng(seed)
    else:
        _numpy_rng = np.random.default_rng()


def _rng() -> np.random.Generator:
    if _numpy_rng is None:
        return np.random.default_rng()
    return _numpy_rng


def normalize_instrument_config(config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Return mix track list from legacy instruments dict or tracks list."""
    if config is None:
        return default_mix_tracks()
    if isinstance(config, list):
        return normalize_mix_tracks(config)
    return migrate_to_mix_tracks(config)


def _drum_seed_from_tracks(tracks: List[Dict[str, Any]], global_seed: Optional[int]) -> int:
    for track in tracks:
        if track.get("mode") == "drums" and not track.get("mute"):
            return int(track.get("seed", global_seed or 0))
    return int(global_seed or 0)


def generate_drum_pattern(seed: Optional[int] = None) -> Dict[str, List[int]]:
    if seed is not None:
        random.seed(seed)
    kick, snare, hihat = [], [], []
    for step in range(16):
        kick.append(1 if random.random() < KICK_PROB[step] else 0)
        snare.append(1 if random.random() < SNARE_PROB[step] else 0)
        hihat.append(1 if random.random() < HIHAT_PROB[step] else 0)
    return {"kick": kick, "snare": snare, "hihat": hihat}


def step_times_visual(bpm: float, swing: float) -> List[float]:
    """Deterministic step positions for groove grid (no humanize jitter)."""
    step_duration = (60.0 / bpm) / 4.0
    times = []
    for step in range(16):
        t = step * step_duration
        if step % 2 != 0:
            t += step_duration * swing
        times.append(t)
    return times


def step_timestamps(bpm: float, swing: float) -> List[float]:
    step_duration = (60.0 / bpm) / 4.0
    times = []
    for step in range(16):
        t = step * step_duration
        if step % 2 != 0:
            t += step_duration * swing
        t += random.gauss(0, 0.002)
        times.append(max(0.0, t))
    return times


def _lowpass_fft(data: np.ndarray, cutoff_hz: float) -> np.ndarray:
    if len(data) == 0:
        return data
    spectrum = np.fft.rfft(data)
    freqs = np.fft.rfftfreq(len(data), 1.0 / SAMPLE_RATE)
    spectrum[freqs > cutoff_hz] = 0
    return np.fft.irfft(spectrum, len(data))


def _mix_at(buffer: np.ndarray, start: int, wave: np.ndarray) -> None:
    if len(wave) == 0:
        return
    end = min(start + len(wave), len(buffer))
    length = end - start
    if length <= 0:
        return
    buffer[start:end] += wave[:length]


def apply_reverb(buffer: np.ndarray, decay: float) -> np.ndarray:
    if decay <= 0.01:
        return buffer
    delay_samples = int(SAMPLE_RATE * 0.11)
    wet = np.zeros_like(buffer)
    wet[delay_samples:] = buffer[:-delay_samples] * decay * 0.35
    wet[int(SAMPLE_RATE * 0.07) :] += buffer[: -int(SAMPLE_RATE * 0.07)] * decay * 0.15
    return buffer + wet


def _lofi_warmth(buffer: np.ndarray) -> np.ndarray:
    warmed = _lowpass_fft(buffer, 11000)
    return buffer * 0.55 + warmed * 0.45


def _soft_limit(buffer: np.ndarray, ceiling: float = 0.88) -> np.ndarray:
    peak = np.max(np.abs(buffer))
    if peak > 0:
        buffer = buffer / peak * min(ceiling, peak)
    return np.tanh(buffer * 1.15) / np.tanh(1.15) * ceiling


def synthesize_measure(
    theme_id: str,
    bpm: float = 80,
    swing: float = 0.15,
    sidechain_depth: float = 0.6,
    melody_density: int = 70,
    reverb_decay: float = 0.45,
    chord_index: int = 0,
    drum_pattern: Optional[Dict[str, List[int]]] = None,
    melody_steps: Optional[List[Optional[int]]] = None,
    seed: Optional[int] = None,
    return_stems: bool = False,
    instruments: Optional[Any] = None,
    mix_tracks: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[np.ndarray, Dict[str, List[int]], List[Optional[int]], Optional[Dict[str, np.ndarray]]]:
    if seed is not None:
        set_synthesis_seed(seed)

    tracks = normalize_instrument_config(mix_tracks if mix_tracks is not None else instruments)
    profile = THEME_PROFILES[theme_id]
    prog = profile["progression"][chord_index % len(profile["progression"])]
    bass_root = prog["root_midi"] - 12
    chord_midis = chord_tones(prog["root_midi"], prog["intervals"])

    drum_seed = _drum_seed_from_tracks(tracks, seed)
    drums = drum_pattern or generate_drum_pattern(drum_seed)
    melody = melody_steps or generate_melody_steps(theme_id, melody_density, seed)

    step_dur = (60.0 / bpm) / 4.0
    measure_dur = step_dur * 16
    total = int(SAMPLE_RATE * measure_dur)
    times = step_timestamps(bpm, swing)

    ctx = MeasureContext(
        theme_id=theme_id,
        bpm=bpm,
        swing=swing,
        sidechain_depth=sidechain_depth,
        melody_density=melody_density,
        global_seed=seed,
        bass_root=bass_root,
        chord_midis=chord_midis,
        melody_steps=melody,
        drum_pattern=drums,
        step_times=times,
        step_dur=step_dur,
        total_samples=total,
        kick_steps=drums["kick"],
    )
    for track in tracks:
        if track.get("mode") == "counter_melody" and not track.get("mute"):
            ctx.counter_melodies[track["id"]] = generate_melody_steps(
                theme_id, melody_density, seed=track.get("seed", 0)
            )

    track_bufs: Dict[str, np.ndarray] = {}
    dry = np.zeros(total, dtype=np.float64)
    for track in tracks:
        rng = np.random.default_rng(int(track.get("seed", seed or 0)))
        audio = render_mix_track(track, ctx, rng)
        track_bufs[track["id"]] = audio
        if not track.get("mute"):
            dry += audio

    warmed = _lofi_warmth(dry)
    with_reverb = apply_reverb(warmed.copy(), reverb_decay)
    reverb_buf = with_reverb - warmed
    buf = _soft_limit(with_reverb)

    stems = None
    if return_stems:
        buckets = aggregate_stem_buckets(track_bufs, tracks)
        stems = {
            "drums": buckets["drums"],
            "bass": buckets["bass"],
            "chords": buckets["chords"],
            "melody": buckets["melody"],
            "reverb": reverb_buf,
        }
    return buf, drums, melody, stems


def synthesize_track(
    theme_id: str,
    bpm: float = 80,
    swing: float = 0.15,
    sidechain_depth: float = 0.6,
    melody_density: int = 70,
    reverb_decay: float = 0.45,
    num_measures: int = 8,
    seed: Optional[int] = None,
    instruments: Optional[Any] = None,
    mix_tracks: Optional[List[Dict[str, Any]]] = None,
) -> np.ndarray:
    if seed is not None:
        set_synthesis_seed(seed)

    tracks = normalize_instrument_config(mix_tracks if mix_tracks is not None else instruments)
    drum_seed = _drum_seed_from_tracks(tracks, seed)

    parts = []
    drums = generate_drum_pattern(drum_seed)
    track_arg = mix_tracks if mix_tracks is not None else instruments
    for m in range(num_measures):
        chunk, drums, _, _ = synthesize_measure(
            theme_id=theme_id,
            bpm=bpm,
            swing=swing,
            sidechain_depth=sidechain_depth,
            melody_density=melody_density,
            reverb_decay=reverb_decay,
            chord_index=m,
            drum_pattern=drums if m % 4 != 0 else generate_drum_pattern(seed=(drum_seed or 0) + m),
            seed=(seed or 0) + m * 17,
            mix_tracks=track_arg,
        )
        parts.append(chunk)
    return np.concatenate(parts)


def buffer_to_int16(buffer: np.ndarray) -> np.ndarray:
    clipped = np.clip(buffer, -1.0, 1.0)
    return (clipped * 32767).astype(np.int16)


def save_wav(path: str, buffer: np.ndarray) -> float:
    pcm = buffer_to_int16(buffer)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())
    return len(buffer) / SAMPLE_RATE


def buffer_duration_sec(buffer: np.ndarray) -> float:
    return len(buffer) / SAMPLE_RATE
