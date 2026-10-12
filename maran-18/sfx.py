#!/usr/bin/env python3
"""Original sound effects for the Maran "18 NIS" typography video, synthesized from scratch.

Soft and elegant: airy swooshes, gentle computer clicks, a screen tap, small coin clinks,
three rising ticks and only two bells (on "מרן" and when the logo settles).

Reads cues.json (one cue per visual event, written by scene.py), renders every cue, groups
them into three stems, ducks them under the voice-over and writes a loudness-normalised
master (-14 LUFS integrated, <= -1 dBTP).

usage: sfx.py <cues.json> <vo.wav> <out_dir> [--oneshots]
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
DUR = 15.5
N = int(round(DUR * SR))
VO_END = 12.93
FPS = 30000 / 1001

cues_path, vo_path, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
ONESHOTS = "--oneshots" in sys.argv[4:]
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
    t = t_axis(dur)
    return np.interp(t, [p[0] for p in points], [p[1] for p in points])


def bp(x, lo, hi, order=2):
    b, a = signal.butter(order, [max(20, lo), min(SR / 2 - 100, hi)], btype="band", fs=SR)
    return signal.lfilter(b, a, x)


def hp(x, f, order=2):
    b, a = signal.butter(order, f, btype="high", fs=SR)
    return signal.lfilter(b, a, x)


def lp(x, f, order=2):
    b, a = signal.butter(order, min(f, SR / 2 - 100), btype="low", fs=SR)
    return signal.lfilter(b, a, x)


def sweep_filter(x, f0, f1, q=1.2, curve=1.0, block=256):
    """Band-pass whose centre glides from f0 to f1."""
    y = np.zeros_like(x)
    n = len(x)
    zi = np.zeros(2)
    for s in range(0, n, block):
        p = (s / max(1, n - 1)) ** curve
        f = f0 * (f1 / f0) ** p
        w0 = 2 * math.pi * min(f, SR / 2 - 200) / SR
        alpha = math.sin(w0) / (2 * q)
        cw = math.cos(w0)
        b = np.array([alpha, 0, -alpha]) / (1 + alpha)
        a = np.array([1 + alpha, -2 * cw, 1 - alpha]) / (1 + alpha)
        out, zi = signal.lfilter(b, a, x[s:s + block], zi=zi)
        y[s:s + block] = out
    return y


def osc(freq, dur, phase=0.0):
    n = int(dur * SR)
    f = np.full(n, float(freq)) if np.isscalar(freq) else np.asarray(freq)[:n]
    return np.sin(phase + 2 * math.pi * np.cumsum(f) / SR)


def glide(f0, f1, dur):
    return f0 * (f1 / f0) ** np.linspace(0, 1, int(dur * SR))


def norm(x, peak=1.0):
    return x / (np.max(np.abs(x)) + 1e-12) * peak


def stereo(x, pan=0.0, to_pan=None, width=0.0):
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
        for _ in range(2):
            v = lp(g.standard_normal(n) * e, bright)
            irs.append(v / np.sqrt(np.sum(v ** 2)))
        _IR[key] = irs
    irs = _IR[key]
    wet = np.stack([signal.fftconvolve(st[:, c], irs[c]) for c in range(2)], 1)
    dry = np.vstack([st, np.zeros((len(wet) - len(st), 2))])
    return dry * (1 - mix * 0.5) + wet * mix


NOTE = lambda midi: 440.0 * 2 ** ((midi - 69) / 12)


# ------------------------------------------------------------------ sound design
def s_air_rise(c, seed):
    """Breath of air rising with the steam: slow band sweep upwards, wide and soft."""
    d = c.get("dur", 1.2)
    x = sweep_filter(noise(d, seed), 260, 3200, q=0.9, curve=1.1)
    e = env_curve(d, [(0, 0), (d * 0.55, 1), (d * 0.8, 0.6), (d, 0)]) ** 1.5
    return reverb(stereo(norm(lp(x, 6000) * e), -0.15, 0.15, width=0.5), 0.3, 1.0)


def s_swoosh_soft(c, seed):
    """Gentle whoosh: rises, peaks two thirds in, dissolves."""
    d = c.get("dur", 0.55) + 0.1
    x = sweep_filter(noise(d, seed), 380, 2600, q=1.0, curve=0.9)
    x = lp(x, 5200)
    e = env_curve(d, [(0, 0), (d * 0.62, 1), (d * 0.82, 0.5), (d, 0)]) ** 1.7
    return reverb(stereo(norm(x * e), 0.2, -0.2, width=0.4), 0.24, 0.8)


def s_swoosh_long(c, seed):
    """Longer airy sweep under the light flash, with a faint silky top."""
    d = c.get("dur", 0.95) + 0.1
    x = sweep_filter(noise(d, seed), 300, 4200, q=0.9, curve=1.15)
    top = hp(noise(d, seed + 5), 7000) * 0.18
    e = env_curve(d, [(0, 0), (d * 0.7, 1), (d * 0.86, 0.55), (d, 0)]) ** 1.6
    return reverb(stereo(norm(lp(x, 7000) * e + top * e), -0.25, 0.25, width=0.55), 0.32, 1.1)


def s_click_soft(c, seed):
    """Soft computer click: a short filtered tick, a tiny tone and a felt-like body."""
    p = c.get("pitch", 1.0)
    d = 0.09
    x = bp(noise(d, seed), 1800 * p, 6500 * p) * env_exp(d, 0.0018, 0.0003)
    x += 0.35 * osc(1650 * p, d) * env_exp(d, 0.007, 0.0005)
    x += 0.30 * osc(glide(210 * p, 120 * p, d), d) * env_exp(d, 0.014, 0.001)
    return reverb(stereo(norm(lp(x, 9000))), 0.14, 0.4)


def s_tap(c, seed):
    """Finger tap on a phone screen: a rounded 'tok' and a short glassy transient."""
    d = 0.16
    x = 0.9 * osc(glide(820, 430, 0.03).tolist() + [430] * (int(d * SR) - int(0.03 * SR)), d) * env_exp(d, 0.022, 0.0008)
    x += 0.45 * lp(bp(noise(d, seed), 1500, 7000) * env_exp(d, 0.0025, 0.0002), 6000)
    x += 0.35 * osc(glide(160, 90, d), d) * env_exp(d, 0.02, 0.001)
    return reverb(stereo(norm(x)), 0.16, 0.45)


def s_coin(c, seed):
    """Small metallic clink: a few inharmonic partials with fast decays."""
    g = rng(seed)
    p = c.get("pitch", 1.0)
    d = 0.5
    x = np.zeros(int(d * SR))
    for f, a, tau in ((2350, 1.0, 0.10), (3980, 0.7, 0.07), (5620, 0.45, 0.05), (7150, 0.3, 0.035)):
        x += a * osc(f * p * g.uniform(0.99, 1.01), d, g.uniform(0, 6)) * env_exp(d, tau, 0.0004)
    x += 0.3 * bp(noise(d, seed), 4000, 12000) * env_exp(d, 0.003, 0.0002)
    return reverb(stereo(norm(x), g.uniform(-0.2, 0.2)), 0.2, 0.6, bright=9000)


def s_tick(c, seed):
    """Delicate wooden/glass tick, pitched (rises from cue to cue)."""
    p = c.get("pitch", 1.0)
    d = 0.22
    f = 1180 * p
    x = osc(f, d) * env_exp(d, 0.045, 0.0008)
    x += 0.35 * osc(f * 2.76, d) * env_exp(d, 0.018, 0.0005)
    x += 0.25 * bp(noise(d, seed), 2500, 8000) * env_exp(d, 0.002, 0.0002)
    return reverb(stereo(norm(x), 0.1 * (p - 1.12) / 0.12), 0.2, 0.6)


def s_bell(c, seed):
    """Warm bell: soft mallet strike, inharmonic partials, long tail. note 0 = on "מרן", 1 = logo."""
    note = c.get("note", 0)
    f0 = NOTE(76) if note == 0 else NOTE(69)        # E5 / A4
    d = 3.2 if note else 2.4
    g = rng(seed)
    partials = [(0.5, 0.35, 1.8), (1.0, 1.0, 1.4), (1.183, 0.42, 1.0), (1.506, 0.30, 0.8), (2.0, 0.40, 0.7),
                (2.514, 0.18, 0.45), (2.662, 0.14, 0.4), (3.011, 0.10, 0.3), (4.166, 0.06, 0.2)]
    x = np.zeros(int(d * SR))
    for r, a, tau in partials:
        x += a * osc(f0 * r * g.uniform(0.998, 1.002), d, g.uniform(0, 6)) * env_exp(d, tau * (1.3 if note else 1.0), 0.004)
    x += 0.12 * lp(noise(d, seed), 3000) * env_exp(d, 0.01, 0.001)
    if note:
        x += 0.25 * osc(f0 * 1.5, d) * env_exp(d, 1.2, 0.02)      # a soft fifth for the resolve
    return reverb(stereo(norm(lp(x, 9000)), 0, width=0.35), 0.38, 2.2, 0.02, 7000)


def s_bloom(c, seed):
    """Warm, deep swell as the logo blooms out of the light."""
    d = c.get("dur", 1.4) + 0.4
    x = np.zeros(int(d * SR))
    t = t_axis(d)
    for m, a in ((45, 0.8), (52, 0.55), (57, 0.45), (64, 0.25)):
        vib = 1 + 0.002 * np.sin(2 * math.pi * 4.5 * t)
        x += a * osc(NOTE(m) * vib, d)
    x += 0.25 * lp(noise(d, seed), 900)
    e = env_curve(d, [(0, 0), (d * 0.35, 1), (d * 0.6, 0.7), (d, 0)]) ** 1.4
    return reverb(stereo(norm(lp(x, 2200) * e), 0, width=0.4), 0.35, 1.6, 0.02, 4000)


def s_boop(c, seed):
    """Tiny playful rising boop for the arrow."""
    d = 0.14
    x = osc(glide(520, 860, 0.07).tolist() + [860] * (int(d * SR) - int(0.07 * SR)), d) * \
        env_curve(d, [(0, 0), (0.008, 1), (0.05, 0.6), (d, 0)])
    return reverb(stereo(norm(x)), 0.22, 0.5)


SOUNDS = {"air_rise": s_air_rise, "swoosh_soft": s_swoosh_soft, "swoosh_long": s_swoosh_long,
          "click_soft": s_click_soft, "tap": s_tap, "coin": s_coin, "tick": s_tick, "bell": s_bell,
          "bloom": s_bloom, "boop": s_boop}
STEM_OF = {"swooshes": {"air_rise", "swoosh_soft", "swoosh_long"},
           "clicks": {"click_soft", "tap", "coin", "tick", "boop"},
           "tonal": {"bell", "bloom"}}
STEM = {k: name for name, ks in STEM_OF.items() for k in ks}
KIND_HE = {"air_rise": "נשיפת אוויר עולה", "swoosh_soft": "ווש רך", "swoosh_long": "ווש ארוך",
           "click_soft": "קליק רך", "tap": "לחיצה על מסך", "coin": "נקישת מטבע", "tick": "נקישה עדינה",
           "bell": "פעמון", "bloom": "פריחה חמה", "boop": "בופ קטן"}


# ------------------------------------------------------------------ voice-over
def read_wav(path):
    w = wave.open(path)
    sr, n, ch, sw = w.getframerate(), w.getnframes(), w.getnchannels(), w.getsampwidth()
    assert sw == 2 and sr == SR, (sw, sr)
    a = np.frombuffer(w.readframes(n), np.int16).astype(np.float64).reshape(-1, ch) / 32768
    return np.repeat(a, 2, 1) if ch == 1 else a


def write_wav(path, x, bits=24):
    x = np.clip(x, -1, 1)
    w = wave.open(path, "wb")
    w.setnchannels(2)
    w.setsampwidth(bits // 8)
    w.setframerate(SR)
    if bits == 24:
        v = np.round(x * (2 ** 23 - 1)).astype(np.int32).reshape(-1)
        w.writeframes(np.stack([(v & 255), (v >> 8) & 255, (v >> 16) & 255], 1).astype(np.uint8).tobytes())
    else:
        w.writeframes(np.round(x * 32767).astype(np.int16).tobytes())
    w.close()


vo = read_wav(vo_path)
vo = np.vstack([vo, np.zeros((max(0, N - len(vo)), 2))])[:N]

# voice envelope for ducking (attack 8 ms, release 160 ms), up to -4 dB under the voice
mono = np.abs(vo.mean(1))
env = np.zeros(N)
a_att, a_rel = math.exp(-1 / (0.008 * SR)), math.exp(-1 / (0.16 * SR))
lvl = 0.0
for i in range(0, N, 32):
    v = mono[i:i + 32].max()
    lvl = (a_att ** 32) * lvl + (1 - a_att ** 32) * v if v > lvl else (a_rel ** 32) * lvl + (1 - a_rel ** 32) * v
    env[i:i + 32] = lvl
env = env / (env.max() + 1e-9)
duck = 1 - 0.37 * np.clip(env * 1.6, 0, 1)

# ------------------------------------------------------------------ render cues
cues = json.load(open(cues_path, encoding="utf-8"))
stems = {name: np.zeros((N + SR * 4, 2)) for name in STEM_OF}
oneshots = []
for i, c in enumerate(cues):
    st = SOUNDS[c["kind"]](c, c.get("synth_seed", 1000 + i))
    if c["t"] < VO_END and c["kind"] not in ("bloom",):
        st = np.stack([hp(st[:, 0], 130), hp(st[:, 1], 130)], 1)     # keep the voice's low end clean
    st = st / (np.max(np.abs(st)) + 1e-9) * db(c.get("gain", -20))
    o = int(round((c["t"] - c.get("pre", 0.0)) * SR))
    if o < 0:
        st, o = st[-o:], 0
    oneshots.append((c, o, st))
    end = min(len(stems["clicks"]), o + len(st))
    seg = st[: end - o]
    dk = np.ones(len(seg))
    m = max(0, min(len(seg), N - o))
    dk[:m] = duck[o:o + m]
    stems[STEM[c["kind"]]][o:end] += seg * dk[:, None]

for k in stems:
    tail = stems[k][N:]
    stems[k] = stems[k][:N]
    fade = int(0.25 * SR)              # the comp ends on the logo: fade any reverb tail at the very end
    stems[k][-fade:] *= np.linspace(1, 0, fade)[:, None] ** 2
sfx = sum(stems.values())
mix = vo + sfx

# ------------------------------------------------------------------ master: loudness + true-peak limiter
meter = pyln.Meter(SR)
lufs_in = meter.integrated_loudness(mix)
gain = db(-14.0 - lufs_in)


def true_peak_limit(x, ceiling_db=-1.0, look=0.004, rel=0.08):
    ceiling = db(ceiling_db)
    up = signal.resample_poly(x, 4, 1, axis=0)
    pk = np.abs(up).max(1).reshape(-1, 4).max(1)[: len(x)]
    need = np.minimum(1.0, ceiling / (pk + 1e-12))
    g = minimum_filter1d(need, size=2 * int(look * SR) + 1)
    out = np.empty_like(g)
    cur = 1.0
    ar = math.exp(-1 / (rel * SR))
    for i in range(len(g)):
        cur = g[i] if g[i] < cur else ar * cur + (1 - ar) * g[i]
        out[i] = cur
    return x * out[:, None]


master = true_peak_limit(mix * gain)
lufs_out = meter.integrated_loudness(master)
tp = 20 * math.log10(np.abs(signal.resample_poly(master, 4, 1, axis=0)).max() + 1e-12)

write_wav(os.path.join(out_dir, "MIX_vo_sfx.wav"), master)
write_wav(os.path.join(out_dir, "VO.wav"), vo * gain)
for k, v in stems.items():
    write_wav(os.path.join(out_dir, "SFX_%s.wav" % k), v * gain)
write_wav(os.path.join(out_dir, "SFX_all.wav"), sfx * gain)
if ONESHOTS:
    od = os.path.join(out_dir, "oneshots")
    os.makedirs(od, exist_ok=True)
    rows = ["﻿file,start_s,timecode_29.97,cue_s,kind,type_he"]
    for k, (c, o, st) in enumerate(sorted(oneshots, key=lambda r: (r[1], r[0]["kind"]))):
        start = o / SR
        fr = int(round(start * FPS))
        tc = "00:00:%02d:%02d" % (fr // 30, fr % 30)
        name = "%03d_%05.2fs_%s.wav" % (k + 1, start, c["kind"])
        y = st * gain
        loud = np.nonzero(np.abs(y).max(1) > db(-90))[0]
        y = y[: (loud[-1] + int(0.01 * SR)) if len(loud) else 1]
        write_wav(os.path.join(od, name), y)
        rows.append("%s,%.3f,%s,%.3f,%s,%s" % (name, start, tc, c["t"], c["kind"], KIND_HE.get(c["kind"], c["kind"])))
    open(os.path.join(out_dir, "cue_list.csv"), "w", encoding="utf-8").write("\n".join(rows) + "\n")
    print("oneshots %d -> %s" % (len(oneshots), od))
json.dump({"lufs_in": lufs_in, "gain_db": 20 * math.log10(gain), "lufs_out": lufs_out, "true_peak_dbtp": tp},
          open(os.path.join(out_dir, "sfx_report.json"), "w"), indent=1)
print("cues %d  mix in %.1f LUFS -> out %.1f LUFS, TP %.2f dBTP" % (len(cues), lufs_in, lufs_out, tp))
