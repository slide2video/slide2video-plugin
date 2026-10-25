import pytest

import lv

from lv import cli, net, site
from lv.util import UserError


def test_site_url_defaults_to_slide2video(monkeypatch):
    monkeypatch.delenv("LV_SITE_URL", raising=False)
    assert site.site_url() == "https://slide2video.com"


def test_pair_waits_for_the_code_then_stores_the_token(fake_site):
    lines = []
    email = site.pair(name="Test Mac", sleep=lambda s: None, out=lines.append)
    assert email == "user@example.org"
    assert site.store.get(fake_site.url) == fake_site.token
    assert any("ABC-123" in l for l in lines) and any("/devices" in l for l in lines)
    assert not any(fake_site.token in l for l in lines)


def test_pair_expired_code(fake_site):
    fake_site.pair_expired = True
    with pytest.raises(UserError) as e:
        site.pair(name="Test Mac", sleep=lambda s: None, out=lambda s: None)
    assert "expired" in str(e.value)


def test_call_without_token_says_connect(fake_site):
    with pytest.raises(UserError) as e:
        site.call("/api/device/status")
    assert e.value.args[0] == site.not_paired()


def test_revoked_token_says_connect(paired):
    site.store.set(paired.url, "s2v_revoked")
    with pytest.raises(UserError) as e:
        site.call("/api/device/status")
    assert e.value.args[0] == site.not_paired()


def test_contract_mismatch_says_update(paired):
    paired.contract = 3
    with pytest.raises(UserError) as e:
        site.call("/api/device/status")
    assert "/plugin update slide2video" in str(e.value)


def test_empty_204_is_an_empty_dict(paired):
    assert site.call("/api/device/next") == {}


def test_cli_pair_and_status(fake_site, monkeypatch, capsys):
    monkeypatch.setattr(site.time, "sleep", lambda s: None)
    assert cli.main(["pair", "--name", "Test Mac"]) == 0
    out = capsys.readouterr().out
    assert "connected" in out and fake_site.token not in out
    assert cli.main(["worker", "--status"]) == 0
    assert "user@example.org" in capsys.readouterr().out


class _Done:
    def __init__(self, returncode=0, stderr=""):
        self.returncode, self.stderr, self.stdout = returncode, stderr, ""


def test_keychain_set_keeps_the_token_out_of_argv(monkeypatch):
    calls = []

    def fake_run(argv, **kw):
        calls.append((argv, kw))
        return _Done()

    monkeypatch.setattr(site.subprocess, "run", fake_run)
    site.KeychainStore().set("https://slide2video.com", "s2v_secret-token-0123456789ab")
    argv, kw = calls[0]
    assert not any("s2v_secret-token-0123456789ab" in a for a in argv)
    assert "s2v_secret-token-0123456789ab" in kw["input"]


def test_keychain_set_failure_does_not_show_the_token(monkeypatch):
    def fake_run(argv, **kw):
        return _Done(returncode=1, stderr="error: keychain locked s2v_secret-token-0123456789ab")

    monkeypatch.setattr(site.subprocess, "run", fake_run)
    with pytest.raises(UserError) as e:
        site.KeychainStore().set("https://slide2video.com", "s2v_secret-token-0123456789ab")
    assert "Keychain" in str(e.value)
    assert "s2v_secret-token-0123456789ab" not in str(e.value)


def test_file_store_is_private(tmp_path, monkeypatch):
    import os
    s = site.FileStore()
    s.set("https://slide2video.com", "s2v_x")
    assert s.get("https://slide2video.com") == "s2v_x"
    if os.name == "posix":
        assert oct(s._file().stat().st_mode & 0o777) == "0o600"


def test_keychain_set_refuses_a_token_that_injects_a_command(monkeypatch):
    calls = []
    monkeypatch.setattr(site.subprocess, "run", lambda argv, **kw: calls.append(argv) or _Done())
    with pytest.raises(UserError) as e:
        site.KeychainStore().set("https://slide2video.com", "s2v_abcdefghijklmnopqrst\ndelete-keychain x")
    assert "s2v" not in str(e.value)
    assert calls == []


def test_keychain_set_refuses_a_site_with_a_space(monkeypatch):
    calls = []
    monkeypatch.setattr(site.subprocess, "run", lambda argv, **kw: calls.append(argv) or _Done())
    with pytest.raises(UserError):
        site.KeychainStore().set("https://evil.example x", "s2v_abcdefghijklmnopqrst")
    assert calls == []


def test_pair_refuses_a_malformed_token_and_stores_nothing(fake_site):
    fake_site.token = "s2v_bad token\nx"
    with pytest.raises(UserError) as e:
        site.pair(name="Test Mac", sleep=lambda s: None, out=lambda s: None)
    assert "bad token" not in str(e.value)
    assert site.store.get(fake_site.url) is None


def test_pair_code_shows_at_once_when_output_is_not_a_terminal(fake_site, tmp_path):
    """Claude Code runs `pair` in the background with its output in a pipe: the code line must arrive while it still
    waits, not when it exits (issue #4)."""
    import os
    import queue
    import subprocess
    import sys
    import threading

    from conftest import PLUGIN

    fake_site.pair_polls_pending = 10**6  # never typed: the command keeps waiting
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}
    env.update(LV_SITE_URL=fake_site.url, LESSON_VIDEOS_HOME=str(tmp_path / "home"))
    p = subprocess.Popen([sys.executable, str(PLUGIN / "scripts/slide2video.py"), "pair", "--name", "Test Mac"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, encoding="utf-8")
    lines = queue.Queue()
    threading.Thread(target=lambda: lines.put(p.stdout.readline()), daemon=True).start()
    try:
        first = lines.get(timeout=30)
        assert p.poll() is None  # still waiting for the code
        assert "ABC-123" in first
    except queue.Empty:
        raise AssertionError("no pairing code within 30 s: stdout is buffered") from None
    finally:
        p.kill()
        p.wait()


def test_call_sends_its_version_and_the_old_contract_header(paired):
    site.call("/api/device/status")
    assert paired.plugin_headers[-1] == lv.__version__
    assert paired.contract == 2  # the fake checks X-LV-Contract against the plugin major


def test_call_remembers_the_websites_version(paired, monkeypatch):
    monkeypatch.setattr(site, "LATEST", None)
    site.call("/api/device/status")
    assert site.LATEST is None  # an older website sends none
    paired.latest = "2.8.0"
    site.call("/api/device/next")  # 204 answers carry it too
    assert site.LATEST == "2.8.0"


def test_a_refusal_prints_the_websites_own_words(paired):
    paired.refuse = "slide2video.com hasn't caught up with slide2video 1.0.0 yet. Nothing to do on this computer; try again later."
    with pytest.raises(UserError) as e:
        site.call("/api/device/status")
    assert str(e.value) == paired.refuse


def test_the_fallback_update_message_says_to_reopen_claude_code():
    assert site.UPDATE == ("Update the slide2video plugin on this computer: run /plugin update slide2video, "
                           "then close and reopen Claude Code, then run /slide2video:serve.")


def test_status_names_the_version_and_an_available_update(paired, capsys, monkeypatch):
    monkeypatch.setattr(site, "LATEST", None)
    assert cli.main(["worker", "--status"]) == 0
    out = capsys.readouterr().out
    assert f"(this device: Test Mac, slide2video {lv.__version__})." in out and "newer" not in out
    paired.latest = "2.8.0"
    assert cli.main(["worker", "--status"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[1] == ("A newer slide2video (2.8.0) is available. To update: run /plugin update slide2video, "
                      "then close and reopen Claude Code, then run /slide2video:serve.")
    paired.latest = "1.0.0"
    assert cli.main(["worker", "--status"]) == 0
    assert "newer" not in capsys.readouterr().out


def test_only_slide2video_com(monkeypatch):
    monkeypatch.delenv("LV_SITE_URL", raising=False)
    assert site.site_url() == "https://slide2video.com"
    assert site.host() == "slide2video.com"
    assert site.cmd("serve") == "/slide2video:serve"
    assert not hasattr(site, "use") and not hasattr(site, "is_pro")


def test_the_test_override_still_wins(monkeypatch):
    monkeypatch.setenv("LV_SITE_URL", "http://127.0.0.1:9")
    assert site.site_url() == "http://127.0.0.1:9"


def test_not_paired_names_the_site_and_command(monkeypatch):
    monkeypatch.delenv("LV_SITE_URL", raising=False)
    assert "slide2video.com" in site.not_paired() and "/slide2video:setup " in site.not_paired()


def test_cli_has_no_site_option():
    for site_arg in ("pro", "https://evil.example"):
        for cmd in (["pair"], ["worker", "--status"]):
            with pytest.raises(SystemExit):
                cli.build_parser().parse_args([*cmd, "--site", site_arg])


# --- review fixes (slide2video-site#8) -----------------------------------------------------------------------------------

def test_keychain_set_trusts_securitys_own_failure_line_not_any_word_error(monkeypatch):
    monkeypatch.setattr(site.subprocess, "run", lambda argv, **kw: _Done(stderr="note: no error handling needed\n"))
    site.KeychainStore().set("https://slide2video.com", "s2v_secret-token-0123456789ab")   # saved
    failed = "security: SecKeychainItemCreateFromContent (<default>): The user name or passphrase you entered is not correct.\n"
    monkeypatch.setattr(site.subprocess, "run", lambda argv, **kw: _Done(stderr=failed))   # exit 0, but it failed
    with pytest.raises(UserError):
        site.KeychainStore().set("https://slide2video.com", "s2v_secret-token-0123456789ab")


def test_file_store_says_pair_again_when_its_file_is_damaged(tmp_path, monkeypatch):
    s = site.FileStore()
    s._file().parent.mkdir(parents=True, exist_ok=True)
    s._file().write_text("{not json", encoding="utf-8")
    with pytest.raises(UserError) as e:
        s.get("https://slide2video.com")
    assert "connect this computer again" in str(e.value)
    s.set("https://slide2video.com", "s2v_x")   # pairing again replaces it
    assert s.get("https://slide2video.com") == "s2v_x"
    s._file().write_text("[]", encoding="utf-8")
    s.delete("https://slide2video.com")
    assert not s._file().exists()


def test_file_store_is_private_from_the_first_byte(tmp_path, monkeypatch):
    import os
    modes = []
    real = os.open

    def spy(path, flags, mode=0o777, *a, **kw):
        if str(path).endswith(".tmp"):
            modes.append(mode)
        return real(path, flags, mode, *a, **kw)
    monkeypatch.setattr(site.os, "open", spy)
    site.FileStore().set("https://slide2video.com", "s2v_x")
    assert modes == [0o600]
    assert not list(site.FileStore()._file().parent.glob(".*.tmp"))


def test_pair_keeps_waiting_through_a_network_blip(fake_site, monkeypatch):
    real, failed = site.call, []

    def flaky(path, *a, **kw):
        if path.endswith("/pair/poll") and not failed:
            failed.append(path)
            raise net.ApiError(0, "connection reset", path)
        return real(path, *a, **kw)
    monkeypatch.setattr(site, "call", flaky)
    assert site.pair(name="Test Mac", sleep=lambda s: None, out=lambda s: None) == "user@example.org"
    assert failed and site.store.get(fake_site.url) == fake_site.token
