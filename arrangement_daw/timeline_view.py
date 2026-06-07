"""Horizontal arrangement timeline with draggable clip blocks."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QMenu,
)

from arrangement_daw.arrangement_model import ArrangementModel, ClipItem
from music_theory import SAMPLE_RATE
from waveform_utils import buffer_to_peaks, load_wav_mono

RULER_H = 28
LANE_H = 72
MIN_PX_PER_SEC = 4.0
MAX_PX_PER_SEC = 120.0


class ClipBlockItem(QGraphicsRectItem):
    def __init__(
        self,
        clip_index: int,
        clip: ClipItem,
        x: float,
        width: float,
        timeline: "TimelineView",
    ):
        super().__init__(0, RULER_H + 4, max(8.0, width), LANE_H - 8)
        self.clip_index = clip_index
        self.clip = clip
        self.timeline = timeline
        self.setPos(x, 0)
        self.setBrush(QBrush(QColor(clip.color)))
        self.setPen(QPen(QColor("#45475a"), 1))
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self._drag_start_x = x
        self._waveform: Optional[np.ndarray] = None

        self.label = QGraphicsTextItem(clip.title[:24], self)
        self.label.setDefaultTextColor(QColor("#1e1e2e"))
        self.label.setPos(4, 2)

        self._load_waveform()
        self._trim_left = QGraphicsRectItem(0, 0, 6, LANE_H - 8, self)
        self._trim_left.setBrush(QBrush(QColor(255, 255, 255, 60)))
        self._trim_right = QGraphicsRectItem(max(8, width) - 6, 0, 6, LANE_H - 8, self)
        self._trim_right.setBrush(QBrush(QColor(255, 255, 255, 60)))

    def _load_waveform(self) -> None:
        try:
            data = load_wav_mono(self.clip.wav_file)
            trim_in = int(self.clip.trim_in_sec * SAMPLE_RATE)
            trim_out = (
                int(self.clip.trim_out_sec * SAMPLE_RATE)
                if self.clip.trim_out_sec is not None
                else len(data)
            )
            self._waveform = data[trim_in:trim_out]
        except OSError:
            self._waveform = None

    def paint(self, painter: QPainter, option, widget=None) -> None:
        super().paint(painter, option, widget)
        if self._waveform is None or len(self._waveform) == 0:
            return
        w = int(self.rect().width()) - 8
        h = int(self.rect().height()) - 20
        if w <= 0 or h <= 0:
            return
        mins, maxs = buffer_to_peaks(self._waveform, w)
        mid = 14 + h / 2
        amp = h / 2 - 2
        painter.setPen(QPen(QColor(30, 30, 46, 180), 1))
        for i, (lo, hi) in enumerate(zip(mins, maxs)):
            x = 4 + i
            y1 = mid - hi * amp
            y2 = mid - lo * amp
            painter.drawLine(int(x), int(y1), int(x), int(y2))

    def mousePressEvent(self, event):
        self._drag_start_x = self.pos().x()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        new_x = self.pos().x()
        new_start = max(0.0, new_x / self.timeline.px_per_sec)
        self.timeline.clip_moved.emit(self.clip_index, new_start)
        self.timeline.rebuild()

    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.addAction("Remove", lambda: self.timeline.clip_remove.emit(self.clip_index))
        menu.addAction("Duplicate", lambda: self.timeline.clip_duplicate.emit(self.clip_index))
        menu.exec(event.screenPos())


class TimelineView(QGraphicsView):
    playhead_changed = Signal(float)
    clip_moved = Signal(int, float)
    clip_remove = Signal(int)
    clip_duplicate = Signal(int)
    clip_selected = Signal(int)
    timeline_clicked = Signal(float)

    def __init__(self, model: ArrangementModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.px_per_sec = 18.0
        self._playhead_sec = 0.0
        self._playhead_line: Optional[QGraphicsLineItem] = None
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor("#11111b")))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMinimumHeight(RULER_H + LANE_H + 24)
        self.setDragMode(QGraphicsView.RubberBandDrag)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.15 if delta > 0 else 1 / 1.15
            self.px_per_sec = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, self.px_per_sec * factor))
            self.rebuild()
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            if scene_pos.y() < RULER_H:
                sec = max(0.0, scene_pos.x() / self.px_per_sec)
                self.set_playhead(sec)
                self.timeline_clicked.emit(sec)
                event.accept()
                return
        super().mousePressEvent(event)

    def set_playhead(self, sec: float) -> None:
        self._playhead_sec = max(0.0, sec)
        self._update_playhead_line()

    def playhead_sec(self) -> float:
        return self._playhead_sec

    def _update_playhead_line(self) -> None:
        if self._playhead_line:
            self._scene.removeItem(self._playhead_line)
        x = self._playhead_sec * self.px_per_sec
        h = RULER_H + LANE_H + 8
        self._playhead_line = self._scene.addLine(x, 0, x, h, QPen(QColor("#f38ba8"), 2))

    def rebuild(self) -> None:
        self._scene.clear()
        self._playhead_line = None
        self._draw_ruler()
        x = 0.0
        for idx, clip in enumerate(self.model.clips):
            if clip.lane != "master":
                continue
            dur = clip.effective_duration_sec()
            w = dur * self.px_per_sec
            block = ClipBlockItem(idx, clip, x, w, self)
            self._scene.addItem(block)
            x += w
        total_w = max(x + 200, 800)
        self._scene.setSceneRect(0, 0, total_w, RULER_H + LANE_H + 8)
        self._update_playhead_line()

    def _draw_ruler(self) -> None:
        total = max(self.model.total_duration_sec(), 60.0)
        width = total * self.px_per_sec + 200
        bg = self._scene.addRect(0, 0, width, RULER_H, QPen(Qt.NoPen), QBrush(QColor("#181825")))
        bg.setZValue(-10)
        step = 10.0 if self.px_per_sec >= 8 else 30.0
        sec = 0.0
        while sec <= total + step:
            x = sec * self.px_per_sec
            self._scene.addLine(x, RULER_H - 8, x, RULER_H, QPen(QColor("#585b70")))
            if int(sec) % int(step) == 0:
                mins = int(sec // 60)
                secs = int(sec % 60)
                label = self._scene.addText(f"{mins}:{secs:02d}")
                label.setDefaultTextColor(QColor("#6c7086"))
                label.setPos(x + 2, 2)
            sec += step
