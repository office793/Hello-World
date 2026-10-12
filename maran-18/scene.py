#!/usr/bin/env python3
"""Scene description for the Maran "18 NIS" typography video (1080x1920, 29.97 fps, 15.5 s).

Ending segment that follows the client's 33 s street video: big gold Hebrew words on the
Yeshivat Maran burgundy, line-drawn gold icons, and the logo with a living link button.

Single source of truth for three consumers:
  * render.js    - canvas preview renderer (same fonts as the AE project)
  * make_jsx.py  - After Effects project builder
  * sfx.py       - sound-effect synthesis, one cue per visual event

usage: scene.py <work_dir> <out_dir>
"""
import json
import math
import os
import random
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import art  # noqa: E402

FPS = 30000 / 1001
W, H, DUR = 1080, 1920, 15.5
NFRAMES = int(round(DUR * FPS))

BURG, BURG_D = "#350A1B", "#2A0714"
GOLD, GOLD_HI, GOLD_LO = art.GOLD, art.GOLD_HI, art.GOLD_LO
CREAM, WHITE = "#F4E7CF", "#FFFFFF"

# fonts: key -> preview family, file, PostScript name (AE), base height / em as AE measures it
FONTS = {
    "H": {"family": "FRL Black", "file": "FrankRuhlLibre-Black.ttf", "ps": "FrankRuhlLibre-Black", "hb": 0.597},
    "S": {"family": "Assistant SB", "file": "Assistant-SemiBold.ttf", "ps": "Assistant-SemiBold", "hb": 0.570},
    "STAM": {"family": "Stam Sefarad", "file": "StamSefaradCLM.ttf", "ps": "StamSefaradCLM", "hb": 0.754},
    "U": {"family": "Open Sans SB", "file": "OpenSans-SemiBold.ttf", "ps": "OpenSans-SemiBold", "hb": 0.714},
}

WORK, OUT = sys.argv[1], sys.argv[2]


def snap(t):
    return round(t * FPS) / FPS


def frame_times(t0, t1):
    a, b = math.ceil(t0 * FPS - 1e-6), math.floor(t1 * FPS + 1e-6)
    return [k / FPS for k in range(a, b + 1)]


# ------------------------------------------------------------------ easing
def e_outBack(p, s=1.70158):
    c3 = s + 1
    return 1 + c3 * (p - 1) ** 3 + s * (p - 1) ** 2


EASE = {
    "linear": lambda p: p,
    "outExpo": lambda p: 1.0 if p >= 1 else 1 - 2 ** (-10 * p),
    "inExpo": lambda p: 0.0 if p <= 0 else 2 ** (10 * p - 10),
    "outCubic": lambda p: 1 - (1 - p) ** 3,
    "inCubic": lambda p: p ** 3,
    "inOutCubic": lambda p: 4 * p ** 3 if p < .5 else 1 - (-2 * p + 2) ** 3 / 2,
    "inOutSine": lambda p: -(math.cos(math.pi * p) - 1) / 2,
    "outQuad": lambda p: 1 - (1 - p) ** 2,
    "inQuad": lambda p: p * p,
    "outQuart": lambda p: 1 - (1 - p) ** 4,
    "outBack": e_outBack,
    "outBack14": lambda p: e_outBack(p, 1.4),
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
    """Start value plus non-overlapping eased moves; exported as per-frame linear keys."""

    def __init__(self, v0):
        self.v0 = v0
        self.moves = []  # (t0, t1, from|None, to, ease)

    def move(self, t0, dur, v, ease="outCubic", frm=None):
        t0 = snap(t0)
        t1 = snap(t0 + dur)
        if t1 <= t0:
            t1 = t0 + 1 / FPS
        self.moves.append((t0, t1, frm, v, ease))
        return self

    def move_to(self, t0, t1, v, ease="outCubic", frm=None):
        return self.move(t0, snap(t1) - snap(t0), v, ease, frm)

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
        ts = set()
        for (t0, t1, _, _, _) in self.moves:
            ts.add(round(t0, 4))
            ts.add(round(t1, 4))
            for t in frame_times(t0, t1):
                ts.add(round(t, 4))
        times = sorted(ts)
        vals = [rnd(self.at(t)) for t in times]
        keys = []
        for i, (t, v) in enumerate(zip(times, vals)):
            if 0 < i < len(vals) - 1 and vals[i - 1] == v and vals[i + 1] == v:
                continue
            keys.append([t, v])
        if len(keys) == 1:
            return keys[0][1]
        return {"k": keys, "h": 0}


def ex(v):
    return v.export() if hasattr(v, "export") else rnd(v)


# ------------------------------------------------------------------ text measuring (HarfBuzz, same fonts as AE)
_HB = {}


def measure(font, size, s):
    import uharfbuzz as hb
    if font not in _HB:
        blob = hb.Blob.from_file_path(os.path.join(WORK, "fonts", FONTS[font]["file"]))
        face = hb.Face(blob)
        _HB[font] = (hb.Font(face), face.upem)
    f, upem = _HB[font]
    buf = hb.Buffer()
    buf.add_str(s)
    buf.guess_segment_properties()
    hb.shape(f, buf)
    return sum(p.x_advance for p in buf.glyph_positions) / upem * size


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
        L["in"], L["out"] = round(snap(L["in"]), 4), round(min(self.dur, snap(L["out"])), 4)
        for k in ("pos", "scale", "rot", "op"):
            if k in L:
                L[k] = ex(L[k])
        for fx in L.get("fx", []):
            for k, v in list(fx.items()):
                if hasattr(v, "export"):
                    fx[k] = ex(v)
        for it in L.get("items", []):
            for k, v in list(it.items()):
                if hasattr(v, "export"):
                    it[k] = ex(v)
            if it.get("trim"):
                it["trim"] = {"s": ex(it["trim"]["s"]), "e": ex(it["trim"]["e"])}
        self.layers.append(L)
        return L

    def json(self):
        return {"name": self.name, "dur": self.dur, "w": W, "h": H, "fps": FPS, "layers": self.layers}


def char_anim(props, t0, dur, stag=0.0, ease="outCubic", mode="in", by="char", order="fwd", starts=None):
    sel = {"t0": round(snap(t0), 4), "dur": dur, "stag": stag, "ease": ease, "mode": mode, "by": by, "order": order}
    if starts:
        sel["starts"] = [round(snap(s), 4) for s in starts]
    return {"props": props, "sel": sel}


def words_in(starts, dy=46, blur=9, dur=0.62, ease="outCubic", scale=None):
    p = {"pos": [0, dy], "op": 0, "blur": blur}
    if scale:
        p["scale"] = [scale, scale]
    return char_anim(p, starts[0], dur, 0, ease, by="word", starts=starts)


def text(comp, name, s, font, size, cx, cy, *, fill=CREAM, grad=False, just="center", direction="rtl", anims=None,
         parent=None, tin=0.0, tout=None, pos=None, scale=None, op=None, rot=None, mb=True, fx=None, track=0,
         light_sweep=None):
    """Text layer positioned by the visual centre (cx, cy) of the letters' base band (AE point text:
    origin on the baseline at the justification point, anchor lifted by half the base height)."""
    hb = FONTS[font]["hb"] * size
    L = dict(name=name, type="text", text=s, font=font, size=size, fill=fill, stroke=None, sw=0,
             just=just, dir=direction, track=track, anims=anims or [], mb=mb, blend="normal",
             anchor=[0, round(-hb / 2, 2)], pos=pos if pos is not None else [cx, cy],
             scale=scale if scale is not None else [100, 100], rot=rot if rot is not None else 0,
             op=op if op is not None else 100, parent=parent, fx=list(fx or []))
    if grad:
        top, bot = (0.80, 0.30) if font == "STAM" else (0.66, 0.08)
        L["grad"] = {"c0": GOLD_HI, "c1": GOLD_LO, "y0": round(-top * size, 2), "y1": round(bot * size, 2)}
        L["fill"] = GOLD
    if light_sweep:
        L["light_sweep"] = light_sweep
    L["in"] = tin
    L["out"] = tout if tout is not None else comp.dur
    return comp.add(**L)


def null(comp, name, cx, cy, *, pos=None, scale=None, rot=None, parent=None, tin=0.0, tout=None):
    return comp.add(name=name, type="null", anchor=[0, 0], pos=pos if pos is not None else [cx, cy],
                    scale=scale if scale is not None else [100, 100], rot=rot if rot is not None else 0,
                    op=100, parent=parent, **{"in": tin, "out": tout if tout is not None else comp.dur})


def shape(comp, name, items, *, anchor=(0, 0), pos=(0, 0), scale=(100, 100), rot=0, op=100, parent=None,
          tin=0.0, tout=None, mb=True, blend="normal", fx=None, **extra):
    L = dict(name=name, type="shape", items=items, anchor=list(anchor),
             pos=pos if hasattr(pos, "export") else list(pos),
             scale=scale if hasattr(scale, "export") else list(scale), rot=rot, op=op, parent=parent,
             mb=mb, blend=blend, fx=list(fx or []))
    L.update(extra)
    L["in"] = tin
    L["out"] = tout if tout is not None else comp.dur
    return comp.add(**L)


def image(comp, name, src, w, h, *, cx, cy, scale=(100, 100), op=100, fx=None, tin=0.0, tout=None, mb=True):
    return comp.add(name=name, type="image", src=src, w=w, h=h, anchor=[w / 2, h / 2], pos=[cx, cy],
                    scale=scale, rot=0, op=op, parent=None, mb=mb, blend="normal", fx=list(fx or []),
                    **{"in": tin, "out": tout if tout is not None else comp.dur})


def rect_item(cx, cy, w, h, r=0, fill=None, stroke=None, sw=0, op=None):
    it = {"kind": "rect", "c": [round(cx, 2), round(cy, 2)], "size": [w, h], "r": r, "fill": fill,
          "stroke": stroke, "sw": sw}
    if op is not None:
        it["op"] = op
    return it


def ellipse_item(cx, cy, w, h, fill=None, stroke=None, sw=0):
    return {"kind": "ellipse", "c": [cx, cy], "size": [w, h], "fill": fill, "stroke": stroke, "sw": sw}


def glow_item(cx, cy, w, h, color):
    """Soft feathered ellipse (AE: ellipse + gaussian blur)."""
    return {"kind": "glow", "c": [cx, cy], "size": [w, h], "fill": color}


def line_item(st, t0=None, dur=0.6, ease="inOutCubic", s=None, e=None, op=None, color=None):
    """Gold stroke from art.py, drawn on with Trim Paths (end 0 -> 100 %) unless e is given."""
    if e is None:
        e = Track(0).move(t0, dur, 100, ease) if t0 is not None else 100
    it = {"kind": "path", "d": st["d"], "fill": None, "stroke": color or st.get("color", GOLD), "sw": st["sw"],
          "cap": "round", "join": "round", "evenodd": False, "len": st["len"],
          "trim": {"s": s if s is not None else 0, "e": e}}
    if op is not None:
        it["op"] = op
    return it


def fill_item(d, color, op=None):
    it = {"kind": "path", "d": d, "fill": color, "stroke": None, "sw": 0, "evenodd": False}
    if op is not None:
        it["op"] = op
    return it


def blur_fx(track):
    return {"type": "blur", "amt": track}


def exit_tracks(cx, cy, t_out, dur=0.28, dy=-38, blur=12, pos0=None):
    """Position / opacity / blur tracks for an element that sits still and leaves upwards, softening."""
    pos = pos0 if pos0 is not None else Track([cx, cy])
    pos.move(t_out, dur, [cx, cy + dy], "inCubic")
    op = Track(100).move(t_out, dur, 0, "inCubic")
    bl = Track(0).move(t_out, dur, blur, "inCubic")
    return pos, op, bl


# ------------------------------------------------------------------ data
WORDS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "words.json"), encoding="utf-8"))
PH = WORDS["phrases"]
T = {}
for ph in PH:
    for w, t in ph:
        T.setdefault(w, t)
LEAD = 0.05          # entrances start a hair before the word is heard

MAIN = Comp("MAIN", DUR)

# ======================================================================================
# Backdrop: burgundy, slow warm light, gold dust, corner flourishes
# ======================================================================================
image(MAIN, "BG", "bg.png", W, H, cx=540, cy=960, mb=False)
shape(MAIN, "BG_light", [glow_item(0, 0, 1300, 1300, "#9C2A4E")],
      pos=Track([330, 560]).move(0, DUR, [760, 1260], "inOutSine"), op=26, blend="add", mb=False)

rng = random.Random(1818)
for i in range(14):
    x0, y0 = rng.uniform(70, 1010), rng.uniform(260, 1700)
    drift = rng.uniform(50, 150)
    size = rng.uniform(4, 9)
    twinkle = Track(0)
    t = rng.uniform(0.0, 1.2)
    twinkle.move(t, 0.8, rng.uniform(25, 50), "inOutSine")
    while t < DUR - 1.5:
        t += rng.uniform(1.1, 2.0)
        twinkle.move(t, rng.uniform(0.7, 1.2), rng.uniform(10, 24) if (i + int(t)) % 2 else rng.uniform(28, 55),
                     "inOutSine")
    shape(MAIN, "DUST_%02d" % i, [glow_item(0, 0, size * 3.2, size * 3.2, "#F2CC7A")],
          pos=Track([x0, y0]).move(0, DUR, [x0 + rng.uniform(-30, 30), y0 - drift], "linear"),
          op=twinkle, blend="add", mb=False)

for name, cx, cy, sx, sy, t0 in (("CORNER_tr", 1012, 96, -100, 100, 0.10), ("CORNER_bl", 68, 1824, 100, -100, 0.25)):
    items = []
    for k, st in enumerate(art.corner(196)):
        items.append(line_item(st, t0 + 0.12 * k, 1.1 if k == 0 else 0.8, "inOutSine"))
    shape(MAIN, name, items, pos=(cx, cy), scale=(sx, sy), op=55, mb=False)

# ======================================================================================
# A  0.00-2.50  "יש עוד ילד שמחכה לארוחה שלו היום": empty plate with rising steam
# ======================================================================================
A_OUT = 2.30
AY = 80
items = []
for st in art.plate():
    part = st["part"]
    t0, d = {"rim": (0.05, 0.70), "well": (0.28, 0.60), "fork": (0.38, 0.55), "knife": (0.44, 0.55)}[part]
    items.append(line_item(st, t0, d, "inOutCubic"))
for i, st in enumerate(art.steam()):
    t0 = 0.62 + 0.16 * i
    items.append(line_item(st, s=Track(0).move(t0 + 0.95, 1.10, 100, "inOutSine"),
                           e=Track(0).move(t0, 1.00, 100, "outCubic")))
pos, op, bl = exit_tracks(540, 668 + AY, A_OUT)
shape(MAIN, "A_plate", items, pos=pos, scale=Track([94, 94]).move(0, A_OUT, [100, 100], "outCubic"),
      op=op, fx=[blur_fx(bl)], tin=0, tout=A_OUT + 0.4)
cue(0.06, "air_rise", dur=1.3, gain=-17)

starts = [PH[0][1][1] - LEAD, PH[0][2][1] - LEAD, T["שמחכה"] - LEAD]
pos, op, bl = exit_tracks(540, 928 + AY, A_OUT + 0.04)
text(MAIN, "A_big", "עוד ילד מחכה", "H", 168, 540, 928 + AY, grad=True, anims=[words_in(starts)],
     pos=pos, op=op, fx=[blur_fx(bl)], tin=starts[0], tout=A_OUT + 0.45)
cue(T["שמחכה"] - 0.01, "click_soft", gain=-25)

starts = [T["לארוחה"] - LEAD, T["שלו"] - LEAD, T["היום"] - LEAD]
pos, op, bl = exit_tracks(540, 1066 + AY, A_OUT + 0.08)
text(MAIN, "A_small", "לארוחה שלו היום", "S", 62, 540, 1066 + AY, fill=CREAM,
     anims=[words_in(starts, dy=30, blur=6, dur=0.5)], pos=pos, op=op, fx=[blur_fx(bl)], tin=starts[0],
     tout=A_OUT + 0.5)

# ======================================================================================
# B  2.50-4.75  "בבקשה, היכנסו עכשיו והאכילו": big call to action + a screen-tap ring
# ======================================================================================
B_OUT = 4.48
pos, op, bl = exit_tracks(540, 772, B_OUT)
text(MAIN, "B_please", "בבקשה", "S", 64, 540, 772, fill=CREAM, anims=[words_in([T["בבקשה"]], 30, 6, 0.5)],
     pos=pos, op=op, fx=[blur_fx(bl)], tin=T["בבקשה"], tout=B_OUT + 0.4)

starts = [T["היכנסו"] - LEAD, T["עכשיו"] - LEAD]
pos, op, bl = exit_tracks(540, 906, B_OUT + 0.03)
text(MAIN, "B_big", "היכנסו עכשיו", "H", 174, 540, 906, grad=True, anims=[words_in(starts, scale=108)],
     pos=pos, op=op, fx=[blur_fx(bl)], tin=starts[0], tout=B_OUT + 0.45)

pos, op, bl = exit_tracks(540, 1040, B_OUT + 0.06)
text(MAIN, "B_feed", "והאכילו", "S", 64, 540, 1040, fill=CREAM,
     anims=[words_in([T["והאכילו"] - LEAD], 30, 6, 0.5)], pos=pos, op=op, fx=[blur_fx(bl)],
     tin=T["והאכילו"] - LEAD, tout=B_OUT + 0.45)

T_TAP = T["עכשיו"] + 0.08
TAP_Y = 1192
null(MAIN, "B_tap", 540, TAP_Y, tin=T_TAP - 0.1, tout=B_OUT + 0.4)
shape(MAIN, "B_tap_dot", [ellipse_item(0, 0, 30, 30, fill=GOLD)], parent="B_tap",
      scale=Track([0, 0]).move(T_TAP, 0.20, [100, 100], "outBack").move(T_TAP + 0.55, 0.40, [70, 70], "inOutSine"),
      op=Track(0).move(T_TAP, 0.08, 100, "linear").move(T_TAP + 0.60, 0.45, 0, "inOutSine"),
      tin=T_TAP, tout=T_TAP + 1.1)
for k, dt in enumerate((0.0, 0.16)):
    shape(MAIN, "B_tap_ring%d" % (k + 1), [line_item(art.tap_ring(50), e=100)], parent="B_tap",
          scale=Track([28, 28]).move(T_TAP + dt, 0.85, [170, 170], "outCubic"),
          op=Track(0).move(T_TAP + dt, 0.06, 95 - 25 * k, "linear").move(T_TAP + dt + 0.12, 0.7, 0, "inQuad"),
          tin=T_TAP + dt, tout=T_TAP + dt + 0.95)
shape(MAIN, "B_tap_halo", [glow_item(0, 0, 150, 150, GOLD)], parent="B_tap", blend="add",
      op=Track(0).move(T_TAP, 0.08, 40, "linear").move(T_TAP + 0.1, 0.6, 0, "outCubic"), tin=T_TAP,
      tout=T_TAP + 0.8, mb=False)
cue(T_TAP, "tap", gain=-17)

# ======================================================================================
# C  4.75-7.40  "עוד ילד רעב במסגרת הפעילות של מרן": bowl with steam, then the name "מרן"
# ======================================================================================
C_OUT1 = T["של"] - 0.12        # bowl + "עוד ילד רעב" leave just before "מרן"
CY = 80
items = []
for st in art.bowl():
    t0, d = {"rim": (4.72, 0.62), "body": (4.80, 0.62), "foot": (5.10, 0.40), "inner": (5.12, 0.45)}[st["part"]]
    items.append(line_item(st, t0, d, "inOutCubic"))
for i, st in enumerate(art.steam(-30, -186)):
    t0 = 5.20 + 0.14 * i
    items.append(line_item(st, s=Track(0).move(t0 + 0.75, 0.95, 100, "inOutSine"),
                           e=Track(0).move(t0, 0.90, 100, "outCubic")))
pos, op, bl = exit_tracks(540, 640 + CY, C_OUT1)
shape(MAIN, "C_bowl", items, pos=pos, scale=Track([94, 94]).move(4.70, 1.9, [100, 100], "outCubic"), op=op,
      fx=[blur_fx(bl)], tin=4.70, tout=C_OUT1 + 0.4)
cue(4.74, "swoosh_soft", dur=0.55, gain=-17)

starts = [4.80, 4.90, T["רעב"] - LEAD]
pos, op, bl = exit_tracks(540, 930 + CY, C_OUT1 + 0.03)
text(MAIN, "C_big", "עוד ילד רעב", "H", 180, 540, 930 + CY, grad=True, anims=[words_in(starts)],
     pos=pos, op=op, fx=[blur_fx(bl)], tin=starts[0], tout=C_OUT1 + 0.45)

starts = [T["במסגרת"] - LEAD, T["הפעילות"] - LEAD, T["של"] - LEAD]
M_OUT = 7.54
M_DUR = 0.22
mpos = Track([540, 1072 + CY]).move(C_OUT1 + 0.02, 0.42, [540, 712], "inOutCubic")
pos, op, bl = exit_tracks(540, 712, M_OUT, M_DUR, pos0=mpos)
text(MAIN, "C_frame", "במסגרת הפעילות של", "S", 60, 540, 1072 + CY, fill=CREAM,
     anims=[words_in(starts, dy=28, blur=6, dur=0.5)], pos=pos, op=op, fx=[blur_fx(bl)], tin=starts[0],
     tout=M_OUT + 0.4)

T_M = T["מרן"]
shape(MAIN, "C_aura", [glow_item(0, 0, 900, 560, GOLD)], pos=(540, 900), blend="add",
      op=Track(0).move(T_M - 0.02, 0.45, 20, "outCubic").move(M_OUT, M_DUR, 0, "inCubic"),
      scale=Track([70, 70]).move(T_M - 0.02, 0.9, [100, 100], "outCubic"), tin=T_M - 0.05, tout=M_OUT + 0.4,
      mb=False)
pos, op, bl = exit_tracks(540, 920, M_OUT + 0.02, M_DUR, dy=-30)
w_m = measure("STAM", 400, "מרן")
text(MAIN, "C_maran", "מרן", "STAM", 400, 540, 920, grad=True,
     anims=[char_anim({"op": 0, "blur": 14, "scale": [114, 114], "pos": [0, 22]}, T_M - 0.05, 0.40, 0.04,
                      "outCubic")],
     pos=pos, op=op, fx=[blur_fx(bl)], tin=T_M - 0.04, tout=M_OUT + 0.45,
     light_sweep={"t0": round(snap(T_M + 0.16), 4), "t1": round(snap(T_M + 0.72), 4), "x0": round(-w_m / 2 - 140),
                  "x1": round(w_m / 2 + 140), "width": 90, "op": 0.85})
cue(T_M + 0.02, "bell", gain=-20, note=0)

items = [line_item(st, T_M + 0.10 + (0.0 if st["part"] in ("diamond",) else 0.08), 0.55, "outCubic")
         for st in art.divider(220)]
pos, op, bl = exit_tracks(540, 1262, M_OUT + 0.02, M_DUR, dy=-30)
shape(MAIN, "C_divider", items, pos=pos, op=op, fx=[blur_fx(bl)], tin=T_M + 0.08, tout=M_OUT + 0.45)

# ======================================================================================
# D  7.40-10.05  "בזכות העזרה שלכם, עם 18 שקלים": hands with a heart, then a huge "₪ 18" with coins
# ======================================================================================
D_OUT1 = 8.46
items = []
for st in art.hands():
    part = st["part"]
    if part == "heart":
        continue
    t0, d = {"hand": (7.72, 0.60), "finger": (8.00, 0.38)}[part]
    items.append(line_item(st, t0, d, "inOutCubic"))
DY = 60
pos, op, bl = exit_tracks(540, 660 + DY, D_OUT1)
shape(MAIN, "D_hands", items, pos=pos, op=op, fx=[blur_fx(bl)], tin=7.70, tout=D_OUT1 + 0.4)
heart = art.heart(0, 0, 0.92, 6)
pos, op, bl = exit_tracks(540, 644 + DY, D_OUT1)
shape(MAIN, "D_heart", [line_item(heart, 8.00, 0.50, "inOutCubic")], pos=pos,
      scale=Track([100, 100]).move(8.30, 0.14, [112, 112], "outQuad").move(8.44, 0.30, [100, 100], "inOutSine"),
      op=op, fx=[blur_fx(bl)], tin=7.98, tout=D_OUT1 + 0.4)
cue(7.64, "swoosh_soft", dur=0.6, gain=-18)

pos, op, bl = exit_tracks(540, 896 + DY, D_OUT1 + 0.03)
text(MAIN, "D_thanks", "בזכות", "S", 64, 540, 896 + DY, fill=CREAM,
     anims=[words_in([7.74], 30, 6, 0.5)], pos=pos, op=op, fx=[blur_fx(bl)],
     tin=7.74, tout=D_OUT1 + 0.45)
starts = [7.80, T["שלכם"] - LEAD]
pos, op, bl = exit_tracks(540, 1034 + DY, D_OUT1 + 0.05)
text(MAIN, "D_help", "העזרה שלכם", "H", 172, 540, 1034 + DY, grad=True, anims=[words_in(starts)],
     pos=pos, op=op, fx=[blur_fx(bl)], tin=starts[0], tout=D_OUT1 + 0.5)

# "₪ 18": the shekel sign sits to the left of the number, as Hebrew text renders "18 ₪"
T18 = T["שמונה"] - 0.02
N_SIZE, S_SIZE, GAP = 460, 250, 30
w18, wsh = measure("H", N_SIZE, "18"), measure("H", S_SIZE, "₪")
left = 540 - (w18 + GAP + wsh) / 2
cx_sh, cx_18 = left + wsh / 2, left + wsh + GAP + w18 / 2
BASE_Y = 1080
cy_18 = BASE_Y - FONTS["H"]["hb"] * N_SIZE / 2
cy_sh = BASE_Y - FONTS["H"]["hb"] * S_SIZE / 2
N_OUT = 9.86
shape(MAIN, "D_aura", [glow_item(0, 0, 900, 620, GOLD)], pos=(540, 980), blend="add",
      op=Track(0).move(T18, 0.4, 18, "outCubic").move(N_OUT, 0.34, 0, "inCubic"), tin=T18, tout=N_OUT + 0.4,
      mb=False)
pos, op, bl = exit_tracks(cx_18, cy_18, N_OUT, dy=-34)
text(MAIN, "D_18", "18", "H", N_SIZE, cx_18, cy_18, grad=True, pos=pos,
     scale=Track([72, 72]).move(T18, 0.55, [100, 100], "outBack14"),
     op=Track(0).move(T18, 0.16, 100, "linear").move(N_OUT, 0.34, 0, "inCubic"),
     fx=[blur_fx(Track(18).move(T18, 0.32, 0, "outCubic").move(N_OUT, 0.34, 12, "inCubic"))], tin=T18,
     tout=N_OUT + 0.4,
     light_sweep={"t0": round(snap(9.40), 4), "t1": round(snap(9.86), 4), "x0": round(-w18 / 2 - 120),
                  "x1": round(w18 / 2 + 120), "width": 80, "op": 0.8})
cue(T18 + 0.04, "click_soft", gain=-21, pitch=0.8)
T_SH = T["שקלים"] - LEAD
pos = Track([cx_sh + 46, cy_sh]).move(T_SH, 0.5, [cx_sh, cy_sh], "outCubic")
pos, op, bl = exit_tracks(cx_sh, cy_sh, N_OUT + 0.02, dy=-34, pos0=pos)
text(MAIN, "D_shekel", "₪", "H", S_SIZE, cx_sh, cy_sh, grad=True, pos=pos,
     op=Track(0).move(T_SH, 0.3, 100, "outCubic").move(N_OUT + 0.02, 0.34, 0, "inCubic"),
     fx=[blur_fx(Track(12).move(T_SH, 0.35, 0, "outCubic").move(N_OUT + 0.02, 0.34, 12, "inCubic"))],
     tin=T_SH, tout=N_OUT + 0.45)

COIN_Y = 1262
for k, (dt, dx) in enumerate(((0.20, -6), (0.34, 8), (0.48, -3))):
    tc = T18 + dt
    y_rest = COIN_Y - 30 * k
    parts = art.coin_parts(0, 0, 100, 27, 20)
    items = [fill_item(p["d"], p["fill"]) if p.get("fill") else
             {"kind": "path", "d": p["d"], "fill": None, "stroke": p["color"], "sw": p["sw"], "cap": "round",
              "join": "round", "evenodd": False} for p in parts]
    pos = Track([540 + dx, y_rest - 260]).move(tc, 0.42, [540 + dx, y_rest], "outBack14")
    pos, op, bl = exit_tracks(540 + dx, y_rest, N_OUT + 0.04, dy=-34, pos0=pos)
    shape(MAIN, "D_coin%d" % (k + 1), items, pos=pos,
          op=Track(0).move(tc, 0.14, 100, "linear").move(N_OUT + 0.04, 0.34, 0, "inCubic"), fx=[blur_fx(bl)],
          tin=tc, tout=N_OUT + 0.45)
    cue(tc + 0.36, "coin", gain=-23 - 2 * k, pitch=1.0 + 0.07 * k)

# ======================================================================================
# E  10.05-12.20  "תזכו לשפע, לברכה ולישועות": a right-aligned list, icon beside each word
# ======================================================================================
E_OUT = 11.98
E_DUR = 0.22
pos, op, bl = exit_tracks(540, 650, E_OUT, E_DUR)
text(MAIN, "E_merit", "תזכו", "S", 64, 540, 650, fill=CREAM, anims=[words_in([T["תזכו"] - LEAD], 30, 6, 0.5)],
     pos=pos, op=op, fx=[blur_fx(bl)], tin=T["תזכו"] - LEAD, tout=E_OUT + 0.4)

ROW_SIZE = 140
ROWS = [("שפע", T["לשפע"], art.wheat(), 0.52, 820), ("ברכה", T["לברכה"], art.sparkle(), 0.62, 995),
        ("ישועות", T["ולישועות"], art.sunrise(), 0.60, 1170)]
ICON_X, WORD_RIGHT = 730, 626
for k, (word, tw, icon, isc, y) in enumerate(ROWS):
    t0 = tw - 0.06
    items = [line_item(st, t0 + 0.04 * j, 0.55, "outCubic") for j, st in enumerate(icon)]
    pos, op, bl = exit_tracks(ICON_X, y, E_OUT + 0.03 * k, E_DUR)
    shape(MAIN, "E_icon%d" % (k + 1), items, pos=pos, scale=(isc * 100, isc * 100), op=op, fx=[blur_fx(bl)],
          tin=t0, tout=E_OUT + 0.5)
    ww = measure("H", ROW_SIZE, word)
    cx = WORD_RIGHT - ww / 2
    if k < 2:
        pos, op, bl = exit_tracks(cx, y, E_OUT + 0.03 * k, E_DUR)
        text(MAIN, "E_word%d" % (k + 1), word, "H", ROW_SIZE, cx, y, grad=True,
             anims=[char_anim({"pos": [26, 0], "op": 0, "blur": 8}, t0, 0.5, 0.04, "outCubic")],
             pos=pos, op=op, fx=[blur_fx(bl)], tin=t0, tout=E_OUT + 0.45)
    else:
        # "ישועות" travels to the centre and grows into the final line
        Y_YESH, SC = 868, round(190 / ROW_SIZE * 100, 2)
        pos = Track([cx, y]).move(12.04, 0.42, [540, Y_YESH], "inOutCubic")
        F_OUT = 12.86
        pos.move(F_OUT, 0.24, [540, Y_YESH - 30], "inCubic")
        w_y = ww
        text(MAIN, "E_word3", word, "H", ROW_SIZE, cx, y, grad=True,
             anims=[char_anim({"pos": [26, 0], "op": 0, "blur": 8}, t0, 0.5, 0.04, "outCubic")],
             pos=pos, scale=Track([100, 100]).move(12.04, 0.42, [SC, SC], "inOutCubic"),
             op=Track(100).move(F_OUT, 0.24, 0, "inCubic"),
             fx=[blur_fx(Track(0).move(F_OUT, 0.24, 14, "inCubic"))], tin=t0, tout=F_OUT + 0.3,
             light_sweep={"t0": round(snap(12.36), 4), "t1": round(snap(12.84), 4), "x0": round(-ww / 2 - 90),
                          "x1": round(ww / 2 + 90), "width": 60, "op": 0.85})
    cue(t0 + 0.04, "tick", gain=-24, pitch=1.0 + 0.12 * k)

# ======================================================================================
# F  12.10-12.95  "ישועות גדולות"
# ======================================================================================
F_OUT = 12.86
T_G = 12.32
w_g = measure("H", 190, "גדולות")
pos, op, bl = exit_tracks(540, 1062, F_OUT + 0.02, dur=0.24, dy=-30, blur=14)
text(MAIN, "F_great", "גדולות", "H", 190, 540, 1062, grad=True, anims=[words_in([T_G], dy=50, blur=12, dur=0.6)],
     pos=pos, op=op, fx=[blur_fx(bl)], tin=T_G, tout=F_OUT + 0.4,
     light_sweep={"t0": round(snap(12.44), 4), "t1": round(snap(12.88), 4), "x0": round(-w_g / 2 - 120),
                  "x1": round(w_g / 2 + 120), "width": 90, "op": 0.85})
for k, (sx, sy, r, t0) in enumerate(((236, 790, 30, 12.40), (850, 1150, 22, 12.56), (860, 760, 16, 12.66))):
    st = art.star4(0, 0, r, 3.5)
    shape(MAIN, "F_twinkle%d" % (k + 1), [line_item(st, e=100)], pos=(sx, sy),
          scale=Track([0, 0]).move(t0, 0.25, [100, 100], "outBack").move(t0 + 0.35, 0.3, [0, 0], "inCubic"),
          rot=Track(0).move(t0, 0.7, 45, "outCubic"), tin=t0, tout=t0 + 0.7, mb=False)
cue(12.12, "swoosh_long", dur=0.95, gain=-18)

# ======================================================================================
# G  12.95-15.50  logo, link button, bouncing arrow
# ======================================================================================
T_L = 13.00
LOGO_W, LOGO_H = 1127, 1360
LOGO_Y, LOGO_SC = 744, 55.0
shape(MAIN, "G_bloom", [glow_item(0, 0, 1000, 1000, GOLD)], pos=(540, LOGO_Y), blend="add",
      op=Track(0).move(T_L - 0.06, 0.28, 46, "outQuad").move(T_L + 0.30, 1.0, 16, "inOutSine"),
      scale=Track([50, 50]).move(T_L - 0.06, 1.2, [118, 118], "outCubic"), tin=T_L - 0.06, mb=False)
rays = []
for k in range(18):
    a = math.radians(k * 20)
    r0, r1 = 470, 560 if k % 2 else 600
    rays.append({"kind": "path", "d": "M%s L%s" % (art.P(math.cos(a) * r0, math.sin(a) * r0),
                                                    art.P(math.cos(a) * r1, math.sin(a) * r1)),
                 "fill": None, "stroke": GOLD, "sw": 2.5, "cap": "round", "join": "round", "evenodd": False})
shape(MAIN, "G_rays", rays, pos=(540, LOGO_Y), rot=Track(0).move(T_L, DUR - T_L, 14, "linear"),
      scale=Track([86, 86]).move(T_L, 1.0, [100, 100], "outCubic"), blend="add",
      op=Track(0).move(T_L + 0.15, 0.8, 22, "outCubic"), tin=T_L, mb=False)
image(MAIN, "G_logo", "logo.png", LOGO_W, LOGO_H, cx=540, cy=LOGO_Y,
      scale=Track([LOGO_SC * 0.88] * 2).move(T_L, 0.95, [LOGO_SC] * 2, "outCubic")
      .move(T_L + 0.95, DUR - T_L - 0.95, [LOGO_SC * 1.025] * 2, "linear"),
      op=Track(0).move(T_L, 0.42, 100, "outQuad"),
      fx=[blur_fx(Track(22).move(T_L, 0.62, 0, "outCubic"))], tin=T_L)
cue(T_L - 0.04, "bloom", dur=1.4, gain=-25)
cue(T_L + 0.30, "bell", gain=-18, note=1)
for k, (sx, sy, r, t0) in enumerate(((262, 420, 26, 13.45), (826, 1060, 20, 13.95), (836, 380, 16, 14.55),
                                       (248, 1080, 14, 15.0))):
    st = art.star4(0, 0, r, 3.2)
    shape(MAIN, "G_twinkle%d" % (k + 1), [line_item(st, e=100)], pos=(sx, sy),
          scale=Track([0, 0]).move(t0, 0.28, [100, 100], "outBack").move(t0 + 0.42, 0.34, [0, 0], "inCubic"),
          rot=Track(0).move(t0, 0.8, 45, "outCubic"), tin=t0, tout=min(DUR, t0 + 0.8), mb=False)

# link button: gold pill, burgundy URL, breathing, a light glint passing over it
T_B = 13.56
BTN_Y, BTN_W, BTN_H = 1264, 640, 104
bsc = Track([78, 78]).move(T_B, 0.46, [100, 100], "outBack14")
t = T_B + 0.6
while t < DUR:
    bsc.move(t, 0.8, [103.5, 103.5], "inOutSine")
    bsc.move(t + 0.8, 0.8, [100, 100], "inOutSine")
    t += 1.6
null(MAIN, "G_btn", 540, BTN_Y, scale=bsc, tin=T_B)
bop = Track(0).move(T_B, 0.2, 100, "linear")
shape(MAIN, "G_btn_shadow", [glow_item(0, 10, BTN_W + 80, BTN_H + 70, "#12030A")], parent="G_btn", op=bop,
      tin=T_B, mb=False)
shape(MAIN, "G_btn_base", [rect_item(0, 0, BTN_W, BTN_H, BTN_H / 2, fill="#DDA94C"),
                           rect_item(0, -BTN_H * 0.24, BTN_W - 34, BTN_H * 0.40, BTN_H * 0.2, fill="#F3CF85",
                                     op=38),
                           rect_item(0, 0, BTN_W - 12, BTN_H - 12, (BTN_H - 12) / 2, stroke="#FBE3A8", sw=2,
                                     op=70)],
      parent="G_btn", op=bop, tin=T_B)
shape(MAIN, "G_btn_glint", [glow_item(0, 0, 70, 300, "#FFF6DC")], parent="G_btn", blend="add",
      pos=Track([-420, 0]).move(T_B + 0.55, 0.85, [420, 0], "inOutSine").move(T_B + 0.55 + 1.6, 0.01, [-420, 0],
                                                                                "linear")
      .move(T_B + 0.55 + 1.62, 0.85, [420, 0], "inOutSine"),
      rot=18, op=Track(0).move(T_B + 0.5, 0.1, 80, "linear"), tin=T_B + 0.5, matte="G_btn_matte", mb=False)
shape(MAIN, "G_btn_matte", [rect_item(0, 0, BTN_W, BTN_H, BTN_H / 2, fill=WHITE)], parent="G_btn", tin=T_B + 0.5,
      hidden_matte=True, mb=False)
text(MAIN, "G_btn_url", "harav-ovadya.co.il", "U", 46, 0, 0, fill="#3A0B1D", direction="ltr", parent="G_btn",
     op=Track(0).move(T_B + 0.08, 0.25, 100, "linear"), tin=T_B, mb=False)
cue(T_B + 0.02, "click_soft", gain=-22, pitch=1.15)

# arrow: two chevrons, a soft bounce and a cascading glow
T_A = 13.92
ARR_Y = 1370
apos = Track([540, ARR_Y])
t = T_A
while t < DUR:
    apos.move(t, 0.45, [540, ARR_Y + 14], "inOutSine")
    apos.move(t + 0.45, 0.45, [540, ARR_Y], "inOutSine")
    t += 0.9
null(MAIN, "G_arrow", 540, ARR_Y, pos=apos, tin=T_A)
for k in range(2):
    cop = Track(0).move(T_A + 0.08 * k, 0.3, 100 - 30 * k, "outCubic")
    t = T_A + 0.45 + 0.12 * k
    while t < DUR:
        cop.move(t, 0.45, 45 if k == 0 else 100, "inOutSine")
        cop.move(t + 0.45, 0.45, 100 if k == 0 else 55, "inOutSine")
        t += 0.9
    shape(MAIN, "G_chev%d" % (k + 1), [line_item(art.chevron(0, 30, 13, 6), e=100)], parent="G_arrow",
          pos=(0, 32 * k), op=cop, tin=T_A)
cue(T_A + 0.45, "boop", gain=-27)

# ------------------------------------------------------------------ output
os.makedirs(OUT, exist_ok=True)
scene = {"w": W, "h": H, "fps": FPS, "dur": DUR, "frames": NFRAMES,
         "fonts": {k: {"family": v["family"], "file": v["file"], "ps": v["ps"], "hb": v["hb"]} for k, v in FONTS.items()},
         "comps": {k: v.json() for k, v in COMPS.items()}, "main": "MAIN", "vo_end": WORDS["vo_end"]}
json.dump(scene, open(os.path.join(OUT, "scene.json"), "w"), ensure_ascii=False)
CUES.sort(key=lambda c: c["t"])
for c in CUES:
    key = "%s@%.4f" % (c["kind"], c["t"])
    c["synth_seed"] = 5000 + zlib.crc32(key.encode()) % 100000
json.dump(CUES, open(os.path.join(OUT, "cues.json"), "w"), ensure_ascii=False, indent=0)
print("layers MAIN=%d cues=%d frames=%d" % (len(MAIN.layers), len(CUES), NFRAMES))
