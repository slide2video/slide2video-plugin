"""WebVTT captions from narration word timings, split the same way as the on-screen captions."""
from __future__ import annotations

import re

SENTENCE_END = re.compile(r"[.!?][\"”']?$")


def segments(T: dict) -> list[tuple[float, float, str]]:
    out = []
    for sc in T["scenes"]:
        cur = []
        for w in sc.get("words") or []:
            cur.append(w)
            if SENTENCE_END.search(w["w"]) or len(cur) >= 16:
                out.append((round(sc["start"] + cur[0]["s"], 3), round(sc["start"] + cur[-1]["e"], 3), " ".join(x["w"] for x in cur)))
                cur = []
        if cur:
            out.append((round(sc["start"] + cur[0]["s"], 3), round(sc["start"] + cur[-1]["e"], 3), " ".join(x["w"] for x in cur)))
    return out


def stamp(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def vtt(T: dict) -> str:
    lines = ["WEBVTT", ""]
    for i, (s, e, text) in enumerate(segments(T), 1):
        lines += [str(i), f"{stamp(s)} --> {stamp(e + 0.35)}", text, ""]
    return "\n".join(lines)
