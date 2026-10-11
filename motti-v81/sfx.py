#!/usr/bin/env python3
"""Original sound effects for the V8.1 update video, synthesized from scratch.

Reads cues.json (one cue per visual event, written by scene.py), renders every
cue, groups them into five stems, ducks them under the voice-over and writes a
loudness-normalised master (-14 LUFS integrated, <= -1 dBTP).

usage: sfx.py <cues.json> <vo.wav> <out_dir>
"""
import json
import math
import os
import sys
import wave

import numpy as np
import pyloudnorm as pyln
from scipy import signal
from scipy.ndimage import minimum_filter1d

SR = 48000
DUR = 14.88
N = int(round(DUR * SR))
VO_END = 9.50

cues_path, vo_path, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out_dir, exist_ok=True)


# ------------------------------------------------------------------ helpers
def db(x):
    return 10 ** (x / 20)


def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def rng(seed):
    return np.random.default_rng(seed)


def noise(dur, seed=0):
    return rng(seed).standard_normal(int(dur * SR))


def env_exp(dur, tau, attack=0.002):
    t = t_axis(dur)
    e = np.exp(-t / tau)
    a = int(attack * SR)
    if a > 1:
        e[:a] *= np.linspace(0, 1, a)
    return e


def env_curve(dur, points):
    """points: list of (time, level) linear segments."""
    t = t_axis(dur)
    ts = [p[0] for p in points]
    vs = [p[1] for p in points]
    return np.interp(t, ts, vs)


def bp(x, lo, hi, order=2):
    lo = max(20, lo)
    hi = min(SR / 2 - 100, hi)
    b, a = signal.butter(order, [lo, hi], btype="band", fs=SR)
    return signal.lfilter(b, a, x)


def hp(x, f, order=2):
    b, a = signal.butter(order, f, btype="high", fs=SR)
    return signal.lfilter(b, a, x)


def lp(x, f, order=2):
    b, a = signal.butter(order, min(f, SR / 2 - 100), btype="low", fs=SR)
    return signal.lfilter(b, a, x)


def sweep_filter(x, f0, f1, q=1.2, kind="band", curve=1.0, block=256):
    """Time-varying biquad (cutoff glides from f0 to f1)."""
    y = np.zeros_like(x)
    n = len(x)
    zi = np.zeros(2)
    for s in range(0, n, block):
        p = (s / max(1, n - 1)) ** curve
        f = f0 * (f1 / f0) ** p
        w0 = 2 * math.pi * min(f, SR / 2 - 200) / SR
        alpha = math.sin(w0) / (2 * q)
        cw = math.cos(w0)
        if kind == "band":
            b = [alpha, 0, -alpha]
        elif kind == "low":
            b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]
        else:
            b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
        a = [1 + alpha, -2 * cw, 1 - alpha]
        b = np.array(b) / a[0]
        a = np.array(a) / a[0]
        seg = x[s:s + block]
        out, zi = signal.lfilter(b, a, seg, zi=zi)
        y[s:s + block] = out
    return y


def osc(freq, dur, kind="sine", phase=0.0):
    """freq: scalar or per-sample array."""
    n = int(dur * SR)
    f = np.full(n, float(freq)) if np.isscalar(freq) else np.asarray(freq)[:n]
    ph = phase + 2 * math.pi * np.cumsum(f) / SR
    if kind == "sine":
        return np.sin(ph)
    if kind == "square":
        # soft band-limited square (odd harmonics up to ~10 kHz)
        out = np.zeros(n)
        for h in range(1, 16, 2):
            mask = (f * h) < 10000
            out += mask * np.sin(h * ph) / h
        return out * 4 / math.pi
    if kind == "tri":
        out = np.zeros(n)
        for i, h in enumerate(range(1, 12, 2)):
            out += ((-1) ** i) * np.sin(h * ph) / (h * h)
        return out * 8 / (math.pi ** 2)
    raise ValueError(kind)


def glide(f0, f1, dur, curve="exp"):
    t = np.linspace(0, 1, int(dur * SR))
    if curve == "exp":
        return f0 * (f1 / f0) ** t
    return f0 + (f1 - f0) * t


def fit(x, n):
    if len(x) >= n:
        return x[:n]
    return np.pad(x, (0, n - len(x)))


def norm(x, peak=1.0):
    m = np.max(np.abs(x)) + 1e-12
    return x / m * peak


def stereo(x, pan=0.0, to_pan=None, width=0.0, seed=0):
    """Constant-power pan (optionally gliding); width adds a decorrelated side."""
    n = len(x)
    p = np.full(n, pan) if to_pan is None else np.linspace(pan, to_pan, n)
    ang = (p + 1) * math.pi / 4
    l, r = x * np.cos(ang), x * np.sin(ang)
    if width > 0:
        side = hp(np.roll(x, int(0.011 * SR)), 300) * width
        l, r = l + side, r - side
    return np.stack([l, r], 1)


_IR = {}


def reverb(st, mix=0.2, decay=0.9, pre=0.012, bright=6000, seed=3):
    key = (decay, pre, bright, seed)
    if key not in _IR:
        n = int((decay * 1.4 + pre) * SR)
        g = rng(seed)
        t = np.arange(n) / SR
        e = np.exp(-t * 6.9 / decay)
        e[: int(pre * SR)] = 0
        irs = []
        for c in range(2):
            v = g.standard_normal(n) * e
            v = lp(v, bright)
            irs.append(v / np.sqrt(np.sum(v ** 2)))
        _IR[key] = irs
    irs = _IR[key]
    wet = np.stack([signal.fftconvolve(st[:, c], irs[c])[: len(st) + len(irs[c]) - 1] for c in range(2)], 1)
    dry = np.vstack([st, np.zeros((len(wet) - len(st), 2))])
    return dry * (1 - mix * 0.5) + wet * mix


def sat(x, drive=1.5):
    return np.tanh(x * drive) / np.tanh(drive)


def crush(x, bits=6, down=6):
    y = np.repeat(x[::down], down)[: len(x)]
    q = 2 ** (bits - 1)
    return np.round(y * q) / q


NOTE = lambda midi: 440.0 * 2 ** ((midi - 69) / 12)


# ------------------------------------------------------------------ sound design
def s_whoosh(c, seed):
    dur = c.get("dur", 0.3) + 0.12
    rise = c.get("rise", True)
    x = noise(dur, seed)
    if rise:
        x = sweep_filter(x, 350, 4200, q=1.4, curve=1.3)
        e = env_curve(dur, [(0, 0), (dur * 0.70, 1), (dur * 0.86, 0.55), (dur, 0)]) ** 1.6
    else:
        x = sweep_filter(x, 4200, 380, q=1.4, curve=0.7)
        e = env_curve(dur, [(0, 0), (0.025, 1), (dur * 0.5, 0.35), (dur, 0)])
    y = norm(x * e)
    return reverb(stereo(y, c.get("pan", 0), c.get("to_pan"), width=0.35, seed=seed), 0.18, 0.6)


def s_swish(c, seed):
    dur = c.get("dur", 0.18) + 0.06
    x = sweep_filter(noise(dur, seed), 1400, 7000, q=1.1, curve=1.0)
    e = env_curve(dur, [(0, 0), (dur * 0.35, 1), (dur, 0)]) ** 1.3
    return reverb(stereo(norm(x * e), c.get("pan", 0), c.get("to_pan"), width=0.3), 0.12, 0.5)


def s_whip(c, seed):
    dur = c.get("dur", 0.12) + 0.05
    x = sweep_filter(noise(dur, seed), 700, 6500, q=1.6, curve=0.8)
    e = env_curve(dur, [(0, 0), (dur * 0.6, 1), (dur * 0.72, 0.4), (dur, 0)]) ** 1.4
    crack = np.zeros(int(dur * SR))
    k = int(dur * 0.6 * SR)
    burst = hp(noise(0.006, seed + 9), 2500) * env_exp(0.006, 0.0015)
    crack[k:k + len(burst)] = burst[: len(crack) - k]
    return stereo(norm(x * e + 0.5 * crack), c.get("pan", 0), c.get("to_pan"), width=0.25)


def s_suck(c, seed):
    dur = c.get("dur", 0.15)
    x = sweep_filter(noise(dur, seed), 500, 9000, q=0.9, kind="low", curve=2.0)
    e = env_curve(dur, [(0, 0), (dur * 0.92, 1), (dur, 0)]) ** 2.2
    return stereo(norm(hp(x, 300) * e), 0, width=0.3)


def s_tick(c, seed):
    p = c.get("pitch", 1.0)
    d = 0.03
    x = bp(noise(d, seed), 2500 * p, 7000 * p) * env_exp(d, 0.0025, 0.0003)
    x += 0.5 * osc(2600 * p, d) * env_exp(d, 0.006, 0.0005)
    return stereo(norm(x), c.get("pan", 0))


def s_click_small(c, seed):
    p = c.get("pitch", 1.0)
    d = 0.02
    x = bp(noise(d, seed), 3500 * p, 9000) * env_exp(d, 0.0015, 0.0002)
    return stereo(norm(x), c.get("pan", 0))


def s_pop(c, seed):
    p = c.get("pitch", 1.0)
    d = 0.12
    f = glide(950 * p, 260 * p, d)
    x = osc(f, d) * env_exp(d, 0.035, 0.001)
    x += 0.35 * bp(noise(d, seed), 1500, 6000) * env_exp(d, 0.004, 0.0003)
    x += 0.4 * osc(glide(160, 70, d), d) * env_exp(d, 0.03, 0.002)
    return reverb(stereo(norm(sat(x, 1.3)), c.get("pan", 0)), 0.12, 0.45)


def s_rubber_pop(c, seed):
    d = 0.2
    t = t_axis(d)
    f = glide(620, 210, d) * (1 + 0.08 * np.sin(2 * math.pi * 26 * t) * np.exp(-t / 0.08))
    x = osc(f, d) * env_exp(d, 0.06, 0.002)
    x += 0.5 * osc(glide(140, 55, d), d) * env_exp(d, 0.05, 0.002)
    x += 0.25 * bp(noise(d, seed), 1200, 5000) * env_exp(d, 0.005, 0.0003)
    return reverb(stereo(norm(sat(x, 1.6))), 0.12, 0.45)


def s_usb_click(c, seed):
    d = 0.09
    x = np.zeros(int(d * SR))
    for off, amp in ((0.0, 1.0), (0.013, 0.55)):
        k = int(off * SR)
        b = bp(noise(0.02, seed + int(off * 1000)), 1800, 7000) * env_exp(0.02, 0.002, 0.0002)
        b += 0.6 * osc(1850, 0.02) * env_exp(0.02, 0.006)
        x[k:k + len(b)] += amp * b
    x += 0.45 * osc(glide(180, 90, d), d) * env_exp(d, 0.018, 0.001)
    return reverb(stereo(norm(sat(x, 1.4)), 0.1), 0.08, 0.3)


def s_cloth(c, seed):
    d = c.get("dur", 0.36)
    x = bp(noise(d, seed), 300, 3500)
    e = env_curve(d, [(0, 0), (d * 0.3, 1), (d, 0)])
    am = 0.6 + 0.4 * np.abs(lp(noise(d, seed + 1), 30))
    return stereo(norm(x * e * am), 0.3, width=0.4)


def s_air_hit(c, seed):
    d = 0.7
    x = hp(noise(d, seed), 1800) * env_exp(d, 0.11, 0.004)
    pre = int(0.06 * SR)
    swell = hp(noise(0.06, seed + 2), 2500) * np.linspace(0, 1, pre) ** 2
    y = np.concatenate([swell * 0.6, x])
    y += 0.15 * fit(osc(NOTE(84), d + 0.06) * env_exp(d + 0.06, 0.25, 0.02), len(y))
    return reverb(stereo(norm(y), 0, width=0.5), 0.35, 1.1)


def s_pluck(c, seed):
    f = NOTE(72 + c.get("note", 0))
    d = 0.5
    x = osc(f, d) * env_exp(d, 0.16, 0.002)
    x += 0.35 * osc(f * 2, d) * env_exp(d, 0.08, 0.002)
    x += 0.12 * osc(f * 4.01, d) * env_exp(d, 0.03, 0.001)
    return reverb(stereo(norm(x), 0.15 * ((c.get("note", 0) % 5) - 2) / 2), 0.28, 0.9)


def s_bloop(c, seed):
    d = 0.18
    x = osc(glide(380, 1400, 0.07).tolist() + [1400] * (int(d * SR) - int(0.07 * SR)), d) * env_exp(d, 0.05, 0.002)
    return reverb(stereo(norm(x)), 0.25, 0.6)


def s_shimmer(c, seed):
    d = c.get("dur", 0.4) + 0.3
    g = rng(seed)
    x = np.zeros(int(d * SR))
    t = t_axis(d)
    for k in range(10):
        f = g.uniform(3200, 9000)
        am = 0.5 + 0.5 * np.sin(2 * math.pi * g.uniform(6, 18) * t + g.uniform(0, 6))
        x += osc(f, d) * am * g.uniform(0.3, 1.0)
    e = env_curve(d, [(0, 0), (d * 0.3, 1), (d, 0)])
    return reverb(stereo(norm(x * e), 0, width=0.6), 0.45, 1.2)


def s_key(c, seed):
    p = c.get("pitch", 1.0)
    d = 0.05
    x = bp(noise(d, seed), 1800 * p, 6000 * p) * env_exp(d, 0.003, 0.0003)
    x += 0.4 * osc(1250 * p, d) * env_exp(d, 0.012, 0.0005)
    return stereo(norm(x), 0.1 * (p - 1) * 5)


def s_whomp(c, seed):
    d = 0.45
    x = sweep_filter(noise(d, seed), 2500, 180, q=0.8, kind="low", curve=0.6)
    e = env_curve(d, [(0, 0), (0.03, 1), (d, 0)])
    y = hp(x * e, 70) + 0.6 * osc(glide(95, 55, d), d) * env_exp(d, 0.09, 0.006)
    return reverb(stereo(norm(sat(y, 1.2)), 0, width=0.3), 0.2, 0.7)


def s_ping(c, seed):
    d = 0.9
    t = t_axis(d)
    x = osc(1760 * (1 + 0.002 * np.sin(2 * math.pi * 5 * t)), d) * env_exp(d, 0.22, 0.002)
    x += 0.45 * osc(2640, d) * env_exp(d, 0.14, 0.002)
    x += 0.2 * osc(5280.0, d) * env_exp(d, 0.05, 0.001)
    return reverb(stereo(norm(x), 0, width=0.2), 0.4, 1.3)


def s_echo_hit(c, seed):
    reps, gap = c.get("repeats", 4), c.get("gap", 0.07)
    h1 = s_pop({"pitch": 0.8}, seed)[:, 0]
    h2 = s_rubber_pop({}, seed + 1)[:, 0]
    n_ = max(len(h1), len(h2))
    hit = fit(h1, n_) + 0.7 * fit(h2, n_)
    hit = norm(hit)
    d = reps * gap + 0.5
    x = np.zeros((int(d * SR), 2))
    for k in range(reps + 1):
        h = hp(hit, 200 + 400 * k) if k else hit
        st = stereo(h * db(-5.5 * k), (-0.35 if k % 2 else 0.35) * (k > 0))
        o = int(k * gap * SR)
        n = min(len(st), len(x) - o)
        x[o:o + n] += st[:n]
    return x


def s_ui_swoosh(c, seed):
    d = 0.32
    x = sweep_filter(noise(d, seed), 600, 3200, q=1.0, curve=1.0)
    x = x * env_curve(d, [(0, 0), (0.12, 1), (d, 0)])
    x += 0.25 * osc(glide(320, 880, d), d) * env_curve(d, [(0, 0), (0.1, 1), (d, 0)])
    return reverb(stereo(norm(x), 0.5, -0.1, width=0.3), 0.2, 0.6)


def s_wheel_tick(c, seed):
    d = 0.015
    x = bp(noise(d, seed), 2500, 8000) * env_exp(d, 0.0012, 0.0002)
    return stereo(norm(x), 0.0)


def s_page_flip(c, seed):
    p = c.get("pitch", 1.0)
    d = 0.11
    t = t_axis(d)
    x = bp(noise(d, seed), 1600 * p, 8000)
    flutter = 0.55 + 0.45 * np.sin(2 * math.pi * 55 * t) ** 2
    e = env_curve(d, [(0, 0), (0.012, 1), (0.05, 0.6), (d, 0)])
    snap = np.zeros(len(t))
    k = int(0.055 * SR)
    b = hp(noise(0.004, seed + 3), 3000) * env_exp(0.004, 0.0008)
    snap[k:k + len(b)] = b
    return reverb(stereo(norm(x * e * flutter + 0.6 * snap), 0.25 - 0.1 * (p - 1) * 10), 0.1, 0.4)


def s_swipe(c, seed):
    return s_swish(dict(c, dur=c.get("dur", 0.18), pan=0.5, to_pan=-0.5), seed)


def s_ui_click(c, seed):
    d = 0.06
    x = osc(glide(1150, 850, d), d) * env_exp(d, 0.012, 0.0005)
    x += 0.5 * bp(noise(d, seed), 2500, 7000) * env_exp(d, 0.002, 0.0002)
    x += 0.3 * osc(glide(220, 120, d), d) * env_exp(d, 0.015, 0.001)
    return stereo(norm(x), -0.2)


def s_play_chime(c, seed):
    d = 1.0
    x = np.zeros(int(d * SR))
    for off, m in ((0.0, 88), (0.075, 95)):
        f = NOTE(m)
        k = int(off * SR)
        dd = d - off
        b = osc(f, dd) * env_exp(dd, 0.25, 0.002) + 0.25 * osc(f * 2.76, dd) * env_exp(dd, 0.08, 0.001)
        x[k:k + len(b)] += b
    return reverb(stereo(norm(x), -0.15, width=0.25), 0.4, 1.3)


def s_shing(c, seed):
    d = 1.1
    t = t_axis(d)
    x = hp(noise(d, seed), 4500) * env_exp(d, 0.12, 0.003) * 0.6
    for f, a in ((3100, 1.0), (4710, 0.7), (6330, 0.55), (8900, 0.35)):
        x += a * osc(f * (1 + 0.004 * t), d) * env_exp(d, 0.28, 0.004)
    return reverb(stereo(norm(x), 0.35, width=0.5), 0.45, 1.5)


def s_impact(c, seed):
    d = 1.4
    sub = osc(glide(92, 36, 0.6).tolist() + [36] * (int(d * SR) - int(0.6 * SR)), d) * env_exp(d, 0.32, 0.003)
    punch = osc(glide(170, 48, 0.06).tolist() + [48] * (int(d * SR) - int(0.06 * SR)), d) * env_exp(d, 0.05, 0.001)
    snap = bp(noise(d, seed), 900, 6000) * env_exp(d, 0.035, 0.0005)
    air = hp(noise(d, seed + 1), 3000) * env_exp(d, 0.25, 0.004) * 0.25
    x = 0.9 * sub + 0.9 * punch + 0.55 * snap + air
    st = stereo(norm(sat(x, 1.8)), 0, width=0.35)
    return reverb(st, 0.3, 1.6, bright=4500)


def s_glitter(c, seed):
    d = c.get("dur", 0.3) + 0.25
    g = rng(seed)
    x = np.zeros((int(d * SR), 2))
    nb = 26
    for k in range(nb):
        tk = (k / nb) ** 1.6 * c.get("dur", 0.3)
        f = g.uniform(4000, 10500)
        bd = 0.04
        b = osc(f, bd) * env_exp(bd, 0.012, 0.0005) * g.uniform(0.4, 1.0)
        st = stereo(b, g.uniform(-0.8, 0.8))
        o = int(tk * SR)
        x[o:o + len(st)] += st[: len(x) - o]
    return reverb(x / (np.max(np.abs(x)) + 1e-9), 0.4, 1.0)


def s_crt_on(c, seed):
    d = 0.45
    t = t_axis(d)
    x = osc(glide(55, 950, 0.28).tolist() + [950] * (int(d * SR) - int(0.28 * SR)), d, "tri")
    x *= env_curve(d, [(0, 0), (0.05, 0.6), (0.28, 1), (d, 0)])
    stat = bp(noise(d, seed), 2000, 9000) * env_curve(d, [(0, 0), (0.02, 1), (0.15, 0.25), (d, 0)]) * 0.5
    hum = 0.25 * osc(100, d) * env_curve(d, [(0, 0), (0.05, 1), (0.3, 0.4), (d, 0)])
    return reverb(stereo(norm(0.6 * x + stat + hum), 0, width=0.3), 0.2, 0.7)


def s_crumble(c, seed):
    d = c.get("dur", 0.55) + 0.1
    g = rng(seed)
    x = np.zeros((int(d * SR), 2))
    ng = 60
    for k in range(ng):
        tk = g.uniform(0, c.get("dur", 0.55)) ** 1.0
        gd = g.uniform(0.012, 0.035)
        gr = crush(bp(noise(gd, seed + k), g.uniform(400, 2000), g.uniform(3000, 9000)), bits=5, down=g.integers(3, 9))
        gr *= env_exp(gd, gd / 3, 0.001) * (1 - tk / d) * g.uniform(0.3, 1.0)
        st = stereo(gr, g.uniform(-0.9, 0.9))
        o = int(tk * SR)
        x[o:o + len(st)] += st[: len(x) - o]
    rum = osc(glide(120, 40, d), d) * env_curve(d, [(0, 0), (0.02, 1), (d, 0)]) * 0.5
    x += stereo(rum)
    return x / (np.max(np.abs(x)) + 1e-9)


def s_arp_down(c, seed):
    n, gap = c.get("n", 8), c.get("gap", 0.045)
    notes = [96, 93, 89, 86, 84, 81, 77, 74, 72, 69][:n]
    d = n * gap + 0.2
    x = np.zeros(int(d * SR))
    for k, m in enumerate(notes):
        bd = 0.06
        b = osc(NOTE(m), bd, "square") * env_exp(bd, 0.03, 0.001)
        o = int(k * gap * SR)
        x[o:o + len(b)] += b[: len(x) - o] * (1 - 0.06 * k)
    return reverb(stereo(norm(lp(x, 7000)), 0, width=0.2), 0.15, 0.5)


def s_glitch(c, seed):
    d = c.get("dur", 0.08)
    g = rng(seed)
    n = int(d * SR)
    x = np.zeros(n)
    pos = 0
    while pos < n:
        seg = int(g.uniform(0.004, 0.018) * SR)
        kind = g.integers(0, 3)
        if kind == 0:
            s = noise(seg / SR, seed + pos)
        elif kind == 1:
            s = osc(g.uniform(300, 3500), seg / SR, "square")
        else:
            s = osc(glide(g.uniform(2000, 5000), g.uniform(100, 600), seg / SR), seg / SR, "square")
        rep = g.integers(1, 4)
        s = np.tile(s, rep)[: n - pos]
        x[pos:pos + len(s)] = s * g.uniform(0.4, 1.0)
        pos += len(s)
    x = crush(x, bits=int(g.integers(4, 7)), down=int(g.integers(2, 7)))
    x *= env_curve(d, [(0, 1), (d * 0.85, 1), (d, 0)])
    return stereo(norm(lp(x, 9000)), g.uniform(-0.3, 0.3), width=0.4)


def s_data_bleep(c, seed):
    g = rng(c.get("seed", seed))
    d = 0.025
    x = osc(g.uniform(1800, 4200), d, "square") * env_exp(d, 0.008, 0.0005)
    return stereo(norm(lp(x, 8000)), g.uniform(-0.4, 0.4))


def s_lock_click(c, seed):
    d = 0.25
    x = bp(noise(d, seed), 2500, 9000) * env_exp(d, 0.002, 0.0002)
    x += 0.7 * (osc(2093, d) + 0.6 * osc(3136, d)) * env_exp(d, 0.05, 0.0008)
    x += 0.5 * osc(glide(200, 90, d), d) * env_exp(d, 0.03, 0.001)
    return reverb(stereo(norm(x), 0, width=0.2), 0.2, 0.6)


def s_spawn(c, seed):
    p = c.get("pitch", 1.0)
    d = 0.05
    x = osc(glide(700 * p, 1100 * p, d), d) * env_exp(d, 0.015, 0.002)
    return stereo(norm(x), 0)


def s_rotate_blip(c, seed):
    p = c.get("pitch", 1.0)
    d = 0.05
    x = osc(glide(900 * p, 1500 * p, d), d, "square") * env_exp(d, 0.02, 0.001)
    return stereo(norm(lp(x, 7000)), 0.2)


def s_lock_thud(c, seed):
    p = c.get("pitch", 1.0)
    d = 0.22
    x = osc(glide(210 * p, 120 * p, d), d) * env_exp(d, 0.05, 0.001)
    x += 0.5 * osc(430 * p, d) * env_exp(d, 0.02, 0.001)
    x += 0.6 * bp(noise(d, seed), 900, 4500) * env_exp(d, 0.006, 0.0003)
    x += 0.4 * osc(glide(90, 50, d), d) * env_exp(d, 0.04, 0.002)
    return reverb(stereo(norm(sat(x, 2.0)), 0, width=0.15), 0.12, 0.4)


def s_sweep_up(c, seed):
    d = c.get("dur", 0.1) + 0.25
    t = t_axis(d)
    core = int(c.get("dur", 0.1) * SR)
    f = np.concatenate([glide(700, 4200, core / SR), np.full(int(d * SR) - core, 4200.0)])
    x = osc(f, d) * env_curve(d, [(0, 0.2), (core / SR, 1), (d, 0)])
    x += 0.3 * hp(noise(d, seed), 3000) * env_curve(d, [(0, 0), (core / SR, 1), (d, 0)])
    return reverb(stereo(norm(x), -0.4, 0.4, width=0.2), 0.3, 0.8)


def s_resolve_snap(c, seed):
    d = 1.3
    x = hp(noise(d, seed), 2000) * env_exp(d, 0.006, 0.0002) * 1.2
    for m, a in ((84, 1.0), (88, 0.8), (91, 0.7), (96, 0.4)):
        x += a * osc(NOTE(m), d) * env_exp(d, 0.35, 0.002) * 0.45
    x += 0.7 * osc(glide(110, 50, d), d) * env_exp(d, 0.06, 0.002)
    x += 0.2 * hp(noise(d, seed + 7), 5000) * env_exp(d, 0.4, 0.05)
    return reverb(stereo(norm(sat(x, 1.2)), 0, width=0.45), 0.42, 1.6)


def s_blip(c, seed):
    p = c.get("pitch", 1.0)
    d = 0.06
    x = osc(1600 * p, d, "tri") * env_exp(d, 0.02, 0.001)
    return reverb(stereo(norm(x), rng(seed).uniform(-0.6, 0.6)), 0.3, 0.7)


def s_zap(c, seed):
    d = 0.11
    x = osc(glide(3200, 260, d), d, "square") * env_exp(d, 0.05, 0.001)
    x += 0.4 * crush(noise(d, seed), 4, 5) * env_exp(d, 0.02, 0.001)
    return stereo(norm(lp(x, 8000)), 0, width=0.4)


def s_row_clear(c, seed):
    p = c.get("pitch", 1.0)
    d = 0.22
    x = np.zeros(int(d * SR))
    for k, m in enumerate((79, 84, 88)):
        bd = 0.12
        b = osc(NOTE(m) * p, bd, "tri") * env_exp(bd, 0.04, 0.001)
        o = int(k * 0.022 * SR)
        x[o:o + len(b)] += b[: len(x) - o]
    x += 0.25 * hp(noise(d, seed), 5000) * env_exp(d, 0.03, 0.001)
    return reverb(stereo(norm(x), 0, width=0.3), 0.2, 0.6)


def s_crt_off(c, seed):
    d = 0.4
    x = osc(glide(1300, 38, 0.14).tolist() + [38] * (int(d * SR) - int(0.14 * SR)), d) * env_exp(d, 0.09, 0.001)
    x += 0.5 * bp(noise(d, seed), 2000, 8000) * env_exp(d, 0.01, 0.0005)
    x += 0.3 * osc(60, d) * env_exp(d, 0.12, 0.003)
    return reverb(stereo(norm(sat(x, 1.4)), 0, width=0.2), 0.25, 0.9)


# ---- reference style (client's reel): crisp, bright, clean digital - no booms, no tonal chimes
def s_click_hi(c, seed):
    """Caption slam: a very short bright click (optional mid 'body' for heavy words)."""
    g = rng(seed)
    d = 0.07
    pt = c.get("pitch", 1.0)
    x = hp(noise(d, seed), 3500, 4) * env_exp(d, 0.0035, 0.0003)
    x += 0.55 * osc(4300 * pt * g.uniform(0.95, 1.05), d) * env_exp(d, 0.0025, 0.0002)
    if c.get("body"):
        x += 0.55 * osc(glide(1150 * pt, 720 * pt, d), d) * env_exp(d, 0.009, 0.0004)
        x += 0.35 * bp(noise(d, seed + 1), 900, 4200) * env_exp(d, 0.006, 0.0003)
    st = stereo(norm(x), g.uniform(-0.15, 0.15), width=0.15, seed=seed)
    return reverb(st, 0.08, 0.25, 0.006, 12000)


def s_tap(c, seed):
    """UI tap: short clean click with a tiny 'tock'."""
    d = 0.06
    pt = c.get("pitch", 1.0)
    x = bp(noise(d, seed), 1500, 7500) * env_exp(d, 0.0025, 0.0002)
    x += 0.6 * osc(1300 * pt, d) * env_exp(d, 0.006, 0.0003)
    return reverb(stereo(norm(x), 0.0, width=0.1, seed=seed), 0.06, 0.2, 0.005, 10000)


def s_shutter(c, seed):
    """Camera-shutter double click (snap + softer return)."""
    d = 0.12
    x = np.zeros(int(d * SR))
    for k, (t0, a, f) in enumerate(((0.0, 1.0, 1.0), (c.get("gap", 0.034), 0.65, 0.85))):
        n0 = int(t0 * SR)
        m = len(x) - n0
        dd = m / SR
        z = bp(noise(dd, seed + k), 2000 * f, 12000) * env_exp(dd, 0.004, 0.0002)
        z += 0.6 * bp(noise(dd, seed + 10 + k), 600 * f, 2600 * f) * env_exp(dd, 0.008, 0.0003)
        x[n0:] += a * z
    return reverb(stereo(norm(x), c.get("pan", 0.0), width=0.2, seed=seed), 0.1, 0.3, 0.006, 11000)


def s_air(c, seed):
    """Short airy whoosh; with cue 'pre' it peaks exactly on the cue time (starts before the cut)."""
    dur = c.get("dur", 0.24)
    pk = min(max(c.get("pre", dur * 0.35), 0.03), dur - 0.02)
    tail = 0.10
    d = dur + tail
    x = noise(d, seed)
    up = c.get("dir", "up") == "up"
    f0, f1 = (1800, 9000) if up else (9000, 2400)
    band = sweep_filter(x, f0, f1, q=0.9, kind="band", curve=1.0)
    air = hp(noise(d, seed + 3), 6500, 2)
    t = t_axis(d)
    e = np.where(t < pk, (t / pk) ** 2.2, np.exp(-(t - pk) / (0.045 + 0.12 * (dur - pk))))
    y = (band + 0.35 * air) * e
    st = stereo(norm(y), c.get("pan", -0.3), c.get("to_pan", 0.3), width=0.3, seed=seed)
    return reverb(st, 0.12, 0.35, 0.008, 12000)


def s_riser_thin(c, seed):
    """Thin rising tone + air that stops dead on the cue (use pre = dur)."""
    d = c.get("dur", 0.2)
    f = glide(c.get("f0", 1800), c.get("f1", 7500), d)
    t = t_axis(d)
    e = (t / d) ** 2.5
    e[-int(0.004 * SR):] *= np.linspace(1, 0, int(0.004 * SR))
    x = 0.6 * osc(f, d) * e + hp(noise(d, seed), 5000, 2) * e * 0.8
    return stereo(norm(x), -0.2, 0.2, width=0.25, seed=seed)


def s_hit_bright(c, seed):
    """Short bright hit: crack + mid body + air tail, no sub boom."""
    d = 0.5
    x = bp(noise(d, seed), 1500, 12000) * env_exp(d, 0.025, 0.0004)
    x += 0.45 * osc(glide(320, 240, d), d) * env_exp(d, 0.022, 0.0008)
    x += 0.35 * osc(2200, d) * env_exp(d, 0.006, 0.0002)
    x += 0.25 * hp(noise(d, seed + 1), 4000, 2) * env_exp(d, 0.12, 0.002)
    x = hp(sat(norm(x), 1.3), 120)
    return reverb(stereo(norm(x), 0, width=0.3, seed=seed), 0.14, 0.45, 0.01, 11000)


def s_sparkle(c, seed):
    """Airy high-frequency sparkle tail (noise grains, no melody)."""
    g = rng(seed)
    d = c.get("dur", 0.45)
    n = int(d * SR)
    imp = np.zeros(n)
    for _ in range(int(60 * d)):
        k = int(min(n - 1, abs(g.exponential(d * 0.35)) * SR))
        imp[k] += g.uniform(0.3, 1.0) * g.choice([-1, 1])
    x = bp(imp, 6000, 15000, 2) * 6 + 0.35 * hp(noise(d, seed), 8000, 2) * env_exp(d, d * 0.3, 0.003)
    return reverb(stereo(norm(x), 0, width=0.6, seed=seed), 0.3, 0.8, 0.01, 14000)


SOUNDS = {
    "whoosh": s_whoosh, "swish": s_swish, "whip": s_whip, "suck": s_suck, "tick": s_tick,
    "click_small": s_click_small, "pop": s_pop, "rubber_pop": s_rubber_pop, "usb_click": s_usb_click,
    "cloth": s_cloth, "air_hit": s_air_hit, "pluck": s_pluck, "bloop": s_bloop, "shimmer": s_shimmer,
    "key": s_key, "whomp": s_whomp, "ping": s_ping, "echo_hit": s_echo_hit, "ui_swoosh": s_ui_swoosh,
    "wheel_tick": s_wheel_tick, "page_flip": s_page_flip, "swipe": s_swipe, "ui_click": s_ui_click,
    "play_chime": s_play_chime, "shing": s_shing, "impact": s_impact, "glitter": s_glitter,
    "crt_on": s_crt_on, "crumble": s_crumble, "arp_down": s_arp_down, "glitch": s_glitch,
    "data_bleep": s_data_bleep, "lock_click": s_lock_click, "spawn": s_spawn, "rotate_blip": s_rotate_blip,
    "lock_thud": s_lock_thud, "sweep_up": s_sweep_up, "resolve_snap": s_resolve_snap, "blip": s_blip,
    "zap": s_zap, "row_clear": s_row_clear, "crt_off": s_crt_off,
    "click_hi": s_click_hi, "tap": s_tap, "shutter": s_shutter, "air": s_air, "riser_thin": s_riser_thin,
    "hit_bright": s_hit_bright, "sparkle": s_sparkle,
}
STEM_OF = {
    "transitions": {"whoosh", "swish", "whip", "suck", "swipe", "ui_swoosh", "whomp", "cloth", "air", "riser_thin"},
    "ui": {"tick", "click_small", "pop", "rubber_pop", "usb_click", "key", "wheel_tick", "page_flip", "ui_click",
           "lock_click", "click_hi", "tap", "shutter"},
    "hits": {"air_hit", "impact", "echo_hit", "lock_thud", "resolve_snap", "hit_bright"},
    "tonal": {"pluck", "bloop", "shimmer", "ping", "play_chime", "shing", "glitter", "sweep_up", "sparkle"},
    "digital": {"crt_on", "crumble", "arp_down", "glitch", "data_bleep", "spawn", "rotate_blip", "blip", "zap",
                "row_clear", "crt_off"},
}
STEM = {k: name for name, ks in STEM_OF.items() for k in ks}
# loudness calibration of the reference-style kinds: very short / airy sounds need more peak level to sit
# just under the voice (like the clicks and whooshes of the reference), not buried in it
KIND_TRIM = {"click_hi": 9.0, "tap": 7.0, "shutter": 7.0, "air": 6.0, "riser_thin": 5.0, "hit_bright": 3.0,
             "sparkle": 4.0}
NO_DUCK = {"impact", "key", "hit_bright"}   # typing and the climax hit stay clear over the voice


# ------------------------------------------------------------------ voice-over
def read_wav(path):
    w = wave.open(path)
    sr, n, ch, sw = w.getframerate(), w.getnframes(), w.getnchannels(), w.getsampwidth()
    raw = w.readframes(n)
    if sw == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        a = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
        a = np.where(a >= 1 << 23, a - (1 << 24), a).astype(np.float64) / (1 << 23)
    else:
        a = np.frombuffer(raw, np.int16).astype(np.float64) / 32768
    a = a.reshape(-1, ch)
    if ch == 1:
        a = np.repeat(a, 2, 1)
    assert sr == SR, sr
    return a


def write_wav(path, x, bits=24):
    x = np.clip(x, -1, 1)
    w = wave.open(path, "wb")
    w.setnchannels(2)
    w.setsampwidth(bits // 8)
    w.setframerate(SR)
    if bits == 24:
        v = np.round(x * (2 ** 23 - 1)).astype(np.int32).reshape(-1)
        b = np.stack([(v & 255), (v >> 8) & 255, (v >> 16) & 255], 1).astype(np.uint8)
        w.writeframes(b.tobytes())
    else:
        w.writeframes(np.round(x * 32767).astype(np.int16).tobytes())
    w.close()


vo = read_wav(vo_path)
vo = np.vstack([vo, np.zeros((max(0, N - len(vo)), 2))])[:N]

# voice envelope for ducking (attack 8 ms, release 160 ms)
mono = np.abs(vo.mean(1))
env = np.zeros(N)
a_att, a_rel = math.exp(-1 / (0.008 * SR)), math.exp(-1 / (0.16 * SR))
lvl = 0.0
for i in range(0, N, 32):
    v = mono[i:i + 32].max()
    lvl = (a_att ** 32) * lvl + (1 - a_att ** 32) * v if v > lvl else (a_rel ** 32) * lvl + (1 - a_rel ** 32) * v
    env[i:i + 32] = lvl
env = env / (env.max() + 1e-9)
duck = 1 - 0.5 * np.clip(env * 1.6, 0, 1)       # up to -6 dB under the voice

# ------------------------------------------------------------------ render cues
cues = json.load(open(cues_path, encoding="utf-8"))
stems = {name: np.zeros((N + SR * 3, 2)) for name in STEM_OF}
cue_log = []
for i, c in enumerate(cues):
    fn = SOUNDS[c["kind"]]
    st = fn(c, c.get("synth_seed", 1000 + i))
    if c["t"] < VO_END and c["kind"] not in NO_DUCK:
        st = np.stack([hp(st[:, 0], 140), hp(st[:, 1], 140)], 1)
    g = db(c.get("gain", -18) + KIND_TRIM.get(c["kind"], 0.0))
    st = st / (np.max(np.abs(st)) + 1e-9) * g
    o = int(round((c["t"] - c.get("pre", 0.0)) * SR))   # 'pre': the sound starts before its cue time
    if o < 0:
        st, o = st[-o:], 0
    end = min(len(stems["ui"]), o + len(st))
    seg = st[: end - o]
    if c["kind"] not in NO_DUCK:
        dk = np.ones(len(seg))
        m = max(0, min(len(seg), N - o))
        dk[:m] = duck[o:o + m]
        seg = seg * dk[:, None]
    stems[STEM[c["kind"]]][o:end] += seg
    cue_log.append({"t": c["t"], "kind": c["kind"], "stem": STEM[c["kind"]], "gain": c.get("gain")})

for k in stems:
    stems[k] = stems[k][:N]
sfx = sum(stems.values())
mix = vo + sfx

# ------------------------------------------------------------------ master: loudness + true-peak limiter
meter = pyln.Meter(SR)
lufs_in = meter.integrated_loudness(mix)
gain = db(-14.0 - lufs_in)
mix_g = mix * gain


def true_peak_limit(x, ceiling_db=-1.0, look=0.004, rel=0.08):
    ceiling = db(ceiling_db)
    up = signal.resample_poly(x, 4, 1, axis=0)
    pk = np.abs(up).max(1).reshape(-1, 4).max(1)[: len(x)]
    need = np.minimum(1.0, ceiling / (pk + 1e-12))
    # look-ahead min filter then release smoothing
    la = int(look * SR)
    g = minimum_filter1d(need, size=2 * la + 1)
    out = np.empty_like(g)
    cur = 1.0
    ar = math.exp(-1 / (rel * SR))
    for i in range(len(g)):
        cur = g[i] if g[i] < cur else ar * cur + (1 - ar) * g[i]
        out[i] = cur
    return x * out[:, None]


master = true_peak_limit(mix_g)
lufs_out = meter.integrated_loudness(master)
tp = 20 * math.log10(np.abs(signal.resample_poly(master, 4, 1, axis=0)).max() + 1e-12)

write_wav(os.path.join(out_dir, "MIX_vo_sfx.wav"), master)
write_wav(os.path.join(out_dir, "VO.wav"), vo * gain)
for k, v in stems.items():
    write_wav(os.path.join(out_dir, "SFX_%s.wav" % k), v * gain)
write_wav(os.path.join(out_dir, "SFX_all.wav"), sfx * gain)
json.dump({"lufs_in": lufs_in, "gain_db": 20 * math.log10(gain), "lufs_out": lufs_out, "true_peak_dbtp": tp,
           "cues": cue_log}, open(os.path.join(out_dir, "sfx_report.json"), "w"), indent=1)
print("cues %d  mix in %.1f LUFS -> out %.1f LUFS, TP %.2f dBTP" % (len(cues), lufs_in, lufs_out, tp))
