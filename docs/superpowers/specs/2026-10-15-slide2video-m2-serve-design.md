# slide2video M2: the Mac keeps working while Claude Code is open

**Date:** 2026-10-15 · **Status:** design approved in chat; written spec awaiting review
**Repos:** `plugins` (`lesson-videos`: `worker --watch`, keep-awake, the `serve` skill, setup and docs) +
`slide2video` (Disconnect, Online/Offline, waiting copy) · **Replaces** the LaunchAgent design in
`2026-10-13-lesson-videos-site-design.md` §6.2 and §11 "M2" · **Issue:** plugins#6

## 1. Purpose

After M1 the teacher pastes `worker --once` into Terminal for every step; a lesson takes four or more steps and
each can take an hour. M2 makes the Mac pick up steps by itself, so a lesson uploaded at school moves forward at
home without anyone at the Mac.

**Decisions taken in the brainstorm (2026-10-15):**

| Topic | Decision |
|---|---|
| How it starts | The teacher opens Claude Code and runs **`/lesson-videos:serve`**. No LaunchAgent, nothing starts with the OS. It runs while that Claude Code window is open. |
| Sleep | The worker keeps the computer awake for **as long as it runs**, waiting included (several videos may be queued, and a sleeping Mac can't see new uploads). |
| Stopping | From Claude Code (stop the background task, or Ctrl-C) or from the website's new **Disconnect** button. |
| Disconnect mid-step | The step in progress **finishes**, then the worker stops. No cancel path. |
| Disconnect vs Remove | Disconnect only stops the worker; the pairing and the lessons homed on that computer stay. Remove (revoke) is unchanged. |
| Autostart | Intentionally not built. If a teacher asks, Claude explains why and can set it up for that one computer on request. |
| Windows | Best effort in code (no bash-only syntax, a Windows keep-awake); untested until a Windows trial. |

**Success:** with `/lesson-videos:serve` running on the Mac, a teacher uploads at school, answers and approves on
the website, and every step runs without anyone touching the Mac. Disconnect on the website stops the worker and
its keep-awake within one poll after the current step.

## 2. Mac side (`plugins/lesson-videos`)

### 2.1 `LV worker --watch` (`scripts/lv/worker.py`, `cli.py`)

- New flag `--watch` (mutually exclusive with `--once`/`--status`; `--once` stays the default and stays for
  testing).
- **Single watcher:** takes `<lessons root>/.worker-watch.lock` with the same pid-file logic as `_lock()`. If held
  by a live process: print "This computer is already making videos (started <when>)." and exit 0.
- **Keep-awake** (`scripts/lv/awake.py`, one function `keep_awake() -> handle | None` and `release(handle)`):
  - macOS: `subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])`. `-i` blocks idle sleep, the display
    may sleep; `-w` makes caffeinate exit by itself when the worker exits, even if it is killed. Also terminated in
    a `finally`.
  - Windows: `ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)` from the main
    thread (the setting belongs to the calling thread, which runs the whole loop) on start and
    `ES_CONTINUOUS` on release (the setting dies with the process anyway).
  - Anything else, or if the call fails: print one line ("This computer may sleep while waiting; keep it awake
    yourself.") and continue.
- **Loop:**
  1. `run_once()` (the first call of a watcher asks `/next?start=1`, §3.2); if it ran a turn, loop immediately
     (more may be queued).
  2. If there was no turn: sleep `POLL` = 30 s, then loop.
  3. **Stop signal:** if the website answered "stop" (§3.2), print "Disconnected from the website. To start again,
     run /lesson-videos:serve." and exit 0.
  4. **Errors:** network errors and 5xx → print one short line, back off 30 s → 60 s → 120 s → 300 s (cap), reset
     on success. 401 (revoked / not paired) → print the existing NOT_PAIRED message and exit 1. 426 → print the
     update message and exit 1. Ctrl-C / SIGTERM → exit 0 cleanly (the per-turn lock and keep-awake are released
     in `finally`).
- Output lines (each flushed — line buffering is on since 0.6.1): start line ("Making videos for slide2video.com
  as <email> on <device>. Waiting for lessons…"), one line per turn start and finish (the existing
  `_run_turn` lines), the stop/error lines. No line per idle poll.
- `run_once()` returns a richer result internally (ran a turn / idle / stop) so the loop can tell them apart; the
  CLI exit codes of `--once` are unchanged.

### 2.2 The `serve` skill (`skills/serve/SKILL.md`, new)

Description: use when the teacher wants this computer to make videos for slide2video.com, or asks to start,
check or stop it.

1. `LV worker --status`. Not paired → offer to pair (same steps as setup step 8), then continue.
2. Start `LV worker --watch` with the Bash tool's `run_in_background` (no timeout). Read the first line of its
   output to confirm it started (or relay the "already making videos" / error line).
3. Tell the teacher in plain words: this computer now makes the videos for lessons on slide2video.com; keep this
   Claude Code window open; the screen may turn off but the computer won't sleep; on a laptop keep the lid open
   or plugged into a display; the website's Devices page shows it as Online; to stop, say "stop" here or press
   Disconnect on the website.
4. **Status** ("is it working?"): read the last lines of the background task's output and summarise.
5. **Stop** ("stop"): stop the background task; confirm it exited.
6. **Autostart** ("can it start by itself when the computer starts?"): explain that this is intentionally not
   built: the computer would make videos with nobody watching, it would hold the computer awake from every
   start-up, and it is not yet known whether Claude Code started in the background by the system can use the
   Claude subscription without a sign-in prompt. If the teacher still wants it, Claude may set it up for this one
   computer on request (macOS: a LaunchAgent in `~/Library/LaunchAgents/` running the same `worker --watch` command
   with full paths; Windows: a Task Scheduler task at log-on), test it once, and tell the teacher how to remove it.
   Never set it up unasked.
- Commands only through `LV` (the quoted `uv run …/lesson-videos.py` line), no bash-only syntax, as in every
  lesson-videos skill.

### 2.3 Setup, docs and version

- `skills/setup/SKILL.md` step 8: after pairing, say "to make videos, run `/lesson-videos:serve` in Claude Code"
  instead of handing over the Terminal `worker --once` line; drop the "don't run worker --once yourself" paragraph
  (serve runs it in the background correctly).
- `docs/install/slide2video.md`: the Terminal steps become "open Claude Code and run /lesson-videos:serve".
- Version 0.7.0 (new skill, new mode) in the three places `tests/test_packaging.py` checks.

## 3. Website (`slide2video`)

### 3.1 Data

Migration `0004_disconnect.sql`: `ALTER TABLE devices ADD COLUMN stop_requested_at INTEGER;`

### 3.2 Device API (contract stays version 1; no compatibility needed with plugin versions before 0.7.0, which nobody runs)

- `GET /api/device/next`: after the existing `last_seen` update, if the device has `stop_requested_at` set,
  clear it and answer **200 with `{"stop": true}`** instead of claiming a turn. The worker checks for `stop` before
  validating a turn, so the existing HTTP helper (which returns only the JSON body) needs no change.
- **A fresh start clears an old mark:** a watcher's first call is `GET /api/device/next?start=1`, which clears any
  `stop_requested_at` left from a Disconnect pressed while the computer was offline, and then works as a normal
  `/next`. Without this, starting `/lesson-videos:serve` after such a Disconnect would stop at once.
- The heartbeat is unchanged (the running step finishes; §1).
- Document `{"stop": true}` and `?start=1` in `plugins/lesson-videos/site-contract/README.md` (new) and the pinned copy.

### 3.3 Teacher API and Devices page

- `POST /api/devices/:id/disconnect`: scoped to the teacher, not for revoked devices; sets
  `stop_requested_at = now`; logs a `device_disconnected` event; returns `{name}`. Cross-teacher test.
- Devices row state, from `last_seen` and `stop_requested_at`:
  - **Online** when last seen under 2 minutes ago (the watcher polls every 30 s) → shows **Disconnect**.
  - **Stopping…** when `stop_requested_at` is set and the computer is still Online (the mark is cleared once the
    computer picks it up); a computer that went offline with the mark still set shows Offline.
  - **Offline · last seen …** otherwise → no Disconnect button.
  - The existing "making N lessons" and Remove stay.
- Disconnect asks for confirmation with the existing `data-confirm` mechanism: "Disconnect <name>? It stops making
  videos. To connect it again, someone has to open Claude Code on that computer and run /lesson-videos:serve." If a
  step is running: "It finishes the step it's on first."
- Lesson page waiting panel ("Waiting for your computer"): "On that computer, open Claude Code and run
  /lesson-videos:serve." replaces "run the line from setup in Terminal"; the guide link stays.
- Devices "Add a device" steps: mention `/lesson-videos:serve` as the last step.

## 4. Testing

- **Plugin (pytest, fake site):** watch loop runs queued turns back to back, idles with the poll interval (time
  and sleep injected), stops on `{"stop": true}`, exits 1 on 401 and 426, backs off on network errors; second watcher
  refused; keep-awake called with the right command on macOS and the Windows call faked; release on exit. Skill
  tests: serve skill exists, runs `worker --watch` in the background, covers stop, status and the autostart
  answer; setup step 8 points to serve. Packaging 0.7.0.
- **Site (Vitest):** migration; `/next` returns `{"stop": true}` once and clears the mark; `/next?start=1`
  clears a stale mark and answers normally; a device without the mark is unaffected; disconnect route scoping (other teacher, revoked device → 404); Devices page shows Online /
  Stopping / Offline and the button only when Online; waiting-panel copy.
- **End to end (Daniel's Mac):** run `/lesson-videos:serve`, confirm `caffeinate` is running
  (`pgrep caffeinate`), upload the sample deck, answer and approve on the website without touching the Mac, then
  Disconnect and confirm both the worker and `caffeinate` have exited.

## 5. Out of scope

Autostart built in by default; cancelling a running step from the website; sleep prevention with the lid closed;
Linux keep-awake; a Windows trial (the code is written to work, testing comes later).
