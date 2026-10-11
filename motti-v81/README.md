# MOTTI Rosenfeld — "Update V8.1" (After Effects)

Kinetic-typography edit of the 9.88 s update video plus a 5 s digital-clock end card
("עדכון: V8.1"). Output: 1080x1920, 25 fps, 14.88 s.

One scene description drives three outputs, so the preview, the After Effects project
and the sound design stay frame-locked:

| file | role |
|---|---|
| `scene.py` | Single source of truth: every layer, keyframe track and sound cue (`scene.json`, `cues.json`). |
| `render.html` / `render.js` | Canvas interpreter of `scene.json` (AE semantics: parenting, text animators, 180° motion blur). |
| `render_driver.js` / `render_list.js` | Headless Chromium (Playwright) frame renderers. |
| `sfx.py` | Synthesizes every cue from scratch, ducks under the VO, masters to -14 LUFS / -1 dBTP. |
| `make_jsx.py` + `ae_template.jsx` | Writes the ExtendScript that rebuilds the whole project in AE with the user's fonts. |
| `ae_mock.js` | Dry-runs the generated `.jsx` against a mock AE DOM (match names, value dimensions, timing, expressions). |
| `tools/` | Asset prep: frames/VO extraction, site crops, live site captures (`capture_site.js`), logo vector trace, word-onset snapping, windowed ASR. |

## Rebuild

```sh
python3 tools/prep_assets.py <update.mp4> <launch_reference.mp4> work/
python3 tools/snap_words.py work/audio/vo.wav work/words.json
NODE_PATH=$(npm root -g) node tools/capture_site.js work   # live mottirozenfeld.com: home scroll + organ panel
python3 scene.py work out
python3 -m http.server 8765 --directory .. &      # serves build/ and work/
NODE_PATH=$(npm root -g) node render_driver.js http://127.0.0.1:8765 frames 0 371
python3 sfx.py out/cues.json work/audio/vo.wav out/audio
python3 make_jsx.py out/scene.json ae_template.jsx MOTTI_Update_V8.1_build.jsx
ASSET_ROOT=<assets dir> node ae_mock.js MOTTI_Update_V8.1_build.jsx [--rtl]
```

`render_driver.js` expects the page at `<base>/build/render.html` and assets at `../work`
(relative to it); adjust the paths in the driver if your layout differs.

Client footage, audio and the rendered preview are not committed; they are delivered
directly with the AE package.
