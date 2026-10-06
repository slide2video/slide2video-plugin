"""Veo image-to-video clips from deck photos, and their JPEG frames for the engine's clip()."""
from __future__ import annotations

import base64
import io
import time
from pathlib import Path

from . import config, keys, net, tools
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


def result_uri(op: dict) -> str:
    if op.get("error"):
        raise UserError(f"Veo failed: {op['error'].get('message', 'no reason given')}")
    resp = (op.get("response") or {}).get("generateVideoResponse") or {}
    samples = resp.get("generatedSamples") or []
    if not samples:
        if resp.get("raiMediaFilteredCount") or resp.get("raiMediaFilteredReasons"):
            reasons = "; ".join(resp.get("raiMediaFilteredReasons") or []) or "no reason given"
            raise UserError(f"Veo's safety filter dropped the clip ({reasons}). Try another photo or prompt (photos of children are often refused).")
        raise UserError("Veo finished without a video and without a reason; try again.")
    uri = (samples[0].get("video") or {}).get("uri")
    if not uri:
        raise UserError("Veo finished without a video link; try again.")
    return uri


def veo(image_png: bytes, prompt: str, request=None, sleep=time.sleep, max_polls: int = 60) -> bytes:
    request = request or net.request
    h = {"x-goog-api-key": keys.get("GEMINI_API_KEY")}
    payload = {"instances": [{"prompt": prompt, "image": {"bytesBase64Encoded": base64.b64encode(image_png).decode("ascii"),
                                                          "mimeType": "image/png"}}],
               "parameters": {"aspectRatio": "16:9", "durationSeconds": config.VEO_SECONDS, "resolution": "720p",
                              "personGeneration": "allow_adult"}}
    try:
        op = request(f"{config.GEMINI_ROOT}/models/{config.VEO_MODEL}:predictLongRunning", data=payload, headers=h, timeout=60)
        name = op.get("name") or ""
        if not name:
            raise UserError("Veo didn't start the job; try again.")
        for _ in range(max_polls):
            sleep(10)
            op = request(f"{config.GEMINI_ROOT}/{name}", headers=h, timeout=60)
            if op.get("done"):
                return request(result_uri(op), headers=h, timeout=300, raw=True)
    except net.ApiError as e:
        raise net.gemini_error(e, "AI clip") from None
    raise UserError(f"Veo was still working after {max_polls * 10 // 60} minutes; try again later.")


def make_clip(image: Path, prompt: str, name: str, work: Path, frac: float = 0.5, request=None, sleep=time.sleep,
              strip: bool = True) -> Path:
    out = Path(work) / "clips" / f"{name}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(veo(prep(image, frac), prompt, request=request, sleep=sleep))
    write_text(out.with_suffix(".txt"), f"source: {Path(image).name}\nprompt: {prompt}\n")
    if strip:  # one frame per second, side by side, to check the subject doesn't drift
        run(tools.ffmpeg(), "-v", "error", "-y", "-i", out, "-vf", "fps=1,scale=320:-2,tile=8x1", "-frames:v", "1",
            out.with_name(f"{name}-strip.jpg"))
    print(f"clip {out} (~${config.VEO_SECONDS * config.VEO_PRICE_PER_SECOND:.2f})")
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
