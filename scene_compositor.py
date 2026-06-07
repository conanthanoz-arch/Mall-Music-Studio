"""Scene layout constants and compositing helpers for the mall patrol stream."""

import math
from typing import Tuple

from PIL import Image, ImageDraw, ImageEnhance

# Art guidelines (You15)
CANVAS_W, CANVAS_H = 1920, 1080
SKY_W, SKY_H = 3840, 1080
FLOOR_Y = 850
GUARD_SPRITE_H = 175
GUARD_Y = FLOOR_Y - GUARD_SPRITE_H  # feet lock to floor line
INTERIOR_END_X = 1400
STORE_1_POS = (350, 500)
STORE_2_POS = (1120, 500)
AD_SIZE = (450, 350)
PATROL_START_X = 80
PATROL_END_X = 1820
PILLAR_X = 900
PILLAR_W = 100
PARALLAX_RATIO = 0.35


def crop_parallax_sky(sky: Image.Image, scroll_x: float) -> Image.Image:
    """Crop a 1920-wide window from the panoramic sky with horizontal scroll."""
    max_offset = max(0, sky.width - CANVAS_W)
    offset = int(scroll_x * PARALLAX_RATIO) % (max_offset + 1) if max_offset else 0
    return sky.crop((offset, 0, offset + CANVAS_W, min(SKY_H, sky.height)))


def guard_behind_pillar(guard_x: int) -> bool:
    """True when guard should render under foreground pillar layer."""
    return PILLAR_X <= guard_x <= PILLAR_X + PILLAR_W


def composite_guard(canvas: Image.Image, sprite: Image.Image, guard_x: int, guard_y: int = GUARD_Y):
    canvas.alpha_composite(sprite, dest=(guard_x, guard_y))


def apply_dual_zone_lighting(
    canvas: Image.Image,
    block_frame: int,
    block_duration: int,
    guard_x: int,
) -> Image.Image:
    """
    Semi-transparent lighting overlay: skylight sun shafts (interior) + streetlight (exterior at night).
    """
    time_factor = (math.sin(2 * math.pi * block_frame / block_duration) + 1) / 2
    is_night = time_factor < 0.28

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    if not is_night and time_factor > 0.25:
        angle = int(math.cos(2 * math.pi * block_frame / block_duration) * 120)
        opacity = int(time_factor * 70)
        draw.polygon(
            [
                (500 + angle, 0),
                (700 + angle, 0),
                (900 + angle, FLOOR_Y),
                (600 + angle, FLOOR_Y),
            ],
            fill=(255, 230, 180, opacity),
        )

    if is_night:
        if guard_x < INTERIOR_END_X:
            draw.rectangle([0, 0, INTERIOR_END_X, CANVAS_H], fill=(20, 30, 80, 35))
        else:
            draw.ellipse(
                [1550, 520, 1750, 720],
                fill=(255, 220, 140, 90),
            )
            draw.rectangle([INTERIOR_END_X, 0, CANVAS_W, CANVAS_H], fill=(10, 15, 40, 50))

    return Image.alpha_composite(canvas, overlay)


def apply_time_grade(
    canvas: Image.Image,
    block_frame: int,
    block_duration: int,
    is_business_hours: bool,
) -> Image.Image:
    """Global brightness/saturation tint; smoother than hard cut."""
    time_factor = (math.sin(2 * math.pi * block_frame / block_duration) + 1) / 2
    rgb = canvas.convert("RGB")
    brightness = 0.35 + time_factor * 0.65 if is_business_hours else 0.25 + time_factor * 0.35
    rgb = ImageEnhance.Brightness(rgb).enhance(brightness)
    rgb = ImageEnhance.Color(rgb).enhance(0.45 + time_factor * 0.55)

    if not is_business_hours:
        rgb = Image.blend(rgb, Image.new("RGB", rgb.size, (5, 10, 35)), alpha=0.3)

    return rgb


def build_frame(
    theme_manager,
    guard_x: int,
    frame: int,
    block_frame: int,
    block_duration: int,
    is_business_hours: bool,
) -> Image.Image:
    """Full 6-layer compositing stack."""
    bg = theme_manager.bg_day if is_business_hours else theme_manager.bg_night
    sky_window = crop_parallax_sky(theme_manager.sky_panorama, guard_x)
    canvas = sky_window.copy()
    canvas.alpha_composite(bg, dest=(0, 0))

    ad_1, ad_2 = theme_manager.get_theme_advertisements()
    canvas.alpha_composite(ad_1, dest=STORE_1_POS)
    canvas.alpha_composite(ad_2, dest=STORE_2_POS)

    sprite = theme_manager.guard_right
    composite_guard(canvas, sprite, guard_x)
    canvas.alpha_composite(theme_manager.foreground, dest=(0, 0))

    canvas = apply_dual_zone_lighting(canvas, block_frame, block_duration, guard_x)

    if not is_business_hours and theme_manager.flashlight_mask:
        fl = theme_manager.flashlight_mask.copy()
        canvas.alpha_composite(fl, dest=(guard_x - 80, GUARD_Y - 120))

    return apply_time_grade(canvas, block_frame, block_duration, is_business_hours)
