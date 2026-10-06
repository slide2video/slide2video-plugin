"""Final audio: narration + ducked music bed + sound effects, loudness-normalized."""
from __future__ import annotations

from pathlib import Path

from . import sfx, tools
from .util import read_json, run


def mix_audio(ch: Path, T: dict, spec: dict) -> Path:
    b = ch / "build"
    total = T["duration"]
    events = read_json(b / "sfx.json") if (b / "sfx.json").exists() else []
    ins = ["-i", str(b / "narration.mp3")]
    flt = ["[0:a]aformat=channel_layouts=stereo,asplit=2[nar][key]"]
    mixes = ["[nar]"]
    idx = 1
    music = spec.get("music")
    mp = (ch / music).resolve() if music else None
    if mp and not mp.exists():
        print(f"note: music file {music} not found; mixing without music")
        mp = None
    if mp:
        ins += ["-stream_loop", "-1", "-i", str(mp)]
        flt.append(f"[{idx}:a]aformat=channel_layouts=stereo,volume={spec.get('music_db', -24)}dB,atrim=0:{total},"
                   f"afade=t=in:d=2,afade=t=out:st={max(0, total - 3)}:d=3[bed]")
        flt.append("[bed][key]sidechaincompress=threshold=0.04:ratio=6:attack=20:release=400[duck]")
        mixes.append("[duck]")
        idx += 1
    else:
        flt[0] = "[0:a]aformat=channel_layouts=stereo[nar]"
    groups: dict[str, list[dict]] = {}
    for e in events:
        groups.setdefault(e["name"], []).append(e)
    missing = []
    for name, es in groups.items():
        f = sfx.sfx_dir() / f"{name}.wav"
        if not f.exists():
            missing.append(name)
            continue
        ins += ["-i", str(f)]
        labels = [f"s{idx}x{k}" for k in range(len(es))]
        flt.append(f"[{idx}:a]aformat=channel_layouts=stereo:sample_rates=44100,asplit={len(es)}" + "".join(f"[{l}i]" for l in labels))
        for l, e in zip(labels, es):
            ms = max(0, int(e["t"] * 1000))
            flt.append(f"[{l}i]volume={e.get('gain', -8)}dB,adelay={ms}|{ms}[{l}]")
            mixes.append(f"[{l}]")
        idx += 1
    if missing:
        print("note: unknown sound effects skipped: " + ", ".join(sorted(missing)))
    flt.append("".join(mixes) + f"amix=inputs={len(mixes)}:normalize=0:duration=first,loudnorm=I=-16:TP=-1.5:LRA=11[out]")
    out = b / "mix.m4a"
    run(tools.ffmpeg(), "-v", "error", "-y", *ins, "-filter_complex", ";".join(flt), "-map", "[out]", "-t", total,
        "-ar", 44100, "-c:a", "aac", "-b:a", "192k", out)
    return out
