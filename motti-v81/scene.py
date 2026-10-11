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
fblur.move(T_SINGER1, 0.18, 20, "outCubic")
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
cue(0.68, "cloth", dur=0.36)

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
cue(0.0, "whoosh", dur=0.30, rise=True, gain=-14, pan=0.25)

pulse = Track([125, 125]).move(0.40, 0.16, [100, 100], "outExpo")
pulse.move(0.64, 0.06, [108, 108], "outCubic").move(0.70, 0.14, [100, 100], "inOutCubic")
op_in = Track(0).move(0.40, 0.08, 100, "outCubic").move(0.94, 0.12, 0, "inCubic")
text(PART1, "A_hadash_outline", "חדש", "H", 230, 540, 1250, fill=None, stroke=BLUE, sw=7, parent="A_GRP",
     tin=0.0, tout=T_CARD, scale=pulse, op=op_in)
fill_op = Track(0).move(0.64, 0.06, 100, "outCubic").move(0.94, 0.12, 0, "inCubic")
text(PART1, "A_hadash_fill", "חדש", "H", 230, 540, 1250, fill=BLUE, parent="A_GRP", tin=0.0, tout=T_CARD,
     scale=pulse, op=fill_op)
cue(0.40, "tick", gain=-20)
cue(0.64, "pop", gain=-15, pitch=1.0)
cue(1.00, "suck", dur=0.08, gain=-18)

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
cue(T_CARD, "air_hit", gain=-12)
for k in range(4):
    cue(T_CARD + 0.10 + k * 0.04, "click_small", gain=-22, pitch=1.0 + 0.08 * k)

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
    cue(t0, "pluck", gain=-17, note={"M": 0, "O": 2, "T1": 4, "T2": 7, "i": 9}[gname])
g = LOGO["groups"]["dot"]
dx, dy = (g["bbox"][0] + g["bbox"][2]) / 2, (g["bbox"][1] + g["bbox"][3]) / 2
shape(PART1, "B_logo_dot", [path_item(g["d"], fill=BLUE, evenodd=True)], anchor=(dx, dy),
      pos=Track([dx, dy - 170]).move(1.47, 0.34, [dx, dy], "outBounce"),
      op=Track(0).move(1.47, 0.04, 100, "linear"), parent="CARD", tin=T_CARD, tout=T_CARD_END)
cue(1.47 + 0.34 * 0.36, "bloop", gain=-16)
for i, letter in enumerate(LOGO["ros"]):
    t0 = 1.66 + i * 0.024
    b = letter["bbox"]
    cxl, cyl = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    shape(PART1, "B_ros_%d" % i, [path_item(letter["d"], fill=BLUE, evenodd=True)], anchor=(cxl, cyl),
          pos=Track([cxl - 16, cyl]).move(t0, 0.16, [cxl, cyl], "outCubic"),
          op=Track(0).move(t0, 0.10, 100, "linear"), parent="CARD", tin=T_CARD, tout=T_CARD_END)
    cue(t0, "tick", gain=-31, pitch=1.3 + 0.03 * i)
text(PART1, "B_rozenfeld", "רוזנפלד", "H", 145, 518, 1222 - 0.305 * 145, fill=BLUE, parent="CARD",
     tin=T_CARD, tout=T_CARD_END, clip=[0, 0, 1080, 1222 + 14],
     anims=[char_anim({"pos": [0, 150], "op": 0}, 1.57, 0.28, 0.025, "outExpo")])
cue(1.57, "swish", gain=-17, dur=0.22, pan=0.0)
cue(2.05, "shimmer", dur=0.40, gain=-26)

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
cue(T_CARD_END, "swish", gain=-17, dur=0.18, pan=0.5, to_pan=0.0)
cue(T_GUITAR, "whip", gain=-20, dur=0.12)

op = Track(0).move(2.84, 0.06, 100, "linear").move(3.68, 0.12, 0, "inCubic")
text(PART1, "C_achshav", "עכשיו", "H", 196, 540, 440, parent="C_GRP", tin=2.84, tout=T_SINGER1, shadow=True,
     op=op, pos=Track([540, 330]).move(2.84, 0.16, [540, 440], "outBack2"),
     scale=Track([118, 118]).move(2.84, 0.16, [100, 100], "outExpo"))
cue(2.96, "rubber_pop", gain=-14)
cue(T_SAX, "whip", gain=-20, dur=0.12)

text(PART1, "C_laatar", "לאתר", "H", 196, 540, 628, parent="C_GRP", tin=3.18, tout=T_SINGER1, shadow=True,
     op=c_txt_out(), clip=[0, 0, 1080, 628 + 0.305 * 196 + 12],
     anims=[char_anim({"pos": [0, 140], "op": 0}, 3.18, 0.26, 0.03, "outExpo")])
cue(3.20, "pop", gain=-15, pitch=1.15)

# ---- phone (brand-light body) rising from below; browser chrome + live site inside
PH_C, PH_W, PH_H = (540, 1440), 640, 1340          # body (bottom runs off-frame)
SCR = (236, 786, 844, 2094)                        # screen rect
CHROME_B = 918                                     # status bar 786-826, address bar 826-918
SITE_SC = (SCR[2] - SCR[0]) / 780 * 100            # 780 px wide capture -> 608 px screen
null(PART1, "C_PHONE", PH_C[0], PH_C[1], parent="C_GRP",
     pos=Track([PH_C[0], PH_C[1] + 900]).move(T_GUITAR, 0.30, list(PH_C), "outExpo"),
     rot=Track(8).move(T_GUITAR, 0.30, 0, "outExpo"), tin=T_GUITAR, tout=T_SINGER1)
cue(T_GUITAR, "ui_swoosh", gain=-17)
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
cue(3.40, "bloop", gain=-21, pitch=1.2)
for k in range(4):
    cue(3.52 + k * 0.06, "wheel_tick", gain=-27 - k)

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
     tin=T_GUITAR, tout=T_SINGER1, op=100, mb=False,
     anims=[char_anim({"op": 0}, type_t0, 0.0, type_step, "linear", mode="in", step=type_step)])
for k in range(0, len(URL), 2):
    cue(type_t0 + k * type_step, "key", gain=-28, pitch=0.9 + 0.2 * random.Random(k).random())

# "go" button on the address bar, tapped on "לאתר"
GO = (802, 872)
go_sc = Track([0, 0]).move(3.16, 0.12, [100, 100], "outBack2").move(3.28, 0.04, [84, 84], "outCubic")
go_sc.move(3.32, 0.10, [100, 100], "outBack")
shape(PART1, "C_go", [ellipse_item(GO[0], GO[1], 46, 46, fill=LBLUE),
                      path_item("M%.1f %.1f L%.1f %.1f M%.1f %.1f L%.1f %.1f L%.1f %.1f" % (
                          GO[0] - 10, GO[1], GO[0] + 9, GO[1], GO[0] + 1, GO[1] - 8, GO[0] + 9, GO[1],
                          GO[0] + 1, GO[1] + 8), stroke=WHITE, sw=4, cap="round")],
      anchor=GO, pos=GO, scale=go_sc, parent="C_PHONE", op=100, tin=3.16, tout=T_SINGER1)
cue(3.16, "pop", gain=-22, pitch=1.4)
touch_op = Track(0).move(3.22, 0.05, 55, "linear").move(3.34, 0.08, 0, "linear")
touch_sc = Track([125, 125]).move(3.22, 0.06, [100, 100], "outCubic").move(3.28, 0.04, [82, 82], "outCubic")
shape(PART1, "C_touch", [ellipse_item(GO[0], GO[1], 74, 74, fill="#3A4A63")], anchor=GO, pos=GO, scale=touch_sc,
      op=touch_op, parent="C_PHONE", tin=3.20, tout=3.44)
shape(PART1, "C_tap_ripple", [ellipse_item(GO[0], GO[1], 0, 0, stroke=LBLUE,
                                           size=Track([46, 46]).move(3.28, 0.24, [170, 170], "outCubic"),
                                           swt=Track(6).move(3.28, 0.24, 1, "outCubic"))],
      op=Track(0).jump(3.28, 90).move(3.32, 0.20, 0, "outCubic"), parent="C_PHONE", tin=3.28, tout=3.54)
cue(3.28, "ui_click", gain=-14)

# loading bar under the address bar
shape(PART1, "C_loading", [rect_item(scr_c[0], CHROME_B - 2, SCR[2] - SCR[0], 5, fill=LBLUE)],
      anchor=(SCR[0], CHROME_B - 2), pos=(SCR[0], CHROME_B - 2),
      scale=Track([0, 100]).move(3.30, 0.10, [62, 100], "outCubic").move(3.40, 0.08, [100, 100], "inOutCubic"),
      op=Track(100).move(3.48, 0.06, 0, "linear"), parent="C_PHONE", tin=3.30, tout=3.56)
cue(3.30, "sweep_up", gain=-25, dur=0.16)
cue(3.64, "whoosh", dur=0.24, rise=True, gain=-16)

# ======================================================================================
# D  3.88-5.32  singer: "והאזינו לעדכון החדש" + VO-driven sound bars + echo stack
# ======================================================================================
null(PART1, "D_GRP", 540, 960, pos=Track([540, 960]).move_to(5.22, T_SITE, [-560, 960], "inQuad"),
     tin=T_SINGER1, tout=T_SITE)
cue(T_SINGER1, "whomp", gain=-17)
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
cue(3.90, "ping", gain=-20)

text(PART1, "D_laadkon", "לעדכון", "H", 222, 540, 1010, parent="D_GRP", tin=4.14, tout=T_SITE, shadow=True,
     clip=[0, 0, 1080, 1010 + 0.305 * 222 + 0.19 * 222 + 10],
     anims=[char_anim({"pos": [0, 165], "op": 0}, 4.14, 0.26, 0.03, "outExpo")])
cue(4.16, "pop", gain=-16, pitch=1.05)

for k in (3, 2, 1):
    t0 = 4.72 + (k - 1) * 0.07
    y0, y1 = 1245 + 84 * (k - 1), 1245 + 84 * k
    text(PART1, "D_hechadash_echo%d" % k, "החדש", "H", 262, 540, y1, parent="D_GRP", tin=t0, tout=T_SITE,
         op=Track(0).move(t0, 0.06, [52, 30, 15][k - 1], "linear"),
         pos=Track([540, y0]).move(t0, 0.12, [540, y1], "outCubic"))
text(PART1, "D_hechadash", "החדש", "H", 262, 540, 1245, parent="D_GRP", tin=4.58, tout=T_SITE, shadow=True,
     op=Track(0).move(4.58, 0.06, 100, "linear"),
     scale=Track([55, 55]).move(4.58, 0.20, [100, 100], "outBack2"))
cue(4.66, "echo_hit", gain=-13, repeats=4, gap=0.07)
cue(5.20, "whip", gain=-15, dur=0.16, pan=0.0, to_pan=-0.6)

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
cue(T_SITE, "ui_swoosh", gain=-16)

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
    cue(5.42 + k * 0.10, "wheel_tick", gain=-27)

op = Track(0).move(5.30, 0.10, 100, "linear").move(5.98, 0.10, 0, "inCubic")
text(PART1, "E_tuchlu", "תוכלו", "L", 112, 540, 360, parent="E_GRP", tin=T_SITE, tout=6.10, shadow=True, op=op,
     pos=Track([540, 392]).move(5.30, 0.16, [540, 360], "outExpo").move(5.98, 0.10, [540, 300], "inCubic"))
cue(5.30, "tick", gain=-21)
op = Track(100).move(5.98, 0.10, 0, "inCubic")
text(PART1, "E_ledafdef", "לדפדף", "H", 222, 540, 560, parent="E_GRP", tin=5.60, tout=6.10, shadow=True, op=op,
     pos=Track([540, 560]).move(5.98, 0.10, [540, 500], "inCubic"),
     anims=[char_anim({"scale": [0, 100], "op": 0}, 5.62, 0.20, 0.035, "outBack14")])
for k in range(5):
    cue(5.62 + k * 0.035, "page_flip", gain=-20 - k, pitch=1.0 + 0.05 * k)
op = Track(0).move(6.00, 0.10, 100, "linear")
text(PART1, "E_bein", "בין", "L", 112, 540, 360, parent="E_GRP", tin=6.00, tout=T_SINGER2, shadow=True, op=op,
     pos=Track([540, 392]).move(6.00, 0.16, [540, 360], "outExpo"))
text(PART1, "E_hatchanim", "התכנים", "H", 222, 540, 560, parent="E_GRP", tin=6.22, tout=T_SINGER2, shadow=True,
     clip=[0, 0, 1080, 560 + 0.305 * 222 + 14],
     anims=[char_anim({"pos": [0, 165], "op": 0}, 6.22, 0.26, 0.03, "outExpo")])
cue(6.24, "pop", gain=-16, pitch=1.1)

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
        cue(t0, "swish", gain=-21, dur=0.14, pan=0.6, to_pan=0.0)
cue(6.30, "swipe", gain=-17, dur=0.18)
cue(6.54, "whoosh", dur=0.12, rise=False, gain=-18)

# ======================================================================================
# F  6.64-9.72  singer: play button "להאזין" / "ולהתרשם" / "מכל מה" / "שנוסף" / "בסט"
# ======================================================================================
null(PART1, "F_TXT", 540, 960, pos=Track([540, 960]).move(8.86, 0.12, [540, 720], "inExpo"),
     scale=Track([100, 100]).move(8.86, 0.12, [90, 90], "inExpo"), tin=T_SINGER2, tout=T_DIS)
# group 1 ("להאזין ולהתרשם") hands over to group 2 ("מכל מה שנוסף") - both sit low, over the crowd,
# so the singer's face stays clear
null(PART1, "F_G1", 540, 960, parent="F_TXT", pos=Track([540, 960]).move(7.96, 0.10, [540, 880], "inCubic"),
     tin=T_SINGER2, tout=8.10)
f_out = lambda: Track(100).move(8.86, 0.12, 0, "inExpo")
g1_out = lambda: Track(100).move(7.96, 0.10, 0, "inCubic")

# play button (circle + triangle) - AE keeps it left of the word via an expression
pb_c = (292, 1010)
pb_sc = Track([0, 0]).move(6.72, 0.14, [100, 100], "outBack2").move(6.86, 0.05, [86, 86], "outCubic")
pb_sc.move(6.91, 0.10, [100, 100], "outBack")
null(PART1, "F_PLAY", pb_c[0], pb_c[1], parent="F_G1", scale=pb_sc, tin=6.70, tout=8.10)
PART1.layers[-1]["ae_left_of"] = {"layer": "F_lehaazin", "gap": 92}
op = Track(0).move(6.72, 0.05, 100, "linear").move(7.96, 0.10, 0, "inCubic")
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
cue(6.86, "ui_click", gain=-15)
cue(6.88, "play_chime", gain=-20)

text(PART1, "F_lehaazin", "להאזין", "L", 142, 600, 1010, parent="F_G1", tin=6.70, tout=8.10, shadow=True,
     op=Track(0).move(6.72, 0.08, 100, "linear").move(7.96, 0.10, 0, "inCubic"),
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
          tout=8.10, op=Track(88).move(7.96, 0.10, 0, "inCubic"))
cue(6.90, "shimmer", dur=0.50, gain=-27)

text(PART1, "F_ulehitrashem", "ולהתרשם", "H", 198, 540, 1262, parent="F_G1", tin=7.37, tout=8.10, shadow=True,
     op=Track(0).move(7.37, 0.08, 100, "linear").move(7.96, 0.10, 0, "inCubic"),
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
cue(7.40, "shing", gain=-15)

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
cue(7.98, "ui_swoosh", gain=-17)
p_blur = lambda: Track(0).move(8.96, 0.20, 10, "outCubic")
shape(PART1, "F_panel_plate", [rect_item(PC[0], PC[1], PW, PH, r=16, fill="#9FA3A9")], parent="F_PANEL",
      op=Track(0).move(7.98, 0.08, 100, "linear").move(8.96, 0.12, 0, "linear"), tin=7.98, tout=9.10,
      fx=[dict(SHADOW, op=62, dist=28, soft=72)])
organ_vis = {0: Track(0).move(7.98, 0.08, 100, "linear").jump(8.12, 0),
             1: Track(0).jump(8.12, 100).jump(8.40, 0),
             2: Track(0).jump(8.40, 100).move(8.96, 0.40, 0, "inOutSine")}
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
    lit_op = lambda: Track(0).jump(t_on, 100).move(8.96, 0.40, 0, "inOutSine")
    lit_sc = Track([122, 122]).move(t_on, 0.14, [100, 100], "outBack2")
    shape(PART1, "F_btn%s_glow" % nm, [glow_item(bc[0], bc[1], bw * 3.2, bw * 3.2, PINK)], anchor=bc, pos=bc,
          scale=lit_sc, op=lit_op(), parent="F_PANEL", blend="add", tin=t_on, tout=9.40, mb=False,
          fx=[{"type": "blur", "amt": p_blur()}])
    shape(PART1, "F_btn%s_lit" % nm, [rect_item(bc[0], bc[1], bw - 4, bw - 4, r=6, fill=PINK)], anchor=bc, pos=bc,
          scale=Track([122, 122]).move(t_on, 0.14, [100, 100], "outBack2"), op=lit_op(), parent="F_PANEL",
          blend="multiply", tin=t_on, tout=9.40, fx=[{"type": "blur", "amt": p_blur()}])
    cue(t_on, "ui_click", gain=-15, pitch=1.0 if nm == "A" else 1.12)
    cue(t_on + 0.01, "blip", gain=-24, pitch=1.0 if nm == "A" else 1.25)

# touch indicator: tap "02 Dance", swipe to the DJ folder, tap A then B
row = box_c(ORG["organ_0"]["rows"][0]["box"])
sw0, sw1 = opt(700, 280), opt(420, 280)
ba, bb = box_c(ORG["organ_2"]["buttons"]["A"]), box_c(ORG["organ_2"]["buttons"]["B"])
t_pos = Track(list(row)).jump(8.28, list(sw0)).move(8.32, 0.08, list(sw1), "inOutCubic")
t_pos.jump(8.56, list(ba)).move(8.68, 0.08, list(bb), "inOutCubic")
t_op = Track(0).move(8.02, 0.04, 60, "linear").move(8.14, 0.06, 0, "linear")
t_op.move(8.28, 0.04, 60, "linear").move(8.42, 0.06, 0, "linear")
t_op.move(8.56, 0.04, 60, "linear").move(8.84, 0.08, 0, "linear")
t_sc = Track([120, 120]).move(8.02, 0.06, [100, 100], "outCubic").move(8.08, 0.04, [80, 80], "outCubic")
t_sc.move(8.12, 0.08, [100, 100], "outCubic")
t_sc.move(8.60, 0.04, [80, 80], "outCubic").move(8.64, 0.04, [100, 100], "outCubic")
t_sc.move(8.72, 0.04, [80, 80], "outCubic").move(8.76, 0.04, [100, 100], "outCubic")
shape(PART1, "F_touch", [ellipse_item(0, 0, 58, 58, fill=WHITE, stroke=LBLUE, sw=3)], pos=t_pos, scale=t_sc,
      op=t_op, parent="F_PANEL", tin=8.00, tout=8.94)
cue(8.08, "ui_click", gain=-15)
cue(8.32, "swipe", gain=-18, dur=0.12)

text(PART1, "F_mikol_ma", "מכל מה", "L", 124, 540, 722, parent="F_TXT", tin=7.98, tout=T_DIS, shadow=True,
     op=f_out(), anims=[char_anim({"pos": [0, 46], "op": 0}, 8.00, 0.16, 0.28, "outExpo", by="word")])
text(PART1, "F_shenosaf", "שנוסף", "H", 206, 540, 1590, parent="F_TXT", tin=8.54, tout=T_DIS, shadow=True,
     op=f_out(), clip=[0, 0, 1080, 1590 + 0.305 * 206 + 0.19 * 206 + 10],
     anims=[char_anim({"pos": [0, 150], "op": 0}, 8.54, 0.26, 0.03, "outExpo")])
cue(8.56, "pop", gain=-16, pitch=0.95)
cue(8.80, "suck", dur=0.20, gain=-15)

# climax "בסט"
bs_sc = Track([0, 0]).move_to(8.96, 9.03, [114, 114], "outCubic").move_to(9.03, 9.12, [100, 100], "inOutCubic")
bs_sc.move_to(9.12, T_DIS, [104, 104], "linear")
text(PART1, "F_baset", "בסט", "H", 400, 540, 1000, tin=8.96, tout=T_DIS, shadow=True, scale=bs_sc, parent="SHAKE",
     op=Track(0).move(8.96, 0.04, 100, "linear"))
cue(9.02, "impact", gain=-13)
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
cue(9.04, "glitter", dur=0.30, gain=-24)

# ======================================================================================
# MAIN: PART1 precomp, disintegration cells, end card
# ======================================================================================
MAIN.add(name="end_white", type="solid", color=WHITE, w=W, h=H, anchor=[540, 960], pos=[540, 960],
         scale=[100, 100], rot=0, op=100, parent=None, mb=False, **{"in": T_DIS, "out": DUR})
MAIN.add(name="PART1", type="precomp", comp="PART1", w=W, h=H, anchor=[540, 960], pos=[540, 960],
         scale=[100, 100], rot=0, op=100, parent=None, mb=True, tm=None, **{"in": 0.0, "out": T_DIS})

GRID, GOY = 27, 13
# grid of the "game board" (27 px pitch; the 108 px transition cells line up with it)
lines = []
for k in range(0, 41):
    lines.append("M%d %d L%d %d" % (k * GRID, -40, k * GRID, 1960))
for k in range(-1, 72):
    y = GOY + k * GRID
    lines.append("M%d %d L%d %d" % (-40, y, 1120, y))
shape(MAIN, "H_grid", [path_item(" ".join(lines), stroke="#E8EEF7", sw=1.5, cap="butt", evenodd=False)],
      op=100, tin=T_END, tout=DUR, mb=False,
      masks=[{"ellipse": [540, 960], "size": Track([0, 0]).move(T_END, 0.40, [2600, 2600], "outCubic"),
              "feather": 260}])
cue(T_END, "crt_on", gain=-17)

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
cue(T_DIS, "crumble", dur=0.55, gain=-14)
cue(T_DIS + 0.02, "arp_down", n=8, gap=0.045, gain=-20)

# ---------------------------------------------------------------- end card
# Everything here stays on screen until the last frame.
null(MAIN, "END_SHAKE", 540, 960, tin=T_END, tout=DUR)
end_shake = Frames([540, 960])

# "עדכון:" glitch-in, scramble, lock
ADK = "עדכון:"
HEB = "אבגדהוזחטיכלמנסעפצקרשת"
srng = random.Random(5)
src_keys = []
lock_t = [10.40, 10.46, 10.52, 10.58, 10.64, 10.64]
for t in frame_times(10.34, 10.64):
    s_ = "".join(ch if t >= lock_t[i] - 1e-6 else srng.choice(HEB) for i, ch in enumerate(ADK))
    src_keys.append([round(t, 4), s_])
src_keys.append([10.68, ADK])
ADK_Y = 700
adk_op = Frames(0)
adk_op.set_range(10.10, 10.18, 100).set_range(10.18, 10.22, 0).set_range(10.22, 10.30, 100)
adk_op.set_range(10.30, 10.34, 0).set_range(10.34, 15.0, 100)
adk_sc = Track([100, 100]).move(10.66, 0.02, [105, 105], "linear").move(10.68, 0.14, [100, 100], "outCubic")
adk = text(MAIN, "H_adkon", ADK, "H", 125, 540, ADK_Y, fill=BLUE, parent="END_SHAKE", tin=10.10, tout=DUR,
           op=adk_op, scale=adk_sc, src=src_keys, mb=False)
cue(10.10, "glitch", dur=0.08, gain=-15)
cue(10.22, "glitch", dur=0.08, gain=-16)
cue(10.34, "glitch", dur=0.06, gain=-17)
for t in frame_times(10.34, 10.64):
    cue(t, "data_bleep", gain=-27, seed=int(t * 100))
cue(10.66, "lock_click", gain=-12)

# ---- Tetris "V8.1": fine 15-row pixel letters on the 27 px board (approved option 2)
GLYPHS = {
    "V": ["X.......X", "X.......X", "X.......X", "X.......X", ".X.....X.", ".X.....X.", ".X.....X.",
          "..X...X..", "..X...X..", "..X...X..", "...X.X...", "...X.X...", "...X.X...", "....X....", "....X...."],
    "8": ["..XXXX..", ".X....X.", ".X....X.", ".X....X.", ".X....X.", ".X....X.", "..XXXX..", ".X....X.",
          "X......X", "X......X", "X......X", "X......X", "X......X", ".X....X.", "..XXXX.."],
    ".": ["..", "..", "..", "..", "..", "..", "..", "..", "..", "..", "..", "..", "..", "..", ".X"],
    "1": ["...X.", "..XX.", ".X.X.", "X..X.", "...X.", "...X.", "...X.", "...X.", "...X.", "...X.", "...X.",
          "...X.", "...X.", "...X.", "..XXX"],
}
LETTER_GAP, BLOCK, BRAD = 2, 23, 5
ROWS = len(GLYPHS["V"])
assert all(len(GLYPHS[g]) == ROWS for g in "V8.1")
TOTAL_COLS = sum(len(GLYPHS[g][0]) for g in "V8.1") + LETTER_GAP * 3
col0 = round((W / GRID - TOTAL_COLS) / 2)
row0 = round((1100 - ROWS * GRID / 2 - GOY) / GRID)
BX0, BY0 = col0 * GRID, GOY + row0 * GRID
V_CX, V_CY = BX0 + TOTAL_COLS * GRID / 2, BY0 + ROWS * GRID / 2
cells = []                     # (col, row, glyph)
cc = col0
for gch in "V8.1":
    gl = GLYPHS[gch]
    for r, line in enumerate(gl):
        for c, ch in enumerate(line):
            if ch == "X":
                cells.append((cc + c, row0 + r, gch))
    cc += len(gl[0]) + LETTER_GAP
cell_set = {(c, r) for c, r, _ in cells}
glyph_of = {(c, r): g for c, r, g in cells}

# partition into pieces of up to 4 cells (8-connected), building bottom-up
unassigned = set(cell_set)
pieces = []
while unassigned:
    start = max(unassigned, key=lambda p: (p[1], -p[0]))
    group, queue = [start], [start]
    unassigned.discard(start)
    while queue and len(group) < 4:
        p = queue.pop(0)
        nbrs = [(p[0] + dx, p[1] + dy) for dy in (0, -1, 1) for dx in (0, -1, 1) if (dx or dy)]
        nbrs.sort(key=lambda q: (abs(q[0] - p[0]) + abs(q[1] - p[1]), -q[1]))
        for q in nbrs:
            if q in unassigned and glyph_of[q] == glyph_of[start] and len(group) < 4:
                unassigned.discard(q)
                group.append(q)
                queue.append(q)
    pieces.append(sorted(group))
pieces.sort(key=lambda g: (-max(r for _, r in g), min(c for c, _ in g)))
NP = len(pieces)
P_COLORS = [BLUE, "#1F66B8", BLUE, LBLUE]
FALL_FR = 10
t_first, t_last_land = 10.50, 11.80
step = (t_last_land - FALL_FR / FPS - t_first) / (NP - 1)
prng = random.Random(21)
piece_info = []


def cell_rect_items(group, color):
    inset = (GRID - BLOCK) / 2
    return [rect_item(c * GRID + GRID / 2, GOY + rr * GRID + GRID / 2, GRID - 2 * inset, GRID - 2 * inset,
                      r=BRAD, fill=color) for c, rr in group]


# the whole word pops once as one unit when it locks in
grp_sc = Track([100, 100]).move(12.04, 0.04, [104, 104], "outCubic").move(12.08, 0.16, [100, 100], "outCubic")
null(MAIN, "V81_GRP", V_CX, V_CY, parent="END_SHAKE", scale=grp_sc, tin=T_END, tout=DUR)

HEAD_CLEAR_Y = 790              # falling pieces stay below the heading "עדכון:"
BUILD_END_F = round(12.0 * FPS)
occupied = {}                   # frame -> board cells taken by pieces already scheduled


def piece_cells(grp, rot, dcol, drow):
    """Board cells of a piece rotated about its bbox centre and shifted; None if off-grid."""
    minc = min(c for c, _ in grp); maxc = max(c for c, _ in grp)
    minr = min(r for _, r in grp); maxr = max(r for _, r in grp)
    cx, cy = (minc + maxc + 1) / 2, (minr + maxr + 1) / 2
    ca, sa = round(math.cos(math.radians(rot))), round(math.sin(math.radians(rot)))
    out = set()
    for c, r in grp:
        x, y = c + 0.5 - cx, r + 0.5 - cy
        xc, yc = cx + x * ca - y * sa - 0.5 + dcol, cy + x * sa + y * ca - 0.5 + drow
        if abs(xc - round(xc)) > 1e-6 or abs(yc - round(yc)) > 1e-6:
            return None
        out.add((round(xc), round(yc)))
    return out


def fall_schedule(n, side, rot0, grid_ok_half):
    """Per-frame (rows_above, column_shift, rotation) for an n-frame drop."""
    sched = []
    for f in range(n + 1):
        shift = side * 2 if (f < min(4, n - 1)) else 0
        if f < max(1, min(3, n // 2)):
            rot = rot0
        elif abs(rot0) == 180 and grid_ok_half and f < min(5, n - 1):
            rot = rot0 // 2
        else:
            rot = 0
        sched.append((n - f, shift, rot))
    return sched


for k, grp in enumerate(pieces):
    color = P_COLORS[k % len(P_COLORS)] if len(grp) > 1 else "#1F66B8"
    land_f = round((t_first + k * step) * FPS) + FALL_FR
    tl = land_f / FPS
    minc = min(c for c, _ in grp); maxc = max(c for c, _ in grp)
    minr = min(r for _, r in grp); maxr = max(r for _, r in grp)
    pcx = (minc + maxc + 1) / 2 * GRID
    pcy = GOY + (minr + maxr + 1) / 2 * GRID
    n_max = max(1, min(FALL_FR, int((GOY + minr * GRID - HEAD_CLEAR_Y) // GRID)))
    # candidate (rotation, side) pairs: only rotations that keep the blocks on the board grid
    rots = [r for r in (0, 180, -90, 90) if len(grp) > 1 and piece_cells(grp, r, 0, 0) is not None] or [0]
    half_ok = piece_cells(grp, 90, 0, 0) is not None
    pref = (prng.choice(rots + [0, 0]), prng.choice([0, 0, -1, 1]))
    cands = [pref] + [(r, sd) for r in rots for sd in (0, -1, 1)]
    chosen = None
    for n in range(n_max, 0, -1):
        for rot0, side in cands:
            sched = fall_schedule(n, side, rot0, half_ok)
            frames_cells, ok = {}, True
            for f, (above, shift, rot) in enumerate(sched):
                cs = piece_cells(grp, rot, shift, -above)
                if cs is None or cs & occupied.get(land_f - n + f, set()):
                    ok = False
                    break
                frames_cells[land_f - n + f] = cs
            if ok:
                for fi in range(land_f + 1, BUILD_END_F):
                    if set(grp) & occupied.get(fi, set()):
                        ok = False
                        break
            if ok:
                chosen = (n, rot0, side, sched, frames_cells)
                break
        if chosen:
            break
    if not chosen:      # last resort: one-frame drop straight into place
        chosen = (1, 0, 0, fall_schedule(1, 0, 0, False), {land_f - 1: set(grp), land_f: set(grp)})
    n, rot0, side, sched, frames_cells = chosen
    for fi, cs in frames_cells.items():
        occupied.setdefault(fi, set()).update(cs)
    for fi in range(land_f + 1, BUILD_END_F):
        occupied.setdefault(fi, set()).update(grp)
    ts = (land_f - n) / FPS
    pos = Frames([pcx, pcy - n * GRID])
    rot = Frames(sched[0][2])
    for f, (above, shift, r_) in enumerate(sched):
        t = ts + f / FPS
        pos.set(t, [pcx + shift * GRID, pcy - above * GRID])
        rot.set(t, r_)
    vis = Frames(0).set_range(ts, 15.0, 100)
    sq = Frames([100, 100])
    for f, v in enumerate([[106, 90], [102, 97], [100, 100]]):
        sq.set(tl + f / FPS, v)
    # lock-in glitch: the blocks themselves jump sideways / blink for three frames, then settle
    jit = random.Random(100 + k)
    for fr_t in (11.92, 11.96, 12.00):
        vis.set(fr_t, 0 if jit.random() < 0.25 else 100)
        pos.set(fr_t, [pcx + jit.choice([-1, 1]) * jit.uniform(6, 30), pcy])
    vis.set(12.04, 100)
    pos.set(12.04, [pcx, pcy])
    # micro glitch during the hold
    for fr_t in (13.20, 13.24):
        if jit.random() < 0.45:
            pos.set(fr_t, [pcx + jit.choice([-1, 1]) * jit.uniform(4, 16), pcy])
        else:
            pos.set(fr_t, [pcx, pcy])
    pos.set(13.28, [pcx, pcy])
    shape(MAIN, "H_piece_%02d" % k, cell_rect_items(grp, color), anchor=(pcx, pcy), pos=pos, scale=sq, rot=rot,
          op=vis, parent="V81_GRP", tin=ts, tout=DUR, mb=False)
    # ghost (landing preview) - re-stacked below every piece after the loop
    shape(MAIN, "H_ghost_%02d" % k, cell_rect_items(grp, PALE), op=Frames(0).set_range(ts, tl, 70).set(tl, 0),
          parent="V81_GRP", tin=ts, tout=tl + 0.04, mb=False)
    # lock flash, squashed together with the piece
    shape(MAIN, "H_lockflash_%02d" % k, cell_rect_items(grp, WHITE), anchor=(pcx, pcy), pos=(pcx, pcy),
          scale=sq.export(), op=Frames(0).set(tl, 85).set(tl + 1 / FPS, 45).set(tl + 2 / FPS, 0), parent="V81_GRP",
          tin=tl, tout=tl + 0.12, mb=False)
    end_shake.set(tl, [541.5, 959]).set(tl + 1 / FPS, [539, 960.5]).set(tl + 2 / FPS, [540, 960])
    piece_info.append({"k": k, "cells": grp, "color": color, "t_spawn": ts, "t_land": tl, "rot0": rot0, "fall": n})
    if k % 3 == 0:
        cue(ts, "spawn", gain=-32, pitch=1.0 + 0.04 * (k % 5))
    if rot0 and k % 2 == 0:
        cue(ts + 2 / FPS, "rotate_blip", gain=-26, pitch=1.0 + 0.05 * (k % 4))
    if k % 2 == 0:
        cue(tl, "lock_thud", gain=-15, pitch=0.9 + 0.035 * (k % 7))
    else:
        cue(tl, "tick", gain=-24, pitch=0.85)

# ghosts sit underneath all falling pieces (as in Tetris)
_ghosts = [l for l in MAIN.layers if l["name"].startswith("H_ghost_")]
MAIN.layers = [l for l in MAIN.layers if not l["name"].startswith("H_ghost_")]
_first_piece = next(i for i, l in enumerate(MAIN.layers) if l["name"].startswith("H_piece_"))
MAIN.layers[_first_piece:_first_piece] = _ghosts
print("falls:", [p["fall"] for p in piece_info], "rot:", [p["rot0"] for p in piece_info])

# scanline + cell flash + lock-in glitch + unified pop (no switch to a typeface: the blocks stay)
shape(MAIN, "H_scan_soft", [rect_item(540, 0, 1100, 70, r=0, fill="#9CC8FF")],
      pos=Track([0, BY0 - 30]).move_to(11.84, 11.92, [0, BY0 + ROWS * GRID + 30], "linear"), op=80,
      tin=11.84, tout=11.94, mb=True, fx=[{"type": "blur", "amt": 16}], blend="normal")
shape(MAIN, "H_scan_core", [rect_item(540, 0, 1100, 8, r=0, fill=WHITE)],
      pos=Track([0, BY0 - 30]).move_to(11.84, 11.92, [0, BY0 + ROWS * GRID + 30], "linear"), op=100,
      tin=11.84, tout=11.94, mb=True)
cue(11.84, "sweep_up", dur=0.10, gain=-15)
all_cells = sorted(cell_set)
shape(MAIN, "H_cells_flash", cell_rect_items(all_cells, WHITE),
      op=Frames(0).set(11.88, 50).set(11.92, 80).set(11.96, 0).set(12.04, 70).set(12.08, 35).set(12.12, 0),
      parent="V81_GRP", tin=11.86, tout=12.16, mb=False)
cue(11.92, "glitch", dur=0.12, gain=-14)
cue(12.04, "resolve_snap", gain=-11)

# light sweep across the blocks, column by column (left to right)
for ci in range(TOTAL_COLS):
    col_cells = [p for p in all_cells if p[0] == col0 + ci]
    if not col_cells:
        continue
    tp = 12.52 + ci * 0.012
    shape(MAIN, "H_sheen_%02d" % ci, cell_rect_items(col_cells, WHITE),
          op=Track(0).move_to(tp - 0.08, tp, 55, "inOutSine").move_to(tp, tp + 0.12, 0, "inOutSine"),
          parent="V81_GRP", tin=12.40, tout=13.00, mb=False)
cue(12.50, "shimmer", dur=0.40, gain=-26)

# floating pixels until the end
fprng = random.Random(44)
spots = [(150, 470), (930, 520), (110, 860), (985, 905), (170, 1420), (900, 1450), (330, 1580), (760, 1610),
         (250, 330), (820, 330), (60, 1180), (1020, 1240), (520, 1560), (640, 470)]
for k, (x, y) in enumerate(spots):
    s = fprng.choice([12, 16, 20, 26])
    col = fprng.choice([BLUE, LBLUE, "#BFD7F5"])
    blink = Frames(0)
    t = 12.30 + fprng.uniform(0, 0.4)
    blink.set(t, 100)
    while t < 14.6:
        t += fprng.uniform(0.25, 0.7)
        blink.set(t, fprng.choice([100, 100, 35]))
    shape(MAIN, "H_px_%02d" % k, [rect_item(x, y, s, s, r=3, fill=col)],
          pos=Track([0, 0]).move_to(12.30, DUR, [fprng.uniform(-24, 24), fprng.uniform(-30, -10)], "linear"),
          op=blink, tin=12.30, tout=DUR, mb=False)
for t in (12.9, 13.55, 14.05):
    cue(t, "blip", gain=-31, pitch=1.3 + 0.2 * random.Random(int(t * 10)).random())


# glitch slices on the heading (expanded to plain layers so AE and the preview match)
def glitch_layers(base, events, seed, tag):
    rng = random.Random(seed)
    size = base["size"]
    y_top, y_bot = -ASC * size * (1.0 if base["dir"] == "rtl" else 0.95), DESC * size
    nsl = 7
    cuts = sorted(rng.uniform(y_top, y_bot) for _ in range(nsl - 1))
    bands = [y_top - 30] + cuts + [y_bot + 30]
    base_op = base["op"]
    for s in range(nsl):
        xo = Frames([0, 0])
        vis = Frames(0)
        for (t, n, amp, _split) in events:
            for f in range(n):
                tt = t + f / FPS
                vis.set(tt, 100)
                xo.set(tt, [rng.uniform(-amp, amp) if rng.random() > 0.25 else 0, 0])
            vis.set(t + n / FPS, 0)
            xo.set(t + n / FPS, [0, 0])
        L = json.loads(json.dumps(base))
        L["name"] = "%s_slice%d" % (tag, s)
        L["op"] = vis.export()
        L["masks"] = [{"rect": [-3000, bands[s], 3000, bands[s + 1]]}]
        L["glitch_of"] = base["name"]
        L["xoff"] = xo.export()
        L["mb"] = False
        MAIN.add(**L)
    for nm, col, sgn in (("cyan", CYAN, -1), ("magenta", MAGENTA, 1)):
        xo = Frames([0, 0])
        vis = Frames(0)
        for (t, n, amp, split) in events:
            for f in range(n):
                tt = t + f / FPS
                vis.set(tt, 85)
                xo.set(tt, [sgn * split * (1 - 0.35 * f), sgn * split * 0.15])
            vis.set(t + n / FPS, 0)
        L = json.loads(json.dumps(base))
        L["name"] = "%s_%s" % (tag, nm)
        L["fill"] = col
        L["stroke"] = None
        L["blend"] = "multiply"
        L["op"] = vis.export()
        L["xoff"] = xo.export()
        L["glitch_of"] = base["name"]
        L["mb"] = False
        idx = MAIN.layers.index(base)
        MAIN.layers.insert(idx, L)   # below the base text
    # hide the base text while its slices are shown
    op_fr = Frames(0)
    k = base_op["k"] if isinstance(base_op, dict) else [[0.0, base_op]]
    cur = 0
    seq = {round(t * FPS): v for t, v in k}
    for f in range(NFRAMES + 1):
        if f in seq:
            cur = seq[f]
        op_fr.set(f / FPS, cur)
    for (t, n, _a, _s) in events:
        for f in range(n):
            op_fr.set(t + f / FPS, 0)
    base["op"] = op_fr.export()


glitch_layers(adk, [(10.10, 2, 70, 16), (10.22, 2, 36, 10), (10.40, 1, 14, 5), (10.52, 1, 14, 5),
                    (10.64, 1, 10, 4), (13.20, 2, 18, 6)], 9, "H_adkon_g")
cue(13.20, "zap", gain=-17)

MAIN.layers.insert(1, MAIN.layers.pop([l["name"] for l in MAIN.layers].index("PART1")))
# "עדכון:" (and its glitch copies) above the falling pieces
_adk = [l for l in MAIN.layers if l["name"].startswith("H_adkon")]
MAIN.layers = [l for l in MAIN.layers if not l["name"].startswith("H_adkon")] + _adk
for L in MAIN.layers:
    if L["name"] == "END_SHAKE":
        L["pos"] = end_shake.export()

# ------------------------------------------------------------------ output
os.makedirs(OUT, exist_ok=True)
scene = {"w": W, "h": H, "fps": FPS, "dur": DUR, "frames": NFRAMES,
         "colors": {"blue": BLUE, "lblue": LBLUE, "pale": PALE},
         "fonts": {"H": {"family": "NotoHeb", "weight": 900}, "L": {"family": "NotoHeb", "weight": 300}},
         "comps": {k: v.json() for k, v in COMPS.items()}, "main": "MAIN",
         "words": WT, "vo_end": VO_END}
json.dump(scene, open(os.path.join(OUT, "scene.json"), "w"), ensure_ascii=False)
CUES.sort(key=lambda c: c["t"])
json.dump(CUES, open(os.path.join(OUT, "cues.json"), "w"), ensure_ascii=False, indent=0)
print("layers PART1=%d MAIN=%d pieces=%d cues=%d" % (len(PART1.layers), len(MAIN.layers), NP, len(CUES)))
