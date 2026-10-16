import os
import sys
import time
from pathlib import Path

import pytest

from lv import config, ingest, project, worker
from lv.util import read_text, write_text


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Path.home() is a temp folder, and the test env overrides that pick the folders are removed."""
    home = tmp_path / "User Home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    for var in ("LESSON_VIDEOS_HOME", "LESSON_VIDEOS_SETTINGS", "LV_LESSONS_DIR", "APPDATA", "LOCALAPPDATA",
                "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
        monkeypatch.delenv(var, raising=False)
    return home


def test_home_is_dot_slide2video(fake_home):
    assert config.home() == fake_home / ".slide2video"


def test_first_run_copies_the_old_home_and_leaves_it(fake_home):
    old = fake_home / ".lesson-videos"
    write_text(old / "keys.env", "ELEVENLABS_API_KEY=abc\n")
    write_text(old / "site-token.json", "{}")
    os.chmod(old / "site-token.json", 0o600)
    (old / "sfx").mkdir()
    config.migrate_home()
    new = fake_home / ".slide2video"
    assert read_text(new / "keys.env") == "ELEVENLABS_API_KEY=abc\n"
    assert (new / "sfx").is_dir()
    assert (old / "keys.env").is_file()                                   # old folder untouched
    if sys.platform != "win32":
        assert (new / "site-token.json").stat().st_mode & 0o777 == 0o600   # still owner-only
    assert not list(fake_home.glob(".slide2video*.partial*"))              # no leftovers


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need admin rights on Windows")
def test_a_symlinked_keys_file_stays_a_symlink(fake_home, tmp_path):
    secret = tmp_path / "secrets" / "keys.env"
    write_text(secret, "GEMINI_API_KEY=x\n")
    old = fake_home / ".lesson-videos"
    old.mkdir()
    (old / "keys.env").symlink_to(secret)
    config.migrate_home()
    link = fake_home / ".slide2video" / "keys.env"
    assert link.is_symlink() and link.resolve() == secret.resolve()


def test_nothing_is_copied_when_the_new_home_exists(fake_home):
    write_text(fake_home / ".lesson-videos" / "keys.env", "OLD\n")
    write_text(fake_home / ".slide2video" / "keys.env", "NEW\n")
    config.migrate_home()
    assert read_text(fake_home / ".slide2video" / "keys.env") == "NEW\n"


def test_nothing_happens_without_an_old_home(fake_home):
    config.migrate_home()
    assert not (fake_home / ".slide2video").exists()


def test_an_explicit_home_is_never_migrated(fake_home, tmp_path, monkeypatch):
    monkeypatch.setenv("LESSON_VIDEOS_HOME", str(tmp_path / "elsewhere"))
    write_text(fake_home / ".lesson-videos" / "keys.env", "OLD\n")
    config.migrate_home()
    assert not (tmp_path / "elsewhere").exists() and not (fake_home / ".slide2video").exists()


def test_a_leftover_partial_copy_is_replaced(fake_home):
    write_text(fake_home / ".lesson-videos" / "keys.env", "OLD\n")
    write_text(fake_home / ".slide2video.partial-123" / "half", "x")      # an earlier run was interrupted
    two_hours_ago = time.time() - 7200
    os.utime(fake_home / ".slide2video.partial-123", (two_hours_ago, two_hours_ago))
    config.migrate_home()
    assert read_text(fake_home / ".slide2video" / "keys.env") == "OLD\n"
    assert not (fake_home / ".slide2video" / "half").exists()
    assert not (fake_home / ".slide2video.partial-123").exists()


def test_a_fresh_partial_of_another_run_is_left_alone(fake_home):
    write_text(fake_home / ".lesson-videos" / "keys.env", "OLD\n")
    write_text(fake_home / ".slide2video.partial-live" / "x" / "half", "x")   # another process is copying right now
    config.migrate_home()
    assert (fake_home / ".slide2video.partial-live" / "x" / "half").exists()
    assert read_text(fake_home / ".slide2video" / "keys.env") == "OLD\n"


def test_the_settings_file_is_copied(fake_home):
    old = project.old_settings_file()
    write_text(old, '{"project": "/somewhere"}')
    config.migrate_home()
    assert project.settings_file() != old
    assert read_text(project.settings_file()) == '{"project": "/somewhere"}'
    assert old.is_file()


def test_old_results_and_cache_folders_keep_being_used(fake_home):
    base = fake_home / ("Movies" if sys.platform == "darwin" else "Videos")
    assert project.default_results() == base / "slide2video"
    (base / "Lesson Videos").mkdir(parents=True)
    assert project.default_results() == base / "Lesson Videos"
    new_cache = project.cache_dir()
    assert "slide2video" in new_cache.as_posix()
    old_cache = Path(new_cache.as_posix().replace("slide2video", "lesson-videos"))
    old_cache.mkdir(parents=True)
    assert project.cache_dir() == old_cache


def test_the_worker_keeps_an_existing_lesson_videos_folder(fake_home):
    assert worker.lessons_root() == fake_home / "slide2video"
    (fake_home / "Lesson Videos").mkdir()
    assert worker.lessons_root() == fake_home / "Lesson Videos"


def test_a_chat_run_resumes_an_old_work_folder(tmp_path):
    deck = tmp_path / "Unit 1" / "deck.pptx"
    write_text(deck, "x")
    assert ingest.default_work(deck) == deck.parent.resolve() / "slide2video" / "_work"
    (deck.parent / "lesson-videos" / "_work").mkdir(parents=True)
    assert ingest.default_work(deck) == deck.parent.resolve() / "lesson-videos" / "_work"


def test_every_command_migrates_first(fake_home, monkeypatch, capsys):
    from lv import cli
    write_text(fake_home / ".lesson-videos" / "keys.env", "ELEVENLABS_API_KEY=abc\n")
    cli.main(["where", str(fake_home)])
    assert (fake_home / ".slide2video" / "keys.env").is_file()
