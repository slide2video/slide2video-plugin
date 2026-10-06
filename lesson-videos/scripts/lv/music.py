"""One Lyria track used as a looped, ducked music bed under the narration."""
from __future__ import annotations

import base64
from pathlib import Path

from . import config, keys, net
from .util import UserError, write_text


def make_bed(work: Path, prompt: str, request=None) -> Path:
    request = request or net.request
    key = keys.get("GEMINI_API_KEY")
    try:
        d = request(f"{config.GEMINI_ROOT}/interactions",
                    data={"model": config.LYRIA_MODEL, "input": prompt, "response_format": {"type": "audio"}},
                    headers={"x-goog-api-key": key}, timeout=300)
    except net.ApiError as e:
        raise net.gemini_error(e, "music") from None
    for step in d.get("steps") or []:
        for block in step.get("content") or []:
            if block.get("type") == "audio" and block.get("data"):
                out = Path(work) / "music" / "bed.mp3"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(base64.b64decode(block["data"]))
                write_text(out.with_suffix(".txt"), prompt)
                return out
    raise UserError(f"Lyria returned no audio (status {d.get('status')!r}); try a simpler prompt.")
