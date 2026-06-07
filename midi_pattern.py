"""Parse MIDI files into 16-step patterns for one measure."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from music_theory import SAMPLE_RATE

try:
    import mido
except ImportError:
    mido = None  # type: ignore

# General MIDI drum map (subset)
GM_KICK = {35, 36}
GM_SNARE = {38, 40, 37}
GM_HAT = {42, 44, 46}


def _require_mido() -> Any:
    if mido is None:
        raise ImportError("mido is required for MIDI import. pip install mido")
    return mido


def midi_patterns_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "midi_patterns")


def ensure_default_patterns() -> None:
    """Write original CC0-style demo patterns if missing."""
    _require_mido()
    out_dir = midi_patterns_dir()
    os.makedirs(out_dir, exist_ok=True)
    chill = os.path.join(out_dir, "chill_minor.mid")
    if os.path.isfile(chill):
        return
    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.Message("program_change", program=0, time=0))
    # C minor pentatonic melody @ 80 BPM, 1 bar
    notes = [60, 63, 65, 67, 65, 63, 60, None, 63, 65, 68, 67, 65, 63, 60, None]
    step_ticks = 480 // 4  # 16th notes
    for note in notes:
        if note is not None:
            track.append(mido.Message("note_on", note=note, velocity=72, time=0))
            track.append(mido.Message("note_off", note=note, velocity=0, time=step_ticks - 10))
        else:
            track.append(mido.Message("note_off", note=60, velocity=0, time=step_ticks))
    mid.save(chill)

    drums = os.path.join(out_dir, "lofi_drums.mid")
    if not os.path.isfile(drums):
        dmid = mido.MidiFile(ticks_per_beat=480)
        dtrack = mido.MidiTrack()
        dmid.tracks.append(dtrack)
        kick_steps = {0, 8, 10}
        snare_steps = {4, 12}
        for step in range(16):
            t = 480 // 4
            if step in kick_steps:
                dtrack.append(mido.Message("note_on", channel=9, note=36, velocity=100, time=0))
                dtrack.append(mido.Message("note_off", channel=9, note=36, velocity=0, time=t - 5))
            elif step in snare_steps:
                dtrack.append(mido.Message("note_on", channel=9, note=38, velocity=90, time=0))
                dtrack.append(mido.Message("note_off", channel=9, note=38, velocity=0, time=t - 5))
            else:
                dtrack.append(mido.Message("note_off", channel=9, note=36, velocity=0, time=t))
        dmid.save(drums)


def _collect_note_events(mid_path: str) -> List[Tuple[float, int, int, bool]]:
    """Return (time_sec, note, velocity, is_drum) sorted by time."""
    mido = _require_mido()
    mid = mido.MidiFile(mid_path)
    events: List[Tuple[float, int, int, bool]] = []
    tempo = 500000
    for track in mid.tracks:
        t = 0.0
        active: Dict[int, int] = {}
        for msg in track:
            t += mido.tick2second(msg.time, mid.ticks_per_beat, tempo)
            if msg.type == "set_tempo":
                tempo = msg.tempo
            elif msg.type == "note_on":
                is_drum = getattr(msg, "channel", 0) == 9
                if msg.velocity > 0:
                    active[msg.note] = msg.velocity
                    events.append((t, msg.note, msg.velocity, is_drum))
                elif msg.note in active:
                    del active[msg.note]
            elif msg.type == "note_off":
                is_drum = getattr(msg, "channel", 0) == 9
                if msg.note in active:
                    del active[msg.note]
    events.sort(key=lambda x: x[0])
    return events


def _bar_duration_sec(bpm: float) -> float:
    return (60.0 / bpm) * 4.0


def parse_midi_pattern(
    mid_path: str,
    bpm: float = 80.0,
    bar_index: int = 0,
) -> Dict[str, Any]:
    """Quantize first bar (or bar_index) to 16 steps."""
    events = _collect_note_events(mid_path)
    bar_start = bar_index * _bar_duration_sec(bpm)
    bar_end = bar_start + _bar_duration_sec(bpm)
    step_dur = _bar_duration_sec(bpm) / 16.0

    melody_steps: List[Optional[int]] = [None] * 16
    drum_pattern = {"kick": [0] * 16, "snare": [0] * 16, "hihat": [0] * 16}
    chord_notes: List[int] = []

    for time_sec, note, velocity, is_drum in events:
        if time_sec < bar_start or time_sec >= bar_end:
            continue
        rel = time_sec - bar_start
        step = min(15, int(rel / step_dur))
        if is_drum:
            if note in GM_KICK:
                drum_pattern["kick"][step] = 1
            elif note in GM_SNARE:
                drum_pattern["snare"][step] = 1
            elif note in GM_HAT:
                drum_pattern["hihat"][step] = 1
        else:
            if velocity > 0:
                if melody_steps[step] is None or velocity > 60:
                    melody_steps[step] = note
                if step in (0, 4, 8, 12) and note not in chord_notes:
                    chord_notes.append(note)

    chord_midis = chord_notes[:4] if chord_notes else [48, 51, 55]

    return {
        "melody_steps": melody_steps,
        "drum_pattern": drum_pattern,
        "chord_midis": chord_midis,
        "source": mid_path,
    }


def load_midi_pattern(path: str, bpm: float = 80.0) -> Dict[str, Any]:
    ensure_default_patterns()
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return parse_midi_pattern(path, bpm=bpm)


def list_default_midi_patterns() -> List[str]:
    ensure_default_patterns()
    out = []
    d = midi_patterns_dir()
    if os.path.isdir(d):
        for name in sorted(os.listdir(d)):
            if name.lower().endswith(".mid"):
                out.append(os.path.join(d, name))
    return out
