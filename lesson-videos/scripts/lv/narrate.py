"""Narration: one ElevenLabs take per scene (cached by text), word timings, the narration track."""
from __future__ import annotations

import base64
import concurrent.futures as cf
import hashlib
import json
from pathlib import Path

from . import config, keys, net, tools
from .util import UserError, read_json, read_text, run, write_json, write_text


def cache_key(voice: str, say: str) -> str:
    raw = f"{voice}|{config.ELEVEN_MODEL}|{json.dumps(config.VOICE_SETTINGS)}|{say}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def words_from(al: dict) -> list[dict]:
    words, cur, s, e = [], "", None, None
    for ch, cs, ce in zip(al["chars"], al["starts"], al["ends"]):
        if ch.isspace():
            if cur:
                words.append({"w": cur, "s": round(s, 3), "e": round(e, 3)})
            cur, s = "", None
            continue
        if s is None:
            s = cs
        cur += ch
        e = ce
    if cur:
        words.append({"w": cur, "s": round(s, 3), "e": round(e, 3)})
    return words


def speak(text: str, voice: str, out: Path) -> None:
    body = {"text": text, "model_id": config.ELEVEN_MODEL, "voice_settings": config.VOICE_SETTINGS}
    url = f"{config.ELEVEN_ROOT}/text-to-speech/{voice}/with-timestamps?output_format={config.ELEVEN_FORMAT}"
    d = net.request(url, data=body, headers={"xi-api-key": keys.get("ELEVENLABS_API_KEY")}, timeout=180)
    a = d.get("alignment") or {}
    write_json(out.with_suffix(".json"), {"chars": a.get("characters", []), "starts": a.get("character_start_times_seconds", []),
                                          "ends": a.get("character_end_times_seconds", [])})
    out.write_bytes(base64.b64decode(d["audio_base64"]))  # the mp3 is the cache marker, so it is written last


def build_timing(spec: dict, takes: dict) -> dict:
    """Pure: scenes + {id: (speech_seconds, words, audio_relpath)} -> timing dict."""
    t, out = 0.0, []
    for sc in spec["scenes"]:
        lead, tail, hold = sc.get("lead", 0.5), sc.get("tail", 0.7), sc.get("hold", 0)
        speech, words, audio = takes.get(sc["id"], (0.0, [], None))
        words = [{**w, "s": round(w["s"] + lead, 3), "e": round(w["e"] + lead, 3)} for w in words]
        dur = max(sc.get("min", 0), lead + speech + tail + hold)
        out.append({"id": sc["id"], "start": round(t, 3), "dur": round(dur, 3), "lead": lead,
                    "speech": round(speech, 3), "words": words, "audio": audio})
        t += dur
    return {"chapter": spec.get("chapter", ""), "title": spec.get("title", ""), "duration": round(t, 3), "scenes": out}


def narration_error(e: net.ApiError, done: int, total: int) -> str:
    msg = (f"Narration stopped after {done} of {total} new scenes ({e.host} said {e.status}). "
           "Finished scenes are saved and won't be paid for again.")
    d = e.detail.lower()
    if "quota" in d or e.status == 402:
        msg += (" Your ElevenLabs credits for this month are used up: run `keys check` to see what's left, "
                "or upgrade the plan, then run `narrate` again.")
    elif e.status == 401:
        msg += " The ElevenLabs key was rejected or can't use Text to Speech: run `keys check`."
    elif e.status == 429:
        msg += " ElevenLabs is limiting requests: wait a minute and run `narrate` again."
    else:
        msg += f" Details: {e.detail[:200]}"
    return msg


def narrate(ch: Path, speak_fn=speak, workers: int = config.NARRATION_WORKERS) -> dict:
    spec = read_json(ch / "script.json")
    voice = spec.get("voice", config.DEFAULT_VOICE)
    vd = ch / "build" / "voice"
    vd.mkdir(parents=True, exist_ok=True)
    files, jobs = {}, []
    for sc in spec["scenes"]:
        say = sc.get("say", "").strip()
        if not say:
            continue
        f = vd / f"{sc['id']}-{cache_key(voice, say)}.mp3"
        files[sc["id"]] = f
        if not f.exists():
            jobs.append((say, f))
    if jobs and speak_fn is speak:
        keys.get("ELEVENLABS_API_KEY")  # fail early with the friendly message
    done = 0
    try:
        with cf.ThreadPoolExecutor(workers) as ex:
            for fu in cf.as_completed([ex.submit(speak_fn, say, voice, f) for say, f in jobs]):
                fu.result()
                done += 1
                print(f"  voiced {done}/{len(jobs)}", flush=True)
    except net.ApiError as e:
        raise UserError(narration_error(e, done, len(jobs))) from None
    takes = {sid: (tools.duration(f), words_from(read_json(f.with_suffix(".json"))), f.relative_to(ch).as_posix())
             for sid, f in files.items()}
    T = build_timing(spec, takes)
    write_text(ch / "build" / "timing.js", "window.TIMING = " + json.dumps(T) + ";\n")
    narration_track(ch, T)
    return T


def read_timing(ch: Path) -> dict:
    f = ch / "build" / "timing.js"
    if not f.exists():
        raise UserError(f"{ch.name}: no narration yet. Run `narrate` first.")
    return json.loads(read_text(f).split("=", 1)[1].strip().rstrip(";"))


def narration_track(ch: Path, T: dict) -> Path:
    out = ch / "build" / "narration.mp3"
    total = T["duration"]
    voiced = [s for s in T["scenes"] if s["audio"]]
    if not voiced:
        run(tools.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", total, "-b:a", "192k", out)
        return out
    ins, flt = [], []
    for i, s in enumerate(voiced):
        ins += ["-i", str(ch / s["audio"])]
        ms = int((s["start"] + s["lead"]) * 1000)
        flt.append(f"[{i}:a]adelay={ms}|{ms},aformat=channel_layouts=stereo[a{i}]")
    flt.append("".join(f"[a{i}]" for i in range(len(voiced))) + f"amix=inputs={len(voiced)}:normalize=0,apad=whole_dur={total}[out]")
    run(tools.ffmpeg(), "-v", "error", "-y", *ins, "-filter_complex", ";".join(flt), "-map", "[out]", "-t", total,
        "-ar", 44100, "-b:a", "192k", out)
    return out
