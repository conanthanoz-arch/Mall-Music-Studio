"""Performance benchmark for the compositing engine."""

import multiprocessing
import os
import time

import PIL.Image
import psutil

from scene_compositor import PATROL_START_X, build_frame

try:
    PIL.Image.set_num_threads(multiprocessing.cpu_count())
except AttributeError:
    pass


def run_performance_benchmark():
    print("=== INITIALIZING HARDWARE PERFORMANCE BENCHMARK ===")
    print(f"Detected CPU Threads Available: {multiprocessing.cpu_count()}")

    theme_path = os.path.join("assets", "pixel_art")
    day_asset = os.path.join(theme_path, "mall_structure_day.png")
    if not os.path.exists(day_asset):
        print("[ERROR] Run generate_placeholders.py first to create test PNGs.")
        return

from scene_compositor import PATROL_START_X, build_frame
from theme_manager import ThemeAssetManager


def run_performance_benchmark():
    print("=== INITIALIZING HARDWARE PERFORMANCE BENCHMARK ===")
    print(f"Detected CPU Threads Available: {multiprocessing.cpu_count()}")

    theme_path = os.path.join("assets", "pixel_art")
    day_asset = os.path.join(theme_path, "mall_structure_day.png")
    if not os.path.exists(day_asset):
        print("[ERROR] Run generate_placeholders.py first to create test PNGs.")
        return

    tm = ThemeAssetManager()
    tm.load_theme_into_ram(0)

    test_frames = 1000
    target_frame_time = 1.0 / 30.0
    total_processing_time = 0
    max_frame_time = 0
    min_frame_time = 999.0
    guard_x = PATROL_START_X

    print(f"Processing {test_frames} full 6-layer frames unthrottled...")

    process = psutil.Process(os.getpid())
    start_ram = process.memory_info().rss / (1024 * 1024)

    for frame in range(test_frames):
        frame_start = time.time()
        guard_x = PATROL_START_X + (frame % 1700)
        final_img = build_frame(tm, guard_x, frame, frame, 648000, True)
        final_img.convert("RGB")
        frame_duration = time.time() - frame_start
        total_processing_time += frame_duration
        max_frame_time = max(max_frame_time, frame_duration)
        min_frame_time = min(min_frame_time, frame_duration)

    end_ram = process.memory_info().rss / (1024 * 1024)
    avg_frame_time_ms = (total_processing_time / test_frames) * 1000
    max_frame_time_ms = max_frame_time * 1000
    min_frame_time_ms = min_frame_time * 1000
    theoretical_max_fps = 1.0 / (total_processing_time / test_frames)
    cpu_headroom_percent = (
        1.0 - ((total_processing_time / test_frames) / target_frame_time)
    ) * 100

    print("\n================ BENCHMARK ANALYTICS REPORT ================")
    print(f"Average Frame Render Speed:    {avg_frame_time_ms:.2f} ms")
    print(f"Fastest Spiked Frame:          {min_frame_time_ms:.2f} ms")
    print(f"Slowest Spiked Frame:          {max_frame_time_ms:.2f} ms")
    print(f"RAM Leakage Delta:             {(end_ram - start_ram):.2f} MB")
    print(f"Theoretical Max Frame Capacity: {theoretical_max_fps:.1f} FPS")
    print(f"System CPU Idle Headroom:      {cpu_headroom_percent:.1f} %")
    print("============================================================")

    if avg_frame_time_ms > 33.3:
        print("\n[ALERT] PERFORMANCE ALERT: Rendering slower than 33.3ms per frame.")
    elif cpu_headroom_percent < 25.0:
        print("\n[WARN] Low hardware headroom detected.")
    else:
        print("\n[OK] GREEN STATUS: Broadcast stability profile EXCELLENT.")


if __name__ == "__main__":
    run_performance_benchmark()
