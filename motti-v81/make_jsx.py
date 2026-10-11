#!/usr/bin/env python3
"""Write the After Effects builder (.jsx) from scene.json.  usage: make_jsx.py <scene.json> <template> <out.jsx>"""
import json
import sys

scene = json.load(open(sys.argv[1], encoding="utf-8"))
tpl = open(sys.argv[2], encoding="utf-8").read()
images, seq = [], None
for comp in scene["comps"].values():
    for L in comp["layers"]:
        if L["type"] == "image" and L["src"] not in images:
            images.append(L["src"])
        if L["type"] == "seq":
            seq = L["srcs"][0]
meta = {
    "footage": "footage/work.mp4",
    "images": images,
    "seq": seq,
    "audio": ["MIX_vo_sfx.wav", "VO.wav", "SFX_transitions.wav", "SFX_ui.wav", "SFX_hits.wav", "SFX_tonal.wav",
              "SFX_digital.wav"],
    "mainAudio": "MIX_vo_sfx.wav",
    "blurScale": 2.2,
    "maxTextWidth": 1000,
}
scene_js = json.dumps(scene, ensure_ascii=True, separators=(",", ":"))
out = tpl.replace("__SCENE__", scene_js).replace("__META__", json.dumps(meta, ensure_ascii=True))
open(sys.argv[3], "w", encoding="utf-8").write("﻿" + out)
print("jsx written: %d KB, %d layers" % (len(out) // 1024, sum(len(c["layers"]) for c in scene["comps"].values())))
