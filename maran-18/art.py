"""Vector line art for the Maran "18 NIS" video (gold strokes on burgundy).

Every icon is a list of strokes in its own layer space (origin = icon centre, about +-200 px).
Each stroke is a single sub-path so After Effects' Trim Paths and the preview's dash-based
trim draw it the same way (start = first vertex).  Paths use only M / L / C / Z.
"""
import math

GOLD = "#E3B25A"         # line gold (a touch lighter than the site's #E9AF2C so thin lines read)
GOLD_HI = "#F7D98E"
GOLD_LO = "#A8702A"


def f(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


def P(x, y):
    return f(x) + "," + f(y)


# ------------------------------------------------------------------ path builders
def arc(cx, cy, rx, ry, a0, a1, move=True):
    """Elliptical arc from angle a0 to a1 (degrees, screen space: 0 = +x, 90 = down) as cubic segments."""
    n = max(1, int(math.ceil(abs(a1 - a0) / 90.0 - 1e-9)))
    da = math.radians(a1 - a0) / n
    k = 4.0 / 3.0 * math.tan(da / 4.0)
    out = []
    a = math.radians(a0)
    x0, y0 = cx + rx * math.cos(a), cy + ry * math.sin(a)
    if move:
        out.append("M" + P(x0, y0))
    for _ in range(n):
        b = a + da
        x1, y1 = cx + rx * math.cos(b), cy + ry * math.sin(b)
        c1 = (x0 - k * rx * math.sin(a), y0 + k * ry * math.cos(a))
        c2 = (x1 + k * rx * math.sin(b), y1 - k * ry * math.cos(b))
        out.append("C" + P(*c1) + " " + P(*c2) + " " + P(x1, y1))
        a, x0, y0 = b, x1, y1
    return " ".join(out)


def ellipse(cx, cy, rx, ry, start=90.0, ccw=False):
    """Closed ellipse starting at angle `start` (default: bottom centre)."""
    return arc(cx, cy, rx, ry, start, start + (-360 if ccw else 360)) + " Z"


def smooth(pts, closed=False, tension=1.0):
    """Catmull-Rom spline through pts as cubic Beziers."""
    n = len(pts)
    out = ["M" + P(*pts[0])]
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p0 = pts[(i - 1) % n] if (closed or i > 0) else pts[i]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if (closed or i + 2 < n) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) * tension / 6.0, p1[1] + (p2[1] - p0[1]) * tension / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension / 6.0, p2[1] - (p3[1] - p1[1]) * tension / 6.0)
        out.append("C" + P(*c1) + " " + P(*c2) + " " + P(*p2))
    if closed:
        out.append("Z")
    return " ".join(out)


def wave(x, y0, y1, amp, wl, phase=0.0, taper=True, n=28):
    """Rising steam wisp from (x, y0) up to y1 (y1 < y0)."""
    pts = []
    for i in range(n + 1):
        p = i / n
        y = y0 + (y1 - y0) * p
        a = amp * (0.35 + 0.65 * p) if taper else amp
        pts.append((x + a * math.sin(2 * math.pi * (y0 - y) / wl + phase), y))
    return smooth(pts)


def poly(pts, closed=False):
    s = "M" + P(*pts[0]) + " " + " ".join("L" + P(*p) for p in pts[1:])
    return s + (" Z" if closed else "")


def xform(d, sx=1.0, sy=1.0, rot=0.0, tx=0.0, ty=0.0):
    """Scale, rotate (deg), then translate every coordinate of a path."""
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    out = []
    for tok in d.split():
        cmd = ""
        if tok[0] in "MLCZ":
            cmd, tok = tok[0], tok[1:]
        if not tok:
            out.append(cmd)
            continue
        x, y = map(float, tok.split(","))
        x, y = x * sx, y * sy
        x, y = x * c - y * s + tx, x * s + y * c + ty
        out.append(cmd + P(x, y))
    return " ".join(out)


# ------------------------------------------------------------------ path length (for trim / dashes)
def _pts(d):
    toks = d.replace(",", " ").split()
    i, cur, start, segs = 0, None, None, []
    cmd = None
    while i < len(toks):
        t = toks[i]
        if t[0] in "MLCZ":
            cmd = t[0]
            rest = t[1:]
            if rest:
                toks[i] = rest
            else:
                i += 1
            if cmd == "Z":
                if cur and start and cur != start:
                    segs.append(("L", cur, start))
                cur = start
                continue
        if cmd == "M":
            cur = (float(toks[i]), float(toks[i + 1]))
            start = cur
            i += 2
            cmd = "L"
        elif cmd == "L":
            p = (float(toks[i]), float(toks[i + 1]))
            segs.append(("L", cur, p))
            cur = p
            i += 2
        elif cmd == "C":
            c1 = (float(toks[i]), float(toks[i + 1]))
            c2 = (float(toks[i + 2]), float(toks[i + 3]))
            p = (float(toks[i + 4]), float(toks[i + 5]))
            segs.append(("C", cur, c1, c2, p))
            cur = p
            i += 6
    return segs


def length(d):
    total = 0.0
    for s in _pts(d):
        if s[0] == "L":
            total += math.dist(s[1], s[2])
        else:
            p0, c1, c2, p3 = s[1:]
            prev = p0
            for k in range(1, 41):
                t = k / 40
                mt = 1 - t
                x = mt ** 3 * p0[0] + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t ** 3 * p3[0]
                y = mt ** 3 * p0[1] + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t ** 3 * p3[1]
                total += math.dist(prev, (x, y))
                prev = (x, y)
    return round(total, 2)


def stroke(d, sw=6.0, color=GOLD, **kw):
    s = {"d": d, "sw": sw, "color": color, "len": length(d)}
    s.update(kw)
    return s


# ------------------------------------------------------------------ icons
def plate():
    """Empty plate (front view, slight top angle) with fork and knife; steam drawn separately."""
    return [
        stroke(ellipse(0, 52, 168, 48, start=90), 6, part="rim"),
        stroke(ellipse(0, 55, 112, 28, start=90), 4.5, part="well"),
        stroke("M-246,-64 L-246,-22 C-246,-4 -214,-4 -214,-22 L-214,-64", 5, part="fork"),
        stroke("M-230,-64 L-230,118", 5, part="fork"),
        stroke("M246,118 L246,-66 C270,-50 276,-8 262,14 L246,14", 5, part="knife"),
    ]


def steam(y0=-14, y1=-176, xs=(-46, 0, 46), amp=12, wl=92):
    return [stroke(wave(x, y0 - (8 if i == 1 else 0), y1 - (22 if i == 1 else 0), amp, wl, phase=1.4 * i),
                   4.5, part="steam") for i, x in enumerate(xs)]


def bowl():
    return [
        stroke(ellipse(0, 0, 158, 36, start=180), 6, part="rim"),
        stroke("M-158,0 C-158,96 -84,146 0,146 C84,146 158,96 158,0", 6, part="body"),
        stroke(poly([(-50, 146), (-60, 170), (60, 170), (50, 146)]), 5, part="foot"),
        stroke(arc(0, 0, 118, 22, 200, 340), 3.5, part="inner"),
    ]


def heart(cx=0, cy=0, s=1.0, sw=6):
    d = "M0,-26 C-12,-58 -66,-60 -68,-16 C-70,22 -26,46 0,70 C26,46 70,22 68,-16 C66,-60 12,-58 0,-26 Z"
    return stroke(xform(d, s, s, 0, cx, cy), sw, part="heart")


def hands():
    """Two cupped hands (front view, palms up) holding a heart."""
    left = ("M-34,176 C-38,150 -40,132 -46,118 C-90,112 -150,86 -176,40 C-186,22 -188,4 -178,-6 "
            "C-168,-14 -154,-8 -150,6 C-136,42 -96,72 -6,92")
    right = xform(left, -1, 1)
    fingers_l = [
        stroke("M-186,24 C-176,30 -166,30 -158,24", 3.5, part="finger"),
        stroke("M-176,52 C-166,58 -154,58 -146,52", 3.5, part="finger"),
        stroke("M-160,78 C-150,84 -138,84 -130,78", 3.5, part="finger"),
    ]
    fingers_r = [stroke(xform(s["d"], -1, 1), 3.5, part="finger") for s in fingers_l]
    return [stroke(left, 6, part="hand"), stroke(right, 6, part="hand")] + fingers_l + fingers_r + \
        [heart(0, -16, 0.92, 6)]


def coin_parts(cx, cy, rx=86, ry=24, th=17):
    """Filled coin (side band + top face + inner ring), drawn bottom-up."""
    band = ("M" + P(cx - rx, cy) + " L" + P(cx - rx, cy + th) + " " +
            arc(cx, cy + th, rx, ry, 180, 0, move=False)[0:] + " L" + P(cx + rx, cy) + " " +
            arc(cx, cy, rx, ry, 0, 180, move=False) + " Z")
    return [
        {"d": band, "fill": GOLD_LO, "part": "band"},
        {"d": ellipse(cx, cy, rx, ry), "fill": "#E9B957", "part": "face"},
        {"d": ellipse(cx, cy, rx * 0.72, ry * 0.68), "stroke_only": True, "color": "#B9822F", "sw": 3, "part": "ring"},
    ]


def wheat():
    out = [stroke("M0,138 C4,70 4,10 0,-92", 5, part="stem")]
    grain = "M0,-25 C13,-13 13,13 0,25 C-13,13 -13,-13 0,-25 Z"
    for i, y in enumerate((-62, -26, 10, 46)):
        for side in (-1, 1):
            x = side * 19
            out.append(stroke(xform(grain, 1, 1, side * 34, x, y - (6 if side > 0 else 0)), 4.5, part="grain"))
    out.append(stroke(xform(grain, 1, 1, 0, 0, -108), 4.5, part="grain"))
    out.append(stroke("M2,100 C26,84 50,80 70,54", 4.5, part="leaf"))
    out.append(stroke("M0,-134 L0,-162", 3.5, part="awn"))
    return out


def star4(cx, cy, r, sw=5):
    k = r * 0.16
    d = ("M" + P(cx, cy - r) + " C" + P(cx + k * 0.5, cy - k) + " " + P(cx + k, cy - k * 0.5) + " " + P(cx + r, cy) +
         " C" + P(cx + k, cy + k * 0.5) + " " + P(cx + k * 0.5, cy + k) + " " + P(cx, cy + r) +
         " C" + P(cx - k * 0.5, cy + k) + " " + P(cx - k, cy + k * 0.5) + " " + P(cx - r, cy) +
         " C" + P(cx - k, cy - k * 0.5) + " " + P(cx - k * 0.5, cy - k) + " " + P(cx, cy - r) + " Z")
    return stroke(d, sw, part="star")


def sparkle():
    return [star4(0, 0, 92, 5.5), star4(86, -70, 30, 4), star4(-78, 64, 22, 4), star4(-70, -66, 14, 3.5)]


def sunrise():
    out = [stroke("M-150,48 L150,48", 5, part="horizon"),
           stroke(arc(0, 48, 66, 66, 180, 360), 5.5, part="sun")]
    for a in (192, 216, 242, 270, 298, 324, 348):
        r0, r1 = 90, 128 if a == 270 else 120
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        out.append(stroke("M" + P(ca * r0, 48 + sa * r0) + " L" + P(ca * r1, 48 + sa * r1), 4.5, part="ray"))
    out.append(stroke("M-96,74 L96,74", 3.5, part="horizon2"))
    return out


def chevron(y=0, w=34, h=16, sw=7):
    return stroke(poly([(-w, y - h), (0, y + h), (w, y - h)]), sw, part="chevron")


def divider(half=230, gap=26):
    return [
        stroke("M" + P(gap, 0) + " L" + P(half, 0), 3, part="line"),
        stroke("M" + P(-gap, 0) + " L" + P(-half, 0), 3, part="line"),
        stroke(poly([(0, -11), (11, 0), (0, 11), (-11, 0)], True), 3, part="diamond"),
        stroke(poly([(half + 14, -5), (half + 19, 0), (half + 14, 5), (half + 9, 0)], True), 2.5, part="end"),
        stroke(poly([(-half - 14, -5), (-half - 9, 0), (-half - 14, 5), (-half - 19, 0)], True), 2.5, part="end"),
    ]


def scroll_curl(x0, y0, direction, r0=26.0, turns=1.15, sign=1):
    """Spiral curl that starts tangent to `direction` (deg) at (x0, y0) and winds inwards."""
    pts = []
    n = 40
    total = turns * 2 * math.pi
    # centre sits to the side of the start point
    ang = math.radians(direction + sign * 90)
    cx, cy = x0 + r0 * math.cos(ang), y0 + r0 * math.sin(ang)
    a_start = math.atan2(y0 - cy, x0 - cx)
    for i in range(n + 1):
        th = total * i / n
        r = r0 * math.exp(-0.32 * th)
        a = a_start + sign * th
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def corner(arm=210):
    """Top-left corner flourish (mirror with layer scale for the other corners).

    An L bracket whose arms end in inward scrolls, a thin inner bracket and a small diamond.
    """
    curl_h = scroll_curl(arm, 0, 0, 20, 1.1, 1)
    curl_v = scroll_curl(0, arm, 90, 20, 1.1, -1)
    bracket = [p for p in reversed(curl_v)] + [(0, arm * 0.5), (0, 0), (arm * 0.5, 0)] + curl_h
    inner = arm * 0.62
    return [
        stroke(smooth_poly_mixed(bracket), 3, part="bracket"),
        stroke(poly([(16, inner), (16, 16), (inner, 16)]), 1.8, part="inner"),
        stroke(poly([(-16, -16), (-6, -26), (4, -16), (-6, -6)], True), 2.2, part="gem"),
    ]


def smooth_poly_mixed(pts):
    """Spline for curl points, straight lines where consecutive points are far apart."""
    out = ["M" + P(*pts[0])]
    i = 0
    n = len(pts)
    while i < n - 1:
        a, b = pts[i], pts[i + 1]
        if math.dist(a, b) > 40:
            out.append("L" + P(*b))
            i += 1
            continue
        # gather a run of close points and spline it
        j = i + 1
        while j < n - 1 and math.dist(pts[j], pts[j + 1]) <= 40:
            j += 1
        run = pts[i:j + 1]
        s = smooth(run).split(" ", 1)
        if len(s) > 1:
            out.append(s[1])
        i = j
    return " ".join(out)


def tap_ring(r):
    return stroke(ellipse(0, 0, r, r, start=-90), 3.5, part="ring")


ICONS = {
    "plate": plate, "steam": steam, "bowl": bowl, "hands": hands, "wheat": wheat, "sparkle": sparkle,
    "sunrise": sunrise, "divider": divider, "corner": corner,
}
