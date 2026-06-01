#!/usr/bin/env python3
"""Crop each photo to its written PAGE(S), discarding blank facing pages and
background. These are open-book photos: a photo may contain ONE written page
(facing page blank) or TWO (a full spread). We detect the gutter and emit one
cropped image per written page:
  single page  -> processed/cropped/<photo_id>.jpg
  spread       -> processed/cropped/<photo_id>a.jpg (left) + <photo_id>b.jpg (right)
Also writes dataset/pages.csv (page_id, photo_id, side, register, cropped, src).

Ink = pixels notably darker than their local BRIGHT surroundings (paper); this
excludes the dark background and the blank facing page.

Usage: python scripts/crop_pages.py [p001 p002 ...] [--preview]
"""
import os, csv, sys
import numpy as np
from scipy.ndimage import uniform_filter, uniform_filter1d
from PIL import Image, ImageFile, ImageOps
ImageFile.LOAD_TRUNCATED_IMAGES = True

MANIFEST = "dataset/manifest.csv"
OUTDIR = "processed/cropped"
PAGES_CSV = "dataset/pages.csv"
PAPER_MIN = 130       # local mean luminance above this = bright paper (not dark bg)
INK_DELTA = 25        # pixel this much darker than local paper = ink stroke
CORE_FRAC = 0.12      # locate dense text core at this * robust density
GROW_FRAC = 0.02      # grow to full text extent down to this * robust density
PAD = 0.05            # padding as fraction of cropped dimension
MIN_KEEP = 0.10       # crop smaller than this (of full frame) -> treat as failure
ANALYZE_MAX = 1500
GUTTER_LO, GUTTER_HI = 0.30, 0.70   # search the gutter in this central band of the text
GUTTER_VALLEY = 0.22  # central valley below this * min(flanking peaks) => a real gutter
MIN_PAGE_W = 0.10     # each page column band must be at least this wide (of image)

def load_oriented(path):
    """Open + apply EXIF orientation (~135 phone photos are flagged sideways)."""
    return ImageOps.exif_transpose(Image.open(path))

def _ink_profiles(path):
    with load_oriented(path) as im:
        W, H = im.size
        rgb = im.convert("RGB")
        scale = min(1.0, ANALYZE_MAX / max(W, H))
        if scale < 1.0:
            rgb = rgb.resize((max(1, int(W*scale)), max(1, int(H*scale))))
        a = np.asarray(rgb).astype(np.float32)
    lum = 0.299*a[...,0] + 0.587*a[...,1] + 0.114*a[...,2]
    k = max(15, int(max(lum.shape)/15))
    local = uniform_filter(lum, size=k)
    mask = (local > PAPER_MIN) & (lum < local - INK_DELTA)
    return mask, lum, scale, W, H

def _extent(profile, frac=0.06):
    """First/last index where profile exceeds frac * its 92nd percentile.
    Full text extent (includes all blocks) — used for a page's vertical range."""
    ref = np.percentile(profile, 92) or profile.max()
    if ref <= 0:
        return 0, len(profile)-1
    idx = np.where(profile > frac*ref)[0]
    return (int(idx[0]), int(idx[-1])) if len(idx) else (0, len(profile)-1)

def _page_bands(col):
    """Return column (start,end) band(s) for the written page(s): 2 for a spread,
    1 for a single page. Finds substantial column runs directly (no grow-from-core,
    which would stop at the gutter and hide the second page)."""
    n = len(col)
    ref = np.percentile(col, 92) or col.max()
    if ref <= 0:
        return [(0, n-1)]
    above = col > max(0.08*ref, 1.0)
    runs, i = [], 0
    while i < n:
        if above[i]:
            j = i
            while j+1 < n and above[j+1]:
                j += 1
            runs.append((i, j, col[i:j+1].sum())); i = j+1
        else:
            i += 1
    if not runs:
        return [(0, n-1)]
    maxink = max(r[2] for r in runs)
    pages = [r for r in runs if (r[1]-r[0]) > 0.07*n and r[2] > 0.20*maxink]
    if len(pages) == 2:                                   # clean spread -> split
        return [(pages[0][0], pages[0][1]), (pages[1][0], pages[1][1])]
    if len(pages) == 1:
        return [(pages[0][0], pages[0][1])]
    # 0 or >2 (ambiguous): one page spanning all substantial ink -> no data loss
    src = pages or runs
    return [(src[0][0], src[-1][1])]

def _real_spread(bands, n):
    """Two bands are two PHYSICAL pages (not a page + a marginal number column)
    when they are roughly equal in width and the gap between them sits near the
    centre of the photo. Calibrated on Turate spreads (flat books → bright gutter,
    so luminance is useless; geometry is the reliable signal)."""
    if len(bands) != 2:
        return False
    (a0, a1), (b0, b1) = bands
    if b0 <= a1 + 1:
        return False
    w1, w2 = a1-a0, b1-b0
    balanced = min(w1, w2) / max(w1, w2) > 0.45
    both_big = min(w1, w2) > 0.18*n
    gap_mid = ((a1 + b0) / 2) / n
    central = 0.30 < gap_mid < 0.70
    return balanced and both_big and central

def detect_page_boxes(path):
    """Return list of (box, kept_ratio) for the 1 or 2 written pages in the photo."""
    mask, lum, scale, W, H = _ink_profiles(path)
    if mask.sum() < 50:
        return [((0, 0, W, H), 1.0)]
    col = uniform_filter1d(mask.sum(0).astype(float), 9)
    bands = _page_bands(col)
    if len(bands) == 2 and not _real_spread(bands, len(col)):
        bands = [(bands[0][0], bands[1][1])]               # one page (e.g. name|age cols)
    inv = 1.0/scale
    boxes = []
    for cx0, cx1 in bands:
        row = uniform_filter1d(mask[:, cx0:cx1+1].sum(1).astype(float), 9)
        ry0, ry1 = _extent(row)                            # full vertical range (all blocks)
        bx0, bx1, by0, by1 = cx0*inv, cx1*inv, ry0*inv, ry1*inv
        bw, bh = bx1-bx0, by1-by0
        bx0 = max(0, bx0-bw*PAD); bx1 = min(W, bx1+bw*PAD)
        by0 = max(0, by0-bh*PAD); by1 = min(H, by1+bh*PAD)
        box = (int(bx0), int(by0), int(bx1), int(by1))
        ratio = ((box[2]-box[0])*(box[3]-box[1])) / (W*H)
        boxes.append((box, ratio))
    # single-page sanity floor: tiny crop -> keep full frame
    if len(boxes) == 1 and boxes[0][1] < MIN_KEEP:
        return [((0, 0, W, H), 1.0)]
    return boxes

def main(subset, preview):
    os.makedirs(OUTDIR, exist_ok=True)
    rows = list(csv.DictReader(open(MANIFEST)))
    if subset:
        rows = [r for r in rows if r["page_id"] in subset]
    pages = []
    for r in rows:
        photo_id = r["page_id"]               # manifest page_id == one source photo
        boxes = detect_page_boxes(r["orig_path"])
        sides = [""] if len(boxes) == 1 else ["a", "b"]
        with load_oriented(r["orig_path"]) as im:
            for (box, ratio), side in zip(boxes, sides):
                pid = photo_id + side
                crop = im.crop(box)
                crop.save(os.path.join(OUTDIR, pid + ".jpg"), quality=92)
                if preview:
                    t = crop.copy(); t.thumbnail((800, 800))
                    t.save(os.path.join(OUTDIR, pid + "_preview.jpg"))
                pages.append({"page_id": pid, "photo_id": photo_id, "side": side or "single",
                              "register": r["register"], "cropped": f"{OUTDIR}/{pid}.jpg",
                              "src": r["orig_path"], "kept_pct": round(ratio*100, 1)})
                print(f"{pid:7s} kept {ratio*100:5.1f}%  {r['register']}")
    # write pages.csv only on full runs (subset runs would clobber it)
    if not subset:
        with open(PAGES_CSV, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(pages[0].keys()))
            w.writeheader(); w.writerows(pages)
        print(f"\nwrote {PAGES_CSV}: {len(pages)} pages from {len(rows)} photos")
    else:
        print(f"\n{len(pages)} page(s) from {len(rows)} photo(s) (subset; pages.csv not rewritten)")

if __name__ == "__main__":
    args = sys.argv[1:]
    preview = "--preview" in args
    ids = [a for a in args if not a.startswith("-")]
    main(set(ids) or None, preview)
