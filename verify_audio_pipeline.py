"""Validates master audio loop sync against the Python tracklist."""

import os
import sys

from mutagen.mp3 import MP3

from config import FRAME_RATE, TRACKLIST


def verify_master_audio_pipeline():
    print("=== RUNNING STREAM AUDIO INTEGRITY CHECKS ===")

    master_file = "lofi_music.mp3"
    if not os.path.exists(master_file):
        print(f"[CRITICAL ERROR] '{master_file}' not found. Add your compiled master loop first.")
        sys.exit(1)

    try:
        audio = MP3(master_file)
        actual_duration = audio.info.length
        sample_rate = audio.info.sample_rate
    except Exception as exc:
        print(f"[CRITICAL ERROR] Failed to parse MP3: {exc}")
        sys.exit(1)

    if sample_rate != 44100:
        print(f"[WARNING] Sample rate is {sample_rate}Hz instead of 44100Hz.")
    else:
        print("[OK] Sample Rate Validated: 44,100 Hz")

    calculated_duration = sum(track["duration_sec"] for track in TRACKLIST)
    calculated_total_frames = sum(
        round(track["duration_sec"] * FRAME_RATE) for track in TRACKLIST
    )
    drift_seconds = abs(actual_duration - calculated_duration)
    drift_frames = drift_seconds * FRAME_RATE

    print("\n--- MATRIX DATA MATCH ANALYSIS ---")
    print(f"Master File Real Duration: {actual_duration:.3f} seconds")
    print(f"Python Array Total Time:   {calculated_duration:.3f} seconds")
    print(f"Total Sequence Video Frames: {calculated_total_frames} frames")

    if drift_frames > 15:
        print("\n[CRITICAL SYNC ERROR DETECTED]")
        print(
            f"[WARN] Text tracker drifts from audio by {drift_seconds:.3f}s ({drift_frames:.1f} frames)."
        )
        sys.exit(1)

    print(f"[OK] Timeline Sync Confirmed: drift is negligible ({drift_frames:.2f} frames).")
    print("\n=== SYSTEM BROADCAST READY FOR LAUNCH ===")


if __name__ == "__main__":
    verify_master_audio_pipeline()
