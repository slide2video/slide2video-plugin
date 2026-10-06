"""Command line: `uv run lesson-videos.py <command>`."""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .util import UserError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lesson-videos", description="Turn a slide deck into narrated study videos.")
    p.add_argument("--version", action="version", version=f"lesson-videos {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True, metavar="command")
    k = sub.add_parser("keys", help="open the keys file; `keys check` tests the keys")
    k.add_argument("action", nargs="?", choices=["open", "check"], default="open")
    return p


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    args = build_parser().parse_args(argv)
    try:
        return dispatch(args)
    except UserError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


def dispatch(args) -> int:
    from . import keys
    if args.cmd == "keys":
        if args.action == "check":
            rows = keys.check()
            for name, good, msg in rows:
                print(f"{'✓' if good else '✗'} {name}: {msg}")
            return 0 if all(good for _, good, _ in rows) else 1
        f = keys.ensure_file()
        keys.open_in_editor(f)
        print(f"Opened {f}. Paste the keys after the = signs, save, close the editor, then run `keys check`.")
        return 0
    raise UserError(f"unknown command {args.cmd}")
