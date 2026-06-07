"""Load and resolve CC0 / user-licensed sample manifest entries."""

import json
import os
import sys
from typing import Any, Dict, List, Optional

_LIBRARY_ROOT: Optional[str] = None
_manifest_cache: Optional[Dict[str, Any]] = None


def set_licensed_library_root(path: str) -> None:
    global _LIBRARY_ROOT, _manifest_cache
    _LIBRARY_ROOT = path
    _manifest_cache = None


def licensed_library_dir() -> str:
    if _LIBRARY_ROOT:
        return _LIBRARY_ROOT
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        portable = os.path.join(exe_dir, "licensed_library")
        if os.path.isdir(portable):
            return portable
        return os.path.join(os.path.dirname(exe_dir), "licensed_library")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "licensed_library")


def manifest_path() -> str:
    return os.path.join(licensed_library_dir(), "manifest.json")


def load_manifest(force: bool = False) -> Dict[str, Any]:
    global _manifest_cache
    if _manifest_cache is not None and not force:
        return _manifest_cache
    path = manifest_path()
    if not os.path.isfile(path):
        _manifest_cache = {"version": 1, "entries": [], "presets": []}
        return _manifest_cache
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "entries" not in data:
        data["entries"] = []
    if "presets" not in data:
        data["presets"] = []
    _manifest_cache = data
    return data


def save_manifest(data: Dict[str, Any]) -> None:
    global _manifest_cache
    root = licensed_library_dir()
    os.makedirs(root, exist_ok=True)
    path = manifest_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    _manifest_cache = data


def resolve_sample_path(relative_path: str) -> str:
    return os.path.join(licensed_library_dir(), relative_path.replace("/", os.sep))


def get_manifest_entry(entry_id: str) -> Optional[Dict[str, Any]]:
    for entry in load_manifest().get("entries", []):
        if entry.get("id") == entry_id:
            return entry
    return None


def list_manifest_entries(
    slot: Optional[str] = None,
    entry_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    out = []
    for entry in load_manifest().get("entries", []):
        if slot and entry.get("slot") != slot:
            continue
        if entry_type and entry.get("type") != entry_type:
            continue
        out.append(entry)
    return out


def register_user_entry(entry: Dict[str, Any]) -> str:
    data = load_manifest(force=True)
    entries = data.setdefault("entries", [])
    entry_id = entry.get("id")
    if not entry_id:
        raise ValueError("entry id required")
    entries = [e for e in entries if e.get("id") != entry_id]
    entries.append(entry)
    data["entries"] = entries
    save_manifest(data)
    return entry_id


def vinyl_crackle_path() -> Optional[str]:
    for entry in load_manifest().get("entries", []):
        if entry.get("id") in ("freesound_vinyl_crackle", "cc0_vinyl_bed", "kenney_vinyl_texture"):
            path = resolve_sample_path(entry["path"])
            if os.path.isfile(path):
                return path
    for entry in load_manifest().get("entries", []):
        tags = entry.get("tags") or []
        if "vinyl" in tags or "crackle" in tags:
            path = resolve_sample_path(entry["path"])
            if os.path.isfile(path):
                return path
    return None
