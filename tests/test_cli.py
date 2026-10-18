import io
import subprocess
import sys

import pytest

from conftest import PLUGIN
from lv import cli, config, net


def test_keys_check_without_keys(capsys):
    assert cli.main(["keys", "check"]) == 0
    assert "✓ ElevenLabs: not set (optional): the free voice will be used" in capsys.readouterr().out


def test_unsupported_deck_no_traceback(tmp_path, capsys):
    deck = tmp_path / "deck.key"
    deck.write_bytes(b"x")
    assert cli.main(["ingest", str(deck)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: deck.key: export it as PowerPoint") and "Traceback" not in err


def test_api_error_is_printed_plainly(monkeypatch, capsys):
    def boom(args):
        raise net.ApiError(500, "server sad", "https://api.elevenlabs.io/v1/x")
    monkeypatch.setattr(cli, "dispatch", boom)
    assert cli.main(["keys"]) == 1
    assert "api.elevenlabs.io failed (500)" in capsys.readouterr().err


def test_cli_prints_unicode_on_cp1252(tmp_path):
    env = {"PYTHONIOENCODING": "cp1252", "LESSON_VIDEOS_HOME": str(tmp_path),
           "LESSON_VIDEOS_SETTINGS": str(tmp_path / "settings.json"), "PATH": __import__("os").environ["PATH"],
           "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")}
    r = subprocess.run([sys.executable, str(PLUGIN / "scripts/slide2video.py"), "keys", "check"], capture_output=True, env=env)
    assert r.returncode == 0 and "✓".encode("utf-8") in r.stdout


def test_open_uses_the_default_browser(monkeypatch, capsys):
    import webbrowser
    opened = []
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url) or True)
    assert cli.main(["open", "https://elevenlabs.io/app/settings/api-keys"]) == 0
    assert opened == ["https://elevenlabs.io/app/settings/api-keys"]


def test_keys_paste_cli_never_prints_key(monkeypatch, capsys):
    from lv import keys
    el = "sk_0123456789abcdef0123456789abcdef"
    monkeypatch.setattr(keys, "paste", lambda service: (keys.store("ELEVENLABS_API_KEY", el) and "ELEVENLABS_API_KEY", True))
    monkeypatch.setattr(keys, "check", lambda: [("ElevenLabs", True, "set, ends in …cdef; 9,000 characters left"),
                                                ("Gemini", True, "not set (optional)")])
    assert cli.main(["keys", "paste", "elevenlabs"]) == 0
    out = capsys.readouterr().out
    assert el not in out and "ElevenLabs" in out and "Gemini" not in out


def test_keys_paste_warns_when_env_wins(monkeypatch, capsys):
    from lv import keys
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_fromenvironment0000000000")
    monkeypatch.setattr(keys, "paste", lambda service: ("ELEVENLABS_API_KEY", True))
    monkeypatch.setattr(keys, "check", lambda: [("ElevenLabs", True, "ok"), ("Gemini", True, "ok")])
    cli.main(["keys", "paste", "elevenlabs"])
    assert "environment" in capsys.readouterr().out


def test_keys_paste_says_when_clipboard_still_holds_key(monkeypatch, capsys):
    from lv import keys
    monkeypatch.setattr(keys, "paste", lambda service: ("ELEVENLABS_API_KEY", False))
    monkeypatch.setattr(keys, "check", lambda: [("ElevenLabs", True, "ok"), ("Gemini", True, "ok")])
    cli.main(["keys", "paste", "elevenlabs"])
    out = capsys.readouterr().out
    assert "cleared the clipboard" not in out and "copy something else" in out


def test_keys_paste_needs_service(capsys):
    assert cli.main(["keys", "paste"]) == 1
    assert "keys paste elevenlabs" in capsys.readouterr().err


def test_keys_load_reports_nothing_found(tmp_path, capsys):
    f = tmp_path / "empty.txt"
    f.write_text("nothing here\n", encoding="utf-8")
    assert cli.main(["keys", "load", str(f)]) == 1
    assert "No keys found" in capsys.readouterr().out


def test_site_mode_refuses_risky_commands(monkeypatch, capsys):
    monkeypatch.setenv("LV_SITE_MODE", "1")
    for argv in (["open", "https://x"], ["keys", "load", "f"], ["pair"], ["worker"]):
        assert cli.main(argv) == 1
        assert "isn't available while working for slide2video.com" in capsys.readouterr().err
    cli.main(["keys", "check"])
    assert "isn't available while working" not in capsys.readouterr().err


def test_site_mode_keeps_paths_inside_the_lesson(monkeypatch, tmp_path, capsys):
    import json
    lesson = tmp_path / "lesson"
    (lesson / "site").mkdir(parents=True)
    (tmp_path / "outside.jpg").write_bytes(b"x")
    try:
        (lesson / "link.jpg").symlink_to(tmp_path / "outside.jpg")
    except OSError:
        pytest.skip("symlinks need Developer Mode on Windows")
    (lesson / "site" / "card.json").write_text(json.dumps(
        {"contract": 2, "kind": "questions", "message": "Q",
         "questions": [{"id": "g", "text": "Grade?", "options": [{"label": "6"}]}]}), encoding="utf-8")
    monkeypatch.chdir(lesson)
    monkeypatch.setenv("LV_SITE_MODE", "1")
    for argv in (["asset", "/etc/hosts", "x.jpg"],
                 ["render", "lesson-videos/_work/ch1", "--out", str(tmp_path / "elsewhere")],
                 ["asset", "link.jpg", "x.jpg"],
                 ["asset", "site/card.json", str(config.PLUGIN_ROOT / "x.jpg")]):
        assert cli.main(argv) == 1
        assert "is outside this lesson's folder" in capsys.readouterr().err
    assert cli.main(["card", "site/card.json"]) == 0
    capsys.readouterr()
    monkeypatch.delenv("LV_SITE_MODE")
    cli.main(["asset", "/etc/hosts", "x.jpg"])
    assert "is outside this lesson's folder" not in capsys.readouterr().err


def test_site_mode_refuses_a_registered_project(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LV_SITE_MODE", "1")
    monkeypatch.setenv("LESSON_VIDEOS_PROJECT", str(tmp_path))
    assert cli.main(["where"]) == 1
    assert "project folder can't be used" in capsys.readouterr().err


def test_site_mode_refuses_a_project_registered_in_settings(monkeypatch, tmp_path, capsys):
    import json
    settings = tmp_path / "prefs" / "planted.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"project": str(tmp_path / "elsewhere")}), encoding="utf-8")
    lesson = tmp_path / "lesson"
    lesson.mkdir()
    monkeypatch.chdir(lesson)
    monkeypatch.delenv("LESSON_VIDEOS_PROJECT", raising=False)
    monkeypatch.setenv("LESSON_VIDEOS_SETTINGS", str(settings))
    monkeypatch.setenv("LV_SITE_MODE", "1")
    assert cli.main(["where"]) == 1
    assert "A slide2video project folder can't be used while working for slide2video.com." in capsys.readouterr().err


def test_clip_name_cannot_leave_the_clips_folder(monkeypatch, tmp_path, capsys):
    import pytest
    from lv import clips
    monkeypatch.setattr(clips, "veo", lambda *a, **k: pytest.fail("no clip should be made"))
    (tmp_path / "photo.jpg").write_bytes(b"x")
    for site_mode in (False, True):
        if site_mode:
            monkeypatch.chdir(tmp_path)
            monkeypatch.setenv("LV_SITE_MODE", "1")
        for name in ("../x", "a/b", "a\\b", ".hidden", "..", "x..y/z"):
            assert cli.main(["clip", str(tmp_path / "photo.jpg"), "--work", str(tmp_path / "w"), "--name", name,
                             "--prompt", "p"]) == 1
            assert "clip name" in capsys.readouterr().err


def test_a_failed_migration_never_blocks_a_command(monkeypatch, capsys, tmp_path):
    from lv import config
    def boom():
        raise OSError("disk full")
    monkeypatch.setattr(config, "migrate_home", boom)
    assert cli.main(["where", str(tmp_path)]) == 0
    assert "couldn't copy the old lesson-videos settings" in capsys.readouterr().err
