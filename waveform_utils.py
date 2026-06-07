"""Waveform downsampling and Tkinter canvas drawing helpers."""

import os
import wave
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import numpy as np

from music_theory import SAMPLE_RATE

if TYPE_CHECKING:
    import tkinter as tk

STEM_LANES = [
    ("Drums", "drums", "#f38ba8"),
    ("Bass", "bass", "#fab387"),
    ("Chords", "chords", "#a6e3a1"),
    ("Melody", "melody", "#89b4fa"),
    ("Reverb", "reverb", "#cba6f7"),
]


def load_wav_mono(path: str) -> np.ndarray:
    """Load WAV as float64 mono in [-1, 1]."""
    with wave.open(path, "rb") as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if sample_width == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32767.0
    elif sample_width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128) / 128.0
    else:
        raise ValueError(f"Unsupported sample width: {sample_width}")

    if n_channels > 1:
        data = data.reshape(-1, n_channels).mean(axis=1)
    return data


def envelope_peaks(samples: np.ndarray, num_points: int) -> Tuple[np.ndarray, np.ndarray]:
    """Min/max envelope buckets for waveform display."""
    if len(samples) == 0 or num_points <= 0:
        return np.array([]), np.array([])
    num_points = min(num_points, max(1, len(samples) // 2))
    chunk = max(1, len(samples) // num_points)
    mins, maxs = [], []
    for i in range(num_points):
        start = i * chunk
        end = min(len(samples), start + chunk)
        if start >= end:
            break
        segment = samples[start:end]
        mins.append(float(np.min(segment)))
        maxs.append(float(np.max(segment)))
    return np.array(mins), np.array(maxs)


def buffer_to_peaks(buffer: np.ndarray, width: int) -> Tuple[np.ndarray, np.ndarray]:
    return envelope_peaks(np.asarray(buffer, dtype=np.float64), width)


def _canvas_size(canvas: "tk.Canvas", default_w: int = 640, default_h: int = 90) -> Tuple[int, int]:
    w = max(10, canvas.winfo_width() or default_w)
    h = max(10, canvas.winfo_height() or default_h)
    return w, h


def _draw_envelope_lines(
    canvas: "tk.Canvas",
    buffer: np.ndarray,
    x0: int,
    y0: int,
    width: int,
    height: int,
    color: str,
) -> None:
    if len(buffer) == 0 or width <= 0 or height <= 0:
        return
    mins, maxs = buffer_to_peaks(buffer, width)
    mid = y0 + height / 2
    amp = (height / 2) - 2
    for i, (lo, hi) in enumerate(zip(mins, maxs)):
        x = x0 + i
        y1 = mid - hi * amp
        y2 = mid - lo * amp
        canvas.create_line(x, y1, x, y2, fill=color)


class WaveformCanvas:
    """Draws a min/max waveform on a Tkinter Canvas."""

    def __init__(self, canvas: "tk.Canvas"):
        self.canvas = canvas
        self._playhead_id = None
        self._duration_sec = 0.0

    def draw_buffer(self, buffer: np.ndarray, label: str = "") -> None:
        self._duration_sec = len(buffer) / SAMPLE_RATE if len(buffer) else 0.0
        self.canvas.delete("all")
        w, h = _canvas_size(self.canvas)
        self.canvas.create_rectangle(0, 0, w, h, fill="#181825", outline="#313244")
        if label:
            self.canvas.create_text(
                8, 10, text=label, anchor="nw", fill="#6c7086", font=("Segoe UI", 8)
            )

        if len(buffer) == 0:
            return

        _draw_envelope_lines(self.canvas, buffer, 2, 0, w - 4, h, "#89b4fa")
        self._playhead_id = self.canvas.create_line(2, 0, 2, h, fill="#f38ba8", width=2)

    def draw_file(self, path: str, label: str = "") -> None:
        try:
            samples = load_wav_mono(path)
        except (OSError, wave.Error, ValueError):
            self.canvas.delete("all")
            self.canvas.create_text(
                10, 40, text="Could not load waveform", fill="#f38ba8", anchor="w"
            )
            return
        self.draw_buffer(samples, label=label or os.path.basename(path))

    def set_playhead_ratio(self, ratio: float) -> None:
        if self._playhead_id is None:
            return
        w, h = _canvas_size(self.canvas)
        x = 2 + int(max(0.0, min(1.0, ratio)) * (w - 4))
        self.canvas.coords(self._playhead_id, x, 0, x, h)

    def draw_region_ratio(self, start_ratio: float, end_ratio: float, color: str = "#a6e3a144") -> None:
        """Highlight the sample region on the stem timeline."""
        self.canvas.delete("sample_region")
        w, h = _canvas_size(self.canvas)
        x0 = 2 + int(max(0.0, min(1.0, start_ratio)) * (w - 4))
        x1 = 2 + int(max(0.0, min(1.0, end_ratio)) * (w - 4))
        if x1 <= x0:
            x1 = x0 + 2
        self.canvas.create_rectangle(x0, 2, x1, h - 2, fill=color, outline="#a6e3a1", width=1, tags="sample_region")

    def clear(self) -> None:
        self.canvas.delete("all")
        self._playhead_id = None
        self._duration_sec = 0.0

    @property
    def duration_sec(self) -> float:
        return self._duration_sec


class StemLanesCanvas:
    """Stacked mini-waveforms for drums / bass / chords / melody / reverb."""

    def __init__(self, canvas: "tk.Canvas"):
        self.canvas = canvas

    def draw_stems(self, stems: Dict[str, np.ndarray], label: str = "") -> None:
        self.canvas.delete("all")
        w, h = _canvas_size(self.canvas, default_h=130)
        self.canvas.create_rectangle(0, 0, w, h, fill="#181825", outline="#313244")
        if label:
            self.canvas.create_text(
                8, 6, text=label, anchor="nw", fill="#6c7086", font=("Segoe UI", 8)
            )

        lane_count = len(STEM_LANES)
        top_pad = 18 if label else 4
        lane_h = max(8, (h - top_pad - 4) // lane_count)
        plot_w = w - 54

        for i, (lane_label, key, color) in enumerate(STEM_LANES):
            y0 = top_pad + i * lane_h
            self.canvas.create_text(
                4, y0 + lane_h // 2, text=lane_label, anchor="w", fill=color, font=("Segoe UI", 7)
            )
            self.canvas.create_rectangle(50, y0, w - 2, y0 + lane_h - 1, fill="#11111b", outline="#313244")
            buf = stems.get(key)
            if buf is not None and len(buf):
                _draw_envelope_lines(self.canvas, buf, 51, y0, plot_w, lane_h - 1, color)


class GrooveGridCanvas:
    """16-step groove grid with swing timing and drum hits."""

    def __init__(self, canvas: "tk.Canvas"):
        self.canvas = canvas

    def draw(
        self,
        bpm: float,
        swing: float,
        drums: Dict[str, List[int]],
        step_times: Optional[List[float]] = None,
        measure_dur: Optional[float] = None,
    ) -> None:
        self.canvas.delete("all")
        w, h = _canvas_size(self.canvas, default_h=58)
        self.canvas.create_rectangle(0, 0, w, h, fill="#181825", outline="#313244")

        step_dur = (60.0 / bpm) / 4.0
        if measure_dur is None:
            measure_dur = step_dur * 16
        if step_times is None:
            from audio_synthesizer import step_times_visual

            step_times = step_times_visual(bpm, swing)

        left = 36
        plot_w = w - left - 8
        grid_top = 14
        row_h = 12
        rows = [("K", "kick", "#f38ba8"), ("S", "snare", "#fab387"), ("H", "hihat", "#89b4fa")]

        self.canvas.create_text(
            4, 8, text=f"{int(bpm)} BPM  swing {swing:.2f}", anchor="nw", fill="#6c7086", font=("Segoe UI", 7)
        )

        for ri, (row_label, drum_key, color) in enumerate(rows):
            y = grid_top + ri * row_h
            self.canvas.create_text(
                4, y + row_h // 2, text=row_label, anchor="w", fill=color, font=("Consolas", 8, "bold")
            )
            self.canvas.create_line(left, y + row_h, w - 4, y + row_h, fill="#313244")

            for step in range(16):
                t = step_times[step]
                x = left + int((t / measure_dur) * plot_w)
                if drums.get(drum_key, [0] * 16)[step]:
                    self.canvas.create_oval(x - 3, y + 1, x + 3, y + row_h - 3, fill=color, outline="")
                elif step % 4 == 0:
                    self.canvas.create_line(x, y + 2, x, y + row_h - 2, fill="#45475a")

        for step in range(16):
            if step % 2 == 1 and swing > 0.01:
                t = step_times[step]
                x = left + int((t / measure_dur) * plot_w)
                self.canvas.create_line(x, grid_top - 2, x, grid_top + 3 * row_h, fill="#585b70", dash=(2, 3))
