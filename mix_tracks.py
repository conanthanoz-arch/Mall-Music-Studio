"""Mix track list model — additive instrument tracks with volume/mute."""

import uuid
from copy import deepcopy
from typing import Any, Dict, List, Optional

from instrument_presets import DEFAULT_SLOT_PRESETS, SLOTS

MAX_MIX_TRACKS = 16

TRACK_MODES = {
    "drums": "Drums (pattern)",
    "bass_root": "Bass (root)",
    "chords": "Chords",
    "melody": "Melody (primary)",
    "follow_melody": "Follow melody",
    "counter_melody": "Counter melody",
    "follow_chords": "Follow chords",
}


def _new_id() -> str:
    return f"t_{uuid.uuid4().hex[:8]}"


def make_track(
    name: str,
    preset: str,
    mode: str,
    seed: int = 0,
    volume: float = 1.0,
    mute: bool = False,
    octave_shift: int = 0,
    track_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "id": track_id or _new_id(),
        "name": name,
        "preset": preset,
        "mode": mode,
        "seed": int(seed),
        "volume": float(max(0.0, min(1.0, volume))),
        "mute": bool(mute),
        "octave_shift": int(octave_shift),
    }


def default_mix_tracks() -> List[Dict[str, Any]]:
    return [
        make_track("Drums", DEFAULT_SLOT_PRESETS["drums"], "drums", seed=101, volume=1.0, track_id="t_drums"),
        make_track("Bass", DEFAULT_SLOT_PRESETS["bass"], "bass_root", seed=202, volume=1.0, track_id="t_bass"),
        make_track("Chords", DEFAULT_SLOT_PRESETS["chords"], "chords", seed=303, volume=1.0, track_id="t_chords"),
        make_track("Lead", DEFAULT_SLOT_PRESETS["lead"], "melody", seed=404, volume=1.0, track_id="t_lead"),
    ]


def migrate_to_mix_tracks(data: Any) -> List[Dict[str, Any]]:
    """Convert saved track JSON or legacy instruments dict to mix track list."""
    if isinstance(data, list):
        return normalize_mix_tracks(data)
    if not isinstance(data, dict):
        return default_mix_tracks()
    if "tracks" in data:
        return normalize_mix_tracks(data["tracks"])
    # Legacy v0.6 flat instruments {drums: {preset, seed}, ...}
    if any(k in data for k in SLOTS):
        tracks = []
        names = {"drums": "Drums", "bass": "Bass", "chords": "Chords", "lead": "Lead"}
        modes = {"drums": "drums", "bass": "bass_root", "chords": "chords", "lead": "melody"}
        for slot in SLOTS:
            if slot not in data:
                continue
            entry = data[slot]
            tracks.append(
                make_track(
                    names[slot],
                    entry.get("preset", DEFAULT_SLOT_PRESETS[slot]),
                    modes[slot],
                    seed=entry.get("seed", 0),
                    volume=entry.get("volume", 1.0),
                    mute=entry.get("mute", False),
                    track_id=f"t_{slot}",
                )
            )
        return normalize_mix_tracks(tracks) if tracks else default_mix_tracks()
    return default_mix_tracks()


def normalize_mix_tracks(tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for i, raw in enumerate(tracks[:MAX_MIX_TRACKS]):
        mode = raw.get("mode", "follow_melody")
        if mode not in TRACK_MODES:
            mode = "follow_melody"
        out.append(
            make_track(
                name=str(raw.get("name") or f"Track {i + 1}"),
                preset=str(raw.get("preset") or DEFAULT_SLOT_PRESETS.get("lead", "sine_lead")),
                mode=mode,
                seed=int(raw.get("seed", 0)),
                volume=float(raw.get("volume", 1.0)),
                mute=bool(raw.get("mute", False)),
                octave_shift=int(raw.get("octave_shift", 0)),
                track_id=str(raw.get("id") or _new_id()),
            )
        )
    return out if out else default_mix_tracks()


def stem_bucket_for_mode(mode: str) -> str:
    if mode == "drums":
        return "drums"
    if mode == "bass_root":
        return "bass"
    if mode in ("chords", "follow_chords"):
        return "chords"
    return "melody"


def suggest_track_name(preset_label: str, existing_names: List[str]) -> str:
    base = preset_label
    if base not in existing_names:
        return base
    n = 1
    while f"{base} {n:02d}" in existing_names:
        n += 1
    return f"{base} {n:02d}"


def tracks_to_save(tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return deepcopy(normalize_mix_tracks(tracks))
