"""`narrate` and `render` return within about config.STEP_SECONDS and say to run them again, keeping what they made."""
import time

import pytest

from conftest import HELLO_JS
from lv import cli, config, narrate, page, paths, render, sfx, tools
from lv.util import NOT_FINISHED, NotFinished


def test_step_seconds_reads_the_override(monkeypatch):
    monkeypatch.delenv("LV_STEP_SECONDS", raising=False)
    assert config.step_seconds() == config.STEP_SECONDS
    assert config.STEP_SECONDS <= 210        # with the end of the last item, under the five-minute cache
    monkeypatch.setenv("LV_STEP_SECONDS", "12.5")
    assert config.step_seconds() == 12.5
    monkeypatch.setenv("LV_STEP_SECONDS", "0")
    assert config.step_seconds() is None
    monkeypatch.setenv("LV_STEP_SECONDS", "soon")
    assert config.step_seconds() == config.STEP_SECONDS


def test_cli_says_run_again_with_its_own_exit_code(monkeypatch, capsys):
    def stop(args):
        raise NotFinished("Narration isn't finished: 3 of 9 new scenes recorded so far.")
    monkeypatch.setattr(cli, "dispatch", stop)
    assert cli.main(["narrate", "ch1"]) == NOT_FINISHED == 3
    out = capsys.readouterr().out
    assert out.startswith("not finished: Narration isn't finished") and "Traceback" not in out


def test_narrate_stops_in_time_and_continues(make_chapter, fake_speak):
    narrate.narrate(make_chapter([{"id": "old", "say": "An older script."}]), speak_fn=fake_speak)
    ch = make_chapter([{"id": f"s{i}", "say": f"Scene number {i}."} for i in range(4)])  # the same folder, rewritten
    assert (ch / "build" / "timing.js").exists()

    def slow(text, voice, out):
        time.sleep(0.3)
        fake_speak(text, voice, out)
    with pytest.raises(NotFinished) as e:
        narrate.narrate(ch, speak_fn=slow, workers=1, seconds=0.4)
    assert "Run the same narrate command again" in str(e.value) and "left" in str(e.value)
    made = len(fake_speak.calls) - 1
    assert 1 <= made < 4
    assert not (ch / "build" / "timing.js").exists()   # an older timing would no longer match: render refuses
    T = narrate.narrate(ch, speak_fn=slow, workers=1, seconds=60)
    assert len(fake_speak.calls) - 1 == 4             # every scene recorded once
    assert len(T["scenes"]) == 4 and (ch / "build" / "timing.js").exists()


def test_narrate_always_makes_one_take(make_chapter, fake_speak):
    ch = make_chapter([{"id": "a", "say": "One."}, {"id": "b", "say": "Two."}])
    with pytest.raises(NotFinished):
        narrate.narrate(ch, speak_fn=fake_speak, workers=1, seconds=1e-6)
    assert len(fake_speak.calls) == 1
    with pytest.raises(NotFinished):
        narrate.narrate(make_chapter([{"id": "a", "say": "One."}, {"id": "b", "say": "Two."},
                                      {"id": "c", "say": "Three."}]), speak_fn=fake_speak, workers=1, seconds=1e-6)
    assert len(fake_speak.calls) == 2


def test_render_stops_in_time_and_resumes(make_chapter, fake_speak, browser_ok):
    sfx.build()
    ch = make_chapter([{"id": "hello", "say": "Hello there.", "min": 25}], HELLO_JS)
    narrate.narrate(ch, speak_fn=fake_speak)
    pieces = ch / "build" / "pieces"
    with pytest.raises(NotFinished) as e:
        render.render(ch, workers=1, fps=10, seconds=1e-6)   # past its deadline: one piece, then stop
    assert "1 of 3 pieces" in str(e.value) and "Run the same render command again" in str(e.value)
    assert sorted(f.name for f in pieces.glob("piece*.mp4")) == ["piece0000.mp4"]
    (ch / "scenes.js").write_text(HELLO_JS + "// changed\n", encoding="utf-8")
    with pytest.raises(NotFinished):
        render.render(ch, workers=2, fps=10, seconds=1e-6)   # scenes.js changed: the old piece is stale
    assert sorted(f.name for f in pieces.glob("piece*.mp4")) == ["piece0000.mp4", "piece0001.mp4"]
    out = render.render(ch, workers=1, fps=10, seconds=600)
    assert abs(tools.duration(out) - narrate.read_timing(ch)["duration"]) < 0.2
    assert {"video", "audio"} <= tools.streams(out)
    assert not pieces.exists()                            # the pieces go once the video is made


def test_render_pieces_follow_their_inputs(make_chapter, fake_speak, browser_ok):
    ch = make_chapter([{"id": "hello", "say": "Hello there.", "min": 12}], HELLO_JS)
    narrate.narrate(ch, speak_fn=fake_speak)
    p = paths.chapter(ch)
    page.ensure_page(ch)
    key = render._inputs_key(p, 10, 120, 100)
    assert key == render._inputs_key(p, 10, 120, 100)
    assert key != render._inputs_key(p, 30, 360, 300)
    (p.assets / "pic.jpg").parent.mkdir(parents=True, exist_ok=True)
    (p.assets / "pic.jpg").write_bytes(b"x")
    assert key != render._inputs_key(p, 10, 120, 100)
