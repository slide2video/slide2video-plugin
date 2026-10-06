import pytest

from conftest import HELLO_JS
from lv import narrate, page, render, sfx, tools
from lv.util import UserError, read_text


def test_output_path_layout(make_chapter):
    ch = make_chapter([{"id": "a", "min": 1}], out="Entry 5/6: Keys.mp4")
    assert page.output_dir(ch) == ch.parent.parent
    assert page.output_path(ch, {"out": "Entry 5/6: Keys.mp4"}).name == "Entry 5-6- Keys.mp4"


def test_stills_and_render(make_chapter, fake_speak, browser_ok):
    sfx.build()
    ch = make_chapter([{"id": "hello", "say": "Hello there, students.", "min": 2}], HELLO_JS)
    narrate.narrate(ch, speak_fn=fake_speak)
    sheet = render.stills(ch, [0.5, 1.5])
    assert sheet.exists() and len(list((ch / "build/stills").glob("t*.jpg"))) == 2
    out = render.render(ch, workers=2)
    assert out == ch.parent.parent / "Chapter 1 - Test.mp4"
    assert abs(tools.duration(out) - narrate.read_timing(ch)["duration"]) < 0.2
    assert {"video", "audio"} <= tools.streams(out)
    assert read_text(out.with_suffix(".vtt")).startswith("WEBVTT")
    assert (ch / "build" / "final.jpg").exists()  # frames from the finished MP4, for the last visual check


def test_render_reports_page_error(make_chapter, fake_speak, browser_ok):
    ch = make_chapter([{"id": "hello", "min": 1}], "throw new Error('boom in scenes');\n")
    narrate.narrate(ch, speak_fn=fake_speak)
    with pytest.raises(UserError) as e:
        render.stills(ch, [0.5])
    assert "boom in scenes" in str(e.value)


def test_render_reports_missing_asset(make_chapter, fake_speak, browser_ok):
    js = "Engine.assets({ pic: 'assets/nope.jpg' });\n" + HELLO_JS
    ch = make_chapter([{"id": "hello", "min": 1}], js)
    narrate.narrate(ch, speak_fn=fake_speak)
    with pytest.raises(UserError) as e:
        render.render(ch, workers=1)
    assert "assets/nope.jpg" in str(e.value)


def test_render_needs_narration_first(make_chapter):
    ch = make_chapter([{"id": "hello", "min": 1}], HELLO_JS)
    with pytest.raises(UserError) as e:
        render.render(ch)
    assert "narrate" in str(e.value)


def test_wander_spreads_particles(make_chapter, fake_speak, browser_ok):
    ch = make_chapter([{"id": "hello", "min": 1}], HELLO_JS)
    narrate.narrate(ch, speak_fn=fake_speak)
    page.ensure_page(ch)
    with render.page_for(ch) as (pg, logs):
        xs = pg.evaluate("[...Array(20)].map((_, i) => Engine.wander(i, 0, {x: 0, y: 0, w: 1000, h: 1000}, 3)[0])")
    assert max(xs) - min(xs) > 600, xs


@pytest.mark.parametrize("js,needle", [
    ("scene('hello', (g, t, s) => { Engine.clip(g, 'assets/clip_nope', 192, t, 0, 0, 640, 360); });\n", "assets/clip_nope/"),
    ("scene('hello', (g, t, s) => { Engine.img(g, 'nokey', 0, 0, 640, 360); });\n", '"nokey"'),
    ("scene('other', (g, t, s) => {});\n", 'no scene() for "hello"'),
])
def test_render_reports_silent_gray(make_chapter, fake_speak, browser_ok, js, needle):
    ch = make_chapter([{"id": "hello", "min": 1}], js)
    narrate.narrate(ch, speak_fn=fake_speak)
    with pytest.raises(UserError) as e:
        render.stills(ch, [0.5])
    assert needle in str(e.value)


def test_render_builds_sound_effects_when_missing(make_chapter, fake_speak, browser_ok, capsys, lv_home):
    assert not (lv_home / "sfx").exists()
    ch = make_chapter([{"id": "hello", "min": 1}], HELLO_JS)
    narrate.narrate(ch, speak_fn=fake_speak)
    render.render(ch, workers=1)
    assert "unknown sound effects skipped" not in capsys.readouterr().out
