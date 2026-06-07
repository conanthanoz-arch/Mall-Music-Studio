"""Launch YouTube import sidecar worker (subprocess)."""

import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional


from tools.youtube_import import _subprocess_env, check_ffmpeg_available


def import_progress_path(library_dir: str) -> str:
    return os.path.join(library_dir, "import_jobs", "latest", "progress.json")


def read_import_progress(library_dir: str) -> Dict[str, Any]:
    path = import_progress_path(library_dir)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def manifest_path(library_dir: str) -> str:
    return os.path.join(library_dir, "import_jobs", "latest", "manifest.json")


def read_import_manifest(library_dir: str) -> Dict[str, Any]:
    path = manifest_path(library_dir)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_import_manifest(library_dir: str, manifest: Dict[str, Any]) -> None:
    path = manifest_path(library_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def project_root() -> str:
    if getattr(sys, "frozen", False):
        return os.path.abspath(os.path.join(os.path.dirname(sys.executable), ".."))
    return os.path.dirname(os.path.abspath(__file__))


def import_python() -> str:
    """Python interpreter used for YouTube import (prefers project .venv)."""
    root = project_root()
    for rel in (
        os.path.join(".venv", "Scripts", "python.exe"),
        os.path.join(".venv", "bin", "python"),
    ):
        candidate = os.path.join(root, rel)
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return sys.executable


def worker_script_path() -> str:
    path = os.path.join(project_root(), "tools", "import_worker.py")
    if not os.path.isfile(path):
        raise RuntimeError(
            f"Import worker not found at {path}. "
            "Run Mall Music Studio from the project folder or keep tools/ next to the EXE."
        )
    return path


def _has_module(python: str, module: str) -> bool:
    proc = subprocess.run(
        [python, "-c", f"import {module}"],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def check_import_dependencies() -> Dict[str, Any]:
    py = import_python()
    yt_ok = _has_module(py, "yt_dlp")
    demucs_ok = _has_module(py, "demucs")
    soundfile_ok = _has_module(py, "soundfile")
    worker_ok = os.path.isfile(os.path.join(project_root(), "tools", "import_worker.py"))
    ffmpeg_ok = check_ffmpeg_available()
    return {
        "yt_dlp": yt_ok,
        "demucs": demucs_ok,
        "soundfile": soundfile_ok,
        "ffmpeg": ffmpeg_ok,
        "worker": worker_ok,
        "python": py,
        "ready": yt_ok and demucs_ok and soundfile_ok and worker_ok and ffmpeg_ok,
    }


def install_command() -> str:
    py = import_python()
    pip = os.path.join(os.path.dirname(py), "pip.exe")
    if os.path.isfile(pip):
        return f'"{pip}" install yt-dlp demucs soundfile'
    return f'"{py}" -m pip install yt-dlp demucs soundfile'


def run_import_subprocess(
    url: str,
    library_dir: str,
    max_download_sec: float = 120.0,
) -> Dict[str, Any]:
    """Download + Demucs; returns manifest dict or raises RuntimeError."""
    deps = check_import_dependencies()
    if not deps["ready"]:
        missing = []
        if not deps["yt_dlp"]:
            missing.append("yt-dlp")
        if not deps["demucs"]:
            missing.append("demucs")
        if not deps.get("soundfile"):
            missing.append("soundfile")
        if not deps.get("ffmpeg"):
            missing.append("ffmpeg")
        if not deps["worker"]:
            missing.append("import worker script")
        raise RuntimeError(
            "Missing import dependencies: " + ", ".join(missing) + ".\n"
            "Install with:\n  " + install_command()
        )

    script = worker_script_path()
    python = deps["python"]
    out_path = manifest_path(library_dir)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    cmd: List[str] = [
        python,
        script,
        url,
        "--library-dir",
        library_dir,
        "--max-download-sec",
        str(max_download_sec),
        "--manifest-out",
        out_path,
    ]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=project_root(),
        env=_subprocess_env(),
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(err[:1200] or "Import worker failed")

    if os.path.isfile(out_path):
        with open(out_path, "r", encoding="utf-8") as f:
            return json.load(f)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Import finished but manifest missing: {exc}") from exc
