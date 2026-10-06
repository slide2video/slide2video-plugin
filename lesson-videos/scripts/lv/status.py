"""Where each chapter stands, from the files on disk, so a run can resume in a later session."""
from __future__ import annotations

import re
from pathlib import Path

from .page import output_path
from .util import read_json


def chapters(work: Path) -> list[Path]:
    found = [f.parent for f in Path(work).glob("*/script.json")]
    return sorted(found, key=lambda p: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", p.name)])


def _mtime(p: Path) -> float:
    return p.stat().st_mtime if p.exists() else 0.0


def stage(ch: Path) -> str:
    script, timing, scenes = ch / "script.json", ch / "build" / "timing.js", ch / "scenes.js"
    if not script.exists():
        return "empty"
    if _mtime(timing) < _mtime(script):
        return "script written: run narrate"
    if not scenes.exists():
        return "narrated: write scenes.js"
    out = output_path(ch, read_json(script))
    if _mtime(out) < max(_mtime(scenes), _mtime(timing)):
        return "scenes written: check stills, then render"
    return f"done: {out.name}"


def report(work: Path) -> str:
    rows = [f"{ch.name:<8} {stage(ch)}" for ch in chapters(work)]
    return "\n".join(rows) if rows else "No chapters yet."
