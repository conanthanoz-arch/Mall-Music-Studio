"""Separate audio into stems using Demucs (subprocess)."""

import json
import os
import subprocess
import sys
from typing import Any, Dict, List

from tools.youtube_import import _subprocess_env


def _verify_demucs() -> None:
    proc = subprocess.run(
        [sys.executable, "-c", "import demucs"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_subprocess_env(),
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "demucs not found. Install with:\n"
            f'  "{sys.executable}" -m pip install demucs\n'
            "(Requires PyTorch — large download.)"
        )


def _verify_soundfile() -> None:
    proc = subprocess.run(
        [sys.executable, "-c", "import soundfile"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_subprocess_env(),
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "soundfile not found (required for Demucs to save WAV stems).\n"
            f'  "{sys.executable}" -m pip install soundfile'
        )


def _clear_corrupt_demucs_cache() -> None:
    """Remove partially downloaded Demucs model weights (common after interrupted downloads)."""
    try:
        import torch

        cache_dir = os.path.join(torch.hub.get_dir(), "checkpoints")
        if not os.path.isdir(cache_dir):
            return
        for name in os.listdir(cache_dir):
            if not name.endswith(".th"):
                continue
            path = os.path.join(cache_dir, name)
            try:
                if os.path.getsize(path) < 70_000_000:
                    os.remove(path)
            except OSError:
                pass
    except Exception:
        pass


def separate_stems(
    wav_path: str,
    output_dir: str,
    model: str = "htdemucs",
    two_stems: str = "",
) -> List[Dict[str, Any]]:
    """
    Run demucs on wav_path. Returns list of {name, wav, label}.
    """
    os.makedirs(output_dir, exist_ok=True)
    _verify_demucs()
    _verify_soundfile()
    _clear_corrupt_demucs_cache()

    cmd = [
        sys.executable,
        "-m",
        "demucs",
        "-n",
        model,
        "--out",
        output_dir,
        wav_path,
    ]
    if two_stems:
        cmd.extend(["--two-stems", two_stems])

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_subprocess_env(),
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        if "filename 'storages' not found" in err or "Couldn't find appropriate backend" in err:
            if "storages" in err:
                _clear_corrupt_demucs_cache()
                hint = "Corrupted Demucs model cache was cleared — retry once."
            else:
                hint = 'Install soundfile: pip install soundfile'
            raise RuntimeError(f"demucs failed: {err[:600]}\n\n{hint}")
        raise RuntimeError(f"demucs failed: {err[:800]}")

    base = os.path.splitext(os.path.basename(wav_path))[0]
    stem_root = os.path.join(output_dir, model, base)
    if not os.path.isdir(stem_root):
        for root, _dirs, files in os.walk(output_dir):
            if "drums.wav" in files or "bass.wav" in files:
                stem_root = root
                break

    if not os.path.isdir(stem_root):
        raise RuntimeError(f"Demucs output not found under {output_dir}")

    stems: List[Dict[str, Any]] = []
    for name in sorted(os.listdir(stem_root)):
        if not name.endswith(".wav"):
            continue
        stem_key = os.path.splitext(name)[0]
        stems.append(
            {
                "name": stem_key,
                "wav": os.path.join(stem_root, name),
                "label": stem_key.replace("_", " ").title(),
            }
        )
    if not stems:
        raise RuntimeError("No stem WAV files produced")
    return stems


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("wav")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    result = separate_stems(args.wav, args.out_dir)
    print(json.dumps(result, indent=2))
