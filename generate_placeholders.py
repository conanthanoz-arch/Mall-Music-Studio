"""Generate colored placeholder PNG assets for local development testing."""

import os

from PIL import Image, ImageDraw

from config import REQUIRED_ASSETS, THEMES
from scene_compositor import (
    AD_SIZE,
    CANVAS_H,
    CANVAS_W,
    FLOOR_Y,
    GUARD_SPRITE_H,
    INTERIOR_END_X,
    PILLAR_W,
    SKY_H,
    SKY_W,
    STORE_1_POS,
    STORE_2_POS,
)

THEME_COLORS = {
    "pixel_art": (180, 120, 80),
    "anime_vector": (120, 160, 220),
    "matte_painting": (100, 140, 100),
    "cyberpunk": (180, 60, 200),
}

GUARD_W = 50


def make_structure(size, base_color, label, is_night=False):
    img = Image.new("RGBA", size, base_color + (255,))
    draw = ImageDraw.Draw(img)
    draw.line([(0, FLOOR_Y), (size[0], FLOOR_Y)], fill=(60, 60, 60, 255), width=2)
    draw.line([(INTERIOR_END_X, 0), (INTERIOR_END_X, size[1])], fill=(100, 100, 100, 255), width=2)
    for pos in (STORE_1_POS, STORE_2_POS):
        x, y = pos
        draw.rectangle([x, y, x + AD_SIZE[0], y + AD_SIZE[1]], fill=(0, 0, 0, 0))
    # Skylight / outdoor sky cutouts (transparent)
    draw.rectangle([400, 0, 800, 120], fill=(0, 0, 0, 0))
    draw.rectangle([INTERIOR_END_X, 0, size[0], 200], fill=(0, 0, 0, 0))
    tint = (30, 30, 60, 80) if is_night else (0, 0, 0, 0)
    if is_night:
        draw.rectangle([0, 0, size[0], size[1]], fill=tint)
    draw.text((40, 40), label, fill=(255, 255, 255, 255))
    return img


def make_sky(size, base_color):
    img = Image.new("RGBA", size, (135, 180, 235, 255))
    draw = ImageDraw.Draw(img)
    for i in range(0, size[0], 400):
        draw.ellipse([i, 40, i + 180, 160], fill=(255, 255, 255, 180))
    draw.text((40, 40), "panoramic_sky", fill=base_color + (255,))
    return img


def make_pillars(size):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([900, 0, 900 + PILLAR_W, size[1]], fill=(90, 90, 90, 230))
    draw.rectangle([1650, 400, 1680, FLOOR_Y], fill=(70, 70, 70, 230))
    return img


def make_guard(size, facing="right"):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([8, 20, 42, 120], fill=(50, 80, 120, 255))
    draw.rectangle([10, 120, 40, size[1]], fill=(40, 40, 40, 255))
    draw.text((4, 4), facing[:1].upper(), fill=(255, 255, 255, 255))
    return img


def make_flashlight(size):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.polygon([(0, size[1]), (size[0], size[1] // 2), (size[0], size[1])], fill=(255, 255, 220, 100))
    return img


def generate_theme_assets(theme_name, base_color):
    theme_dir = os.path.join("assets", theme_name)
    os.makedirs(theme_dir, exist_ok=True)

    assets = {
        "mall_structure_day.png": make_structure((CANVAS_W, CANVAS_H), base_color, f"{theme_name}/day"),
        "mall_structure_night.png": make_structure(
            (CANVAS_W, CANVAS_H), base_color, f"{theme_name}/night", is_night=True
        ),
        "guard_walk_right.png": make_guard((GUARD_W, GUARD_SPRITE_H), "right"),
        "guard_walk_left.png": make_guard((GUARD_W, GUARD_SPRITE_H), "left"),
        "mall_pillars.png": make_pillars((CANVAS_W, CANVAS_H)),
        "panoramic_sky.png": make_sky((SKY_W, SKY_H), base_color),
        "guard_flashlight_mask.png": make_flashlight((350, 200)),
    }

    for name, img in assets.items():
        path = os.path.join(theme_dir, name)
        img.save(path)
        print(f"  Created {path}")


def generate_ads():
    os.makedirs("ads", exist_ok=True)
    ads = {
        "ads/pixel_logo.png": (255, 100, 100),
        "ads/neon_logo.png": (100, 255, 200),
        "fictional_store_1.png": (200, 150, 80),
        "fictional_store_2.png": (80, 150, 200),
    }
    for path, color in ads.items():
        if path.startswith("ads"):
            os.makedirs("ads", exist_ok=True)
        img = Image.new("RGBA", AD_SIZE, color + (200,))
        draw = ImageDraw.Draw(img)
        draw.text((20, AD_SIZE[1] // 2 - 10), os.path.basename(path), fill=(255, 255, 255, 255))
        img.save(path)
        print(f"  Created {path}")


def main():
    print("Generating placeholder assets (art-guideline dimensions)...")
    os.makedirs("assets", exist_ok=True)
    os.makedirs("music_library", exist_ok=True)

    for theme, color in THEME_COLORS.items():
        print(f"\nTheme: {theme}")
        generate_theme_assets(theme, color)

    print("\nAdvertiser placeholders:")
    generate_ads()
    print("\nDone. Run: python benchmark_engine.py")
    print("       python tools/generate_layout_wireframe.py")


if __name__ == "__main__":
    main()
