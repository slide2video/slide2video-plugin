import os
import sys

import pytest

from conftest import HELLO_JS
from lv import narrate, net, render, sfx, tools, voices
from lv.util import UserError, read_json


def test_chain_without_key_uses_free_voices(monkeypatch):
    assert voices.chain({}) == ["edge", "system", "none"]
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_0123456789abcdef0123")
    assert voices.chain({}) == ["elevenlabs", "edge", "system", "none"]
    assert voices.chain({"narrator": "elevenlabs"}) == ["elevenlabs"]
    assert voices.chain({"narrator": "system"}) == ["system", "none"]
    with pytest.raises(UserError):
        voices.chain({"narrator": "robot"})


def test_estimate_words_spans_the_take_with_pauses():
    words = voices.estimate_words("Step one. Then two, then three.", 4.0)
    assert [w["w"] for w in words] == ["Step", "one.", "Then", "two,", "then", "three."]
    assert words[0]["s"] >= 0 and words[-1]["e"] <= 4.0
    assert all(a["e"] <= b["s"] for a, b in zip(words, words[1:]))
    gap_after_sentence = words[2]["s"] - words[1]["e"]
    gap_inside = words[1]["s"] - words[0]["e"]
    assert gap_after_sentence > gap_inside


def test_align_events_keeps_script_punctuation_and_splits_merged_events():
    text = "In 2024, water evaporates. Twelve percent!"
    events = [(0.1, 0.6, "In 2024"), (0.8, 0.3, "water"), (1.2, 0.6, "evaporates"), (2.0, 0.4, "Twelve"), (2.5, 0.5, "percent")]
    words = voices.align_events(text, events)
    assert [w["w"] for w in words] == ["In", "2024,", "water", "evaporates.", "Twelve", "percent!"]
    assert words[0]["s"] == 0.1 and words[1]["e"] == 0.7 and words[3]["s"] == 1.2


def test_align_events_gives_up_on_mismatch():
    assert voices.align_events("Twelve percent", [(0.0, 1.0, "12%")]) is None


def _fail(*a, **k):
    raise voices.VoiceUnavailable("offline in this test")


def _fake_voice(text, voice, out):
    from conftest import _silence
    _silence(out, 0.05 * len(text))
    return voices.estimate_words(text, 0.05 * len(text))


def test_narrate_falls_back_to_the_next_voice(make_chapter, monkeypatch, capsys):
    monkeypatch.setitem(voices.SPEAKERS, "edge", _fail)
    monkeypatch.setitem(voices.SPEAKERS, "system", _fake_voice)
    ch = make_chapter([{"id": "a", "say": "Water follows salt."}])
    T = narrate.narrate(ch)
    assert T["narrator"] == "system" and T["scenes"][0]["audio"]
    assert "Using this computer's own voice" in capsys.readouterr().out
    assert read_json(next((ch / "build/voice").glob("*.json")))["words"][0]["w"] == "Water"


def test_elevenlabs_failure_in_auto_mode_falls_back(make_chapter, monkeypatch, capsys):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_0123456789abcdef0123")
    def quota(text, voice, out):
        raise net.ApiError(401, '{"detail": {"status": "quota_exceeded", "message": "You have 0 credits remaining."}}', "https://api.elevenlabs.io/v1/x")
    monkeypatch.setattr(narrate, "speak", quota)
    monkeypatch.setitem(voices.SPEAKERS, "edge", _fake_voice)
    ch = make_chapter([{"id": "a", "say": "Hello."}])
    assert narrate.narrate(ch)["narrator"] == "edge"
    assert "0 credits remaining" in capsys.readouterr().out


def test_captions_only_when_no_voice_works_still_renders(make_chapter, monkeypatch, browser_ok):
    monkeypatch.setitem(voices.SPEAKERS, "edge", _fail)
    monkeypatch.setitem(voices.SPEAKERS, "system", _fail)
    sfx.build()
    ch = make_chapter([{"id": "hello", "say": "One drop of water travels around the whole planet."}], HELLO_JS)
    T = narrate.narrate(ch)
    assert T["narrator"] == "none" and T["scenes"][0]["audio"] is None
    assert T["scenes"][0]["speech"] >= 3 and T["scenes"][0]["words"][-1]["w"] == "planet."
    out = render.render(ch, workers=1)
    assert {"video", "audio"} <= tools.streams(out) and abs(tools.duration(out) - T["duration"]) < 0.2


@pytest.mark.skipif(sys.platform not in ("darwin", "win32"), reason="built-in voice tested on macOS and Windows")
def test_system_voice_live(tmp_path):
    words = voices.SPEAKERS["system"]("Water follows salt.", "", tmp_path / "take.mp3")
    assert tools.duration(tmp_path / "take.mp3") > 0.5 and [w["w"] for w in words] == ["Water", "follows", "salt."]


@pytest.mark.skipif(not os.environ.get("LV_LIVE_TESTS"), reason="set LV_LIVE_TESTS=1 to call the free Microsoft voice")
def test_edge_voice_live(tmp_path):
    words = voices.SPEAKERS["edge"]("Step one is evaporation.", "en-US-AvaMultilingualNeural", tmp_path / "take.mp3")
    assert [w["w"] for w in words] == ["Step", "one", "is", "evaporation."] and words[0]["s"] < 0.5
