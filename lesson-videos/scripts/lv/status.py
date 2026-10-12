"""Where each chapter stands, from the files on disk, so a run can resume in a later session."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from . import paths
from .page import output_path
from .util import read_json, write_json


def chapters(work: Path) -> list[Path]:
    found = [f.parent for f in paths.lesson(work).code.glob("*/script.json")]
    return sorted(found, key=lambda p: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", p.name)])


def _mtime(p: Path) -> float:
    return p.stat().st_mtime if p.exists() else 0.0


STAMP = "rendered.json"


def _fingerprint(p: paths.ChapterPaths) -> dict:
    files = {"script": p.code / "script.json", "scenes": p.code / "scenes.js"}
    return {k: hashlib.sha1(f.read_bytes()).hexdigest() if f.exists() else None for k, f in files.items()}


def mark_rendered(ch: Path, out: Path) -> None:
    """Remember what the finished video was made from, next to the paid media (the cache can be wiped and a git
    checkout resets file dates, so `stage` can't rely on them alone)."""
    p = paths.chapter(ch)
    write_json(p.sources / STAMP, {"out": Path(out).name, **_fingerprint(p)})


def stage(ch: Path) -> str:
    p = paths.chapter(ch)
    script, timing, scenes = p.code / "script.json", p.build / "timing.js", p.code / "scenes.js"
    if not script.exists():
        return "empty"
    stamp = p.sources / STAMP
    if stamp.exists():
        s = read_json(stamp)
        if (p.out / s.get("out", "")).is_file() and {k: s.get(k) for k in ("script", "scenes")} == _fingerprint(p):
            return f"done: {s['out']}"
    if _mtime(timing) < _mtime(script):
        return "script written: run narrate"
    if not scenes.exists():
        return "narrated: write scenes.js"
    out = output_path(ch, read_json(script), p.out)
    if _mtime(out) < max(_mtime(scenes), _mtime(timing)):
        return "scenes written: check stills, then render"
    return f"done: {out.name}"


def report(work: Path) -> str:
    rows = [f"{ch.name:<8} {stage(ch)}" for ch in chapters(work)]
    return "\n".join(rows) if rows else "No chapters yet."
