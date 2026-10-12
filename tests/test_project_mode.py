import time

import pytest

from lv import estimate, mix, narrate, paths, status
from lv.util import write_json, write_text

SCENES = [{"id": "hello", "say": "Hello there, students.", "min": 1}, {"id": "bye", "say": "Bye now."}]


@pytest.fixture
def project_chapter(lv_project):
    ch = lv_project.lessons_dir / "biology" / "unit-2" / "ch1"
    write_json(ch / "script.json", {"chapter": "TEST", "title": "Test", "out": "Chapter 1 - Test.mp4",
                                    "music": "../music/bed.mp3", "scenes": SCENES})
    return ch


def test_narrate_project_mode(project_chapter, fake_speak):
    p = paths.chapter(project_chapter)
    T = narrate.narrate(project_chapter, speak_fn=fake_speak)
    assert sorted(f.name for f in project_chapter.iterdir()) == ["script.json"]   # nothing written into the repo
    assert len(list(p.voice.glob("*.mp3"))) == 2
    assert (p.build / "timing.js").exists() and (p.build / "narration.mp3").exists()
    assert all(s["audio"] and "/" not in s["audio"] for s in T["scenes"])
    narrate.narrate(project_chapter, speak_fn=fake_speak)
    assert len(fake_speak.calls) == 2                                             # second run: all cached


def test_cached_only_refuses_new_takes(make_chapter, fake_speak):
    ch = make_chapter(SCENES)
    with pytest.raises(narrate.NeedsNewTakes) as e:
        narrate.narrate(ch, speak_fn=fake_speak, cached_only=True)
    assert "hello" in str(e.value) and "bye" in str(e.value) and fake_speak.calls == []
    narrate.narrate(ch, speak_fn=fake_speak)
    narrate.narrate(ch, speak_fn=fake_speak, cached_only=True)                   # all cached: fine
    assert len(fake_speak.calls) == 2


def test_cached_only_never_falls_back_to_another_voice(make_chapter):
    ch = make_chapter(SCENES, narrator="edge")
    with pytest.raises(narrate.NeedsNewTakes):
        narrate.narrate(ch, cached_only=True)
    assert not (ch / "build" / "timing.js").exists()


def test_old_timing_audio_paths_still_mix(make_chapter, fake_speak):
    ch = make_chapter(SCENES)
    T = narrate.narrate(ch, speak_fn=fake_speak)
    for s in T["scenes"]:
        s["audio"] = "build/voice/" + s["audio"]                                  # how 0.2.0 wrote it
    assert narrate.narration_track(ch, T).exists()


def test_music_resolves_against_sources(project_chapter, make_chapter):
    p = paths.chapter(project_chapter)
    bed = p.sources.parent / "music" / "bed.mp3"
    write_text(bed, "x")
    assert mix.music_file(project_chapter, {"music": "../music/bed.mp3"}) == bed.resolve()
    teacher = make_chapter(SCENES)
    write_text(teacher.parent / "music" / "bed.mp3", "x")
    assert mix.music_file(teacher, {"music": "../music/bed.mp3"}) == (teacher.parent / "music" / "bed.mp3").resolve()
    assert mix.music_file(teacher, {}) is None


def test_status_and_estimate_project_mode(project_chapter, fake_speak):
    unit = project_chapter.parent
    assert status.stage(project_chapter) == "script written: run narrate"
    narrate.narrate(project_chapter, speak_fn=fake_speak)
    assert status.stage(project_chapter) == "narrated: write scenes.js"
    write_text(project_chapter / "scenes.js", "")
    assert status.stage(project_chapter) == "scenes written: check stills, then render"
    time.sleep(0.01)
    write_text(paths.chapter(project_chapter).out / "Chapter 1 - Test.mp4", "x")
    assert status.stage(project_chapter) == "done: Chapter 1 - Test.mp4"
    assert [c.name for c in status.chapters(unit)] == ["ch1"]
    assert estimate.chars_in_scripts(unit) == len("Hello there, students.") + len("Bye now.")


def test_status_survives_a_wiped_cache(project_chapter, fake_speak):
    import shutil
    p = paths.chapter(project_chapter)
    narrate.narrate(project_chapter, speak_fn=fake_speak)
    write_text(project_chapter / "scenes.js", "")
    out = p.out / "Chapter 1 - Test.mp4"
    write_text(out, "x")
    status.mark_rendered(project_chapter, out)
    shutil.rmtree(p.build)
    assert status.stage(project_chapter) == "done: Chapter 1 - Test.mp4"
    write_text(project_chapter / "scenes.js", "// changed")
    assert status.stage(project_chapter) == "script written: run narrate"
