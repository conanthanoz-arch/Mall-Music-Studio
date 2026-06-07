"""Multi-theme asset loader for 6-hour aesthetic rotation blocks."""

import csv
import os
import sys
from datetime import datetime

from PIL import Image

from config import REQUIRED_ASSETS, THEMES


class ThemeAssetManager:
    def __init__(self):
        self.current_theme_id = None
        self.theme_name = ""
        self.bg_day = None
        self.bg_night = None
        self.guard_right = None
        self.guard_left = None
        self.foreground = None
        self.sky_panorama = None
        self.flashlight_mask = None

    def load_theme_into_ram(self, theme_id: int) -> None:
        self.current_theme_id = theme_id
        self.theme_name = THEMES[theme_id]
        theme_path = os.path.join("assets", self.theme_name)

        print(
            f"\n[SYSTEM] >>> CHANGING NETWORK THEME TO: {self.theme_name.upper()} <<<",
            file=sys.stderr,
        )

        self.bg_day = self.bg_night = self.guard_right = self.guard_left = None
        self.foreground = self.sky_panorama = self.flashlight_mask = None

        if not os.path.isdir(theme_path):
            print(
                f"[CRITICAL ERROR] Theme directory '{theme_path}' does not exist!",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            for asset in REQUIRED_ASSETS:
                asset_path = os.path.join(theme_path, asset)
                if not os.path.exists(asset_path):
                    print(
                        f"[CRITICAL ERROR] Missing asset: {asset_path}",
                        file=sys.stderr,
                    )
                    sys.exit(1)

            self.bg_day = Image.open(
                os.path.join(theme_path, "mall_structure_day.png")
            ).convert("RGBA")
            self.bg_night = Image.open(
                os.path.join(theme_path, "mall_structure_night.png")
            ).convert("RGBA")
            self.guard_right = Image.open(
                os.path.join(theme_path, "guard_walk_right.png")
            ).convert("RGBA")
            self.guard_left = Image.open(
                os.path.join(theme_path, "guard_walk_left.png")
            ).convert("RGBA")
            self.foreground = Image.open(
                os.path.join(theme_path, "mall_pillars.png")
            ).convert("RGBA")
            self.sky_panorama = Image.open(
                os.path.join(theme_path, "panoramic_sky.png")
            ).convert("RGBA")

            fl_path = os.path.join(theme_path, "guard_flashlight_mask.png")
            if os.path.exists(fl_path):
                self.flashlight_mask = Image.open(fl_path).convert("RGBA")
            else:
                self.flashlight_mask = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))

            print(
                f"[SUCCESS] {self.theme_name.upper()} textures loaded into system memory.",
                file=sys.stderr,
            )
        except OSError as exc:
            print(
                f"[CRITICAL ERROR] Failed to load theme {self.theme_name}. Details: {exc}",
                file=sys.stderr,
            )
            sys.exit(1)

    def get_theme_advertisements(self):
        s1 = Image.new("RGBA", (450, 350), (0, 0, 0, 0))
        s2 = Image.new("RGBA", (450, 350), (0, 0, 0, 0))

        for fallback in ("fictional_store_1.png", "fictional_store_2.png"):
            if os.path.exists(fallback):
                img = Image.open(fallback).convert("RGBA")
                if fallback.endswith("_1.png"):
                    s1 = img
                else:
                    s2 = img

        if not os.path.exists("advertiser_log.csv"):
            return s1, s2

        current_date = datetime.now().date()
        with open("advertiser_log.csv", mode="r", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                try:
                    start_dt = datetime.strptime(row["Start_Date"], "%Y-%m-%d").date()
                    end_dt = datetime.strptime(row["End_Date"], "%Y-%m-%d").date()
                    is_active = row["Active_Status"].strip().lower() == "true"
                    theme_match = row.get("Theme_Style", self.theme_name) == self.theme_name

                    if (
                        is_active
                        and start_dt <= current_date <= end_dt
                        and theme_match
                        and os.path.exists(row["Asset_File"])
                    ):
                        ad_img = Image.open(row["Asset_File"]).convert("RGBA")
                        if row["Storefront_ID"] == "store_1":
                            s1 = ad_img
                        elif row["Storefront_ID"] == "store_2":
                            s2 = ad_img
                except (KeyError, ValueError):
                    pass

        return s1, s2
