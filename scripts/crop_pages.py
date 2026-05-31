#!/usr/bin/env python3
"""Crop each scan to its written area (ink bounding box), discarding the blank
facing page and the background. These are open-book photos where text occupies
only part of the frame; cropping to the ink lifts every downstream engine.

Outputs processed/cropped/<page_id>.jpg (full res). With --preview also writes
small <page_id>_preview.jpg thumbnails for visual QA.

Usage:
  python scripts/crop_pages.py                 # all pages
  python scripts/crop_pages.py p001 p100 --preview   # subset + previews
"""
import os, csv, sys
import numpy as np
from scipy.ndimage import uniform_filter, uniform_filter1d
from PIL import Image, ImageFile, ImageOps
ImageFile.LOAD_TRUNCATED_IMAGES = True

def load_oriented(path):
    """Open an image and apply its EXIF orientation. ~135 of the phone photos
    carry a 90deg rotation flag PIL ignores by default; honoring it is the
    single biggest correctness fix in preprocessing."""
    return ImageOps.exif_transpose(Image.open(path))

MANIFEST = "dataset/manifest.csv"
OUTDIR = "processed/cropped"
PAPER_MIN = 130      # local mean luminance above this = bright paper (not dark bg)
INK_DELTA = 25       # pixel this much darker than local paper = ink stroke
CORE_FRAC = 0.12     # locate the dense text core at this * robust density
GROW_FRAC = 0.02     # then grow out to full text extent down to this * robust density
PAD = 0.05           # padding as fraction of cropped dimension (generous: avoid clipping)
MIN_KEEP = 0.15      # crops smaller than this are treated as failures -> keep full frame
ANALYZE_MAX = 1500   # downscale long edge for analysis speed only

def densest_span(profile, ref, frac):
    """Start/end of the contiguous above-threshold run holding the most ink.
    Picks the text block over thin noise bands (deckle edges, ruling).
    `ref` is a robust density level (high percentile, not max) so a lone
    water-stain or ink-blot spike can't inflate the threshold above text."""
    thr = frac * ref
    above = profile > thr
    best, best_sum, i, n = (0, len(profile) - 1), -1.0, 0, len(profile)
    while i < n:
        if above[i]:
            j = i
            while j + 1 < n and above[j + 1]:
                j += 1
            s = profile[i:j + 1].sum()
            if s > best_sum:
                best_sum, best = s, (i, j)
            i = j + 1
        else:
            i += 1
    return best

def text_span(profile):
    """Locate the dense text core, then grow to its full contiguous extent at a
    lower threshold. The blank-page gap stops growth before the deckle edge."""
    ref = np.percentile(profile, 92)          # robust to stain/blot spikes
    if ref <= 0:                              # very sparse page: fall back to max
        ref = profile.max()
    a, b = densest_span(profile, ref, CORE_FRAC)
    thr = GROW_FRAC * ref
    while a > 0 and profile[a - 1] > thr:
        a -= 1
    while b < len(profile) - 1 and profile[b + 1] > thr:
        b += 1
    return a, b

def crop_box(path):
    # These are open-book photos: bright paper pages on a DARK background.
    # Ink = pixels notably darker than their local surroundings, where those
    # surroundings are bright paper. This excludes the dark background (dark
    # neighborhood) and the blank facing page (no dark strokes on it).
    with load_oriented(path) as im:
        W, H = im.size
        rgb = im.convert("RGB")
        scale = min(1.0, ANALYZE_MAX / max(W, H))
        if scale < 1.0:
            rgb = rgb.resize((max(1, int(W * scale)), max(1, int(H * scale))))
        a = np.asarray(rgb).astype(np.float32)
    lum = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    k = max(15, int(max(lum.shape) / 15))            # local window ~1/15 of image
    local = uniform_filter(lum, size=k)
    mask = (local > PAPER_MIN) & (lum < local - INK_DELTA)
    if mask.sum() < 50:                       # almost no ink -> keep whole frame
        return (0, 0, W, H), 1.0
    # density profiles: text block is dense; a blank facing page is sparse
    col = uniform_filter1d(mask.sum(0).astype(float), 9)
    row = uniform_filter1d(mask.sum(1).astype(float), 9)
    x0, x1 = text_span(col)
    y0, y1 = text_span(row)
    inv = 1.0 / scale
    x0, x1, y0, y1 = x0 * inv, x1 * inv, y0 * inv, y1 * inv
    bw, bh = x1 - x0, y1 - y0
    x0 = max(0, x0 - bw * PAD); x1 = min(W, x1 + bw * PAD)
    y0 = max(0, y0 - bh * PAD); y1 = min(H, y1 + bh * PAD)
    box = (int(x0), int(y0), int(x1), int(y1))
    ratio = ((box[2] - box[0]) * (box[3] - box[1])) / (W * H)
    if ratio < MIN_KEEP:                      # suspicious tight crop -> safer to keep all
        return (0, 0, W, H), 1.0
    return box, ratio

def main(subset, preview):
    os.makedirs(OUTDIR, exist_ok=True)
    rows = list(csv.DictReader(open(MANIFEST)))
    if subset:
        rows = [r for r in rows if r["page_id"] in subset]
    ratios = []
    for r in rows:
        box, ratio = crop_box(r["orig_path"])
        with load_oriented(r["orig_path"]) as im:
            crop = im.crop(box)
            crop.save(os.path.join(OUTDIR, r["page_id"] + ".jpg"), quality=92)
            if preview:
                t = crop.copy(); t.thumbnail((800, 800))
                t.save(os.path.join(OUTDIR, r["page_id"] + "_preview.jpg"))
        ratios.append(ratio)
        print(f"{r['page_id']}  kept {ratio*100:5.1f}%  {r['register']}")
    print(f"\ncropped {len(rows)} images; mean kept area "
          f"{100*sum(ratios)/len(ratios):.1f}%")

if __name__ == "__main__":
    args = sys.argv[1:]
    preview = "--preview" in args
    ids = [a for a in args if not a.startswith("-")]
    main(set(ids) or None, preview)
