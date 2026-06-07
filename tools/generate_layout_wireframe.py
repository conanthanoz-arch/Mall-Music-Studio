"""Generate layout wireframe PNG for ComfyUI ControlNet guidance."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw

from scene_compositor import (
    CANVAS_H,
    CANVAS_W,
    FLOOR_Y,
    INTERIOR_END_X,
    PILLAR_X,
    PILLAR_W,
    STORE_1_POS,
    STORE_2_POS,
    AD_SIZE,
)

OUT = os.path.join("tools", "layout_wireframe.png")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), (240, 240, 240))
    draw = ImageDraw.Draw(img)

    draw.line([(0, FLOOR_Y), (CANVAS_W, FLOOR_Y)], fill=(80, 80, 80), width=3)
    draw.line([(INTERIOR_END_X, 0), (INTERIOR_END_X, CANVAS_H)], fill=(120, 120, 120), width=2)
    draw.text((20, 20), "ZONE 1 INTERIOR", fill=(60, 60, 60))
    draw.text((INTERIOR_END_X + 20, 20), "ZONE 2 SIDEWALK", fill=(60, 60, 60))

    for label, pos in (("STORE 1", STORE_1_POS), ("STORE 2", STORE_2_POS)):
        x, y = pos
        draw.rectangle([x, y, x + AD_SIZE[0], y + AD_SIZE[1]], outline=(200, 80, 80), width=3)
        draw.text((x + 8, y + 8), label, fill=(200, 80, 80))

    draw.rectangle([PILLAR_X, 0, PILLAR_X + PILLAR_W, CANVAS_H], fill=(100, 100, 100))
    draw.rectangle([1650, 400, 1680, FLOOR_Y], fill=(80, 80, 80))
    draw.rectangle([INTERIOR_END_X - 30, 200, INTERIOR_END_X + 30, FLOOR_Y], outline=(0, 100, 200), width=2)
    draw.text((INTERIOR_END_X - 60, 160), "GLASS DOORS", fill=(0, 100, 200))

    img.save(OUT)
    print(f"Saved {OUT} ({CANVAS_W}x{CANVAS_H})")


if __name__ == "__main__":
    main()
