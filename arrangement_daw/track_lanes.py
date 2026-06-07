"""Mixer-style track lane overview."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from arrangement_daw.arrangement_model import ArrangementModel, LANES

LANE_COLORS = {
    "master": "#89b4fa",
    "drums": "#f38ba8",
    "bass": "#fab387",
    "chords": "#a6e3a1",
    "melody": "#cba6f7",
}


class TrackLanesWidget(QWidget):
    """Stacked lane strip mirroring timeline clip positions."""

    def __init__(self, model: ArrangementModel, px_per_sec: float = 18.0, parent=None):
        super().__init__(parent)
        self.model = model
        self.px_per_sec = px_per_sec
        self.setMinimumHeight(len(LANES) * 28 + 8)
        self.setMaximumHeight(len(LANES) * 28 + 8)

    def set_px_per_sec(self, px: float) -> None:
        self.px_per_sec = px
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#11111b"))
        lane_h = 26
        label_w = 54
        for li, lane in enumerate(LANES):
            y = 4 + li * lane_h
            color = QColor(LANE_COLORS.get(lane, "#585b70"))
            painter.setPen(QPen(color))
            painter.drawText(4, y + 16, lane[:8].title())
            painter.setPen(QPen(QColor("#313244")))
            painter.drawRect(label_w, y, self.width() - label_w - 4, lane_h - 2)
            if lane != "master":
                continue
            x = label_w + 2
            for clip in self.model.master_clips():
                w = max(4, int(clip.effective_duration_sec() * self.px_per_sec))
                painter.fillRect(x, y + 1, w, lane_h - 4, QColor(clip.color))
                x += w
        painter.end()
