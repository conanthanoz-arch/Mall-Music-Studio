"""Main Arrangement Studio window (PySide6)."""

from __future__ import annotations

import os
import sys
from typing import Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from arrangement_daw.arrangement_model import ArrangementModel, ClipItem
from arrangement_daw.audio_transport import ArrangementAudioTransport
from arrangement_daw.session_view import LibraryBrowser, SessionGrid
from arrangement_daw.timeline_view import TimelineView
from arrangement_daw.track_lanes import TrackLanesWidget
from arrangement_daw.transport_bar import TransportBar
from playlist_arranger import (
    SIX_HOUR_SEC,
    build_tracklist_snippet,
    export_master_mp3,
    format_duration,
    concat_wavs,
    save_master_wav,
    save_playlist,
)


def ensure_qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        app.setApplicationName("Mall Music Arrangement Studio")
    return app


DARK_STYLE = """
QMainWindow, QWidget, QDockWidget { background-color: #1e1e2e; color: #cdd6f4; }
QPushButton { background-color: #45475a; color: #cdd6f4; border: none; padding: 6px 12px; }
QPushButton:hover { background-color: #585b70; }
QListWidget, QTableWidget { background-color: #313244; color: #cdd6f4; gridline-color: #45475a; }
QHeaderView::section { background-color: #181825; color: #a6adc8; }
QMenuBar { background-color: #181825; color: #cdd6f4; }
QMenu { background-color: #313244; color: #cdd6f4; }
QStatusBar { background-color: #181825; color: #6c7086; }
QTabWidget::pane { border: 1px solid #313244; }
QTabBar::tab { background: #313244; color: #a6adc8; padding: 6px 12px; }
QTabBar::tab:selected { background: #45475a; color: #cdd6f4; }
"""


class ArrangementWindow(QMainWindow):
    def __init__(self, library_dir: str, app_base: Optional[str] = None):
        ensure_qt_app()
        super().__init__()
        self.library_dir = library_dir
        self.app_base = app_base or os.path.dirname(library_dir)
        self.model = ArrangementModel(library_dir)
        self.audio = ArrangementAudioTransport()
        self.audio.on_position = self._on_audio_position
        self.audio.on_finished = self._on_audio_finished

        self.setWindowTitle("Arrangement Studio — Mall Music")
        self.setMinimumSize(1000, 640)
        self.setStyleSheet(DARK_STYLE)

        self._build_menus()
        self._build_ui()
        self._wire_shortcuts()
        self._wire_signals()
        self._refresh_all()

        self._playhead_timer = QTimer(self)
        self._playhead_timer.timeout.connect(self._tick_playhead)
        self._playhead_timer.start(50)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        act_save = QAction("Save Playlist", self)
        act_save.setShortcut(QKeySequence.Save)
        act_save.triggered.connect(self._save_playlist)
        file_menu.addAction(act_save)
        act_export = QAction("Export Master Loop", self)
        act_export.triggered.connect(self._export_master)
        file_menu.addAction(act_export)
        file_menu.addSeparator()
        act_refresh = QAction("Refresh Library", self)
        act_refresh.triggered.connect(self._refresh_library)
        file_menu.addAction(act_refresh)

        edit = self.menuBar().addMenu("Edit")
        act_undo = QAction("Undo", self)
        act_undo.setShortcut(QKeySequence.Undo)
        act_undo.triggered.connect(self._undo)
        edit.addAction(act_undo)
        act_redo = QAction("Redo", self)
        act_redo.setShortcut(QKeySequence.Redo)
        act_redo.triggered.connect(self._redo)
        edit.addAction(act_redo)
        act_del = QAction("Remove Clip", self)
        act_del.setShortcut(QKeySequence.Delete)
        act_del.triggered.connect(self._remove_selected)
        edit.addAction(act_del)
        act_split = QAction("Split at Playhead", self)
        act_split.triggered.connect(self._split_at_playhead)
        edit.addAction(act_split)

        self.menuBar().addAction("Modular Rack (future)", lambda: None)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.transport = TransportBar()
        layout.addWidget(self.transport)

        tabs = QTabWidget()
        arrange_tab = QWidget()
        arrange_layout = QVBoxLayout(arrange_tab)

        self.timeline = TimelineView(self.model)
        arrange_layout.addWidget(self.timeline)

        self.lanes = TrackLanesWidget(self.model, self.timeline.px_per_sec)
        arrange_layout.addWidget(self.lanes)

        tabs.addTab(arrange_tab, "Arrangement")

        session_tab = QWidget()
        session_layout = QVBoxLayout(session_tab)
        self.session = SessionGrid(self.model)
        session_layout.addWidget(self.session)
        tabs.addTab(session_tab, "Session")

        tabs.addTab(QWidget(), "Modular Rack")

        layout.addWidget(tabs, stretch=1)

        self.setStatusBar(QStatusBar())

        dock = QDockWidget("Library", self)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.library = LibraryBrowser(self.model)
        dock.setWidget(self.library)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

    def _wire_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.Key_Space), self, self._toggle_play)

    def _wire_signals(self) -> None:
        self.transport.play_clicked.connect(self._toggle_play)
        self.transport.stop_clicked.connect(self._stop)
        self.transport.loop_toggled.connect(lambda _: None)

        self.timeline.clip_moved.connect(self._on_clip_moved)
        self.timeline.clip_remove.connect(self._on_clip_remove)
        self.timeline.clip_duplicate.connect(self._on_clip_duplicate)
        self.timeline.timeline_clicked.connect(self._on_timeline_click)

        self.library.item_activated.connect(self._add_library_to_timeline)
        self.session.slot_clicked.connect(self._on_session_slot)

    def _refresh_all(self) -> None:
        self.timeline.rebuild()
        self.lanes.set_px_per_sec(self.timeline.px_per_sec)
        self.lanes.update()
        self.session.refresh()
        self.library.refresh()
        self._update_transport_labels()

    def _refresh_library(self) -> None:
        self.model.load()
        self._refresh_all()

    def _update_transport_labels(self) -> None:
        total = self.model.total_duration_sec()
        cur = self.timeline.playhead_sec()
        pct = 100.0 * total / SIX_HOUR_SEC if SIX_HOUR_SEC else 0
        self.transport.set_time(cur, total, pct)
        bpms = [c.bpm for c in self.model.master_clips() if c.bpm]
        self.transport.set_bpm(bpms[0] if bpms else None)
        self.statusBar().showMessage(
            f"Timeline: {format_duration(total)} / {format_duration(SIX_HOUR_SEC)} ({pct:.1f}% of 6h)"
        )

    def _toggle_play(self) -> None:
        if self.audio.is_playing:
            self._stop()
            return
        tracks = self.model.export_track_dicts()
        if not tracks:
            self.transport.set_status("Timeline empty")
            return
        start = self.timeline.playhead_sec()
        ok = self.audio.play_tracks(tracks, loop=self.transport.loop_enabled(), start_sec=start)
        self.transport.set_status("Playing" if ok else "Playback failed")

    def _stop(self) -> None:
        self.audio.stop()
        self.transport.set_status("Stopped")

    def _on_audio_position(self, sec: float) -> None:
        QTimer.singleShot(0, lambda: self._set_playhead_ui(sec))

    def _on_audio_finished(self) -> None:
        QTimer.singleShot(0, lambda: self.transport.set_status("Stopped"))

    def _set_playhead_ui(self, sec: float) -> None:
        self.timeline.set_playhead(sec)
        total = self.model.total_duration_sec()
        pct = 100.0 * total / SIX_HOUR_SEC if SIX_HOUR_SEC else 0
        self.transport.set_time(sec, total, pct)

    def _tick_playhead(self) -> None:
        if self.audio.is_playing:
            self._set_playhead_ui(self.audio.current_sec())

    def _on_timeline_click(self, sec: float) -> None:
        if self.audio.is_playing:
            self.audio.seek(sec, self.model.export_track_dicts(), self.transport.loop_enabled())
        self._update_transport_labels()

    def _on_clip_moved(self, index: int, new_start_sec: float) -> None:
        self.model.reorder_by_time(index, new_start_sec)
        self._refresh_all()

    def _on_clip_remove(self, index: int) -> None:
        self.model.remove_clip(index)
        self._refresh_all()

    def _on_clip_duplicate(self, index: int) -> None:
        self.model.duplicate_clip(index)
        self._refresh_all()

    def _add_library_to_timeline(self, meta: dict) -> None:
        clip = ClipItem.from_library_meta(meta, len(self.model.clips))
        self.model.add_clip(clip)
        self._refresh_all()
        self.transport.set_status(f"Added: {clip.title}")

    def _on_session_slot(self, row: int, col: int, clip: Optional[ClipItem]) -> None:
        if clip:
            self.model.add_clip(copy_clip(clip))
            self._refresh_all()
            self.transport.set_status(f"Added from session: {clip.title}")
        else:
            idx = self.library.list.currentRow()
            if idx >= 0:
                self.session.assign_from_library_index(idx, row, col)
                self.transport.set_status("Assigned library clip to session slot")

    def _remove_selected(self) -> None:
        items = self.timeline.scene().selectedItems()
        for item in items:
            if hasattr(item, "clip_index"):
                self.model.remove_clip(item.clip_index)
        self._refresh_all()

    def _split_at_playhead(self) -> None:
        if self.model.split_at_playhead(self.timeline.playhead_sec()):
            self._refresh_all()
            self.transport.set_status("Split at playhead")

    def _undo(self) -> None:
        if self.model.undo():
            self._refresh_all()
            self.transport.set_status("Undo")

    def _redo(self) -> None:
        if self.model.redo():
            self._refresh_all()
            self.transport.set_status("Redo")

    def _save_playlist(self) -> None:
        if not self.model.master_clips():
            QMessageBox.information(self, "Save", "Timeline is empty.")
            return
        path = self.model.save_playlist()
        self.model.save_session()
        QMessageBox.information(self, "Saved", f"Playlist saved:\n{path}")

    def _export_master(self) -> None:
        tracks = self.model.export_track_dicts()
        if not tracks:
            QMessageBox.information(self, "Export", "Add clips to the timeline first.")
            return
        try:
            master = concat_wavs(tracks)
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        wav_out = os.path.join(self.app_base, "lofi_master.wav")
        mp3_out = os.path.join(self.app_base, "lofi_music.mp3")
        tracklist_out = os.path.join(self.app_base, "tracklist_export.txt")
        save_master_wav(master, wav_out)
        snippet = build_tracklist_snippet(tracks)
        with open(tracklist_out, "w", encoding="utf-8") as f:
            f.write(snippet)
        mp3_ok = export_master_mp3(wav_out, mp3_out)
        save_playlist(self.library_dir, tracks)
        msg = f"Wrote:\n{wav_out}\n{tracklist_out}\n"
        if mp3_ok:
            msg += mp3_out
        QMessageBox.information(self, "Export", msg)

    def closeEvent(self, event) -> None:
        self.audio.stop()
        self.model.save_session()
        super().closeEvent(event)


def copy_clip(clip: ClipItem) -> ClipItem:
    import copy

    return copy.deepcopy(clip)
