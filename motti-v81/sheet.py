# Contact sheet of rendered frames with frame/time labels.
import sys, os
from PIL import Image, ImageDraw, ImageFont
src, out, cols = sys.argv[1], sys.argv[2], int(sys.argv[3])
files = sorted(f for f in os.listdir(src) if f.endswith(".png"))
if len(sys.argv) > 4:
    keep = set(sys.argv[4].split(","))
    files = [f for f in files if str(int(f[1:5])) in keep]
tw = 270; th = 480
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * (tw + 6), rows * (th + 26)), "#222")
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 16)
d = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    im = Image.open(os.path.join(src, f)).convert("RGB").resize((tw, th), Image.LANCZOS)
    x, y = (i % cols) * (tw + 6), (i // cols) * (th + 26)
    sheet.paste(im, (x, y + 24))
    fr = int(f[1:5]); d.text((x + 4, y + 3), "f%d  %.2fs" % (fr, fr / 25), fill="yellow", font=font)
sheet.save(out)
