"""Audio playback for arrangement preview (pygame)."""

from __future__ import annotations

import os
import tempfile
import threading
import time
from typing import Callable, Optional

import numpy as np

from audio_synthesizer import save_wav
from music_theory import SAMPLE_RATE
from playlist_arranger import concat_wavs


class ArrangementAudioTransport:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._playing = False
        self._loop = False
        self._duration = 0.0
        self._start_offset = 0.0
        self._clock_start = 0.0
        self._temp_path = ""
        self.on_position: Optional[Callable[[float], None]] = None
        self.on_finished: Optional[Callable[[], None]] = None

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def duration(self) -> float:
        return self._duration

    def current_sec(self) -> float:
        if not self._playing:
            return self._start_offset
        elapsed = time.time() - self._clock_start
        pos = self._start_offset + elapsed
        if self._loop and self._duration > 0:
            pos = pos % self._duration
        return min(pos, self._duration) if self._duration > 0 else pos

    def stop(self) -> None:
        self._stop_flag.set()
        self._playing = False
        try:
            import pygame

            pygame.mixer.music.stop()
        except (ImportError, pygame.error):
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._thread = None

    def play_tracks(
        self,
        tracks: list,
        loop: bool = False,
        start_sec: float = 0.0,
    ) -> bool:
        self.stop()
        if not tracks:
            return False
        try:
            buffer = concat_wavs(tracks)
        except OSError:
            return False
        if len(buffer) == 0:
            return False
        self._duration = len(buffer) / SAMPLE_RATE
        self._loop = loop
        self._start_offset = max(0.0, min(start_sec, self._duration))
        self._stop_flag.clear()

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        self._temp_path = tmp.name
        save_wav(self._temp_path, buffer)

        self._thread = threading.Thread(
            target=self._run_playback,
            daemon=True,
        )
        self._thread.start()
        return True

    def _run_playback(self) -> None:
        try:
            import pygame

            pygame.mixer.init(frequency=SAMPLE_RATE)
            start_sample = int(self._start_offset * SAMPLE_RATE)
            data = None
            if start_sample > 0:
                from waveform_utils import load_wav_mono

                data = load_wav_mono(self._temp_path)
                segment = data[start_sample:]
                seg_path = self._temp_path + ".seg.wav"
                save_wav(seg_path, segment)
                path = seg_path
            else:
                path = self._temp_path

            self._clock_start = time.time()
            self._playing = True
            loops = -1 if self._loop else 0
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(loops)

            while not self._stop_flag.is_set():
                if not pygame.mixer.music.get_busy() and not self._loop:
                    break
                if self.on_position:
                    self.on_position(self.current_sec())
                time.sleep(0.03)
        except ImportError:
            pass
        finally:
            self._playing = False
            if self.on_finished:
                self.on_finished()

    def seek(self, sec: float, tracks: list, loop: bool) -> None:
        was_playing = self._playing
        self.stop()
        if was_playing:
            self.play_tracks(tracks, loop=loop, start_sec=sec)
