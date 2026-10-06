"""Cost estimates shown at the plan gate, before anything is paid for."""
from __future__ import annotations

from pathlib import Path

from . import config
from .util import read_json


def chars_in_scripts(work: Path) -> int:
    return sum(len(sc.get("say", "").strip()) for f in Path(work).glob("*/script.json") for sc in read_json(f).get("scenes", []))


def plan_chars(chapters: int, minutes: float) -> int:
    return int(chapters * minutes * config.CHARS_PER_MINUTE)


def gemini_usd(clips: int, music: bool) -> float:
    return round(clips * config.VEO_SECONDS * config.VEO_PRICE_PER_SECOND + (config.LYRIA_PRICE if music else 0), 2)


def report(chars: int, clips: int, music: bool, paid_voice: bool = True) -> str:
    clip_usd = config.VEO_SECONDS * config.VEO_PRICE_PER_SECOND
    lines = [
        f"Narration: about {chars:,} ElevenLabs characters (Free plan: 10,000 a month; Starter: 30,000 a month). "
        "Allow about 20% extra for re-recorded scenes." if paid_voice else
        "Narration: free voice, $0.00 (no ElevenLabs key is set).",
        f"Gemini: about ${gemini_usd(clips, music):.2f} ({clips} AI clip(s) at ${clip_usd:.2f} each"
        + (f", plus music ${config.LYRIA_PRICE:.2f})." if music else ", no music)."),
    ]
    return "\n".join(lines)
