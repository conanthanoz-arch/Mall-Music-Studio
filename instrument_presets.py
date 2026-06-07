"""Built-in and user instrument preset library for Mall Music Studio."""

import json
import os
import sys
from copy import deepcopy
from typing import Any, Dict, List, Optional

SLOTS = ("drums", "bass", "chords", "lead")

BUILTIN_PRESETS: Dict[str, Dict[str, Any]] = {
    # --- Drums (kits) ---
    "lo_fi_kit": {
        "id": "lo_fi_kit",
        "label": "Lo-Fi Kit",
        "slot": "drums",
        "engine": "drum_kit",
        "kick": {"type": "lofi", "volume": 0.48},
        "snare": {"type": "lofi", "volume": 1.0},
        "hihat_closed": {"type": "lofi_closed", "volume": 1.0},
        "hihat_open": {"type": "lofi_open", "volume": 1.0},
    },
    "808_classic": {
        "id": "808_classic",
        "label": "808 Classic",
        "slot": "drums",
        "engine": "drum_kit",
        "kick": {"type": "808", "volume": 0.55},
        "snare": {"type": "808_clap", "volume": 0.9},
        "hihat_closed": {"type": "808_hat", "volume": 0.85},
        "hihat_open": {"type": "808_hat_open", "volume": 0.7},
    },
    "breakbeat_tight": {
        "id": "breakbeat_tight",
        "label": "Breakbeat Tight",
        "slot": "drums",
        "engine": "drum_kit",
        "kick": {"type": "tight", "volume": 0.5},
        "snare": {"type": "crisp", "volume": 1.05},
        "hihat_closed": {"type": "lofi_closed", "volume": 1.1},
        "hihat_open": {"type": "lofi_open", "volume": 0.9},
    },
    # --- Bass ---
    "sub_sine": {
        "id": "sub_sine",
        "label": "Sub Sine",
        "slot": "bass",
        "engine": "va_voice",
        "volume": 1.0,
        "oscillators": [{"wave": "sine", "level": 1.0}],
        "envelope": {"attack_ms": 3, "decay_ms": 120, "sustain": 0.7, "release_ms": 40},
    },
    "moog_saw": {
        "id": "moog_saw",
        "label": "Moog Saw Bass",
        "slot": "bass",
        "engine": "va_voice",
        "volume": 1.0,
        "oscillators": [{"wave": "saw", "level": 0.85}],
        "filter": {"type": "lp", "cutoff_hz": 520, "resonance": 0.35},
        "envelope": {"attack_ms": 4, "decay_ms": 180, "sustain": 0.55, "release_ms": 60},
        "saturation": 0.25,
    },
    "fm_bass": {
        "id": "fm_bass",
        "label": "FM Bass",
        "slot": "bass",
        "engine": "va_voice",
        "volume": 1.0,
        "oscillators": [{"wave": "sine", "level": 1.0}],
        "fm": {"ratio": 2.0, "index": 2.8},
        "filter": {"type": "lp", "cutoff_hz": 800, "resonance": 0.15},
        "envelope": {"attack_ms": 2, "decay_ms": 150, "sustain": 0.5, "release_ms": 50},
    },
    "reese_bass": {
        "id": "reese_bass",
        "label": "Reese Bass",
        "slot": "bass",
        "engine": "va_voice",
        "volume": 1.0,
        "oscillators": [
            {"wave": "saw", "level": 0.5, "detune_cents": -12},
            {"wave": "saw", "level": 0.5, "detune_cents": 12},
        ],
        "filter": {"type": "lp", "cutoff_hz": 650, "resonance": 0.2},
        "envelope": {"attack_ms": 8, "decay_ms": 200, "sustain": 0.65, "release_ms": 80},
    },
    # --- Chords ---
    "warm_pad": {
        "id": "warm_pad",
        "label": "Warm Pad",
        "slot": "chords",
        "engine": "va_voice",
        "volume": 1.0,
        "oscillators": [
            {"wave": "sine", "level": 0.45, "detune_cents": -6},
            {"wave": "sine", "level": 0.45, "detune_cents": 6},
            {"wave": "triangle", "level": 0.25},
        ],
        "envelope": {"attack_ms": 35, "decay_ms": 400, "sustain": 0.75, "release_ms": 200},
        "fx_chain": [{"type": "chorus", "mix": 0.3}],
    },
    "rhodes_pad": {
        "id": "rhodes_pad",
        "label": "Rhodes",
        "slot": "chords",
        "engine": "va_voice",
        "volume": 1.0,
        "oscillators": [{"wave": "sine", "level": 0.7}],
        "fm": {"ratio": 3.5, "index": 1.2},
        "filter": {"type": "lp", "cutoff_hz": 4200, "resonance": 0.1},
        "envelope": {"attack_ms": 5, "decay_ms": 350, "sustain": 0.6, "release_ms": 180},
    },
    "choir_stack": {
        "id": "choir_stack",
        "label": "Choir Stack",
        "slot": "chords",
        "engine": "va_voice",
        "volume": 1.0,
        "oscillators": [
            {"wave": "saw", "level": 0.25, "detune_cents": -10},
            {"wave": "saw", "level": 0.25, "detune_cents": 10},
            {"wave": "triangle", "level": 0.35},
        ],
        "filter": {"type": "lp", "cutoff_hz": 3800, "resonance": 0.12},
        "envelope": {"attack_ms": 60, "decay_ms": 500, "sustain": 0.8, "release_ms": 250},
        "fx_chain": [{"type": "chorus", "mix": 0.45}],
    },
    "jazz_organ": {
        "id": "jazz_organ",
        "label": "Jazz Organ",
        "slot": "chords",
        "engine": "va_voice",
        "volume": 1.0,
        "oscillators": [
            {"wave": "square", "level": 0.35},
            {"wave": "square", "level": 0.35, "detune_cents": 3},
        ],
        "filter": {"type": "lp", "cutoff_hz": 2800, "resonance": 0.08},
        "envelope": {"attack_ms": 12, "decay_ms": 80, "sustain": 0.9, "release_ms": 120},
    },
    # --- Lead ---
    "sine_lead": {
        "id": "sine_lead",
        "label": "Sine Lead",
        "slot": "lead",
        "engine": "va_voice",
        "volume": 1.0,
        "oscillators": [{"wave": "sine", "level": 1.0}],
        "envelope": {"attack_ms": 3, "decay_ms": 100, "sustain": 0.4, "release_ms": 60},
    },
    "pluck_lead": {
        "id": "pluck_lead",
        "label": "Pluck Lead",
        "slot": "lead",
        "engine": "va_voice",
        "volume": 1.0,
        "oscillators": [{"wave": "triangle", "level": 0.9}],
        "filter": {"type": "lp", "cutoff_hz": 5000, "resonance": 0.25},
        "envelope": {"attack_ms": 1, "decay_ms": 220, "sustain": 0.05, "release_ms": 90},
    },
    "bell_fm": {
        "id": "bell_fm",
        "label": "Bell FM",
        "slot": "lead",
        "engine": "va_voice",
        "volume": 1.0,
        "oscillators": [{"wave": "sine", "level": 1.0}],
        "fm": {"ratio": 4.0, "index": 3.5},
        "envelope": {"attack_ms": 1, "decay_ms": 600, "sustain": 0.02, "release_ms": 400},
    },
    "pan_flute": {
        "id": "pan_flute",
        "label": "Pan Flute",
        "slot": "lead",
        "engine": "va_voice",
        "volume": 1.0,
        "oscillators": [
            {"wave": "sine", "level": 0.65},
            {"wave": "triangle", "level": 0.35, "detune_cents": 4},
        ],
        "breath_noise": 0.14,
        "filter": {"type": "bandpass", "hp_hz": 550, "lp_hz": 4500},
        "envelope": {"attack_ms": 48, "decay_ms": 180, "sustain": 0.42, "release_ms": 100},
        "vibrato": {"rate_hz": 5.2, "depth_cents": 9},
        "fx_chain": [{"type": "chorus", "mix": 0.22}],
    },
    "electric_guitar_clean": {
        "id": "electric_guitar_clean",
        "label": "Electric Guitar (Clean)",
        "slot": "layer",
        "engine": "va_voice",
        "volume": 1.0,
        "oscillators": [{"wave": "saw", "level": 0.55}, {"wave": "sine", "level": 0.25}],
        "filter": {"type": "lp", "cutoff_hz": 4200, "resonance": 0.12},
        "envelope": {"attack_ms": 4, "decay_ms": 280, "sustain": 0.35, "release_ms": 120},
    },
    "electric_guitar_drive": {
        "id": "electric_guitar_drive",
        "label": "Electric Guitar (Drive)",
        "slot": "layer",
        "engine": "va_voice",
        "volume": 1.0,
        "oscillators": [{"wave": "saw", "level": 0.7}],
        "filter": {"type": "lp", "cutoff_hz": 3200, "resonance": 0.2},
        "saturation": 0.45,
        "envelope": {"attack_ms": 3, "decay_ms": 240, "sustain": 0.4, "release_ms": 100},
    },
    "electric_guitar_chorus_drive": {
        "id": "electric_guitar_chorus_drive",
        "label": "Electric Guitar (Chorus Drive)",
        "slot": "layer",
        "engine": "va_voice",
        "volume": 1.0,
        "oscillators": [{"wave": "saw", "level": 0.65}, {"wave": "saw", "level": 0.35, "detune_cents": 8}],
        "filter": {"type": "lp", "cutoff_hz": 3600, "resonance": 0.18},
        "saturation": 0.35,
        "envelope": {"attack_ms": 5, "decay_ms": 300, "sustain": 0.45, "release_ms": 140},
        "fx_chain": [{"type": "chorus", "mix": 0.42}],
    },
    "bass_guitar": {
        "id": "bass_guitar",
        "label": "Bass Guitar",
        "slot": "bass",
        "engine": "va_voice",
        "volume": 1.0,
        "oscillators": [{"wave": "saw", "level": 0.5}, {"wave": "square", "level": 0.2, "detune_cents": -5}],
        "filter": {"type": "lp", "cutoff_hz": 680, "resonance": 0.15},
        "envelope": {"attack_ms": 6, "decay_ms": 200, "sustain": 0.6, "release_ms": 70},
    },
}

DEFAULT_SLOT_PRESETS = {
    "drums": "lo_fi_kit",
    "bass": "sub_sine",
    "chords": "warm_pad",
    "lead": "sine_lead",
}

_LIBRARY_ROOT: Optional[str] = None


def set_library_root(path: str) -> None:
    global _LIBRARY_ROOT
    _LIBRARY_ROOT = path


def presets_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "instrument_presets")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "instrument_presets")


def user_presets_dir() -> str:
    path = os.path.join(presets_base_dir(), "user")
    os.makedirs(path, exist_ok=True)
    return path


def _load_user_presets() -> Dict[str, Dict[str, Any]]:
    loaded: Dict[str, Dict[str, Any]] = {}
    user_dir = user_presets_dir()
    if not os.path.isdir(user_dir):
        return loaded
    for name in os.listdir(user_dir):
        if not name.endswith(".json"):
            continue
        path = os.path.join(user_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                preset = json.load(f)
            preset_id = preset.get("id") or os.path.splitext(name)[0]
            preset["id"] = preset_id
            loaded[preset_id] = preset
        except (OSError, json.JSONDecodeError):
            continue
    return loaded


def all_presets() -> Dict[str, Dict[str, Any]]:
    merged = deepcopy(BUILTIN_PRESETS)
    merged.update(_load_user_presets())
    return merged


def get_preset(preset_id: str) -> Dict[str, Any]:
    presets = all_presets()
    if preset_id not in presets:
        slot = next((s for s in SLOTS if preset_id == DEFAULT_SLOT_PRESETS.get(s)), None)
        fallback = DEFAULT_SLOT_PRESETS.get(slot or "bass", "sub_sine")
        preset_id = fallback if fallback in presets else next(iter(presets))
    return deepcopy(presets[preset_id])


def list_presets_for_slot(slot: str) -> List[Dict[str, Any]]:
    presets = all_presets()
    items = [p for p in presets.values() if p.get("slot") in (slot, "layer")]
    items.sort(key=lambda p: (p.get("label") or p.get("id", "")).lower())
    return items


def list_presets_for_mode(mode: str) -> List[Dict[str, Any]]:
    presets = all_presets().values()
    if mode == "drums":
        items = [p for p in presets if p.get("engine") == "drum_kit"]
    else:
        items = [p for p in presets if p.get("engine") == "va_voice"]
    items.sort(key=lambda p: (p.get("label") or p.get("id", "")).lower())
    return items


def delete_user_preset(preset_id: str) -> bool:
    path = os.path.join(user_presets_dir(), f"{preset_id}.json")
    if not os.path.isfile(path):
        return False
    try:
        os.remove(path)
    except OSError:
        return False
    return True


def preset_id_from_label_for_mode(mode: str, label: str) -> str:
    for p in list_presets_for_mode(mode):
        if p.get("label") == label:
            return p["id"]
    items = list_presets_for_mode(mode)
    return items[0]["id"] if items else "sine_lead"


def preset_labels_for_slot(slot: str) -> List[str]:
    return [p["label"] for p in list_presets_for_slot(slot)]


def preset_id_from_label(slot: str, label: str) -> str:
    for p in list_presets_for_slot(slot):
        if p.get("label") == label:
            return p["id"]
    return DEFAULT_SLOT_PRESETS[slot]


def label_from_preset_id(preset_id: str) -> str:
    p = get_preset(preset_id)
    return p.get("label", preset_id)


def save_user_preset(preset: Dict[str, Any]) -> str:
    preset = deepcopy(preset)
    preset_id = preset.get("id")
    if not preset_id:
        raise ValueError("Preset must have an id")
    slot = preset.get("slot")
    if slot not in SLOTS and slot != "layer":
        raise ValueError(f"Invalid slot: {slot}")
    path = os.path.join(user_presets_dir(), f"{preset_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(preset, f, indent=2)
    return path


def default_instrument_config() -> Dict[str, Any]:
    return {
        "drums": {"preset": DEFAULT_SLOT_PRESETS["drums"], "seed": 101},
        "bass": {"preset": DEFAULT_SLOT_PRESETS["bass"], "seed": 202},
        "chords": {"preset": DEFAULT_SLOT_PRESETS["chords"], "seed": 303},
        "lead": {"preset": DEFAULT_SLOT_PRESETS["lead"], "seed": 404},
    }
