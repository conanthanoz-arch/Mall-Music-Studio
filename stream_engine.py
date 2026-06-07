"""Master RAM-piping stream engine for 24/7 YouTube lo-fi broadcast."""

import csv
import multiprocessing
import os
import sys
import time

import PIL
from PIL import ImageDraw, ImageFont

from config import (
    BLOCK_DURATION_FRAMES,
    FRAME_RATE,
    TOTAL_DAILY_FRAMES,
    TRACKLIST,
)
from scene_compositor import (
    PATROL_END_X,
    PATROL_START_X,
    build_frame,
)
from theme_manager import ThemeAssetManager

try:
    PIL.Image.set_num_threads(multiprocessing.cpu_count())
except AttributeError:
    pass


def build_track_frame_map(tracklist, fps):
    frame_map = []
    current_start = 0
    for track in tracklist:
        duration_frames = int(track["duration_sec"] * fps)
        frame_map.append(
            {
                "title": track["title"],
                "artist": track["artist"],
                "start_frame": current_start,
                "end_frame": current_start + duration_frames,
            }
        )
        current_start += duration_frames
    return frame_map, current_start


TRACK_FRAME_MAP, AUDIO_LOOP_DURATION = build_track_frame_map(TRACKLIST, FRAME_RATE)


def run_preflight_diagnostics():
    from config import THEMES

    for theme in THEMES.values():
        theme_path = os.path.join("assets", theme)
        if not os.path.isdir(theme_path):
            print(f"[CRITICAL ERROR] Missing theme directory: {theme_path}", file=sys.stderr)
            sys.exit(1)

    if not os.path.exists("advertiser_log.csv"):
        with open("advertiser_log.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Storefront_ID",
                    "Brand_Name",
                    "Asset_File",
                    "Start_Date",
                    "End_Date",
                    "Active_Status",
                    "Theme_Style",
                ]
            )

    print("[SUCCESS] All core assets validated. System initialized. Starting infinite loop...", file=sys.stderr)


def load_fonts():
    for font_name in ("Arial.ttf", os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arial.ttf")):
        if os.path.exists(font_name):
            return (
                ImageFont.truetype(font_name, 28),
                ImageFont.truetype(font_name, 20),
                ImageFont.truetype(font_name, 22),
            )
    default = ImageFont.load_default()
    return default, default, default


def get_track_info(frame):
    normalized = frame % AUDIO_LOOP_DURATION
    for track in TRACK_FRAME_MAP:
        if track["start_frame"] <= normalized < track["end_frame"]:
            return track["title"], track["artist"], normalized - track["start_frame"]
    return "Ambient Track", "Mall Collective", 0


def main():
    run_preflight_diagnostics()
    font_title, font_artist, font_dialogue = load_fonts()

    theme_manager = ThemeAssetManager()
    guard_x = PATROL_START_X
    guard_speed = 2
    frame = 0
    target_frame_time = 1.0 / FRAME_RATE

    while True:
        start_time = time.time()

        daily_cycle_frame = frame % TOTAL_DAILY_FRAMES
        current_block_frame = daily_cycle_frame % BLOCK_DURATION_FRAMES
        target_theme_id = daily_cycle_frame // BLOCK_DURATION_FRAMES

        if theme_manager.current_theme_id != target_theme_id:
            theme_manager.load_theme_into_ram(target_theme_id)

        is_open = current_block_frame <= (4 * 60 * 60 * FRAME_RATE)

        guard_x += guard_speed
        if guard_x >= PATROL_END_X:
            guard_x = PATROL_START_X

        final_img = build_frame(
            theme_manager,
            guard_x,
            frame,
            current_block_frame,
            BLOCK_DURATION_FRAMES,
            is_open,
        )

        title, artist, song_frame = get_track_info(frame)
        draw = ImageDraw.Draw(final_img)
        draw.rounded_rectangle([40, 40, 520, 120], radius=8, fill=(0, 0, 0, 140))
        draw.text((60, 50), f"Now Playing: {title}", fill=(255, 255, 255), font=font_title)
        draw.text((60, 85), f"by {artist}", fill=(200, 200, 200), font=font_artist)

        if song_frame < (4 * FRAME_RATE):
            from scene_compositor import GUARD_Y

            draw.rounded_rectangle(
                [guard_x + 20, GUARD_Y - 80, guard_x + 250, GUARD_Y - 30],
                radius=12,
                fill=(255, 255, 255, 230),
            )
            draw.text(
                (guard_x + 35, GUARD_Y - 68),
                "Loving this beat...",
                fill=(20, 20, 20),
                font=font_dialogue,
            )

        try:
            final_img.save(sys.stdout.buffer, "JPEG", quality=85)
        except (BrokenPipeError, IOError):
            break

        elapsed_time = time.time() - start_time
        if elapsed_time < target_frame_time:
            time.sleep(target_frame_time - elapsed_time)

        frame += 1


if __name__ == "__main__":
    main()
