"""The worker that makes slide2video.com's lessons on this computer.

`worker --once` (the default): take this computer's next turn from the website, run Claude Code on it in the lesson's
folder, send back the card Claude wrote (or an error card), and exit.
`worker --watch` (what /slide2video:serve runs in the background): do that for every turn, one after another,
waiting between checks while there is none, keeping the computer awake, until Disconnect on the website, the
pairing is gone, or the process is stopped (Ctrl-C or SIGTERM; a step it was working on is handed back to start
again).
`worker --turn TURN.json --card-out CARD.json`: run the turn in that file the same way and write the resulting card to
the second file, without taking a turn from the website or finishing one."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path, PurePath

import lv
from . import awake, config, contract, keys, narrate, net, paths, site, version
from .util import UserError, read_json, read_text, safe_name, write_json, write_text

PROMPT = "Run /slide2video:make in site mode for this folder."
HEARTBEAT = 60                 # seconds between lease renewals
CLAUDE_TIMEOUT = 3 * 3600      # one turn never runs longer than this
CONTENT_TYPES = {".mp4": "video/mp4", ".vtt": "text/vtt", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".png": "image/png", ".json": "application/json"}
LIMIT = re.compile(r"(?:5-hour|weekly|usage|session) limit (?:reached|hit)|Claude usage limit", re.I)
LIMIT_SUFFIX = {".mp4": "video", ".vtt": "captions", ".jpg": "stills", ".jpeg": "stills", ".png": "stills"}
RESET = re.compile(r"resets?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap]m)(?:\s*\(([A-Za-z_]+(?:/[A-Za-z0-9_+-]+)+|UTC)\))?", re.I)
MAX_UPLOAD = 100 * 1024 * 1024  # the website takes at most this much in one file
GROUP_GRACE = 5                # seconds Claude's process group gets after SIGTERM before SIGKILL
# Claude Code reads these from the folder it runs in; a turn could plant them for the next turn. Never part of a lesson.
# AGENTS.md too: Claude Code reads it natively. --setting-sources "" keeps both instruction files out today; this
# guard is for the day it doesn't.
CLAUDE_CONFIG = (".claude", ".mcp.json", "CLAUDE.md", "CLAUDE.local.md", "AGENTS.md")
# Edit(...) rules cover every file-editing tool (Write too); Claude Code ignores Write(...) rules.
DENIED = ["WebFetch", "WebSearch", "Edit(./.claude/**)", "Edit(./.mcp.json)", "Edit(./CLAUDE.md)",
          "Edit(./CLAUDE.local.md)", "Edit(./AGENTS.md)"]
# Never an API key or another provider (CLAUDE_CODE_USE_BEDROCK/VERTEX/FOUNDRY go with every other CLAUDE_CODE_*).
DROPPED_ENV = ("LESSON_VIDEOS_PROJECT", "CLAUDECODE", "CLAUDE_EFFORT", "CLAUDE_PID", "ANTHROPIC_API_KEY",
               "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")
NEEDS_API_KEY = "Set ANTHROPIC_API_KEY to use --api-key."
BASH_TIMEOUT_MS = "3600000"    # render and narrate can take far longer than Claude Code's 10-minute Bash limit
SCHOOL_ONLY = "This computer makes School videos only."
POLL = 30                      # seconds between checks while no lesson is waiting
BACKOFF = (30, 60, 120, 300)   # seconds after network or server errors, capped at the last
IDLE, RAN, STOP, BUSY = "idle", "ran", "stop", "busy"
STOP_FINISH_TIMEOUT = 10       # seconds: a stopped step is handed back once, quickly, or left to its lease
STOPPED = ("Stopped on this computer before this step finished. It starts again when the computer is making videos "
           "again.")


def disconnected_line() -> str:
    return f"Disconnected from the website. To start again, run {site.cmd('serve')}."


def lessons_root() -> Path:
    """Where website lessons are worked on. A ~/Lesson Videos left by lesson-videos keeps being used, so a lesson in
    progress continues after the update."""
    if value := os.environ.get("LV_LESSONS_DIR"):
        base = Path(value)
    else:
        old = Path.home() / "Lesson Videos"
        base = old if old.is_dir() else Path.home() / "slide2video"
    return base


def project_dir(project: dict) -> Path:
    """The video project's folder: `LV_PROJECT_DIR` when set, else found by its id (the title on the site may have changed since)."""
    given = os.environ.get("LV_PROJECT_DIR", "").strip()
    if given:
        return Path(given)
    root, tag = lessons_root(), f"({project['id']})"
    if root.exists():
        for d in root.iterdir():
            if d.is_dir() and d.name.endswith(tag):
                return d
    return root / f"{safe_name(project['title'])[:80]} {tag}"


def lv_command() -> str:
    return f'"{shutil.which("uv") or "uv"}" run "{config.ENTRY}"'


def read_rule(folder: PurePath) -> str:
    """A Read rule for an absolute folder. Claude Code matches Windows paths in POSIX form: C:\\Plugins\\lv is
    /c/Plugins/lv, so the rule is Read(//c/Plugins/lv/**); //C:/Plugins/lv never matches."""
    path = folder.as_posix()
    if re.match(r"[A-Za-z]:/", path):
        path = "/" + path[0].lower() + path[2:]
    return f"Read(/{path}/**)"


def claude_command(lv: str) -> list[str]:
    """Claude Code pinned to this job: one model (config.CLAUDE_MODEL), no user, project or local settings (so no
    hooks, extra allow rules or permission mode of the teacher's own), no MCP servers, this plugin loaded explicitly,
    and anything not allowed below is refused without asking (nobody is there to answer)."""
    claude = shutil.which("claude")
    if not claude:
        raise UserError("Claude Code isn't installed on this computer (no `claude` command). Install it from "
                        "https://claude.com/claude-code, sign in once, then try again.")
    model = os.environ.get("LV_CLAUDE_MODEL") or config.CLAUDE_MODEL
    return [claude, "-p", PROMPT, "--model", model,
            "--permission-mode", "dontAsk", "--setting-sources", "", "--strict-mcp-config",
            "--plugin-dir", str(config.PLUGIN_ROOT),
            "--allowedTools", f"Bash({lv}:*)", "Read(./**)", read_rule(config.PLUGIN_ROOT), "Edit(./**)",
            "--disallowedTools", *DENIED]


def _site_env(private: Path, api_key: bool = False, root: Path | None = None) -> dict:
    """Claude's environment: site mode on, and no registered project folder to redirect output into. The settings
    file is never created and sits in a private folder outside the lesson, where Claude's file tools can't plant one.
    Variables a parent Claude Code session set are dropped (the job is its own session), and so is every way to use an
    API key or another provider: the job always runs on the teacher's Claude subscription. The subscription sign-in
    token a teacher may keep in CLAUDE_CODE_OAUTH_TOKEN is kept. With `api_key`, ANTHROPIC_API_KEY and
    ANTHROPIC_BASE_URL from the environment are kept instead (and the sign-in token is dropped), and Claude Code's
    non-essential traffic is off."""
    if api_key and not os.environ.get("ANTHROPIC_API_KEY"):
        raise UserError(NEEDS_API_KEY)
    env = {k: v for k, v in os.environ.items() if k not in DROPPED_ENV
           and (not k.startswith("CLAUDE_CODE_") or k == "CLAUDE_CODE_OAUTH_TOKEN")}
    if api_key:
        env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
        for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"):
            if os.environ.get(k):
                env[k] = os.environ[k]
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    env["LV_SITE_MODE"] = "1"
    if root is not None:   # the lesson folder the site-mode path guard holds every path to, wherever Claude cds
        env["LV_SITE_ROOT"] = str(Path(root).resolve())
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


class LeaseLost(Exception):
    """The website gave this step to someone else (a heartbeat answered 409): Claude is stopped, nothing is sent."""


# set by the heartbeat when the website says this computer no longer holds the turn; cleared at each turn's start
_turn_stop = threading.Event()


def _private_dir(cwd: Path) -> Path:
    """A new private folder for Claude's settings, never inside the lesson folder (where Claude's file tools could plant
    one), even when TMPDIR points there."""
    d = Path(tempfile.mkdtemp(prefix="lv-site-"))
    r, lesson = d.resolve(), Path(cwd).resolve()
    if r == lesson or lesson in r.parents:
        shutil.rmtree(d, ignore_errors=True)
        config.home().mkdir(parents=True, exist_ok=True)
        d = Path(tempfile.mkdtemp(prefix="lv-site-", dir=config.home()))
    return d


def _kill_group(proc: subprocess.Popen) -> None:
    """Stop Claude and everything it started (uv, the renderer, ffmpeg): its whole process group (POSIX) or process
    tree (Windows)."""
    if proc.poll() is not None and os.name == "nt":
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=30)
        else:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=GROUP_GRACE)
            except subprocess.TimeoutExpired:
                pass
            os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError, subprocess.SubprocessError):
        pass
    try:
        proc.wait(timeout=GROUP_GRACE)
    except subprocess.TimeoutExpired:
        pass


def _run_in_group(cmd: list[str], *, timeout: float, **kw) -> subprocess.CompletedProcess:
    """subprocess.run, but Claude runs in its own process group, and the whole group is stopped when it times out, when
    the website takes the step back (_turn_stop: LeaseLost) or when the worker itself is stopped, so the renderer and
    ffmpeg never keep writing into the lesson folder while the next step starts."""
    if os.name == "nt":
        kw["creationflags"] = kw.get("creationflags", 0) | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    proc = subprocess.Popen(cmd, **kw)
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                return subprocess.CompletedProcess(cmd, proc.wait(timeout=max(0.1, min(5.0, deadline - time.monotonic()))))
            except subprocess.TimeoutExpired:
                if _turn_stop.is_set():
                    raise LeaseLost() from None
                if time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired(cmd, timeout) from None
    except BaseException:
        _kill_group(proc)
        raise


def run_claude(cmd: list[str], cwd: Path, log: Path, api_key: bool = False) -> int:
    _clear_claude_config(cwd)
    private = _private_dir(cwd)
    try:
        with open(log, "w", encoding="utf-8") as f:
            return _run_in_group(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                 env=_site_env(private, api_key=api_key, root=cwd), timeout=CLAUDE_TIMEOUT).returncode
    finally:
        shutil.rmtree(private, ignore_errors=True)


def _zone(name: str | None):
    """The time zone Claude's message names ("resets 3pm (America/Los_Angeles)"), or None for this computer's own."""
    if not name:
        return None
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("UTC" if name.upper() == "UTC" else name)
    except Exception:  # noqa: BLE001  unknown name, or no time zone data (Windows without tzdata)
        return None


def _reset_time(log: str, now: dt.datetime) -> dt.datetime:
    """When the usage limit resets, from Claude's "resets 3pm" (in the zone it names, else this computer's), across a
    daylight-saving change too: the wall time is found on the right day first, and its offset comes from the zone."""
    m = RESET.search(log)
    if not m:
        return now + dt.timedelta(hours=1)
    hour = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "pm" else 0)
    zone = _zone(m.group(4))
    # wall-clock time in the zone, without an offset; with no zone, this computer's own local time
    local = now.astimezone(zone).replace(tzinfo=None) if zone else now.astimezone().replace(tzinfo=None)
    t = local.replace(hour=hour, minute=int(m.group(2) or 0), second=0, microsecond=0)
    if t <= local:
        t += dt.timedelta(days=1)
    # a naive time made aware: in the zone (ZoneInfo gives that day's offset), else by the system's rules for that day
    return t.replace(tzinfo=zone) if zone else t.astimezone()


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
    """Scene marks for the player: id, start, length, a label, the first words of the narration and the deck slide the
    scene shows (`slide`, only when script.json names one)."""
    try:
        T = narrate.read_timing(ch_dir)
        spec = {s["id"]: s for s in read_json(paths.chapter(ch_dir).code / "script.json")["scenes"]}
    except (OSError, ValueError, KeyError, UserError):
        return None

    def mark(s: dict) -> dict:
        sc = spec.get(s["id"], {})
        m = {"id": s["id"], "start": s["start"], "dur": s["dur"], "label": s["id"].replace("_", " ").replace("-", " ").title(),
             "first_words": " ".join(sc.get("say", "").split()[:8])}
        if type(sc.get("slide")) is int:
            m["slide"] = sc["slide"]
        return m
    return {"duration": T["duration"], "scenes": [mark(s) for s in T["scenes"]]}


class _Lock:
    """An OS lock on an open file (flock on POSIX, msvcrt on Windows): the kernel releases it when the process ends,
    however it ends, so a stale lock never needs taking over and two runs can never both hold it. The file stays."""

    def __init__(self, fd: int):
        self.fd = fd

    def release(self) -> None:
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(self.fd, 0, os.SEEK_SET)
                msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fd, fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            os.close(self.fd)


def _lock(root: Path, name: str = ".worker.lock") -> _Lock | None:
    """The run lock, or None while another run holds it."""
    root.mkdir(parents=True, exist_ok=True)
    fd = os.open(root / name, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    try:   # who holds it, for a person looking; nothing reads it
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
    except OSError:
        pass
    return _Lock(fd)


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


NOTES = 5                       # notes the website shows while a step runs


def _notes(f: Path) -> list[str]:
    """The last few lines of site/notes.txt: what Claude noticed, in plain words, for the website to show."""
    try:
        lines = [l.strip() for l in read_text(f).splitlines() if l.strip()]
    except OSError:
        return []
    return [keys.redact(l)[:200] for l in lines[-NOTES:]]


class _Heartbeat(threading.Thread):
    """Renews the turn's lease every HEARTBEAT seconds. A 409 means the website no longer gives this computer the
    turn (its lease ran out and it went to another run): `lost` is set and so is _turn_stop, which stops Claude."""

    def __init__(self, turn_id: str, progress: Path):
        super().__init__(daemon=True)
        self.turn_id, self.progress, self.done, self.lost = turn_id, progress, threading.Event(), threading.Event()

    def run(self):
        while not self.done.wait(HEARTBEAT):
            try:
                text, fraction = _progress(self.progress)
                body = {"progress": text} if fraction is None else {"progress": text, "fraction": fraction}
                if notes := _notes(self.progress.with_name("notes.txt")):
                    body["notes"] = notes
                site.call(f"/api/device/turns/{self.turn_id}/heartbeat", body)
            except net.ApiError as e:
                if e.status == 409:
                    self.lost.set()
                    _turn_stop.set()
                    return
            except Exception:  # noqa: BLE001  a missed heartbeat only shortens the lease
                pass

    def stop(self) -> None:
        """No more beats, and none still in flight (one landing after the finish would be refused anyway)."""
        self.done.set()
        if self.is_alive():
            self.join(timeout=60)


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
        if dest.is_symlink():   # never written through: a link planted at in/<name> could point anywhere
            dest.unlink()
        fd, tmp = tempfile.mkstemp(prefix=".fetch-", dir=dest.parent)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, dest)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise


def _upload(turn_id: str, path: str, data: bytes, content_type: str) -> None:
    site.call(f"/api/device/turns/{turn_id}/files?path={urllib.parse.quote(path)}", data=data, method="PUT",
              headers={"Content-Type": content_type}, timeout=900)


def _next_version(folder: Path, chapter: int) -> int:
    """The chapter's next version number; taken for good only by _keep_version, once its files are uploaded (a failed
    upload doesn't leave a gap: v1, v3)."""
    f = folder / "site" / "versions.json"
    d = read_json(f) if f.exists() else {}
    return d.get(str(chapter), 0) + 1


def _keep_version(folder: Path, chapter: int, version: int) -> None:
    f = folder / "site" / "versions.json"
    d = read_json(f) if f.exists() else {}
    d[str(chapter)] = max(d.get(str(chapter), 0), version)
    write_json(f, d)


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
    for f in local.values():
        if f.stat().st_size > MAX_UPLOAD:
            raise UserError(f"{f.name} is {f.stat().st_size / 1024 / 1024:.0f} MB, more than the {MAX_UPLOAD // 1024 // 1024} MB "
                            "slide2video.com takes in one file. Make the chapter shorter, or ask for a smaller video.")
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
    _keep_version(folder, ch, card["version"])
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


def _hand_back_card(log: str) -> dict:
    card = error_card(STOPPED, log)
    card["retry_after"] = dt.datetime.now().astimezone().isoformat()
    return card


def _write_card(card_out: Path, card: dict) -> None:
    """Write the card whole or not at all: into a temporary file next to it, then moved into place."""
    card_out = Path(card_out)
    card_out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".card-", suffix=".tmp", dir=card_out.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(_redacted(card), indent=1, ensure_ascii=False) + "\n")
        os.replace(tmp, card_out)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _hand_back(turn_id: str, log: str) -> None:
    """Stopped in the middle of a step: tell the website at once, so the step waits for this computer to start again
    instead of looking busy until its lease runs out. One quick try; a failure leaves it to the lease."""
    card = _hand_back_card(log)
    try:
        site.call(f"/api/device/turns/{turn_id}/finish", _redacted(card), timeout=STOP_FINISH_TIMEOUT, retries=0)
    except Exception:  # noqa: BLE001  stopping must not wait on or fail because of the website
        pass


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


def _run_turn(turn: dict, claude, out, finish: bool = True, card_out: Path | None = None) -> int:
    """Run one turn. With `finish=False` nothing is sent to /finish: the card (or, when stopped, the hand-back card)
    is written to `card_out` instead."""
    tid, kind = turn["turn"]["id"], turn["turn"]["kind"]
    out(f"Working on “{turn['project']['title']}” ({kind}).")
    log: Path | None = None
    beat: _Heartbeat | None = None
    _turn_stop.clear()
    try:
        if kind != "delete" and turn["project"]["style"] != "school":
            raise UserError(SCHOOL_ONLY)
        folder = project_dir(turn["project"])
        if kind == "delete":
            shutil.rmtree(folder, ignore_errors=True)
            if folder.exists() or folder.is_symlink():   # locked, in use, or not ours to remove: say so, keep the tombstone
                card = error_card(f"Couldn't remove {folder.name} from this computer. Close anything using it and try again.", "")
            else:
                card = {"contract": contract.VERSION, "kind": "done", "message": "Removed from this computer."}
        else:
            sitedir = folder / "site"
            sitedir.mkdir(parents=True, exist_ok=True)
            (sitedir / "card.json").unlink(missing_ok=True)
            (sitedir / "notes.txt").unlink(missing_ok=True)
            write_text(sitedir / "progress.txt", "Starting\n")
            log = sitedir / "claude.log"
            beat = _Heartbeat(tid, sitedir / "progress.txt")
            beat.start()
            card = _claude_turn(turn, folder, sitedir, log, claude)
            card = _with_slides(card, folder)
    except LeaseLost:  # the website gave the step to another run: nothing more is sent for it
        if beat is not None:
            beat.stop()
        out("This step was given to another run (this computer's turn ran out), so its result isn't sent.")
        if not finish and card_out is not None:
            _card_if_missing(card_out, lambda: _hand_back_card(_log_text(log)))
        return 1
    except KeyboardInterrupt:  # Ctrl-C, or SIGTERM from "stop" in Claude Code: Claude's process group is stopped
        if beat is not None:
            beat.done.set()
        if finish:
            _hand_back(tid, _log_text(log))
        elif card_out is not None:
            _card_if_missing(card_out, lambda: _hand_back_card(_log_text(log)))
        raise
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
            beat.stop()
    if beat is not None and beat.lost.is_set():   # lost while the card was being made: nothing is sent
        out("This step was given to another run (this computer's turn ran out), so its result isn't sent.")
        return 1
    if not finish:
        try:
            _write_card(card_out, card)
        except OSError as e:
            out(f"Couldn't write the result: {keys.redact(str(e))[:200]}")
            return 1
        out(f"Result: {card['kind']}. {card['message']}")
        return 1 if card["kind"] == "error" else 0
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
        if isinstance(turn, dict) and turn.get("stop") is True:
            return STOP, 0
        bad = contract.problems("turn", turn)
        if bad:
            inner = turn.get("turn") if isinstance(turn, dict) else None
            tid = inner.get("id") if isinstance(inner, dict) else None
            if tid:
                _finish(tid, error_card("This job doesn't match what this plugin understands: " + "; ".join(bad[:3]), ""))
            return RAN, 1
        return RAN, _run_turn(turn, claude or run_claude, out)
    finally:
        lock.release()


def _claude_runner(claude, api_key: bool):
    """The function that runs Claude Code for a turn; with `api_key`, the key is checked before any turn is taken."""
    if claude is not None or not api_key:
        return claude
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise UserError(NEEDS_API_KEY)
    return lambda cmd, cwd, log: run_claude(cmd, cwd, log, api_key=True)


def run_once(claude=None, out=print, api_key: bool = False) -> int:
    state, code = _once(_claude_runner(claude, api_key), out)
    if state == STOP:
        out(disconnected_line())
    return code


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


def run_given(turn_file: Path, card_out: Path, api_key: bool = False, claude=None, out=print) -> int:
    """`worker --turn`: run the turn in `turn_file` the way a taken turn runs (inputs, Claude Code, review uploads,
    heartbeats), without taking it from the website's queue or finishing it. The card goes to `card_out` on every way
    out: the exit code is 0 for a card that isn't an error, 1 otherwise. When stopped, the hand-back card is written,
    then the interruption continues. An old `card_out` is removed first, so a missing file means the process was
    killed."""
    card_out = Path(card_out)
    previous = _sigterm_as_interrupt()
    try:
        card_out.unlink(missing_ok=True)
        return _run_given(turn_file, card_out, api_key, claude, out)
    except KeyboardInterrupt:
        _card_if_missing(card_out, lambda: _hand_back_card(""))
        raise
    except Exception as e:  # noqa: BLE001  an unexpected failure still leaves a card
        message = f"This step failed on this computer: {e}"
        _card_if_missing(card_out, lambda: error_card(message, ""))
        out(f"Result: error. {keys.redact(message)[:200]}")
        return 1
    except BaseException:
        _card_if_missing(card_out, lambda: error_card("This step failed on this computer.", ""))
        raise
    finally:
        _restore_sigterm(previous)


def _card_if_missing(card_out: Path, make) -> None:
    """Best effort: write a card only when none was written on the way here."""
    try:
        if not card_out.exists():
            _write_card(card_out, make())
    except Exception:  # noqa: BLE001  nothing more can be done; the missing file says what happened
        pass


def _run_given(turn_file: Path, card_out: Path, api_key: bool, claude, out) -> int:
    try:
        claude = _claude_runner(claude, api_key)
        turn = read_json(turn_file)
        bad = contract.problems("turn", turn)
        if bad:
            raise UserError("This job doesn't match what this plugin understands: " + "; ".join(bad[:3]))
    except (OSError, ValueError, UserError) as e:
        card = error_card(str(e) if isinstance(e, UserError) else f"The job file couldn't be read: {e}", "")
        _write_card(card_out, card)
        out(f"Result: error. {card['message']}")
        return 1
    lock = _lock(lessons_root())
    if lock is None:
        _write_card(card_out, error_card(BUSY_LINE, ""))
        out(BUSY_LINE)
        return 1
    try:
        return _run_turn(turn, claude or run_claude, out, finish=False, card_out=card_out)
    finally:
        lock.release()


def watch(claude=None, out=print, sleep=time.sleep, awake_on=awake.keep_awake, awake_off=awake.release,
          api_key: bool = False) -> int:
    """`worker --watch`: run every step this computer is given, one after another, until the website says stop
    (Disconnect), the pairing is gone, or the process is stopped. Keeps the computer awake meanwhile."""
    claude = _claude_runner(claude, api_key)
    root = lessons_root()
    guard = _lock(root, ".worker-watch.lock")
    if guard is None:
        out(f"This computer is already making videos for {site.host()} (another window is running it).")
        return 0
    handle = previous = None
    awake = False
    try:
        previous = _sigterm_as_interrupt()
        try:
            who = site.status()
            as_who = f" as {who['user_email']} on {who['device_name']}"
        except UserError as e:              # not connected, or the plugin needs an update: nothing to start
            out(str(e))
            return 1
        except (net.ApiError, KeyError, TypeError):  # can't reach the website yet: the loop below backs off
            as_who = ""
        handle, awake = awake_on(out=out), True
        out(f"Making videos for {site.site_url()}{as_who} with slide2video {lv.__version__}. "
            "Waiting for lessons… (stop with Ctrl-C, or Disconnect on the website)")
        told = None

        def tell_update():                  # once per website version that is newer than this plugin
            nonlocal told
            line = version.update_line(site.LATEST)
            if line and site.LATEST != told:
                told = site.LATEST
                out(line)
        tell_update()
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
            tell_update()
            if state == BUSY:               # a --once run holds the lock: no call made, so keep `start` for the first real one
                said_busy = True
                sleep(POLL)
                continue
            start, said_busy = False, False
            if state == STOP:
                out(disconnected_line())
                return 0
            if state == IDLE:
                sleep(POLL)
    except KeyboardInterrupt:
        out("Stopped. This computer no longer makes videos for the website.")
        return 0
    finally:
        if awake:
            awake_off(handle)
        _restore_sigterm(previous)
        guard.release()
