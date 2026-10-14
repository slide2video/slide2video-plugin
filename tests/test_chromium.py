import shutil
import sys

import pytest

from lv import chromium
from lv.util import UserError, write_text


def test_path_prefers_env_then_saved_then_none(tmp_path, monkeypatch):
    monkeypatch.delenv("LV_CHROMIUM", raising=False)
    assert chromium.path() is None
    saved = write_text(tmp_path / "saved chrome", "")
    write_text(chromium.saved_file(), str(saved) + "\n")
    assert chromium.path() == str(saved)
    env = write_text(tmp_path / "env chrome", "")
    monkeypatch.setenv("LV_CHROMIUM", str(env))
    assert chromium.path() == str(env)


def test_missing_paths_are_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("LV_CHROMIUM", str(tmp_path / "gone"))
    write_text(chromium.saved_file(), str(tmp_path / "also gone"))
    assert chromium.path() is None


def test_launch_passes_executable_only_when_set(tmp_path, monkeypatch):
    calls = []

    class P:
        class chromium:
            @staticmethod
            def launch(**kw):
                calls.append(kw)
                return "browser"

    monkeypatch.delenv("LV_CHROMIUM", raising=False)
    assert chromium.launch(P) == "browser"
    assert calls[-1] == {"args": chromium.LAUNCH_ARGS}
    exe = write_text(tmp_path / "chrome", "")
    monkeypatch.setenv("LV_CHROMIUM", str(exe))
    chromium.launch(P)
    assert calls[-1] == {"args": chromium.LAUNCH_ARGS, "executable_path": str(exe)}


def test_ensure_skips_download_when_browser_starts():
    def boom():
        raise AssertionError("must not install")
    assert chromium.ensure(probe=lambda: "", playwright_install=boom, npm_install=boom).startswith("ready")


def test_ensure_downloads_with_playwright_when_needed():
    state = {"installed": False}

    def install():
        state["installed"] = True
    probe = lambda: "" if state["installed"] else "Executable doesn't exist"  # noqa: E731
    assert chromium.ensure(probe=probe, playwright_install=install) == "ready (downloaded)"


def test_ensure_falls_back_to_npm_on_linux(tmp_path, monkeypatch):
    monkeypatch.delenv("LV_CHROMIUM", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(chromium.shutil, "which", lambda name: f"/usr/bin/{name}")
    exe = write_text(tmp_path / "npm chrome", "")

    def pw_fail():
        raise UserError("403 from cdn.playwright.dev")
    probe = lambda: "" if chromium.path() == str(exe) else "missing"  # noqa: E731
    msg = chromium.ensure(probe=probe, playwright_install=pw_fail, npm_install=lambda: exe)
    assert "npm" in msg
    assert chromium.saved_file().read_text(encoding="utf-8").strip() == str(exe)


def test_ensure_reports_first_error_when_nothing_works(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")

    def pw_fail():
        raise UserError("Could not download the Chromium renderer")
    with pytest.raises(UserError, match="Could not download"):
        chromium.ensure(probe=lambda: "missing", playwright_install=pw_fail)


def test_install_npm_copies_binary(tmp_path):
    src = write_text(tmp_path / "extracted" / "chromium", "#!/bin/sh\n")
    seen = []

    class R:
        def __init__(self, out=""):
            self.returncode, self.stdout, self.stderr = 0, out, ""

    def run(cmd, **kw):
        seen.append(cmd)
        return R(f"{src}\n" if cmd[0] == "node" else "")
    dest = chromium.install_npm(run=run)
    assert dest.read_text(encoding="utf-8") == "#!/bin/sh\n"
    assert seen[0][:2] == ["npm", "install"] and chromium.NPM_PACKAGE in seen[0]
    assert seen[1][0] == "node"


def test_ensure_explains_why_a_downloaded_browser_wont_start(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    with pytest.raises(UserError, match="crashed on start"):
        chromium.ensure(probe=lambda: "crashed on start", playwright_install=lambda: None)


def test_ensure_names_lv_chromium_when_it_is_the_broken_one(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    exe = write_text(tmp_path / "my chrome", "")
    monkeypatch.setenv("LV_CHROMIUM", str(exe))
    with pytest.raises(UserError, match="LV_CHROMIUM"):
        chromium.ensure(probe=lambda: "bad binary", playwright_install=lambda: None)


def test_npm_browser_is_not_saved_when_it_wont_start(tmp_path, monkeypatch):
    monkeypatch.delenv("LV_CHROMIUM", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(chromium.shutil, "which", lambda name: f"/usr/bin/{name}")
    exe = write_text(tmp_path / "npm chrome", "")

    def pw_fail():
        raise UserError("403 from cdn.playwright.dev")
    with pytest.raises(UserError):
        chromium.ensure(probe=lambda: "missing libs", playwright_install=pw_fail, npm_install=lambda: exe)
    assert not chromium.saved_file().exists()


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_install_npm_handles_the_es_module_build(tmp_path):
    """@sparticuz/chromium 153+ is an ES module: require() returns {default: {...}} (seen in a Cowork cloud session)."""
    import subprocess
    exe = write_text(tmp_path / "unpacked" / "chromium", "#!/bin/sh\n")
    pkg = chromium.config.home() / "chromium-npm" / "node_modules" / "@sparticuz" / "chromium"
    write_text(pkg / "package.json", '{"name": "@sparticuz/chromium", "type": "module", "main": "index.js"}')
    write_text(pkg / "index.js", f"export default {{ executablePath: async () => {str(exe)!r} }};\n")

    def run(cmd, **kw):
        if cmd[0] == "npm":
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.run(cmd, **kw)
    assert chromium.install_npm(run=run).read_text(encoding="utf-8") == "#!/bin/sh\n"
