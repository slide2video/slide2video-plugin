import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "lesson-videos"


@pytest.fixture(autouse=True)
def lv_home(tmp_path, monkeypatch):
    """Every test gets its own ~/.lesson-videos (with a space in the path) and no real keys."""
    home = tmp_path / "home with space"
    monkeypatch.setenv("LESSON_VIDEOS_HOME", str(home))
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return home


import subprocess


def _silence(path, seconds):
    from lv import tools
    subprocess.run([tools.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", f"{seconds:.3f}", "-b:a", "128k", str(path)], check=True)


@pytest.fixture
def fake_speak():
    """Stand-in for ElevenLabs: silence 0.06 s per character, evenly spaced alignment."""
    calls = []

    def speak(text, voice, out):
        from lv.util import write_json
        calls.append(text)
        n = len(text)
        write_json(out.with_suffix(".json"), {"chars": list(text), "starts": [i * 0.06 for i in range(n)],
                                              "ends": [(i + 1) * 0.06 for i in range(n)]})
        _silence(out, n * 0.06)
    speak.calls = calls
    return speak


@pytest.fixture
def make_chapter(tmp_path):
    """Write a chapter folder (script.json + optional scenes.js) under a path with spaces."""
    def make(scenes, scenes_js=None, name="ch1", **top):
        from lv.util import write_json, write_text
        ch = tmp_path / "Unit 1 – Biología" / "lesson-videos" / "_work" / name
        write_json(ch / "script.json", {"chapter": "TEST", "title": "Test chapter", "out": "Chapter 1 - Test.mp4", **top, "scenes": scenes})
        if scenes_js is not None:
            write_text(ch / "scenes.js", scenes_js)
        return ch
    return make


@pytest.fixture(scope="session")
def browser_ok():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch().close()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Chromium not installed for this environment ({e}); run `uv run python -m playwright install chromium`")
    return True


HELLO_JS = "scene('hello', (g, t, s) => Engine.titleCard(g, t, s, { kicker: 'Test', title: 'Héllo *world*', emojis: ['🌊'] }), { bug: false, sfx: [[0.3, 'pop0', -12]] });\n"
