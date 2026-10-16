from pathlib import Path

import pytest

from lv import paths
from lv.util import UserError


def test_teacher_mode_in_work_folder(tmp_path):
    ch = tmp_path / "Unit 1" / "slide2video" / "_work" / "ch1"
    p = paths.chapter(ch)
    assert (p.code, p.sources, p.build, p.voice) == (ch, ch, ch / "build", ch / "build" / "voice")
    assert p.assets == ch / "assets" and p.out == ch.parent.parent and not p.project
    les = paths.lesson(ch.parent)
    assert (les.code, les.sources, les.work, les.out) == (ch.parent, ch.parent, ch.parent, ch.parent.parent)


def test_teacher_mode_loose_chapter(tmp_path):
    ch = tmp_path / "somewhere" / "ch1"
    assert paths.chapter(ch).out == ch / "out"


def test_project_mode(lv_project, tmp_path):
    ch = lv_project.lessons_dir / "biology" / "unit-2" / "ch1"
    p = paths.chapter(ch)
    unit = tmp_path / "My Movies" / "lessons" / "biology" / "unit-2"
    assert p.project and p.lesson_id == "biology/unit-2"
    assert p.code == ch
    assert p.sources == unit / "_source" / "ch1" and p.assets == unit / "_source" / "ch1" / "assets"
    assert p.voice == unit / "_source" / "ch1" / "voice"
    assert p.build == tmp_path / "cache dir" / "work" / "lessons" / "biology" / "unit-2" / "ch1"
    assert p.out == unit
    les = paths.lesson(ch.parent)
    assert les.sources == unit / "_source" and les.out == unit
    assert les.work == tmp_path / "cache dir" / "work" / "lessons" / "biology" / "unit-2"


def test_relative_path_resolves(lv_project, monkeypatch):
    unit = lv_project.lessons_dir / "biology" / "unit-2"
    (unit / "ch1").mkdir(parents=True)
    monkeypatch.chdir(unit)
    assert paths.chapter(Path("ch1")) == paths.chapter(unit / "ch1")
    assert paths.chapter(Path("ch1/")) == paths.chapter(unit / "ch1")
    assert paths.lesson(Path(".")) == paths.lesson(unit)


def test_outside_the_project_is_teacher_mode(lv_project, tmp_path):
    ch = tmp_path / "Desktop" / "slide2video" / "_work" / "ch1"
    assert not paths.chapter(ch).project and paths.chapter(ch).build == ch / "build"


def test_lessons_root_is_not_a_lesson(lv_project):
    with pytest.raises(UserError) as e:
        paths.lesson(lv_project.lessons_dir)
    assert "<course>/<unit>" in str(e.value)
    with pytest.raises(UserError):
        paths.chapter(lv_project.lessons_dir / "ch1")


def test_custom_lessons_dir(tmp_path, monkeypatch):
    from lv.util import write_text
    write_text(tmp_path / "p/config.yaml", f"lessons_dir: teaching\nresults_dir: {(tmp_path / 'r').as_posix()}\n")
    monkeypatch.setenv("LESSON_VIDEOS_PROJECT", str(tmp_path / "p"))
    p = paths.chapter(tmp_path / "p" / "teaching" / "chem" / "unit-1" / "ch3")
    assert p.lesson_id == "chem/unit-1" and p.out == tmp_path / "r" / "lessons" / "chem" / "unit-1"


def test_unregistered_project_refuses_instead_of_teacher_mode(tmp_path):
    from lv.util import write_text
    write_text(tmp_path / "moved repo/config.yaml", "artist: Someone\nlessons_dir: lessons\n")
    ch = tmp_path / "moved repo" / "lessons" / "biology" / "unit-2" / "ch1"
    with pytest.raises(UserError) as e:
        paths.chapter(ch)
    assert "init --path" in str(e.value) and "moved repo" in str(e.value)


def test_config_without_lessons_dir_is_not_a_project(tmp_path):
    from lv.util import write_text
    write_text(tmp_path / "music only/config.yaml", "artist: Someone\n")
    ch = tmp_path / "music only" / "lessons" / "x" / "ch1"
    assert not paths.chapter(ch).project


def test_case_variant_path_on_case_insensitive_disk(lv_project):
    unit = lv_project.lessons_dir / "biology" / "unit-2"
    (unit / "ch1").mkdir(parents=True)
    variant = Path(str(lv_project.lessons_dir).replace("/lessons", "/LESSONS")) / "biology" / "unit-2" / "ch1"
    if not variant.exists():
        pytest.skip("case-sensitive file system")
    p = paths.chapter(variant)
    assert p.project and p.lesson_id == "biology/unit-2" and p.voice == paths.chapter(unit / "ch1").voice


def test_unreadable_config_above_a_deck_is_ignored(tmp_path):
    from lv.util import write_text
    write_text(tmp_path / "Documents/config.yaml", "this: [is not yaml\n")
    ch = tmp_path / "Documents" / "Biology" / "slide2video" / "_work" / "ch1"
    assert paths.chapter(ch).build == ch / "build"
