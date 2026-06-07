"""YouTube import allowlist — restrict analysis to user-owned content."""

import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    ROOT = os.path.dirname(os.path.abspath(sys.executable))


def allowlist_path() -> str:
    return os.path.join(ROOT, "import_allowlist.json")


def example_path() -> str:
    return os.path.join(ROOT, "import_allowlist.example.json")


def load_allowlist() -> Dict[str, Any]:
    path = allowlist_path()
    if not os.path.isfile(path):
        ex = example_path()
        if os.path.isfile(ex):
            with open(ex, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "allowed_channel_ids": [],
            "allowed_video_ids": [],
            "require_confirmation": True,
        }
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_unrestricted() -> bool:
    return os.environ.get("MMS_IMPORT_UNRESTRICTED", "").strip() in ("1", "true", "yes")


def check_import_allowed(
    channel_id: Optional[str],
    video_id: Optional[str],
    user_confirmed: bool = False,
) -> Tuple[bool, str]:
    if is_unrestricted():
        return True, ""

    cfg = load_allowlist()
    channels: List[str] = list(cfg.get("allowed_channel_ids") or [])
    videos: List[str] = list(cfg.get("allowed_video_ids") or [])
    require_conf = bool(cfg.get("require_confirmation", True))

    if video_id and video_id in videos:
        return True, ""
    if channel_id and channel_id in channels:
        return True, ""

    if require_conf and user_confirmed and not channels and not videos:
        return True, ""

    if channels or videos:
        return False, (
            "This YouTube URL is not on your import allowlist.\n"
            "Add your channel_id or video_id to import_allowlist.json "
            "(see import_allowlist.example.json)."
        )

    if require_conf and not user_confirmed:
        return False, (
            "Confirm that you own the rights to this URL, or add it to import_allowlist.json."
        )

    return True, ""
