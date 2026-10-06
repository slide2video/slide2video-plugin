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
