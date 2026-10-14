import io
import subprocess
import sys

from conftest import PLUGIN
from lv import cli, net


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
    env = {"PYTHONIOENCODING": "cp1252", "LESSON_VIDEOS_HOME": str(tmp_path), "PATH": __import__("os").environ["PATH"],
           "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")}
    r = subprocess.run([sys.executable, str(PLUGIN / "scripts/lesson-videos.py"), "keys", "check"], capture_output=True, env=env)
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
