from pathlib import Path

from lv import clips, config, narrate

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
    seen = []
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyD-abcdefghijklmnopqrstuvwxyz12345")
    video = {"steps": [{"type": "model_output", "content": [{"type": "video", "data": "TVA0"}]}]}
    assert clips.omni(b"png", "p", request=lambda url, **kw: seen.append(url) or video) == b"MP4"
    assert seen == ["https://proxy.test/g/interactions"]   # the clip goes where LV_GEMINI_ROOT says


def test_no_module_formats_a_vendor_constant_directly():
    for f in ("narrate.py", "keys.py", "music.py", "clips.py"):
        text = (PLUGIN / "scripts/lv" / f).read_text(encoding="utf-8")
        assert "config.ELEVEN_ROOT}" not in text and "config.GEMINI_ROOT}" not in text, f


def test_eleven_root_reaches_the_narration_request(monkeypatch, tmp_path):
    monkeypatch.setenv("LV_ELEVEN_ROOT", "https://proxy.test/el/")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_0123456789abcdef0123")
    seen = []

    def request(url, **kw):
        seen.append(url)
        return {"audio_base64": "", "alignment": {}}
    monkeypatch.setattr(narrate.net, "request", request)
    narrate.speak("Hello.", "voice1", tmp_path / "a.mp3")
    assert seen and seen[0].startswith("https://proxy.test/el/text-to-speech/voice1/")
