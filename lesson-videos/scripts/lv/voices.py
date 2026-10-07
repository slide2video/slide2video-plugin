"""Narration voices, best first: ElevenLabs (needs a key), the free Microsoft Edge voice (online, no account),
this computer's own voice (offline), and captions only (silent). A chapter always gets the first one that works."""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import config, keys, tools
from .util import UserError, run, write_text

ORDER = ("elevenlabs", "edge", "system", "none")
LABELS = {
    "elevenlabs": "ElevenLabs",
    "edge": "the free Microsoft voice",
    "system": "this computer's own voice",
    "none": "captions only (no voice)",
}
WORDS_PER_SECOND = 2.5  # captions-only reading pace (150 words a minute)


class VoiceUnavailable(RuntimeError):
    """This voice can't be used right now; narrate() moves on to the next one."""


def chain(spec: dict) -> list[str]:
    choice = spec.get("narrator", "auto")
    if choice == "auto":
        return list(ORDER) if keys.get("ELEVENLABS_API_KEY", required=False) else list(ORDER[1:])
    if choice == "elevenlabs":
        return ["elevenlabs"]  # chosen on purpose: report its errors instead of swapping voices
    if choice in ORDER:
        return list(ORDER[ORDER.index(choice):])
    raise UserError(f'script.json "narrator" must be one of: auto, {", ".join(ORDER)}.')


def voice_for(provider: str, spec: dict) -> str:
    return {"elevenlabs": spec.get("voice", config.DEFAULT_VOICE), "edge": spec.get("edge_voice", config.EDGE_VOICE),
            "system": spec.get("system_voice", "")}.get(provider, "")


def cache_key(provider: str, voice: str, say: str) -> str:
    return hashlib.sha1(f"{provider}|{sys.platform if provider == 'system' else ''}|{voice}|{say}".encode()).hexdigest()[:12]


def reading_time(say: str) -> float:
    return max(1.5, len(say.split()) / WORDS_PER_SECOND)


def plausible_take(seconds: float, text: str) -> bool:
    """False for audio far too short to hold the text (e.g. a machine with no speech voices installed)."""
    return seconds >= max(0.3, 0.12 * len(text.split()))


def _norm(s: str) -> str:
    return re.sub(r"\W+", "", s.lower())


def estimate_words(text: str, duration: float, lead: float = 0.05) -> list[dict]:
    """Spread the script's words over a take by length, with pauses after commas and sentence ends."""
    toks = text.split()
    if not toks:
        return []
    weights = []
    for t in toks:
        w = len(t) + 1
        if t.rstrip("\"'”’)").endswith((",", ";", ":")):
            w += 3
        if t.rstrip("\"'”’)").endswith((".", "!", "?")):
            w += 6
        weights.append(w)
    unit = max(0.1, duration - lead) / sum(weights)
    t0, out = lead, []
    for tok, w in zip(toks, weights):
        out.append({"w": tok, "s": round(t0, 3), "e": round(t0 + (len(tok) + 0.5) * unit, 3)})
        t0 += w * unit
    return out


def align_events(text: str, events: list[tuple[float, float, str]]) -> list[dict] | None:
    """Give the script's own words (with punctuation) the timings of the voice's word events, or None if they disagree."""
    toks, out, i = text.split(), [], 0
    for start, dur, said in events:
        target = _norm(said)
        if not target:
            continue
        group, acc = [], ""
        while i < len(toks) and len(acc) < len(target):
            group.append(toks[i])
            acc += _norm(toks[i])
            i += 1
        if acc != target:
            return None
        weights = [max(1, len(_norm(t))) for t in group]
        t0 = start
        for tok, w in zip(group, weights):
            span = dur * w / sum(weights)
            out.append({"w": tok, "s": round(t0, 3), "e": round(t0 + span, 3)})
            t0 += span
    if any(_norm(t) for t in toks[i:]):
        return None
    return out


def speak_edge(text: str, voice: str, out: Path) -> list[dict]:
    """Microsoft Edge's free online voices (unofficial endpoint, no account), with real word timings."""
    import edge_tts

    async def go():
        com = edge_tts.Communicate(text, voice, boundary="WordBoundary")
        audio, events = bytearray(), []
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
            elif chunk["type"] == "WordBoundary":
                events.append((chunk["offset"] / 1e7, chunk["duration"] / 1e7, chunk["text"]))
        return bytes(audio), events

    last = "no answer"
    for attempt in range(3):
        try:
            audio, events = asyncio.run(go())
            if audio:
                out.write_bytes(audio)
                seconds = tools.duration(out)
                if plausible_take(seconds, text):
                    return align_events(text, events) or estimate_words(text, seconds)
                last = f"only {seconds:.2f}s of audio came back"
            last = "no audio received"
        except Exception as e:  # noqa: BLE001  blocked network, service change, rate limit
            last = f"{e.__class__.__name__}: {str(e)[:160]}"
        time.sleep(2 * (attempt + 1))
    raise VoiceUnavailable(f"the free Microsoft voice didn't answer ({last})")


_PS1 = r"""param([string]$TextFile, [string]$WavFile)
Add-Type -AssemblyName System.Speech
$text = [System.IO.File]::ReadAllText($TextFile, [System.Text.Encoding]::UTF8)
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try { $s.SetOutputToWaveFile($WavFile); $s.Speak($text) } finally { $s.Dispose() }
"""


def speak_system(text: str, voice: str, out: Path) -> list[dict]:
    """The computer's built-in voice: `say` on macOS, System.Speech on Windows, espeak on Linux. Offline."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        txt = write_text(d / "say.txt", text)
        if sys.platform == "darwin":
            raw = d / "say.aiff"
            cmd = ["say", "-f", str(txt), "-o", str(raw)] + (["-v", voice] if voice else [])
        elif os.name == "nt":
            raw = d / "say.wav"
            ps1 = write_text(d / "say.ps1", _PS1)
            cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(ps1), str(txt), str(raw)]
        else:
            exe = shutil.which("espeak-ng") or shutil.which("espeak")
            if not exe:
                raise VoiceUnavailable("this computer has no built-in voice (install espeak-ng)")
            raw = d / "say.wav"
            cmd = [exe, "-f", str(txt), "-w", str(raw)] + (["-v", voice] if voice else [])
        try:
            r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=300)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise VoiceUnavailable(f"this computer's voice failed ({e})") from None
        if r.returncode or not raw.exists() or raw.stat().st_size < 1000:
            raise VoiceUnavailable(f"this computer's voice failed ({(r.stderr or r.stdout).strip()[:160]})")
        run(tools.ffmpeg(), "-v", "error", "-y", "-i", raw, "-ac", "1", "-b:a", "128k", out)
    seconds = tools.duration(out)
    if not plausible_take(seconds, text):
        raise VoiceUnavailable(f"this computer's voice produced only {seconds:.2f}s of audio (no speech voice installed?)")
    return estimate_words(text, seconds)


SPEAKERS = {"edge": speak_edge, "system": speak_system}


def probe(provider: str) -> None:
    """Raise VoiceUnavailable if this voice can't speak a test sentence right now."""
    with tempfile.TemporaryDirectory() as d:
        SPEAKERS[provider]("Testing the narrator voice for lesson videos.", voice_for(provider, {}), Path(d) / "probe.mp3")
