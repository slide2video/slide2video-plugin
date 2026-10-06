"""ffmpeg/ffprobe (system first, else the static-ffmpeg download) and the Playwright browser."""
from __future__ import annotations

import functools
import shutil
import subprocess
import sys

from .util import UserError


@functools.cache
def _pair() -> tuple[str, str]:
    ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ff and fp:
        return ff, fp
    try:
        from static_ffmpeg import run
        ff, fp = run.get_or_fetch_platform_executables_else_raise()
        return str(ff), str(fp)
    except Exception as e:  # noqa: BLE001  network blocked, unsupported platform
        raise UserError(f"Could not get ffmpeg ({e}). Install it (macOS: `brew install ffmpeg`; Windows: "
                        "`winget install Gyan.FFmpeg`) or allow downloads from github.com, then retry.") from None


def ffmpeg() -> str:
    return _pair()[0]


def ffprobe() -> str:
    return _pair()[1]


def _probe(*args) -> str:
    return subprocess.run([ffprobe(), "-v", "error", *map(str, args)], capture_output=True, check=True,
                          encoding="utf-8", errors="replace").stdout


def duration(path) -> float:
    return float(_probe("-show_entries", "format=duration", "-of", "csv=p=0", path).strip())


def streams(path) -> set[str]:
    return {l.strip().strip(",") for l in _probe("-show_entries", "stream=codec_type", "-of", "csv=p=0", path).splitlines() if l.strip()}


def has_x264() -> bool:
    out = subprocess.run([ffmpeg(), "-hide_banner", "-encoders"], capture_output=True, encoding="utf-8", errors="replace").stdout
    return "libx264" in out


def install_chromium() -> None:
    r = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], capture_output=True,
                       encoding="utf-8", errors="replace")
    if r.returncode:
        raise UserError("Could not download the Chromium renderer (about 150 MB). Check the internet connection "
                        "(school networks may block it), then run `doctor` again.\n" + r.stderr[-800:])
