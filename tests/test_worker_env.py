import pytest

from lv import site, worker
from lv.util import UserError


def test_site_token_from_environment_is_used(paired, monkeypatch):
    env_token = "s2v_from-the-environment-0123456789"
    paired.token = env_token
    monkeypatch.setenv("LV_SITE_TOKEN", env_token)
    stored = site.store.get(paired.url)
    assert site.call("/api/device/status")
    assert site.store.get(paired.url) == stored  # the store is untouched


def test_site_token_from_environment_needs_no_pairing(fake_site, monkeypatch):
    monkeypatch.setenv("LV_SITE_TOKEN", fake_site.token)
    assert site.call("/api/device/status")
    assert site.store.get(fake_site.url) is None


def test_bad_site_token_in_environment_is_refused(paired, monkeypatch):
    monkeypatch.setenv("LV_SITE_TOKEN", "not a token")
    with pytest.raises(UserError):
        site.call("/api/device/status")


def test_api_key_mode_keeps_the_key_and_base_url(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "other")
    env = worker._site_env(tmp_path, api_key=True)
    assert env["ANTHROPIC_API_KEY"] == "sk-ant-test"
    assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:9"
    assert env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    assert env["LV_SITE_MODE"] == "1"


def test_default_mode_still_drops_api_keys(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:9")
    env = worker._site_env(tmp_path)
    assert "ANTHROPIC_API_KEY" not in env and "ANTHROPIC_BASE_URL" not in env
    assert "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC" not in env


def test_api_key_mode_needs_a_key(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(UserError, match="Set ANTHROPIC_API_KEY to use --api-key."):
        worker._site_env(tmp_path, api_key=True)
    with pytest.raises(UserError, match="--api-key"):
        worker.run_once(api_key=True)


def test_api_key_flag_reaches_claude_launch(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    seen = {}
    monkeypatch.setattr(worker.subprocess, "run",
                        lambda cmd, **kw: seen.update(kw) or type("R", (), {"returncode": 0})())
    runner = worker._claude_runner(None, True)
    runner(["claude"], tmp_path, tmp_path / "log")
    assert seen["env"]["ANTHROPIC_API_KEY"] == "sk-ant-test"
    assert worker._claude_runner(None, False) is None
