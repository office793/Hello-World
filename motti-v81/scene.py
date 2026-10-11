#!/usr/bin/env python3
"""Scene description for "Motti Rosenfeld - update V8.1" (1080x1920, 25 fps, 14.88 s).

Single source of truth for three consumers:
  * render.js    - canvas preview renderer (stand-in font)
  * make_jsx.py  - After Effects project builder (the user's own font)
  * sfx.py       - sound-effect synthesis, one cue per visual event

usage: scene.py <work_dir> <out_dir>
"""
import json
import math
import os
import random
import sys
import zlib

FPS, W, H, DUR = 25, 1080, 1920, 14.88
NFRAMES = round(DUR * FPS)  # 372
BLUE, LBLUE, PALE, WHITE, BLACK = "#185090", "#267AD7", "#DCE8F7", "#FFFFFF", "#000000"
CYAN, MAGENTA = "#00E5FF", "#FF2D95"
HB = {"H": 0.61, "L": 0.59}   # Hebrew base height / em (stand-in font)
CAP = 0.714                   # Latin cap height / em
ASC, DESC = 0.82, 0.24        # glyph extent (em) used for glitch slice bands
SHADOW = {"type": "shadow", "color": BLACK, "op": 45, "dist": 8, "soft": 34, "dir": 180}

WORK, OUT = sys.argv[1], sys.argv[2]


def snap(t):
    return round(t * FPS) / FPS


def frame_times(t0, t1):
    """Frame times inside [t0, t1]."""
    a, b = math.ceil(t0 * FPS - 1e-6), math.floor(t1 * FPS + 1e-6)
    return [k / FPS for k in range(a, b + 1)]


# ------------------------------------------------------------------ easing
def e_linear(p): return p
def e_outExpo(p): return 1.0 if p >= 1 else 1 - 2 ** (-10 * p)
def e_inExpo(p): return 0.0 if p <= 0 else 2 ** (10 * p - 10)
def e_outCubic(p): return 1 - (1 - p) ** 3
def e_inCubic(p): return p ** 3
def e_inOutCubic(p): return 4 * p ** 3 if p < .5 else 1 - (-2 * p + 2) ** 3 / 2
def e_inOutSine(p): return -(math.cos(math.pi * p) - 1) / 2
def e_outQuad(p): return 1 - (1 - p) ** 2


def e_outBack(p, s=1.70158):
    c3 = s + 1
    return 1 + c3 * (p - 1) ** 3 + s * (p - 1) ** 2


def e_outBounce(p):
    n1, d1 = 7.5625, 2.75
    if p < 1 / d1:
        return n1 * p * p
    if p < 2 / d1:
        p -= 1.5 / d1
        return n1 * p * p + .75
    if p < 2.5 / d1:
        p -= 2.25 / d1
        return n1 * p * p + .9375
    p -= 2.625 / d1
    return n1 * p * p + .984375


EASE = {
    "linear": e_linear, "outExpo": e_outExpo, "inExpo": e_inExpo, "outCubic": e_outCubic,
    "inCubic": e_inCubic, "inOutCubic": e_inOutCubic, "inOutSine": e_inOutSine, "outQuad": e_outQuad, "inQuad": lambda p: p * p,
    "outBack": e_outBack, "outBack2": lambda p: e_outBack(p, 2.4), "outBack14": lambda p: e_outBack(p, 1.4),
    "outBounce": e_outBounce,
}


def lerp(a, b, p):
    if isinstance(a, (list, tuple)):
        return [lerp(x, y, p) for x, y in zip(a, b)]
    return a + (b - a) * p


def rnd(v):
    if isinstance(v, (list, tuple)):
        return [rnd(x) for x in v]
    return round(v, 3) if isinstance(v, float) else v


# ------------------------------------------------------------------ tracks
class Track:
    """Start value plus non-overlapping eased moves; exported as per-frame keys.

    Smooth tracks export linear keys (motion blur friendly); tracks with jumps
    export hold keys sampled once per frame.
    """

    def __init__(self, v0):
        self.v0 = v0
        self.moves = []  # (t0, t1, from|None, to, ease)
        self.jumps = False

    def move(self, t0, dur, v, ease="outExpo", frm=None):
        t0 = snap(t0)
        t1 = snap(t0 + dur)
        if t1 <= t0:
            t1 = t0 + 1 / FPS
        self.moves.append((t0, t1, frm, v, ease))
        return self

    def move_to(self, t0, t1, v, ease="outExpo", frm=None):
        return self.move(t0, snap(t1) - snap(t0), v, ease, frm)

    def jump(self, t, v):
        t = snap(t)
        self.moves.append((t, t, None, v, "linear"))
        self.jumps = True
        return self

    def at(self, t):
        v = self.v0
        for (t0, t1, frm, vt, ease) in sorted(self.moves, key=lambda m: (m[0], m[1])):
            if t >= t1 - 1e-9:
                v = vt
            elif t >= t0:
                a = frm if frm is not None else v
                v = lerp(a, vt, EASE[ease]((t - t0) / (t1 - t0)))
                break
            else:
                break
        return v

    def export(self):
        if not self.moves:
            return rnd(self.v0)
        ms = sorted(self.moves, key=lambda m: (m[0], m[1]))
        if self.jumps:
            times = frame_times(0, DUR)
            keys = []
            last = None
            for t in times:
                v = rnd(self.at(t))
                if v != last:
                    keys.append([round(t, 4), v])
                    last = v
            return {"k": keys, "h": 1}
        ts = set()
        for (t0, t1, _, _, _) in ms:
            ts.add(round(t0, 4))
            ts.add(round(t1, 4))
            for t in frame_times(t0, t1):
                ts.add(round(t, 4))
        times = sorted(ts)
        vals = [rnd(self.at(t)) for t in times]
        keys = []
        for i, (t, v) in enumerate(zip(times, vals)):
            prev_same = i > 0 and vals[i - 1] == v
            next_same = i < len(vals) - 1 and vals[i + 1] == v
            if prev_same and next_same:
                continue
            keys.append([t, v])
        if len(keys) == 1:
            return keys[0][1]
        return {"k": keys, "h": 0}


class Frames:
    """Explicit per-frame values (hold keys) - used for glitch / stepped motion."""

    def __init__(self, v0):
        self.v0 = v0
        self.vals = {}

    def set(self, t, v):
        self.vals[round(t * FPS)] = v
        return self

    def set_range(self, t0, t1, v):
        for k in range(round(t0 * FPS), round(t1 * FPS)):
            self.vals[k] = v
        return self

    def export(self):
        if not self.vals:
            return rnd(self.v0)
        keys, last = [], None
        for k in range(0, NFRAMES + 1):
            v = rnd(self.vals.get(k, last if last is not None else self.v0))
            if k not in self.vals and last is None:
                v = rnd(self.v0)
            if v != last:
                keys.append([round(k / FPS, 4), v])
                last = v
        return {"k": keys, "h": 1}


def ex(v):
    return v.export() if hasattr(v, "export") else rnd(v)


# ------------------------------------------------------------------ comps / layers
COMPS = {}
CUES = []


def cue(t, kind, **p):
    CUES.append(dict(t=round(t, 4), kind=kind, **p))


class Comp:
    def __init__(self, name, dur):
        self.name, self.dur, self.layers = name, dur, []
        COMPS[name] = self

    def add(self, **L):
        names = {l["name"] for l in self.layers}
        assert L["name"] not in names, L["name"]
        L.setdefault("in", 0.0)
        L.setdefault("out", self.dur)
        L["in"], L["out"] = round(snap(L["in"]), 4), round(snap(L["out"]), 4)
        for k in ("pos", "scale", "rot", "op"):
            if k in L:
                L[k] = ex(L[k])
        for fx in L.get("fx", []):
            for k, v in list(fx.items()):
                if hasattr(v, "export"):
                    fx[k] = ex(v)
        for it in L.get("items", []) + L.get("masks", []):
            for k, v in list(it.items()):
                if hasattr(v, "export"):
                    it[k] = ex(v)
        if "idx" in L:
            L["idx"] = ex(L["idx"])
        if "tm" in L:
            L["tm"] = ex(L["tm"])
        self.layers.append(L)
        return L

    def json(self):
        return {"name": self.name, "dur": self.dur, "w": W, "h": H, "fps": FPS, "layers": self.layers}


def text(comp, name, s, font, size, cx, cy, *, fill=WHITE, just="center", direction="rtl", stroke=None,
         sw=0, anims=None, shadow=False, parent=None, tin=0.0, tout=None, pos=None, scale=None,
         op=None, rot=None, clip=None, mb=True, src=None, blend="normal", masks=None, fx=None, track=0):
    """Text layer positioned by the visual centre (cx, cy) of the letters' base band.

    Layer space follows AE point text: origin on the baseline at the justification
    point; the anchor is lifted by half the base height so scaling happens around
    the visual centre.
    """
    hb = (CAP if direction == "ltr" else HB[font]) * size
    L = dict(name=name, type="text", text=s, font=font, size=size, fill=fill, stroke=stroke, sw=sw,
             just=just, dir=direction, track=track, anims=anims or [], mb=mb, blend=blend,
             anchor=[0, round(-hb / 2, 2)], pos=pos if pos is not None else [cx, cy],
             scale=scale if scale is not None else [100, 100], rot=rot if rot is not None else 0,
             op=op if op is not None else 100, parent=parent, fx=list(fx or []))
    if shadow:
        L["fx"].append(dict(SHADOW))
    if clip:
        L["clip"] = clip
    if src:
        L["src"] = src
    if masks:
        L["masks"] = masks
    L["in"] = tin
    L["out"] = tout if tout is not None else comp.dur
    return comp.add(**L)


def char_anim(props, t0, dur, stag, ease="outExpo", mode="in", by="char", order="fwd", step=None):
    return {"props": props, "sel": {"t0": round(snap(t0), 4), "dur": dur, "stag": stag, "ease": ease,
                                    "mode": mode, "by": by, "order": order, "step": step}}


def null(comp, name, cx, cy, *, pos=None, scale=None, rot=None, parent=None, tin=0.0, tout=None):
    return comp.add(name=name, type="null", anchor=[cx, cy], pos=pos if pos is not None else [cx, cy],
                    scale=scale if scale is not None else [100, 100], rot=rot if rot is not None else 0,
                    op=100, parent=parent, **{"in": tin, "out": tout if tout is not None else comp.dur})


def shape(comp, name, items, *, anchor=(0, 0), pos=(0, 0), scale=(100, 100), rot=0, op=100, parent=None,
          tin=0.0, tout=None, mb=True, blend="normal", fx=None, clip=None, masks=None):
    L = dict(name=name, type="shape", items=items, anchor=list(anchor),
             pos=pos if (hasattr(pos, "export") or isinstance(pos, dict)) else list(pos),
             scale=scale if (hasattr(scale, "export") or isinstance(scale, dict)) else list(scale), rot=rot, op=op,
             parent=parent,
             mb=mb, blend=blend, fx=list(fx or []))
    if clip:
        L["clip"] = clip
    if masks:
        L["masks"] = masks
    L["in"] = tin
    L["out"] = tout if tout is not None else comp.dur
    return comp.add(**L)


def rect_item(cx, cy, w, h, r=0, fill=None, stroke=None, sw=0, size=None, swt=None):
    it = {"kind": "rect", "c": [round(cx, 2), round(cy, 2)], "size": size if size is not None else [w, h],
          "r": r, "fill": fill, "stroke": stroke, "sw": swt if swt is not None else sw}
    return it


def ellipse_item(cx, cy, w, h, fill=None, stroke=None, sw=0, size=None, swt=None):
    return {"kind": "ellipse", "c": [cx, cy], "size": size if size is not None else [w, h], "fill": fill,
            "stroke": stroke, "sw": swt if swt is not None else sw}


def path_item(d, fill=None, stroke=None, sw=0, cap="round", join="round", evenodd=True):
    return {"kind": "path", "d": d, "fill": fill, "stroke": stroke, "sw": sw, "cap": cap, "join": join,
            "evenodd": evenodd}


def glow_item(cx, cy, w, h, color):
    """Soft feathered ellipse (AE: ellipse + gaussian blur of ~0.3 * min(w, h))."""
    return {"kind": "glow", "c": [cx, cy], "size": [w, h], "fill": color}


def word_width(s, font, size):
    """Rough advance-width estimate for layout decisions (stand-in font)."""
    adv = {"H": 0.70, "L": 0.58}[font]
    return len(s.replace(" ", "")) * adv * size + s.count(" ") * 0.25 * size


# ------------------------------------------------------------------ data
words = {w["w"]: w["snap"] for w in json.load(open(os.path.join(WORK, "words.json")))}
WT = dict(words)
WT["עדכון"] = 0.04
WT["חדש"] = 0.44
VO_END = 9.50
ENV = json.load(open(os.path.join(WORK, "vo_env.json")))
LOGO = json.load(open(os.path.join(WORK, "logo", "logo.json")))


def jpeg_size(path):
    """(width, height) from a JPEG's SOF marker."""
    with open(path, "rb") as f:
        data = f.read()
    i = 2
    while i < len(data):
        marker, seg = data[i + 1], int.from_bytes(data[i + 2:i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big")
        i += 2 + seg
    raise ValueError("no SOF in " + path)


def env_at(t):
    i = int(round(t * 100))
    return ENV[i] if 0 <= i < len(ENV) else 0.0


# cut points of the supplied edit
T_CARD, T_CARD_END, T_GUITAR, T_SAX, T_SINGER1 = 1.08, 2.44, 2.84, 3.20, 3.88
T_SITE, T_SINGER2, T_DIS, T_END = 5.32, 6.64, 9.72, 9.88

PART1 = Comp("PART1", T_END)
MAIN = Comp("MAIN", DUR)

# ======================================================================================
# PART1  (0 - 9.72): footage + captions
# ======================================================================================
null(PART1, "SHAKE", W / 2, H / 2, pos=(
    Track([540, 960])
))
shake = Frames([540, 960])
shake_seed = random.Random(7)


def add_shake(t, amp, frames):
    for k in range(frames):
        a = amp * (1 - k / frames)
        shake.set(t + k / FPS, [540 + shake_seed.uniform(-a, a), 960 + shake_seed.uniform(-a, a)])
    shake.set(t + frames / FPS, [540, 960])


add_shake(2.96, 7, 4)      # "עכשיו" lands
add_shake(9.04, 16, 6)     # "בסט" impact
PART1.layers[-1]["pos"] = shake.export()

# ---- footage
fsc = Track([100, 100])
fsc.move_to(0.0, 1.08, [103, 103], "linear")
fsc.move_to(1.12, 2.40, [100, 100], "linear")
fsc.move_to(T_CARD_END, T_SINGER1 - 0.04, [108, 108], "linear")
fsc.move_to(T_SINGER1 - 0.04, T_SINGER1, [100, 100], "linear")
fsc.move_to(T_SINGER1, T_SITE - 0.12, [104, 104], "linear")
fsc.move_to(5.40, 6.60, [125, 125], "linear")
fsc.move(T_SINGER2, 0.28, [100, 100], "outExpo")
fsc.move_to(T_SINGER2 + 0.28, 9.0, [105, 105], "linear")
fsc.move(9.04, 0.10, [110, 110], "outCubic")
fsc.move_to(9.14, T_DIS, [107, 107], "inOutSine")
fpos = Track([540, 960])
fpos.move_to(5.22, T_SITE, [-560, 960], "inQuad")
fpos.move_to(5.40, 6.60, [540, 960], "linear")
fblur = Track(0)
fblur.jump(T_GUITAR, 44)                       # guitar / sax shots: no recognisable faces behind the phone
fblur.move(T_SINGER1, 0.18, 20, "outCubic", frm=0)
fblur.move_to(5.40, 6.60, 22, "linear")
fblur.move_to(T_SINGER2, 7.40, 0, "inOutSine")
fblur.move(7.96, 0.20, 16, "outCubic")         # crowd softens behind the organ panel
fblur.move(8.96, 0.14, 0, "outCubic")          # ... and snaps back into focus on "בסט"
PART1.add(name="whip_backdrop", type="solid", color="#0B2F63", w=W, h=H, anchor=[540, 960], pos=[540, 960],
          scale=[100, 100], rot=0, op=100, parent=None, mb=False, **{"in": 5.16, "out": T_SITE})
PART1.add(name="footage", type="footage", src="footage", w=W, h=H, anchor=[540, 960], pos=fpos, scale=fsc,
          rot=0, op=100, parent="SHAKE", mb=True, fx=[{"type": "blur", "amt": fblur}],
          **{"in": 0.0, "out": T_DIS})
cue(0.64, "usb_click")

darken = Track(0)
darken.move_to(1.20, 2.40, 26, "linear")
darken.move(T_SINGER1, 0.18, 34, "outCubic")
darken.move_to(T_SINGER2, 7.40, 24, "inOutSine")
darken.move(7.96, 0.20, 40, "outCubic")
darken.move(8.96, 0.14, 24, "outCubic")
PART1.add(name="darken", type="solid", color=BLACK, w=W, h=H, anchor=[540, 960], pos=[540, 960],
          scale=[100, 100], rot=0, op=darken, parent=None, mb=False, **{"in": 0.0, "out": T_DIS})

# ======================================================================================
# A  0.00-1.08  USB shot: "עדכון" / "חדש"
# ======================================================================================
haze_op = Track(0).move(0.0, 0.16, 62, "outCubic").move(0.94, 0.12, 0, "inCubic")
shape(PART1, "A_haze", [glow_item(540, 1175, 980, 620, WHITE)], op=haze_op, tin=0.0, tout=T_CARD, mb=False)

null(PART1, "A_GRP", 0, 0, pos=Track([0, 0]).move(0.94, 0.12, [0, -130], "inCubic"), tin=0.0, tout=T_CARD)
op_exit = Track(100).move(0.94, 0.12, 0, "inCubic")
text(PART1, "A_adkon", "עדכון", "H", 210, 540, 1030, fill=BLUE, parent="A_GRP", tin=0.0, tout=T_CARD,
     op=op_exit, clip=[0, 0, 1080, 1030 + 0.305 * 210 + 0.2 * 210 + 6],
     anims=[char_anim({"pos": [0, 120], "op": 0}, 0.0, 0.30, 0.035, "outExpo")])
cue(0.0, "air", dur=0.26, pre=0.0, gain=-16, pan=0.25, to_pan=-0.1)
cue(0.12, "click_hi", gain=-17, body=True)

pulse = Track([125, 125]).move(0.40, 0.16, [100, 100], "outExpo")
pulse.move(0.64, 0.06, [108, 108], "outCubic").move(0.70, 0.14, [100, 100], "inOutCubic")
op_in = Track(0).move(0.40, 0.08, 100, "outCubic").move(0.94, 0.12, 0, "inCubic")
text(PART1, "A_hadash_outline", "חדש", "H", 230, 540, 1250, fill=None, stroke=BLUE, sw=7, parent="A_GRP",
     tin=0.0, tout=T_CARD, scale=pulse, op=op_in)
fill_op = Track(0).move(0.64, 0.06, 100, "outCubic").move(0.94, 0.12, 0, "inCubic")
text(PART1, "A_hadash_fill", "חדש", "H", 230, 540, 1250, fill=BLUE, parent="A_GRP", tin=0.0, tout=T_CARD,
     scale=pulse, op=fill_op)
cue(0.40, "click_hi", gain=-18)
cue(0.64, "click_hi", gain=-15, body=True, pitch=0.95)
cue(T_CARD, "air", dur=0.20, pre=0.12, gain=-15, pan=-0.3, to_pan=0.3)

# ======================================================================================
# B  1.08-2.44  brand card on white: "מבית MOTTI רוזנפלד"
# ======================================================================================
PART1.add(name="B_white", type="solid", color=WHITE, w=W, h=H, anchor=[540, 960], pos=[540, 960],
          scale=[100, 100], rot=0, op=100, parent=None, mb=False, **{"in": T_CARD, "out": T_CARD_END})
null(PART1, "CARD", 540, 960, scale=Track([100, 100]).move_to(T_CARD, T_CARD_END, [103.5, 103.5], "inOutSine"),
     tin=T_CARD, tout=T_CARD_END)

# corner brackets (viewfinder) - same geometry as the reference card
def bracket_path(cx, cy, sx, sy, arm=128, r=38):
    k = 0.5523 * r
    x0, y0 = cx, cy
    a = (x0, y0 + sy * arm)
    b = (x0, y0 + sy * r)
    c = (x0 + sx * r, y0)
    d = (x0 + sx * arm, y0)
    return "M%.1f %.1f L%.1f %.1f C%.1f %.1f %.1f %.1f %.1f %.1f L%.1f %.1f" % (
        a[0], a[1], b[0], b[1], b[0], b[1] - sy * k, c[0] - sx * k, c[1], c[0], c[1], d[0], d[1])


br_items = [path_item(bracket_path(115, 127, 1, 1), stroke=BLUE, sw=14, evenodd=False),
            path_item(bracket_path(965, 127, -1, 1), stroke=BLUE, sw=14, evenodd=False),
            path_item(bracket_path(115, 1793, 1, -1), stroke=BLUE, sw=14, evenodd=False),
            path_item(bracket_path(965, 1793, -1, -1), stroke=BLUE, sw=14, evenodd=False)]
for it in br_items:
    it["fill"] = None
br_scale = Track([150, 150]).move(T_CARD, 0.24, [100, 100], "outExpo")
br_scale.move_to(T_CARD + 0.24, T_CARD_END, [98.8, 98.8], "linear")
shape(PART1, "B_brackets", br_items, anchor=(540, 960), pos=(540, 960), scale=br_scale,
      op=Track(0).move(T_CARD, 0.08, 100, "linear"), tin=T_CARD, tout=T_CARD_END)
cue(T_CARD, "shutter", gain=-14)
for k in range(4):
    cue(T_CARD + 0.10 + k * 0.04, "click_hi", gain=-23, pitch=1.0 + 0.06 * k)

text(PART1, "B_mibeit", "מבית", "H", 135, 706, 776 - 0.305 * 135, fill=BLUE, just="right", parent="CARD",
     tin=T_CARD, tout=T_CARD_END,
     anims=[char_anim({"pos": [0, -80], "op": 0}, T_CARD, 0.24, 0.03, "outBack")])

# logo build (traced vector of the MOTTI Rosenfeld logo)
logo_t = {"M": 1.18, "O": 1.24, "T1": 1.30, "T2": 1.35, "i": 1.40}
for gname, t0 in logo_t.items():
    g = LOGO["groups"][gname]
    bx = (g["bbox"][0] + g["bbox"][2]) / 2
    by = g["bbox"][3]
    sc = Track([25, 25]).move(t0, 0.24, [100, 100], "outBack2")
    ps = Track([bx, by + 46]).move(t0, 0.24, [bx, by], "outExpo")
    shape(PART1, "B_logo_" + gname, [path_item(g["d"], fill=BLUE, evenodd=True)], anchor=(bx, by), pos=ps,
          scale=sc, op=Track(0).move(t0, 0.07, 100, "linear"), parent="CARD", tin=T_CARD, tout=T_CARD_END)
    cue(t0, "click_hi", gain=-18, pitch={"M": 0.9, "O": 0.95, "T1": 1.0, "T2": 1.05, "i": 1.1}[gname])
g = LOGO["groups"]["dot"]
dx, dy = (g["bbox"][0] + g["bbox"][2]) / 2, (g["bbox"][1] + g["bbox"][3]) / 2
shape(PART1, "B_logo_dot", [path_item(g["d"], fill=BLUE, evenodd=True)], anchor=(dx, dy),
      pos=Track([dx, dy - 170]).move(1.47, 0.34, [dx, dy], "outBounce"),
      op=Track(0).move(1.47, 0.04, 100, "linear"), parent="CARD", tin=T_CARD, tout=T_CARD_END)
cue(1.47 + 0.34 * 0.36, "click_hi", gain=-17, body=True, pitch=1.15)
for i, letter in enumerate(LOGO["ros"]):
    t0 = 1.66 + i * 0.024
    b = letter["bbox"]
    cxl, cyl = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    shape(PART1, "B_ros_%d" % i, [path_item(letter["d"], fill=BLUE, evenodd=True)], anchor=(cxl, cyl),
          pos=Track([cxl - 16, cyl]).move(t0, 0.16, [cxl, cyl], "outCubic"),
          op=Track(0).move(t0, 0.10, 100, "linear"), parent="CARD", tin=T_CARD, tout=T_CARD_END)
    cue(t0, "click_hi", gain=-30, pitch=1.2 + 0.03 * i)
text(PART1, "B_rozenfeld", "רוזנפלד", "H", 145, 518, 1222 - 0.305 * 145, fill=BLUE, parent="CARD",
     tin=T_CARD, tout=T_CARD_END, clip=[0, 0, 1080, 1222 + 14],
     anims=[char_anim({"pos": [0, 150], "op": 0}, 1.57, 0.28, 0.025, "outExpo")])
cue(1.57, "air", dur=0.18, pre=0.08, gain=-20, pan=0.3, to_pan=-0.3)
cue(2.05, "sparkle", dur=0.40, gain=-25)

# ======================================================================================
# C  2.44-3.88  "היכנסו עכשיו לאתר": entering the live site on a phone
#   The hands shot (2.44-2.84) stays sharp; the guitar / sax shots behind the phone are blurred
#   and tinted so no face is recognisable. The site itself (site/enter, live capture) is sharp.
# ======================================================================================
C_ZOOM = (540, 1350)                     # zoom-through point: centre of the visible screen
cgrp_sc = Track([100, 100]).move(3.64, 0.24, [300, 300], "inQuad")      # dive into the screen
null(PART1, "C_GRP", C_ZOOM[0], C_ZOOM[1], scale=cgrp_sc, tin=T_CARD_END, tout=T_SINGER1, parent="SHAKE")
c_txt_out = lambda: Track(100).move(3.68, 0.12, 0, "inCubic")

PART1.add(name="C_tint", type="solid", color="#0B2F63", w=W, h=H, anchor=[540, 960], pos=[540, 960],
          scale=[100, 100], rot=0, op=40, parent=None, mb=False, **{"in": T_GUITAR, "out": T_SINGER1})

op = Track(0).move(T_CARD_END, 0.08, 100, "linear").move(3.68, 0.12, 0, "inCubic")
text(PART1, "C_hikansu", "היכנסו", "L", 108, 540, 272, parent="C_GRP", tin=T_CARD_END, tout=T_SINGER1,
     shadow=True, op=op, pos=Track([720, 272]).move(T_CARD_END, 0.20, [540, 272], "outExpo"))
cue(T_CARD_END, "air", dur=0.18, pre=0.06, gain=-17, pan=0.5, to_pan=0.0)
cue(2.50, "click_hi", gain=-20)
cue(T_GUITAR, "air", dur=0.24, pre=0.08, gain=-15, pan=0.0, to_pan=0.2, dir="down")

op = Track(0).move(2.84, 0.06, 100, "linear").move(3.68, 0.12, 0, "inCubic")
text(PART1, "C_achshav", "עכשיו", "H", 196, 540, 440, parent="C_GRP", tin=2.84, tout=T_SINGER1, shadow=True,
     op=op, pos=Track([540, 330]).move(2.84, 0.16, [540, 440], "outBack2"),
     scale=Track([118, 118]).move(2.84, 0.16, [100, 100], "outExpo"))
cue(2.96, "click_hi", gain=-14, body=True)
cue(T_SAX, "air", dur=0.16, pre=0.06, gain=-19, pan=-0.3, to_pan=0.2)

text(PART1, "C_laatar", "לאתר", "H", 196, 540, 628, parent="C_GRP", tin=3.18, tout=T_SINGER1, shadow=True,
     op=c_txt_out(), clip=[0, 0, 1080, 628 + 0.305 * 196 + 12],
     anims=[char_anim({"pos": [0, 140], "op": 0}, 3.18, 0.26, 0.03, "outExpo")])
cue(3.22, "click_hi", gain=-15, body=True, pitch=1.05)

# ---- phone (brand-light body) rising from below; browser chrome + live site inside
PH_C, PH_W, PH_H = (540, 1440), 640, 1340          # body (bottom runs off-frame)
SCR = (236, 786, 844, 2094)                        # screen rect
CHROME_B = 918                                     # status bar 786-826, address bar 826-918
SITE_SC = (SCR[2] - SCR[0]) / 780 * 100            # 780 px wide capture -> 608 px screen
null(PART1, "C_PHONE", PH_C[0], PH_C[1], parent="C_GRP",
     pos=Track([PH_C[0], PH_C[1] + 900]).move(T_GUITAR, 0.30, list(PH_C), "outExpo"),
     rot=Track(8).move(T_GUITAR, 0.30, 0, "outExpo"), tin=T_GUITAR, tout=T_SINGER1)
shape(PART1, "C_phone_body", [rect_item(PH_C[0], PH_C[1], PH_W, PH_H, r=72, fill="#EEF3FA")],
      parent="C_PHONE", op=100, tin=T_GUITAR, tout=T_SINGER1, fx=[dict(SHADOW, op=60, dist=26, soft=70)])
scr_c = ((SCR[0] + SCR[2]) / 2, (SCR[1] + SCR[3]) / 2)
shape(PART1, "C_phone_screen", [
    rect_item(scr_c[0], scr_c[1], SCR[2] - SCR[0], SCR[3] - SCR[1], r=56, fill="#EEF2F7")],
      parent="C_PHONE", op=100, tin=T_GUITAR, tout=T_SINGER1)

nenter = len([f for f in os.listdir(os.path.join(WORK, "site", "enter")) if f.endswith(".jpg")])
site_idx = Track(0).move_to(3.50, 3.86, 20, "outCubic")       # a short flick: 160 css px
PART1.add(name="C_site", type="seq", srcs=["site/enter/e%02d.jpg" % k for k in range(nenter)],
          w=780, h=1688, anchor=[390, 0], pos=[540, CHROME_B], scale=[SITE_SC, SITE_SC], rot=0,
          op=Track(0).move(3.40, 0.06, 100, "linear"), parent="C_PHONE",
          mb=True, idx=site_idx, masks=[{"rect": [0, 0, 780, (SCR[3] - CHROME_B) / SITE_SC * 100]}],
          **{"in": 3.40, "out": T_SINGER1})
cue(3.40, "shutter", gain=-17)
for k in range(2):
    cue(3.52 + k * 0.06, "click_hi", gain=-23 - k, pitch=1.2)

# status bar + address bar (drawn over the page, like a real browser)
chrome_c = (scr_c[0], (SCR[1] + CHROME_B) / 2)
shape(PART1, "C_chrome", [
    rect_item(chrome_c[0], chrome_c[1], SCR[2] - SCR[0], CHROME_B - SCR[1], r=56, fill="#F2F5FA"),
    rect_item(chrome_c[0], (chrome_c[1] + CHROME_B) / 2, SCR[2] - SCR[0], (CHROME_B - chrome_c[1]), fill="#F2F5FA"),
    rect_item(chrome_c[0], CHROME_B - 1, SCR[2] - SCR[0], 2, fill="#DCE3EE"),
    rect_item(540, 806, 118, 30, r=15, fill="#0B1220"),
    rect_item(540, 872, 560, 62, r=31, fill=WHITE, stroke="#D5DEEA", sw=2),
    rect_item(288, 877, 18, 14, r=3, fill="#5B6B85"),
    path_item("M282.5 870 L282.5 866 C282.5 857.5 293.5 857.5 293.5 866 L293.5 870", stroke="#5B6B85", sw=3,
              cap="round"),
], parent="C_PHONE", op=100, tin=T_GUITAR, tout=T_SINGER1)

URL = "mottirozenfeld.com"
type_t0, type_t1 = 2.98, 3.20
type_step = (type_t1 - type_t0) / len(URL)
text(PART1, "C_url", URL, "H", 30, 308, 872, fill="#1B2A44", just="left", direction="ltr", parent="C_PHONE",
     tin=T_GUITAR, tout=T_SINGER1, op=100,
     anims=[char_anim({"op": 0}, type_t0, 0.0, type_step, "linear", mode="in", step=type_step)])
for k in range(0, len(URL), 2):
    cue(type_t0 + k * type_step, "click_hi", gain=-17, pitch=0.9 + 0.2 * random.Random(k).random())

# "go" button on the address bar, tapped on "לאתר"
GO = (790, 872)
go_sc = Track([0, 0]).move(3.16, 0.12, [100, 100], "outBack2").move(3.28, 0.04, [84, 84], "outCubic")
go_sc.move(3.32, 0.10, [100, 100], "outBack")
shape(PART1, "C_go", [ellipse_item(GO[0], GO[1], 46, 46, fill=LBLUE),
                      path_item("M%.1f %.1f L%.1f %.1f M%.1f %.1f L%.1f %.1f L%.1f %.1f" % (
                          GO[0] - 10, GO[1], GO[0] + 9, GO[1], GO[0] + 1, GO[1] - 8, GO[0] + 9, GO[1],
                          GO[0] + 1, GO[1] + 8), stroke=WHITE, sw=4, cap="round")],
      anchor=GO, pos=GO, scale=go_sc, parent="C_PHONE", op=100, tin=3.16, tout=T_SINGER1)
cue(3.16, "tap", gain=-21, pitch=1.3)
touch_op = Track(0).move(3.22, 0.05, 55, "linear").move(3.34, 0.08, 0, "linear")
touch_sc = Track([125, 125]).move(3.22, 0.06, [100, 100], "outCubic").move(3.28, 0.04, [82, 82], "outCubic")
shape(PART1, "C_touch", [ellipse_item(GO[0], GO[1], 74, 74, fill="#3A4A63")], anchor=GO, pos=GO, scale=touch_sc,
      op=touch_op, parent="C_PHONE", tin=3.20, tout=3.44)
shape(PART1, "C_tap_ripple", [ellipse_item(GO[0], GO[1], 0, 0, stroke=LBLUE,
                                           size=Track([46, 46]).move(3.28, 0.24, [112, 112], "outCubic"),
                                           swt=Track(6).move(3.28, 0.24, 1, "outCubic"))],
      op=Track(0).jump(3.28, 90).move(3.32, 0.20, 0, "outCubic"), parent="C_PHONE", tin=3.28, tout=3.54)
cue(3.28, "tap", gain=-13)

# loading bar under the address bar
shape(PART1, "C_loading", [rect_item(scr_c[0], CHROME_B - 2, SCR[2] - SCR[0], 5, fill=LBLUE)],
      anchor=(SCR[0], CHROME_B - 2), pos=(SCR[0], CHROME_B - 2),
      scale=Track([0, 100]).move(3.30, 0.10, [62, 100], "outCubic").move(3.40, 0.08, [100, 100], "inOutCubic"),
      op=Track(100).move(3.48, 0.06, 0, "linear"), parent="C_PHONE", tin=3.30, tout=3.56)
cue(3.46, "riser_thin", dur=0.16, pre=0.16, gain=-24)
cue(T_SINGER1, "air", dur=0.30, pre=0.24, gain=-13, pan=-0.2, to_pan=0.2)

# ======================================================================================
# D  3.88-5.32  singer: "והאזינו לעדכון החדש" + VO-driven sound bars + echo stack
# ======================================================================================
null(PART1, "D_GRP", 540, 960, pos=Track([540, 960]).move_to(5.22, T_SITE, [-560, 960], "inQuad"),
     tin=T_SINGER1, tout=T_SITE)
text(PART1, "D_vehaazinu", "והאזינו", "L", 132, 540, 690, parent="D_GRP", tin=T_SINGER1, tout=T_SITE,
     shadow=True, op=Track(0).move(T_SINGER1, 0.08, 100, "linear"),
     pos=Track([540, 730]).move(T_SINGER1, 0.18, [540, 690], "outExpo"))

NB = 27
brng = random.Random(3)
bar_prof = [0.42 + 0.58 * math.exp(-((i - 13) / 7.0) ** 2) + brng.uniform(-0.08, 0.08) for i in range(NB)]
for i in range(NB):
    x = 540 + (i - 13) * 26
    t_on = 3.90 + abs(i - 13) * 0.008
    vals = {}
    for t in frame_times(T_SINGER1, T_SITE):
        grow = e_outBack(min(max((t - t_on) / 0.14, 0), 1)) if t >= t_on else 0
        e = env_at(t - abs(i - 13) * 0.014)
        h = 14 + (124 - 14) * bar_prof[i] * (0.18 + 0.82 * e)
        vals[round(t, 4)] = [100, round(100 * grow * h / 124, 2)]
    trk = {"k": [[t, v] for t, v in sorted(vals.items())], "h": 0}
    shape(PART1, "D_bar_%02d" % i, [rect_item(x, 822, 14, 124, r=7, fill=LBLUE)], anchor=(x, 822),
          pos=(x, 822), scale=trk, parent="D_GRP", tin=T_SINGER1, tout=T_SITE, mb=True,
          fx=[{"type": "glow", "color": LBLUE, "op": 70, "soft": 22}])
cue(3.90, "click_hi", gain=-18)

text(PART1, "D_laadkon", "לעדכון", "H", 222, 540, 1010, parent="D_GRP", tin=4.14, tout=T_SITE, shadow=True,
     clip=[0, 0, 1080, 1010 + 0.305 * 222 + 0.19 * 222 + 10],
     anims=[char_anim({"pos": [0, 165], "op": 0}, 4.14, 0.26, 0.03, "outExpo")])
cue(4.16, "click_hi", gain=-15, body=True)

for k in (3, 2, 1):
    t0 = 4.72 + (k - 1) * 0.07
    y0, y1 = 1245 + 84 * (k - 1), 1245 + 84 * k
    text(PART1, "D_hechadash_echo%d" % k, "החדש", "H", 262, 540, y1, parent="D_GRP", tin=t0, tout=T_SITE,
         op=Track(0).move(t0, 0.06, [52, 30, 15][k - 1], "linear"),
         pos=Track([540, y0]).move(t0, 0.12, [540, y1], "outCubic"))
text(PART1, "D_hechadash", "החדש", "H", 262, 540, 1245, parent="D_GRP", tin=4.58, tout=T_SITE, shadow=True,
     op=Track(0).move(4.58, 0.06, 100, "linear"),
     scale=Track([55, 55]).move(4.58, 0.20, [100, 100], "outBack2"))
cue(4.62, "click_hi", gain=-13, body=True, pitch=0.9)
for k in range(3):
    cue(4.72 + 0.07 * k, "click_hi", gain=-19 - 2 * k, pitch=1.0 + 0.08 * k)
cue(T_SITE, "air", dur=0.26, pre=0.14, gain=-14, pan=0.3, to_pan=-0.6)

# ======================================================================================
# E  5.32-6.64  website: "תוכלו לדפדף בין התכנים" (scrolling site + set-card carousel)
# ======================================================================================
PART1.add(name="E_base", type="solid", color="#0B2F63", w=W, h=H, anchor=[540, 960], pos=[540, 960],
          scale=[100, 100], rot=0, op=100, parent=None, mb=False, **{"in": T_SITE, "out": T_SINGER2})
egrp_pos = Track([1060, 960]).move(T_SITE, 0.16, [540, 960], "outExpo")
null(PART1, "E_GRP", 540, 960, pos=egrp_pos,
     scale=Track([100, 100]).move_to(6.50, T_SINGER2, [78, 78], "inQuad"), tin=T_SITE, tout=T_SINGER2)
PART1.add(name="E_site_bg", type="image", src="site/site_bg.png", w=W, h=H, anchor=[540, 960],
          pos=Track([540, 980]).move_to(T_SITE, T_SINGER2, [540, 900], "linear"), scale=[114, 114], rot=0,
          op=100, parent="E_GRP", mb=True, fx=[{"type": "blur", "amt": 26}], **{"in": T_SITE, "out": T_SINGER2})
PART1.add(name="E_tint", type="solid", color="#0B2F63", w=W, h=H, anchor=[540, 960], pos=[540, 960],
          scale=[130, 130], rot=0, op=58, parent="E_GRP", mb=True, **{"in": T_SITE, "out": T_SINGER2})

# phone card with the site scroll recording
null(PART1, "E_PHONE", 540, 1250, parent="E_GRP",
     pos=Track([540, 1340]).move(T_SITE, 0.20, [540, 1250], "outExpo").move_to(5.98, 6.12, [-600, 1250], "inExpo"),
     rot=Track(-7).move(T_SITE, 0.20, 0, "outExpo").move_to(5.98, 6.12, 9, "inExpo"), tin=T_SITE, tout=6.14)
shape(PART1, "E_phone_frame", [rect_item(540, 1250, 606, 1068, r=50, fill="#EEF3FA")], parent="E_PHONE",
      tin=T_SITE, tout=6.14, fx=[dict(SHADOW, op=55, dist=26, soft=60)])
nscroll = len(os.listdir(os.path.join(WORK, "site", "scroll")))
idx = Track(0).move_to(5.36, 6.02, nscroll - 1, "linear")
PART1.add(name="E_phone_screen", type="seq", srcs=["site/scroll/s%02d.jpg" % (k + 1) for k in range(nscroll)],
          w=720, h=1280, anchor=[360, 640], pos=[540, 1250], scale=[82.5, 82.5], rot=0, op=100, parent="E_PHONE",
          mb=True, idx=idx, masks=[{"rect": [0, 0, 720, 1280], "r": 52}], **{"in": T_SITE, "out": 6.14})
for k in range(6):
    cue(5.42 + k * 0.10, "click_hi", gain=-27, pitch=1.2)

op = Track(0).move(5.30, 0.10, 100, "linear").move(5.98, 0.10, 0, "inCubic")
text(PART1, "E_tuchlu", "תוכלו", "L", 112, 540, 360, parent="E_GRP", tin=T_SITE, tout=6.10, shadow=True, op=op,
     pos=Track([540, 392]).move(5.30, 0.16, [540, 360], "outExpo").move(5.98, 0.10, [540, 300], "inCubic"))
cue(5.30, "click_hi", gain=-19)
op = Track(100).move(5.98, 0.10, 0, "inCubic")
text(PART1, "E_ledafdef", "לדפדף", "H", 222, 540, 560, parent="E_GRP", tin=5.60, tout=6.10, shadow=True, op=op,
     pos=Track([540, 560]).move(5.98, 0.10, [540, 500], "inCubic"),
     anims=[char_anim({"scale": [0, 100], "op": 0}, 5.62, 0.20, 0.035, "outBack14")])
for k in range(5):
    cue(5.62 + k * 0.035, "click_hi", gain=-19 - k, pitch=1.0 + 0.05 * k)
op = Track(0).move(6.00, 0.10, 100, "linear")
text(PART1, "E_bein", "בין", "L", 112, 540, 360, parent="E_GRP", tin=6.00, tout=T_SINGER2, shadow=True, op=op,
     pos=Track([540, 392]).move(6.00, 0.16, [540, 360], "outExpo"))
text(PART1, "E_hatchanim", "התכנים", "H", 222, 540, 560, parent="E_GRP", tin=6.22, tout=T_SINGER2, shadow=True,
     clip=[0, 0, 1080, 560 + 0.305 * 222 + 14],
     anims=[char_anim({"pos": [0, 165], "op": 0}, 6.22, 0.26, 0.03, "outExpo")])
cue(6.00, "click_hi", gain=-20)
cue(6.24, "click_hi", gain=-15, body=True, pitch=1.05)

# set-card carousel
cards = [("pro_master", 434, 527), ("dance_dj", 432, 523), ("live_style", 404, 487), ("pro_master", 434, 527)]
slot_x = {-2: -470, -1: 40, 0: 540, 1: 1040, 2: 1560}
slot_sc = {-2: 92, -1: 100, 0: 126, 1: 100, 2: 92}
for k, (nm, cw, ch) in enumerate(cards):
    s0 = k - 1          # slot after fly-in
    s1 = s0 - 1         # slot after the swipe
    t0 = 6.00 + 0.035 * k
    if k < 3:
        px = Track([1700 + 160 * k, 1250]).move(t0, 0.26, [slot_x[s0], 1250], "outExpo")
        sc = Track([slot_sc[s0], slot_sc[s0]])
    else:
        px = Track([slot_x[2], 1250])
        sc = Track([slot_sc[2], slot_sc[2]])
    px.move(6.30, 0.18, [slot_x[max(s1, -2)], 1250], "inOutCubic")
    sc.move(6.30, 0.18, [slot_sc[max(s1, -2)]] * 2, "inOutCubic")
    PART1.add(name="E_card_%d" % k, type="image", src="site/card_%s.png" % nm, w=cw, h=ch,
              anchor=[cw / 2, ch / 2], pos=px, scale=sc, rot=0, op=100, parent="E_GRP", mb=True,
              fx=[dict(SHADOW, op=50, dist=22, soft=44)], **{"in": 6.00, "out": T_SINGER2})
    if k < 3:
        cue(t0 + 0.06, "air", dur=0.14, pre=0.06, gain=-22, pan=0.6, to_pan=0.0)
cue(6.40, "air", dur=0.20, pre=0.10, gain=-17, pan=0.5, to_pan=-0.5)
cue(T_SINGER2, "air", dur=0.18, pre=0.10, gain=-16, dir="down")

# ======================================================================================
# F  6.64-9.72  singer: play button "להאזין" / "ולהתרשם" / "מכל מה" / "שנוסף" / "בסט"
# ======================================================================================
null(PART1, "F_TXT", 540, 960, pos=Track([540, 960]).move(8.86, 0.12, [540, 720], "inExpo"),
     scale=Track([100, 100]).move(8.86, 0.12, [90, 90], "inExpo"), tin=T_SINGER2, tout=T_DIS)
# group 1 ("להאזין ולהתרשם") hands over to group 2 ("מכל מה שנוסף") - both sit low, over the crowd,
# so the singer's face stays clear
null(PART1, "F_G1", 540, 960, parent="F_TXT", pos=Track([540, 960]).move(7.94, 0.08, [540, 880], "outCubic"),
     tin=T_SINGER2, tout=8.10)
f_out = lambda: Track(100).move(8.86, 0.12, 0, "inExpo")
g1_out = lambda: Track(100).move(7.94, 0.08, 0, "outCubic")

# play button (circle + triangle) - AE keeps it left of the word via an expression
pb_c = (292, 1010)
pb_sc = Track([0, 0]).move(6.72, 0.14, [100, 100], "outBack2").move(6.86, 0.05, [86, 86], "outCubic")
pb_sc.move(6.91, 0.10, [100, 100], "outBack")
null(PART1, "F_PLAY", pb_c[0], pb_c[1], parent="F_G1", scale=pb_sc, tin=6.70, tout=8.10)
PART1.layers[-1]["ae_left_of"] = {"layer": "F_lehaazin", "gap": 92}
op = Track(0).move(6.72, 0.05, 100, "linear").move(7.94, 0.08, 0, "outCubic")
shape(PART1, "F_play_btn", [ellipse_item(pb_c[0], pb_c[1], 118, 118, fill=BLUE, stroke=WHITE, sw=5),
                            path_item("M%.1f %.1f L%.1f %.1f L%.1f %.1f Z" % (pb_c[0] - 15, pb_c[1] - 24,
                                                                         pb_c[0] + 25, pb_c[1],
                                                                         pb_c[0] - 15, pb_c[1] + 24),
                                      fill=WHITE, evenodd=False)],
      parent="F_PLAY", op=op, tin=6.70, tout=8.10, fx=[dict(SHADOW, op=40)])
ring_size = Track([118, 118]).move(6.88, 0.42, [330, 330], "outCubic")
ring_sw = Track(6).move(6.88, 0.42, 1, "outCubic")
shape(PART1, "F_play_ripple", [ellipse_item(pb_c[0], pb_c[1], 0, 0, stroke=WHITE, size=ring_size, swt=ring_sw)],
      parent="F_PLAY", op=Track(0).jump(6.88, 85).move(6.92, 0.38, 0, "outCubic"), tin=6.86, tout=7.40, mb=True)
cue(6.80, "click_hi", gain=-19)
cue(6.86, "tap", gain=-14)

text(PART1, "F_lehaazin", "להאזין", "L", 142, 600, 1010, parent="F_G1", tin=6.70, tout=8.10, shadow=True,
     op=Track(0).move(6.72, 0.08, 100, "linear").move(7.94, 0.08, 0, "outCubic"),
     pos=Track([668, 1010]).move(6.72, 0.20, [600, 1010], "outExpo"))

NB2 = 31
for i in range(NB2):
    x = 600 + (i - 15) * 16
    t_on = 6.90 + i * 0.012
    vals = {}
    for t in frame_times(6.86, 8.10):
        grow = e_outBack(min(max((t - t_on) / 0.12, 0), 1)) if t >= t_on else 0
        e = env_at(t - abs(i - 15) * 0.012)
        h = 10 + (92 - 10) * (0.35 + 0.65 * math.exp(-((i - 15) / 9.0) ** 2)) * (0.15 + 0.85 * e)
        vals[round(t, 4)] = [100, round(100 * grow * h / 92, 2)]
    shape(PART1, "F_wave_%02d" % i, [rect_item(x, 1122, 9, 92, r=4.5, fill=WHITE)], anchor=(x, 1122),
          pos=(x, 1122), scale={"k": [[t, v] for t, v in sorted(vals.items())], "h": 0}, parent="F_G1", tin=6.86,
          tout=8.10, op=Track(88).move(7.94, 0.08, 0, "outCubic"))
cue(6.90, "sparkle", dur=0.40, gain=-29)

text(PART1, "F_ulehitrashem", "ולהתרשם", "H", 198, 540, 1262, parent="F_G1", tin=7.37, tout=8.10, shadow=True,
     op=Track(0).move(7.37, 0.08, 100, "linear").move(7.94, 0.08, 0, "outCubic"),
     scale=Track([136, 136]).move(7.37, 0.22, [100, 100], "outExpo"))
PART1.layers[-1]["light_sweep"] = {"t0": 7.46, "t1": 7.74, "x0": -120, "x1": 1200, "width": 150}
fl_op = Track(0).move(7.40, 0.08, 88, "outCubic").move(7.48, 0.26, 0, "inOutSine")
fl_sc = Track([55, 55]).move(7.40, 0.34, [160, 160], "outCubic")
shape(PART1, "F_flare", [glow_item(865, 1200, 300, 300, WHITE)], anchor=(865, 1200), pos=(865, 1200), scale=fl_sc,
      op=fl_op, blend="add", tin=7.38, tout=7.80, mb=False)
shape(PART1, "F_streak", [glow_item(865, 1200, 1100, 34, "#9CC8FF")], anchor=(865, 1200), pos=(865, 1200),
      scale=Track([40, 100]).move(7.40, 0.34, [120, 100], "outCubic"),
      op=Track(0).move(7.40, 0.08, 75, "outCubic").move(7.48, 0.26, 0, "inOutSine"), blend="add", tin=7.38,
      tout=7.80, mb=False)
cue(7.40, "click_hi", gain=-14, body=True)
cue(7.42, "sparkle", dur=0.35, gain=-23)

# ---- organ simulation recorded from the live V8.1 update page (site/organ_N.jpg, tools/capture_site.js)
#   7.98 the panel floats in over the blurred crowd; 8.08 tap "02 Dance" -> new dance styles;
#   8.32 swipe -> new DJ styles 51-55; 8.64 / 8.76 A and B light up pink; 8.96 it recedes behind "בסט"
ORG = json.load(open(os.path.join(WORK, "site", "organ_boxes.json")))
OIW, OIH = jpeg_size(os.path.join(WORK, "site", "organ_0.jpg"))
OCW = ORG["organ_0"]["panel"][2]                  # panel width in css px
PW, PC = 1000, (540, 1130)                        # on-screen width / centre
PH = OIH * PW / OIW
k_css = PW / OCW


def opt(x, y):
    """css px inside the panel -> comp px (panel at rest)."""
    return (round(PC[0] - PW / 2 + x * k_css, 1), round(PC[1] - PH / 2 + y * k_css, 1))


def box_c(b):
    return opt(b[0] + b[2] / 2, b[1] + b[3] / 2)


null(PART1, "F_PANEL", PC[0], PC[1], parent="SHAKE",
     pos=Track([PC[0], PC[1] + 360]).move(7.98, 0.30, list(PC), "outExpo").move(8.96, 0.18, [540, 1000], "outCubic"),
     scale=Track([86, 86]).move(7.98, 0.30, [100, 100], "outExpo").move_to(8.28, 8.96, [104, 104], "linear")
     .move(8.96, 0.18, [70, 70], "outCubic"),
     rot=Track(-6).move(7.98, 0.30, 0, "outExpo"), tin=7.98, tout=9.40)
cue(7.98, "air", dur=0.22, pre=0.08, gain=-16, pan=0.0, to_pan=0.0)
cue(8.00, "click_hi", gain=-19)
cue(8.28, "click_hi", gain=-19)
p_blur = lambda: Track(0).move(8.96, 0.16, 12, "outCubic")
shape(PART1, "F_panel_plate", [rect_item(PC[0], PC[1], PW, PH, r=16, fill="#9FA3A9")], parent="F_PANEL",
      op=Track(0).move(7.98, 0.08, 100, "linear").move(8.96, 0.12, 0, "linear"), tin=7.98, tout=9.10,
      fx=[dict(SHADOW, op=62, dist=28, soft=72)])
p_fade = lambda: Track(100).move(8.96, 0.24, 0, "outCubic")
organ_vis = {0: Track(0).move(7.98, 0.08, 100, "linear"), 1: 100, 2: p_fade()}
for n, (t_in, t_out) in enumerate(((7.98, 8.12), (8.12, 8.40), (8.40, 9.40))):
    PART1.add(name="F_organ_%d" % n, type="image", src="site/organ_%d.jpg" % n, w=OIW, h=OIH,
              anchor=[OIW / 2, OIH / 2], pos=list(PC), scale=[PW / OIW * 100] * 2, rot=0, op=organ_vis[n],
              parent="F_PANEL", mb=True, masks=[{"rect": [0, 0, OIW, OIH], "r": round(16 * OIW / PW, 1)}],
              fx=[{"type": "blur", "amt": p_blur()}], **{"in": t_in, "out": t_out})

# LCD refresh flash on the style screen at each state change
scr0, scr1 = opt(316, 135), opt(820, 418)
shape(PART1, "F_screen_flash", [rect_item((scr0[0] + scr1[0]) / 2, (scr0[1] + scr1[1]) / 2, scr1[0] - scr0[0],
                                          scr1[1] - scr0[1], r=4, fill=WHITE)],
      op=Track(0).jump(8.12, 55).move(8.16, 0.12, 0, "outCubic").jump(8.40, 55).move(8.44, 0.12, 0, "outCubic"),
      parent="F_PANEL", blend="add", tin=8.12, tout=8.60, mb=False)

# A / B light up pink (as on the site while a style plays)
PINK = "#FF4FA3"
for nm, t_on in (("A", 8.64), ("B", 8.76)):
    bc = box_c(ORG["organ_2"]["buttons"][nm])
    bw = ORG["organ_2"]["buttons"][nm][2] * k_css
    lit_op = p_fade
    lit_sc = Track([122, 122]).move(t_on, 0.14, [100, 100], "outBack2")
    shape(PART1, "F_btn%s_glow" % nm, [glow_item(bc[0], bc[1], bw * 3.2, bw * 3.2, PINK)], anchor=bc, pos=bc,
          scale=lit_sc, op=lit_op(), parent="F_PANEL", blend="add", tin=t_on, tout=9.40, mb=False,
          fx=[{"type": "blur", "amt": p_blur()}])
    shape(PART1, "F_btn%s_lit" % nm, [rect_item(bc[0], bc[1], bw - 4, bw - 4, r=6, fill=PINK)], anchor=bc, pos=bc,
          scale=Track([122, 122]).move(t_on, 0.14, [100, 100], "outBack2"), op=lit_op(), parent="F_PANEL",
          blend="multiply", tin=t_on, tout=9.40, fx=[{"type": "blur", "amt": p_blur()}])
    cue(t_on, "tap", gain=-14, pitch=1.0 if nm == "A" else 1.12)

# touch indicator: tap "02 Dance", swipe to the DJ folder, tap A then B
row = box_c(ORG["organ_0"]["rows"][0]["box"])
sw0, sw1 = opt(700, 280), opt(420, 280)
ba, bb = box_c(ORG["organ_2"]["buttons"]["A"]), box_c(ORG["organ_2"]["buttons"]["B"])
t_pos = Track(list(row)).move(8.24, 0.04, list(sw0), "linear").move(8.32, 0.08, list(sw1), "inOutCubic")
t_pos.move(8.48, 0.08, list(ba), "linear").move(8.68, 0.08, list(bb), "inOutCubic")
t_op = Track(0).move(8.02, 0.04, 60, "linear").move(8.14, 0.06, 0, "linear")
t_op.move(8.28, 0.04, 60, "linear").move(8.42, 0.06, 0, "linear")
t_op.move(8.56, 0.04, 60, "linear").move(8.84, 0.08, 0, "linear")
t_sc = Track([120, 120]).move(8.02, 0.06, [100, 100], "outCubic").move(8.08, 0.04, [80, 80], "outCubic")
t_sc.move(8.12, 0.08, [100, 100], "outCubic")
t_sc.move(8.60, 0.04, [80, 80], "outCubic").move(8.64, 0.04, [100, 100], "outCubic")
t_sc.move(8.72, 0.04, [80, 80], "outCubic").move(8.76, 0.04, [100, 100], "outCubic")
shape(PART1, "F_touch", [ellipse_item(0, 0, 58, 58, fill=WHITE, stroke=LBLUE, sw=3)], pos=t_pos, scale=t_sc,
      op=t_op, parent="F_PANEL", tin=8.00, tout=8.94)
cue(8.08, "tap", gain=-14)
cue(8.36, "air", dur=0.12, pre=0.04, gain=-20, pan=0.4, to_pan=-0.4)

text(PART1, "F_mikol_ma", "מכל מה", "L", 124, 540, 722, parent="F_TXT", tin=7.98, tout=T_DIS, shadow=True,
     op=f_out(), anims=[char_anim({"pos": [0, 46], "op": 0}, 8.00, 0.16, 0.28, "outExpo", by="word")])
text(PART1, "F_shenosaf", "שנוסף", "H", 206, 540, 1590, parent="F_TXT", tin=8.54, tout=T_DIS, shadow=True,
     op=f_out(), clip=[0, 0, 1080, 1590 + 0.305 * 206 + 0.19 * 206 + 10],
     anims=[char_anim({"pos": [0, 150], "op": 0}, 8.54, 0.26, 0.03, "outExpo")])
cue(8.56, "click_hi", gain=-15, body=True, pitch=0.95)
# 8.80-8.86: no effects (a beat of air before the climax), then a thin riser into the hit
cue(9.02, "riser_thin", dur=0.16, pre=0.16, gain=-15)

# climax "בסט"
bs_sc = Track([0, 0]).move_to(8.96, 9.03, [114, 114], "outCubic").move_to(9.03, 9.12, [100, 100], "inOutCubic")
bs_sc.move_to(9.12, T_DIS, [104, 104], "linear")
text(PART1, "F_baset", "בסט", "H", 400, 540, 1000, tin=8.96, tout=T_DIS, shadow=True, scale=bs_sc, parent="SHAKE",
     op=Track(0).move(8.96, 0.04, 100, "linear"))
cue(9.02, "hit_bright", gain=-12)
for nm, col, delay, size1, sw0 in (("F_ring1", WHITE, 0.0, 1900, 28), ("F_ring2", LBLUE, 0.06, 1500, 18)):
    shape(PART1, nm, [ellipse_item(540, 1000, 0, 0, stroke=col,
                                   size=Track([160, 160]).move(9.02 + delay, 0.40, [size1, size1], "outCubic"),
                                   swt=Track(sw0).move(9.02 + delay, 0.40, 2, "outCubic"))],
          op=Track(0).jump(9.02 + delay, 92).move(9.06 + delay, 0.36, 0, "outCubic"),
          blend="add" if col == LBLUE else "normal", tin=9.00, tout=9.50)
PART1.add(name="F_flash", type="solid", color=WHITE, w=W, h=H, anchor=[540, 960], pos=[540, 960], scale=[100, 100],
          rot=0, op=Track(0).jump(9.02, 42).move(9.06, 0.10, 0, "outCubic"), parent=None, mb=False, blend="add",
          **{"in": 9.00, "out": 9.30})

# logo-style bar clusters bursting out of the word (AE: clusters follow the real text width)
cluster = [(150, 16), (104, 16), (66, 16), (36, 16), (16, 16), (11, 11)]   # (height, width) from the word outward
for side in (-1, 1):
    cname = "F_BARS_%s" % ("L" if side < 0 else "R")
    edge = 540 + side * 420
    null(PART1, cname, edge, 1000, tin=9.00, tout=T_DIS, parent="SHAKE")
    PART1.layers[-1]["ae_edge_of"] = {"layer": "F_baset", "side": side, "gap": 44}
    for j, (hh, ww) in enumerate(cluster):
        x = edge + side * (j * 34)
        t_on = 9.04 + j * 0.022
        vals = {}
        for t in frame_times(9.00, T_DIS):
            grow = e_outBack(min(max((t - t_on) / 0.12, 0), 1)) if t >= t_on else 0
            pul = 0.75 + 0.45 * env_at(t - 0.02 * j) if t < VO_END + 0.05 else 0.75 + 0.1 * math.sin(t * 18 + j)
            vals[round(t, 4)] = [round(100 * grow, 2), round(100 * grow * pul, 2)]
        r = min(hh, ww) / 2
        shape(PART1, "%s_%d" % (cname, j), [rect_item(x, 1000, ww, hh, r=r, fill=LBLUE if hh > 20 else WHITE)],
              anchor=(x, 1000), pos=(x, 1000), scale={"k": [[t, v] for t, v in sorted(vals.items())], "h": 0},
              parent=cname, tin=9.00, tout=T_DIS, fx=[{"type": "glow", "color": LBLUE, "op": 70, "soft": 20}])
cue(9.04, "sparkle", dur=0.45, gain=-21)

# ======================================================================================
# MAIN: PART1 precomp, disintegration cells, end card
# ======================================================================================
MAIN.add(name="end_white", type="solid", color=WHITE, w=W, h=H, anchor=[540, 960], pos=[540, 960],
         scale=[100, 100], rot=0, op=100, parent=None, mb=False, **{"in": T_DIS, "out": DUR})
MAIN.add(name="PART1", type="precomp", comp="PART1", w=W, h=H, anchor=[540, 960], pos=[540, 960],
         scale=[100, 100], rot=0, op=100, parent=None, mb=True, tm=None, **{"in": 0.0, "out": T_DIS})

GRID, GOY = 27, 13

# disintegration: 108 px cells of the frozen frame fall away (aligned with the board grid)
CELL = 108
crng = random.Random(11)
rows = list(range(-1, 18))
cell_names = []
for r in rows:
    for c in range(10):
        x0, y0 = c * CELL, GOY + r * CELL
        cx, cy = x0 + CELL / 2, y0 + CELL / 2
        t0 = T_DIS + (17 - r) * 0.004 + crng.uniform(0, 0.02)
        vx = crng.uniform(-160, 160)
        v0 = crng.uniform(250, 600)
        rr = crng.uniform(-1, 1) * 140
        g = 22000
        pos = {"k": [], "h": 0}
        rot = {"k": [], "h": 0}
        sc = {"k": [], "h": 0}
        opk = {"k": [], "h": 0}
        t_end = None
        for t in [T_DIS] + frame_times(T_DIS, 10.62):
            dt = max(0.0, t - t0)
            yy = cy + v0 * dt + 0.5 * g * dt * dt
            pos["k"].append([round(t, 4), [round(cx + vx * dt, 2), round(yy, 2)]])
            rot["k"].append([round(t, 4), round(rr * dt, 2)])
            s = round(100 - 45 * min(1, dt / 0.35), 2)
            sc["k"].append([round(t, 4), [s, s]])
            opk["k"].append([round(t, 4), round(100 * (1 - min(1, max(0, (dt - 0.18) / 0.20))), 2)])
            if (yy - CELL > H or dt > 0.40) and t_end is None:
                t_end = t
                break
        t_end = t_end or 10.62
        nm = "H_cell_%02d_%d" % (r + 1, c)
        cell_names.append(nm)
        MAIN.add(name=nm, type="precomp", comp="PART1", w=W, h=H, anchor=[cx, cy], pos=pos, scale=sc, rot=rot,
                 op=opk, parent=None, mb=False, tm=T_DIS - 1 / FPS, masks=[{"rect": [x0, y0, x0 + CELL, y0 + CELL]}],
                 **{"in": T_DIS, "out": t_end + 1 / FPS})
cue(T_DIS, "air", dur=0.30, pre=0.06, gain=-14, dir="down", pan=-0.2, to_pan=0.2)
for k in range(4):
    cue(T_DIS + 0.04 + 0.05 * k, "click_hi", gain=-24 - k, pitch=1.1 - 0.05 * k)

# ---------------------------------------------------------------- end card: digital clock "V8.1"
# Approved option C2 (slanted, thin, chamfered segments; faint unlit segments stay only behind the 1).
# Entrance: "עדכון:" rises letter by letter (no scramble, never any other letter), the display powers
# on, then V counts A..V, 8 counts 0..8, the dot lights, 1 counts 0..1. Everything stays to the end.
CK_LIT, CK_GHOST, CK_FLASH = "#1F66B8", "#EEF3FA", "#6FB1FF"
CK_DH, CK_T, CK_GAP, CK_DW, CK_VW, CK_DOT = 360.0, 31.0, 5.0, 222.0, 244.0, 38.0
CK_K = math.tan(math.radians(5.5))           # italic slant
CK_TOP = 852.67                              # digit top (heading baseline 730.67 + 122)
CK_BASE = CK_TOP + CK_DH


def ck_clip(poly, nx, ny, px, py, off=0.0):
    """Keep the part of convex `poly` with n.(p - P) >= off (n normalised)."""
    ln = math.hypot(nx, ny)
    nx, ny = nx / ln, ny / ln
    out = []
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        fa = nx * (a[0] - px) + ny * (a[1] - py) - off
        fb = nx * (b[0] - px) + ny * (b[1] - py) - off
        if fa >= 0:
            out.append(a)
        if (fa < 0 < fb) or (fb < 0 < fa):
            k = fa / (fa - fb)
            out.append((a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k))
    return out


def ck_rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def ck_seven(w, h, t, g):
    """7-seg in (0,0)-(w,h): outer corners mitred at 45 deg, middle joints pointed."""
    m, hg, s = h / 2.0, g / 2.0, {}
    p = ck_clip(ck_clip(ck_rect(-w, 0, 2 * w, t), 1, -1, 0, 0, hg), -1, -1, w, 0, hg)
    s["a"] = p
    p = ck_clip(ck_clip(ck_rect(-w, h - t, 2 * w, h), 1, 1, 0, h, hg), -1, 1, w, h, hg)
    s["d"] = p
    p = ck_rect(-w, m - t / 2, 2 * w, m + t / 2)
    for sx, cx in ((1, t / 2), (-1, w - t / 2)):
        p = ck_clip(ck_clip(p, sx, -1, cx, m, hg), sx, 1, cx, m, hg)
    s["g"] = p
    for side, x0 in (("L", 0.0), ("R", w - t)):
        cx = x0 + t / 2
        p = ck_rect(x0, -h, x0 + t, 2 * h)
        p = ck_clip(p, -1, 1, 0, 0, hg) if side == "L" else ck_clip(p, 1, 1, w, 0, hg)
        p = ck_clip(ck_clip(p, -1, -1, cx, m, hg), 1, -1, cx, m, hg)
        s["f" if side == "L" else "b"] = p
        p = ck_rect(x0, -h, x0 + t, 2 * h)
        p = ck_clip(ck_clip(p, -1, 1, cx, m, hg), 1, 1, cx, m, hg)
        p = ck_clip(p, -1, -1, 0, h, hg) if side == "L" else ck_clip(p, 1, -1, w, h, hg)
        s["e" if side == "L" else "c"] = p
    return s


def ck_vstrokes(w, h, t, g):
    """The approved V: straight bars from the top corners to a fused apex, split at mid-height."""
    hg, cx, s = g / 2.0, w / 2.0, {}
    for side in (-1, 1):
        ox0 = 0.0 if side < 0 else w
        ln = math.hypot(cx - ox0, h)
        ux, uy = (cx - ox0) / ln, h / ln
        nx, ny = (uy, -ux) if side < 0 else (-uy, ux)
        far = 3 * h
        band = [(ox0 - ux * far, -uy * far), (ox0 + ux * far, uy * far),
                (ox0 + ux * far + nx * t, uy * far + ny * t), (ox0 - ux * far + nx * t, -uy * far + ny * t)]
        band = ck_clip(band, 0, 1, 0, 0)
        band = ck_clip(band, side, 1, ox0, 0.0, 0.0)
        band = ck_clip(band, 0, -1, 0, h)
        band = ck_clip(band, side, 0, cx, 0, -0.6)   # the two lower bars overlap at the apex (no AA seam)
        c0x, c0y = ox0 + nx * t / 2, ny * t / 2
        k = (h * 0.5 - c0y) / uy
        px, py = c0x + ux * k, c0y + uy * k
        name = "vl" if side < 0 else "vr"
        up = ck_clip(ck_clip(band, -ux - nx, -uy - ny, px, py, hg), -ux + nx, -uy + ny, px, py, hg)
        lo = ck_clip(ck_clip(band, ux - nx, uy - ny, px, py, hg), ux + nx, uy + ny, px, py, hg)
        s[name + "_up"], s[name + "_lo"] = up, lo
    return s


def ck_fourteen(w, h, t, g):
    """14-segment set for the counting letters: the 7-seg frame with a split middle bar,
    two centre verticals and four inner diagonals, in the same chamfered style."""
    s = ck_seven(w, h, t, g)
    m, hg, cx = h / 2.0, g / 2.0, w / 2.0
    gm = s.pop("g")
    s["g1"] = ck_clip(gm, -1, 0, cx, 0, hg)
    s["g2"] = ck_clip(gm, 1, 0, cx, 0, hg)
    tc = t * 0.9
    for nm, y0, y1 in (("h", t + g, m - t / 2 - g), ("i", m + t / 2 + g, h - t - g)):
        p = ck_rect(cx - tc / 2, y0 - h, cx + tc / 2, y1 + h)
        p = ck_clip(ck_clip(p, -1, 1, cx, y0, 0), 1, 1, cx, y0, 0)      # pointed top
        p = ck_clip(ck_clip(p, -1, -1, cx, y1, 0), 1, -1, cx, y1, 0)    # pointed bottom
        s[nm] = p
    x0, x1 = t + g, cx - tc / 2 - g
    for nm, (ax, ay, bx, by), box in (
            ("j", (x0, t + g, x1, m - t / 2 - g), (x0, t + g, x1, m - t / 2 - g)),
            ("k", (w - x0, t + g, w - x1, m - t / 2 - g), (w - x1, t + g, w - x0, m - t / 2 - g)),
            ("l", (x1, m + t / 2 + g, x0, h - t - g), (x0, m + t / 2 + g, x1, h - t - g)),
            ("m", (w - x1, m + t / 2 + g, w - x0, h - t - g), (w - x1, m + t / 2 + g, w - x0, h - t - g))):
        ln = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / ln, (by - ay) / ln
        nx, ny = -uy, ux
        hw = tc * 0.5
        far = 2 * h
        p = [(ax - ux * far + nx * hw, ay - uy * far + ny * hw), (ax + ux * far + nx * hw, ay + uy * far + ny * hw),
             (ax + ux * far - nx * hw, ay + uy * far - ny * hw), (ax - ux * far - nx * hw, ay - uy * far - ny * hw)]
        p = ck_clip(ck_clip(p, 1, 0, box[0], 0), -1, 0, box[2], 0)
        p = ck_clip(ck_clip(p, 0, 1, 0, box[1]), 0, -1, 0, box[3])
        s[nm] = p
    return s


def ck_shear(poly, ox):
    return [(ox + x + (CK_DH - y) * CK_K, CK_TOP + y) for x, y in poly]


def ck_path(poly):
    return "M" + " L".join("%.2f %.2f" % (x, y) for x, y in poly) + " Z"


# cells: V (14-seg + the approved V bars), 8 and 1 (7-seg), decimal point
ck_row = CK_VW + CK_DW + CK_DOT + CK_DW + 48.0 + 17.0 + 16.0 + CK_DH * CK_K
ck_x = {"V": (W - ck_row) / 2.0}
ck_x["8"] = ck_x["V"] + CK_VW + 48.0
ck_x["."] = ck_x["8"] + CK_DW + 17.0
ck_x["1"] = ck_x["."] + CK_DOT + 16.0
CELL_SEGS = {"V": {**ck_fourteen(CK_VW, CK_DH, CK_T, CK_GAP), **ck_vstrokes(CK_VW, CK_DH, CK_T, CK_GAP)},
             "8": ck_seven(CK_DW, CK_DH, CK_T, CK_GAP), "1": ck_seven(CK_DW, CK_DH, CK_T, CK_GAP),
             ".": {"p": ck_rect(0, CK_DH - CK_DOT, CK_DOT, CK_DH)}}
CELL_POLY = {c: {k: ck_shear(p, ck_x[c]) for k, p in segs.items()} for c, segs in CELL_SEGS.items()}
GHOST_SEGS = {"V": [k for k in CELL_SEGS["V"] if not k.startswith("v")], "8": list("abcdefg"),
              "1": list("abcdefg"), ".": ["p"]}

LETTER = {"A": "a b c e f g1 g2", "B": "a b c d g2 h i", "C": "a d e f", "D": "a b c d h i", "E": "a d e f g1 g2",
          "F": "a e f g1", "G": "a c d e f g2", "H": "b c e f g1 g2", "I": "a d h i", "J": "b c d e",
          "K": "e f g1 k m", "L": "d e f", "M": "b c e f j k", "N": "b c e f j m", "O": "a b c d e f",
          "P": "a b e f g1 g2", "Q": "a b c d e f m", "R": "a b e f g1 g2 m", "S": "a c d f g1 g2", "T": "a h i",
          "U": "b c d e f", "V": "vl_up vl_lo vr_up vr_lo"}
DIGIT = {"0": "a b c d e f", "1": "b c", "2": "a b d e g", "3": "a b c d g", "4": "b c f g", "5": "a c d f g",
         "6": "a c d e f g", "7": "a b c", "8": "a b c d e f g"}

# count schedule: (time, glyph) per cell; the last entry is the locked value
T_ON = 10.36                                  # display powers on
T_COUNT = 10.52
sched = {"V": [], "8": [], "1": [], ".": []}
t = T_COUNT
for ch in "ABCDEFGHIJKLMNOPQR":               # one frame each ...
    sched["V"].append((t, ch))
    t += 1 / FPS
for ch, nfr in (("S", 2), ("T", 2), ("U", 3)):  # ... slowing down before the lock
    sched["V"].append((t, ch))
    t += nfr / FPS
T_LOCK = {"V": round(t, 4)}
sched["V"].append((T_LOCK["V"], "V"))
for d_, tt in zip("012345678", (10.52, 10.64, 10.76, 10.88, 11.00, 11.12, 11.24, 11.40, 11.64)):
    sched["8"].append((tt, d_))
T_LOCK["8"] = 11.64
T_LOCK["."] = 11.72
sched["."].append((T_LOCK["."], "on"))
sched["1"] += [(T_COUNT, "0"), (11.80, "1")]
T_LOCK["1"] = 11.80
T_DONE = 11.80


def glyph_segs(cell, glyph):
    if cell == ".":
        return {"p"}
    return set((LETTER if cell == "V" else DIGIT)[glyph].split())


ck_cx = {c: (min(x for p in CELL_POLY[c].values() for x, _ in p) + max(x for p in CELL_POLY[c].values() for x, _ in p)) / 2
         for c in CELL_POLY}
CK_CY = CK_TOP + CK_DH / 2
for c in "V8.1":
    # lock bump around the cell centre
    bump = Track([100, 100]).move(T_LOCK[c], 0.04, [106, 106], "outCubic").move(T_LOCK[c] + 0.04, 0.16, [100, 100],
                                                                                 "outBack")
    null(MAIN, "CK_cell_%s" % ("dot" if c == "." else c), ck_cx[c], CK_CY, scale=bump, tin=T_ON, tout=DUR)
    par = "CK_cell_%s" % ("dot" if c == "." else c)
    # unlit segments: flicker on with the display; they stay only behind the 1
    g_op = Frames(0)
    for tt, v in ((T_ON, 100), (T_ON + 0.04, 0), (T_ON + 0.08, 100), (T_ON + 0.12, 30), (T_ON + 0.16, 100)):
        g_op.set(tt, v)
    if c != "1":
        for f in range(5):
            g_op.set(T_LOCK[c] + 0.04 * (f + 1), round(100 * (1 - (f + 1) / 5)))
    shape(MAIN, "CK_ghost_%s" % ("dot" if c == "." else c),
          [path_item(ck_path(CELL_POLY[c][k]), fill=CK_GHOST, evenodd=False) for k in GHOST_SEGS[c]],
          op=g_op.export(), parent=par, tin=T_ON, tout=DUR, mb=False)
    # lit segments: one layer each, on while the current glyph uses it
    for k in CELL_POLY[c]:
        op_k = Frames(0)
        for tt, glyph in sched[c]:
            op_k.set(tt, 100 if k in glyph_segs(c, glyph) else 0)
        if not op_k.vals or max(op_k.vals.values()) == 0:
            continue
        shape(MAIN, "CK_seg_%s_%s" % ("dot" if c == "." else c, k),
              [path_item(ck_path(CELL_POLY[c][k]), fill=CK_LIT, evenodd=False)],
              op=op_k.export(), parent=par, tin=sched[c][0][0], tout=DUR, mb=False)
    # lock flash: the final glyph in a lighter blue, fading out
    fin = glyph_segs(c, sched[c][-1][1])
    shape(MAIN, "CK_flash_%s" % ("dot" if c == "." else c),
          [path_item(ck_path(CELL_POLY[c][k]), fill=CK_FLASH, evenodd=False) for k in sorted(fin)],
          op=Track(100).move(T_LOCK[c] + 0.04, 0.20, 0, "outCubic"), parent=par, tin=T_LOCK[c],
          tout=T_LOCK[c] + 0.28, mb=False)

# sounds of the display
cue(T_ON, "shutter", gain=-17)
cue(T_ON + 0.08, "click_hi", gain=-24)
cue(T_ON + 0.16, "click_hi", gain=-22)
for i, (tt, ch) in enumerate(sched["V"][:-1]):
    cue(tt, "click_hi", gain=-27, pitch=1.0 + 0.02 * i)
for tt, d_ in sched["8"][:-1]:
    cue(tt + 0.02, "click_hi", gain=-24, pitch=0.85)
for c in "V81":
    cue(T_LOCK[c], "click_hi", gain=-15 if c != "1" else -13, body=True)
cue(T_LOCK["."], "click_hi", gain=-20, pitch=1.3)
cue(T_DONE, "riser_thin", dur=0.28, pre=0.28, gain=-24)
cue(T_DONE + 0.02, "hit_bright", gain=-15)
cue(T_DONE + 0.04, "sparkle", dur=0.45, gain=-22)

# one light sweep across the digits (additive white: visible on the segments only)
shape(MAIN, "CK_sweep", [glow_item(0, 0, 150, 1000, WHITE)], rot=18,
      pos=Track([20, CK_CY]).move(11.92, 0.42, [1080, CK_CY], "inOutSine"), op=85, blend="add",
      tin=11.90, tout=12.40, mb=True)
cue(11.92, "sparkle", dur=0.40, gain=-26)

# "עדכון:" - the word rises letter by letter (right to left); the colon is two square dots, like the
# clock's decimal point, and blinks once a second like a clock colon.
ADK_SIZE, ADK_BASE = 134, 730.67
ADK_W, CQ, CGAP = 333.0, 0.165 * 134, 0.11 * 134      # stand-in word width; AE follows the real width
adk_x0 = (W - (ADK_W + CGAP + CQ)) / 2.0
ADK_CX = adk_x0 + CQ + CGAP + ADK_W / 2.0
ADK_CY = ADK_BASE - HB["H"] * ADK_SIZE / 2.0
text(MAIN, "H_adkon", "עדכון", "H", ADK_SIZE, ADK_CX, ADK_CY, fill=BLUE, tin=9.92, tout=DUR,
     clip=[0, 0, 1080, ADK_BASE + 0.2 * ADK_SIZE + 6],
     anims=[char_anim({"pos": [0, 120], "op": 0}, 9.96, 0.30, 0.035, "outExpo")])
cue(9.96, "air", dur=0.22, pre=0.04, gain=-19)
cue(10.06, "click_hi", gain=-18, body=True)
col_cx = adk_x0 + CQ / 2.0
dots = [ADK_BASE - 0.58 * ADK_SIZE + CQ / 2.0, ADK_BASE - CQ / 2.0]
col_cy = (dots[0] + dots[1]) / 2.0
blink = Frames(0)
blink.set(10.20, 100)
for k in range(3):
    blink.set_range(12.26 + k, 12.76 + k, 0)
    blink.set(12.76 + k, 100)
shape(MAIN, "H_colon", [rect_item(col_cx, y, CQ, CQ, fill=BLUE) for y in dots], anchor=(col_cx, col_cy),
      pos=(col_cx, col_cy), scale=Track([0, 0]).move(10.20, 0.16, [100, 100], "outBack2"), op=blink.export(),
      tin=10.20, tout=DUR, mb=False)
MAIN.layers[-1]["ae_left_of"] = {"layer": "H_adkon", "gap": round(CGAP + CQ / 2.0, 2)}
cue(10.20, "click_hi", gain=-20, pitch=1.2)
for k in range(3):
    cue(12.76 + k, "click_hi", gain=-28, pitch=1.1)

MAIN.layers.insert(1, MAIN.layers.pop([l["name"] for l in MAIN.layers].index("PART1")))

# ------------------------------------------------------------------ output
os.makedirs(OUT, exist_ok=True)
scene = {"w": W, "h": H, "fps": FPS, "dur": DUR, "frames": NFRAMES,
         "colors": {"blue": BLUE, "lblue": LBLUE, "pale": PALE},
         "fonts": {"H": {"family": "NotoHeb", "weight": 900}, "L": {"family": "NotoHeb", "weight": 300}},
         "comps": {k: v.json() for k, v in COMPS.items()}, "main": "MAIN",
         "words": WT, "vo_end": VO_END}
json.dump(scene, open(os.path.join(OUT, "scene.json"), "w"), ensure_ascii=False)
CUES.sort(key=lambda c: c["t"])
# Stable synthesis seeds: cues that existed in the approved mix keep their seed (cue_seeds.json),
# new cues get one derived from kind + time, so adding a cue never re-rolls the others.
SEED_LOCK = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cue_seeds.json")))
for c in CUES:
    key = "%s@%.4f" % (c["kind"], c["t"])
    c["synth_seed"] = SEED_LOCK.get(key, 5000 + zlib.crc32(key.encode()) % 100000)
json.dump(CUES, open(os.path.join(OUT, "cues.json"), "w"), ensure_ascii=False, indent=0)
print("layers PART1=%d MAIN=%d cues=%d" % (len(PART1.layers), len(MAIN.layers), len(CUES)))
