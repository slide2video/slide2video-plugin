"""API keys: environment first, then ~/.lesson-videos/keys.env. Values are never printed."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from . import config
from .util import UserError, read_text, write_text

VARS = {
    "ELEVENLABS_API_KEY": "ElevenLabs (narration, required)",
    "GEMINI_API_KEY": "Gemini (music and AI clips, optional)",
}
TEMPLATE = """# lesson-videos API keys
# Paste each key right after the = sign (no spaces, no quotes), then save and close.
# Keep this file private. To replace a key, paste the new one over the old one.

# ElevenLabs (required, narration): https://elevenlabs.io/app/settings/api-keys
ELEVENLABS_API_KEY=

# Gemini (optional, music and AI video clips): https://aistudio.google.com/api-keys
GEMINI_API_KEY=
"""
_PLACEHOLDER = re.compile(r"^(|x+|changeme|your[-_ ].*|<.*>|\.\.\.)$", re.I)
_SHAPES = re.compile(r"(AIza[0-9A-Za-z_\-]{10,}|sk_[A-Za-z0-9]{16,}|xi-[A-Za-z0-9]{8,})")


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
        rows.append(("ElevenLabs", False, "missing (required): run `keys` and paste it"))
    else:
        try:
            sub = request(f"{config.ELEVEN_ROOT}/user/subscription", headers={"xi-api-key": el}, timeout=30)
            left = int(sub.get("character_limit", 0)) - int(sub.get("character_count", 0))
            rows.append(("ElevenLabs", True, f"{mask(el)}; {left:,} characters left this month ({sub.get('tier', '?')} plan)"))
        except net.ApiError as e:
            d = e.detail.lower()
            if "permission" in d:  # the key authenticated; it just can't read the account
                rows.append(("ElevenLabs", True, f"{mask(el)}; key works, but can't show your remaining credits "
                                                 "(to see them, edit the key at elevenlabs.io and allow User → Read)"))
            else:
                hint = "the key was rejected: create a new one and paste it again" if e.status == 401 else str(e)
                rows.append(("ElevenLabs", False, f"{mask(el)}; {hint}"))
    gm = get("GEMINI_API_KEY", required=False)
    if not gm:
        rows.append(("Gemini", True, "not set (optional): no music, no AI clips"))
    else:
        try:
            request(f"{config.GEMINI_ROOT}/models?pageSize=1", headers={"x-goog-api-key": gm}, timeout=30)
            rows.append(("Gemini", True, f"{mask(gm)}; key works. Billing is checked the first time music or a clip is made."))
        except net.ApiError as e:
            hint = "the key was rejected: create a new one and paste it again" if e.status in (400, 401, 403) else str(e)
            rows.append(("Gemini", False, f"{mask(gm)}; {hint}"))
    return rows
