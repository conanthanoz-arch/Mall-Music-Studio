"""Download audio from YouTube URLs via yt-dlp."""

import glob
import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from audio_synthesizer import save_wav
from music_theory import SAMPLE_RATE
from waveform_utils import load_wav_mono


def _subprocess_env() -> dict:
    env = os.environ.copy()
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        ffmpeg_dir = os.path.dirname(ffmpeg)
        env["PATH"] = ffmpeg_dir + os.pathsep + env.get("PATH", "")
    return env


def _ffmpeg_path() -> Optional[str]:
    return shutil.which("ffmpeg")


def _yt_dlp_cmd() -> List[str]:
    for name in ("yt-dlp", "yt-dlp.exe"):
        path = shutil.which(name)
        if path:
            return [path]
    scripts = os.path.join(os.path.dirname(sys.executable), "yt-dlp.exe")
    if os.path.isfile(scripts):
        return [scripts]
    return [sys.executable, "-m", "yt_dlp"]


def _verify_yt_dlp() -> None:
    cmd = _yt_dlp_cmd() + ["--version"]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_subprocess_env(),
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "yt-dlp not found. Install with:\n"
            f'  "{sys.executable}" -m pip install -U yt-dlp'
        )


def _clean_source_files(output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    for pattern in ("source.*", "source.wav"):
        for path in glob.glob(os.path.join(output_dir, pattern)):
            try:
                os.remove(path)
            except OSError:
                pass


def _trim_wav(path: str, max_duration_sec: float) -> None:
    if max_duration_sec <= 0:
        return
    data = load_wav_mono(path)
    max_samples = int(max_duration_sec * SAMPLE_RATE)
    if len(data) > max_samples:
        save_wav(path, data[:max_samples])


def _normalize_youtube_url(url: str) -> str:
    url = url.strip()
    if "youtube.com/watch" in url and "v=" in url:
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(url)
        vid = parse_qs(parsed.query).get("v", [None])[0]
        if vid:
            return f"https://www.youtube.com/watch?v={vid}"
    if "youtu.be/" in url:
        from urllib.parse import urlparse

        vid = urlparse(url).path.lstrip("/").split("/")[0]
        if vid:
            return f"https://www.youtube.com/watch?v={vid}"
    return url


def _video_id_from_url(url: str) -> Optional[str]:
    url = _normalize_youtube_url(url)
    if "v=" in url:
        from urllib.parse import parse_qs, urlparse

        return parse_qs(urlparse(url).query).get("v", [None])[0]
    return None


def fetch_video_metadata(url: str) -> Dict[str, Any]:
    """Return channel_id, video_id, title without downloading audio."""
    _verify_yt_dlp()
    url = _normalize_youtube_url(url)
    code, out, err = _run_yt_dlp(["--dump-single-json", "--no-playlist", url])
    if code != 0:
        raise RuntimeError((err or out or "yt-dlp metadata failed")[:800])
    data = json.loads(out)
    return {
        "title": data.get("title") or "YouTube Import",
        "duration_sec": float(data.get("duration") or 0),
        "channel_id": data.get("channel_id") or data.get("uploader_id"),
        "video_id": data.get("id") or _video_id_from_url(url),
        "source_url": url,
    }


def assert_import_allowed(url: str, user_confirmed: bool = False) -> None:
    from tools.import_allowlist import check_import_allowed

    meta = fetch_video_metadata(url)
    ok, msg = check_import_allowed(
        meta.get("channel_id"),
        meta.get("video_id"),
        user_confirmed=user_confirmed,
    )
    if not ok:
        raise RuntimeError(msg)


def _ffmpeg_to_wav(src_path: str, wav_path: str) -> None:
    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError(
            "ffmpeg is required to convert downloaded audio.\n"
            "Install ffmpeg and add it to PATH."
        )
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        src_path,
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE),
        wav_path,
    ]
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
        raise RuntimeError(f"ffmpeg conversion failed: {err[:500]}")


def _run_yt_dlp(args: List[str]) -> Tuple[int, str, str]:
    proc = subprocess.run(
        _yt_dlp_cmd() + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_subprocess_env(),
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _parse_title_duration(stdout: str) -> Tuple[str, float]:
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
    title = lines[0] if lines else "YouTube Import"
    duration = 0.0
    if len(lines) > 1:
        try:
            duration = float(lines[1])
        except ValueError:
            duration = 0.0
    return title, duration


def _find_downloaded_source(output_dir: str) -> Optional[str]:
    wav_path = os.path.join(output_dir, "source.wav")
    if os.path.isfile(wav_path):
        return wav_path
    for ext in (".wav", ".m4a", ".webm", ".opus", ".mp3", ".aac"):
        candidate = os.path.join(output_dir, f"source{ext}")
        if os.path.isfile(candidate):
            return candidate
    return None


def download_youtube_audio(
    url: str,
    output_dir: str,
    max_duration_sec: Optional[float] = 120.0,
    user_confirmed: bool = False,
) -> Dict[str, Any]:
    """Download best audio and convert to WAV."""
    assert_import_allowed(url, user_confirmed=user_confirmed)
    os.makedirs(output_dir, exist_ok=True)
    _clean_source_files(output_dir)
    _verify_yt_dlp()
    url = _normalize_youtube_url(url)

    out_template = os.path.join(output_dir, "source.%(ext)s")
    wav_path = os.path.join(output_dir, "source.wav")
    title = "YouTube Import"
    duration = 0.0
    errors: List[str] = []

    client_sets = (
        "youtube:player_client=web,android",
        "youtube:player_client=mweb,android",
        "youtube:player_client=android",
    )

    for clients in client_sets:
        code, out, err = _run_yt_dlp(
            [
                "--no-playlist",
                "--extractor-args",
                clients,
                "--extract-audio",
                "--audio-format",
                "wav",
                "--audio-quality",
                "0",
                "-o",
                out_template,
                "--print",
                "after_move:%(title)s",
                "--print",
                "after_move:%(duration)s",
                url,
            ]
        )
        if code == 0 and os.path.isfile(wav_path):
            title, duration = _parse_title_duration(out)
            break
        errors.append(err.strip()[:300] or out.strip()[:300])
        _clean_source_files(output_dir)

    if not os.path.isfile(wav_path):
        for clients in client_sets:
            code, out, err = _run_yt_dlp(
                [
                    "--no-playlist",
                    "--extractor-args",
                    clients,
                    "-f",
                    "bestaudio/best",
                    "-o",
                    out_template,
                    "--print",
                    "after_move:%(title)s",
                    "--print",
                    "after_move:%(duration)s",
                    url,
                ]
            )
            src = _find_downloaded_source(output_dir)
            if code == 0 and src:
                title, duration = _parse_title_duration(out)
                if not src.endswith(".wav"):
                    _ffmpeg_to_wav(src, wav_path)
                    try:
                        os.remove(src)
                    except OSError:
                        pass
                break
            errors.append(err.strip()[:300] or out.strip()[:300])
            _clean_source_files(output_dir)

    if not os.path.isfile(wav_path):
        if not _ffmpeg_path():
            raise RuntimeError(
                "yt-dlp download failed and ffmpeg is not installed.\n"
                "Install ffmpeg, then retry.\n\n"
                + (errors[-1] if errors else "")
            )
        raise RuntimeError(
            "yt-dlp failed to download this video after multiple attempts.\n"
            "Try updating yt-dlp: pip install -U yt-dlp\n\n"
            + (errors[-1] if errors else "")
        )

    if max_duration_sec:
        _trim_wav(wav_path, max_duration_sec)
        duration = min(duration or max_duration_sec, max_duration_sec)

    return {
        "wav_path": wav_path,
        "title": title,
        "duration_sec": duration,
        "source_url": url,
    }


def check_ffmpeg_available() -> bool:
    return _ffmpeg_path() is not None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-sec", type=float, default=120.0)
    args = parser.parse_args()
    meta = download_youtube_audio(args.url, args.out_dir, max_duration_sec=args.max_sec)
    print(json.dumps(meta, indent=2))
