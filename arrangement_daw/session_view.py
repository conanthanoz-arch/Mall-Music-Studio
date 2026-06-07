"""Ableton-style session clip grid."""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from arrangement_daw.arrangement_model import ArrangementModel, ClipItem

MIME_LIBRARY = "application/x-mallmusic-library-index"
MIME_SESSION = "application/x-mallmusic-session"


class LibraryBrowser(QWidget):
    """Dock: filterable library list with drag support."""

    item_activated = Signal(object)

    def __init__(self, model: ArrangementModel, parent=None):
        super().__init__(parent)
        self.model = model
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Library — drag to Session or Timeline"))
        self.list = QListWidget()
        self.list.setDragEnabled(True)
        self.list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.list)
        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        for i, meta in enumerate(self.model.library_metas()):
            dur = float(meta.get("duration_sec", 0))
            title = meta.get("title", "?")
            theme = meta.get("theme", "")
            item = QListWidgetItem(f"{title}  ({dur:.1f}s)  [{theme}]")
            item.setData(Qt.UserRole, i)
            self.list.addItem(item)

    def _on_double_click(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.UserRole)
        metas = self.model.library_metas()
        if 0 <= idx < len(metas):
            self.item_activated.emit(metas[idx])

    def startDrag(self, *args, **kwargs):
        pass


class SessionGrid(QWidget):
    """Session clip launcher grid."""

    slot_clicked = Signal(int, int, object)
    drop_to_timeline = Signal(object)

    ROW_LABELS = ["Theme A", "Theme B", "Theme C", "Theme D"]

    def __init__(self, model: ArrangementModel, parent=None):
        super().__init__(parent)
        self.model = model
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Session — click slot to preview; drag to timeline"))
        self.table = QTableWidget(model.session_rows, model.session_cols)
        self.table.setHorizontalHeaderLabels([str(i + 1) for i in range(model.session_cols)])
        self.table.setVerticalHeaderLabels(self.ROW_LABELS[: model.session_rows])
        self.table.setAcceptDrops(True)
        self.table.setDragDropMode(QTableWidget.DragDrop)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.cellClicked.connect(self._on_cell_click)
        self.table.setMinimumHeight(160)
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self) -> None:
        for r in range(self.model.session_rows):
            for c in range(self.model.session_cols):
                clip = self.model.session[r][c]
                text = clip.title[:16] if clip else ""
                item = QTableWidgetItem(text)
                item.setBackground(QColor(clip.color if clip else "#313244"))
                item.setForeground(QColor("#cdd6f4" if clip else "#6c7086"))
                item.setData(Qt.UserRole, (r, c))
                self.table.setItem(r, c, item)

    def _on_cell_click(self, row: int, col: int) -> None:
        clip = self.model.session[row][col]
        self.slot_clicked.emit(row, col, clip)

    def assign_library_meta(self, row: int, col: int, meta: dict) -> None:
        clip = ClipItem.from_library_meta(meta, row * self.model.session_cols + col)
        self.model.set_session_slot(row, col, clip)
        self.refresh()

    def assign_from_library_index(self, lib_index: int, row: int, col: int) -> None:
        metas = self.model.library_metas()
        if 0 <= lib_index < len(metas):
            self.assign_library_meta(row, col, metas[lib_index])
