"""Command line: `uv run lesson-videos.py <command>`."""
from __future__ import annotations

import argparse
import os
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
    k = sub.add_parser("keys", help="open the keys file; `keys check` tests them; `keys paste elevenlabs|gemini` "
                                    "saves the key on the clipboard; `keys load FILE` imports a keys file (or .zip)")
    k.add_argument("action", nargs="?", choices=["open", "check", "paste", "load"], default="open")
    k.add_argument("target", nargs="?", help="paste: elevenlabs or gemini; load: the keys file")
    ini = sub.add_parser("init", help="optional: keep lessons in a project folder (text there, videos and paid media "
                                      "in a results folder)")
    ini.add_argument("--path", type=Path, required=True)
    wh = sub.add_parser("where", help="where a lesson's (or chapter's) files go")
    wh.add_argument("path", type=Path, nargs="?", default=Path("."))
    n = sub.add_parser("narrate", help="record narration for a chapter (cached; only changed scenes cost credits)")
    n.add_argument("chapter", type=Path)
    n.add_argument("--cached-only", action="store_true", help="never record a new take; fail and name the scenes "
                                                               "that need one")
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
    cd = sub.add_parser("card", help="check a site-mode card (site/card.json) before stopping")
    cd.add_argument("file", type=Path)
    pr = sub.add_parser("pair", help="connect this computer to slide2video.com (shows a code to type on the website)")
    pr.add_argument("--name", help="what the website calls this computer (default: its computer name)")
    wk = sub.add_parser("worker", help="take this computer's next job from slide2video.com and run it")
    wk.add_argument("--once", action="store_true", help="run at most one job, then exit (the default)")
    wk.add_argument("--status", action="store_true", help="show which account this computer is connected to")
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


def _site_mode_paths_ok(args) -> None:
    """In site mode every path argument must stay inside the lesson folder (the current directory), and no
    registered project folder (env or settings file) may redirect output elsewhere."""
    from . import project
    if os.environ.get("LESSON_VIDEOS_PROJECT") or project.project_home() is not None:
        raise UserError("A lesson-videos project folder can't be used while working for slide2video.com.")
    root = Path.cwd().resolve()
    for v in vars(args).values():
        for item in (v if isinstance(v, list) else [v]):
            if isinstance(item, Path):
                r = item.resolve()
                if r != root and root not in r.parents:
                    raise UserError(f"{item} is outside this lesson's folder; in site mode only files in the lesson folder can be used.")


def dispatch(args) -> int:
    from . import keys
    if os.environ.get("LV_SITE_MODE") == "1" and (
            args.cmd in ("open", "pair", "worker", "init") or (args.cmd == "keys" and args.action != "check")):
        raise UserError(f"{args.cmd} isn't available while working for slide2video.com.")
    if os.environ.get("LV_SITE_MODE") == "1":
        _site_mode_paths_ok(args)
    if args.cmd == "doctor":
        from . import doctor
        return doctor.run_doctor(args.no_keys)
    if args.cmd == "keys":
        if args.action == "paste":
            if args.target not in keys.SERVICES:
                raise UserError("Say which key: `keys paste elevenlabs` or `keys paste gemini`.")
            var, cleared = keys.paste(args.target)
            stored = [var]
            print(f"Saved the {keys.NAMES[var]} key and cleared the clipboard." if cleared else
                  f"Saved the {keys.NAMES[var]} key, but couldn't clear the clipboard: copy something else "
                  "so the key isn't pasted somewhere by accident.")
        elif args.action == "load":
            if not args.target:
                raise UserError("Give the attached keys file: `keys load <file>`.")
            stored = keys.load(Path(args.target))
            if not stored:
                print("No keys found in that file. Check each key is pasted right after its = sign, then attach it again.")
                return 1
            print("Saved: " + ", ".join(keys.NAMES[v] for v in stored) + ".")
        elif args.action == "check":
            stored = list(keys.VARS)
        else:
            f = keys.ensure_file()
            keys.open_in_editor(f)
            print(f"Opened {f}. Paste the keys after the = signs, save, close the editor, then run `keys check`.")
            return 0
        for var in stored:
            if os.environ.get(var, "").strip() and args.action != "check":
                print(f"note: {var} is also set in this computer's environment, and that value is used instead.")
        names = {keys.NAMES[v] for v in stored}
        rows = [r for r in keys.check() if r[0] in names]
        for name, good, msg in rows:
            print(f"{'✓' if good else '✗'} {name}: {msg}")
        return 0 if all(good for _, good, _ in rows) else 1
    if args.cmd == "card":
        from . import contract
        from .util import read_json
        try:
            obj = read_json(args.file)
        except (OSError, ValueError) as e:
            print(f"{args.file}: not readable JSON ({e})")
            return 1
        bad = contract.problems("card", obj)
        print("card ok" if not bad else "\n".join(bad))
        return 0 if not bad else 1
    if args.cmd == "pair":
        from . import site
        email = site.pair(name=args.name)
        print(f"This computer is connected to {site.site_url()} for {email}.")
        return 0
    if args.cmd == "worker":
        from . import site
        if args.status:
            s = site.status()
            print(f"Connected to {site.site_url()} as {s['teacher_email']} (this device: {s['device_name']}).")
            return 0
        from . import worker
        return worker.run_once()
    if args.cmd == "open":
        import webbrowser
        webbrowser.open(args.url)
        print(f"Opened {args.url} in the browser.")
        return 0
    if args.cmd == "init":
        from . import project
        p, created = project.init_project(args.path)
        print(f"{'created' if created else 'kept'} {p.home / project.CONFIG}")
        if not created and "lessons_dir" not in project._config(p.home):
            print("note: it has no lessons_dir line; lessons go in lessons/ (add `lessons_dir: lessons` to make it explicit)")
        print(f"lessons: {p.lessons_dir}\nvideos:  {p.results_dir / 'lessons'}\nwork:    {p.work_dir / 'lessons'}")
        return 0
    if args.cmd == "where":
        print(where(args.path))
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
        print(estimate.report(chars, args.clips, args.music, paid_voice=bool(keys.get("ELEVENLABS_API_KEY", required=False))))
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
        T = narrate.narrate(args.chapter.resolve(), cached_only=args.cached_only)
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


def where(path: Path) -> str:
    from . import paths, project
    proj = project.load_project()
    lines = []
    if proj is None:
        lines.append("No project folder registered: everything goes next to the deck, in lesson-videos/.")
    elif not proj.exists:
        lines.append(f"The registered project folder {proj.home} doesn't exist; run `init --path` again. "
                     "Until then everything goes next to the deck.")
    path = Path(path).resolve()
    if (path / "script.json").exists():
        c = paths.chapter(path)
        if c.project:
            lines.append(f"lesson:  {c.lesson_id}")
        lines += [f"chapter: {c.code}", f"assets:  {c.assets}", f"voice:   {c.voice}", f"build:   {c.build}",
                  f"videos:  {c.out}"]
        return "\n".join(lines)
    if proj is not None and proj.exists and paths._below(path, proj.home) is not None \
            and paths._below(path, proj.lessons_dir.resolve()) in (None, Path(".")):
        lines += [f"project: {proj.home}", f"lessons: {proj.lessons_dir}  (one folder per lesson: <course>/<unit>)",
                  f"videos:  {proj.results_dir / 'lessons'}", f"work:    {proj.work_dir / 'lessons'}",
                  "Run `where` on a lesson folder (lessons/<course>/<unit>) to see where its files go."]
        return "\n".join(lines)
    les = paths.lesson(path)
    if les.project:
        lines += [f"lesson:  {les.lesson_id}", f"text:    {les.code}", f"sources: {les.sources}",
                  f"work:    {les.work}", f"videos:  {les.out}"]
    elif proj is not None and proj.exists:
        lines.append(f"{path} is not inside the project's lessons folder ({proj.lessons_dir}): everything goes next "
                     "to the deck, in lesson-videos/.")
    return "\n".join(lines)
