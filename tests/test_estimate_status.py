import os
import time

from lv import estimate, status
from lv.util import write_json, write_text


def test_plan_estimate():
    assert estimate.plan_chars(5, 5) == 22500
    assert estimate.gemini_usd(2, True) == 0.88
    r = estimate.report(22500, 2, True)
    assert "22,500" in r and "$0.88" in r and "20%" in r
    free = estimate.report(22500, 0, False, paid_voice=False)
    assert "free voice" in free and "$0.00" in free


def test_chars_in_scripts(tmp_path):
    write_json(tmp_path / "ch1/script.json", {"scenes": [{"id": "a", "say": "Hello."}, {"id": "b"}]})
    write_json(tmp_path / "ch2/script.json", {"scenes": [{"id": "a", "say": "Hi"}]})
    assert estimate.chars_in_scripts(tmp_path) == 8


def test_status_stages(tmp_path):
    work = tmp_path / "lesson-videos" / "_work"
    ch = work / "ch2"
    write_json(ch / "script.json", {"out": "Chapter 2 - X.mp4", "scenes": []})
    assert status.stage(ch) == "script written: run narrate"
    time.sleep(0.01)
    write_text(ch / "build/timing.js", "window.TIMING = {};")
    assert status.stage(ch) == "narrated: write scenes.js"
    write_text(ch / "scenes.js", "")
    assert status.stage(ch) == "scenes written: check stills, then render"
    time.sleep(0.01)
    write_text(tmp_path / "lesson-videos/Chapter 2 - X.mp4", "x")
    assert status.stage(ch) == "done: Chapter 2 - X.mp4"
    write_json(work / "ch10/script.json", {"scenes": []})
    assert [c.name for c in status.chapters(work)] == ["ch2", "ch10"]
    assert "ch10" in status.report(work)
