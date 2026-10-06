import json

import pytest

from lv import narrate, net, tools
from lv.util import UserError, read_text


def test_cache_key_matches_original_build_py():
    # value computed with the Unit 1 build.py formula; old caches must stay valid
    assert narrate.cache_key("cgSgspJ2msm6clMCkdW9", "Hello there.") == "1dd3ed56061b"


def test_words_from_groups_characters():
    al = {"chars": list("Hi you"), "starts": [0, .1, .2, .3, .4, .5], "ends": [.1, .2, .3, .4, .5, .6]}
    assert narrate.words_from(al) == [{"w": "Hi", "s": 0, "e": 0.2}, {"w": "you", "s": 0.3, "e": 0.6}]


def test_build_timing_math():
    spec = {"chapter": "C", "title": "T", "scenes": [
        {"id": "a", "say": "x"}, {"id": "b", "say": "y", "lead": 1.0, "tail": 0.5, "hold": 2},
        {"id": "c", "min": 3}]}
    takes = {"a": (2.0, [{"w": "x", "s": 0.1, "e": 0.4}], "build/voice/a.mp3"), "b": (1.0, [], "build/voice/b.mp3")}
    T = narrate.build_timing(spec, takes)
    assert [s["start"] for s in T["scenes"]] == [0, 3.2, 7.7]
    assert [s["dur"] for s in T["scenes"]] == [3.2, 4.5, 3]
    assert T["scenes"][0]["words"] == [{"w": "x", "s": 0.6, "e": 0.9}]
    assert T["duration"] == 10.7 and T["scenes"][2]["audio"] is None


def test_narrate_writes_timing_and_track_and_caches(make_chapter, fake_speak):
    ch = make_chapter([{"id": "one", "say": "Hola, ¿qué tal?"}, {"id": "two", "say": "Water follows salt."}])
    T = narrate.narrate(ch, speak_fn=fake_speak)
    assert len(fake_speak.calls) == 2
    assert read_text(ch / "build/timing.js").startswith("window.TIMING = ")
    assert narrate.read_timing(ch)["duration"] == T["duration"]
    assert abs(tools.duration(ch / "build/narration.mp3") - T["duration"]) < 0.15
    narrate.narrate(ch, speak_fn=fake_speak)
    assert len(fake_speak.calls) == 2  # cached: no new takes


def test_no_speech_makes_silence(make_chapter, fake_speak):
    ch = make_chapter([{"id": "only", "min": 2}])
    T = narrate.narrate(ch, speak_fn=fake_speak)
    assert fake_speak.calls == [] and T["duration"] == 2
    assert abs(tools.duration(ch / "build/narration.mp3") - 2) < 0.15


def test_quota_error_keeps_finished_scenes(make_chapter, fake_speak):
    ch = make_chapter([{"id": f"s{i}", "say": f"Scene number {i}."} for i in range(4)])
    def flaky(text, voice, out):
        if text.endswith("3."):
            raise net.ApiError(401, '{"detail": {"status": "quota_exceeded"}}', "https://api.elevenlabs.io/v1/x")
        fake_speak(text, voice, out)
    with pytest.raises(UserError) as e:
        narrate.narrate(ch, speak_fn=flaky, workers=1)
    msg = str(e.value)
    assert "credits" in msg and "keys check" in msg and "saved" in msg
    assert len(list((ch / "build/voice").glob("*.mp3"))) == 3
