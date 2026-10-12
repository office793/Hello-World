#!/usr/bin/env python3
"""Prepare the work folder for the Maran "18 NIS" typography video.

usage: prep_assets.py <vo.mp3> <logo.(webp|png)> <fonts_dir> <work_dir>

  work/audio/vo.wav      48 kHz stereo PCM of the client voice-over
  work/audio/vo_env.json 10 ms RMS envelope (0..1) of the VO, used for SFX ducking
  work/logo.png          logo, alpha made fully opaque inside the shape, trimmed to its bounds
  work/bg.png            1080x1920 burgundy backdrop (radial light, soft cloud texture, grain)
  work/fonts/            the fonts the preview and the AE project use
"""
import json
import os
import shutil
import subprocess
import sys
import wave

import numpy as np
from PIL import Image
from scipy import ndimage as nd

vo_src, logo_src, fonts_dir, work = sys.argv[1:5]
os.makedirs(os.path.join(work, "audio"), exist_ok=True)
os.makedirs(os.path.join(work, "fonts"), exist_ok=True)
W, H = 1080, 1920

# ---- voice-over
vo = os.path.join(work, "audio", "vo.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vo_src, "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", vo], check=True)
w = wave.open(vo)
a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32).reshape(-1, 2).mean(1) / 32768
hop = 480
env = [float(np.sqrt(np.mean(a[i:i + hop] ** 2))) for i in range(0, len(a), hop)]
mx = max(env)
json.dump([round(e / mx, 4) for e in env], open(os.path.join(work, "audio", "vo_env.json"), "w"))
print("vo: %.2f s" % (len(a) / 48000))

# ---- logo: the supplied file is ~99 % opaque inside (alpha 249-254); make the inside solid
im = Image.open(logo_src).convert("RGBA")
arr = np.asarray(im).copy()
al = arr[..., 3].astype(np.float32)
inside = nd.binary_erosion(al > 200, iterations=2)
al[inside] = 255
arr[..., 3] = al.astype(np.uint8)
ys, xs = np.nonzero(arr[..., 3] > 8)
arr = arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
Image.fromarray(arr).save(os.path.join(work, "logo.png"))
print("logo:", arr.shape[1], "x", arr.shape[0])

# ---- backdrop: deep burgundy, warm light slightly above centre, darker corners
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
r = np.sqrt(((xx - 540) / 1.0) ** 2 + ((yy - 860) / 1.18) ** 2) / 1000.0
stops = [(0.00, (0x76, 0x16, 0x37)), (0.35, (0x5C, 0x10, 0x2B)), (0.75, (0x3D, 0x0B, 0x1E)), (1.25, (0x22, 0x05, 0x10))]
img = np.zeros((H, W, 3), np.float32)
for c in range(3):
    img[..., c] = np.interp(r, [s[0] for s in stops], [s[1][c] for s in stops])
rng = np.random.default_rng(18)
cloud = nd.gaussian_filter(rng.standard_normal((H // 4, W // 4)), 18)
cloud = np.kron(cloud / np.abs(cloud).max(), np.ones((4, 4)))[:H, :W]
cloud = nd.gaussian_filter(cloud, 6)
img *= (1 + 0.07 * cloud)[..., None]
img += rng.normal(0, 1.1, (H, W, 1))          # grain (also dithers the gradient)
Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(os.path.join(work, "bg.png"))

# ---- fonts
for f in sorted(os.listdir(fonts_dir)):
    if f.lower().endswith((".ttf", ".otf")) and "[" not in f:
        shutil.copy(os.path.join(fonts_dir, f), os.path.join(work, "fonts", f))
print("fonts:", ", ".join(sorted(os.listdir(os.path.join(work, "fonts")))))
