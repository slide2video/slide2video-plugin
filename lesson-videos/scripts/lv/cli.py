"""Command line: `uv run lesson-videos.py <command>`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .util import UserError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lesson-videos", description="Turn a slide deck into narrated study videos.")
    p.add_argument("--version", action="version", version=f"lesson-videos {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True, metavar="command")
    k = sub.add_parser("keys", help="open the keys file; `keys check` tests the keys")
    k.add_argument("action", nargs="?", choices=["open", "check"], default="open")
    n = sub.add_parser("narrate", help="record narration for a chapter (cached; only changed scenes cost credits)")
    n.add_argument("chapter", type=Path)
    s = sub.add_parser("stills", help="contact sheet of frames at the given seconds")
    s.add_argument("chapter", type=Path)
    s.add_argument("times", type=float, nargs="+")
    r = sub.add_parser("render", help="render the finished MP4 and captions")
    r.add_argument("chapter", type=Path)
    r.add_argument("--workers", type=int)
    r.add_argument("--fps", type=int, default=30)
    r.add_argument("--out", type=Path)
    pt = sub.add_parser("_part")
    for a in ("chapter", "out"):
        pt.add_argument(a, type=Path)
    for a in ("fps", "f0", "f1"):
        pt.add_argument(a, type=int)
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
    from . import narrate, render
    if args.cmd == "narrate":
        T = narrate.narrate(args.chapter.resolve())
        print(f"narration {T['duration']:.1f}s, {len(T['scenes'])} scenes")
        for s in T["scenes"]:
            print(f"  {s['id']:<16} start {s['start']:7.2f}  dur {s['dur']:6.2f}")
        return 0
    if args.cmd == "stills":
        print(render.stills(args.chapter.resolve(), args.times))
        return 0
    if args.cmd == "render":
        render.render(args.chapter.resolve(), args.workers, args.fps, args.out.resolve() if args.out else None)
        return 0
    if args.cmd == "_part":
        render.video_part(args.chapter, args.out, args.fps, args.f0, args.f1)
        return 0
    raise UserError(f"unknown command {args.cmd}")
