"""Synthesized sound effects (pops, sparkles, whooshes, plucks...), built once into ~/.lesson-videos/sfx."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
from scipy import signal

from . import config

SR = 48000
NAMES = tuple([f"pencil{i}" for i in range(3)] + [f"crayon{i}" for i in range(2)] + [f"tape{i}" for i in range(3)]
              + [f"whoosh{i}" for i in range(3)] + [f"sparkle{i}" for i in range(3)] + [f"pop{i}" for i in range(4)]
              + [f"pluck{i}" for i in range(4)] + ["waves0"] + [f"zip{i}" for i in range(3)] + ["shutter0"]
              + [f"thump{i}" for i in range(2)])


def sfx_dir() -> Path:
    return config.home() / "sfx"


def _save(name, x, stereo=None):
    if stereo is None:
        stereo = np.stack([x, x], 1)
    stereo = stereo / (np.abs(stereo).max() + 1e-9) * 0.89
    d = (stereo * 32767).astype(np.int16)
    sfx_dir().mkdir(parents=True, exist_ok=True)
    with wave.open(str(sfx_dir() / f"{name}.wav"), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(d.tobytes())


def _t(d): return np.arange(int(d * SR)) / SR
def _bp(x, lo, hi, o=2): return signal.sosfilt(signal.butter(o, [lo, hi], "band", fs=SR, output="sos"), x)
def _lp(x, f, o=2): return signal.sosfilt(signal.butter(o, f, "low", fs=SR, output="sos"), x)
def _hp(x, f, o=2): return signal.sosfilt(signal.butter(o, f, "high", fs=SR, output="sos"), x)


def _synth():
    rng = np.random.default_rng(11)

    def pink(n):
        w = rng.standard_normal(n); f = np.fft.rfft(w); k = np.arange(len(f)); k[0] = 1
        return np.fft.irfft(f / np.sqrt(k), n)

    def ir(d=0.9, decay=3.5):
        n = int(d * SR); e = np.exp(-decay * np.arange(n) / n * 5)
        L = _lp(rng.standard_normal(n) * e, 7000); R = _lp(rng.standard_normal(n) * e, 7000)
        return L / np.abs(L).sum() * 30, R / np.abs(R).sum() * 30
    IRL, IRR = ir()

    def verb(x, wet=0.25):
        L = signal.fftconvolve(x, IRL)[:len(x) + len(IRL) - 1]; R = signal.fftconvolve(x, IRR)[:len(L)]
        dry = np.pad(x, (0, len(L) - len(x)))
        return np.stack([dry + wet * L, dry + wet * R], 1)

    def pencil(d, seed):
        r = np.random.default_rng(seed); n = int(d * SR); tt = _t(d)
        base = _bp(pink(n), 1800, 7000) * 0.6 + _bp(r.standard_normal(n), 3000, 9000) * 0.25
        rate = r.uniform(6, 9); env = np.abs(np.sin(np.pi * rate * tt + r.uniform(0, 3))) ** 0.7
        env *= 0.7 + 0.3 * np.sin(2 * np.pi * 1.3 * tt)
        grains = np.zeros(n); idx = r.integers(0, n, int(d * 900)); grains[idx] = r.uniform(-1, 1, len(idx)); grains = _hp(grains, 2500) * 0.5
        fade = np.minimum(1, np.minimum(tt / 0.04, (d - tt) / 0.08))
        return (base + grains) * env * fade
    for i, d in enumerate([0.7, 1.3, 2.0]): _save(f"pencil{i}", pencil(d, 100 + i))

    def crayon(d, seed):
        r = np.random.default_rng(seed); n = int(d * SR); tt = _t(d)
        base = _bp(pink(n), 700, 4500) * 0.8
        env = np.abs(np.sin(np.pi * r.uniform(3.5, 5) * tt)) ** 0.5
        return base * env * np.minimum(1, np.minimum(tt / 0.03, (d - tt) / 0.1))
    for i, d in enumerate([0.8, 1.4]): _save(f"crayon{i}", crayon(d, 200 + i))

    def tape(seed):
        r = np.random.default_rng(seed); d = 0.55; n = int(d * SR); tt = _t(d)
        rip_d = r.uniform(0.22, 0.32); m = tt < rip_d
        dens = np.where(m, 3000 + 9000 * (tt / rip_d), 0)
        imp = (r.random(n) < dens / SR) * r.uniform(-1, 1, n)
        crack = _bp(imp, 900, 9000) * 1.2 + _bp(r.standard_normal(n), 2000, 8000) * 0.15 * m
        env = np.where(m, np.minimum(1, tt / 0.02), np.exp(-(tt - rip_d) * 60))
        thump_t = tt - (rip_d + 0.06)
        thump = np.where(thump_t > 0, np.sin(2 * np.pi * 140 * thump_t) * np.exp(-thump_t * 45), 0) * 0.5
        press = np.where(thump_t > 0, _bp(r.standard_normal(n), 300, 2500) * np.exp(-np.maximum(thump_t, 0) * 30), 0) * 0.3
        return crack * env + thump + press
    for i in range(3): _save(f"tape{i}", tape(300 + i))

    def whoosh(d, seed, lo=350, hi=2600):
        r = np.random.default_rng(seed); n = int(d * SR); tt = _t(d); x = r.standard_normal(n)
        out = np.zeros(n); blk = 480; zi = None
        for s in range(0, n, blk):
            p = s / n; fc = lo + (hi - lo) * np.sin(np.pi * p) ** 1.5
            sos = signal.butter(2, [fc * 0.6, fc * 1.5], "band", fs=SR, output="sos")
            if zi is None: zi = np.zeros((sos.shape[0], 2))
            out[s:s + blk], zi = signal.sosfilt(sos, x[s:s + blk], zi=zi)
        y = out * np.sin(np.pi * tt / d) ** 2
        pan = tt / d
        return y, np.stack([y * np.cos(pan * np.pi / 2) * 1.2, y * np.sin(pan * np.pi / 2) * 1.2], 1)
    for i, d in enumerate([0.6, 0.9, 1.3]):
        m, s = whoosh(d, 400 + i); _save(f"whoosh{i}", m, s)

    def bell(f, d, amp=1.0):
        tt = _t(d)
        return amp * (np.sin(2 * np.pi * f * tt) * np.exp(-tt * 5) + 0.35 * np.sin(2 * np.pi * f * 2.76 * tt) * np.exp(-tt * 11)
                      + 0.15 * np.sin(2 * np.pi * f * 5.4 * tt) * np.exp(-tt * 18)) * np.minimum(1, tt / 0.002)

    def sparkle(notes, gap, seed, d=2.2):
        r = np.random.default_rng(seed); n = int(d * SR); x = np.zeros(n)
        for k, f in enumerate(notes):
            s = int((k * gap + r.uniform(0, 0.015)) * SR); b = bell(f, 1.2, 0.6 + 0.4 * r.random())
            x[s:s + len(b)] += b[:n - s]
        return verb(x, 0.35)[:n + int(0.5 * SR)]
    P = [1046.5, 1174.7, 1318.5, 1568.0, 1760.0, 2093.0, 2349.3, 2637.0, 3136.0]
    _save("sparkle0", None, sparkle([P[i] for i in [2, 4, 5, 7, 8]], 0.07, 500))
    _save("sparkle1", None, sparkle([P[i] for i in [8, 6, 5, 3, 2, 0]], 0.06, 501))
    _save("sparkle2", None, sparkle([P[i] for i in [0, 3, 5, 8]], 0.11, 502))

    def pop(f0, seed):
        r = np.random.default_rng(seed); d = 0.18; tt = _t(d)
        f = f0 * (0.45 + 0.55 * np.exp(-tt * 40)); ph = 2 * np.pi * np.cumsum(f) / SR
        return (np.sin(ph) * np.exp(-tt * 28) * np.minimum(1, tt / 0.003)
                + _bp(r.standard_normal(len(tt)), 1500, 6000) * np.exp(-tt * 120) * 0.2)
    for i, f in enumerate([700, 900, 1100, 1300]): _save(f"pop{i}", None, verb(pop(f, 600 + i), 0.12))

    def pluck(f, d=0.9, seed=0):
        r = np.random.default_rng(seed); n = int(d * SR); N = int(SR / f); buf = r.uniform(-1, 1, N); out = np.zeros(n)
        for i in range(n):
            out[i] = buf[i % N]; buf[i % N] = 0.996 * 0.5 * (buf[i % N] + buf[(i + 1) % N])
        return out
    for i, f in enumerate([523.3, 659.3, 784.0, 1046.5]): _save(f"pluck{i}", None, verb(pluck(f, 0.8, 700 + i), 0.2))

    def waves(d):
        n = int(d * SR); tt = _t(d); b = np.cumsum(rng.standard_normal(n)); b = _hp(b, 40); b = _lp(b, 1800)
        sw = 0.55 + 0.45 * np.sin(2 * np.pi * tt / 2.6 - 1.2) ** 2
        fiz = _bp(rng.standard_normal(n), 2500, 9000) * (np.sin(2 * np.pi * tt / 2.6 - 0.6).clip(0) ** 3) * 0.3
        fade = np.minimum(1, np.minimum(tt / 0.6, (d - tt) / 0.8))
        L = (b / np.abs(b).max() * sw + fiz) * fade; R = np.roll(L, 900)
        return np.stack([L, R], 1)
    _save("waves0", None, waves(4.0))

    def zipper(seed, d=0.35):
        r = np.random.default_rng(seed); n = int(d * SR); tt = _t(d); x = r.standard_normal(n)
        out = np.zeros(n); blk = 240; zi = None
        for s in range(0, n, blk):
            fc = 1200 + 4000 * (s / n); sos = signal.butter(2, [fc * 0.7, fc * 1.3], "band", fs=SR, output="sos")
            if zi is None: zi = np.zeros((sos.shape[0], 2))
            out[s:s + blk], zi = signal.sosfilt(sos, x[s:s + blk], zi=zi)
        return out * np.sin(np.pi * tt / d) ** 1.5
    for i in range(3): _save(f"zip{i}", zipper(800 + i, [0.3, 0.45, 0.6][i]))

    def shutter():
        d = 0.7; n = int(d * SR); tt = _t(d); x = np.zeros(n)
        for s0, a in [(0.0, 1.0), (0.075, 0.7)]:
            s = int(s0 * SR); m = int(0.012 * SR)
            x[s:s + m] += _hp(rng.standard_normal(m), 1500) * np.exp(-np.arange(m) / SR * 400) * a
        wt = tt - 0.16; saw = signal.sawtooth(2 * np.pi * (700 + 150 * np.sin(2 * np.pi * 18 * tt)) * tt) * 0.12
        whirr = np.where((wt > 0) & (wt < 0.4), _lp(saw + 0.2 * _bp(rng.standard_normal(n), 800, 3000), 3000)
                         * np.sin(np.pi * np.clip(wt / 0.4, 0, 1)), 0)
        return x + whirr * 0.8
    _save("shutter0", shutter())

    def thump(seed):
        r = np.random.default_rng(seed); d = 0.3; tt = _t(d)
        return np.sin(2 * np.pi * 95 * tt) * np.exp(-tt * 30) * 0.8 + _bp(r.standard_normal(len(tt)), 400, 3500) * np.exp(-tt * 45) * 0.6
    for i in range(2): _save(f"thump{i}", thump(900 + i))


def build(force: bool = False) -> Path:
    if force or not all((sfx_dir() / f"{n}.wav").exists() for n in NAMES):
        _synth()
    return sfx_dir()
