#!/usr/bin/env python3
"""Prepare the working assets used by scene.py / render.js / sfx.py.

usage: prep_assets.py <work_video.mp4> <reference_video.mp4> <work_dir>

Creates in <work_dir>:
  frames/f001.jpg ...       work-video frames (25 fps)
  audio/vo.wav              voice-over (48 kHz, 24 bit)
  vo_env.json               100 Hz voice envelope (drives the sound bars)
  site/site_bg.png          site page (reference 7.0 s) for the blurred background
  site/scroll/sNN.jpg       site scroll recording (reference 23.12-24.52 s)
  site/card_*.png           set cards cropped from the reference (37.2 s)
  logo/brand_47.1.png       reference brand card frame
  logo/trace_raw.json/svg   traced vector paths, logo/logo.json grouped per letter
words.json (word onsets) is produced separately by snap_words.py.
"""
import json
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw

work_video, ref_video, W = sys.argv[1], sys.argv[2], sys.argv[3]
HERE = os.path.dirname(os.path.abspath(__file__))


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


for d in ("frames", "audio", "site/scroll", "logo"):
    os.makedirs(os.path.join(W, d), exist_ok=True)

ff("-i", work_video, "-q:v", "1", "-qmin", "1", os.path.join(W, "frames/f%03d.jpg"))
ff("-i", work_video, "-vn", "-c:a", "pcm_s24le", "-ar", "48000", os.path.join(W, "audio/vo.wav"))
ff("-ss", "7.0", "-i", ref_video, "-frames:v", "1", os.path.join(W, "site/site_bg.png"))
ff("-ss", "23.12", "-t", "1.40", "-i", ref_video, "-vf", "scale=720:1280:flags=lanczos", "-q:v", "2",
   os.path.join(W, "site/scroll/s%02d.jpg"))
ff("-ss", "37.2", "-i", ref_video, "-frames:v", "1", os.path.join(W, "site/cards_372.png"))
ff("-ss", "47.1", "-i", ref_video, "-frames:v", "1", os.path.join(W, "logo/brand_47.1.png"))

# set cards (bounds measured on the 37.2 s reference frame)
src = Image.open(os.path.join(W, "site/cards_372.png")).convert("RGB")
for k, (x0, y0, x1, y1) in {"pro_master": (74, 780, 507, 1306), "dance_dj": (575, 779, 1006, 1301),
                            "live_style": (327, 1362, 730, 1848)}.items():
    c = src.crop((x0, y0, x1 + 1, y1 + 1)).convert("RGBA")
    m = Image.new("L", c.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, c.width - 1, c.height - 1), radius=20, fill=255)
    c.putalpha(m)
    c.save(os.path.join(W, "site/card_%s.png" % k))

# logo trace + grouping
subprocess.run([sys.executable, "-I", os.path.join(HERE, "trace_logo.py"), os.path.join(W, "logo/brand_47.1.png"),
                os.path.join(W, "logo/trace_raw.json"), os.path.join(W, "logo/trace_raw.svg")], check=True)
c = json.load(open(os.path.join(W, "logo/trace_raw.json")))


def inb(b, x0, y0, x1, y1):
    return b[0] >= x0 and b[1] >= y0 and b[2] <= x1 and b[3] <= y1


groups = {"M": [], "O": [], "T1": [], "T2": [], "i": [], "dot": [], "ros": []}
for k, cv in enumerate(c):
    b = cv["bbox"]
    if b[0] <= 181 and b[2] >= 899:
        continue                                   # crop frame
    if b[1] > 1110 or (b[3] < 778 and b[0] > 540):
        continue                                   # Hebrew words of the card (set as live text)
    if b[1] > 1040 and b[3] < 1095:
        groups["ros"].append(k)
    elif inb(b, 225, 785, 400, 1130):
        groups["M"].append(k)
    elif inb(b, 405, 850, 580, 1025):
        groups["O"].append(k)
    elif inb(b, 540, 800, 690, 1005):
        groups["T1"].append(k)
    elif inb(b, 650, 900, 795, 1105):
        groups["T2"].append(k)
    elif inb(b, 805, 875, 855, 1030):
        groups["i"].append(k)
    elif inb(b, 725, 775, 780, 826):
        groups["dot"].append(k)
letters = []
for k in sorted(groups["ros"], key=lambda k: c[k]["bbox"][0]):
    b = c[k]["bbox"]
    for L in letters:
        if b[0] >= L["bbox"][0] - 1 and b[2] <= L["bbox"][2] + 1:
            L["paths"].append(c[k]["d"])
            break
    else:
        letters.append({"bbox": b, "paths": [c[k]["d"]]})
out = {"groups": {}, "ros": [{"bbox": L["bbox"], "d": " ".join(L["paths"])} for L in letters]}
for g in ["M", "O", "T1", "T2", "i", "dot"]:
    bs = [c[k]["bbox"] for k in groups[g]]
    out["groups"][g] = {"bbox": [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs),
                                 max(b[3] for b in bs)], "d": " ".join(c[k]["d"] for k in groups[g])}
allb = [v["bbox"] for v in out["groups"].values()] + [L["bbox"] for L in out["ros"]]
out["bbox"] = [min(b[0] for b in allb), min(b[1] for b in allb), max(b[2] for b in allb), max(b[3] for b in allb)]
json.dump(out, open(os.path.join(W, "logo/logo.json"), "w"))

# voice envelope, 100 Hz, 0..1 over a 36 dB range
w = wave.open(os.path.join(W, "audio/vo.wav"))
sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
b = np.frombuffer(w.readframes(n), np.uint8).reshape(-1, 3)
a = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
a = (np.where(a >= 1 << 23, a - (1 << 24), a).astype(np.float32) / (1 << 23)).reshape(-1, ch).mean(1)
hop = sr // 100
env = np.array([np.sqrt(np.mean(a[i:i + hop * 3] ** 2) + 1e-12) for i in range(0, len(a), hop)])
v = np.clip((20 * np.log10(env / env.max()) + 36) / 36, 0, 1)
json.dump([round(float(x), 3) for x in v], open(os.path.join(W, "vo_env.json"), "w"))
print("assets ready in", W)
