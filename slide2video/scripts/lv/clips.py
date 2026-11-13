"""AI image-to-video clips from deck photos (Gemini Omni Flash), and their JPEG frames for the engine's clip()."""
from __future__ import annotations

import base64
import io
import os
from pathlib import Path

from . import config, keys, net, paths, tools
from .util import UserError, run, write_text


def prep(image: Path, frac: float = 0.5) -> bytes:
    """Crop to 16:9 (frac picks the vertical position, 0 = top) and resize to 1280x720 PNG."""
    from PIL import Image, ImageOps
    with Image.open(image) as src:
        im = ImageOps.exif_transpose(src).convert("RGB")
    w, h = im.size
    th = round(w * 9 / 16)
    if th <= h:
        top = int((h - th) * frac)
        im = im.crop((0, top, w, top + th))
    else:
        tw = round(h * 16 / 9)
        left = (w - tw) // 2
        im = im.crop((left, 0, left + tw, h))
    b = io.BytesIO()
    im.resize((1280, 720), Image.LANCZOS).save(b, "PNG")
    return b.getvalue()


def video_of(resp: dict) -> bytes:
    """The clip in an Interactions answer (a `video` part of a `model_output` step, inline), or why there is none."""
    texts = []
    for step in resp.get("steps") or []:
        for part in (step.get("content") or []) if isinstance(step, dict) else []:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "video" and part.get("data"):
                return base64.b64decode(part["data"])
            if part.get("type") == "text" and isinstance(part.get("text"), str) and step.get("type") == "model_output":
                texts.append(part["text"].strip())
    said = " ".join(t for t in texts if t)[:300]
    raise UserError("The video model made no clip" + (f": {said}" if said else f" (status: {resp.get('status') or 'none'})")
                    + ". Try another photo or prompt (photos of people, and of children above all, are often refused).")


class NotBilled(UserError):
    """The clip service refused the call (a 4xx answer): no clip was made or billed."""


def omni(image_png: bytes, prompt: str, request=None) -> bytes:
    """One 10-second 720p 16:9 clip from the photo: Gemini Omni Flash through the Interactions API, answered at once
    (no polling) with the video inline."""
    request = request or net.request
    h = {"x-goog-api-key": keys.get("GEMINI_API_KEY")}
    payload = {"model": config.CLIP_MODEL,
               "input": [{"type": "image", "data": base64.b64encode(image_png).decode("ascii"), "mime_type": "image/png"},
                         {"type": "text", "text": prompt}],
               "generation_config": {"video_config": {"task": "image_to_video"}},
               "response_format": {"type": "video", "resolution": "720p", "aspect_ratio": "16:9"},
               "background": False, "store": False, "stream": False}
    try:
        resp = request(f"{config.gemini_root()}/interactions", data=payload, headers=h, timeout=900, retries=0)
    except net.ApiError as e:
        err = net.gemini_error(e, "AI clip")
        # only a refusal (4xx) surely billed nothing; a server error (5xx) or no answer at all (status 0: a timeout, a
        # dropped connection) may come after the work was done, so it keeps its place
        raise (NotBilled(str(err)) if 400 <= e.status < 500 else err) from None
    return video_of(resp)


def check_name(name: str) -> str:
    """A clip name is one plain file name inside _work/clips/."""
    if not name or "/" in name or "\\" in name or ".." in name or name.startswith("."):
        raise UserError(f"The clip name {name!r} can't be used: give a plain name such as `river`, without "
                        "slashes, `..` or a leading dot.")
    return name


def reserve_place(ledger: Path, limit: int) -> Path:
    """Takes one of a step's `limit` clip places in `ledger` (a folder the worker made outside the lesson, where Claude
    can't write): the first place file that can be created exclusively, so clip commands started together never take
    the same place, and deleting, renaming or moving a finished clip gives nothing back. UserError when none is left."""
    ledger.mkdir(parents=True, exist_ok=True)
    for i in range(limit):
        place = ledger / f"clip-{i + 1}"
        try:
            os.close(os.open(place, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return place
        except FileExistsError:
            continue
    raise UserError(f"This video project may have at most {limit} AI clip{'' if limit == 1 else 's'}, and this step "
                    "has asked for them all: make the chapters without more.")


def make_clip(image: Path, prompt: str, name: str, work: Path, frac: float = 0.5, request=None, strip: bool = True,
              place: Path | None = None) -> Path:
    """One clip into the lesson's clips folder. With `place` (reserve_place), the place is given back only when the
    clip can't have been billed: the photo couldn't be prepared, there is no key, or the service refused the call
    (4xx)."""
    check_name(name)
    out = paths.lesson(work).sources / "clips" / f"{name}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    png = None
    try:
        png = prep(image, frac)
        video = omni(png, prompt, request=request)
    except BaseException as e:
        if place is not None and (png is None or isinstance(e, (NotBilled, keys.MissingKey))):
            place.unlink(missing_ok=True)
        raise
    out.write_bytes(video)
    write_text(out.with_suffix(".txt"), f"source: {Path(image).name}\nprompt: {prompt}\n")
    if strip:  # one frame per second, side by side, to check the subject doesn't drift
        run(tools.ffmpeg(), "-v", "error", "-y", "-i", out, "-vf", "fps=1,scale=320:-2,tile=8x1", "-frames:v", "1",
            out.with_name(f"{name}-strip.jpg"))
    print(f"clip {out} (~${config.CLIP_PRICE:.2f})")
    return out


def frames(mp4: Path, dest: Path, max_frames: int | None = None) -> int:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("*.jpg"):
        old.unlink()
    args = [tools.ffmpeg(), "-v", "error", "-y", "-i", mp4, "-vf", "fps=24,scale=1280:-2", "-q:v", "3"]
    if max_frames:
        args += ["-frames:v", max_frames]
    run(*args, dest / "%04d.jpg")
    return len(list(dest.glob("*.jpg")))
