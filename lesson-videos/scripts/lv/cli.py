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
    d = sub.add_parser("doctor", help="install and check everything, then render a 3-second test video")
    d.add_argument("--no-keys", action="store_true", help="skip the API key checks (for CI)")
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
    o = sub.add_parser("open", help="open a web page in the default browser")
    o.add_argument("url")
    a = sub.add_parser("asset", help="copy a deck image into a chapter's assets (upright, <=1600 px, JPEG-safe)")
    a.add_argument("src", type=Path)
    a.add_argument("dst", type=Path)
    a.add_argument("--max", type=int, default=1600)
    i = sub.add_parser("ingest", help="read a .pptx/.pdf deck into lesson-videos/_work/deck/")
    i.add_argument("deck", type=Path)
    i.add_argument("--work", type=Path)
    e = sub.add_parser("estimate", help="estimated ElevenLabs characters and Gemini dollars")
    e.add_argument("work", type=Path)
    e.add_argument("--chapters", type=int, help="plan stage: number of chapters (else count the written scripts)")
    e.add_argument("--minutes", type=float, default=5)
    e.add_argument("--clips", type=int, default=0)
    e.add_argument("--music", action="store_true")
    st = sub.add_parser("status", help="which chapters are done and what each needs next")
    st.add_argument("work", type=Path)
    m = sub.add_parser("music", help="one Lyria music bed (~$0.08) into _work/music/bed.mp3")
    m.add_argument("work", type=Path)
    m.add_argument("--prompt", required=True)
    c = sub.add_parser("clip", help="one Veo clip (~$0.40) from a photo into _work/clips/")
    c.add_argument("image", type=Path)
    c.add_argument("--work", type=Path, required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--prompt", required=True)
    c.add_argument("--frac", type=float, default=0.5)
    f = sub.add_parser("frames", help="turn a clip into JPEG frames for clip() in scenes.js")
    f.add_argument("clip", type=Path)
    f.add_argument("dest", type=Path)
    f.add_argument("--max", type=int)
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
    except Exception as e:  # noqa: BLE001
        from . import net
        if isinstance(e, net.ApiError):
            print(f"error: {e}", file=sys.stderr)
            return 1
        raise
    except KeyboardInterrupt:
        return 130


def dispatch(args) -> int:
    from . import keys
    if args.cmd == "doctor":
        from . import doctor
        return doctor.run_doctor(args.no_keys)
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
    if args.cmd == "open":
        import webbrowser
        webbrowser.open(args.url)
        print(f"Opened {args.url} in the browser.")
        return 0
    from . import ingest
    if args.cmd == "asset":
        print(ingest.prepare_asset(args.src, args.dst, args.max))
        return 0
    if args.cmd == "ingest":
        ingest.ingest(args.deck, args.work or ingest.default_work(args.deck))
        return 0
    from . import estimate, status
    if args.cmd == "estimate":
        chars = estimate.plan_chars(args.chapters, args.minutes) if args.chapters else estimate.chars_in_scripts(args.work)
        print(estimate.report(chars, args.clips, args.music))
        return 0
    if args.cmd == "status":
        print(status.report(args.work.resolve()))
        return 0
    from . import clips, music
    if args.cmd == "music":
        print(music.make_bed(args.work.resolve(), args.prompt))
        return 0
    if args.cmd == "clip":
        clips.make_clip(args.image, args.prompt, args.name, args.work.resolve(), args.frac)
        return 0
    if args.cmd == "frames":
        print(f"{clips.frames(args.clip, args.dest, args.max)} frames → {args.dest}")
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
