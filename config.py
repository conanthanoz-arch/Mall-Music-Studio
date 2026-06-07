"""Shared configuration for the YoutubeLoopStream engine."""

FRAME_RATE = 30
BLOCK_DURATION_FRAMES = 60 * 60 * 6 * FRAME_RATE  # 6 hours per theme block
TOTAL_DAILY_FRAMES = BLOCK_DURATION_FRAMES * 4  # 24-hour rotation

THEMES = {
    0: "pixel_art",       # 00:00 - 06:00
    1: "anime_vector",    # 06:00 - 12:00
    2: "matte_painting",  # 12:00 - 18:00
    3: "cyberpunk",       # 18:00 - 24:00
}

TRACKLIST = [
    {"title": "Late Night Patrol", "artist": "Lo-Fi Guard Collective", "duration_sec": 180.0},
    {"title": "Neon Escalator Echoes", "artist": "Synth Wave Cadet", "duration_sec": 215.0},
    {"title": "Closed Mall Blues", "artist": "Coffee Shop Beats", "duration_sec": 165.0},
    {"title": "Security Desk Solitude", "artist": "Midnight Ranger", "duration_sec": 240.0},
    {"title": "After Hours Slumber", "artist": "Vaporwave Visionary", "duration_sec": 195.0},
]

REQUIRED_ASSETS = [
    "mall_structure_day.png",
    "mall_structure_night.png",
    "guard_walk_right.png",
    "guard_walk_left.png",
    "mall_pillars.png",
    "panoramic_sky.png",
]
