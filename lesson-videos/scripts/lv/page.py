"""Chapter page files (index.html, engine copy, fonts) and where the finished video goes."""
from __future__ import annotations

import shutil
from pathlib import Path

from . import config, paths
from .util import safe_name, write_text

INDEX = """<!doctype html><html><head><meta charset="utf-8"><title>lesson video</title>
<style>@font-face{font-family:"Patrick Hand";src:url(fonts/PatrickHand-Regular.ttf)}
@font-face{font-family:"Nunito";src:url(fonts/Nunito.ttf);font-weight:200 1000}
html,body{margin:0;background:#000}canvas{width:100vw;max-width:1920px;display:block;margin:auto}</style>
</head><body><canvas id="c" width="1920" height="1080"></canvas>
<script src="build/timing.js"></script><script src="build/engine.js"></script><script src="scenes.js"></script></body></html>
"""


def ensure_page(ch: Path) -> None:
    """The page's generated files. Teacher mode writes index.html and fonts into the chapter folder (it opens in a
    browser as is); project mode keeps them in the build folder so the project stays text-only."""
    p = paths.chapter(ch)
    p.build.mkdir(parents=True, exist_ok=True)
    shutil.copy(config.ENGINE_JS, p.build / "engine.js")
    if p.project:
        write_text(p.build / "index.html", INDEX)
        return
    (ch / "fonts").mkdir(exist_ok=True)
    for f in config.FONT_FILES:
        if not (ch / "fonts" / f).exists():
            shutil.copy(config.FONTS_DIR / f, ch / "fonts" / f)
    write_text(ch / "index.html", INDEX)


def routes(p: paths.ChapterPaths) -> list[tuple[str, Path]]:
    """What the render server serves: URL prefix → file or folder, longest prefix first."""
    index = p.build / "index.html" if p.project else p.code / "index.html"
    return [("/index.html", index), ("/assets/", p.assets), ("/build/", p.build), ("/fonts/", config.FONTS_DIR),
            ("/", p.code)]


def output_dir(ch: Path) -> Path:
    """Teacher mode: <deck>/lesson-videos/ for chapters in _work/, else the chapter's own out/ folder. Project mode:
    the unit's results folder."""
    return paths.chapter(ch).out


def output_path(ch: Path, spec: dict, out_dir: Path | None = None) -> Path:
    name = spec.get("out") or f"{spec.get('title') or ch.name}.mp4"
    if not name.lower().endswith(".mp4"):
        name += ".mp4"
    return (out_dir or output_dir(ch)) / safe_name(name)
