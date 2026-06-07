"""Music theory constants and MIDI/frequency helpers for MallMusicStudio."""

import math
from typing import List, Tuple

SAMPLE_RATE = 44100

CHORD_MAJOR_7TH = [0, 4, 7, 11]
CHORD_MINOR_7TH = [0, 3, 7, 10]
CHORD_DOM_7TH = [0, 4, 7, 10]

THEME_PROFILES = {
    "pixel_art": {
        "label": "Pixel Art (Chillhop)",
        "scale": [0, 2, 3, 5, 7, 9, 10],  # C natural minor pentatonic-ish
        "root_midi": 48,
        "progression": [
            {"root_midi": 48, "intervals": CHORD_MINOR_7TH},
            {"root_midi": 51, "intervals": CHORD_MINOR_7TH},
            {"root_midi": 53, "intervals": CHORD_MAJOR_7TH},
            {"root_midi": 55, "intervals": CHORD_MINOR_7TH},
        ],
    },
    "anime_vector": {
        "label": "Anime Vector (Major 7th)",
        "scale": [0, 2, 4, 5, 7, 9, 11],
        "root_midi": 65,
        "progression": [
            {"root_midi": 65, "intervals": CHORD_MAJOR_7TH},
            {"root_midi": 67, "intervals": CHORD_MAJOR_7TH},
            {"root_midi": 64, "intervals": CHORD_MINOR_7TH},
            {"root_midi": 69, "intervals": CHORD_MINOR_7TH},
        ],
    },
    "matte_painting": {
        "label": "Matte Painting (Ambient)",
        "scale": [0, 2, 4, 7, 9],
        "root_midi": 57,
        "progression": [
            {"root_midi": 57, "intervals": CHORD_MINOR_7TH},
            {"root_midi": 62, "intervals": CHORD_MAJOR_7TH},
            {"root_midi": 64, "intervals": CHORD_MINOR_7TH},
            {"root_midi": 59, "intervals": CHORD_MINOR_7TH},
        ],
    },
    "cyberpunk": {
        "label": "Cyberpunk (Neon Noir)",
        "scale": [0, 2, 3, 5, 7, 8, 10],
        "root_midi": 57,
        "progression": [
            {"root_midi": 57, "intervals": CHORD_MINOR_7TH},
            {"root_midi": 53, "intervals": CHORD_MAJOR_7TH},
            {"root_midi": 55, "intervals": CHORD_DOM_7TH},
            {"root_midi": 57, "intervals": CHORD_MINOR_7TH},
        ],
    },
}


def midi_to_hz(midi_note: float) -> float:
    return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))


def chord_tones(root_midi: int, intervals: List[int]) -> List[int]:
    return [root_midi + i for i in intervals]


def scale_note_midi(root_midi: int, scale: List[int], degree: int) -> int:
    octave_offset = (degree // len(scale)) * 12
    return root_midi + scale[degree % len(scale)] + octave_offset


def humanize_velocity(base: int = 90, sigma: float = 2.5) -> int:
    import random

    v = int(base + random.gauss(0, sigma))
    return max(1, min(127, v))
