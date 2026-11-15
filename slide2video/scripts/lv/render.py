"""Serve a chapter folder, seek the page frame by frame in headless Chromium, pipe JPEGs into ffmpeg."""
from __future__ import annotations

import base64
import functools
import hashlib
import http.server
import math
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from contextlib import contextmanager
from pathlib import Path

from . import captions, chromium, config, mix, paths, sfx, status, tools
from .narrate import read_timing
from .page import ensure_page, output_path, routes
from .util import NotFinished, UserError, read_json, run, write_json, write_text

GRAB = """async ([t, q]) => {
  window.__render(t);
  if (Engine.pending) { await Engine.waitLoads(); window.__render(t); }
  return document.getElementById('c').toDataURL('image/jpeg', q).split(',')[1];
}"""


_MISSING = str(Path(__file__).with_name(".lv-not-served") / "x")  # never exists: the base class answers 404


class _Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".js": "text/javascript", ".html": "text/html", ".ttf": "font/ttf", ".jpg": "image/jpeg",
                      ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".mp3": "audio/mpeg",
                      ".json": "application/json", ".svg": "image/svg+xml"}

    def __init__(self, *args, routes=(), **kw):
        self.routes = routes
        super().__init__(*args, **kw)

    def translate_path(self, path: str) -> str:
        """URL prefix → folder (or exact URL → file); anything that escapes its folder is not served."""
        url = urllib.parse.unquote(urllib.parse.urlsplit(path).path)
        for prefix, target in self.routes:
            if prefix.endswith("/") and url.startswith(prefix):
                base = Path(target).resolve()
                f = (base / url[len(prefix):]).resolve()
                return str(f) if f.is_relative_to(base) else _MISSING
            if url == prefix:
                return str(target)
        return _MISSING

    def log_message(self, *args):
        pass


@contextmanager
def serve(routes: list[tuple[str, Path]]):
    handler = functools.partial(_Handler, routes=routes, directory=str(Path.cwd()))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield srv.server_address[1]
    finally:
        srv.shutdown()
        srv.server_close()


def _local_only(ctx, port: int, logs: list[str]) -> None:
    """Second layer (the first is chromium.launch: no network but the page server's port). Requests other than
    http://127.0.0.1:<port>/… and the data:/blob: URLs the page makes itself are aborted and logged. WebSockets are
    routed to a handler that only logs and never calls connect_to_server(): Playwright then answers with a fake
    socket inside the browser, so scenes.js may see it "open" but no connection is made to any server."""
    local = f"http://127.0.0.1:{port}/"

    def gate(route):
        url = route.request.url
        if url.startswith(local) or url.startswith(("data:", "blob:")):
            route.continue_()
        else:
            logs.append(f"blocked: {url[:200]} (the page may only load its own files)")
            route.abort("blockedbyclient")

    def no_socket(ws):  # log only: ws.close() here deadlocks the sync API, and nothing is connected anyway
        logs.append(f"blocked: {ws.url[:200]} (the page may only load its own files)")

    ctx.route("**/*", gate)
    ctx.route_web_socket("**/*", no_socket)


@contextmanager
def page_for(ch: Path):
    from playwright.sync_api import sync_playwright
    logs: list[str] = []
    with serve(routes(paths.chapter(ch))) as port, sync_playwright() as p:
        try:
            browser = chromium.launch(p, local_port=port)
        except Exception as e:  # noqa: BLE001
            raise UserError(f"The Chromium renderer is missing or won't start ({str(e).splitlines()[0]}). Run `doctor`.") from None
        try:
            ctx = browser.new_context(viewport={"width": config.W, "height": config.H}, device_scale_factor=1,
                                      service_workers="block")
            _local_only(ctx, port, logs)
            pg = ctx.new_page()
            pg.on("console", lambda m: logs.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
            pg.on("pageerror", lambda e: logs.append(f"PAGEERROR: {e}"))
            pg.goto(f"http://127.0.0.1:{port}/index.html?export=1")
            try:
                pg.wait_for_function("window.__ready === true", timeout=90_000)
            except Exception:  # noqa: BLE001
                raise UserError("The chapter page never finished loading:\n" + "\n".join(logs[:20])) from None
            yield pg, logs
        finally:
            browser.close()


def fail_on_errors(logs: list[str]) -> None:
    bad = [l for l in logs if l.startswith("PAGEERROR") or "asset failed" in l]
    if bad:
        raise UserError("The chapter page has errors; fix scenes.js or the asset paths:\n" + "\n".join(bad[:20]))


def grab(pg, t: float, q: float) -> bytes:
    try:
        return base64.b64decode(pg.evaluate(GRAB, [t, q]))
    except Exception as e:  # noqa: BLE001
        raise UserError(f"Drawing the frame at {t:.2f}s failed: {str(e).splitlines()[0]}") from None


def events(ch: Path) -> list[dict]:
    with page_for(ch) as (pg, logs):
        fail_on_errors(logs)
        return pg.evaluate("window.__sfx()")


def stills(ch: Path, times: list[float], cols: int = 3) -> Path:
    from PIL import Image, ImageDraw
    read_timing(ch)
    ensure_page(ch)
    b = paths.chapter(ch).build
    out = b / "stills"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    with page_for(ch) as (pg, logs):
        fail_on_errors(logs)
        files = []
        for t in times:
            f = out / f"t{t:07.2f}.jpg"
            f.write_bytes(grab(pg, t, 0.9))
            files.append(f)
        fail_on_errors(logs)
        notes = [l for l in logs if l.startswith(("warning", "error"))]
    tw, th = 640, 360
    sheet = Image.new("RGB", (cols * tw, math.ceil(len(files) / cols) * th), "white")
    d = ImageDraw.Draw(sheet)
    for i, f in enumerate(files):
        with Image.open(f) as im:
            sheet.paste(im.resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
        d.text(((i % cols) * tw + 8, (i // cols) * th + 8), f.stem, fill="yellow")
    sheet_path = b / "stills.jpg"
    sheet.save(sheet_path, quality=85)
    for line in notes[:20]:
        print(line)
    return sheet_path


def _encode(pg, logs: list[str], out: Path, fps: int, f0: int, f1: int) -> None:
    """Frames f0..f1-1 into the MP4 `out`, written under a temporary name first, so `out` exists only when whole."""
    tmp = out.with_name(out.stem + ".part.mp4")
    ff = subprocess.Popen([tools.ffmpeg(), "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg",
                           "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                           "-r", str(fps), str(tmp)], stdin=subprocess.PIPE)
    try:
        for i in range(f0, f1):
            ff.stdin.write(grab(pg, i / fps, 0.94))
    finally:
        ff.stdin.close()
        code = ff.wait()
    fail_on_errors(logs)
    if code:
        tmp.unlink(missing_ok=True)
        raise UserError(f"ffmpeg failed while encoding {out.name} (exit {code}).")
    os.replace(tmp, out)


def piece_name(i: int) -> str:
    return f"piece{i:04d}.mp4"


def video_pieces(ch: Path, folder: Path, fps: int, size: int, frames: int, pieces: list[int],
                 deadline: float | None = None) -> None:
    """Render the given pieces (`size` frames each, of `frames` in all) into `folder`, one page for all of them. With
    a deadline (time.time()), a piece starts only while it would likely end before it; the first always starts."""
    count = math.ceil(frames / size)
    with page_for(ch) as (pg, logs):
        fail_on_errors(logs)
        made, slowest = 0, 0.0
        for i in pieces:
            out = folder / piece_name(i)
            if out.exists():
                continue
            if deadline is not None and made and time.time() + slowest > deadline:
                break
            t0 = time.time()
            _encode(pg, logs, out, fps, i * size, min(frames, (i + 1) * size))
            made, slowest = made + 1, max(slowest, time.time() - t0)
            print(f"  rendered piece {i + 1}/{count}", flush=True)


def final_sheet(video: Path, sheet: Path) -> Path:
    """Four frames (15/40/65/90%) of the finished MP4, side by side in a 2x2 grid."""
    dur = tools.duration(video)
    picks = [sheet.with_name(f"final-{k}.jpg") for k in range(4)]
    for k, f in enumerate(picks):
        run(tools.ffmpeg(), "-v", "error", "-y", "-ss", f"{dur * (0.15 + 0.25 * k):.2f}", "-i", video,
            "-frames:v", "1", "-vf", "scale=960:-2", f)
    run(tools.ffmpeg(), "-v", "error", "-y", *[a for f in picks for a in ("-i", f)],
        "-filter_complex", "[0][1]hstack[t];[2][3]hstack[b];[t][b]vstack", sheet)
    for f in picks:
        f.unlink(missing_ok=True)
    return sheet


def default_workers() -> int:
    return max(1, min(4, (os.cpu_count() or 2) // 2))


FINISH_SECONDS = 30   # kept free at the end of a timed render for joining the pieces, the sound and the checks


def _inputs_key(p: paths.ChapterPaths, fps: int, frames: int, size: int) -> str:
    """A fingerprint of everything the frames are drawn from (the page, scenes.js, timing, engine, assets, fonts) and
    how they are cut into pieces. Pieces rendered under another fingerprint are stale."""
    h = hashlib.sha1(f"pieces 1|{fps}|{frames}|{size}|{config.W}x{config.H}".encode())
    files = {p.build / "timing.js", p.build / "engine.js", p.build / "index.html"}
    files |= {f for f in p.code.iterdir() if f.is_file()}
    for f in sorted(files):
        if f.is_file():
            h.update(f"{f.name}|".encode() + hashlib.sha1(f.read_bytes()).digest())
    for root in (p.assets, config.FONTS_DIR):
        if root.is_dir():
            for f in sorted(root.rglob("*")):
                if f.is_file():
                    st = f.stat()
                    h.update(f"{f.relative_to(root).as_posix()}|{st.st_size}|{st.st_mtime_ns}".encode())
    return h.hexdigest()


def _pieces_folder(p: paths.ChapterPaths, key: str) -> Path:
    """build/pieces, emptied when what it holds was rendered from other inputs."""
    folder = p.build / "pieces"
    stamp = folder / "inputs.txt"
    if not stamp.is_file() or stamp.read_text(encoding="utf-8") != key:
        shutil.rmtree(folder, ignore_errors=True)
        write_text(stamp, key)
    return folder


def render(ch: Path, workers: int | None = None, fps: int = config.FPS, out_dir: Path | None = None,
           seconds: float | None = None) -> Path:
    """Render the chapter in pieces of config.RENDER_PIECE_SECONDS, kept in build/pieces until the video is made.
    With `seconds`, stop starting pieces once they would end after that many seconds (less FINISH_SECONDS) and raise
    NotFinished if pieces are left: running it again renders only the rest, unless an input changed in between."""
    started = time.time()
    p = paths.chapter(ch)
    spec = read_json(p.code / "script.json")
    T = read_timing(ch)
    ensure_page(ch)
    b = p.build
    write_json(b / "sfx.json", events(ch))
    n = round(T["duration"] * fps)
    size = max(1, round(config.RENDER_PIECE_SECONDS * fps))
    count = math.ceil(n / size)
    folder = _pieces_folder(p, _inputs_key(p, fps, n, size))
    todo = [i for i in range(count) if not (folder / piece_name(i)).exists()]
    if todo:
        workers = max(1, min(workers or default_workers(), len(todo)))
        deadline = 0.0 if seconds is None else started + seconds - FINISH_SECONDS
        procs = [subprocess.Popen([sys.executable, str(config.ENTRY), "_part", str(ch), str(folder), str(fps), str(size),
                                   str(n), repr(deadline), *map(str, todo[w::workers])]) for w in range(workers)]
        codes = [pr.wait() for pr in procs]
        if any(codes):
            raise UserError(f"Rendering failed in {sum(1 for c in codes if c)} of {len(codes)} worker(s); see the messages above.")
        left = [i for i in todo if not (folder / piece_name(i)).exists()]
        if left:
            raise NotFinished(f"Rendering isn't finished: {count - len(left)} of {count} pieces of the video are done, "
                              f"{len(left)} left. Run the same render command again to carry on (finished pieces are "
                              "kept).")
    lst = write_text(folder / "pieces.txt", "".join(f"file '{piece_name(i)}'\n" for i in range(count)))
    run(tools.ffmpeg(), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", b / "video.mp4")
    sfx.build()  # no-op when the library exists; rebuilds it if ~/.slide2video was cleared
    audio = mix.mix_audio(ch, T, spec)
    out = output_path(ch, spec, out_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    run(tools.ffmpeg(), "-v", "error", "-y", "-i", b / "video.mp4", "-i", audio, "-c:v", "copy", "-c:a", "copy",
        "-map", "0:v", "-map", "1:a", "-shortest", "-movflags", "+faststart", out)
    write_text(out.with_suffix(".vtt"), captions.vtt(T))
    if out_dir is None:  # a check render elsewhere doesn't count as the chapter's video
        status.mark_rendered(ch, out)
    shutil.rmtree(folder, ignore_errors=True)
    print(f"wrote {out} ({tools.duration(out):.1f}s; narration {T['duration']:.1f}s)")
    print(f"frames from the finished video: {final_sheet(out, b / 'final.jpg')}")
    return out
