"""Render one mix track into an audio buffer for a single measure."""

from typing import Any, Dict, List, Optional

import numpy as np

from drum_engine import render_drum_hit
from instrument_presets import get_preset
from melody_generator import generate_melody_steps
from mix_tracks import stem_bucket_for_mode
from music_theory import SAMPLE_RATE, humanize_velocity
from sample_engine import render_sample_kit_hit, render_sample_loop_preset
from voice_engine import render_voice


def _mix_at(buffer: np.ndarray, start: int, wave: np.ndarray) -> None:
    if len(wave) == 0:
        return
    end = min(start + len(wave), len(buffer))
    length = end - start
    if length <= 0:
        return
    buffer[start:end] += wave[:length]


def _shift_midi(note: Optional[int], octave_shift: int) -> Optional[int]:
    if note is None:
        return None
    return note + 12 * octave_shift


def _render_note(
    preset: Dict[str, Any],
    midi_note: float,
    duration: float,
    volume: float,
    rng: np.random.Generator,
) -> np.ndarray:
    return render_voice(preset, midi_note, duration, volume=volume, rng=rng)


def _is_melodic_engine(preset: Dict[str, Any]) -> bool:
    return preset.get("engine") in ("va_voice", "sample_loop")


class MeasureContext:
    """Shared musical context for one measure."""

    def __init__(
        self,
        theme_id: str,
        bpm: float,
        swing: float,
        sidechain_depth: float,
        melody_density: int,
        global_seed: Optional[int],
        bass_root: int,
        chord_midis: List[int],
        melody_steps: List[Optional[int]],
        drum_pattern: Dict[str, List[int]],
        step_times: List[float],
        step_dur: float,
        total_samples: int,
        kick_steps: List[int],
    ):
        self.theme_id = theme_id
        self.bpm = bpm
        self.swing = swing
        self.sidechain_depth = sidechain_depth
        self.melody_density = melody_density
        self.global_seed = global_seed
        self.bass_root = bass_root
        self.chord_midis = chord_midis
        self.melody_steps = melody_steps
        self.drum_pattern = drum_pattern
        self.step_times = step_times
        self.step_dur = step_dur
        self.total_samples = total_samples
        self.kick_steps = kick_steps
        self.counter_melodies: Dict[str, List[Optional[int]]] = {}


def render_mix_track(
    track: Dict[str, Any],
    ctx: MeasureContext,
    rng: np.random.Generator,
) -> np.ndarray:
    if track.get("mute"):
        return np.zeros(ctx.total_samples, dtype=np.float64)

    mode = track.get("mode", "follow_melody")
    preset = get_preset(track.get("preset", "sine_lead"))
    vol = float(track.get("volume", 1.0))
    octave = int(track.get("octave_shift", 0))
    buf = np.zeros(ctx.total_samples, dtype=np.float64)
    engine = preset.get("engine", "va_voice")

    if mode in ("loop_chords", "loop_layer") and engine == "sample_loop":
        layer_vol = 0.65 if mode == "loop_chords" else 0.35
        loop = render_sample_loop_preset(
            preset, ctx.total_samples, ctx.bpm, volume=vol * layer_vol
        )
        return loop

    if mode == "drums" and engine == "sample_kit":
        for step in range(16):
            start = int(ctx.step_times[step] * SAMPLE_RATE)
            if start >= ctx.total_samples:
                continue
            if ctx.drum_pattern["hihat"][step]:
                closed = step != 15
                vel = 0.75 + humanize_velocity(50) / 254.0
                hat = render_sample_kit_hit(preset, "hihat", closed_hat=closed, volume=vel) * vel
                _mix_at(buf, start, hat)
            if ctx.drum_pattern["snare"][step]:
                sn = render_sample_kit_hit(preset, "snare", volume=humanize_velocity(80) / 127.0)
                _mix_at(buf, start, sn)
            if ctx.drum_pattern["kick"][step]:
                _mix_at(buf, start, render_sample_kit_hit(preset, "kick", volume=1.0))
        return buf * vol

    if mode == "drums" and engine == "drum_kit":
        for step in range(16):
            start = int(ctx.step_times[step] * SAMPLE_RATE)
            if start >= ctx.total_samples:
                continue
            if ctx.drum_pattern["hihat"][step]:
                closed = step != 15
                vel = 0.75 + humanize_velocity(50) / 254.0
                hat = render_drum_hit(preset, "hihat", closed_hat=closed, rng=rng) * vel
                _mix_at(buf, start, hat)
            if ctx.drum_pattern["snare"][step]:
                sn = render_drum_hit(preset, "snare", rng=rng) * (humanize_velocity(80) / 127.0)
                _mix_at(buf, start, sn)
            if ctx.drum_pattern["kick"][step]:
                _mix_at(buf, start, render_drum_hit(preset, "kick", rng=rng))
        return buf * vol

    if not _is_melodic_engine(preset):
        return buf

    for step in range(16):
        start = int(ctx.step_times[step] * SAMPLE_RATE)
        if start >= ctx.total_samples:
            continue

        if mode == "bass_root":
            bass_vol = (0.15 + (1.0 - ctx.sidechain_depth) * 0.25) * vol
            if ctx.drum_pattern["kick"][step]:
                bass_vol *= 1.0 - ctx.sidechain_depth * 0.75
            note = _render_note(
                preset, ctx.bass_root, ctx.step_dur * 1.4, volume=bass_vol, rng=rng
            )
            _mix_at(buf, start, note)

        elif mode == "chords":
            if step in (0, 8):
                for midi in ctx.chord_midis[:3]:
                    ch = _render_note(
                        preset,
                        midi - 12,
                        ctx.step_dur * 3.5,
                        volume=0.04 * vol,
                        rng=rng,
                    )
                    _mix_at(buf, start, ch)

        elif mode == "follow_chords":
            if step in (0, 4, 8, 12):
                for midi in ctx.chord_midis[:3]:
                    ch = _render_note(
                        preset,
                        midi - 12 + 12 * octave,
                        ctx.step_dur * 2.8,
                        volume=0.035 * vol,
                        rng=rng,
                    )
                    _mix_at(buf, start, ch)

        elif mode == "melody":
            m = _shift_midi(ctx.melody_steps[step], octave)
            if m is not None:
                lead = _render_note(preset, m, ctx.step_dur * 0.85, volume=0.07 * vol, rng=rng)
                _mix_at(buf, start, lead)

        elif mode == "follow_melody":
            m = _shift_midi(ctx.melody_steps[step], octave)
            if m is not None:
                lead = _render_note(preset, m, ctx.step_dur * 0.85, volume=0.06 * vol, rng=rng)
                _mix_at(buf, start, lead)

        elif mode == "counter_melody":
            counter = ctx.counter_melodies.get(track.get("id"))
            if counter is None:
                counter = generate_melody_steps(
                    ctx.theme_id, ctx.melody_density, seed=track.get("seed", 0)
                )
            m = _shift_midi(counter[step], octave)
            if m is not None:
                lead = _render_note(preset, m, ctx.step_dur * 0.8, volume=0.05 * vol, rng=rng)
                _mix_at(buf, start, lead)

    return buf


def aggregate_stem_buckets(
    track_bufs: Dict[str, np.ndarray], tracks: List[Dict[str, Any]]
) -> Dict[str, np.ndarray]:
    """Map per-track buffers into drums/bass/chords/melody lanes for visualization."""
    buckets: Dict[str, Optional[np.ndarray]] = {k: None for k in ("drums", "bass", "chords", "melody")}
    for track in tracks:
        if track.get("mute"):
            continue
        audio = track_bufs.get(track["id"])
        if audio is None:
            continue
        key = stem_bucket_for_mode(track.get("mode", ""))
        if buckets[key] is None:
            buckets[key] = np.zeros_like(audio)
        buckets[key] = buckets[key] + audio

    sample_len = 0
    for audio in track_bufs.values():
        sample_len = max(sample_len, len(audio))
    empty = np.zeros(sample_len, dtype=np.float64)
    return {k: (buckets[k] if buckets[k] is not None else empty) for k in buckets}
