# Contact sheet of rendered frames with frame/time labels.  usage: sheet.py <frames_dir> <out.png> <cols> [w]
import os
import sys

from PIL import Image, ImageDraw, ImageFont

FPS = 30000 / 1001
src, out, cols = sys.argv[1], sys.argv[2], int(sys.argv[3])
tw = int(sys.argv[4]) if len(sys.argv) > 4 else 270
th = tw * 16 // 9
files = sorted(f for f in os.listdir(src) if f.endswith(".png"))
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * (tw + 6), rows * (th + 26)), "#222")
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 16)
except OSError:
    font = ImageFont.load_default()
d = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    im = Image.open(os.path.join(src, f)).convert("RGB").resize((tw, th), Image.LANCZOS)
    x, y = (i % cols) * (tw + 6), (i // cols) * (th + 26)
    sheet.paste(im, (x, y + 24))
    fr = int(f[1:5])
    d.text((x + 4, y + 3), "f%d  %.2fs" % (fr, fr / FPS), fill="yellow", font=font)
sheet.save(out)
