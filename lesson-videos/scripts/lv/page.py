"""Chapter page files (index.html, engine copy, fonts) and where the finished video goes."""
from __future__ import annotations

import shutil
from pathlib import Path

from . import config
from .util import safe_name, write_text

INDEX = """<!doctype html><html><head><meta charset="utf-8"><title>lesson video</title>
<style>@font-face{font-family:"Patrick Hand";src:url(fonts/PatrickHand-Regular.ttf)}
@font-face{font-family:"Nunito";src:url(fonts/Nunito.ttf);font-weight:200 1000}
html,body{margin:0;background:#000}canvas{width:100vw;max-width:1920px;display:block;margin:auto}</style>
</head><body><canvas id="c" width="1920" height="1080"></canvas>
<script src="build/timing.js"></script><script src="build/engine.js"></script><script src="scenes.js"></script></body></html>
"""


def ensure_page(ch: Path) -> None:
    (ch / "build").mkdir(parents=True, exist_ok=True)
    (ch / "fonts").mkdir(exist_ok=True)
    for f in config.FONT_FILES:
        if not (ch / "fonts" / f).exists():
            shutil.copy(config.FONTS_DIR / f, ch / "fonts" / f)
    shutil.copy(config.ENGINE_JS, ch / "build" / "engine.js")
    write_text(ch / "index.html", INDEX)


def output_dir(ch: Path) -> Path:
    """<deck>/lesson-videos/ for chapters in _work/, else the chapter's own out/ folder."""
    return ch.parent.parent if ch.parent.name == "_work" else ch / "out"


def output_path(ch: Path, spec: dict, out_dir: Path | None = None) -> Path:
    name = spec.get("out") or f"{spec.get('title') or ch.name}.mp4"
    if not name.lower().endswith(".mp4"):
        name += ".mp4"
    return (out_dir or output_dir(ch)) / safe_name(name)
