"""Install and check everything, then prove it works with a 3-second test video."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from . import config, keys, narrate, render, sfx, tools
from .util import UserError, write_json, write_text

TEST_SCENES = ("scene('hello', (g, t, s) => Engine.titleCard(g, t, s, { kicker: 'lesson-videos', title: 'It *works*!', "
               "sub: 'Test render', emojis: ['🎬', '✅'] }), { bug: false, sfx: [[0.5, 'sparkle0', -12]] });\n")


def test_render() -> float:
    with tempfile.TemporaryDirectory() as d:
        ch = Path(d) / "doctor test" / "ch1"
        write_json(ch / "script.json", {"chapter": "TEST", "title": "Doctor test", "out": "doctor-test.mp4",
                                        "scenes": [{"id": "hello", "min": 3}]})
        write_text(ch / "scenes.js", TEST_SCENES)
        narrate.narrate(ch)
        out = render.render(ch, workers=1, out_dir=Path(d))
        dur, kinds = tools.duration(out), tools.streams(out)
        if abs(dur - 3) > 0.3 or not {"video", "audio"} <= kinds:
            raise UserError(f"the test video came out wrong ({dur:.1f}s, streams {sorted(kinds)})")
        return dur


def run_doctor(no_keys: bool = False, install: bool = True) -> int:
    rows: list[tuple[str, str, str]] = []
    ok = lambda name, msg: rows.append(("✓", name, msg))      # noqa: E731
    bad = lambda name, msg: rows.append(("✗", name, msg))     # noqa: E731
    ok("Python", sys.version.split()[0])
    try:
        ok("ffmpeg", tools.ffmpeg())
        if not tools.has_x264():
            bad("ffmpeg H.264", "this ffmpeg can't write H.264 video; install the full ffmpeg build")
    except UserError as e:
        bad("ffmpeg", str(e))
    try:
        if install:
            tools.install_chromium()
        ok("Chromium renderer", "ready")
    except UserError as e:
        bad("Chromium renderer", str(e))
    missing = [f for f in config.FONT_FILES if not (config.FONTS_DIR / f).exists()]
    (bad if missing else ok)("Fonts", "missing: " + ", ".join(missing) if missing else "bundled")
    try:
        ok("Sound effects", f"{len(sfx.NAMES)} in {sfx.build()}")
    except Exception as e:  # noqa: BLE001
        bad("Sound effects", str(e))
    if not any(r[0] == "✗" for r in rows):
        try:
            ok("Test video", f"{test_render():.1f}s rendered")
        except UserError as e:
            bad("Test video", str(e))
    if not no_keys:
        for name, good, msg in keys.check():
            (ok if good else bad)(f"{name} key", msg)
    for mark, name, msg in rows:
        print(f"{mark} {name}: {msg}")
    return 0 if all(r[0] == "✓" for r in rows) else 1
