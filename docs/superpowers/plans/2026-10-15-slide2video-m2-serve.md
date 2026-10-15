# slide2video M2 (serve while Claude Code is open) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/lesson-videos:serve` keeps this computer making slide2video.com steps (awake, one step after another) until the Claude Code window closes or the teacher presses Disconnect on the website.

**Architecture:** The plugin gains `LV worker --watch` (a loop around the existing one-step worker), a small keep-awake module (`caffeinate` on macOS, `SetThreadExecutionState` on Windows) and a `serve` skill that starts the loop as a background Bash task. The website gains a `stop_requested_at` mark per device, set by a Disconnect button and delivered once as `{"stop": true}` on the worker's next `GET /api/device/next`; `?start=1` on a watcher's first call clears a stale mark.

**Tech Stack:** Python 3.12 via `uv` (pytest, a fake HTTP site in `tests/site_fake.py`); Cloudflare Worker in TypeScript (Hono, D1, Vitest with `@cloudflare/vitest-pool-workers`).

**Spec:** `docs/superpowers/specs/2026-10-15-slide2video-m2-serve-design.md` (plugins repo, branch `m2-serve`).

## Global Constraints

- Two repos. Plugin work: `/Users/daniellandi/Projects/plugins` on branch `m2-serve` (rules: `plugins/AGENTS.md`). Site work: `/Users/daniellandi/Projects/slide2video` on a new branch `m2-disconnect` off `main` (rules: `slide2video/AGENTS.md`; **ignore the plugins repo's rules there**).
- Plugin Python: `encoding="utf-8"` on every file read/write; subprocesses as argument lists; Windows and macOS (no bash-only syntax in skills; Windows code paths best effort, untested).
- Skills call commands only as `LV <command>` where LV = `uv run "${CLAUDE_SKILL_DIR}/../../scripts/lesson-videos.py"`, with the `/root/.claude/plugins/synced/` fallback sentence (see existing skills).
- No compatibility with plugin versions before 0.7.0 is needed (nobody runs them). The job contract stays at version 1.
- Poll interval when idle: **30 s**. Network/5xx back-off: **30 s → 60 s → 120 s → 300 s** (cap), reset after a successful call.
- Online on the website = last seen **under 2 minutes** ago.
- Disconnect lets the running step **finish**; no cancel.
- Version **0.7.0** in `lesson-videos/.claude-plugin/plugin.json`, the lesson-videos entry in `.claude-plugin/marketplace.json`, `lesson-videos/scripts/lv/__init__.py`.
- Site: every query scoped to the teacher; a cross-teacher test for every new route; don't edit `src/legal.ts`; escape all text (`expectSafe`).
- Commit messages end with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_012XSHebKL7ftdoXou4Dxodb
  ```
- Gates: plugins `uv run pytest -q` (repo root); slide2video `npm run check && npm test`. Don't merge, push or deploy inside tasks.

## Review Focus

1. **Claude Code stops the background task** (SIGTERM, not Ctrl-C): the worker must still remove its lock files and end keep-awake; a later `serve` must start normally. → Task 2 test `test_watch_cleans_up_on_sigterm_style_interrupt` and Task 1 `-w <pid>`.
2. **Disconnect pressed while the computer is off**, then `serve` started days later: must not stop at once. → Task 4 `?start=1` test, Task 2 `test_watch_first_call_sends_start`.
3. **Wi-Fi drops for an hour** while waiting: the loop must survive with back-off, not exit. → Task 2 `test_watch_backs_off_on_network_errors_and_recovers`.
4. **`serve` run twice** (teacher runs the command again in a second window): the second must say it's already running and exit 0, not run two loops. → Task 2 `test_second_watcher_is_refused`.
5. **Pairing revoked on the website (Remove) while serve runs**: the loop must stop with the "connect again" message, not spin. → Task 2 `test_watch_stops_when_not_paired`.

---

## Part A — plugin (`/Users/daniellandi/Projects/plugins`, branch `m2-serve`)

### Task 1: Keep-awake module

**Files:**
- Create: `lesson-videos/scripts/lv/awake.py`
- Test: `tests/test_awake.py`

**Interfaces:**
- Produces: `awake.keep_awake(out=print, platform=sys.platform, popen=subprocess.Popen, which=shutil.which, kernel32=None) -> object | None` and `awake.release(handle, kernel32=None) -> None`. The handle is a `Popen` (macOS), the module constant `awake.WINDOWS` (Windows) or `None` (not kept awake).

- [ ] **Step 1: Write the failing tests** (`tests/test_awake.py`)

```python
import os

from lv import awake


class FakeProc:
    def __init__(self, argv, **kw):
        self.argv, self.kw, self.terminated = argv, kw, False

    def terminate(self):
        self.terminated = True


def test_macos_runs_caffeinate_tied_to_this_process():
    lines = []
    h = awake.keep_awake(out=lines.append, platform="darwin", popen=FakeProc, which=lambda n: "/usr/bin/caffeinate")
    assert h.argv == ["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())]
    assert lines == []
    awake.release(h)
    assert h.terminated


def test_windows_sets_and_clears_the_execution_state():
    calls = []

    class K:
        def SetThreadExecutionState(self, flags):
            calls.append(flags)
            return 1
    k = K()
    h = awake.keep_awake(out=print, platform="win32", kernel32=k)
    assert h is awake.WINDOWS and calls == [awake.ES_CONTINUOUS | awake.ES_SYSTEM_REQUIRED]
    awake.release(h, kernel32=k)
    assert calls[-1] == awake.ES_CONTINUOUS


def test_other_systems_warn_and_continue():
    lines = []
    assert awake.keep_awake(out=lines.append, platform="linux") is None
    assert lines == [awake.WARNING]
    awake.release(None)  # no error


def test_macos_without_caffeinate_warns():
    lines = []
    assert awake.keep_awake(out=lines.append, platform="darwin", which=lambda n: None) is None
    assert lines == [awake.WARNING]
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_awake.py -q`
Expected: FAIL (`ImportError: cannot import name 'awake'`).

- [ ] **Step 3: Implement** (`lesson-videos/scripts/lv/awake.py`)

```python
"""Keep this computer awake while `worker --watch` runs: a sleeping computer can't see new lessons. The display may
still turn off. macOS: caffeinate, tied to this process so it ends with it even if the worker is killed. Windows:
the thread execution state (it belongs to the calling thread, so call both functions from the main thread)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
WINDOWS = object()
WARNING = "This computer may sleep while waiting for lessons; keep it awake yourself."


def keep_awake(out=print, platform=sys.platform, popen=subprocess.Popen, which=shutil.which, kernel32=None):
    if platform == "darwin":
        exe = which("caffeinate")
        if exe:
            try:
                return popen([exe, "-i", "-w", str(os.getpid())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass
    elif platform == "win32":
        try:
            k = kernel32 or __import__("ctypes").windll.kernel32
            if k.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED):
                return WINDOWS
        except (AttributeError, OSError):
            pass
    out(WARNING)
    return None


def release(handle, kernel32=None) -> None:
    if handle is None:
        return
    if handle is WINDOWS:
        try:
            (kernel32 or __import__("ctypes").windll.kernel32).SetThreadExecutionState(ES_CONTINUOUS)
        except (AttributeError, OSError):
            pass
        return
    try:
        handle.terminate()
    except OSError:
        pass
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_awake.py -q` → 4 passed.

- [ ] **Step 5: Commit**

```bash
git add lesson-videos/scripts/lv/awake.py tests/test_awake.py
git commit -m "lesson-videos: keep-awake for the watching worker (caffeinate on macOS, execution state on Windows)"
```

### Task 2: `worker --watch` loop

**Files:**
- Modify: `lesson-videos/scripts/lv/worker.py` (`_lock` ~line 137, `run_once` ~line 351; add `watch`)
- Modify: `lesson-videos/scripts/lv/cli.py` (worker parser ~line 76, dispatch ~line 184)
- Modify: `tests/site_fake.py` (FakeSite: `stop_next`, `next_queries`, `fail_next`)
- Test: `tests/test_worker_watch.py`

**Interfaces:**
- Consumes: `awake.keep_awake`, `awake.release` (Task 1); `site.call`, `site.status`, `net.ApiError(status, detail, url)`, `UserError`.
- Produces: `worker.watch(claude=None, out=print, sleep=time.sleep, awake_on=awake.keep_awake, awake_off=awake.release) -> int`; `worker._once(claude, out, start=False) -> tuple[str, int]` returning `(IDLE | RAN | STOP, exit_code)`; constants `POLL = 30`, `BACKOFF = (30, 60, 120, 300)`. `run_once()` keeps its signature and exit codes. CLI: `worker --watch`.

- [ ] **Step 1: Extend the fake site** (`tests/site_fake.py`)

In `FakeSite.__init__` add: `self.stop_next, self.next_queries, self.fail_next = False, [], 0`.
Replace the `/api/device/next` branch with:

```python
                if u.path == "/api/device/next":
                    site.next_queries.append(u.query)
                    if u.query == "start=1":       # like the real site: a fresh watcher clears a stale stop
                        site.stop_next = False
                    if site.fail_next > 0:
                        site.fail_next -= 1
                        return self._send(503, {"error": "busy"})
                    if site.stop_next:
                        site.stop_next = False
                        return self._send(200, {"stop": True})
                    return self._send(200, site.turns.pop(0)) if site.turns else self._send(204)
```

- [ ] **Step 2: Write the failing tests** (`tests/test_worker_watch.py`)

```python
import os

import pytest

from lv import worker
from test_worker import DECK, QUESTIONS, _claude_writing, _turn, lessons  # noqa: F401  (fixture)


class Awake:
    def __init__(self):
        self.on = self.off = 0

    def keep(self, out=print):
        self.on += 1
        return "handle"

    def release(self, h):
        assert h == "handle"
        self.off += 1


def _watch(claude, **kw):
    a, lines, sleeps = Awake(), [], []
    code = worker.watch(claude=claude, out=lines.append, sleep=sleeps.append, awake_on=a.keep, awake_off=a.release, **kw)
    return code, lines, sleeps, a


def test_watch_runs_queued_turns_back_to_back_then_stops(paired, lessons):
    for i in range(2):
        paired.turns.append(_turn(tid=f"trn_{i}123456789abcdefghijkl"))
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    paired.stop_next = False
    fake = _claude_writing(QUESTIONS)

    def stop_after_turns(seconds):  # the first idle wait: ask the site to stop
        paired.stop_next = True
    a, lines = Awake(), []
    code = worker.watch(claude=fake, out=lines.append, sleep=stop_after_turns, awake_on=a.keep, awake_off=a.release)
    assert code == 0 and len(paired.finished) == 2 and len(fake.calls) == 2
    assert any("Disconnected from the website" in l and "/lesson-videos:serve" in l for l in lines)
    assert a.on == 1 and a.off == 1
    assert not (lessons / ".worker-watch.lock").exists() and not (lessons / ".worker.lock").exists()


def test_watch_first_call_sends_start_so_a_stale_stop_is_ignored(paired, lessons):
    paired.stop_next = True  # Disconnect pressed while this computer was off

    def sleep(s):  # first idle wait: now a real Disconnect
        paired.stop_next = True
    a = Awake()
    code = worker.watch(claude=_claude_writing(QUESTIONS), out=lambda l: None, sleep=sleep, awake_on=a.keep, awake_off=a.release)
    assert code == 0 and paired.next_queries == ["start=1", ""]  # did not stop on the stale mark


def test_watch_idles_with_the_poll_interval(paired, lessons):
    calls = {"n": 0}

    def sleep(s):
        assert s == worker.POLL
        calls["n"] += 1
        if calls["n"] == 3:
            paired.stop_next = True
    a = Awake()
    worker.watch(claude=_claude_writing(QUESTIONS), out=lambda l: None, sleep=sleep, awake_on=a.keep, awake_off=a.release)
    assert paired.next_queries == ["start=1", "", "", ""]  # only the first call says start=1


def test_watch_backs_off_on_network_errors_and_recovers(paired, lessons, monkeypatch):
    monkeypatch.setattr(worker.net, "request", _no_retry(worker.net.request))
    paired.fail_next = 5
    waits = []

    def sleep(s):
        waits.append(s)
        if paired.fail_next == 0 and len(waits) > 5:
            paired.stop_next = True
    a = Awake()
    code = worker.watch(claude=_claude_writing(QUESTIONS), out=lambda l: None, sleep=sleep, awake_on=a.keep, awake_off=a.release)
    assert code == 0
    assert waits[:6] == [30, 60, 120, 300, 300, worker.POLL]  # back-off caps at 300, then the normal poll again


def _no_retry(request):
    def call(*a, **kw):
        kw["retries"] = 0
        return request(*a, **kw)
    return call


def test_watch_stops_when_not_paired(paired, lessons):
    paired.token = "something-else"  # the site no longer accepts this computer's token (Remove on the website)
    code, lines, sleeps, a = _watch(_claude_writing(QUESTIONS))
    assert code == 1 and "isn't connected to slide2video.com" in lines[-1] and a.off == 1


def test_watch_stops_on_contract_mismatch(paired, lessons):
    paired.contract = 2
    code, lines, sleeps, a = _watch(_claude_writing(QUESTIONS))
    assert code == 1 and "Update the lesson-videos plugin" in lines[-1]


def test_second_watcher_is_refused(paired, lessons):
    lessons.mkdir(parents=True)
    (lessons / ".worker-watch.lock").write_text(str(os.getpid()), encoding="utf-8")
    code, lines, sleeps, a = _watch(_claude_writing(QUESTIONS))
    assert code == 0 and "already making videos" in lines[-1] and a.on == 0 and paired.next_queries == []


def test_watch_cleans_up_on_sigterm_style_interrupt(paired, lessons):
    def interrupted(seconds):
        raise KeyboardInterrupt  # SIGTERM is turned into KeyboardInterrupt by watch()
    a = Awake()
    code = worker.watch(claude=_claude_writing(QUESTIONS), out=lambda l: None, sleep=interrupted,
                        awake_on=a.keep, awake_off=a.release)
    assert code == 0 and a.off == 1 and not (lessons / ".worker-watch.lock").exists()


def test_run_once_still_reports_idle_as_zero(paired, lessons):
    assert worker.run_once(claude=_claude_writing(QUESTIONS)) == 0


def test_cli_worker_watch_is_wired(monkeypatch):
    from lv import cli
    seen = {}
    monkeypatch.setattr(worker, "watch", lambda **kw: seen.setdefault("called", 0) or 0)
    assert cli.main(["worker", "--watch"]) == 0 and "called" in seen
```

- [ ] **Step 3: Run to verify they fail**

Run: `uv run pytest tests/test_worker_watch.py -q`
Expected: FAIL (`AttributeError: module 'lv.worker' has no attribute 'watch'`).

- [ ] **Step 4: Implement in `worker.py`**

Add imports `import signal`, `import time` and `from . import awake` (keep alphabetical with the existing `from . import …` line: `from . import awake, config, contract, keys, narrate, net, paths, site`). Add constants after `BASH_TIMEOUT_MS`:

```python
POLL = 30                      # seconds between checks while no lesson is waiting
BACKOFF = (30, 60, 120, 300)   # seconds after network or server errors, capped at the last
IDLE, RAN, STOP = "idle", "ran", "stop"
```

Change `_lock` to take a file name (default unchanged):

```python
def _lock(root: Path, name: str = ".worker.lock") -> Path | None:
    root.mkdir(parents=True, exist_ok=True)
    f = root / name
    ...  # body unchanged, but the stale branch recurses with `return _lock(root, name)`
```

Replace `run_once` with `_once` + a thin `run_once`:

```python
def _once(claude, out, start: bool = False) -> tuple[str, int]:
    root = lessons_root()
    lock = _lock(root)
    if lock is None:
        out("Another worker run is still going.")
        return IDLE, 0
    try:
        turn = site.call("/api/device/next" + ("?start=1" if start else ""))
        if not turn:
            return IDLE, 0
        if turn.get("stop") is True:
            return STOP, 0
        bad = contract.problems("turn", turn)
        if bad:
            tid = (turn.get("turn") or {}).get("id")
            if tid:
                _finish(tid, error_card("This job doesn't match what this plugin understands: " + "; ".join(bad[:3]), ""))
            return RAN, 1
        return RAN, _run_turn(turn, claude or run_claude, out)
    finally:
        lock.unlink(missing_ok=True)


def run_once(claude=None, out=print) -> int:
    return _once(claude, out)[1]


def _sigterm_as_interrupt():
    """Claude Code stops a background task with SIGTERM: turn it into KeyboardInterrupt so `finally` cleans up.
    Returns the previous handler (None if none was set), for `_restore_sigterm`."""
    def raise_interrupt(signum, frame):
        raise KeyboardInterrupt
    try:
        return signal.signal(signal.SIGTERM, raise_interrupt)
    except (ValueError, AttributeError, OSError):  # not the main thread, or no SIGTERM here
        return None


def _restore_sigterm(previous) -> None:
    if previous is not None:
        try:
            signal.signal(signal.SIGTERM, previous)
        except (ValueError, AttributeError, OSError):
            pass


def watch(claude=None, out=print, sleep=time.sleep, awake_on=awake.keep_awake, awake_off=awake.release) -> int:
    """`worker --watch`: run every step this computer is given, one after another, until the website says stop
    (Disconnect), the pairing is gone, or the process is stopped. Keeps the computer awake meanwhile."""
    root = lessons_root()
    guard = _lock(root, ".worker-watch.lock")
    if guard is None:
        out("This computer is already making videos for slide2video.com (another window is running it).")
        return 0
    handle = previous = None
    try:
        previous = _sigterm_as_interrupt()
        handle = awake_on(out=out)
        out(f"Making videos for {site.site_url()}. Waiting for lessons… (stop with Ctrl-C, or Disconnect on the website)")
        start, failures = True, 0
        while True:
            try:
                state, _ = _once(claude, out, start=start)
            except UserError as e:          # 401 (not connected) or 426 (update the plugin)
                out(str(e))
                return 1
            except net.ApiError as e:       # network down or the site busy: wait longer each time
                wait = BACKOFF[min(failures, len(BACKOFF) - 1)]
                failures += 1
                out(f"Can't reach the website ({e.status or 'no connection'}); trying again in {wait} s.")
                sleep(wait)
                continue
            start, failures = False, 0
            if state == STOP:
                out("Disconnected from the website. To start again, run /lesson-videos:serve.")
                return 0
            if state == IDLE:
                sleep(POLL)
    except KeyboardInterrupt:
        out("Stopped. This computer no longer makes videos for the website.")
        return 0
    finally:
        awake_off(handle)
        _restore_sigterm(previous)
        guard.unlink(missing_ok=True)
```

Note for the implementer: `net.ApiError` raised by `site.call` for 5xx and status 0 must reach this `except`; `site.call` re-raises any `ApiError` other than 401/426 (see `site.py` `call`). An `ApiError` with a 4xx other than 401/426 from `/next` (should not happen) also backs off — acceptable.

Also add `from .util import UserError` is already imported at the top of `worker.py` (`from .util import UserError, …`): reuse it.

- [ ] **Step 5: Wire the CLI** (`cli.py`)

Replace the two worker flags with a mutually exclusive group:

```python
    wk = sub.add_parser("worker", help="take this computer's next job from slide2video.com and run it")
    mode = wk.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="run at most one job, then exit (the default)")
    mode.add_argument("--watch", action="store_true",
                      help="keep running jobs as they come, keeping the computer awake, until stopped or disconnected")
    mode.add_argument("--status", action="store_true", help="show which account this computer is connected to")
```

In the dispatch, after the `--status` branch:

```python
        from . import worker
        if args.watch:
            return worker.watch()
        return worker.run_once()
```

- [ ] **Step 6: Run the new tests and the existing worker tests**

Run: `uv run pytest tests/test_worker_watch.py tests/test_worker.py tests/test_site.py -q` → all pass.
If `test_cli_worker_watch_is_wired` fails because `cli.main` needs `LV_SITE_MODE` unset or similar, read `cli.py` lines 120–135 (site-mode switch-offs) and set/unset env in the test with `monkeypatch`, not by changing the switch-offs.

- [ ] **Step 7: Commit**

```bash
git add lesson-videos/scripts/lv/worker.py lesson-videos/scripts/lv/cli.py tests/site_fake.py tests/test_worker_watch.py
git commit -m "lesson-videos: worker --watch runs every step as it comes, keeps the computer awake, stops on Disconnect"
```

### Task 3: `serve` skill, setup step 8, install guide, contract note, version 0.7.0

**Files:**
- Create: `lesson-videos/skills/serve/SKILL.md`
- Create: `lesson-videos/site-contract/README.md`
- Modify: `lesson-videos/skills/setup/SKILL.md` (step 8 "Connect this computer to slide2video.com")
- Modify: `lesson-videos/docs/install/slide2video.md` (lines ~41–60: the Terminal steps)
- Modify: `lesson-videos/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `lesson-videos/scripts/lv/__init__.py` (0.7.0)
- Test: `tests/test_skills.py`

**Interfaces:**
- Consumes: `LV worker --watch`, `LV worker --status`, `LV pair` (Task 2, existing).

- [ ] **Step 1: Write the failing tests** (`tests/test_skills.py`)

Change `SKILLS` to `["setup", "make", "serve", "elevenlabs-get-api-key", "google-get-api-key"]` (the existing frontmatter, real-commands and shell-syntax tests then cover `serve`). Replace `test_setup_hands_the_worker_command_to_the_teacher` with:

```python
def test_setup_points_to_serve_after_pairing():
    connect = _setup_section("Connect this computer to slide2video.com")
    assert "/lesson-videos:serve" in connect
    assert "worker --once" not in connect and "Terminal" not in connect


def test_serve_runs_the_watching_worker_in_the_background():
    fm, text = frontmatter("serve")
    assert "LV worker --watch" in text and "run_in_background" in text
    assert "LV worker --status" in text.split("LV worker --watch", 1)[0]  # checks the connection first
    low = text.lower()
    assert "keep this claude code window open" in low
    assert "disconnect" in low and "stop" in low
    assert "/root/.claude/plugins/synced/" in text


def test_serve_explains_autostart_is_intentionally_not_built():
    _, text = frontmatter("serve")
    section = text.split("## Start automatically", 1)[1]
    low = section.lower()
    assert "on purpose" in low or "intentionally" in low
    assert "launchagent" in low and "task scheduler" in low
    assert "never set it up unasked" in low or "only if the teacher asks" in low
```

Add `"serve"` to the loop in `tests/test_packaging.py::test_skills_use_skill_dir_not_plugin_root` (`for name in ("make", "setup", "serve")`) and `test_skills_say_where_to_find_the_scripts_when_skill_dir_is_empty`.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_skills.py tests/test_packaging.py -q` → FAIL (no `skills/serve/SKILL.md`).

- [ ] **Step 3: Write `lesson-videos/skills/serve/SKILL.md`**

````markdown
---
name: serve
description: Use when the teacher wants this computer to make the videos for lessons they upload to slide2video.com ("start making videos", "serve", "connect to the website and keep working"), or asks whether it's working, to stop it, or whether it can start by itself. Starts the lesson-videos worker in the background, keeps the computer awake while it runs, and stops when asked or when Disconnect is pressed on the website.
---

# lesson-videos: make videos for slide2video.com

You are helping a teacher who may never have used a terminal. Explain in one or two plain sentences, do the
technical work yourself.

In this skill, **LV** means this command (keep the quotes):

```
uv run "${CLAUDE_SKILL_DIR}/../../scripts/lesson-videos.py"
```

If that path doesn't exist (in some claude.ai sessions `${CLAUDE_SKILL_DIR}` comes through empty), the plugin is
under `/root/.claude/plugins/synced/`: use the `lesson-videos/scripts/lesson-videos.py` you find there.

## 1. Check the connection

Run `LV worker --status`. If it says "Connected to …", go on. If this computer isn't connected, offer to connect it
now (the same as step 8 of `/lesson-videos:setup`: run `LV pair` with the Bash tool's `run_in_background`, read the
code line from its output, give the teacher the address and code, then check `LV worker --status` again).

## 2. Start

Start `LV worker --watch` with the Bash tool's `run_in_background`. It runs until stopped, so never run it in the
foreground. Read the first lines of its output:
- "Making videos for …": it started.
- "already making videos": it is already running in another window; tell the teacher, nothing else to do.
- anything else: tell the teacher in plain words and do what the message says.

Then tell the teacher:
- This computer now makes the videos for lessons on slide2video.com, one step after another.
- **Keep this Claude Code window open.** The screen may turn off, but the computer won't go to sleep while this runs.
  On a laptop, keep the lid open (or a display plugged in): a closed lid still puts it to sleep.
- The website's **Devices** page shows this computer as Online.
- To stop: say "stop" here, or press **Disconnect** on the Devices page.

## 3. While it runs

- **"Is it working?"**: read the last lines of the background task's output and say in plain words what it's doing
  (waiting for lessons, working on a lesson, or the last thing it sent back).
- **"Stop"**: stop the background task and confirm it has ended. Starting again is running this skill again.
- If the background task ends by itself, read its last lines: "Disconnected from the website" means someone pressed
  Disconnect; a "connect" message means the pairing was removed (offer step 1); an "Update the lesson-videos
  plugin" message means running `/plugin update lesson-videos`, then this skill again.

## Start automatically

If the teacher asks whether this can start by itself when the computer starts: it is not built in, on purpose.
Starting on its own, the computer would make videos with nobody watching, it would stay awake from every start-up,
and it isn't yet known whether Claude Code started in the background by the system can use the Claude subscription
without asking to sign in. The supported way is to open Claude Code and run `/lesson-videos:serve`.

Only if the teacher asks for it anyway, you can set it up for this one computer: on a Mac a LaunchAgent in
`~/Library/LaunchAgents/` that runs the same `worker --watch` command with full paths (the `uv` path from
`which uv` and the full path of `lesson-videos.py`) at log-in; on Windows a Task Scheduler task at log-on. Test it
once, show the teacher where it is and how to remove it. Never set it up unasked.
````

- [ ] **Step 4: Update setup step 8** (`lesson-videos/skills/setup/SKILL.md`)

Keep the step's heading and its pairing paragraphs (status check, the question, `LV pair` in the background). Replace everything from "Don't run `worker --once` yourself" to the end of the step (the Terminal line, its code block and the "Tell them to open Terminal" paragraph) with:

```markdown
To make videos, the teacher (or you, now) runs `/lesson-videos:serve` in Claude Code: it keeps this computer
working on the website's lessons, one step after another, while that Claude Code window stays open. Offer to start
it now.
```

- [ ] **Step 5: Update the install guide** (`lesson-videos/docs/install/slide2video.md`)

Replace the Terminal instructions (the paragraph "Claude also gives you a line to paste into the **Terminal** app…", its code block, and step 2's "open Terminal … paste the line from step 2" text) with: "In Claude Code on your home computer, type `/lesson-videos:serve` and leave that window open. The computer then works on every lesson step by itself, and stays awake while it does (keep a laptop's lid open). To stop, say "stop" in Claude Code, or press **Disconnect** on the website's Devices page; to start again, run `/lesson-videos:serve` again." Read the whole file and keep its numbering and tone consistent.

- [ ] **Step 6: Write `lesson-videos/site-contract/README.md`**

```markdown
# Job contract notes

The JSON schemas in `schemas/` describe the files that travel between slide2video.com and the worker. Two device
API behaviours are not files and live here:

- `GET /api/device/next` answers a turn (`turn.json`), nothing (204), or `{"stop": true}` once after the teacher
  pressed **Disconnect** for this computer: the worker (`worker --watch`) then exits.
- `GET /api/device/next?start=1` is a watcher's first call: it clears a Disconnect left from while the computer was
  offline, then answers as usual.
```

- [ ] **Step 7: Bump to 0.7.0** in the three version files.

- [ ] **Step 8: Run the gate**

Run: `uv run pytest -q` → all pass (report counts).

- [ ] **Step 9: Commit**

```bash
git add lesson-videos/skills/serve lesson-videos/skills/setup/SKILL.md lesson-videos/docs/install/slide2video.md \
  lesson-videos/site-contract/README.md lesson-videos/.claude-plugin/plugin.json .claude-plugin/marketplace.json \
  lesson-videos/scripts/lv/__init__.py tests/test_skills.py tests/test_packaging.py
git commit -m "lesson-videos 0.7.0: /lesson-videos:serve keeps this computer making videos for slide2video.com"
```

---

## Part B — website (`/Users/daniellandi/Projects/slide2video`, branch `m2-disconnect` off `main`)

### Task 4: Stop mark and the device API

**Files:**
- Create: `migrations/0004_disconnect.sql`
- Modify: `src/device.ts` (`device.get("/next", …)` ~line 112)
- Create: `contract/README.md` (copy of `plugins/lesson-videos/site-contract/README.md` from Task 3 Step 6)
- Test: `test/disconnect.test.ts`

**Interfaces:**
- Produces: column `devices.stop_requested_at INTEGER` (null = no stop); `/next` behaviour per the contract README.

- [ ] **Step 1: Write the failing tests** (`test/disconnect.test.ts`)

```ts
import { describe, expect, it } from "vitest";
import { env } from "cloudflare:workers";
import { asDevice, newLesson, pairDevice, seedTeacher } from "./helpers";

const mark = (id: string, at: number | null) =>
  env.DB.prepare("UPDATE devices SET stop_requested_at = ? WHERE id = ?").bind(at, id).run();
const markOf = async (id: string) =>
  (await env.DB.prepare("SELECT stop_requested_at AS s FROM devices WHERE id = ?").bind(id).first<{ s: number | null }>())!.s;

describe("stop mark on /api/device/next", () => {
  it("answers {stop:true} once, clears the mark, and claims no turn", async () => {
    const t = await seedTeacher();
    const d = await pairDevice(t.email);
    await newLesson(t.email, { start: true });
    await mark(d.id, 1);
    const r = await asDevice(d.token, "/api/device/next");
    expect(r.status).toBe(200);
    expect(await r.json()).toEqual({ stop: true });
    expect(await markOf(d.id)).toBeNull();
    const next = await asDevice(d.token, "/api/device/next"); // the queued start turn is still there
    expect(next.status).toBe(200);
    expect((await next.json<any>()).turn.kind).toBe("start");
  });

  it("?start=1 clears a stale mark and answers as usual", async () => {
    const t = await seedTeacher();
    const d = await pairDevice(t.email);
    await mark(d.id, 1);
    const r = await asDevice(d.token, "/api/device/next?start=1");
    expect(r.status).toBe(204);
    expect(await markOf(d.id)).toBeNull();
  });

  it("a device without a mark is unaffected", async () => {
    const t = await seedTeacher();
    const d = await pairDevice(t.email);
    expect((await asDevice(d.token, "/api/device/next")).status).toBe(204);
  });

  it("one device's mark never stops another", async () => {
    const t = await seedTeacher();
    const a = await pairDevice(t.email, "A");
    const b = await pairDevice(t.email, "B");
    await mark(a.id, 1);
    expect((await asDevice(b.token, "/api/device/next")).status).toBe(204);
    expect(await markOf(a.id)).toBe(1);
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `npx vitest run test/disconnect.test.ts`
Expected: FAIL (`no such column: stop_requested_at`).

- [ ] **Step 3: Migration** (`migrations/0004_disconnect.sql`)

```sql
-- Disconnect on the Devices page: the computer's next /api/device/next answers {"stop": true} once and clears it
ALTER TABLE devices ADD COLUMN stop_requested_at INTEGER;
```

- [ ] **Step 4: `/next`** (`src/device.ts`)

```ts
device.get("/next", async (c) => {
  const d = c.get("device");
  const db = c.env.DB;
  if (c.req.query("start") === "1") {
    // a watcher starting: a Disconnect pressed while this computer was off no longer applies
    await db.prepare("UPDATE devices SET stop_requested_at = NULL WHERE id = ?").bind(d.id).run();
  } else {
    const stop = await db.prepare(
      "UPDATE devices SET stop_requested_at = NULL WHERE id = ? AND stop_requested_at IS NOT NULL RETURNING id",
    ).bind(d.id).first();
    if (stop) return c.json({ stop: true });
  }
  const turn = await claimNext(db, d);
  return turn ? c.json(await turnJson(db, turn)) : c.body(null, 204);
});
```

(Check D1 supports `RETURNING` in the test pool; if not, read the mark with a SELECT then UPDATE with `AND stop_requested_at IS NOT NULL` and use `meta.changes`.)

- [ ] **Step 5: Copy the contract note** to `contract/README.md` (same text as Task 3 Step 6).

- [ ] **Step 6: Run** `npx vitest run test/disconnect.test.ts` → 4 passed; then `npm run check && npm test` → all pass.

- [ ] **Step 7: Commit**

```bash
git add migrations/0004_disconnect.sql src/device.ts contract/README.md test/disconnect.test.ts
git commit -m "slide2video: a device's stop mark is delivered once on /next; ?start=1 clears a stale one"
```

### Task 5: Disconnect button, Online/Offline, serve wording

**Files:**
- Modify: `src/teacher-api.ts` (after `teacherApi.delete("/devices/:id", …)` ~line 50)
- Modify: `src/pages.ts` (`pages.get("/devices", …)` ~line 463; lesson waiting panel ~line 435; the Add a device steps ~lines 494–503)
- Test: `test/disconnect.test.ts` (append), `test/pages.test.ts` (adjust copy expectations)

**Interfaces:**
- Consumes: `devices.stop_requested_at` (Task 4).
- Produces: `POST /api/devices/:id/disconnect` → 200 `{name}` | 404; event kind `device_disconnected`.

- [ ] **Step 1: Write the failing tests** (append to `test/disconnect.test.ts`; add `asTeacher` to its imports)

```ts
const post = (email: string, path: string) => asTeacher(email, path, { method: "POST", body: "{}" });
const page = async (email: string) => (await asTeacher(email, "/devices")).text();
const seen = (id: string, secondsAgo: number) =>
  env.DB.prepare("UPDATE devices SET last_seen = ? WHERE id = ?").bind(Math.floor(Date.now() / 1000) - secondsAgo, id).run();

describe("Disconnect", () => {
  it("sets the mark for the teacher's own computer", async () => {
    const t = await seedTeacher();
    const d = await pairDevice(t.email, "Home iMac");
    const r = await post(t.email, `/api/devices/${d.id}/disconnect`);
    expect(r.status).toBe(200);
    expect(await r.json()).toEqual({ name: "Home iMac" });
    expect(await markOf(d.id)).not.toBeNull();
    const ev = await env.DB.prepare("SELECT COUNT(*) AS n FROM events WHERE kind = 'device_disconnected' AND detail = ?").bind(d.id).first<{ n: number }>();
    expect(ev!.n).toBe(1);
  });

  it("refuses another teacher's computer and a removed one", async () => {
    const t = await seedTeacher();
    const other = await seedTeacher();
    const d = await pairDevice(t.email);
    expect((await post(other.email, `/api/devices/${d.id}/disconnect`)).status).toBe(404);
    expect(await markOf(d.id)).toBeNull();
    await asTeacher(t.email, `/api/devices/${d.id}`, { method: "DELETE" });
    expect((await post(t.email, `/api/devices/${d.id}/disconnect`)).status).toBe(404);
  });

  it("Devices shows Online with Disconnect, Stopping…, and Offline without it", async () => {
    const t = await seedTeacher();
    const d = await pairDevice(t.email, "Home iMac");
    await seen(d.id, 30);
    let p = await page(t.email);
    expect(p).toContain("Online");
    expect(p).toContain(`data-api="POST /api/devices/${d.id}/disconnect"`);
    expect(p).toContain("To connect it again, someone has to open Claude Code on that computer and run /lesson-videos:serve.");
    await post(t.email, `/api/devices/${d.id}/disconnect`);
    p = await page(t.email);
    expect(p).toContain("Stopping…");
    expect(p).not.toContain(`/api/devices/${d.id}/disconnect`);
    await seen(d.id, 600);
    p = await page(t.email);
    expect(p).toContain("Offline · last seen");
    expect(p).not.toContain("Stopping…");
    expect(p).not.toContain(`/api/devices/${d.id}/disconnect`);
  });

  it("warns that the step in progress finishes first", async () => {
    const t = await seedTeacher();
    const d = await pairDevice(t.email, "Home iMac");
    await newLesson(t.email, { start: true });
    expect((await asDevice(d.token, "/api/device/next")).status).toBe(200); // now running a step
    expect(await page(t.email)).toContain("It finishes the step it's on first.");
  });
});

describe("serve wording", () => {
  it("the waiting lesson and Add a device say to run /lesson-videos:serve, not Terminal", async () => {
    const t = await seedTeacher();
    await pairDevice(t.email);
    const p = await page(t.email);
    expect(p).toContain("/lesson-videos:serve");
    expect(p).not.toContain("Terminal");
  });
});
```

In `test/pages.test.ts`, find assertions on the old waiting-panel sentence ("run the line from setup in Terminal") and update them to "On that computer, open Claude Code and run /lesson-videos:serve." (`grep -n "Terminal" test/*.ts`).

- [ ] **Step 2: Run to verify they fail**

Run: `npx vitest run test/disconnect.test.ts` → the new tests FAIL (404 on the route, missing text).

- [ ] **Step 3: The route** (`src/teacher-api.ts`, after the DELETE route)

```ts
teacherApi.post("/devices/:id/disconnect", async (c) => {
  const t = c.get("teacher");
  const d = await c.env.DB.prepare(
    "UPDATE devices SET stop_requested_at = ? WHERE id = ? AND teacher_id = ? AND revoked_at IS NULL RETURNING name",
  ).bind(now(), c.req.param("id"), t.id).first<{ name: string }>();
  if (!d) return c.json({ error: "not found" }, 404);
  await logEvent(c.env.DB, t.id, "device_disconnected", c.req.param("id"));
  return c.json({ name: d.name });
});
```

- [ ] **Step 4: The Devices rows** (`src/pages.ts`, `/devices` handler)

Select `stop_requested_at` too, and which devices are running a step:

```ts
  const { results } = await db.prepare(
    "SELECT id, name, last_seen, stop_requested_at FROM devices WHERE teacher_id = ? AND revoked_at IS NULL ORDER BY created_at",
  ).bind(t.id).all<{ id: string; name: string; last_seen: number | null; stop_requested_at: number | null }>();
  const { results: runningRows } = await db.prepare(
    "SELECT DISTINCT tr.device_id AS id FROM turns tr JOIN lessons l ON l.id = tr.lesson_id WHERE l.teacher_id = ? AND tr.state = 'running'",
  ).bind(t.id).all<{ id: string }>();
  const running = new Set(runningRows.map((r) => r.id));
  const ONLINE = 120; // seconds: the watcher checks every 30 s, and heartbeats every 60 s while working
```

Inside the row map, replace the meta and form with:

```ts
    const online = d.last_seen !== null && now() - d.last_seen < ONLINE;
    const stopping = online && d.stop_requested_at !== null;
    const state = !d.last_seen ? "Not seen yet" : stopping ? "Stopping…" : online ? "Online" : `Offline · last seen ${ago(d.last_seen)}`;
    const warn = `Disconnect ${d.name}? It stops making videos.${running.has(d.id) ? " It finishes the step it's on first." : ""} ` +
      "To connect it again, someone has to open Claude Code on that computer and run /lesson-videos:serve.";
    return html`<div class="item">${COMPUTER_ART}<span class="name">${d.name}<span class="meta">${state}${n ? ` · making ${plural(n, "lesson")}` : ""}</span></span>
${online && !stopping ? html`<form class="inline" data-api="POST /api/devices/${d.id}/disconnect" data-kind="none" data-confirm="${warn}"><button>Disconnect</button></form>` : ""}
<form class="inline" data-api="DELETE /api/devices/${d.id}" data-kind="none" data-confirm="Remove ${d.name}? Its lessons can't continue on another device."><button class="danger">Remove</button></form></div>`;
```

Check how `data-confirm` text is shown in `src/client.ts` (it must be the escaped attribute; `html` escapes `${warn}`) and that a `POST` with `data-kind="none"` sends no body that `readObject` would reject (the route reads no body). Refresh the page every 15 s while any device is `stopping` (`refresh: pending.length ? 5 : anyStopping ? 15 : 0`).

- [ ] **Step 5: The wording**

- Lesson waiting panel (`~line 435`): `On that computer, run the line from setup in Terminal.` → `On that computer, open Claude Code and run /lesson-videos:serve.`
- Add a device step 3 (`~line 494`): keep, and add a step 4 before the code box is fine; simplest: change the notice under the steps (`~line 502`) to: `After connecting, type <code>/lesson-videos:serve</code> in Claude Code on that computer and leave the window open: it makes the videos for every lesson you upload. <a href="${GUIDE}" …>Full guide with troubleshooting</a>`.
- `grep -n "Terminal" src/*.ts` must then find nothing in pages (legal pages are untouched).

- [ ] **Step 6: Run** `npx vitest run test/disconnect.test.ts` then `npm run check && npm test` → all pass.

- [ ] **Step 7: Commit**

```bash
git add src/teacher-api.ts src/pages.ts test/disconnect.test.ts test/pages.test.ts
git commit -m "slide2video: Disconnect a computer from Devices; Online/Stopping/Offline; serve instead of Terminal"
```

---

## Part C — ship and check (with Daniel)

### Task 6: Merge, migrate, deploy, end-to-end

- [ ] **Step 1:** Both gates green on their branches; whole-branch review of both diffs.
- [ ] **Step 2 (ask Daniel first):** plugins: merge `m2-serve` → `main`, push. slide2video: merge `m2-disconnect` → `main`, push, then `npx wrangler d1 migrations apply slide2video --remote` (applies `0004_disconnect.sql`; check it lists only 0004 as new before confirming), then `npm run deploy`.
- [ ] **Step 3: End to end on Daniel's Mac:** `/plugin update lesson-videos` (0.7.0), stop the old Terminal loop, run `/lesson-videos:serve`; `pgrep -fl caffeinate` shows `caffeinate -i -w <pid>`; Devices shows Online; upload `examples/water-cycle.pptx`, answer and approve on the website without touching the Mac; press Disconnect; the background task ends with "Disconnected from the website" and `pgrep caffeinate` shows nothing.
- [ ] **Step 4:** Update plugins#6 (narrowed scope, link the spec), close it on merge; note in plugins#8 that the original spec's §6.2 is replaced by this spec.
