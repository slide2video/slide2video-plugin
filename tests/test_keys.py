import os
import sys

import pytest

from lv import keys, net

EL = "sk_0123456789abcdef0123456789abcdef"
GM = "AIzaSyD-abcdefghijklmnopqrstuvwxyz12345"


def test_parse_handles_comments_quotes_export_bom_crlf():
    text = "﻿# comment\r\nexport ELEVENLABS_API_KEY=\"abc123456789\"\r\nGEMINI_API_KEY='zz'\r\n\r\nNOEQUALS\r\n"
    assert keys.parse(text) == {"ELEVENLABS_API_KEY": "abc123456789", "GEMINI_API_KEY": "zz"}


def test_env_wins_over_file(monkeypatch):
    keys.ensure_file().write_text("ELEVENLABS_API_KEY=fromfile12345\n", encoding="utf-8")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fromenv123456")
    assert keys.get("ELEVENLABS_API_KEY") == "fromenv123456"


def test_file_used_and_placeholder_ignored(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "your-key-here")
    keys.ensure_file().write_text("ELEVENLABS_API_KEY=fromfile12345\n", encoding="utf-8")
    assert keys.get("ELEVENLABS_API_KEY") == "fromfile12345"


def test_missing_key_message_names_the_fix():
    with pytest.raises(keys.MissingKey) as e:
        keys.get("ELEVENLABS_API_KEY")
    assert "`keys`" in str(e.value) and "keys check" in str(e.value)
    assert keys.get("GEMINI_API_KEY", required=False) == ""


def test_mask_and_redact(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", EL)
    assert keys.mask(EL) == "set, ends in …cdef"
    assert EL not in keys.redact(f"bad key {EL} and {GM}")
    assert GM not in keys.redact(f"bad key {GM}")


def test_ensure_file_creates_template_once(lv_home):
    f = keys.ensure_file()
    assert f == lv_home / "keys.env"
    assert "ELEVENLABS_API_KEY=" in f.read_text(encoding="utf-8")
    f.write_text("ELEVENLABS_API_KEY=kept\n", encoding="utf-8")
    keys.ensure_file()
    assert f.read_text(encoding="utf-8") == "ELEVENLABS_API_KEY=kept\n"
    if os.name == "posix":
        assert oct(f.stat().st_mode & 0o777) == "0o600"


@pytest.mark.parametrize("platform,first", [("darwin", "open"), ("win32", "notepad.exe"), ("linux", "xdg-open")])
def test_editor_command(tmp_path, platform, first):
    cmd = keys.editor_command(tmp_path / "keys.env", platform)
    assert cmd[0] == first and cmd[-1].endswith("keys.env")


def test_check_reports_credits_without_leaking(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", EL)
    def fake(url, headers=None, timeout=None, **kw):
        assert headers["xi-api-key"] == EL
        return {"character_limit": 30000, "character_count": 1234, "tier": "starter"}
    rows = keys.check(request=fake)
    text = repr(rows)
    assert EL not in text
    assert rows[0][1] is True and "28,766 characters left" in rows[0][2]
    assert rows[1] == ("Gemini", True, "not set (optional): no music, no AI clips")


def test_check_rejected_key_without_leaking(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", EL)
    monkeypatch.setenv("GEMINI_API_KEY", GM)
    def fake(url, headers=None, timeout=None, **kw):
        raise net.ApiError(401, f'{{"detail": "invalid_api_key {EL}"}}', url)
    rows = keys.check(request=fake)
    assert [r[1] for r in rows] == [False, False]
    assert EL not in repr(rows) and GM not in repr(rows)
    assert "rejected" in rows[0][2]


def test_check_missing_permission(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", EL)
    def fake(url, headers=None, timeout=None, **kw):
        raise net.ApiError(401, '{"detail": {"status": "missing_permissions", "message": "user_read"}}', url)
    rows = keys.check(request=fake)
    assert rows[0][1] is True  # authenticated: narration still works, only the credit count is hidden
    assert "User → Read" in rows[0][2] and "credits" in rows[0][2]
