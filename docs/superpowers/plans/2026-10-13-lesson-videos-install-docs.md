# lesson-videos install guides, key skills and Cowork support — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the lesson-videos README around purpose and sample results, add install guides (Claude Code, Cowork) and illustrated key guides, add two Claude-in-Chrome key skills with clipboard-safe key saving, and make the plugin work in claude.ai Cowork cloud sessions.

**Architecture:** Docs live in `lesson-videos/docs/` and ship with the plugin. Key saving is two new `keys` sub-commands (`paste`, `load`) built on one `keys.store()` helper that never prints values. Chromium selection moves into a new `lv/chromium.py` (env var → saved path → Playwright → npm `@sparticuz/chromium` fallback) used by both render and doctor. Skills address scripts through `${CLAUDE_SKILL_DIR}` so they run where `CLAUDE_PLUGIN_ROOT` is unset.

**Tech Stack:** Python 3.11+ (uv inline script), Playwright (sync API), pytest, Markdown skills, Claude in Chrome for screenshots and live tests, `gh` for the release.

**Spec:** `docs/superpowers/specs/2026-10-13-lesson-videos-install-docs-design.md`

## Global Constraints

- Plugin version **0.4.0** in `lesson-videos/.claude-plugin/plugin.json`, the `lesson-videos` entry of `.claude-plugin/marketplace.json`, and `lesson-videos/scripts/lv/__init__.py`.
- Public repo: no class material, student data, keys, or private paths (`tests/test_packaging.py::test_no_private_paths_in_plugin` forbids `/Users/`, `/private/tmp`, `dotfiles`, `marine-biology`, `daniellandi@`, `collage-studio` in plugin `.py/.md/.js/.json`).
- Windows and macOS: every file read/write passes `encoding="utf-8"`; subprocesses use argument lists; skills contain no bash-only syntax.
- Engine API (`lesson-videos/engine/engine.js`) is frozen: not touched by this plan.
- Model IDs and prices live only in `lesson-videos/scripts/lv/config.py`.
- No command, error message, log line, or test output ever contains a key value; masked form is `set, ends in …1234` (`keys.mask`).
- Skills call `uv run "${CLAUDE_SKILL_DIR}/../../scripts/lesson-videos.py"`; no file under `lesson-videos/skills/` mentions `CLAUDE_PLUGIN_ROOT`.
- Claude never types passwords, creates accounts, enters payment details, or changes claude.ai network settings; the maintainer does those. Publishing (GitHub Release upload, `git push`) and committing screenshots each need the maintainer's explicit yes at that moment.
- Gate before merging: `uv run pytest -q` passes. Tier B: work on `lesson-videos-install-docs`, merge to `main` directly, push.

## Review Focus

1. **Clipboard text with a trailing newline, CRLF or surrounding quotes** (Windows `Get-Clipboard` adds CRLF; some sites copy with quotes) → the key is still accepted and stored clean. Test in Task 3.
2. **A key already in `keys.env`, also written as `export VAR="…"`** → `store` replaces that line instead of adding a duplicate that `parse` would resolve unpredictably. Test in Task 3.
3. **`ELEVENLABS_API_KEY` / `GEMINI_API_KEY` set in the environment** → after `keys paste`, `get()` still returns the env value; the command must say the environment value wins instead of reporting success silently. Test in Task 3.
4. **`LV_CHROMIUM` or `chromium.txt` pointing at a file that no longer exists** (fresh Cowork machine, moved home folder) → ignored, falls back to Playwright's browser, never a crash. Test in Task 1.
5. **A keys file saved by TextEdit as rich text (RTF) or with odd encoding** → `keys load` still finds `sk_…` / `AIza…` values next to their variable names and never echoes the file. Test in Task 3.

---

## File map

| File | Change | Responsibility |
|---|---|---|
| `lesson-videos/scripts/lv/chromium.py` | create | Which Chromium to launch; make one available |
| `lesson-videos/scripts/lv/tools.py` | modify | drop `install_chromium` (moved) |
| `lesson-videos/scripts/lv/render.py` | modify | launch through `chromium.launch` |
| `lesson-videos/scripts/lv/doctor.py` | modify | `chromium.ensure()`; blocked-domain hint in Narration |
| `lesson-videos/scripts/lv/net.py` | modify | `behind_proxy()`, `blocked_hint(host)` |
| `lesson-videos/scripts/lv/config.py` | modify | `EDGE_HOST` |
| `lesson-videos/scripts/lv/keys.py` | modify | `store`, `paste`, `load`, clipboard commands, blocked hints in `check` |
| `lesson-videos/scripts/lv/cli.py` | modify | `keys paste <service>`, `keys load <file>` |
| `lesson-videos/skills/make/SKILL.md`, `skills/setup/SKILL.md` | modify | `${CLAUDE_SKILL_DIR}` paths; Cowork notes; hand-off to key skills |
| `lesson-videos/skills/elevenlabs-get-api-key/SKILL.md` | create | Claude-in-Chrome ElevenLabs key flow |
| `lesson-videos/skills/google-get-api-key/SKILL.md` | create | Claude-in-Chrome Gemini key + billing + cap flow |
| `lesson-videos/docs/install/{claude-code,cowork}.md` | create | install guides |
| `lesson-videos/docs/keys/{README,elevenlabs,google,keys-file}.md` | create | key guides |
| `lesson-videos/docs/keys-template.txt` (or `.lvkeys`, Task 0) | create | downloadable empty keys file |
| `lesson-videos/docs/images/*.webp` | create | sample stills, redacted screenshots |
| `lesson-videos/README.md` | rewrite | purpose, samples, choose a path |
| `tests/test_chromium.py`, `tests/test_docs.py` | create | new tests |
| `tests/test_keys.py`, `tests/test_doctor.py`, `tests/test_packaging.py`, `tests/test_cli.py` | modify | new cases |

---

### Task 0: Decide the keys-file extension (attachment probe on claude.ai)

Answers spec §5.2's open check before any doc names the file. Nothing is committed.

**Files:** none in the repo. Scratch file only.

**Interfaces:**
- Produces: `KEYS_FILE_NAME` decision used in Tasks 3, 4, 6: either `lesson-videos-keys.txt` (template `docs/keys-template.txt`) or `lesson-videos.lvkeys` (template `docs/lesson-videos.lvkeys`).

- [ ] **Step 1: Make a dummy keys file with fake values**

Write `<scratchpad>/lesson-videos-keys.txt`:
```
# lesson-videos API keys
ELEVENLABS_API_KEY=sk_FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE
GEMINI_API_KEY=AIzaFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAK
```
and a copy named `lesson-videos.lvkeys`.

- [ ] **Step 2: Attach the `.txt` in a new claude.ai session through Claude in Chrome**

Open `https://claude.ai/new` in a new tab, attach the `.txt` with `mcp__claude-in-chrome__file_upload`, send: *"Don't open or read the attached file. Reply only with: did its contents arrive inside this message as text, or only as a file in your sandbox? Answer 'inline' or 'file only', and give its sandbox path if any."* Also read the page with `get_page_text` to see if the content is rendered in the message.

- [ ] **Step 3: If the answer is "inline" (or the page shows the values), repeat with the `.lvkeys` copy**

- [ ] **Step 4: Record the decision**

Use `.txt` if it arrived "file only"; else `.lvkeys` if that arrived "file only"; if both inline, stop and report to the maintainer (Cowork keys would need another route). Note the sandbox upload path pattern for the make skill's Cowork note (Task 4). Delete the test session from claude.ai only if the maintainer asks.

---

### Task 1: Chromium selection module and doctor/render use it

**Files:**
- Create: `lesson-videos/scripts/lv/chromium.py`
- Modify: `lesson-videos/scripts/lv/tools.py:52-57` (delete `install_chromium`)
- Modify: `lesson-videos/scripts/lv/render.py:74-78`
- Modify: `lesson-videos/scripts/lv/doctor.py` (Chromium row)
- Test: `tests/test_chromium.py`

**Interfaces:**
- Produces:
  - `chromium.LAUNCH_ARGS: list[str]`
  - `chromium.saved_file() -> Path` (`config.home() / "chromium.txt"`)
  - `chromium.path() -> str | None`
  - `chromium.launch(p)` — `p` is a `sync_playwright()` handle; returns a Browser
  - `chromium.can_launch() -> str` — `""` when it starts, else the first error line
  - `chromium.install_playwright(run=subprocess.run) -> None` (raises `UserError`)
  - `chromium.install_npm(run=subprocess.run) -> Path` (raises `UserError`)
  - `chromium.ensure(probe=can_launch, playwright_install=None, npm_install=None) -> str` (raises `UserError`)

- [ ] **Step 1: Write the failing tests**

`tests/test_chromium.py`:
```python
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
    probe = lambda: "" if state["installed"] else "Executable doesn't exist"
    assert chromium.ensure(probe=probe, playwright_install=install) == "ready (downloaded)"


def test_ensure_falls_back_to_npm_on_linux(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(chromium.shutil, "which", lambda name: f"/usr/bin/{name}")
    exe = write_text(tmp_path / "npm chrome", "")
    def pw_fail():
        raise UserError("403 from cdn.playwright.dev")
    probe = lambda: "" if chromium.path() == str(exe) else "missing"
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
```

- [ ] **Step 2: Run to see them fail**

Run: `uv run pytest tests/test_chromium.py -q`
Expected: FAIL — `ImportError: cannot import name 'chromium'`.

- [ ] **Step 3: Write `lesson-videos/scripts/lv/chromium.py`**

```python
"""Which Chromium the renderer launches (LV_CHROMIUM, a saved path, or Playwright's own), and getting one."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import config
from .util import UserError, read_text, write_text

LAUNCH_ARGS = ["--use-gl=angle", "--enable-gpu-rasterization", "--ignore-gpu-blocklist"]
NPM_PACKAGE = "@sparticuz/chromium"   # ships the browser inside the npm package; used where downloads are blocked


def saved_file() -> Path:
    return config.home() / "chromium.txt"


def path() -> str | None:
    """The Chromium to launch, or None for Playwright's own browser. Paths that no longer exist are ignored."""
    env = os.environ.get("LV_CHROMIUM", "").strip()
    if env and Path(env).is_file():
        return env
    f = saved_file()
    if f.exists():
        saved = read_text(f).strip()
        if saved and Path(saved).is_file():
            return saved
    return None


def launch(p):
    """Start headless Chromium from a sync_playwright() handle."""
    exe = path()
    return p.chromium.launch(args=LAUNCH_ARGS, **({"executable_path": exe} if exe else {}))


def can_launch() -> str:
    """'' if the browser starts, else the first line of the error."""
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            launch(p).close()
        return ""
    except Exception as e:  # noqa: BLE001
        return (str(e).splitlines() or [type(e).__name__])[0]


def install_playwright(run=subprocess.run) -> None:
    r = run([sys.executable, "-m", "playwright", "install", "chromium"], capture_output=True,
            encoding="utf-8", errors="replace")
    if r.returncode:
        raise UserError("Could not download the Chromium renderer (about 150 MB). Check the internet connection "
                        "(school networks may block it), then run `doctor` again.\n" + (r.stderr or "")[-800:])


def install_npm(run=subprocess.run) -> Path:
    """Install NPM_PACKAGE under ~/.lesson-videos and copy its browser to a fixed place. Linux only."""
    prefix = config.home() / "chromium-npm"
    prefix.mkdir(parents=True, exist_ok=True)
    r = run(["npm", "install", "--prefix", str(prefix), "--no-audit", "--no-fund", NPM_PACKAGE],
            capture_output=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise UserError(f"Could not install {NPM_PACKAGE} from npm.\n" + (r.stderr or "")[-800:])
    js = f"require({json.dumps(NPM_PACKAGE)}).executablePath().then(p => console.log(p))"
    r = run(["node", "-e", js], cwd=str(prefix), capture_output=True, encoding="utf-8", errors="replace")
    lines = (r.stdout or "").strip().splitlines()
    if r.returncode or not lines or not Path(lines[-1]).is_file():
        raise UserError(f"{NPM_PACKAGE} installed but didn't unpack its browser.\n" + (r.stderr or "")[-800:])
    dest = config.home() / "chromium" / "chrome"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(lines[-1], dest)
    dest.chmod(0o755)
    return dest


def ensure(probe=can_launch, playwright_install=None, npm_install=None) -> str:
    """Make a working Chromium available and say which. Tries the existing one before downloading anything."""
    if not probe():
        return f"ready ({path() or 'Playwright browser'})"
    errors = []
    try:
        (playwright_install or install_playwright)()
        if not probe():
            return "ready (downloaded)"
    except UserError as e:
        errors.append(str(e))
    if sys.platform.startswith("linux") and shutil.which("npm") and shutil.which("node"):
        try:
            exe = (npm_install or install_npm)()
            write_text(saved_file(), str(exe))
            err = probe()
            if not err:
                return f"ready (from npm {NPM_PACKAGE})"
            errors.append(f"the npm Chromium won't start: {err}")
        except UserError as e:
            errors.append(str(e))
    raise UserError(errors[0] if errors else "Chromium won't start. Run `doctor` again.")
```

- [ ] **Step 4: Point render and doctor at it**

`render.py` — replace the launch line inside `page_for`:
```python
        try:
            browser = chromium.launch(p)
```
and add `chromium` to the `from . import ...` line at the top of `render.py` (`from . import captions, chromium, config, mix, paths, sfx, status, tools`).

`doctor.py` — replace the Chromium block:
```python
    try:
        ok("Chromium renderer", chromium.ensure() if install else "ready")
    except UserError as e:
        bad("Chromium renderer", str(e))
```
and import it: `from . import chromium, config, keys, narrate, render, sfx, tools, voices`.

`tools.py` — delete `install_chromium` (lines 52-57) and the now-unused `import sys` only if nothing else uses it (check with `grep -n "sys\." lesson-videos/scripts/lv/tools.py`).

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_chromium.py tests/test_doctor.py tests/test_render*.py -q` (use `ls tests | grep render` for the exact render test file names; if none, run the whole suite).
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add lesson-videos/scripts/lv/chromium.py lesson-videos/scripts/lv/tools.py lesson-videos/scripts/lv/render.py lesson-videos/scripts/lv/doctor.py tests/test_chromium.py
git commit -m "lesson-videos: choose Chromium from LV_CHROMIUM/saved path, try it before downloading, npm fallback"
```

---

### Task 2: Name the blocked domain when Claude's cloud network setting blocks a service

**Files:**
- Modify: `lesson-videos/scripts/lv/net.py` (add helpers)
- Modify: `lesson-videos/scripts/lv/config.py` (add `EDGE_HOST`)
- Modify: `lesson-videos/scripts/lv/keys.py` (`check`)
- Modify: `lesson-videos/scripts/lv/doctor.py` (`narration_summary`)
- Test: `tests/test_keys.py`, `tests/test_doctor.py`

**Interfaces:**
- Produces: `net.behind_proxy() -> bool`; `net.blocked_hint(host: str) -> str` (`""` when not behind a proxy); `config.EDGE_HOST = "speech.platform.bing.com"`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_keys.py`:
```python
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
```
Append to `tests/test_doctor.py`:
```python
def test_narration_names_bing_when_blocked(monkeypatch):
    from lv import voices
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy:3128")
    def down(*a):
        raise voices.VoiceUnavailable("offline")
    monkeypatch.setitem(voices.SPEAKERS, "edge", down)
    monkeypatch.setitem(voices.SPEAKERS, "system", down)
    out = doctor.narration_summary()
    assert "speech.platform.bing.com" in out and "captions-only always works" in out
```

- [ ] **Step 2: Run to see them fail**

Run: `uv run pytest tests/test_keys.py tests/test_doctor.py -q`
Expected: the three new tests FAIL (no hint text).

- [ ] **Step 3: Implement**

`config.py`, next to `EDGE_VOICE`:
```python
EDGE_HOST = "speech.platform.bing.com"     # the free Microsoft voice's server
```
`net.py`, add `import os` and after `ApiError`:
```python
def behind_proxy() -> bool:
    """True in claude.ai cloud sessions (and other proxied networks)."""
    return bool(os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"))


def blocked_hint(host: str) -> str:
    if not behind_proxy():
        return ""
    return (f"blocked by Claude's network setting: in claude.ai open Settings → Capabilities → Additional allowed "
            f"domains, add {host}, then start a new session")
```
`keys.py` `check()` — ElevenLabs `except` branch becomes:
```python
        except net.ApiError as e:
            d = e.detail.lower()
            blocked = net.blocked_hint(urllib.parse.urlparse(config.ELEVEN_ROOT).netloc) if e.status == 0 else ""
            if "permission" in d:  # the key authenticated; it just can't read the account
                rows.append(("ElevenLabs", True, f"{mask(el)}; key works, but can't show your remaining credits "
                                                 "(to see them, edit the key at elevenlabs.io and allow User → Read)"))
            else:
                hint = blocked or ("the key was rejected: create a new one and paste it again" if e.status == 401 else str(e))
                rows.append(("ElevenLabs", False, f"{mask(el)}; {hint}"))
```
Gemini `except` branch:
```python
        except net.ApiError as e:
            blocked = net.blocked_hint(urllib.parse.urlparse(config.GEMINI_ROOT).netloc) if e.status == 0 else ""
            hint = blocked or ("the key was rejected: create a new one and paste it again" if e.status in (400, 401, 403) else str(e))
            rows.append(("Gemini", False, f"{mask(gm)}; {hint}"))
```
Add `import urllib.parse` at the top of `keys.py`.

`doctor.py` `narration_summary()`:
```python
def narration_summary() -> str:
    """Which voices work right now. Never a failure: captions-only always works."""
    from . import net
    parts = ["ElevenLabs (key set)"] if keys.get("ELEVENLABS_API_KEY", required=False) else []
    edge_down = net.blocked_hint(config.EDGE_HOST) or "free Microsoft voice unavailable right now"
    for provider, works, fails in (("edge", "free Microsoft voice works", edge_down),
                                   ("system", "computer's own voice works", "no computer voice")):
        try:
            voices.probe(provider)
            parts.append(works)
        except voices.VoiceUnavailable:
            parts.append(fails)
    return "; ".join(parts) + "; captions-only always works"
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_keys.py tests/test_doctor.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lesson-videos/scripts/lv/net.py lesson-videos/scripts/lv/config.py lesson-videos/scripts/lv/keys.py lesson-videos/scripts/lv/doctor.py tests/test_keys.py tests/test_doctor.py
git commit -m "lesson-videos: name the domain to allow when Claude's cloud network setting blocks a service"
```

---

### Task 3: `keys paste` and `keys load`

**Files:**
- Modify: `lesson-videos/scripts/lv/keys.py`
- Modify: `lesson-videos/scripts/lv/cli.py` (keys parser + dispatch)
- Test: `tests/test_keys.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `keys.ensure_file`, `keys.parse`, `keys.mask`, `keys.check`, `keys._PLACEHOLDER`.
- Produces:
  - `keys.SERVICES = {"elevenlabs": "ELEVENLABS_API_KEY", "gemini": "GEMINI_API_KEY"}`
  - `keys.NAMES = {"ELEVENLABS_API_KEY": "ElevenLabs", "GEMINI_API_KEY": "Gemini"}`
  - `keys.store(var: str, value: str) -> Path`
  - `keys.clipboard_commands(platform: str = sys.platform) -> tuple[list[str], list[str]]` — (read, clear)
  - `keys.clean(text: str) -> str`
  - `keys.paste(service: str, run=subprocess.run, platform: str = sys.platform) -> str` — returns the variable stored
  - `keys.load(path: Path) -> list[str]` — variables stored
  - CLI: `keys paste <elevenlabs|gemini>`, `keys load <file>`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_keys.py`:
```python
import subprocess as _sp


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
    assert keys.paste("elevenlabs", run=run, platform="darwin") == "ELEVENLABS_API_KEY"
    assert keys.parse(keys.keys_file().read_text(encoding="utf-8"))["ELEVENLABS_API_KEY"] == EL
    assert run.calls[0][0] == ["pbpaste"] and run.calls[1][0] == ["pbcopy"] and run.calls[1][1]["input"] == ""
    out = capsys.readouterr()
    assert EL not in out.out + out.err


def test_paste_refuses_non_key_without_echo(capsys):
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
           f"# lesson-videos API keys\\\nELEVENLABS_API_KEY={EL}\\\nGEMINI_API_KEY={GM}}}")
    f = tmp_path / "keys.rtf"
    f.write_bytes(rtf.encode("cp1252"))
    assert sorted(keys.load(f)) == ["ELEVENLABS_API_KEY", "GEMINI_API_KEY"]
    assert keys.get("GEMINI_API_KEY") == GM


def test_load_missing_file():
    with pytest.raises(keys.UserError):
        keys.load(keys.config.home() / "nope.txt")
```
Append to `tests/test_cli.py` (check its imports first; it already imports `cli`):
```python
def test_keys_paste_cli_never_prints_key(monkeypatch, capsys):
    from lv import cli, keys
    el = "sk_0123456789abcdef0123456789abcdef"
    monkeypatch.setattr(keys, "paste", lambda service: keys.store("ELEVENLABS_API_KEY", el) and "ELEVENLABS_API_KEY")
    monkeypatch.setattr(keys, "check", lambda: [("ElevenLabs", True, "set, ends in …cdef; 9,000 characters left"),
                                                ("Gemini", True, "not set (optional)")])
    assert cli.main(["keys", "paste", "elevenlabs"]) == 0
    out = capsys.readouterr().out
    assert el not in out and "ElevenLabs" in out and "Gemini" not in out


def test_keys_paste_warns_when_env_wins(monkeypatch, capsys):
    from lv import cli, keys
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_fromenvironment0000000000")
    monkeypatch.setattr(keys, "paste", lambda service: "ELEVENLABS_API_KEY")
    monkeypatch.setattr(keys, "check", lambda: [("ElevenLabs", True, "ok"), ("Gemini", True, "ok")])
    cli.main(["keys", "paste", "elevenlabs"])
    assert "environment" in capsys.readouterr().out


def test_keys_paste_needs_service(capsys):
    from lv import cli
    assert cli.main(["keys", "paste"]) == 1
    assert "keys paste elevenlabs" in capsys.readouterr().err


def test_keys_load_reports_nothing_found(tmp_path, capsys):
    from lv import cli
    f = tmp_path / "empty.txt"
    f.write_text("nothing here\n", encoding="utf-8")
    assert cli.main(["keys", "load", str(f)]) == 1
    assert "No keys found" in capsys.readouterr().out
```

- [ ] **Step 2: Run to see them fail**

Run: `uv run pytest tests/test_keys.py tests/test_cli.py -q`
Expected: new tests FAIL (`AttributeError: module 'lv.keys' has no attribute 'paste'`, argparse rejects `paste`).

- [ ] **Step 3: Implement in `keys.py`**

Add imports `shutil`, `subprocess` (top). `UserError` is already imported from `.util`. Add after `_SHAPES`:
```python
SERVICES = {"elevenlabs": "ELEVENLABS_API_KEY", "gemini": "GEMINI_API_KEY"}
NAMES = {"ELEVENLABS_API_KEY": "ElevenLabs", "GEMINI_API_KEY": "Gemini"}
_KEY = {"ELEVENLABS_API_KEY": r"sk_[A-Za-z0-9]{16,}", "GEMINI_API_KEY": r"AIza[0-9A-Za-z_\-]{30,}"}
```
Add after `ensure_file`:
```python
def store(var: str, value: str) -> Path:
    """Write var=value into keys.env, replacing any existing line for var. The value is never printed."""
    f = ensure_file()
    out, done = [], False
    for line in read_text(f).splitlines():
        body = line.strip().lstrip("﻿")
        if body.startswith("export "):
            body = body[7:].lstrip()
        if not body.startswith("#") and "=" in body and body.partition("=")[0].strip() == var:
            if not done:
                out.append(f"{var}={value}")
                done = True
            continue
        out.append(line)
    if not done:
        out.append(f"{var}={value}")
    write_text(f, "\n".join(out) + "\n")
    if os.name == "posix":
        os.chmod(f, 0o600)
    return f


def clean(text: str) -> str:
    return text.strip().strip('"').strip("'").strip()


def clipboard_commands(platform: str = sys.platform) -> tuple[list[str], list[str]]:
    """(read, clear) commands; clear is run with empty input."""
    if platform == "darwin":
        return ["pbpaste"], ["pbcopy"]
    if platform.startswith("win"):
        return ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"], ["clip"]
    if shutil.which("wl-paste"):
        return ["wl-paste", "--no-newline"], ["wl-copy"]
    return ["xclip", "-o", "-selection", "clipboard"], ["xclip", "-i", "-selection", "clipboard"]


def paste(service: str, run=subprocess.run, platform: str = sys.platform) -> str:
    """Save the key on the clipboard for `service`, then clear the clipboard. Returns the variable name."""
    var = SERVICES[service]
    label = f"{'an' if service == 'elevenlabs' else 'a'} {NAMES[var]} key"
    read, clear = clipboard_commands(platform)
    try:
        r = run(read, capture_output=True, encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        raise UserError("Couldn't read the clipboard on this computer. Run `keys` and paste the key into the file "
                        "that opens instead.") from None
    value = clean(r.stdout or "")
    if r.returncode or not re.fullmatch(_KEY[var], value):
        raise UserError(f"The clipboard doesn't hold {label}. Click Copy next to the key on the website, "
                        "then try again.")
    store(var, value)
    try:
        run(clear, input="", capture_output=True, encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return var


def load(path: Path) -> list[str]:
    """Import keys from a keys file the teacher attached (plain text or TextEdit rich text). Never prints them."""
    path = Path(path)
    if not path.is_file():
        raise UserError(f"There's no file at {path}. Attach the keys file to this session and try again.")
    text = path.read_bytes().decode("utf-8", errors="replace")
    found = []
    for var, shape in _KEY.items():
        m = re.search(rf"{var}\s*=\s*[\"']?({shape})", text)
        if m and not _PLACEHOLDER.match(m.group(1)):
            store(var, m.group(1))
            found.append(var)
    return found
```

- [ ] **Step 4: Implement in `cli.py`**

Parser: replace the `keys` lines with
```python
    k = sub.add_parser("keys", help="open the keys file; `keys check` tests them; `keys paste elevenlabs|gemini` "
                                    "saves the key on the clipboard; `keys load FILE` imports a keys file")
    k.add_argument("action", nargs="?", choices=["open", "check", "paste", "load"], default="open")
    k.add_argument("target", nargs="?", help="paste: elevenlabs or gemini; load: the keys file")
```
Dispatch: replace the `keys` block with
```python
    if args.cmd == "keys":
        if args.action == "paste":
            if args.target not in keys.SERVICES:
                raise UserError("Say which key: `keys paste elevenlabs` or `keys paste gemini`.")
            stored = [keys.paste(args.target)]
            print(f"Saved the {keys.NAMES[stored[0]]} key and cleared the clipboard.")
        elif args.action == "load":
            if not args.target:
                raise UserError("Give the attached keys file: `keys load <file>`.")
            stored = keys.load(Path(args.target))
            if not stored:
                print("No keys found in that file. Check the key is pasted right after the = sign, then attach it again.")
                return 1
            print("Saved: " + ", ".join(keys.NAMES[v] for v in stored) + ".")
        elif args.action == "check":
            stored = list(keys.VARS)
        else:
            f = keys.ensure_file()
            keys.open_in_editor(f)
            print(f"Opened {f}. Paste the keys after the = signs, save, close the editor, then run `keys check`.")
            return 0
        for var in stored:
            if os.environ.get(var, "").strip():
                print(f"note: {var} is also set in this computer's environment, and that value is used instead.")
        names = {keys.NAMES[v] for v in stored}
        rows = [r for r in keys.check() if r[0] in names]
        for name, good, msg in rows:
            print(f"{'✓' if good else '✗'} {name}: {msg}")
        return 0 if all(good for _, good, _ in rows) else 1
```
Add `import os` at the top of `cli.py`.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_keys.py tests/test_cli.py -q`
Expected: PASS. Then the full suite: `uv run pytest -q` → PASS.

- [ ] **Step 6: Commit**

```bash
git add lesson-videos/scripts/lv/keys.py lesson-videos/scripts/lv/cli.py tests/test_keys.py tests/test_cli.py
git commit -m "lesson-videos: keys paste (from the clipboard) and keys load (attached file), never printing a key"
```

---

### Task 4: Skills address scripts through `${CLAUDE_SKILL_DIR}`; Cowork notes in make

**Files:**
- Modify: `lesson-videos/skills/make/SKILL.md:11,16` and add a Cowork section
- Modify: `lesson-videos/skills/setup/SKILL.md:13`
- Test: `tests/test_packaging.py`

**Interfaces:**
- Consumes: Task 0 decision (`KEYS_FILE_NAME`, upload path pattern), Task 3 commands.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_packaging.py`:
```python
def test_skills_use_skill_dir_not_plugin_root():
    offenders = [str(f.relative_to(REPO)) for f in (PLUGIN / "skills").rglob("*.md")
                 if "CLAUDE_PLUGIN_ROOT" in f.read_text(encoding="utf-8")]
    assert offenders == []
    for name in ("make", "setup"):
        text = (PLUGIN / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert 'uv run "${CLAUDE_SKILL_DIR}/../../scripts/lesson-videos.py"' in text
```

- [ ] **Step 2: Run to see it fail**

Run: `uv run pytest tests/test_packaging.py -q` → FAIL (offenders list make and setup).

- [ ] **Step 3: Edit the skills**

In both SKILL.md files replace the LV block's command with:
```
uv run "${CLAUDE_SKILL_DIR}/../../scripts/lesson-videos.py"
```
In `make/SKILL.md` line 16 replace both `${CLAUDE_PLUGIN_ROOT}/skills/make/` with `${CLAUDE_SKILL_DIR}/`.
In the parallel-helpers paragraph, keep "(with the real plugin path, since helpers don't get it substituted)".

Add to `make/SKILL.md`, after the "Ground rules" list:
```markdown
**In a Cowork cloud session** (claude.ai on the web; you're on a fresh Linux machine each time):
- Run `LV doctor --no-keys` once at the start. It installs what's missing (a browser from npm if the normal download is blocked) and names any website the teacher must allow under Settings → Capabilities → Additional allowed domains.
- If the teacher attached their keys file (`<KEYS_FILE_NAME>`), run `LV keys load "<path of the attached file>"`. **Never open it with Read, `cat` or any other tool**; `keys load` prints only which keys it found.
- The deck is among the attached files. Work next to it as usual, and when a chapter is rendered, share the MP4 (and its `.vtt`) as downloadable files. A file over 30 MB can't be downloaded: re-render that chapter with `--fps 24` and say so.
```
(Replace `<KEYS_FILE_NAME>` with Task 0's decision, `lesson-videos-keys.txt` or `lesson-videos.lvkeys`, and the attached-file path wording with what Task 0 observed.)

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_packaging.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add lesson-videos/skills/make/SKILL.md lesson-videos/skills/setup/SKILL.md tests/test_packaging.py
git commit -m "lesson-videos: skills find the scripts via CLAUDE_SKILL_DIR; Cowork notes in make"
```

---

### Task 5: The two key skills; setup hands off to them

**Files:**
- Create: `lesson-videos/skills/elevenlabs-get-api-key/SKILL.md`
- Create: `lesson-videos/skills/google-get-api-key/SKILL.md`
- Modify: `lesson-videos/skills/setup/SKILL.md` (steps 3–5)
- Test: `tests/test_packaging.py`

**Interfaces:**
- Consumes: `LV keys paste elevenlabs|gemini` (Task 3), `docs/keys/elevenlabs.md`, `docs/keys/google.md` (Task 6; links may land before the files, Task 6's link test catches gaps).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_packaging.py`:
```python
def test_key_skills_present_and_safe():
    import yaml
    for name, service in (("elevenlabs-get-api-key", "elevenlabs"), ("google-get-api-key", "gemini")):
        text = (PLUGIN / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        front = yaml.safe_load(text.split("---")[1])
        assert front["name"] == name and len(front["description"]) <= 1024
        assert f"keys paste {service}" in text
        assert "no screenshots" in text.lower() and "password" in text.lower()
    setup = (PLUGIN / "skills/setup/SKILL.md").read_text(encoding="utf-8")
    assert "elevenlabs-get-api-key" in setup and "google-get-api-key" in setup
```

- [ ] **Step 2: Run to see it fail**

Run: `uv run pytest tests/test_packaging.py::test_key_skills_present_and_safe -q` → FAIL (file missing).

- [ ] **Step 3: Write `skills/elevenlabs-get-api-key/SKILL.md`**

```markdown
---
name: elevenlabs-get-api-key
description: Use when a teacher wants an ElevenLabs API key for lesson-videos narration and Claude in Chrome is available. Opens the ElevenLabs pages in their Chrome, fills in the key's name and permissions, and saves the key from the clipboard with `keys paste` so it never appears in the chat.
---

# Get an ElevenLabs key with Claude in Chrome

In this skill, **LV** means this command (keep the quotes):

```
uv run "${CLAUDE_SKILL_DIR}/../../scripts/lesson-videos.py"
```

**Rules for the whole skill**
- You never type passwords, create accounts, accept terms, or enter payment details. The teacher does those in the tab; you wait.
- Ask the teacher before clicking the final **Create** button.
- **Key secrecy:** from the moment the new key is shown until the teacher tells you they clicked **Copy** and closed that dialog, take **no screenshots** and **do not read the page** of that tab (no read_page, get_page_text, find or zoom). Then save it with `LV keys paste elevenlabs`.
- Never ask for the key in chat and never read `keys.env`. If the teacher pastes a key into the chat, tell them to delete that key on the website and create a new one.

## 0. Check Chrome
Call `mcp__claude-in-chrome__tabs_context_mcp`. If the Claude in Chrome tools aren't available or don't respond, tell the teacher in one sentence and point them to the illustrated guide `${CLAUDE_SKILL_DIR}/../../docs/keys/elevenlabs.md`; stop.

## 1. Explain the plans (before they sign up)
- **Free plan:** 10,000 characters a month, about one 5-minute video. Free-plan audio is for non-commercial use, a published video's title must include "elevenlabs.io", and the free plan must use a personal email address.
- **Starter:** $6/month for 30,000 characters (about four videos) and a commercial licence; they can cancel after the unit.
- They should read ElevenLabs' use policy (elevenlabs.io/use-policy) themselves: it restricts use by government entities without authorization. Don't decide for them.

## 2. Open the keys page
Open a new tab (`tabs_create_mcp`) at `https://elevenlabs.io/app/settings/api-keys`. If it shows a sign-in or sign-up page, tell the teacher to sign in or sign up in that tab and say "done"; wait.

## 3. Fill in the key
Click **Create API Key**. Set the name to `lesson-videos`. Under permissions turn on **Text to Speech** (access) and **User** (read); leave everything else off. Suggest a credit quota (30,000) so the key can never spend more; set it if they agree.

Tell the teacher what you filled in and ask: "Shall I click Create?" Click only after a yes.

## 4. Copy, then save
After clicking Create, say: "Your key is on screen now. Click **Copy** next to it, close the dialog, and tell me when you're done. I won't look at the page until then." Take no screenshots and read nothing until they answer.

Then run:
```
LV keys paste elevenlabs
```
It saves the key from the clipboard, clears the clipboard, tests the key and prints only its last four characters and the credits left. If it says the clipboard doesn't hold a key, ask them to click Copy again and re-run it.

## 5. Done
Tell them the key works and how many characters are left, then close the tab you opened. If you came from `/lesson-videos:setup`, continue there.
```

- [ ] **Step 4: Write `skills/google-get-api-key/SKILL.md`**

```markdown
---
name: google-get-api-key
description: Use when a teacher wants a Google Gemini API key for lesson-videos music and AI clips and Claude in Chrome is available. Opens Google AI Studio in their Chrome, creates the key, saves it from the clipboard with `keys paste` so it never appears in the chat, then guides billing and sets a spend cap.
---

# Get a Gemini key with Claude in Chrome

In this skill, **LV** means this command (keep the quotes):

```
uv run "${CLAUDE_SKILL_DIR}/../../scripts/lesson-videos.py"
```

**Rules for the whole skill**
- You never type passwords, create accounts, accept terms, or enter payment or card details. The teacher does those in the tab; you wait.
- Ask the teacher before clicking **Create API key** and before saving a spend cap.
- **Key secrecy:** from the moment the new key is shown until the teacher tells you they clicked **Copy** and closed that dialog, take **no screenshots** and **do not read the page** of that tab (no read_page, get_page_text, find or zoom). Then save it with `LV keys paste gemini`.
- Never ask for the key in chat and never read `keys.env`. If the teacher pastes a key into the chat, tell them to delete that key in AI Studio and create a new one.

## 0. Check Chrome
Call `mcp__claude-in-chrome__tabs_context_mcp`. If the Claude in Chrome tools aren't available or don't respond, tell the teacher in one sentence and point them to the illustrated guide `${CLAUDE_SKILL_DIR}/../../docs/keys/google.md`; stop.

## 1. Explain the cost (before anything else)
Music and AI clips need a Google account with billing turned on (there's no free tier for them), a minimum $5 prepayment, and cost about $0.40 per clip and $0.08 per music track: roughly $2–3 for a whole unit. Use a **personal** Google account; school accounts often have AI Studio turned off. Ask whether they want to go ahead.

## 2. Create the key
Open a new tab at `https://aistudio.google.com/api-keys`. If Google asks them to sign in or accept terms, they do it and say "done"; wait. Ask "Shall I click Create API key?"; on yes, click it and let it create a project if it asks.

After clicking, say: "Your key is on screen now. Click **Copy** next to it, close the dialog, and tell me when you're done. I won't look at the page until then." Take no screenshots and read nothing until they answer. Then run:
```
LV keys paste gemini
```

## 3. Billing (the teacher pays; you only open the page)
Navigate the same tab to `https://aistudio.google.com/billing` (or click the "Set up billing" link). Tell the teacher to link a billing account and add the $5 prepayment themselves, and say "done"; wait.

## 4. Spend cap
Navigate to `https://aistudio.google.com/spend`. Propose a monthly cap of $10. On their yes, set it and save. Tell them the amount you saved.

## 5. Done
Billing is only confirmed the first time music or a clip is made, because testing it costs money. Close the tab you opened. If you came from `/lesson-videos:setup`, continue there.
```

- [ ] **Step 5: Update `skills/setup/SKILL.md`**

At the start of step 3 add:
```markdown
**If Claude in Chrome is connected** (`mcp__claude-in-chrome__tabs_context_mcp` answers), offer to do the clicking: for ElevenLabs follow `/lesson-videos:elevenlabs-get-api-key`, for Gemini `/lesson-videos:google-get-api-key`; both save the key with `LV keys paste`, so skip step 5 for that key. Otherwise use the steps below; the teacher can also follow the illustrated guides in `${CLAUDE_SKILL_DIR}/../../docs/keys/`.
```
In step 5 add a line: `If the teacher prefers, they can click Copy on the website and you run LV keys paste elevenlabs (or gemini) instead of using the file.`

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_packaging.py -q` → PASS.

- [ ] **Step 7: Commit**

```bash
git add lesson-videos/skills tests/test_packaging.py
git commit -m "lesson-videos: elevenlabs-get-api-key and google-get-api-key skills via Claude in Chrome"
```

---

### Task 6: Install and key guides (text), keys template, docs tests

Screenshots are added in Task 8; this task writes the text and the link test.

**Files:**
- Create: `lesson-videos/docs/install/claude-code.md`, `lesson-videos/docs/install/cowork.md`
- Create: `lesson-videos/docs/keys/README.md`, `elevenlabs.md`, `google.md`, `keys-file.md`
- Create: `lesson-videos/docs/keys-template.txt` (or `lesson-videos.lvkeys` per Task 0)
- Create: `tests/test_docs.py`

**Interfaces:**
- Consumes: Task 0 decision; command names from Tasks 3–5.
- Produces: doc paths the README (Task 7) links: `docs/install/claude-code.md`, `docs/install/cowork.md`, `docs/keys/README.md`.

- [ ] **Step 1: Write `tests/test_docs.py`**

```python
import re

from conftest import PLUGIN
from lv import keys

LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
TEMPLATES = ("keys-template.txt", "lesson-videos.lvkeys")


def _docs():
    return [PLUGIN / "README.md", *sorted((PLUGIN / "docs").rglob("*.md"))]


def test_relative_links_resolve():
    broken = []
    for md in _docs():
        for target in LINK.findall(md.read_text(encoding="utf-8")):
            if re.match(r"[a-z]+:", target) or target.startswith("#"):
                continue
            if not (md.parent / target.split("#")[0]).exists():
                broken.append(f"{md.relative_to(PLUGIN)} -> {target}")
    assert broken == []


def test_images_are_small():
    assert [p.name for p in (PLUGIN / "docs" / "images").glob("*") if p.stat().st_size > 400_000] == []


def test_keys_template_matches_code():
    found = [PLUGIN / "docs" / t for t in TEMPLATES if (PLUGIN / "docs" / t).exists()]
    assert len(found) == 1
    assert found[0].read_text(encoding="utf-8") == keys.TEMPLATE
```

- [ ] **Step 2: Run to see it fail**

Run: `uv run pytest tests/test_docs.py -q` → `test_keys_template_matches_code` FAILS (no template).

- [ ] **Step 3: Write the template**

Write `keys.TEMPLATE`'s exact text to the file name chosen in Task 0:
```bash
uv run python -c "import sys; sys.path.insert(0,'lesson-videos/scripts'); from lv import keys; open('lesson-videos/docs/keys-template.txt','w',encoding='utf-8',newline='\n').write(keys.TEMPLATE)"
```
(Use `lesson-videos.lvkeys` as the target name if Task 0 chose it.)

- [ ] **Step 4: Write `docs/install/claude-code.md`**

Sections and exact content:
1. `# Install with Claude Code (recommended)` — one line: install once; keys are remembered; videos appear next to your deck.
2. `## What you need` — Claude Code desktop app or terminal + a Claude plan (link https://claude.com/claude-code); Windows: Git for Windows first (https://git-scm.com/download/win); about 1 GB free disk; a network that allows downloads.
3. `## Install the plugin (once)` — two options. **A. In Claude Code:** the two `/plugin` lines from today's README. **B. On claude.ai:** Customize → Plugins → Add → Add marketplace → type `DanielLandi/plugins` → Sync → find **Lesson videos** → Add; it appears in Claude Code the next time you open it.
4. `## Set up (about 10 minutes, once)` — type `/lesson-videos:setup`; what it installs; voice choice; keys: link to [../keys/README.md](../keys/README.md).
5. `## Make videos` — today's README "Make videos" section, unchanged in substance.
6. `## Troubleshooting` — today's README troubleshooting table plus a row: "Claude can't open Chrome | Install the Claude in Chrome extension, or follow the [key guides](../keys/README.md) yourself."
7. `## Keeping lessons in a project folder (optional)` — today's README paragraph.

- [ ] **Step 5: Write `docs/install/cowork.md`**

Sections and exact content:
1. `# Use it in Cowork (nothing to install)` — for Claude Pro or Max on claude.ai in a web browser; good for school laptops that don't allow installing apps. Honest trade-off line: each session starts on a fresh cloud computer, so you attach your deck (and keys file) each time and download the finished videos.
2. `## 1. Add the plugin (once)` — claude.ai → **Customize** → **Plugins** → **Add** → **Add marketplace** → **Add from a repository** → type `DanielLandi/plugins` → **Sync** → **Discover** → **Lesson videos** → **Add**. Screenshot slots: `![Add marketplace](../images/cowork-add-marketplace.webp)` (added in Task 8).
3. `## 2. Allow the voice website (once)` — Settings → **Capabilities** → **Additional allowed domains** → add `speech.platform.bing.com` (free voice). Only if you use them: `api.elevenlabs.io` (ElevenLabs), `generativelanguage.googleapis.com` (music and clips). Why: claude.ai lets its cloud computers reach only package sites unless you allow more. Screenshot slot `../images/cowork-allowed-domains.webp`.
4. `## 3. Make videos` — start a new chat, attach the deck (`.pptx` or `.pdf`), and if you use ElevenLabs/Gemini attach your keys file ([how to make it](../keys/keys-file.md)); type `/lesson-videos:make`. The first minutes go to setting up the cloud computer. Each finished chapter appears as a file to download (with its `.vtt` captions).
5. `## Good to know` — rendering is slower than on a laptop (about 8 minutes per 5-minute video); a session that ends early can be continued by attaching the same files and running `/lesson-videos:make` again, but finished chapters must be downloaded before you leave; a Pro plan may need a few sessions for a whole unit.
6. `## Troubleshooting` — rows: "blocked by Claude's network setting … add <domain>" → do step 2 and start a **new** chat; "No keys found in that file" → see keys-file guide; "Chromium" errors → run `/lesson-videos:setup` in the same chat.

- [ ] **Step 6: Write the key guides**

`docs/keys/README.md`:
- Opening callout, verbatim: `> **Have Claude Code and the Claude in Chrome extension?** Type `/lesson-videos:elevenlabs-get-api-key` (or `/lesson-videos:google-get-api-key`) and Claude opens the pages and clicks through for you; you only sign in and, for Google, add billing.`
- `## Do you need a key?` table: no key → free Microsoft voice, $0; ElevenLabs → most natural voice, free plan ≈ 1 video/month, Starter $6/month; Google Gemini → music ($0.08/track) and AI clips ($0.40 each), $5 minimum prepayment.
- Links: [ElevenLabs step by step](elevenlabs.md), [Google step by step](google.md), [Using keys in Cowork](keys-file.md).
- `## Keeping keys safe` — never paste a key into the chat; if you did, delete it on the website and make a new one.

`docs/keys/elevenlabs.md`: the plan explanation (same facts as the skill's step 1), then numbered steps 1–6 matching the skill (open https://elevenlabs.io/app/settings/api-keys; sign up/in; Create API Key; name `lesson-videos`; permissions Text to Speech + User read; optional quota 30,000; Create; **Copy** — shown only once), then `## Save it` with two options: Claude Code → ask Claude to run `keys paste elevenlabs` right after copying; or `/lesson-videos:setup` opens the keys file to paste into. Screenshot slots: `elevenlabs-keys-page.webp`, `elevenlabs-create-dialog.webp` (Task 8).

`docs/keys/google.md`: cost explanation, personal-account note, steps: https://aistudio.google.com/api-keys → sign in → Create API key (let it create a project) → **Copy**; billing at https://aistudio.google.com/billing ($5 prepayment); spend cap at https://aistudio.google.com/spend ($10/month suggested); `## Save it` as above with `keys paste gemini`. Screenshot slots: `google-api-keys.webp`, `google-billing.webp`, `google-spend-cap.webp` (Task 8).

`docs/keys/keys-file.md`: for Cowork. Download [the empty keys file](../keys-template.txt) (or `../lesson-videos.lvkeys`); open it in TextEdit (Mac: **Format → Make Plain Text** if it opens as rich text) or Notepad; paste each key right after its `=`, no spaces; save; attach it to each Cowork chat along with your deck. Claude imports it with `keys load` and never shows it. Keep the file private; don't email it.

Leave image links out of these files until Task 8 adds the images (the link test would fail on missing files). Put an HTML comment `<!-- screenshot: <name>.webp -->` where each goes, so Task 8 knows the spots.

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/test_docs.py tests/test_packaging.py -q` → PASS (`test_no_private_paths_in_plugin` also scans the new `.md` files).

- [ ] **Step 8: Commit**

```bash
git add lesson-videos/docs tests/test_docs.py
git commit -m "lesson-videos: install guides (Claude Code, Cowork), key guides, keys template"
```

---

### Task 7: Sample chapter, stills and the new README

**Files:**
- Create: `lesson-videos/docs/images/sample-1-hook.webp`, `sample-2-diagram.webp`, `sample-3-quiz.webp`, `sample-4-recap.webp`
- Rewrite: `lesson-videos/README.md`

**Interfaces:**
- Consumes: doc paths from Task 6.
- Produces: release URL `https://github.com/DanielLandi/plugins/releases/download/lesson-videos-sample-v1/water-cycle-sample.mp4` (upload happens in Task 9 after the maintainer's yes).

- [ ] **Step 1: Make one chapter from the public sample deck**

Copy `examples/water-cycle.pptx` to `<scratchpad>/sample/water-cycle.pptx` and follow `/lesson-videos:make` there with defaults: grade 6, one chapter, 2–3 minutes, free Microsoft voice, no music or clips. Show the maintainer chapter 1's `final.jpg` and ask for a yes before using it.

- [ ] **Step 2: Extract four stills and convert to WebP**

Pick times for hook, a diagram scene, the quiz, the recap from the chapter's `timing.js` scene starts (+1.5 s). For each:
```bash
uv run python - <<'EOF'
import subprocess, sys
sys.path.insert(0, "lesson-videos/scripts")
from lv import tools
from PIL import Image
mp4 = "<scratchpad>/sample/lesson-videos/Chapter 1 - <Title>.mp4"
for name, t in [("sample-1-hook", T1), ("sample-2-diagram", T2), ("sample-3-quiz", T3), ("sample-4-recap", T4)]:
    png = f"<scratchpad>/{name}.png"
    subprocess.run([tools.ffmpeg(), "-v", "error", "-y", "-ss", str(t), "-i", mp4, "-frames:v", "1", png], check=True)
    Image.open(png).convert("RGB").resize((1280, 720)).save(f"lesson-videos/docs/images/{name}.webp", "WEBP", quality=80)
EOF
```
(Fill `T1..T4` and the paths with the real values; the heredoc runs as written once they are.) Check each file is under 400 KB: `ls -l lesson-videos/docs/images`.

- [ ] **Step 3: Rewrite `lesson-videos/README.md`**

Order and content (spec §4):
1. `# lesson-videos` + one sentence: *Turn your own slide deck into short narrated, animated study videos, one per chapter.*
2. Why paragraph: students rewatch the lesson in the teacher's own words; every fact comes from the slides; Claude also lists contradictions and typos it finds in the deck before building anything.
3. `## See a sample` — a 2×2 table of the four stills (`docs/images/sample-*.webp`), then `**[▶ Watch the full sample video](https://github.com/DanielLandi/plugins/releases/download/lesson-videos-sample-v1/water-cycle-sample.mp4)**` and "Made from [examples/water-cycle.pptx](../examples/water-cycle.pptx) with the free voice, no edits."
4. `## What each video has` — today's bullet list.
5. `## Get started` — table: | | Claude Code (recommended) | Cowork |; rows: *Install* (app, once / nothing), *Each time* (open the deck's folder, type `/lesson-videos:make` / attach the deck, download the videos), *Best for* (your own computer / school laptops that block installs), *Guide* ([docs/install/claude-code.md](docs/install/claude-code.md) / [docs/install/cowork.md](docs/install/cowork.md)).
6. `## Optional: a better voice, music and clips` — free voice by default; ElevenLabs and Google costs one line each; link [docs/keys/](docs/keys/README.md).
7. `## Good to know` — privacy, free-voice terms, ElevenLabs free-plan rules, image licences, where things are kept (today's points, one or two lines each).
8. Footer: `Made by Daniel Landi. MIT licence. Fonts: Patrick Hand and Nunito (SIL Open Font Licence).`

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_docs.py tests/test_packaging.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add lesson-videos/README.md lesson-videos/docs/images/sample-*.webp
git commit -m "lesson-videos: README leads with purpose and a sample; install moves to docs/"
```

---

### Task 8: Redacted screenshots for the key and Cowork guides

**Files:**
- Create: `lesson-videos/docs/images/{elevenlabs-keys-page,elevenlabs-create-dialog,google-api-keys,google-billing,google-spend-cap,cowork-add-marketplace,cowork-allowed-domains}.webp`
- Modify: `lesson-videos/docs/keys/elevenlabs.md`, `google.md`, `lesson-videos/docs/install/cowork.md` (replace the `<!-- screenshot: … -->` comments with image links)

**Interfaces:**
- Consumes: Task 6's screenshot spots.

- [ ] **Step 1: Capture through Claude in Chrome, never past the key**

In a new tab of the maintainer's Chrome, for each page: navigate, `computer screenshot` with `save_to_disk: true` into the scratchpad. For the create dialogs, fill the name/permissions, screenshot, then **Cancel** — do not create a key, so nothing needs deleting. Pages: ElevenLabs api-keys list, ElevenLabs create dialog (filled, before Create); AI Studio api-keys page; AI Studio billing page; AI Studio spend page; claude.ai Add marketplace dialog (with `DanielLandi/plugins` typed); claude.ai Settings → Capabilities allowlist section.

- [ ] **Step 2: Crop and redact**

For each PNG, decide the crop box and every rectangle that shows a name, email, avatar, organization, balance, project ID, or any part of an existing key, by looking at the image. Then:
```bash
uv run python - <<'EOF'
from PIL import Image, ImageDraw
src, out = "<scratchpad>/<shot>.png", "<scratchpad>/<shot>-redacted.png"
crop = (X0, Y0, X1, Y1)
boxes = [(x0, y0, x1, y1), ...]  # in original-image coordinates
im = Image.open(src).convert("RGB")
d = ImageDraw.Draw(im)
for b in boxes:
    d.rectangle(b, fill=(30, 30, 30))
im.crop(crop).save(out)
EOF
```

- [ ] **Step 3: Show the maintainer every redacted image and wait for a yes**

Open them for review: `open <scratchpad>/*-redacted.png`, and list what was blacked out in each. Redo any the maintainer flags.

- [ ] **Step 4: Convert approved images and link them**

Convert each approved PNG to `lesson-videos/docs/images/<name>.webp` (width ≤ 1200 px, `quality=80`), then replace each `<!-- screenshot: <name>.webp -->` with `![<short alt text>](../images/<name>.webp)`.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_docs.py -q` → PASS (links resolve, images under 400 KB).

- [ ] **Step 6: Commit**

```bash
git add lesson-videos/docs
git commit -m "lesson-videos: redacted screenshots in the key and Cowork guides"
```

---

### Task 9: Version 0.4.0, gate, merge, push, sample release

**Files:**
- Modify: `lesson-videos/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (lesson-videos entry), `lesson-videos/scripts/lv/__init__.py`

- [ ] **Step 1: Bump the version in all three places to `0.4.0`**

- [ ] **Step 2: Run the gate**

Run: `uv run pytest -q`
Expected: all pass (studio-marked tests are skipped by default).

- [ ] **Step 3: Commit**

```bash
git add lesson-videos/.claude-plugin/plugin.json .claude-plugin/marketplace.json lesson-videos/scripts/lv/__init__.py
git commit -m "lesson-videos 0.4.0: install guides, key skills, Cowork support"
```

- [ ] **Step 4: Ask the maintainer to confirm the merge, push and release**

Show: commit list (`git log --oneline main..`), and that the release will publish `water-cycle-sample.mp4` publicly. Wait for a yes.

- [ ] **Step 5: Merge, push, release**

```bash
git checkout main && git merge --no-ff lesson-videos-install-docs -m "Merge lesson-videos 0.4.0 (install guides, key skills, Cowork support)"
git push origin main
gh release create lesson-videos-sample-v1 "<scratchpad>/sample/lesson-videos/Chapter 1 - <Title>.mp4#water-cycle-sample.mp4" -R DanielLandi/plugins --title "lesson-videos sample video" --notes "Sample chapter made from examples/water-cycle.pptx with the free voice."
```
If `gh` names the asset after the file instead of the `#` label, copy the MP4 to `<scratchpad>/water-cycle-sample.mp4` first and upload that. Then `curl -sI <release URL>` → expect `302`.

---

### Task 10: Live verification in a Cowork cloud session

**Files:** none unless a fix is needed (then a new branch, test, commit, merge as above).

- [ ] **Step 1: Wait for the marketplace to sync 0.4.0**

claude.ai → Customize → Plugins → Lesson videos shows `0.4.0` (use **Check for updates** if needed).

- [ ] **Step 2: Ask the maintainer to add `speech.platform.bing.com` to the allowed domains**

Settings → Capabilities → Additional allowed domains. Claude does not change this setting.

- [ ] **Step 3: Run the check in a new claude.ai session through Claude in Chrome**

Attach `examples/water-cycle.pptx` and a keys file with **fake** values; send: *"Run `/lesson-videos:setup` checks only: `LV doctor --no-keys`, then `LV keys load` on the attached keys file (don't open it), then make a 1-minute single-chapter video from the attached deck with the free voice, skipping the interview with defaults. Report doctor's output, which voice narrated, render time and file size, and share the MP4."*

Expected: doctor ✓ Chromium (from npm), Narration "free Microsoft voice works"; `keys load` reports ElevenLabs and Gemini saved (check fails on fake keys, which is fine); the MP4 has a voice; doctor ran twice without breaking the browser.

- [ ] **Step 4: Report results to the maintainer**

Table of checks with evidence. Any failure → new branch `lesson-videos-cowork-fix`, a failing test that reproduces it, fix, gate, merge, push, re-run Step 3.
