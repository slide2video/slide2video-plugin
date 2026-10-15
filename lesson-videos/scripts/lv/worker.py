"""`worker --once`: take this computer's next turn from slide2video.com, run Claude Code on it in the lesson's folder,
and send back the card Claude wrote (or an error card)."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path

from . import awake, config, contract, keys, narrate, net, paths, site
from .util import UserError, read_json, read_text, safe_name, write_json, write_text

PROMPT = "Run /lesson-videos:make in site mode for this folder."
HEARTBEAT = 60                 # seconds between lease renewals
CLAUDE_TIMEOUT = 3 * 3600      # one turn never runs longer than this
CONTENT_TYPES = {".mp4": "video/mp4", ".vtt": "text/vtt", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".png": "image/png", ".json": "application/json"}
LIMIT = re.compile(r"(?:5-hour|weekly|usage|session) limit (?:reached|hit)|Claude usage limit", re.I)
LIMIT_SUFFIX = {".mp4": "video", ".vtt": "captions", ".jpg": "stills", ".jpeg": "stills", ".png": "stills"}
RESET = re.compile(r"resets?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap]m)", re.I)
# Claude Code reads these from the folder it runs in; a turn could plant them for the next turn. Never part of a lesson.
CLAUDE_CONFIG = (".claude", ".mcp.json", "CLAUDE.md", "CLAUDE.local.md")
DENIED = ["WebFetch", "WebSearch", "Edit(./.claude/**)", "Write(./.claude/**)", "Edit(./.mcp.json)",
          "Write(./.mcp.json)", "Edit(./CLAUDE.md)", "Write(./CLAUDE.md)", "Edit(./CLAUDE.local.md)",
          "Write(./CLAUDE.local.md)"]
# Never an API key or another provider (CLAUDE_CODE_USE_BEDROCK/VERTEX/FOUNDRY go with every other CLAUDE_CODE_*).
DROPPED_ENV = ("LESSON_VIDEOS_PROJECT", "CLAUDECODE", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")
BASH_TIMEOUT_MS = "3600000"    # render and narrate can take far longer than Claude Code's 10-minute Bash limit
POLL = 30                      # seconds between checks while no lesson is waiting
BACKOFF = (30, 60, 120, 300)   # seconds after network or server errors, capped at the last
IDLE, RAN, STOP, BUSY = "idle", "ran", "stop", "busy"


def lessons_root() -> Path:
    return Path(os.environ.get("LV_LESSONS_DIR") or Path.home() / "Lesson Videos")


def lesson_dir(lesson: dict) -> Path:
    """The lesson's folder, found by its id (the title on the site may have changed since)."""
    root, tag = lessons_root(), f"({lesson['id']})"
    if root.exists():
        for d in root.iterdir():
            if d.is_dir() and d.name.endswith(tag):
                return d
    return root / f"{safe_name(lesson['title'])[:80]} {tag}"


def lv_command() -> str:
    return f'"{shutil.which("uv") or "uv"}" run "{config.ENTRY}"'


def claude_command(lv: str) -> list[str]:
    """Claude Code pinned to this job: no user, project or local settings (so no hooks, extra allow rules or
    permission mode of the teacher's own), no MCP servers, this plugin loaded explicitly, and anything not allowed
    below is refused without asking (nobody is there to answer)."""
    claude = shutil.which("claude")
    if not claude:
        raise UserError("Claude Code isn't installed on this computer (no `claude` command). Install it from "
                        "https://claude.com/claude-code, sign in once, then try again.")
    plugin = str(config.PLUGIN_ROOT).replace("\\", "/").lstrip("/")
    return [claude, "-p", PROMPT, "--permission-mode", "dontAsk", "--setting-sources", "", "--strict-mcp-config",
            "--plugin-dir", str(config.PLUGIN_ROOT),
            "--allowedTools", f"Bash({lv}:*)", "Read(./**)", f"Read(//{plugin}/**)", "Edit(./**)", "Write(./**)",
            "--disallowedTools", *DENIED]


def _site_env(private: Path) -> dict:
    """Claude's environment: site mode on, and no registered project folder to redirect output into. The settings
    file is never created and sits in a private folder outside the lesson, where Claude's file tools can't plant one.
    Variables a parent Claude Code session set are dropped (the job is its own session), and so is every way to use an
    API key or another provider: the job always runs on the teacher's Claude subscription. The subscription sign-in
    token a teacher may keep in CLAUDE_CODE_OAUTH_TOKEN is kept."""
    env = {k: v for k, v in os.environ.items() if k not in DROPPED_ENV
           and (not k.startswith("CLAUDE_CODE_") or k == "CLAUDE_CODE_OAUTH_TOKEN")}
    env["LV_SITE_MODE"] = "1"
    env["LESSON_VIDEOS_SETTINGS"] = str(private / "no-settings.json")
    env["BASH_DEFAULT_TIMEOUT_MS"] = env["BASH_MAX_TIMEOUT_MS"] = BASH_TIMEOUT_MS
    return env


def _clear_claude_config(folder: Path) -> None:
    for name in CLAUDE_CONFIG:
        p = folder / name
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)
        elif p.exists() or p.is_symlink():
            p.unlink()


def run_claude(cmd: list[str], cwd: Path, log: Path) -> int:
    _clear_claude_config(cwd)
    private = Path(tempfile.mkdtemp(prefix="lv-site-"))
    try:
        with open(log, "w", encoding="utf-8") as f:
            return subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                  env=_site_env(private), timeout=CLAUDE_TIMEOUT).returncode
    finally:
        shutil.rmtree(private, ignore_errors=True)


def _reset_time(log: str, now: dt.datetime) -> dt.datetime:
    m = RESET.search(log)
    if not m:
        return now + dt.timedelta(hours=1)
    hour = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "pm" else 0)
    t = now.replace(hour=hour, minute=int(m.group(2) or 0), second=0, microsecond=0)
    return t if t > now else t + dt.timedelta(days=1)


def error_card(message: str, log: str, now=None, detect_limit: bool = False) -> dict:
    message = keys.redact(message)[:2000]
    card = {"contract": contract.VERSION, "kind": "error", "message": message,
            "log_tail": keys.redact("\n".join(log.splitlines()[-40:]))[:20000], "retry_after": None}
    if detect_limit and LIMIT.search(log):
        card["message"] = ("Your Claude plan's usage limit was reached; this continues automatically when it resets. "
                           + message)[:2000]
        card["retry_after"] = _reset_time(log, now or dt.datetime.now().astimezone()).isoformat()
    return card


def timing_for(ch_dir: Path) -> dict | None:
    """Scene marks for the player: id, start, length, a label and the first words of the narration."""
    try:
        T = narrate.read_timing(ch_dir)
        say = {s["id"]: s.get("say", "") for s in read_json(paths.chapter(ch_dir).code / "script.json")["scenes"]}
    except (OSError, ValueError, KeyError, UserError):
        return None
    return {"duration": T["duration"], "scenes": [
        {"id": s["id"], "start": s["start"], "dur": s["dur"], "label": s["id"].replace("_", " ").replace("-", " ").title(),
         "first_words": " ".join(say.get(s["id"], "").split()[:8])} for s in T["scenes"]]}


def _lock(root: Path, name: str = ".worker.lock") -> Path | None:
    root.mkdir(parents=True, exist_ok=True)
    f = root / name
    try:
        fd = os.open(f, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            os.kill(int(read_text(f).strip()), 0)
            return None                      # another run is alive
        except PermissionError:
            return None                      # alive, owned by someone else
        except (ValueError, ProcessLookupError, OSError):
            f.unlink(missing_ok=True)        # stale
            return _lock(root, name)
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    return f


def _last_line(f: Path) -> str:
    try:
        lines = [l for l in read_text(f).splitlines() if l.strip()]
    except OSError:
        return ""
    return lines[-1][:200] if lines else ""


_COUNT = re.compile(r"^(.*?)\s*\[(\d+)/(\d+)\]\s*$")


def _progress(f: Path) -> tuple[str, float | None]:
    """The last progress line for the website, and its share done when it ends with ` [done/total]`."""
    line = _last_line(f)
    m = _COUNT.match(line)
    if m and int(m.group(3)) > 0 and int(m.group(2)) <= int(m.group(3)) and m.group(1).strip():
        return m.group(1).strip(), int(m.group(2)) / int(m.group(3))
    return line, None


class _Heartbeat(threading.Thread):
    def __init__(self, turn_id: str, progress: Path):
        super().__init__(daemon=True)
        self.turn_id, self.progress, self.done = turn_id, progress, threading.Event()

    def run(self):
        while not self.done.wait(HEARTBEAT):
            try:
                text, fraction = _progress(self.progress)
                body = {"progress": text} if fraction is None else {"progress": text, "fraction": fraction}
                site.call(f"/api/device/turns/{self.turn_id}/heartbeat", body)
            except Exception:  # noqa: BLE001  a missed heartbeat only shortens the lease
                pass


def _sha256(f: Path) -> str:
    h = hashlib.sha256()
    with open(f, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _fetch_inputs(turn: dict, folder: Path) -> None:
    for f in turn["files"]:
        dest = folder / f["path"]
        if dest.is_file() and _sha256(dest) == f["sha256"]:
            continue
        data = site.call(f"/api/device/files/{f['id']}", raw=True, timeout=600)
        if hashlib.sha256(data).hexdigest() != f["sha256"]:
            raise UserError(f"{f['name']} arrived damaged; try again.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def _upload(turn_id: str, path: str, data: bytes, content_type: str) -> None:
    site.call(f"/api/device/turns/{turn_id}/files?path={urllib.parse.quote(path)}", data=data, method="PUT",
              headers={"Content-Type": content_type}, timeout=900)


def _next_version(folder: Path, chapter: int) -> int:
    f = folder / "site" / "versions.json"
    d = read_json(f) if f.exists() else {}
    d[str(chapter)] = d.get(str(chapter), 0) + 1
    write_json(f, d)
    return d[str(chapter)]


def _inside(folder: Path, rel: str, field: str) -> Path:
    p = (folder / rel).resolve()
    if (folder / "lesson-videos").resolve() not in p.parents or not p.is_file() or LIMIT_SUFFIX.get(p.suffix.lower()) != field:
        raise UserError(f"The card names {rel!r}, which isn't a {field} file in this lesson's lesson-videos folder.")
    return p


def _publish(card: dict, folder: Path, turn_id: str) -> dict:
    """Upload what a review card names and point the card at the uploaded copies (out/chN/vK/…)."""
    if card["kind"] != "review":
        return card
    local = {k: _inside(folder, card[k], k) for k in ("video", "captions", "stills") if card.get(k)}
    ch = card["chapter"]
    card = {k: v for k, v in card.items() if k not in ("timing", "version")}  # only the worker sets these
    card["version"] = _next_version(folder, ch)
    base = f"out/ch{ch}/v{card['version']}"
    for k, f in local.items():
        _upload(turn_id, f"{base}/{f.name}", f.read_bytes(), CONTENT_TYPES.get(f.suffix.lower(), "application/octet-stream"))
        card[k] = f"{base}/{f.name}"
    timing = timing_for(folder / "lesson-videos" / "_work" / f"ch{ch}")
    if timing:
        _upload(turn_id, f"{base}/timing.json", json.dumps(timing).encode("utf-8"), "application/json")
        card["timing"] = f"{base}/timing.json"
    return card


def _with_slides(card: dict, folder: Path) -> dict:
    """Add the deck's slide count (written by ingest) to a card that has none, for the website's lesson header."""
    f = folder / "lesson-videos" / "_work" / "deck" / "deck.json"
    if "slides" in card or not f.is_file():
        return card
    try:
        n = read_json(f).get("slides")
    except (OSError, ValueError, AttributeError):
        return card
    return {**card, "slides": n} if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= 500 else card


def _redacted(v):
    if isinstance(v, str):
        return keys.redact(v)
    if isinstance(v, list):
        return [_redacted(x) for x in v]
    if isinstance(v, dict):
        return {k: _redacted(x) for k, x in v.items()}
    return v


def _finish(turn_id: str, card: dict, log: str = "") -> dict:
    """Send the card; if the website refuses it (a 4xx other than 401/426), send an error card saying why, once.
    Returns the card the website accepted."""
    try:
        site.call(f"/api/device/turns/{turn_id}/finish", _redacted(card))
        return card
    except net.ApiError as e:
        if not 400 <= e.status < 500 or e.status in (401, 426):
            raise
        reason = keys.redact(site._error_message(e.detail) or f"HTTP {e.status}")[:200]
    card = error_card(f"The website refused this result: {reason}", log)
    site.call(f"/api/device/turns/{turn_id}/finish", _redacted(card))
    return card


def _log_text(log: Path | None) -> str:
    return read_text(log) if log is not None and log.exists() else ""


def _claude_turn(turn: dict, folder: Path, sitedir: Path, log: Path, claude) -> dict:
    tid = turn["turn"]["id"]
    _fetch_inputs(turn, folder)
    write_json(sitedir / "turn.json", turn)
    lv = lv_command()
    write_text(sitedir / "lv.txt", lv + "\n")
    card_file = sitedir / "card.json"
    code = claude(claude_command(lv), folder, log)
    if code != 0 or not card_file.exists():
        return error_card("Claude stopped before it finished this step.", _log_text(log), detect_limit=True)
    card = read_json(card_file)
    bad = contract.problems("card", card)
    if bad:
        where = sorted({m.split(":")[0].strip() for m in bad})[:6]
        return error_card("Claude's reply couldn't be read (problems at: " + ", ".join(where) + ")", _log_text(log))
    if card["kind"] == "error":  # Claude's own words, but the worker's log and no retry time Claude chose
        return error_card(card.get("message") or "Claude reported a problem.", _log_text(log), detect_limit=False)
    return _publish(card, folder, tid)


def _run_turn(turn: dict, claude, out) -> int:
    tid, kind = turn["turn"]["id"], turn["turn"]["kind"]
    out(f"Working on “{turn['lesson']['title']}” ({kind}).")
    log: Path | None = None
    beat: _Heartbeat | None = None
    try:
        folder = lesson_dir(turn["lesson"])
        if kind == "delete":
            shutil.rmtree(folder, ignore_errors=True)
            card = {"contract": contract.VERSION, "kind": "done", "message": "Removed from this computer."}
        else:
            sitedir = folder / "site"
            sitedir.mkdir(parents=True, exist_ok=True)
            (sitedir / "card.json").unlink(missing_ok=True)
            write_text(sitedir / "progress.txt", "Starting\n")
            log = sitedir / "claude.log"
            beat = _Heartbeat(tid, sitedir / "progress.txt")
            beat.start()
            card = _claude_turn(turn, folder, sitedir, log, claude)
            card = _with_slides(card, folder)
    except subprocess.TimeoutExpired:
        card = error_card("Claude took more than 3 hours on this step and was stopped.", _log_text(log))
    except ValueError as e:  # card.json that isn't JSON
        card = error_card(f"Claude's reply couldn't be read: {e}", _log_text(log))
    except UserError as e:
        card = error_card(str(e), _log_text(log))
    except Exception as e:  # noqa: BLE001  site or disk failure: still answer the turn if we can
        card = error_card(f"This step failed on this computer: {e}", _log_text(log))
    finally:
        if beat is not None:
            beat.done.set()
    try:
        card = _finish(tid, card, _log_text(log))
    except Exception as e:  # noqa: BLE001
        out(f"Couldn't send the result back: {keys.redact(str(e))[:200]}")
        return 1
    out(f"Sent back: {card['kind']}. {card['message']}")
    return 1 if card["kind"] == "error" else 0


BUSY_LINE = "Another worker run is still going."


def _once(claude, out, start: bool = False) -> tuple[str, int]:
    root = lessons_root()
    lock = _lock(root)
    if lock is None:
        out(BUSY_LINE)
        return BUSY, 0
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
        start, failures, said_busy = True, 0, False

        def once_out(line):                 # say "still going" once per busy stretch, not every poll
            if line == BUSY_LINE and said_busy:
                return
            out(line)
        while True:
            try:
                state, _ = _once(claude, once_out, start=start)
            except UserError as e:          # 401 (not connected) or 426 (update the plugin)
                out(str(e))
                return 1
            except net.ApiError as e:       # network down or the site busy: wait longer each time
                wait = BACKOFF[min(failures, len(BACKOFF) - 1)]
                failures += 1
                out(f"Can't reach the website ({e.status or 'no connection'}); trying again in {wait} s.")
                sleep(wait)
                continue
            failures = 0
            if state == BUSY:               # a --once run holds the lock: no call made, so keep `start` for the first real one
                said_busy = True
                sleep(POLL)
                continue
            start, said_busy = False, False
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
