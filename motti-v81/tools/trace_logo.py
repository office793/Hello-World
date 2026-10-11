# Trace the MOTTI Rosenfeld logo from the reference brand frame into vector paths.
import sys, json, numpy as np, potrace
from PIL import Image, ImageFilter
src, out_json, out_svg = sys.argv[1], sys.argv[2], sys.argv[3]
X0, Y0, X1, Y1 = 180, 660, 900, 1240          # crop in frame coords
UP = 4
im = Image.open(src).convert("RGB").crop((X0, Y0, X1, Y1))
im = im.resize((im.width * UP, im.height * UP), Image.LANCZOS).filter(ImageFilter.GaussianBlur(2.6))
a = np.asarray(im).astype(np.float32)
# "blueness": distance from white along the brand blue direction
blue = (a[:, :, 2] - a[:, :, 0]) / (0x90 - 0x18)
mask = blue > 0.5
bm = potrace.Bitmap(mask)
path = bm.trace(turdsize=40, turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY, alphamax=1.0, opticurve=True, opttolerance=0.2)

def P(p):  # back to frame pixel coords (1080x1920 frame)
    return [round(X0 + p.x / UP, 3), round(Y0 + p.y / UP, 3)]

curves = []
for c in path:
    segs = []
    for s in c.segments:
        if s.is_corner:
            segs.append({"t": "C", "c": P(s.c), "e": P(s.end_point)})
        else:
            segs.append({"t": "B", "c1": P(s.c1), "c2": P(s.c2), "e": P(s.end_point)})
    pts = [P(c.start_point)] + [s["e"] for s in segs]
    xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
    curves.append({"start": P(c.start_point), "segs": segs, "bbox": [min(xs), min(ys), max(xs), max(ys)]})

def d_of(c):
    d = "M%.2f %.2f" % tuple(c["start"])
    for s in c["segs"]:
        if s["t"] == "C":
            d += " L%.2f %.2f L%.2f %.2f" % (s["c"][0], s["c"][1], s["e"][0], s["e"][1])
        else:
            d += " C%.2f %.2f %.2f %.2f %.2f %.2f" % (s["c1"][0], s["c1"][1], s["c2"][0], s["c2"][1], s["e"][0], s["e"][1])
    return d + " Z"

for i, c in enumerate(curves):
    c["d"] = d_of(c)
    print(i, [round(v) for v in c["bbox"]], len(c["segs"]))
json.dump(curves, open(out_json, "w"))
svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%d %d %d %d"><path fill="#185090" fill-rule="evenodd" d="%s"/></svg>' % (
    X0, Y0, X1 - X0, Y1 - Y0, " ".join(c["d"] for c in curves))
open(out_svg, "w").write(svg)
