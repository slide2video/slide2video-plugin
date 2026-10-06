import io
import subprocess
import sys

from conftest import PLUGIN
from lv import cli, net


def test_keys_check_without_keys(capsys):
    assert cli.main(["keys", "check"]) == 1
    assert "✗ ElevenLabs: missing (required)" in capsys.readouterr().out


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
    assert r.returncode == 1 and "✗".encode("utf-8") in r.stdout
