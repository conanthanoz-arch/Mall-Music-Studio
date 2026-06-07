"""Build frame-rounded TRACKLIST entries from music_library/ metadata."""

import json
import os
import sys

FRAME_RATE = 30


def load_library_tracks(library_dir: str = "music_library"):
    tracks = []
    if not os.path.isdir(library_dir):
        return tracks
    for name in sorted(os.listdir(library_dir)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(library_dir, name)
        with open(path, encoding="utf-8") as f:
            meta = json.load(f)
        wav = meta.get("wav_file") or os.path.join(library_dir, name.replace(".json", ".wav"))
        if not os.path.exists(wav):
            print(f"[WARN] Missing WAV for {name}", file=sys.stderr)
            continue
        tracks.append(
            {
                "title": meta.get("title", name),
                "artist": meta.get("artist", "Mall Music Studio"),
                "duration_sec": float(meta.get("duration_sec", 0)),
                "wav_file": wav,
                "theme": meta.get("theme", ""),
            }
        )
    return tracks


def build_tracklist_snippet(tracks, fps: int = FRAME_RATE) -> str:
    lines = ["TRACKLIST = ["]
    for t in tracks:
        lines.append(
            f'    {{"title": {t["title"]!r}, "artist": {t["artist"]!r}, '
            f'"duration_sec": {t["duration_sec"]:.3f}}},'
        )
    lines.append("]")
    total_sec = sum(t["duration_sec"] for t in tracks)
    total_frames = sum(int(t["duration_sec"] * fps) for t in tracks)
    lines.append("")
    lines.append(f"# Total: {total_sec:.1f}s ({total_sec/3600:.2f}h), {total_frames} frames @ {fps} FPS")
    return "\n".join(lines)


def main():
    library = sys.argv[1] if len(sys.argv) > 1 else "music_library"
    tracks = load_library_tracks(library)
    if not tracks:
        print("No tracks in music_library/. Save tracks from Mall Music Studio first.")
        sys.exit(1)
    print(build_tracklist_snippet(tracks))
    total = sum(t["duration_sec"] for t in tracks)
    print(f"\n# {len(tracks)} tracks, {total:.1f}s total", file=sys.stderr)


if __name__ == "__main__":
    main()
