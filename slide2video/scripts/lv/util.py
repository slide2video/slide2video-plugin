"""UTF-8 file helpers, subprocess with argument lists, and the plain-language error type."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


class UserError(RuntimeError):
    """A failure with a plain-language message; the CLI prints it without a traceback."""


def read_text(p) -> str:
    return Path(p).read_text(encoding="utf-8")


def write_text(p, s: str) -> Path:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")
    return p


def read_json(p):
    return json.loads(read_text(p))


def write_json(p, obj) -> Path:
    return write_text(p, json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


def run(*args, **kw) -> subprocess.CompletedProcess:
    return subprocess.run([str(a) for a in args], check=True, **kw)


def safe_name(name: str) -> str:
    """A file name that is valid on Windows and macOS ("Entry 5/6" -> "Entry 5-6")."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", name).strip().rstrip(".") or "video"
