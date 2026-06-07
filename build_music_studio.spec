# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

ROOT = os.path.dirname(os.path.abspath(SPEC))

pyside_datas, pyside_binaries, pyside_hidden = collect_all("PySide6")

a = Analysis(
    ['music_tuner_ui.py'],
    pathex=[ROOT],
    binaries=pyside_binaries,
    datas=pyside_datas,
    hiddenimports=[
        'numpy',
        'pygame',
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'arrangement_daw',
        'arrangement_daw.arrangement_model',
        'arrangement_daw.arrangement_window',
        'arrangement_daw.timeline_view',
        'arrangement_daw.session_view',
        'arrangement_daw.transport_bar',
        'arrangement_daw.track_lanes',
        'arrangement_daw.audio_transport',
        'waveform_utils',
        'playlist_arranger',
        'instrument_presets',
        'voice_engine',
        'drum_engine',
        'sample_engine',
        'licensed_library',
        'midi_pattern',
        'mix_tracks',
        'track_renderer',
        'import_pipeline',
        'audio_synthesizer',
        'melody_generator',
        'music_theory',
        'tools.sound_profiler',
        'tools.import_worker',
        'tools.youtube_import',
        'tools.stem_separator',
    ] + pyside_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['scipy', 'matplotlib', 'pandas'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MallMusicStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
