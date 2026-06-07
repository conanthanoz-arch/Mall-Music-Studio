"""Arrangement clip model, undo stack, and playlist persistence."""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from playlist_arranger import (
    load_library_metas,
    load_playlist,
    resolve_playlist_entries,
    save_playlist,
)

CLIP_COLORS = [
    "#89b4fa",
    "#a6e3a1",
    "#fab387",
    "#f38ba8",
    "#cba6f7",
    "#94e2d5",
    "#f9e2af",
]

LANES = ("master", "drums", "bass", "chords", "melody")


@dataclass
class ClipItem:
    wav_file: str
    title: str = "Untitled"
    artist: str = "Mall Music Studio"
    theme: str = ""
    duration_sec: float = 0.0
    seed: Optional[int] = None
    trim_in_sec: float = 0.0
    trim_out_sec: Optional[float] = None
    lane: str = "master"
    color: str = "#89b4fa"
    bpm: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], index: int = 0) -> "ClipItem":
        dur = float(data.get("duration_sec") or 0)
        trim_out = data.get("trim_out_sec")
        return cls(
            wav_file=data.get("wav_file", ""),
            title=data.get("title") or "Untitled",
            artist=data.get("artist") or "Mall Music Studio",
            theme=data.get("theme") or "",
            duration_sec=dur,
            seed=data.get("seed"),
            trim_in_sec=float(data.get("trim_in_sec") or 0),
            trim_out_sec=float(trim_out) if trim_out is not None else None,
            lane=data.get("lane") or "master",
            color=data.get("color") or CLIP_COLORS[index % len(CLIP_COLORS)],
            bpm=data.get("bpm"),
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "wav_file": self.wav_file,
            "title": self.title,
            "artist": self.artist,
            "theme": self.theme,
            "duration_sec": float(self.duration_sec or 0),
            "trim_in_sec": self.trim_in_sec,
            "lane": self.lane,
            "color": self.color,
        }
        if self.seed is not None:
            out["seed"] = self.seed
        if self.trim_out_sec is not None:
            out["trim_out_sec"] = self.trim_out_sec
        if self.bpm is not None:
            out["bpm"] = self.bpm
        return out

    def effective_duration_sec(self) -> float:
        base = float(self.duration_sec or 0)
        start = max(0.0, self.trim_in_sec)
        end = self.trim_out_sec if self.trim_out_sec is not None else base
        end = min(end, base)
        return max(0.0, end - start)

    @classmethod
    def from_library_meta(cls, meta: Dict[str, Any], index: int = 0) -> "ClipItem":
        return cls.from_dict(meta, index)


@dataclass
class SessionSlot:
    row: int
    col: int
    clip: Optional[ClipItem] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row": self.row,
            "col": self.col,
            "clip": self.clip.to_dict() if self.clip else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionSlot":
        clip_data = data.get("clip")
        clip = ClipItem.from_dict(clip_data) if clip_data else None
        return cls(row=int(data.get("row", 0)), col=int(data.get("col", 0)), clip=clip)


def session_layout_path(library_dir: str) -> str:
    return os.path.join(library_dir, "session_layout.json")


class ArrangementModel:
    """Ordered master-lane clips + session grid + undo."""

    def __init__(self, library_dir: str):
        self.library_dir = library_dir
        self.clips: List[ClipItem] = []
        self.session_rows = 4
        self.session_cols = 8
        self.session: List[List[Optional[ClipItem]]] = [
            [None] * self.session_cols for _ in range(self.session_rows)
        ]
        self._undo: List[List[Dict[str, Any]]] = []
        self._redo: List[List[Dict[str, Any]]] = []
        self.load()

    def _snapshot(self) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self.clips]

    def _push_undo(self) -> None:
        self._undo.append(self._snapshot())
        if len(self._undo) > 50:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self._snapshot())
        state = self._undo.pop()
        self.clips = [ClipItem.from_dict(d, i) for i, d in enumerate(state)]
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self._snapshot())
        state = self._redo.pop()
        self.clips = [ClipItem.from_dict(d, i) for i, d in enumerate(state)]
        return True

    def load(self) -> None:
        raw = load_playlist(self.library_dir)
        resolved = resolve_playlist_entries(self.library_dir, raw)
        self.clips = [ClipItem.from_dict(d, i) for i, d in enumerate(resolved)]
        self._load_session()

    def _load_session(self) -> None:
        path = session_layout_path(self.library_dir)
        if not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        self.session_rows = int(data.get("rows") or self.session_rows)
        self.session_cols = int(data.get("cols") or self.session_cols)
        self.session = [[None] * self.session_cols for _ in range(self.session_rows)]
        for slot in data.get("slots") or []:
            s = SessionSlot.from_dict(slot)
            if 0 <= s.row < self.session_rows and 0 <= s.col < self.session_cols:
                self.session[s.row][s.col] = s.clip

    def save_session(self) -> None:
        slots = []
        for r in range(self.session_rows):
            for c in range(self.session_cols):
                clip = self.session[r][c]
                if clip:
                    slots.append(SessionSlot(r, c, clip).to_dict())
        payload = {"rows": self.session_rows, "cols": self.session_cols, "slots": slots}
        path = session_layout_path(self.library_dir)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def save_playlist(self) -> str:
        tracks = [c.to_dict() for c in self.master_clips()]
        return save_playlist(self.library_dir, tracks)

    def master_clips(self) -> List[ClipItem]:
        return [c for c in self.clips if c.lane == "master"]

    def library_metas(self) -> List[Dict[str, Any]]:
        return load_library_metas(self.library_dir)

    def total_duration_sec(self) -> float:
        return sum(c.effective_duration_sec() for c in self.master_clips())

    def clip_start_times(self) -> List[Tuple[int, float]]:
        """Return (index, start_sec) for master clips."""
        times: List[Tuple[int, float]] = []
        t = 0.0
        for i, clip in enumerate(self.clips):
            if clip.lane != "master":
                continue
            times.append((i, t))
            t += clip.effective_duration_sec()
        return times

    def add_clip(self, clip: ClipItem, index: Optional[int] = None) -> None:
        self._push_undo()
        if index is None:
            self.clips.append(clip)
        else:
            self.clips.insert(max(0, min(index, len(self.clips))), clip)

    def remove_clip(self, index: int) -> None:
        if index < 0 or index >= len(self.clips):
            return
        self._push_undo()
        del self.clips[index]

    def duplicate_clip(self, index: int) -> None:
        if index < 0 or index >= len(self.clips):
            return
        self._push_undo()
        dup = copy.deepcopy(self.clips[index])
        self.clips.insert(index + 1, dup)

    def move_clip(self, from_index: int, to_index: int) -> None:
        if from_index == to_index:
            return
        if from_index < 0 or from_index >= len(self.clips):
            return
        self._push_undo()
        clip = self.clips.pop(from_index)
        to_index = max(0, min(to_index, len(self.clips)))
        self.clips.insert(to_index, clip)

    def reorder_by_time(self, clip_index: int, new_start_sec: float) -> None:
        """Reorder clip to approximate timeline position."""
        master_indices = [i for i, c in enumerate(self.clips) if c.lane == "master"]
        if clip_index not in master_indices:
            return
        starts = self.clip_start_times()
        pos = master_indices.index(clip_index)
        target = 0
        for i, (idx, start) in enumerate(starts):
            if new_start_sec >= start - 0.5:
                target = i
        if pos != target:
            mi = master_indices[pos]
            self._push_undo()
            clip = self.clips.pop(mi)
            insert_at = master_indices[target] if target < len(master_indices) else len(self.clips)
            if target > pos:
                insert_at = min(insert_at + 1, len(self.clips))
            self.clips.insert(insert_at, clip)

    def split_at_playhead(self, playhead_sec: float) -> bool:
        """Split master clip under playhead."""
        for idx, start in self.clip_start_times():
            clip = self.clips[idx]
            dur = clip.effective_duration_sec()
            if start <= playhead_sec < start + dur:
                offset = playhead_sec - start
                if offset < 0.5 or offset > dur - 0.5:
                    return False
                self._push_undo()
                left = copy.deepcopy(clip)
                right = copy.deepcopy(clip)
                left.trim_out_sec = (left.trim_in_sec or 0) + offset
                right.trim_in_sec = (right.trim_in_sec or 0) + offset
                self.clips[idx] = left
                self.clips.insert(idx + 1, right)
                return True
        return False

    def set_session_slot(self, row: int, col: int, clip: Optional[ClipItem]) -> None:
        if 0 <= row < self.session_rows and 0 <= col < self.session_cols:
            self.session[row][col] = clip
            self.save_session()

    def export_track_dicts(self) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self.master_clips()]
