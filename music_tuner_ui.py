"""Mall Music Studio — visual Tkinter tuner for procedural lo-fi tracks."""

import json
import os
import random
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from audio_synthesizer import (
    buffer_duration_sec,
    generate_drum_pattern,
    save_wav,
    step_times_visual,
    synthesize_measure,
    synthesize_track,
)
import numpy as np

from drum_engine import render_drum_hit
from instrument_presets import (
    delete_user_preset,
    get_preset,
    label_from_preset_id,
    list_presets_for_mode,
    preset_id_from_label_for_mode,
    save_user_preset,
    set_library_root,
)
from tools.import_worker import fit_emulated_preset_for_stem, update_manifest_stem
from voice_engine import render_voice
from mix_tracks import (
    MAX_MIX_TRACKS,
    TRACK_MODES,
    default_mix_tracks,
    make_track,
    suggest_track_name,
    tracks_to_save,
)
from import_pipeline import (
    check_import_dependencies,
    install_command,
    read_import_progress,
    run_import_subprocess,
)
from melody_generator import generate_melody_steps
from music_theory import SAMPLE_RATE, THEME_PROFILES
from playlist_arranger import (
    SIX_HOUR_SEC,
    arrangement_duration_sec,
    build_tracklist_snippet,
    concat_wavs,
    export_master_mp3,
    format_duration,
    load_library_metas,
    load_playlist,
    resolve_playlist_entries,
    save_master_wav,
    save_playlist,
)
from waveform_utils import GrooveGridCanvas, StemLanesCanvas, WaveformCanvas

APP_VERSION = "v0.12"
DEBOUNCE_MS = 320
AUDIO_DEBOUNCE_MS = 450
SEED_MAX = 999999


def app_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


DEFAULT_LIBRARY = os.path.join(app_base_dir(), "music_library")


class MallMusicStudioApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"Mall Music Studio {APP_VERSION}")
        self.root.geometry("900x760")
        self.root.configure(bg="#1e1e2e")
        self.root.minsize(820, 560)

        self.library_dir = DEFAULT_LIBRARY
        os.makedirs(self.library_dir, exist_ok=True)
        set_library_root(self.library_dir)

        self._import_manifest: dict = {}
        self._import_stems: list = []
        self._import_busy = False
        self._import_progress_job = None

        self.var_theme = tk.StringVar(value="pixel_art")
        self.var_bpm = tk.IntVar(value=78)
        self.var_swing = tk.DoubleVar(value=0.15)
        self.var_sidechain = tk.DoubleVar(value=0.60)
        self.var_density = tk.IntVar(value=70)
        self.var_reverb = tk.DoubleVar(value=0.45)
        self.var_measures = tk.IntVar(value=8)
        self.var_target_sec = tk.IntVar(value=180)
        self.var_seed = tk.IntVar(value=random.randint(0, SEED_MAX))
        self.var_auto_advance_seed = tk.BooleanVar(value=False)
        self.var_loop_preview = tk.BooleanVar(value=False)

        self._mix_tracks = default_mix_tracks()
        self._track_row_frames: list = []

        self._last_buffer = None
        self._last_melody: list = []
        self._last_seed = self.var_seed.get()
        self._playback_proc = None
        self._melody_labels: list = []
        self._library_metas: list = []
        self._arrangement: list = []
        self._playhead_job = None
        self._play_duration = 0.0
        self._playhead_ratio = 0.0
        self._playback_clock_last = 0.0
        self._playhead_active = False
        self._debounce_job = None
        self._audio_restart_job = None
        self._last_drums: dict = {}
        self._last_stems: dict = {}
        self._live_preview_busy = False
        self._preview_session_armed = False
        self._synth_thread_busy = False
        self._loop_playhead = False

        self._arr_window = None
        self._qt_poll_job = None

        self._build_ui()
        self._load_arrangement_from_disk()
        self._refresh_library()
        self._wire_param_traces()
        self._update_instant_visuals()
        self._schedule_live_preview()

    def _build_ui(self):
        header = tk.Label(
            self.root,
            text="Mall Music Studio",
            font=("Segoe UI", 18, "bold"),
            fg="#cdd6f4",
            bg="#1e1e2e",
        )
        header.pack(pady=(12, 4))

        style = ttk.Style()
        style.theme_use("default")
        style.configure("TScale", background="#1e1e2e", troughcolor="#313244")

        outer = tk.Frame(self.root, bg="#1e1e2e")
        outer.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._scroll_canvas = tk.Canvas(outer, bg="#1e1e2e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=self._scroll_canvas.yview)
        self._scroll_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._scroll_canvas.pack(side="left", fill="both", expand=True)

        self.scroll_frame = tk.Frame(self._scroll_canvas, bg="#1e1e2e")
        self._scroll_window = self._scroll_canvas.create_window(
            (0, 0), window=self.scroll_frame, anchor="nw"
        )
        self.scroll_frame.bind("<Configure>", self._on_scroll_frame_configure)
        self._scroll_canvas.bind("<Configure>", self._on_scroll_canvas_configure)
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

        self._build_generate_section(self.scroll_frame)
        self._build_youtube_import_section(self.scroll_frame)
        self._build_mix_tracks_section(self.scroll_frame)
        self._build_arrange_section(self.scroll_frame)

    def _on_scroll_frame_configure(self, _event=None):
        self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))

    def _on_scroll_canvas_configure(self, event):
        self._scroll_canvas.itemconfig(self._scroll_window, width=event.width)

    def _on_mousewheel(self, event):
        self._scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _build_generate_section(self, parent):

        wf_frame = tk.LabelFrame(parent, text="Mix waveform", fg="#a6adc8", bg="#1e1e2e")
        wf_frame.pack(fill="x", padx=12, pady=(8, 4))
        self.gen_wave_canvas = tk.Canvas(
            wf_frame, height=88, bg="#181825", highlightthickness=0
        )
        self.gen_wave_canvas.pack(fill="x", padx=8, pady=(8, 4))
        self.gen_waveform = WaveformCanvas(self.gen_wave_canvas)
        self.gen_wave_canvas.bind("<Configure>", lambda _: self._redraw_gen_waveform())

        stem_frame = tk.LabelFrame(parent, text="Stem lanes", fg="#a6adc8", bg="#1e1e2e")
        stem_frame.pack(fill="x", padx=12, pady=4)
        self.gen_stem_canvas = tk.Canvas(
            stem_frame, height=130, bg="#181825", highlightthickness=0
        )
        self.gen_stem_canvas.pack(fill="x", padx=8, pady=8)
        self.gen_stems = StemLanesCanvas(self.gen_stem_canvas)
        self.gen_stem_canvas.bind("<Configure>", lambda _: self._redraw_gen_stems())

        grid_frame = tk.LabelFrame(parent, text="Groove grid (BPM + swing + drums)", fg="#a6adc8", bg="#1e1e2e")
        grid_frame.pack(fill="x", padx=12, pady=4)
        self.gen_grid_canvas = tk.Canvas(
            grid_frame, height=58, bg="#181825", highlightthickness=0
        )
        self.gen_grid_canvas.pack(fill="x", padx=8, pady=8)
        self.gen_groove = GrooveGridCanvas(self.gen_grid_canvas)
        self.gen_grid_canvas.bind("<Configure>", lambda _: self._redraw_gen_groove())

        self.lbl_theme_hint = tk.Label(
            parent,
            text="",
            fg="#89b4fa",
            bg="#1e1e2e",
            font=("Segoe UI", 9),
            anchor="w",
        )
        self.lbl_theme_hint.pack(fill="x", padx=16, pady=(0, 4))
        self.lbl_live_status = tk.Label(
            parent,
            text="Live preview: ready",
            fg="#6c7086",
            bg="#1e1e2e",
            font=("Segoe UI", 8),
            anchor="w",
        )
        self.lbl_live_status.pack(fill="x", padx=16, pady=(0, 4))

        theme_row = tk.Frame(parent, bg="#1e1e2e")
        theme_row.pack(fill="x", padx=12, pady=4)
        tk.Label(theme_row, text="Theme block:", fg="#a6adc8", bg="#1e1e2e").pack(side="left")
        ttk.Combobox(
            theme_row,
            textvariable=self.var_theme,
            values=list(THEME_PROFILES.keys()),
            state="readonly",
            width=18,
        ).pack(side="left", padx=8)
        self.var_theme.trace_add("write", lambda *_: self._on_param_change())

        seed_row = tk.Frame(parent, bg="#1e1e2e")
        seed_row.pack(fill="x", padx=12, pady=4)
        tk.Label(seed_row, text="Random seed:", fg="#a6adc8", bg="#1e1e2e").pack(side="left")
        tk.Spinbox(
            seed_row,
            from_=0,
            to=SEED_MAX,
            textvariable=self.var_seed,
            width=10,
            bg="#313244",
            fg="#cdd6f4",
            buttonbackground="#45475a",
        ).pack(side="left", padx=8)
        self.var_seed.trace_add("write", lambda *_: self._on_param_change())
        for text, cmd in [("Randomize", self._randomize_seed), ("Seed +1", self._bump_seed)]:
            tk.Button(
                seed_row, text=text, command=cmd, bg="#45475a", fg="#cdd6f4", relief="flat", padx=8
            ).pack(side="left", padx=4)
        tk.Checkbutton(
            seed_row,
            text="Auto-advance seed on preview",
            variable=self.var_auto_advance_seed,
            fg="#a6adc8",
            bg="#1e1e2e",
            selectcolor="#313244",
        ).pack(side="left", padx=12)

        for label, var, lo, hi, fmt, preview in [
            ("Track Tempo (BPM):", self.var_bpm, 60, 120, "%d", True),
            ("Groove Swing Amount:", self.var_swing, 0.0, 0.4, "%.2f", True),
            ("Sidechain Compression Depth:", self.var_sidechain, 0.0, 1.0, "%.2f", True),
            ("Melody Note Density (%):", self.var_density, 10, 100, "%d", True),
            ("Ambient Reverb Decay:", self.var_reverb, 0.1, 0.9, "%.2f", True),
            ("Preview measures:", self.var_measures, 1, 32, "%d", True),
            ("Target track length (sec):", self.var_target_sec, 30, 600, "%d", False),
        ]:
            self._slider_row(parent, label, var, lo, hi, fmt, triggers_preview=preview)

        tk.Label(
            parent,
            text=(
                "Sliders update visuals automatically. After Preview Loop, changes restart audio "
                "(until Stop Preview)."
            ),
            fg="#585b70",
            bg="#1e1e2e",
            font=("Segoe UI", 8),
        ).pack(fill="x", padx=16, pady=(0, 4))

        btn_row = tk.Frame(parent, bg="#1e1e2e")
        btn_row.pack(pady=10)
        for text, cmd in [
            ("Synthesize & Test Feel", self._test_one_measure),
            ("Preview Loop", self._preview_loop),
            ("Save Track to Library", self._save_track),
            ("Stop Preview", self._stop_preview),
        ]:
            tk.Button(
                btn_row, text=text, command=cmd, bg="#45475a", fg="#cdd6f4", relief="flat", padx=10, pady=6
            ).pack(side="left", padx=4)

        tk.Checkbutton(
            btn_row,
            text="Loop preview until Stop",
            variable=self.var_loop_preview,
            fg="#a6adc8",
            bg="#1e1e2e",
            selectcolor="#313244",
        ).pack(side="left", padx=12)

        mel_frame = tk.LabelFrame(parent, text="Melody step map", fg="#a6adc8", bg="#1e1e2e")
        mel_frame.pack(fill="x", padx=12, pady=6)
        self._melody_grid = tk.Frame(mel_frame, bg="#1e1e2e")
        self._melody_grid.pack(padx=8, pady=8)
        for i in range(16):
            lbl = tk.Label(
                self._melody_grid, text="-", width=4, bg="#313244", fg="#6c7086", font=("Consolas", 9)
            )
            lbl.grid(row=i // 8, column=i % 8, padx=2, pady=2)
            self._melody_labels.append(lbl)

        info_frame = tk.LabelFrame(parent, text="Duration & quality", fg="#a6adc8", bg="#1e1e2e")
        info_frame.pack(fill="x", padx=12, pady=6)
        self.lbl_duration = tk.Label(info_frame, text="Duration: --", fg="#cdd6f4", bg="#1e1e2e", anchor="w")
        self.lbl_duration.pack(fill="x", padx=8, pady=2)
        self.lbl_frames = tk.Label(info_frame, text="Frames @ 30 FPS: --", fg="#cdd6f4", bg="#1e1e2e", anchor="w")
        self.lbl_frames.pack(fill="x", padx=8, pady=2)
        self.lbl_seed_info = tk.Label(info_frame, text="Active seed: --", fg="#89b4fa", bg="#1e1e2e", anchor="w")
        self.lbl_seed_info.pack(fill="x", padx=8, pady=2)
        self.lbl_library_total = tk.Label(
            info_frame, text="Library total: --", fg="#cdd6f4", bg="#1e1e2e", anchor="w"
        )
        self.lbl_library_total.pack(fill="x", padx=8, pady=2)

        lib_frame = tk.LabelFrame(parent, text="music_library/", fg="#a6adc8", bg="#1e1e2e")
        lib_frame.pack(fill="x", padx=12, pady=(6, 12))
        self.library_list = tk.Listbox(
            lib_frame, bg="#313244", fg="#cdd6f4", selectbackground="#585b70", height=5
        )
        self.library_list.pack(fill="x", padx=8, pady=8)
        self.library_list.bind("<<ListboxSelect>>", lambda _: self._on_library_select())
        self.library_list.bind("<Double-Button-1>", lambda _: self._preview_library_item())

    def _build_youtube_import_section(self, parent):
        frame = tk.LabelFrame(parent, text="Import from YouTube", fg="#a6adc8", bg="#1e1e2e")
        frame.pack(fill="x", padx=12, pady=8)

        tk.Label(
            frame,
            text=(
                "Paste a URL → Analyze stems → scrub to the loud section → Fit emulated sound → "
                "edit synth params → Add as instrument. Audio is analyzed temporarily only; "
                "saved presets are synth JSON with generic names."
            ),
            fg="#585b70",
            bg="#1e1e2e",
            font=("Segoe UI", 8),
            wraplength=820,
            justify="left",
        ).pack(fill="x", padx=10, pady=(8, 2))

        self.lbl_import_deps = tk.Label(frame, text="", fg="#89b4fa", bg="#1e1e2e", font=("Segoe UI", 8))
        self.lbl_import_deps.pack(fill="x", padx=10, pady=(0, 2))

        dep_btn_row = tk.Frame(frame, bg="#1e1e2e")
        dep_btn_row.pack(fill="x", padx=10, pady=(0, 6))
        tk.Button(
            dep_btn_row,
            text="Install import tools",
            command=self._install_import_tools,
            bg="#585b70",
            fg="#cdd6f4",
            relief="flat",
            padx=8,
            pady=2,
        ).pack(side="left")
        tk.Button(
            dep_btn_row,
            text="Refresh status",
            command=self._refresh_import_deps_label,
            bg="#45475a",
            fg="#cdd6f4",
            relief="flat",
            padx=8,
            pady=2,
        ).pack(side="left", padx=6)

        row = tk.Frame(frame, bg="#1e1e2e")
        row.pack(fill="x", padx=10, pady=4)
        self.var_yt_url = tk.StringVar(value="")
        tk.Entry(row, textvariable=self.var_yt_url, bg="#313244", fg="#cdd6f4", width=72).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        tk.Button(
            row,
            text="Analyze stems",
            command=self._run_youtube_import,
            bg="#45475a",
            fg="#cdd6f4",
            relief="flat",
            padx=12,
            pady=4,
        ).pack(side="left")

        self.lbl_import_status = tk.Label(
            frame, text="Ready", fg="#a6adc8", bg="#1e1e2e", anchor="w"
        )
        self.lbl_import_status.pack(fill="x", padx=10, pady=4)
        self._refresh_import_deps_label()

        self.import_stems_list = tk.Listbox(
            frame, bg="#313244", fg="#cdd6f4", selectbackground="#585b70", height=5
        )
        self.import_stems_list.pack(fill="x", padx=10, pady=4)
        self.import_stems_list.bind("<<ListboxSelect>>", lambda _: self._on_import_stem_select())

        tk.Label(
            frame,
            text="Stem timeline — click waveform or drag “Sample from” to the section to analyze",
            fg="#a6adc8",
            bg="#1e1e2e",
            font=("Segoe UI", 8),
        ).pack(fill="x", padx=10, pady=(6, 2))

        self.import_stem_wave_canvas = tk.Canvas(
            frame, height=64, bg="#181825", highlightthickness=0
        )
        self.import_stem_wave_canvas.pack(fill="x", padx=10, pady=(0, 4))
        self.import_stem_waveform = WaveformCanvas(self.import_stem_wave_canvas)
        self.import_stem_wave_canvas.bind("<Button-1>", self._on_import_stem_region_click)

        region_row = tk.Frame(frame, bg="#1e1e2e")
        region_row.pack(fill="x", padx=10, pady=2)
        tk.Label(region_row, text="Sample from", fg="#a6adc8", bg="#1e1e2e", font=("Segoe UI", 8)).pack(
            side="left", padx=(0, 6)
        )
        self.var_sample_region_start = tk.DoubleVar(value=0.0)
        self.sample_region_seek = tk.Scale(
            region_row,
            from_=0.0,
            to=1.0,
            resolution=0.001,
            orient=tk.HORIZONTAL,
            variable=self.var_sample_region_start,
            command=self._on_sample_region_drag,
            showvalue=False,
            bg="#1e1e2e",
            fg="#cdd6f4",
            troughcolor="#313244",
            activebackground="#a6e3a1",
            highlightthickness=0,
            length=300,
        )
        self.sample_region_seek.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.lbl_sample_region_start = tk.Label(
            region_row, text="0:00", fg="#a6e3a1", bg="#1e1e2e", font=("Consolas", 8), width=8
        )
        self.lbl_sample_region_start.pack(side="left")
        tk.Label(region_row, text="Length s", fg="#a6adc8", bg="#1e1e2e", font=("Segoe UI", 8)).pack(
            side="left", padx=(10, 4)
        )
        self.var_sample_region_sec = tk.DoubleVar(value=30.0)
        tk.Spinbox(
            region_row,
            from_=8,
            to=120,
            increment=5,
            textvariable=self.var_sample_region_sec,
            width=5,
            bg="#313244",
            fg="#cdd6f4",
            buttonbackground="#45475a",
            command=self._on_sample_region_drag,
        ).pack(side="left")

        stem_btn_row = tk.Frame(frame, bg="#1e1e2e")
        stem_btn_row.pack(fill="x", padx=10, pady=(4, 8))
        tk.Button(
            stem_btn_row,
            text="Preview stem",
            command=self._preview_import_stem,
            bg="#45475a",
            fg="#cdd6f4",
            relief="flat",
            padx=10,
            pady=4,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            stem_btn_row,
            text="Fit emulated sound",
            command=self._fit_emulated_sound,
            bg="#585b70",
            fg="#cdd6f4",
            relief="flat",
            padx=10,
            pady=4,
        ).pack(side="left")

        preview_row = tk.Frame(frame, bg="#1e1e2e")
        preview_row.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(preview_row, text="Preview from", fg="#a6adc8", bg="#1e1e2e", font=("Segoe UI", 8)).pack(
            side="left", padx=(0, 6)
        )
        self.var_import_stem_pos = tk.DoubleVar(value=0.0)
        self.import_stem_seek = tk.Scale(
            preview_row,
            from_=0.0,
            to=1.0,
            resolution=0.001,
            orient=tk.HORIZONTAL,
            variable=self.var_import_stem_pos,
            command=self._on_import_stem_seek_drag,
            showvalue=False,
            bg="#1e1e2e",
            fg="#cdd6f4",
            troughcolor="#313244",
            activebackground="#89b4fa",
            highlightthickness=0,
            length=300,
        )
        self.import_stem_seek.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.lbl_import_stem_pos = tk.Label(
            preview_row, text="0:00", fg="#89b4fa", bg="#1e1e2e", font=("Consolas", 8), width=8
        )
        self.lbl_import_stem_pos.pack(side="left")

        tk.Label(
            frame,
            text="Emulated sound — synthesized preview (not the stem WAV)",
            fg="#a6adc8",
            bg="#1e1e2e",
            font=("Segoe UI", 8),
        ).pack(fill="x", padx=10, pady=(8, 2))
        self.lbl_emulated_preset = tk.Label(
            frame, text="Fit emulated sound to create a preset", fg="#89b4fa", bg="#1e1e2e", anchor="w"
        )
        self.lbl_emulated_preset.pack(fill="x", padx=10, pady=(0, 4))

        self.emulated_wave_canvas = tk.Canvas(
            frame, height=52, bg="#181825", highlightthickness=0
        )
        self.emulated_wave_canvas.pack(fill="x", padx=10, pady=(0, 4))
        self.emulated_waveform = WaveformCanvas(self.emulated_wave_canvas)

        self.va_edit_row = tk.Frame(frame, bg="#1e1e2e")
        self.va_edit_row.pack(fill="x", padx=10, pady=4)
        tk.Label(self.va_edit_row, text="Vol", fg="#a6adc8", bg="#1e1e2e", width=3).pack(side="left")
        self.var_emu_volume = tk.DoubleVar(value=1.0)
        tk.Scale(
            self.va_edit_row,
            from_=0.0,
            to=2.0,
            resolution=0.01,
            orient=tk.HORIZONTAL,
            variable=self.var_emu_volume,
            length=80,
            bg="#1e1e2e",
            fg="#cdd6f4",
            troughcolor="#313244",
            highlightthickness=0,
        ).pack(side="left", padx=(0, 8))
        tk.Label(self.va_edit_row, text="Attack ms", fg="#a6adc8", bg="#1e1e2e").pack(side="left")
        self.var_emu_attack = tk.DoubleVar(value=10.0)
        tk.Scale(
            self.va_edit_row,
            from_=3.0,
            to=80.0,
            resolution=1.0,
            orient=tk.HORIZONTAL,
            variable=self.var_emu_attack,
            length=90,
            bg="#1e1e2e",
            fg="#cdd6f4",
            troughcolor="#313244",
            highlightthickness=0,
        ).pack(side="left", padx=(0, 8))
        tk.Label(self.va_edit_row, text="Release ms", fg="#a6adc8", bg="#1e1e2e").pack(side="left")
        self.var_emu_release = tk.DoubleVar(value=100.0)
        tk.Scale(
            self.va_edit_row,
            from_=20.0,
            to=400.0,
            resolution=5.0,
            orient=tk.HORIZONTAL,
            variable=self.var_emu_release,
            length=90,
            bg="#1e1e2e",
            fg="#cdd6f4",
            troughcolor="#313244",
            highlightthickness=0,
        ).pack(side="left", padx=(0, 8))
        tk.Label(self.va_edit_row, text="Filter Hz", fg="#a6adc8", bg="#1e1e2e").pack(side="left")
        self.var_emu_cutoff = tk.DoubleVar(value=1200.0)
        tk.Scale(
            self.va_edit_row,
            from_=200.0,
            to=8000.0,
            resolution=50.0,
            orient=tk.HORIZONTAL,
            variable=self.var_emu_cutoff,
            length=110,
            bg="#1e1e2e",
            fg="#cdd6f4",
            troughcolor="#313244",
            highlightthickness=0,
        ).pack(side="left")

        self.drum_edit_row = tk.Frame(frame, bg="#1e1e2e")
        self.drum_edit_row.pack(fill="x", padx=10, pady=4)
        tk.Label(self.drum_edit_row, text="Kick", fg="#a6adc8", bg="#1e1e2e").pack(side="left")
        self.var_emu_kick_type = tk.StringVar(value="lofi")
        ttk.Combobox(
            self.drum_edit_row,
            textvariable=self.var_emu_kick_type,
            values=["lofi", "808", "tight"],
            width=8,
            state="readonly",
        ).pack(side="left", padx=(4, 10))
        tk.Label(self.drum_edit_row, text="Snare", fg="#a6adc8", bg="#1e1e2e").pack(side="left")
        self.var_emu_snare_type = tk.StringVar(value="lofi")
        ttk.Combobox(
            self.drum_edit_row,
            textvariable=self.var_emu_snare_type,
            values=["lofi", "crisp", "808_clap"],
            width=10,
            state="readonly",
        ).pack(side="left", padx=(4, 10))
        tk.Label(self.drum_edit_row, text="Hat", fg="#a6adc8", bg="#1e1e2e").pack(side="left")
        self.var_emu_hat_type = tk.StringVar(value="lofi_closed")
        ttk.Combobox(
            self.drum_edit_row,
            textvariable=self.var_emu_hat_type,
            values=["lofi_closed", "808_hat"],
            width=12,
            state="readonly",
        ).pack(side="left", padx=(4, 10))
        tk.Label(self.drum_edit_row, text="Vol", fg="#a6adc8", bg="#1e1e2e").pack(side="left")
        self.var_emu_drum_vol = tk.DoubleVar(value=1.0)
        tk.Scale(
            self.drum_edit_row,
            from_=0.0,
            to=2.0,
            resolution=0.01,
            orient=tk.HORIZONTAL,
            variable=self.var_emu_drum_vol,
            length=90,
            bg="#1e1e2e",
            fg="#cdd6f4",
            troughcolor="#313244",
            highlightthickness=0,
        ).pack(side="left", padx=(4, 0))
        self.drum_edit_row.pack_forget()

        btn_row = tk.Frame(frame, bg="#1e1e2e")
        btn_row.pack(fill="x", padx=10, pady=(4, 10))
        for text, cmd, color in (
            ("Preview emulated", self._preview_emulated_sound, "#45475a"),
            ("Apply edits", self._apply_emulated_edits, "#45475a"),
            ("Re-fit", self._fit_emulated_sound, "#585b70"),
            ("Delete emulated", self._delete_emulated_preset, "#585b70"),
            ("Add as instrument", self._add_imported_stem_as_track, "#45475a"),
        ):
            tk.Button(
                btn_row,
                text=text,
                command=cmd,
                bg=color,
                fg="#cdd6f4",
                relief="flat",
                padx=8,
                pady=4,
            ).pack(side="left", padx=(0, 6))

        self._import_stem_wav_path = ""
        self._import_stem_duration = 0.0
        self._playhead_waveform = None
        self._editing_emulated_preset_id = None
        self._emulated_preview_path = ""
        self._emulated_preview_duration = 0.0
        self._import_fit_busy = False

    def _refresh_import_deps_label(self):
        deps = check_import_dependencies()
        parts = [
            f"yt-dlp: {'OK' if deps['yt_dlp'] else 'missing'}",
            f"demucs: {'OK' if deps['demucs'] else 'missing'}",
            f"soundfile: {'OK' if deps.get('soundfile') else 'missing'}",
            f"ffmpeg: {'OK' if deps.get('ffmpeg') else 'missing'}",
            f"worker: {'OK' if deps.get('worker', True) else 'missing'}",
        ]
        py = deps.get("python", "")
        if py:
            parts.append(f"python: {os.path.basename(os.path.dirname(py))}\\{os.path.basename(py)}")
        color = "#a6e3a1" if deps.get("ready") else "#f38ba8"
        self.lbl_import_deps.config(text="  |  ".join(parts), fg=color)
        if not hasattr(self, "lbl_import_status"):
            return
        if deps.get("ready"):
            self.lbl_import_status.config(text="Import tools ready.")
        else:
            self.lbl_import_status.config(
                text="Click Install import tools (first time only; demucs download is large)."
            )

    def _install_import_tools(self):
        if getattr(self, "_install_tools_busy", False):
            return
        py = check_import_dependencies().get("python", sys.executable)
        pip_cmd = [py, "-m", "pip", "install", "yt-dlp", "demucs", "soundfile"]
        self._install_tools_busy = True
        self.lbl_import_status.config(text="Installing yt-dlp + demucs (may take several minutes)…")

        def work():
            proc = subprocess.run(
                pip_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=app_base_dir(),
            )
            err = proc.stderr or proc.stdout or ""
            self.root.after(0, lambda: self._on_install_tools_done(proc.returncode, err))

        threading.Thread(target=work, daemon=True).start()

    def _on_install_tools_done(self, code: int, err: str):
        self._install_tools_busy = False
        self._refresh_import_deps_label()
        if code == 0:
            messagebox.showinfo("Import tools", "yt-dlp and demucs installed successfully.")
        else:
            messagebox.showerror(
                "Install failed",
                (err or "pip install failed")[:800]
                + "\n\nOr run from project folder:\n  install_import_tools.bat",
            )

    def _run_youtube_import(self):
        url = self.var_yt_url.get().strip()
        if not url:
            messagebox.showinfo("Import", "Enter a YouTube URL first.")
            return
        if self._import_busy:
            return
        deps = check_import_dependencies()
        if not deps.get("ready"):
            messagebox.showerror(
                "Import",
                "Import tools not ready.\n\n"
                f"Install with:\n  {install_command()}\n\n"
                "Or click **Install import tools** in the YouTube panel.",
            )
            self._refresh_import_deps_label()
            return

        self._import_busy = True
        self.lbl_import_status.config(
            text="Starting stem separation… (first run can take 5–10 min while Demucs downloads models)"
        )
        self.import_stems_list.delete(0, tk.END)
        self._import_progress_job = None
        self._poll_import_progress()

        def work():
            try:
                manifest = run_import_subprocess(url, self.library_dir)
                self.root.after(0, lambda m=manifest: self._on_import_complete(m, None))
            except Exception as exc:
                self.root.after(0, lambda e=exc: self._on_import_complete(None, e))

        threading.Thread(target=work, daemon=True).start()

    def _poll_import_progress(self):
        if not self._import_busy:
            self._import_progress_job = None
            return
        prog = read_import_progress(self.library_dir)
        stage = prog.get("stage", "")
        detail = prog.get("detail", "")
        labels = {
            "downloading": "Downloading from YouTube…",
            "separating": "Separating stems with Demucs…",
            "done": "Ready — scrub to a loud section and fit emulated sound",
            "error": "Import failed",
        }
        if stage == "error" and detail:
            self.lbl_import_status.config(text=f"Import error: {detail[:200]}")
        elif stage:
            msg = labels.get(stage, stage)
            if detail:
                msg = f"{msg}  {detail}"
            self.lbl_import_status.config(text=msg)
        self._import_progress_job = self.root.after(500, self._poll_import_progress)

    def _on_import_complete(self, manifest, error):
        self._import_busy = False
        if self._import_progress_job:
            self.root.after_cancel(self._import_progress_job)
            self._import_progress_job = None
        if error:
            self.lbl_import_status.config(text=f"Import error: {error}")
            messagebox.showerror("Import failed", str(error))
            return
        self._import_manifest = manifest or {}
        self._import_stems = list(self._import_manifest.get("stems") or [])
        self._refresh_import_stems_list()
        self.lbl_import_status.config(
            text=(
                f"{len(self._import_stems)} stems ready. "
                "Select a stem, scrub to the loud section, then Fit emulated sound."
            )
        )
        if self._import_stems:
            self.import_stems_list.selection_set(0)
            self._on_import_stem_select()

    def _refresh_import_stems_list(self):
        self.import_stems_list.delete(0, tk.END)
        for stem in self._import_stems:
            built = stem.get("built", bool(stem.get("preset_id")))
            label = stem.get("label", stem.get("stem", "?"))
            if built:
                pl = stem.get("preset_label") or stem.get("preset_id", "")
                line = f"{label}  →  {pl}"
            else:
                line = f"{label}  [not fitted]"
            self.import_stems_list.insert(tk.END, line)

    def _format_preview_time(self, sec: float) -> str:
        sec = max(0.0, sec)
        mins = int(sec // 60)
        secs = int(sec % 60)
        return f"{mins}:{secs:02d}"

    def _set_import_stem_preview_source(self, wav: str, label: str = "") -> None:
        self._import_stem_wav_path = wav
        self.import_stem_waveform.draw_file(wav, label=label)
        self._import_stem_duration = self.import_stem_waveform.duration_sec
        self.var_import_stem_pos.set(0.0)
        self.import_stem_waveform.set_playhead_ratio(0.0)
        self.lbl_import_stem_pos.config(text=self._format_preview_time(0.0))

    def _on_import_stem_seek_drag(self, _val=None):
        ratio = float(self.var_import_stem_pos.get())
        self.import_stem_waveform.set_playhead_ratio(ratio)
        if self._import_stem_duration > 0:
            self.lbl_import_stem_pos.config(
                text=self._format_preview_time(ratio * self._import_stem_duration)
            )

    def _on_import_stem_region_click(self, event):
        w = max(1, self.import_stem_wave_canvas.winfo_width())
        ratio = max(0.0, min(1.0, (event.x - 2) / max(1, w - 4)))
        self.var_sample_region_start.set(ratio)
        self._on_sample_region_drag()

    def _on_sample_region_drag(self, _val=None):
        if self._import_stem_duration <= 0:
            return
        start_ratio = float(self.var_sample_region_start.get())
        length_sec = float(self.var_sample_region_sec.get())
        start_sec = start_ratio * self._import_stem_duration
        self.lbl_sample_region_start.config(text=self._format_preview_time(start_sec))
        end_ratio = min(1.0, start_ratio + length_sec / self._import_stem_duration)
        self.import_stem_waveform.draw_region_ratio(start_ratio, end_ratio)

    def _selected_import_stem(self):
        idx = self.import_stems_list.curselection()
        if not idx or idx[0] >= len(self._import_stems):
            return None
        return self._import_stems[idx[0]]

    def _on_import_stem_select(self):
        stem = self._selected_import_stem()
        if not stem:
            return
        wav = stem.get("wav")
        if wav and os.path.isfile(wav):
            self._set_import_stem_preview_source(wav, label=stem.get("label", ""))
        dur = self._import_stem_duration
        if dur > 0:
            analyze_start = float(stem.get("analyze_start_sec", 0))
            analyze_sec = float(stem.get("analyze_sec", 30))
            self.var_sample_region_start.set(max(0.0, min(1.0, analyze_start / dur)))
            self.var_sample_region_sec.set(analyze_sec)
            self._on_sample_region_drag()
        self._load_emulated_edit_ui(stem)
        if stem.get("built") and stem.get("preset_id"):
            self._refresh_emulated_preview_waveform()

    def _preview_import_stem(self):
        stem = self._selected_import_stem()
        if not stem:
            messagebox.showinfo("Import", "Select a stem first.")
            return
        wav = stem.get("wav")
        if wav and os.path.isfile(wav):
            if self._import_stem_wav_path != wav:
                self._set_import_stem_preview_source(wav, label=stem.get("label", ""))
            start_sec = float(self.var_import_stem_pos.get()) * self._import_stem_duration
            self._play_file(
                wav,
                duration=self._import_stem_duration,
                waveform=self.import_stem_waveform,
                start_sec=start_sec,
            )

    def _load_emulated_edit_ui(self, stem):
        preset_id = stem.get("preset_id")
        if not preset_id:
            self._editing_emulated_preset_id = None
            self.lbl_emulated_preset.config(text="Fit emulated sound to create a synth preset.")
            self.va_edit_row.pack_forget()
            self.drum_edit_row.pack_forget()
            self.emulated_waveform.clear()
            return
        preset = get_preset(preset_id)
        self._editing_emulated_preset_id = preset_id
        self.lbl_emulated_preset.config(text=preset.get("label", preset_id))
        engine = preset.get("engine", "va_voice")
        if engine == "drum_kit":
            self.va_edit_row.pack_forget()
            self.drum_edit_row.pack(fill="x", padx=10, pady=4)
            self.var_emu_kick_type.set(preset.get("kick", {}).get("type", "lofi"))
            self.var_emu_snare_type.set(preset.get("snare", {}).get("type", "lofi"))
            hat = preset.get("hihat_closed", {}).get("type", "lofi_closed")
            self.var_emu_hat_type.set(hat.replace("_open", "_closed") if "open" in hat else hat)
            self.var_emu_drum_vol.set(float(preset.get("volume", 1.0)))
        else:
            self.drum_edit_row.pack_forget()
            self.va_edit_row.pack(fill="x", padx=10, pady=4)
            env = preset.get("envelope") or {}
            filt = preset.get("filter") or {}
            self.var_emu_volume.set(float(preset.get("volume", 1.0)))
            self.var_emu_attack.set(float(env.get("attack_ms", 10)))
            self.var_emu_release.set(float(env.get("release_ms", 100)))
            self.var_emu_cutoff.set(float(filt.get("cutoff_hz", 1200)))

    def _render_emulated_preview_buffer(self, preset):
        rng = np.random.default_rng(42)
        engine = preset.get("engine", "va_voice")
        vol = float(preset.get("volume", 1.0))
        if engine == "drum_kit":
            kick = render_drum_hit(preset, "kick", rng=rng)
            gap = int(SAMPLE_RATE * 0.08)
            snare = render_drum_hit(preset, "snare", rng=rng)
            hat = render_drum_hit(preset, "hihat", closed_hat=True, rng=rng)
            wave = np.concatenate([kick, np.zeros(gap), snare, np.zeros(gap // 2), hat]) * vol
        else:
            wave = render_voice(preset, midi_note=60, duration=0.9, volume=vol, rng=rng)
        peak = float(np.max(np.abs(wave))) if len(wave) else 1.0
        if peak > 0:
            wave = wave / peak * 0.85
        return wave

    def _refresh_emulated_preview_waveform(self):
        preset_id = self._editing_emulated_preset_id
        if not preset_id:
            return
        preset = get_preset(preset_id)
        wave = self._render_emulated_preview_buffer(preset)
        label = preset.get("label", "Emulated preview")
        self.emulated_waveform.draw_buffer(wave, label=label)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        save_wav(tmp.name, wave)
        self._emulated_preview_path = tmp.name
        self._emulated_preview_duration = len(wave) / SAMPLE_RATE if len(wave) else 0.0

    def _fit_emulated_sound(self):
        stem = self._selected_import_stem()
        if not stem:
            messagebox.showinfo("Import", "Select a stem first.")
            return
        if self._import_fit_busy:
            return
        wav = stem.get("wav")
        if not wav or not os.path.isfile(wav):
            messagebox.showerror("Import", "Stem WAV missing.")
            return
        start_ratio = float(self.var_sample_region_start.get())
        length_sec = float(self.var_sample_region_sec.get())
        if self._import_stem_duration > 0:
            analyze_start = start_ratio * self._import_stem_duration
        else:
            analyze_start = float(stem.get("analyze_start_sec", 0))
        analyze_sec = length_sec
        preset_id = stem.get("preset_id") if stem.get("built") else None
        stem_name = stem.get("stem", "")

        self._import_fit_busy = True
        self.lbl_import_status.config(text="Fitting emulated sound…")

        def work():
            try:
                entry = fit_emulated_preset_for_stem(
                    wav,
                    stem_name,
                    analyze_start_sec=analyze_start,
                    analyze_sec=analyze_sec,
                    preset_id=preset_id,
                )
                manifest = update_manifest_stem(self.library_dir, stem_name, entry)
                self.root.after(0, lambda m=manifest, e=entry: self._on_fit_emulated_done(m, e, None))
            except Exception as exc:
                self.root.after(0, lambda e=exc: self._on_fit_emulated_done(None, None, e))

        threading.Thread(target=work, daemon=True).start()

    def _on_fit_emulated_done(self, manifest, entry, error):
        self._import_fit_busy = False
        if error:
            self.lbl_import_status.config(text=f"Fit failed: {error}")
            messagebox.showerror("Fit emulated sound", str(error))
            return
        if manifest:
            self._import_manifest = manifest
            self._import_stems = list(manifest.get("stems") or [])
        self._refresh_import_stems_list()
        stem_name = entry.get("stem") if entry else None
        if stem_name:
            for i, s in enumerate(self._import_stems):
                if s.get("stem") == stem_name:
                    self.import_stems_list.selection_clear(0, tk.END)
                    self.import_stems_list.selection_set(i)
                    self._on_import_stem_select()
                    break
        label = entry.get("preset_label", "") if entry else ""
        self.lbl_import_status.config(
            text=f"Fitted: {label}. Preview, tweak sliders, then Add as instrument."
        )
        self._rebuild_mix_track_rows()

    def _preview_emulated_sound(self):
        if not self._editing_emulated_preset_id:
            messagebox.showinfo("Import", "Fit emulated sound first.")
            return
        self._refresh_emulated_preview_waveform()
        if self._emulated_preview_path and os.path.isfile(self._emulated_preview_path):
            self._play_file(
                self._emulated_preview_path,
                duration=self._emulated_preview_duration,
                waveform=self.emulated_waveform,
            )

    def _apply_emulated_edits(self):
        preset_id = self._editing_emulated_preset_id
        if not preset_id:
            messagebox.showinfo("Import", "Fit emulated sound first.")
            return
        preset = get_preset(preset_id)
        engine = preset.get("engine", "va_voice")
        if engine == "drum_kit":
            preset["volume"] = float(self.var_emu_drum_vol.get())
            preset.setdefault("kick", {})["type"] = self.var_emu_kick_type.get()
            preset.setdefault("snare", {})["type"] = self.var_emu_snare_type.get()
            hat_type = self.var_emu_hat_type.get()
            preset.setdefault("hihat_closed", {})["type"] = hat_type
            open_type = "808_hat_open" if hat_type == "808_hat" else "lofi_open"
            preset.setdefault("hihat_open", {})["type"] = open_type
        else:
            preset["volume"] = float(self.var_emu_volume.get())
            env = preset.setdefault("envelope", {})
            env["attack_ms"] = float(self.var_emu_attack.get())
            env["release_ms"] = float(self.var_emu_release.get())
            filt = preset.setdefault("filter", {"type": "lp", "cutoff_hz": 1200})
            filt["type"] = filt.get("type", "lp")
            filt["cutoff_hz"] = float(self.var_emu_cutoff.get())
        save_user_preset(preset)
        self._refresh_emulated_preview_waveform()
        stem = self._selected_import_stem()
        if stem and stem.get("preset_id") == preset_id:
            stem["preset_label"] = preset.get("label", stem.get("preset_label", ""))
            update_manifest_stem(self.library_dir, stem.get("stem"), stem)
            self._refresh_import_stems_list()
        self.lbl_import_status.config(text="Emulated preset saved.")
        self._rebuild_mix_track_rows()
        self._on_param_change()

    def _delete_emulated_preset(self):
        stem = self._selected_import_stem()
        if not stem or not stem.get("preset_id"):
            messagebox.showinfo("Import", "No emulated preset to delete.")
            return
        label = stem.get("preset_label") or stem.get("preset_id")
        if not messagebox.askyesno("Delete emulated preset", f"Delete '{label}'?"):
            return
        delete_user_preset(stem["preset_id"])
        entry = {
            **stem,
            "preset_id": None,
            "preset_label": "",
            "built": False,
        }
        manifest = update_manifest_stem(self.library_dir, stem.get("stem"), entry)
        self._import_manifest = manifest
        self._import_stems = list(manifest.get("stems") or [])
        self._editing_emulated_preset_id = None
        self._refresh_import_stems_list()
        idx = self.import_stems_list.curselection()
        if idx:
            self._on_import_stem_select()
        self.lbl_import_status.config(text="Emulated preset deleted.")
        self._rebuild_mix_track_rows()
        self._on_param_change()

    def _add_imported_stem_as_track(self):
        stem = self._selected_import_stem()
        if not stem:
            messagebox.showinfo("Import", "Select a stem first.")
            return
        if not stem.get("built") or not stem.get("preset_id"):
            messagebox.showerror(
                "Import",
                "Fit emulated sound before adding to the mix.",
            )
            return
        preset_id = stem.get("preset_id")

        current = self._collect_mix_tracks()
        if len(current) >= MAX_MIX_TRACKS:
            messagebox.showinfo("Mix tracks", f"Maximum {MAX_MIX_TRACKS} tracks.")
            return

        preset = get_preset(preset_id)
        name = suggest_track_name(current, preset.get("label", "Emulated"))
        mode = "follow_melody"
        stem_key = stem.get("stem", "").lower()
        if stem_key in ("drums", "drum"):
            mode = "drums"
        elif stem_key == "bass":
            mode = "bass_root"
        elif stem_key in ("chords", "piano", "other", "guitar"):
            mode = "follow_chords"

        current.append(
            make_track(
                name=name,
                preset=preset_id,
                mode=mode,
                seed=self._current_seed(),
                volume=0.85,
            )
        )
        self._mix_tracks = current
        self._rebuild_mix_track_rows()
        engine = preset.get("engine", "va_voice")
        if mode == "drums":
            self.lbl_import_status.config(
                text=f"Added drum track '{name}' — {preset.get('label', preset_id)} (emulated kit)"
            )
        else:
            self.lbl_import_status.config(
                text=f"Added mix track '{name}' — {preset.get('label', preset_id)} (synth)"
            )
        self._on_param_change()

    def _build_mix_tracks_section(self, parent):
        frame = tk.LabelFrame(parent, text="Mix tracks", fg="#a6adc8", bg="#1e1e2e")
        frame.pack(fill="x", padx=12, pady=8)

        tk.Label(
            frame,
            text="Default 4 tracks + Add for layers (Pan Flute 01, guitars, etc.). Volume, mute, delete per row.",
            fg="#585b70",
            bg="#1e1e2e",
            font=("Segoe UI", 8),
            wraplength=820,
            justify="left",
        ).pack(fill="x", padx=10, pady=(8, 4))

        self._tracks_container = tk.Frame(frame, bg="#1e1e2e")
        self._tracks_container.pack(fill="x", padx=6, pady=4)

        btn_row = tk.Frame(frame, bg="#1e1e2e")
        btn_row.pack(fill="x", padx=8, pady=8)
        tk.Button(
            btn_row,
            text="+ Add track",
            command=self._add_mix_track,
            bg="#45475a",
            fg="#cdd6f4",
            relief="flat",
            padx=12,
            pady=6,
        ).pack(side="left", padx=4)

        self._rebuild_mix_track_rows()

    def _collect_mix_tracks(self) -> list:
        tracks = []
        for row in self._track_row_frames:
            try:
                vol = float(row["vol_var"].get())
            except (tk.TclError, ValueError):
                vol = 1.0
            try:
                seed = int(row["seed_var"].get())
            except (tk.TclError, ValueError):
                seed = 0
            mode_label = row["mode_var"].get()
            mode = next((k for k, v in TRACK_MODES.items() if v == mode_label), "follow_melody")
            preset_label = row["preset_var"].get()
            preset = preset_id_from_label_for_mode(mode, preset_label)
            tracks.append(
                make_track(
                    name=row["name_var"].get().strip() or "Track",
                    preset=preset,
                    mode=mode,
                    seed=max(0, min(SEED_MAX, seed)),
                    volume=max(0.0, min(1.0, vol)),
                    mute=bool(row["mute_var"].get()),
                    track_id=row["track_id"],
                )
            )
        return tracks if tracks else default_mix_tracks()

    def _rebuild_mix_track_rows(self):
        for row in self._track_row_frames:
            row["frame"].destroy()
        self._track_row_frames = []

        for track in self._mix_tracks:
            self._add_mix_track_row(track)

    def _add_mix_track_row(self, track: dict):
        row_frame = tk.Frame(self._tracks_container, bg="#313244", pady=4)
        row_frame.pack(fill="x", padx=4, pady=3)

        name_var = tk.StringVar(value=track.get("name", "Track"))
        preset_var = tk.StringVar(value=label_from_preset_id(track.get("preset", "sine_lead")))
        mode_key = track.get("mode", "follow_melody")
        mode_var = tk.StringVar(value=TRACK_MODES.get(mode_key, TRACK_MODES["follow_melody"]))
        vol_var = tk.DoubleVar(value=float(track.get("volume", 1.0)))
        seed_var = tk.IntVar(value=int(track.get("seed", 0)))
        mute_var = tk.BooleanVar(value=bool(track.get("mute", False)))
        track_id = track.get("id")

        r1 = tk.Frame(row_frame, bg="#313244")
        r1.pack(fill="x", padx=6, pady=4)
        tk.Entry(r1, textvariable=name_var, width=16, bg="#45475a", fg="#cdd6f4").pack(
            side="left", padx=2
        )

        mode_combo = ttk.Combobox(
            r1,
            textvariable=mode_var,
            values=list(TRACK_MODES.values()),
            state="readonly",
            width=16,
        )
        mode_combo.pack(side="left", padx=2)

        def refresh_presets(_e=None):
            mode_lbl = mode_var.get()
            mode_k = next((k for k, v in TRACK_MODES.items() if v == mode_lbl), "follow_melody")
            labels = [p["label"] for p in list_presets_for_mode(mode_k)]
            preset_combo["values"] = labels
            if preset_var.get() not in labels and labels:
                preset_var.set(labels[0])

        preset_combo = ttk.Combobox(
            r1, textvariable=preset_var, state="readonly", width=22
        )
        refresh_presets()
        preset_combo.pack(side="left", padx=2)
        mode_combo.bind("<<ComboboxSelected>>", refresh_presets)

        r2 = tk.Frame(row_frame, bg="#313244")
        r2.pack(fill="x", padx=6, pady=(0, 4))
        tk.Label(r2, text="Vol", fg="#a6adc8", bg="#313244", width=3).pack(side="left")
        vol_lbl = tk.Label(r2, text=f"{vol_var.get():.0%}", fg="#89b4fa", bg="#313244", width=5)

        def on_vol(v):
            vol_lbl.config(text=f"{float(v):.0%}")
            self._on_param_change()

        ttk.Scale(r2, from_=0.0, to=1.0, variable=vol_var, command=on_vol).pack(
            side="left", fill="x", expand=True, padx=4
        )
        vol_lbl.pack(side="left")

        tk.Label(r2, text="Seed", fg="#a6adc8", bg="#313244").pack(side="left", padx=(8, 2))
        tk.Spinbox(
            r2,
            from_=0,
            to=SEED_MAX,
            textvariable=seed_var,
            width=8,
            bg="#45475a",
            fg="#cdd6f4",
            buttonbackground="#585b70",
        ).pack(side="left", padx=2)

        tk.Checkbutton(
            r2,
            text="Mute",
            variable=mute_var,
            command=self._on_param_change,
            fg="#a6adc8",
            bg="#313244",
            selectcolor="#45475a",
        ).pack(side="left", padx=6)

        def delete_track():
            self._mix_tracks = [t for t in self._collect_mix_tracks() if t["id"] != track_id]
            self._rebuild_mix_track_rows()
            self._on_param_change()

        tk.Button(
            r2,
            text="Delete",
            command=delete_track,
            bg="#585b70",
            fg="#cdd6f4",
            relief="flat",
            padx=8,
        ).pack(side="right", padx=2)

        for var in (name_var, preset_var, mode_var, seed_var):
            var.trace_add("write", lambda *_: self._on_param_change())

        self._track_row_frames.append(
            {
                "frame": row_frame,
                "track_id": track_id,
                "name_var": name_var,
                "preset_var": preset_var,
                "mode_var": mode_var,
                "vol_var": vol_var,
                "seed_var": seed_var,
                "mute_var": mute_var,
            }
        )

    def _add_mix_track(self):
        current = self._collect_mix_tracks()
        if len(current) >= MAX_MIX_TRACKS:
            messagebox.showinfo("Mix tracks", f"Maximum {MAX_MIX_TRACKS} tracks.")
            return
        preset = "pan_flute"
        label = label_from_preset_id(preset)
        name = suggest_track_name(label, [t["name"] for t in current])
        current.append(
            make_track(
                name,
                preset,
                "follow_melody",
                seed=random.randint(0, SEED_MAX),
                volume=0.55,
            )
        )
        self._mix_tracks = current
        self._rebuild_mix_track_rows()
        self._on_param_change()

    def _mix_tracks_payload(self) -> list:
        return tracks_to_save(self._collect_mix_tracks())

    def _drum_track_seed(self) -> int:
        for track in self._collect_mix_tracks():
            if track.get("mode") == "drums":
                return int(track.get("seed", 0))
        return self._current_seed()

    def _build_arrange_section(self, parent):
        frame = tk.LabelFrame(parent, text="Arrangement Studio", fg="#a6adc8", bg="#1e1e2e")
        frame.pack(fill="x", padx=12, pady=8)

        tk.Label(
            frame,
            text=(
                "Build the 6-hour master loop on a horizontal timeline — drag clips, session grid, "
                "transport bar, and track lanes (Ableton / After Effects style)."
            ),
            fg="#585b70",
            bg="#1e1e2e",
            font=("Segoe UI", 8),
            wraplength=820,
            justify="left",
        ).pack(fill="x", padx=10, pady=(8, 4))

        self.lbl_arr_total = tk.Label(
            frame,
            text="Timeline: 0:00.00 / 6:00:00 target",
            fg="#89b4fa",
            bg="#1e1e2e",
            font=("Segoe UI", 11),
        )
        self.lbl_arr_total.pack(fill="x", padx=10, pady=4)

        tk.Button(
            frame,
            text="Open Arrangement Studio",
            command=self._open_arrangement_studio,
            bg="#585b70",
            fg="#cdd6f4",
            relief="flat",
            padx=16,
            pady=10,
        ).pack(padx=10, pady=(4, 10))

    def _open_arrangement_studio(self):
        from arrangement_daw import ArrangementWindow, ensure_qt_app

        ensure_qt_app()
        if self._arr_window is None:
            self._arr_window = ArrangementWindow(self.library_dir, app_base_dir())
        else:
            self._arr_window.model.load()
            self._arr_window._refresh_all()
        self._arr_window.show()
        self._arr_window.raise_()
        try:
            self._arr_window.activateWindow()
        except Exception:
            pass
        if not self._qt_poll_job:
            self._poll_qt_events()

    def _poll_qt_events(self):
        try:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app:
                app.processEvents()
        except ImportError:
            pass
        if self._arr_window is not None and self._arr_window.isVisible():
            self._qt_poll_job = self.root.after(20, self._poll_qt_events)
        else:
            self._qt_poll_job = None
            self._load_arrangement_from_disk()
            self._refresh_arrangement_summary()

    def _refresh_arrangement_summary(self):
        total = arrangement_duration_sec(self._arrangement)
        self.lbl_arr_total.config(
            text=(
                f"Timeline: {format_duration(total)} / {format_duration(SIX_HOUR_SEC)} target "
                f"({100 * total / SIX_HOUR_SEC:.1f}% of 6h block) — {len(self._arrangement)} clip(s)"
            )
        )

    def _slider_row(self, parent, label, var, lo, hi, fmt, triggers_preview=True):
        row = tk.Frame(parent, bg="#1e1e2e")
        row.pack(fill="x", padx=12, pady=3)
        tk.Label(row, text=label, fg="#a6adc8", bg="#1e1e2e", width=28, anchor="w").pack(side="left")
        val_lbl = tk.Label(row, text=fmt % var.get(), fg="#89b4fa", bg="#1e1e2e", width=8)

        def on_change(v):
            val_lbl.config(text=fmt % (int(float(v)) if "%d" in fmt else float(v)))
            if triggers_preview:
                self._on_param_change()
            else:
                self._update_instant_visuals()

        ttk.Scale(row, from_=lo, to=hi, variable=var, command=on_change).pack(
            side="left", fill="x", expand=True, padx=8
        )
        val_lbl.pack(side="right")

    def _wire_param_traces(self):
        for var in (
            self.var_bpm,
            self.var_swing,
            self.var_sidechain,
            self.var_density,
            self.var_reverb,
        ):
            var.trace_add("write", lambda *_: self._on_param_change())
        self.var_target_sec.trace_add("write", lambda *_: self._update_instant_visuals())

    def _on_param_change(self):
        self._update_instant_visuals()
        if not self._preview_session_armed:
            self._schedule_live_preview()
        if self._preview_session_armed:
            self._schedule_audio_restart()

    def _schedule_live_preview(self):
        if self._debounce_job:
            self.root.after_cancel(self._debounce_job)
        self.lbl_live_status.config(text="Live preview: updating…")
        self._debounce_job = self.root.after(DEBOUNCE_MS, self._run_live_preview)

    def _schedule_audio_restart(self):
        if self._audio_restart_job:
            self.root.after_cancel(self._audio_restart_job)
        self.lbl_live_status.config(text="Preview: restarting audio…")
        self._audio_restart_job = self.root.after(AUDIO_DEBOUNCE_MS, self._restart_preview_audio)

    def _update_instant_visuals(self):
        p = self._params()
        seed = self._current_seed()
        profile = THEME_PROFILES.get(p["theme_id"], {})
        prog = profile.get("progression", [{}])[0]
        chord_name = prog.get("root_midi", "?")
        self.lbl_theme_hint.config(
            text=(
                f"Theme: {profile.get('label', p['theme_id'])}  |  "
                f"1st chord root MIDI {chord_name}  |  density {p['melody_density']}%  |  seed {seed}"
            )
        )
        melody = generate_melody_steps(p["theme_id"], p["melody_density"], seed=seed)
        self._update_melody_map(melody)
        self._last_drums = generate_drum_pattern(seed=self._drum_track_seed())
        self._redraw_gen_groove()
        measures = self.var_measures.get()
        target = self.var_target_sec.get()
        save_measures = self._measures_for_target(p["bpm"], target)
        self.lbl_duration.config(
            text=(
                f"Preview: {measures} meas  |  Save target: ~{save_measures} meas / ~{target}s @ {p['bpm']} BPM"
            )
        )

    def _redraw_gen_stems(self):
        if self._last_stems:
            self.gen_stems.draw_stems(self._last_stems, label="Per-stem preview (1 measure)")

    def _redraw_gen_groove(self):
        p = self._params()
        step_dur = (60.0 / p["bpm"]) / 4.0
        times = step_times_visual(p["bpm"], p["swing"])
        self.gen_groove.draw(
            p["bpm"],
            p["swing"],
            self._last_drums or generate_drum_pattern(seed=self._drum_track_seed()),
            step_times=times,
            measure_dur=step_dur * 16,
        )

    def _run_live_preview(self):
        self._debounce_job = None
        if self._live_preview_busy:
            self._schedule_live_preview()
            return
        self._live_preview_busy = True
        p = self._params()
        seed = self._current_seed()
        self._last_seed = seed
        try:
            buf, drums, melody, stems = synthesize_measure(
                **p, seed=seed, return_stems=True, mix_tracks=self._mix_tracks_payload()
            )
            self._last_drums = drums
            self._last_stems = stems or {}
            self._show_gen_waveform(buf, label="Live preview (1 measure)")
            if stems:
                self.gen_stems.draw_stems(stems, label="Per-stem preview (1 measure)")
            self._update_melody_map(melody)
            self._redraw_gen_groove()
            sec = buffer_duration_sec(buf)
            self.lbl_duration.config(
                text=(
                    f"Live measure: {sec:.2f} s @ {p['bpm']} BPM  |  "
                    f"Save target: ~{self._measures_for_target(p['bpm'], self.var_target_sec.get())} meas"
                )
            )
            self.lbl_seed_info.config(text=f"Active seed: {seed}")
            self.lbl_live_status.config(text="Live preview: up to date")
        except Exception as exc:
            self.lbl_live_status.config(text=f"Live preview error: {exc}")
        finally:
            self._live_preview_busy = False

    def _redraw_gen_waveform(self):
        if self._last_buffer is not None:
            self.gen_waveform.draw_buffer(self._last_buffer, label="Current preview")
            self._render_playhead()

    def _redraw_arr_waveform(self):
        if self._arrangement:
            try:
                master = concat_wavs(self._arrangement)
                self.arr_waveform.draw_buffer(
                    master,
                    label=f"Full arrangement ({format_duration(len(master)/SAMPLE_RATE)})",
                )
            except OSError:
                pass

    def _show_gen_waveform(self, buffer, label: str = "Current preview"):
        self._last_buffer = buffer
        self._play_duration = len(buffer) / SAMPLE_RATE if len(buffer) else 0.0
        self.gen_waveform.draw_buffer(buffer, label=label)
        self._render_playhead()

    def _randomize_seed(self):
        self.var_seed.set(random.randint(0, SEED_MAX))

    def _bump_seed(self):
        self.var_seed.set((self.var_seed.get() + 1) % (SEED_MAX + 1))

    def _current_seed(self) -> int:
        try:
            value = int(self.var_seed.get())
        except (tk.TclError, ValueError):
            value = 0
        return max(0, min(SEED_MAX, value))

    def _maybe_advance_seed(self):
        if self.var_auto_advance_seed.get():
            self._bump_seed()

    def _params(self):
        return {
            "theme_id": self.var_theme.get(),
            "bpm": self.var_bpm.get(),
            "swing": self.var_swing.get(),
            "sidechain_depth": self.var_sidechain.get(),
            "melody_density": self.var_density.get(),
            "reverb_decay": self.var_reverb.get(),
        }

    def _update_melody_map(self, steps):
        self._last_melody = steps
        for i, lbl in enumerate(self._melody_labels):
            if steps[i] is None:
                lbl.config(text=".", bg="#313244", fg="#6c7086")
            else:
                lbl.config(text=str(steps[i] % 12), bg="#a6e3a1", fg="#1e1e2e")

    def _update_duration_labels(self, buffer):
        sec = buffer_duration_sec(buffer)
        frames = int(sec * 30)
        target = self.var_target_sec.get()
        ok = abs(sec - target) <= max(5, target * 0.15) if target else True
        hint = "OK" if ok else f"Drift vs target {target}s"
        self.lbl_duration.config(
            text=f"Duration: {sec:.2f} s  [{hint}]  Sample rate: {SAMPLE_RATE} Hz"
        )
        self.lbl_frames.config(text=f"Frames @ 30 FPS: {frames}")

    def _test_one_measure(self):
        p = self._params()
        seed = self._current_seed()
        self._last_seed = seed
        buf, _, melody, stems = synthesize_measure(
            **p, seed=seed, return_stems=True, mix_tracks=self._mix_tracks_payload()
        )
        self._last_stems = stems or {}
        self._show_gen_waveform(buf)
        if stems:
            self.gen_stems.draw_stems(stems, label="Per-stem preview (1 measure)")
        self._update_melody_map(melody)
        self._update_duration_labels(buf)
        self.lbl_seed_info.config(text=f"Active seed: {seed}")
        self._start_preview_playback(buf, loop=False, resume=False)
        self._maybe_advance_seed()

    def _synth_preview_buffer(self):
        p = self._params()
        n = self.var_measures.get()
        seed = self._current_seed()
        return synthesize_track(
            **p, num_measures=n, seed=seed, mix_tracks=self._mix_tracks_payload()
        ), p, seed

    def _apply_preview_buffer(self, buf, p, seed):
        self._last_seed = seed
        self._show_gen_waveform(buf, label=f"Preview loop ({self.var_measures.get()} measures)")
        melody = generate_melody_steps(p["theme_id"], p["melody_density"], seed=seed)
        self._update_melody_map(melody)
        self._update_duration_labels(buf)
        self.lbl_seed_info.config(text=f"Active seed: {seed}")

    def _start_preview_playback(self, buffer, loop: bool = None, resume: bool = False):
        if loop is None:
            loop = bool(self.var_loop_preview.get())
        duration = len(buffer) / SAMPLE_RATE if len(buffer) else 0.0

        if resume:
            self._sync_playback_clock()
            self._stop_audio()
        else:
            self._stop_playback()

        self._loop_playhead = loop
        self._play_duration = duration
        self._playhead_active = True
        if not resume:
            self._playhead_ratio = 0.0
            self._playback_clock_last = time.time()
        self._start_playhead_clock()
        self._render_playhead()

        if duration <= 0:
            return

        start_sec = self._playhead_ratio * duration
        if not loop:
            start_sec = min(start_sec, duration)

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        save_wav(tmp.name, buffer)
        self._play_buffer_audio(buffer, tmp.name, loop=loop, start_sec=start_sec)

    def _preview_loop(self):
        self._preview_session_armed = True
        buf, p, seed = self._synth_preview_buffer()
        self._apply_preview_buffer(buf, p, seed)
        self._start_preview_playback(buf, resume=False)
        self.lbl_live_status.config(
            text=f"Preview armed — playing {self.var_measures.get()} measures"
        )
        self._maybe_advance_seed()

    def _restart_preview_audio(self):
        self._audio_restart_job = None
        if not self._preview_session_armed:
            return
        if self._synth_thread_busy:
            self._schedule_audio_restart()
            return
        self._sync_playback_clock()
        self._stop_audio()
        self._playhead_active = True
        self._start_playhead_clock()
        self._synth_thread_busy = True

        def run():
            try:
                buf, p, seed = self._synth_preview_buffer()
            except Exception as exc:
                self.root.after(
                    0,
                    lambda: self.lbl_live_status.config(text=f"Preview restart error: {exc}"),
                )
                self.root.after(0, self._finish_synth_thread)
                return

            def on_done():
                if not self._preview_session_armed:
                    self._finish_synth_thread()
                    return
                self._apply_preview_buffer(buf, p, seed)
                self._start_preview_playback(buf, resume=True)
                self.lbl_live_status.config(
                    text=f"Preview playing ({self.var_measures.get()} measures)"
                )
                self._finish_synth_thread()

            self.root.after(0, on_done)

        threading.Thread(target=run, daemon=True).start()

    def _finish_synth_thread(self):
        self._synth_thread_busy = False

    def _measures_for_target(self, bpm: float, target_sec: float) -> int:
        measure_sec = (60.0 / bpm) * 4
        return max(4, int(round(target_sec / measure_sec)))

    def _save_track(self):
        p = self._params()
        target = self.var_target_sec.get()
        n = self._measures_for_target(p["bpm"], target)
        seed = self._current_seed()
        buf = synthesize_track(
            **p, num_measures=n, seed=seed, mix_tracks=self._mix_tracks_payload()
        )
        self._show_gen_waveform(buf)
        self._update_duration_labels(buf)
        self.lbl_seed_info.config(text=f"Saved with seed: {seed}")

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"{p['theme_id']}_{p['bpm']}bpm_seed{seed}_{stamp}"
        wav_path = os.path.join(self.library_dir, base + ".wav")
        save_wav(wav_path, buf)

        meta = {
            "title": base.replace("_", " ").title(),
            "artist": "Mall Music Studio",
            "theme": p["theme_id"],
            "bpm": p["bpm"],
            "seed": seed,
            "swing": p["swing"],
            "sidechain_depth": p["sidechain_depth"],
            "melody_density": p["melody_density"],
            "reverb_decay": p["reverb_decay"],
            "mix_tracks": self._mix_tracks_payload(),
            "duration_sec": round(buffer_duration_sec(buf), 3),
            "wav_file": wav_path,
        }
        with open(os.path.join(self.library_dir, base + ".json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        messagebox.showinfo("Saved", f"Track saved:\n{wav_path}")
        self._refresh_library()

    def _refresh_library(self):
        self._library_metas = load_library_metas(self.library_dir)
        self.library_list.delete(0, tk.END)
        total = 0.0
        for meta in self._library_metas:
            dur = float(meta.get("duration_sec", 0))
            total += dur
            seed_tag = f" seed={meta['seed']}" if "seed" in meta else ""
            line = f"{meta.get('title', '?')}  ({dur:.1f}s)  [{meta.get('theme')}]{seed_tag}"
            self.library_list.insert(tk.END, line)
        self.lbl_library_total.config(
            text=f"Library total: {total:.1f} s ({total/3600:.2f} h) — target 6h = {SIX_HOUR_SEC}s"
        )
        self._refresh_arrangement_summary()

    def _on_library_select(self):
        idx = self.library_list.curselection()
        if not idx:
            return
        meta = self._library_metas[idx[0]]
        wav = meta.get("wav_file")
        if wav:
            self.gen_waveform.draw_file(wav, label=meta.get("title", ""))

    def _preview_library_item(self):
        idx = self.library_list.curselection()
        if not idx:
            return
        meta = self._library_metas[idx[0]]
        wav = meta.get("wav_file")
        if wav and os.path.exists(wav):
            self.gen_waveform.draw_file(wav, label=meta.get("title", ""))
            self._play_file(wav, waveform=self.gen_waveform)

    def _load_arrangement_from_disk(self):
        raw = load_playlist(self.library_dir)
        self._arrangement = resolve_playlist_entries(self.library_dir, raw)
        self._refresh_arrangement_summary()

    def _redraw_arr_waveform(self):
        pass

    def _sync_playback_clock(self):
        now = time.time()
        if self._playback_clock_last > 0 and self._play_duration > 0:
            delta_ratio = (now - self._playback_clock_last) / self._play_duration
            if self._loop_playhead:
                self._playhead_ratio = (self._playhead_ratio + delta_ratio) % 1.0
            else:
                self._playhead_ratio = min(1.0, self._playhead_ratio + delta_ratio)
        self._playback_clock_last = now

    def _playback_ratio(self) -> float:
        return self._playhead_ratio

    def _render_playhead(self):
        wf = self._playhead_waveform or self.gen_waveform
        wf.set_playhead_ratio(self._playhead_ratio)
        if wf is self.import_stem_waveform and self._import_stem_duration > 0:
            self.var_import_stem_pos.set(self._playhead_ratio)
            self.lbl_import_stem_pos.config(
                text=self._format_preview_time(self._playhead_ratio * self._import_stem_duration)
            )

    def _start_playhead_clock(self):
        if self._playhead_job is None and self._playhead_active:
            self._playback_clock_last = time.time()
            self._tick_playhead()

    def _stop_playhead_clock(self):
        if self._playhead_job:
            self.root.after_cancel(self._playhead_job)
            self._playhead_job = None

    def _stop_audio(self):
        if self._playback_proc and self._playback_proc.poll() is None:
            self._playback_proc.terminate()
            self._playback_proc = None
        try:
            import pygame

            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.stop()
        except ImportError:
            pass
        except Exception:
            pass

    def _stop_playback(self):
        self._playhead_active = False
        self._stop_playhead_clock()
        self._stop_audio()
        self._playhead_ratio = 0.0
        self._playback_clock_last = 0.0
        self._loop_playhead = False
        self._play_duration = 0.0

    def _stop_preview(self):
        self._preview_session_armed = False
        if self._audio_restart_job:
            self.root.after_cancel(self._audio_restart_job)
            self._audio_restart_job = None
        self._stop_playback()
        self.lbl_live_status.config(text="Preview stopped")

    def _tick_playhead(self):
        if not self._playhead_active or self._play_duration <= 0:
            return
        self._sync_playback_clock()
        if not self._loop_playhead and self._playhead_ratio >= 1.0:
            self._render_playhead()
            self._playhead_active = False
            self._playhead_job = None
            return
        self._render_playhead()
        self._playhead_job = self.root.after(50, self._tick_playhead)

    def _play_buffer(self, buffer):
        self._start_preview_playback(buffer, loop=False, resume=False)

    def _play_buffer_audio(self, buffer, path: str, loop: bool, start_sec: float):
        def run():
            start_sample = int(start_sec * SAMPLE_RATE)
            start_sample = max(0, min(start_sample, max(0, len(buffer) - 1)))

            try:
                import pygame

                pygame.mixer.init(frequency=SAMPLE_RATE)

                def play_sound_segment(segment, suffix: str):
                    if len(segment) == 0:
                        return
                    seg_path = path + suffix
                    save_wav(seg_path, segment)
                    sound = pygame.mixer.Sound(seg_path)
                    channel = sound.play()
                    while channel and channel.get_busy():
                        time.sleep(0.05)

                if loop and start_sample > 0:
                    play_sound_segment(buffer[start_sample:], ".tail.wav")
                    pygame.mixer.music.load(path)
                    pygame.mixer.music.play(-1)
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.05)
                elif loop:
                    pygame.mixer.music.load(path)
                    pygame.mixer.music.play(-1)
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.05)
                elif start_sample > 0:
                    play_sound_segment(buffer[start_sample:], ".seg.wav")
                else:
                    pygame.mixer.music.load(path)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.05)
            except ImportError:
                if loop and start_sample > 0:
                    tail_path = path + ".tail.wav"
                    save_wav(tail_path, buffer[start_sample:])
                    for cmd in (
                        ["ffplay", "-nodisp", "-autoexit", tail_path],
                        ["ffplay", "-nodisp", "-loop", "0", path],
                    ):
                        try:
                            self._playback_proc = subprocess.Popen(
                                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                            )
                            self._playback_proc.wait()
                        except (FileNotFoundError, OSError):
                            break
                elif loop:
                    cmd = ["ffplay", "-nodisp", "-loop", "0", path]
                    try:
                        self._playback_proc = subprocess.Popen(
                            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                        self._playback_proc.wait()
                    except (FileNotFoundError, OSError):
                        pass
                else:
                    if start_sample > 0:
                        seg_path = path + ".seg.wav"
                        save_wav(seg_path, buffer[start_sample:])
                        play_path = seg_path
                    else:
                        play_path = path
                    for attempt in (
                        ["ffplay", "-nodisp", "-autoexit", play_path],
                        ["powershell", "-c", f'(New-Object Media.SoundPlayer "{play_path}").PlaySync()'],
                    ):
                        try:
                            self._playback_proc = subprocess.Popen(
                                attempt, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                            )
                            self._playback_proc.wait()
                            return
                        except (FileNotFoundError, OSError):
                            continue

        threading.Thread(target=run, daemon=True).start()

    def _play_file(
        self,
        path: str,
        duration: float = 0.0,
        waveform: WaveformCanvas = None,
        loop: bool = False,
        start_sec: float = 0.0,
    ):
        self._stop_playback()
        if duration <= 0:
            try:
                from waveform_utils import load_wav_mono

                duration = len(load_wav_mono(path)) / SAMPLE_RATE
            except OSError:
                duration = 0.0
        self._playhead_waveform = waveform or self.gen_waveform
        self._play_duration = duration
        self._loop_playhead = loop
        start_sec = max(0.0, min(start_sec, max(0.0, duration - 0.01)))
        self._playhead_ratio = (start_sec / duration) if duration > 0 else 0.0
        self._playhead_active = duration > 0
        self._playback_clock_last = time.time()
        if duration > 0:
            self._start_playhead_clock()
            self._playhead_waveform.set_playhead_ratio(self._playhead_ratio)

        def run():
            try:
                import pygame

                from waveform_utils import load_wav_mono

                pygame.mixer.init(frequency=SAMPLE_RATE)
                data = load_wav_mono(path)
                start_sample = int(start_sec * SAMPLE_RATE)
                start_sample = max(0, min(start_sample, max(0, len(data) - 1)))
                segment = data[start_sample:]

                def play_segment(seg, suffix: str):
                    if len(seg) == 0:
                        return
                    seg_path = path + suffix
                    save_wav(seg_path, seg)
                    sound = pygame.mixer.Sound(seg_path)
                    channel = sound.play()
                    while channel and channel.get_busy():
                        time.sleep(0.05)

                if loop and start_sample > 0:
                    play_segment(segment, ".tail.wav")
                    pygame.mixer.music.load(path)
                    pygame.mixer.music.play(-1)
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.05)
                elif loop:
                    pygame.mixer.music.load(path)
                    pygame.mixer.music.play(-1)
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.05)
                elif start_sample > 0:
                    play_segment(segment, ".seg.wav")
                else:
                    pygame.mixer.music.load(path)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.05)
            except ImportError:
                play_path = path
                if start_sec > 0:
                    try:
                        from waveform_utils import load_wav_mono

                        data = load_wav_mono(path)
                        start_sample = int(start_sec * SAMPLE_RATE)
                        seg_path = path + ".seg.wav"
                        save_wav(seg_path, data[start_sample:])
                        play_path = seg_path
                    except OSError:
                        play_path = path
                if loop:
                    cmd = ["ffplay", "-nodisp", "-loop", "0", play_path]
                else:
                    cmd = ["ffplay", "-nodisp", "-autoexit", play_path]
                for attempt in (
                    cmd,
                    ["powershell", "-c", f'(New-Object Media.SoundPlayer "{play_path}").PlaySync()'],
                ):
                    try:
                        self._playback_proc = subprocess.Popen(
                            attempt, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                        self._playback_proc.wait()
                        return
                    except (FileNotFoundError, OSError):
                        continue
            finally:
                if not loop:
                    self.root.after(0, lambda: setattr(self, "_playhead_active", False))

        threading.Thread(target=run, daemon=True).start()


def main():
    root = tk.Tk()
    MallMusicStudioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
