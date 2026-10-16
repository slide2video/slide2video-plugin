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
    assert "User to Access" in rows[0][2] and "credits" in rows[0][2]


def test_check_names_blocked_domain_behind_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy:3128")
    monkeypatch.setenv("ELEVENLABS_API_KEY", EL)
    def fake(url, headers=None, timeout=None, **kw):
        raise net.ApiError(0, "Tunnel connection failed: 403 Forbidden", url)
    msg = keys.check(request=fake)[0][2]
    assert "api.elevenlabs.io" in msg and "Settings → Capabilities" in msg and EL not in msg


def test_check_has_no_hint_without_proxy(monkeypatch):
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("https_proxy", raising=False)
    monkeypatch.setenv("ELEVENLABS_API_KEY", EL)
    def fake(url, headers=None, timeout=None, **kw):
        raise net.ApiError(0, "timed out", url)
    assert "Capabilities" not in keys.check(request=fake)[0][2]


import subprocess as _sp
import zipfile


class _Run:
    """Fake subprocess.run: first call returns the clipboard, later calls record the clear."""
    def __init__(self, clip, code=0):
        self.clip, self.code, self.calls = clip, code, []

    def __call__(self, cmd, **kw):
        self.calls.append((cmd, kw))
        out = self.clip if len(self.calls) == 1 else ""
        return _sp.CompletedProcess(cmd, self.code, out, "")


@pytest.mark.parametrize("clip", [EL, EL + "\n", EL + "\r\n", f'"{EL}"', f"  {EL}  "])
def test_paste_stores_clean_value_and_clears_clipboard(clip, capsys):
    run = _Run(clip)
    assert keys.paste("elevenlabs", run=run, platform="darwin") == ("ELEVENLABS_API_KEY", True)
    assert keys.parse(keys.keys_file().read_text(encoding="utf-8"))["ELEVENLABS_API_KEY"] == EL
    assert run.calls[0][0] == ["pbpaste"] and run.calls[1][0] == ["pbcopy"] and run.calls[1][1]["input"] == ""
    out = capsys.readouterr()
    assert EL not in out.out + out.err


class _NoClear(_Run):
    def __call__(self, cmd, **kw):
        if self.calls:
            self.calls.append((cmd, kw))
            raise FileNotFoundError(cmd[0])
        return super().__call__(cmd, **kw)


def test_paste_reports_when_clipboard_was_not_cleared():
    assert keys.paste("elevenlabs", run=_NoClear(EL), platform="darwin") == ("ELEVENLABS_API_KEY", False)
    assert keys.get("ELEVENLABS_API_KEY") == EL


def test_paste_reports_failed_clear_exit_code():
    class Fails(_Run):
        def __call__(self, cmd, **kw):
            r = super().__call__(cmd, **kw)
            return _sp.CompletedProcess(cmd, 1 if len(self.calls) > 1 else 0, r.stdout, "")
    assert keys.paste("elevenlabs", run=Fails(EL), platform="darwin") == ("ELEVENLABS_API_KEY", False)


def test_paste_refuses_non_key_without_echo():
    secret = "my bank password 1234"
    with pytest.raises(keys.UserError) as e:
        keys.paste("gemini", run=_Run(secret), platform="darwin")
    assert secret not in str(e.value) and "Gemini key" in str(e.value)
    assert not keys.keys_file().exists() or "1234" not in keys.keys_file().read_text(encoding="utf-8")


def test_paste_wrong_service_shape_refused():
    with pytest.raises(keys.UserError):
        keys.paste("elevenlabs", run=_Run(GM), platform="darwin")


@pytest.mark.parametrize("platform,read0", [("darwin", "pbpaste"), ("win32", "powershell"), ("linux", None)])
def test_clipboard_commands(platform, read0, monkeypatch):
    monkeypatch.setattr(keys.shutil, "which", lambda n: "/usr/bin/wl-paste" if n == "wl-paste" else None)
    read, clear = keys.clipboard_commands(platform)
    if read0:
        assert read[0] == read0
    else:
        assert read[0] == "wl-paste" and clear[0] == "wl-copy"


def test_store_replaces_existing_and_export_lines():
    keys.ensure_file().write_text('export ELEVENLABS_API_KEY="old_value_123"\nGEMINI_API_KEY=\n', encoding="utf-8")
    keys.store("ELEVENLABS_API_KEY", EL)
    text = keys.keys_file().read_text(encoding="utf-8")
    assert text.count("ELEVENLABS_API_KEY") == 1 and "old_value" not in text
    assert keys.parse(text)["ELEVENLABS_API_KEY"] == EL
    if os.name == "posix":
        assert oct(keys.keys_file().stat().st_mode & 0o777) == "0o600"


def test_load_imports_known_keys_only(tmp_path, capsys):
    f = tmp_path / "attached keys.txt"
    f.write_text(f"ELEVENLABS_API_KEY={EL}\nGEMINI_API_KEY=your-key-here\nOTHER=zzz\n", encoding="utf-8")
    assert keys.load(f) == ["ELEVENLABS_API_KEY"]
    assert keys.get("ELEVENLABS_API_KEY") == EL and keys.get("GEMINI_API_KEY", required=False) == ""
    assert EL not in capsys.readouterr().out


def test_load_reads_textedit_rtf(tmp_path):
    rtf = ("{\\rtf1\\ansi\\ansicpg1252\\cocoartf2822\n{\\fonttbl\\f0\\fswiss Helvetica;}\n\\f0\\fs24 \\cf0 "
           f"# slide2video API keys\\\nELEVENLABS_API_KEY={EL}\\\nGEMINI_API_KEY={GM}}}")
    f = tmp_path / "keys.rtf"
    f.write_bytes(rtf.encode("cp1252"))
    assert sorted(keys.load(f)) == ["ELEVENLABS_API_KEY", "GEMINI_API_KEY"]
    assert keys.get("GEMINI_API_KEY") == GM


def test_load_reads_zip_attachment(tmp_path):
    z = tmp_path / "6e14e5ed-slide2video-keys.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("__MACOSX/._slide2video-keys.txt", b"\x00\x05\x16\x07binary")
        zf.writestr("slide2video-keys.txt", f"ELEVENLABS_API_KEY={EL}\nGEMINI_API_KEY=\n")
    assert keys.load(z) == ["ELEVENLABS_API_KEY"]
    assert keys.get("ELEVENLABS_API_KEY") == EL


@pytest.mark.parametrize("encoding", ["utf-16", "utf-16-le", "utf-16-be"])
def test_load_reads_utf16_notepad_file(tmp_path, encoding):
    f = tmp_path / "keys.txt"
    f.write_bytes(f"ELEVENLABS_API_KEY={EL}\r\nGEMINI_API_KEY={GM}\r\n".encode(encoding))
    assert sorted(keys.load(f)) == ["ELEVENLABS_API_KEY", "GEMINI_API_KEY"]
    assert keys.get("GEMINI_API_KEY") == GM


def test_load_reads_curly_quoted_values(tmp_path):
    f = tmp_path / "keys.txt"
    f.write_text(f"ELEVENLABS_API_KEY=\u201c{EL}\u201d\nGEMINI_API_KEY = \u2018{GM}\u2019\n", encoding="utf-8")
    assert sorted(keys.load(f)) == ["ELEVENLABS_API_KEY", "GEMINI_API_KEY"]
    assert keys.get("ELEVENLABS_API_KEY") == EL and keys.get("GEMINI_API_KEY") == GM


def test_load_missing_file():
    with pytest.raises(keys.UserError):
        keys.load(keys.config.home() / "nope.txt")


def test_blocked_hint_allows_for_an_outage(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy:3128")
    hint = net.blocked_hint("api.elevenlabs.io")
    assert "if you haven't already" in hint.lower() and "try again later" in hint


def test_paste_without_clipboard_points_cowork_users_to_keys_load():
    def no_tool(cmd, **kw):
        raise FileNotFoundError(cmd[0])
    with pytest.raises(keys.UserError) as e:
        keys.paste("elevenlabs", run=no_tool, platform="linux")
    assert "keys load" in str(e.value)


def test_redact_hides_anthropic_tokens():
    from lv import keys as k
    tok = "sk-ant-oat01-AbCdEfGhIjKlMnOpQrStUvWxYz_0123-4567"
    out = k.redact(f"login failed with {tok} at 3pm")
    assert tok not in out and "sk-ant-" not in out and out.endswith("at 3pm")
    assert k.redact("sk-ant-short") == "sk-ant-short"  # too short to be a token
