"""Validate theme PNG assets against art guideline dimensions."""

import os
import sys

from PIL import Image

from config import REQUIRED_ASSETS, THEMES

SPECS = {
    "mall_structure_day.png": (1920, 1080),
    "mall_structure_night.png": (1920, 1080),
    "guard_walk_right.png": (50, 175),
    "guard_walk_left.png": (50, 175),
    "mall_pillars.png": (1920, 1080),
    "panoramic_sky.png": (3840, 1080),
    "guard_flashlight_mask.png": (350, 200),
}


def validate_theme(theme_path: str) -> list:
    errors = []
    for asset in REQUIRED_ASSETS:
        path = os.path.join(theme_path, asset)
        if not os.path.exists(path):
            errors.append(f"Missing: {path}")
            continue
        try:
            img = Image.open(path)
            expected = SPECS.get(asset)
            if expected and img.size != expected:
                errors.append(f"{path}: expected {expected}, got {img.size}")
            if asset.startswith("mall_") or asset == "panoramic_sky.png":
                if img.mode != "RGBA":
                    errors.append(f"{path}: expected RGBA, got {img.mode}")
        except OSError as e:
            errors.append(f"{path}: corrupt ({e})")
    return errors


def main():
    all_errors = []
    for theme in THEMES.values():
        path = os.path.join("assets", theme)
        if not os.path.isdir(path):
            all_errors.append(f"Missing theme dir: {path}")
            continue
        all_errors.extend(validate_theme(path))

    if all_errors:
        print("Asset validation FAILED:", file=sys.stderr)
        for e in all_errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)
    print("[OK] All theme assets pass dimension checks.")


if __name__ == "__main__":
    main()
