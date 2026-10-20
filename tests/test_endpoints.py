from pathlib import Path

from lv import clips, config

PLUGIN = Path(__file__).resolve().parent.parent / "slide2video"


def test_roots_default_to_the_vendors(monkeypatch):
    monkeypatch.delenv("LV_ELEVEN_ROOT", raising=False)
    monkeypatch.delenv("LV_GEMINI_ROOT", raising=False)
    assert config.eleven_root() == "https://api.elevenlabs.io/v1"
    assert config.gemini_root() == "https://generativelanguage.googleapis.com/v1beta"


def test_roots_ignore_blank_and_trailing_slash(monkeypatch):
    monkeypatch.setenv("LV_ELEVEN_ROOT", " ")
    monkeypatch.setenv("LV_GEMINI_ROOT", "https://proxy.test/g/")
    assert config.eleven_root() == "https://api.elevenlabs.io/v1"
    assert config.gemini_root() == "https://proxy.test/g"
    assert clips.retarget("https://generativelanguage.googleapis.com/v1beta/files/a:download?alt=media") == \
        "https://proxy.test/g/files/a:download?alt=media"
    assert clips.retarget("https://other.test/x") == "https://other.test/x"


def test_no_module_formats_a_vendor_constant_directly():
    for f in ("narrate.py", "keys.py", "music.py", "clips.py"):
        text = (PLUGIN / "scripts/lv" / f).read_text(encoding="utf-8")
        assert "config.ELEVEN_ROOT}" not in text and "config.GEMINI_ROOT}" not in text, f
