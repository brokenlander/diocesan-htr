#!/usr/bin/env python3
"""Diagnostic: run Kraken blla segmentation on a page and draw the detected
lines (boundary + baseline + index) and regions onto the image, so we can SEE
whether segmentation is the bottleneck for our register layouts.

Usage: python scripts/seg_inspect.py processed/cropped/p001.jpg
"""
import sys, os
from PIL import Image, ImageDraw, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True
from kraken import blla
from kraken.lib import vgsl

SEG_MODEL = os.path.join(os.path.dirname(blla.__file__), "blla.mlmodel")
path = sys.argv[1]
pid = os.path.splitext(os.path.basename(path))[0]

seg_model = vgsl.TorchVGSLModel.load_model(SEG_MODEL)
im = Image.open(path).convert("RGB")
seg = blla.segment(im, model=seg_model, device="cpu")

lines = list(seg.lines)
regions = seg.regions or {}
print(f"{pid}: {len(lines)} lines")
print("regions:", {k: len(v) for k, v in regions.items()})

draw = im.copy()
d = ImageDraw.Draw(draw)

# regions in green
for rtype, polys in regions.items():
    for r in polys:
        pts = getattr(r, "boundary", r)
        try:
            d.line([tuple(p) for p in pts] + [tuple(pts[0])], fill=(0, 200, 0), width=5)
        except Exception:
            pass

# lines: boundary red, baseline blue, index label
for i, ln in enumerate(lines, 1):
    poly = getattr(ln, "boundary", None)
    if poly:
        try:
            d.line([tuple(p) for p in poly] + [tuple(poly[0])], fill=(230, 0, 0), width=3)
        except Exception:
            pass
    bl = getattr(ln, "baseline", None)
    if bl:
        try:
            d.line([tuple(p) for p in bl], fill=(0, 120, 255), width=4)
            x, y = bl[0]
            d.text((max(0, x - 28), y - 10), str(i), fill=(230, 0, 0))
        except Exception:
            pass

os.makedirs("processed/segmented", exist_ok=True)
full = f"processed/segmented/{pid}_overlay.jpg"
draw.save(full, quality=85)
prev = draw.copy(); prev.thumbnail((1100, 1100))
prevpath = f"processed/segmented/{pid}_overlay_preview.jpg"
prev.save(prevpath, quality=85)
print("saved", prevpath)
