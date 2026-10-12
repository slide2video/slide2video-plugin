import json
from pathlib import Path

import pytest

from lv import project
from lv.util import UserError, read_text, write_text


def test_no_project_by_default():
    assert project.load_project() is None


def test_init_writes_config_and_remembers(tmp_path):
    p, created = project.init_project(tmp_path / "My Lessons")
    assert created
    home = (tmp_path / "My Lessons").resolve()
    assert "lessons_dir: lessons" in read_text(home / "config.yaml")
    assert json.loads(read_text(project.settings_file()))["project"] == str(home)
    assert (home / "lessons").is_dir()
    again = project.load_project()
    assert again == p and again.lessons_dir == home / "lessons"
    assert again.work_dir == project.cache_dir() / "work"


def test_init_keeps_existing_config(tmp_path):
    home = tmp_path / "proj"
    write_text(home / "config.yaml", "artist: Someone\nresults_dir: ~/Somewhere Else\n")
    p, created = project.init_project(home)
    assert not created
    assert read_text(home / "config.yaml") == "artist: Someone\nresults_dir: ~/Somewhere Else\n"
    assert p.results_dir == Path.home() / "Somewhere Else"
    assert p.lessons_dir == home.resolve() / "lessons"


def test_env_names_the_project(tmp_path, monkeypatch):
    write_text(tmp_path / "a/config.yaml", "lessons_dir: teaching\nwork_dir: build-cache\n")
    monkeypatch.setenv("LESSON_VIDEOS_PROJECT", str(tmp_path / "a"))
    p = project.load_project()
    assert p.lessons_dir == (tmp_path / "a").resolve() / "teaching"
    assert p.work_dir == (tmp_path / "a").resolve() / "build-cache"


def test_bad_settings_file(tmp_path):
    write_text(project.settings_file(), "{not json")
    with pytest.raises(UserError) as e:
        project.load_project()
    assert "settings.json" in str(e.value)


def test_bad_config_yaml(tmp_path, monkeypatch):
    write_text(tmp_path / "p/config.yaml", "lessons_dir: [unclosed\n")
    monkeypatch.setenv("LESSON_VIDEOS_PROJECT", str(tmp_path / "p"))
    with pytest.raises(UserError) as e:
        project.load_project()
    assert "config.yaml" in str(e.value)


def test_missing_project_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSON_VIDEOS_PROJECT", str(tmp_path / "gone"))
    p = project.load_project()
    assert p is not None and not p.exists
    assert p.lessons_dir == (tmp_path / "gone").resolve() / "lessons"


def test_fixture_project(lv_project, tmp_path):
    assert lv_project.results_dir == tmp_path / "My Movies"
    assert lv_project.work_dir == tmp_path / "cache dir" / "work"
