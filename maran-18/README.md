# Yeshivat Maran — "18 NIS" typography ending (After Effects)

Kinetic-typography ending for the hungry-child street video: the client's 13.3 s voice-over
("יש עוד ילד שמחכה לארוחה שלו היום... תזכו לשפע, לברכה ולישועות גדולות") set in big gold Hebrew on the
Yeshivat Maran burgundy, with line-drawn gold icons and the logo plus a living link button.
Output: 1080x1920, 29.97 fps, 15.5 s. It follows the 33.4 s video (VO sits at 00:00:33:27 in the edit).

Brand language taken from harav-ovadya.co.il: burgundy `#350A1B`, gold `#E9AF2C` → `#A87029`,
STaM lettering with tagin for "מרן" (as in the site's "זה הזמן להתחבר למרן" title), Open Sans for Latin.

| file | role |
|---|---|
| `words.json` | Word onsets of the VO (energy dips + progressive-window Whisper). |
| `art.py` | Gold line icons (plate, bowl, hands + heart, coins, wheat, sparkle, sunrise, tap ring, chevrons, flourishes) as single-sub-path strokes with lengths for Trim Paths. |
| `scene.py` | Single source of truth: every layer, keyframe track and sound cue (`scene.json`, `cues.json`). |
| `render.html` / `render.js` | Canvas interpreter of `scene.json` (AE semantics: parenting, text animators incl. blur and per-word start times, Trim Paths, ramp-gradient text, alpha track mattes, 180° motion blur). |
| `render_driver.js` | Headless Chromium (Playwright) frame renderer. |
| `sfx.py` | Synthesizes every cue (soft swooshes, UI clicks, screen tap, coin clinks, rising ticks, two bells), ducks under the VO, masters to -14 LUFS / -1 dBTP. |
| `make_jsx.py` + `ae_template.jsx` | Writes the ExtendScript that rebuilds the whole project in AE. |
| `ae_mock.js` | Dry-runs the generated `.jsx` against a mock AE DOM (match names, value dimensions, mattes, expressions). |
| `tools/prep_assets.py` | VO to 48 kHz WAV + envelope, opaque/trimmed logo, burgundy backdrop, font copy. |

Fonts (free): Frank Ruhl Libre Black (big words), Assistant SemiBold (small words), Stam Sefarad CLM
(Culmus, "מרן"), Open Sans SemiBold (link). Static instances of the Google variable fonts are made
with `fontTools.varLib.instancer`.

## Rebuild

```sh
python3 tools/prep_assets.py <vo.mp3> <logo.webp> <fonts_dir> work/
python3 scene.py work out
python3 sfx.py out/cues.json work/audio/vo.wav out/audio --oneshots
# serve a folder holding app/ (this directory), work/ and out/
python3 -m http.server 8765 --directory <root> &
NODE_PATH=$(npm root -g) node render_driver.js http://127.0.0.1:8765 frames 0 464
ffmpeg -framerate 30000/1001 -i frames/f%04d.png -i out/audio/MIX_vo_sfx.wav -c:v libx264 -crf 16 -pix_fmt yuv420p -c:a aac preview.mp4
python3 make_jsx.py out/scene.json ae_template.jsx Maran_18_build.jsx
ASSET_ROOT=<package>/assets node ae_mock.js Maran_18_build.jsx [--rtl]
```

Python needs numpy, scipy, pillow, pyloudnorm, uharfbuzz, fonttools (and sherpa-onnx only to re-time words).
Client audio, logo, footage and the rendered preview are not committed; they ship with the AE package.
