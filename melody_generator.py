"""Markov melody generator for 16-step lo-fi lead lines."""

import random
from typing import List, Optional

from music_theory import THEME_PROFILES, scale_note_midi


def _build_transition_matrix(scale_len: int, density: float) -> List[List[float]]:
    """Higher density = more likely to stay on / move to active notes."""
    rest_prob = max(0.05, 1.0 - density)
    active_prob = density / max(scale_len, 1)
    matrix = []
    for _ in range(scale_len + 1):  # +1 for rest state
        row = [rest_prob]
        row.extend([active_prob] * scale_len)
        total = sum(row)
        matrix.append([p / total for p in row])
    return matrix


def generate_melody_steps(
    theme_id: str,
    density_pct: int = 70,
    seed: Optional[int] = None,
) -> List[Optional[int]]:
    """
    Return 16 MIDI note numbers (or None for rest) for one measure.
    density_pct: 10-100, probability of non-rest steps.
    """
    if seed is not None:
        random.seed(seed)

    profile = THEME_PROFILES[theme_id]
    scale = profile["scale"]
    root = profile["root_midi"] + 12  # lead octave
    density = density_pct / 100.0
    matrix = _build_transition_matrix(len(scale), density)

    steps: List[Optional[int]] = []
    state = 0  # 0 = rest, 1..n = scale degree index

    for _ in range(16):
        row = matrix[state]
        r = random.random()
        cumulative = 0.0
        next_state = 0
        for i, p in enumerate(row):
            cumulative += p
            if r <= cumulative:
                next_state = i
                break

        if next_state == 0:
            steps.append(None)
        else:
            degree = next_state - 1
            steps.append(scale_note_midi(root, scale, degree))
        state = next_state

    return steps
