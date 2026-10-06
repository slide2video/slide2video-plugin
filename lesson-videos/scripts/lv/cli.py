"""Command line: `uv run lesson-videos.py <command>`."""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .util import UserError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lesson-videos", description="Turn a slide deck into narrated study videos.")
    p.add_argument("--version", action="version", version=f"lesson-videos {__version__}")
    p.add_subparsers(dest="cmd", required=True, metavar="command")
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
    raise UserError(f"unknown command {args.cmd}")
