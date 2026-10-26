"""AI image-to-video clips from deck photos (Gemini Omni Flash), and their JPEG frames for the engine's clip()."""
from __future__ import annotations

import base64
import io
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
        raise net.gemini_error(e, "AI clip") from None
    return video_of(resp)


def check_name(name: str) -> str:
    """A clip name is one plain file name inside _work/clips/."""
    if not name or "/" in name or "\\" in name or ".." in name or name.startswith("."):
        raise UserError(f"The clip name {name!r} can't be used: give a plain name such as `river`, without "
                        "slashes, `..` or a leading dot.")
    return name


def make_clip(image: Path, prompt: str, name: str, work: Path, frac: float = 0.5, request=None, strip: bool = True) -> Path:
    check_name(name)
    out = paths.lesson(work).sources / "clips" / f"{name}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(omni(prep(image, frac), prompt, request=request))
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
