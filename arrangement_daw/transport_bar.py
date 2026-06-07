"""Transport bar: play/stop/loop and time display."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from playlist_arranger import SIX_HOUR_SEC, format_duration


class TransportBar(QWidget):
    play_clicked = Signal()
    stop_clicked = Signal()
    loop_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TransportBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.btn_play = QPushButton("Play")
        self.btn_stop = QPushButton("Stop")
        self.btn_play.clicked.connect(self.play_clicked.emit)
        self.btn_stop.clicked.connect(self.stop_clicked.emit)
        layout.addWidget(self.btn_play)
        layout.addWidget(self.btn_stop)

        self.chk_loop = QCheckBox("Loop")
        self.chk_loop.toggled.connect(self.loop_toggled.emit)
        layout.addWidget(self.chk_loop)

        self.lbl_time = QLabel("0:00.00 / 0:00.00")
        self.lbl_time.setStyleSheet("color: #89b4fa; font-family: Consolas; font-size: 13px;")
        layout.addWidget(self.lbl_time)

        self.lbl_target = QLabel(f"Target: {format_duration(SIX_HOUR_SEC)}")
        self.lbl_target.setStyleSheet("color: #6c7086;")
        layout.addWidget(self.lbl_target)

        self.lbl_bpm = QLabel("BPM: —")
        self.lbl_bpm.setStyleSheet("color: #a6adc8;")
        layout.addWidget(self.lbl_bpm)

        layout.addStretch()

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #a6e3a1;")
        layout.addWidget(self.lbl_status)

    def set_time(self, current: float, total: float, target_pct: float) -> None:
        self.lbl_time.setText(
            f"{format_duration(current)} / {format_duration(total)}  ({target_pct:.1f}% of 6h)"
        )

    def set_bpm(self, bpm: float | None) -> None:
        self.lbl_bpm.setText(f"BPM: {bpm:.0f}" if bpm else "BPM: —")

    def set_status(self, text: str) -> None:
        self.lbl_status.setText(text)

    def loop_enabled(self) -> bool:
        return self.chk_loop.isChecked()
