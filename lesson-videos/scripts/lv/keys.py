"""API keys: environment first, then ~/.lesson-videos/keys.env. Values are never printed."""
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import zipfile
from pathlib import Path

from . import config
from .util import UserError, read_text, write_text

VARS = {
    "ELEVENLABS_API_KEY": "ElevenLabs (most natural narration, optional)",
    "GEMINI_API_KEY": "Gemini (music and AI clips, optional)",
}
TEMPLATE = """# lesson-videos API keys
# Paste each key right after the = sign (no spaces, no quotes), then save and close.
# Keep this file private. To replace a key, paste the new one over the old one.

# ElevenLabs (optional, most natural narration; without it a free voice is used): https://elevenlabs.io/app/developers/api-keys
ELEVENLABS_API_KEY=

# Gemini (optional, music and AI video clips): https://aistudio.google.com/api-keys
GEMINI_API_KEY=
"""
_PLACEHOLDER = re.compile(r"^(|x+|changeme|your[-_ ].*|<.*>|\.\.\.)$", re.I)
_SHAPES = re.compile(r"(AIza[0-9A-Za-z_\-]{10,}|sk_[A-Za-z0-9]{16,}|xi-[A-Za-z0-9]{8,})")
SERVICES = {"elevenlabs": "ELEVENLABS_API_KEY", "gemini": "GEMINI_API_KEY"}
NAMES = {"ELEVENLABS_API_KEY": "ElevenLabs", "GEMINI_API_KEY": "Gemini"}
_KEY = {"ELEVENLABS_API_KEY": r"sk_[A-Za-z0-9]{16,}", "GEMINI_API_KEY": r"AIza[0-9A-Za-z_\-]{30,}"}


class MissingKey(UserError):
    pass


def keys_file() -> Path:
    return config.home() / "keys.env"


def parse(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        line = line.strip().lstrip("﻿")
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _from_file(var: str) -> str:
    f = keys_file()
    return parse(read_text(f)).get(var, "").strip() if f.exists() else ""


def get(var: str, required: bool = True) -> str:
    for v in (os.environ.get(var, "").strip(), _from_file(var)):
        if v and not _PLACEHOLDER.match(v):
            return v
    if required:
        raise MissingKey(f"{VARS.get(var, var)}: no key yet. Run the `keys` command, paste the key "
                         "into the file that opens, save it, then run `keys check`.")
    return ""


def mask(v: str) -> str:
    return f"set, ends in …{v[-4:]}" if len(v) >= 8 else "set"


def redact(text) -> str:
    text = str(text)
    for var in VARS:
        v = get(var, required=False)
        if len(v) >= 8:
            text = text.replace(v, "[redacted]")
    return _SHAPES.sub("[redacted]", text)


def ensure_file() -> Path:
    f = keys_file()
    if not f.exists():
        write_text(f, TEMPLATE)
    if os.name == "posix":
        os.chmod(f, 0o600)
    return f


def store(var: str, value: str) -> Path:
    """Write var=value into keys.env, replacing any existing line for var. The value is never printed."""
    f = ensure_file()
    out, done = [], False
    for line in read_text(f).splitlines():
        body = line.strip().lstrip("\ufeff")
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


def paste(service: str, run=subprocess.run, platform: str = sys.platform) -> tuple[str, bool]:
    """Save the key on the clipboard for `service`, then clear the clipboard. Returns (variable name, cleared)."""
    var = SERVICES[service]
    label = f"{'an' if service == 'elevenlabs' else 'a'} {NAMES[var]} key"
    read, clear = clipboard_commands(platform)
    try:
        r = run(read, capture_output=True, encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        raise UserError("Couldn't read the clipboard here. In a Cowork chat, attach your keys file zipped and use "
                        "`keys load`; on your own computer, run `keys` and paste the key into the file that opens.") from None
    value = clean(r.stdout or "")
    if r.returncode or not re.fullmatch(_KEY[var], value):
        raise UserError(f"The clipboard doesn't hold {label}. Click Copy next to the key on the website, "
                        "then try again.")
    store(var, value)
    try:
        cleared = run(clear, input="", capture_output=True, encoding="utf-8", errors="replace", timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        cleared = False
    return var, cleared


def _decode(data: bytes) -> str:
    """UTF-8, or UTF-16 (what Notepad's "Unicode" saves), with or without its byte-order mark."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    if len(data) > 1 and data.count(0) * 3 > len(data):
        return data.decode("utf-16-le" if data[1] == 0 else "utf-16-be", errors="replace")
    return data.decode("utf-8", errors="replace")


def _texts(path: Path) -> list[str]:
    """The file's text, or the text of every file inside it when it's a .zip (how Cowork keeps it out of the chat)."""
    data = path.read_bytes()
    if zipfile.is_zipfile(io.BytesIO(data)):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return [_decode(z.read(i)) for i in z.infolist() if not i.is_dir()]
    return [_decode(data)]


def load(path: Path) -> list[str]:
    """Import keys from a keys file the teacher attached (plain text, TextEdit rich text, or a .zip). Never prints them."""
    path = Path(path)
    if not path.is_file():
        raise UserError(f"There's no file at {path}. Attach the keys file to this session and try again.")
    found = []
    for text in _texts(path):
        for var, shape in _KEY.items():
            m = re.search(rf"{var}\s*=\s*[\"'\u201c\u201d\u2018\u2019]?({shape})", text)
            if m and var not in found and not _PLACEHOLDER.match(m.group(1)):
                store(var, m.group(1))
                found.append(var)
    return found


def editor_command(path: Path, platform: str = sys.platform) -> list[str]:
    if platform == "darwin":
        return ["open", "-e", str(path)]
    if platform.startswith("win"):
        return ["notepad.exe", str(path)]
    return ["xdg-open", str(path)]


def open_in_editor(path: Path, runner=subprocess.Popen) -> list[str]:
    cmd = editor_command(path)
    runner(cmd)
    return cmd


def check(request=None) -> list[tuple[str, bool, str]]:
    """[(service, ok, message)]. Messages never contain key values."""
    from . import net
    request = request or net.request
    rows = []
    el = get("ELEVENLABS_API_KEY", required=False)
    if not el:
        rows.append(("ElevenLabs", True, "not set (optional): the free voice will be used"))
    else:
        try:
            sub = request(f"{config.ELEVEN_ROOT}/user/subscription", headers={"xi-api-key": el}, timeout=30)
            left = int(sub.get("character_limit", 0)) - int(sub.get("character_count", 0))
            rows.append(("ElevenLabs", True, f"{mask(el)}; {left:,} characters left this month ({sub.get('tier', '?')} plan)"))
        except net.ApiError as e:
            d = e.detail.lower()
            blocked = net.blocked_hint(urllib.parse.urlparse(config.ELEVEN_ROOT).netloc) if e.status == 0 else ""
            if "permission" in d:  # the key authenticated; it just can't read the account
                rows.append(("ElevenLabs", True, f"{mask(el)}; key works, but can't show your remaining credits "
                                                 "(to see them, edit the key at elevenlabs.io and set User to Access)"))
            else:
                hint = blocked or ("the key was rejected: create a new one and paste it again" if e.status == 401 else str(e))
                rows.append(("ElevenLabs", False, f"{mask(el)}; {hint}"))
    gm = get("GEMINI_API_KEY", required=False)
    if not gm:
        rows.append(("Gemini", True, "not set (optional): no music, no AI clips"))
    else:
        try:
            request(f"{config.GEMINI_ROOT}/models?pageSize=1", headers={"x-goog-api-key": gm}, timeout=30)
            rows.append(("Gemini", True, f"{mask(gm)}; key works. Billing is checked the first time music or a clip is made."))
        except net.ApiError as e:
            blocked = net.blocked_hint(urllib.parse.urlparse(config.GEMINI_ROOT).netloc) if e.status == 0 else ""
            hint = blocked or ("the key was rejected: create a new one and paste it again" if e.status in (400, 401, 403) else str(e))
            rows.append(("Gemini", False, f"{mask(gm)}; {hint}"))
    return rows
