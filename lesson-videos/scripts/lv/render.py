"""Serve a chapter folder, seek the page frame by frame in headless Chromium, pipe JPEGs into ffmpeg."""
from __future__ import annotations

import base64
import functools
import http.server
import math
import os
import shutil
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

from . import captions, config, mix, tools
from .narrate import read_timing
from .page import ensure_page, output_path
from .util import UserError, read_json, run, write_json, write_text

GRAB = """async ([t, q]) => {
  window.__render(t);
  if (Engine.pending) { await Engine.waitLoads(); window.__render(t); }
  return document.getElementById('c').toDataURL('image/jpeg', q).split(',')[1];
}"""


class _Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".js": "text/javascript", ".html": "text/html", ".ttf": "font/ttf", ".jpg": "image/jpeg",
                      ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".mp3": "audio/mpeg",
                      ".json": "application/json", ".svg": "image/svg+xml"}

    def log_message(self, *args):
        pass


@contextmanager
def serve(root: Path):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Handler, directory=str(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield srv.server_address[1]
    finally:
        srv.shutdown()
        srv.server_close()


@contextmanager
def page_for(ch: Path):
    from playwright.sync_api import sync_playwright
    logs: list[str] = []
    with serve(ch) as port, sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=["--use-gl=angle", "--enable-gpu-rasterization", "--ignore-gpu-blocklist"])
        except Exception as e:  # noqa: BLE001
            raise UserError(f"The Chromium renderer is missing or won't start ({str(e).splitlines()[0]}). Run `doctor`.") from None
        try:
            pg = browser.new_page(viewport={"width": config.W, "height": config.H}, device_scale_factor=1)
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
    out = ch / "build" / "stills"
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
        warnings = [l for l in logs if l.startswith("warning")]
    tw, th = 640, 360
    sheet = Image.new("RGB", (cols * tw, math.ceil(len(files) / cols) * th), "white")
    d = ImageDraw.Draw(sheet)
    for i, f in enumerate(files):
        with Image.open(f) as im:
            sheet.paste(im.resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
        d.text(((i % cols) * tw + 8, (i // cols) * th + 8), f.stem, fill="yellow")
    p = ch / "build" / "stills.jpg"
    sheet.save(p, quality=85)
    for w in warnings[:20]:
        print(w)
    return p


def video_part(ch: Path, out: Path, fps: int, f0: int, f1: int) -> None:
    with page_for(ch) as (pg, logs):
        fail_on_errors(logs)
        ff = subprocess.Popen([tools.ffmpeg(), "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg",
                               "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                               "-r", str(fps), str(out)], stdin=subprocess.PIPE)
        try:
            for i in range(f0, f1):
                ff.stdin.write(grab(pg, i / fps, 0.94))
                if (i - f0) % 600 == 0:
                    print(f"  [{out.name}] frame {i - f0}/{f1 - f0}", file=sys.stderr, flush=True)
        finally:
            ff.stdin.close()
            code = ff.wait()
        fail_on_errors(logs)
    if code:
        raise UserError(f"ffmpeg failed while encoding {out.name} (exit {code}).")


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


def render(ch: Path, workers: int | None = None, fps: int = config.FPS, out_dir: Path | None = None) -> Path:
    spec = read_json(ch / "script.json")
    T = read_timing(ch)
    ensure_page(ch)
    b = ch / "build"
    write_json(b / "sfx.json", events(ch))
    n = round(T["duration"] * fps)
    workers = workers or default_workers()
    seg = math.ceil(n / workers)
    parts, procs = [], []
    for w in range(workers):
        f0, f1 = w * seg, min(n, (w + 1) * seg)
        if f0 >= f1:
            continue
        p = b / f"part{w}.mp4"
        parts.append(p)
        procs.append(subprocess.Popen([sys.executable, str(config.ENTRY), "_part", str(ch), str(p), str(fps), str(f0), str(f1)]))
    codes = [p.wait() for p in procs]
    if any(codes):
        raise UserError(f"Rendering failed in {sum(1 for c in codes if c)} of {len(codes)} worker(s); see the messages above.")
    lst = write_text(b / "parts.txt", "".join(f"file '{p.name}'\n" for p in parts))
    run(tools.ffmpeg(), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", b / "video.mp4")
    audio = mix.mix_audio(ch, T, spec)
    out = output_path(ch, spec, out_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    run(tools.ffmpeg(), "-v", "error", "-y", "-i", b / "video.mp4", "-i", audio, "-c:v", "copy", "-c:a", "copy",
        "-map", "0:v", "-map", "1:a", "-shortest", "-movflags", "+faststart", out)
    write_text(out.with_suffix(".vtt"), captions.vtt(T))
    for p in parts:
        p.unlink(missing_ok=True)
    print(f"wrote {out} ({tools.duration(out):.1f}s; narration {T['duration']:.1f}s)")
    print(f"frames from the finished video: {final_sheet(out, b / 'final.jpg')}")
    return out
