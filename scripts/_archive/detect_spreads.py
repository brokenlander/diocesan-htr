#!/usr/bin/env python3
"""Detect how many written PAGES each photo contains (1 = single page,
2 = open-book spread with both sides written). Counts substantial vertical
text columns via the ink-density profile. Diagnostic only."""
import sys, glob, os
import numpy as np
from scipy.ndimage import uniform_filter, uniform_filter1d
from PIL import Image, ImageFile, ImageOps
ImageFile.LOAD_TRUNCATED_IMAGES = True

PAPER_MIN, INK_DELTA, ANALYZE_MAX = 130, 25, 1500

def page_columns(path):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    W, H = im.size
    s = min(1.0, ANALYZE_MAX / max(W, H))
    if s < 1.0:
        im = im.resize((int(W*s), int(H*s)))
    a = np.asarray(im).astype(np.float32)
    lum = 0.299*a[...,0] + 0.587*a[...,1] + 0.114*a[...,2]
    k = max(15, int(max(lum.shape)/15))
    local = uniform_filter(lum, size=k)
    mask = (local > PAPER_MIN) & (lum < local - INK_DELTA)
    col = uniform_filter1d(mask.sum(0).astype(float), 9)
    if col.max() <= 0:
        return 0, []
    thr = 0.08 * np.percentile(col, 92)            # low bar: catch full text columns
    above = col > max(thr, 1)
    runs, i, n = [], 0, len(col)
    while i < n:
        if above[i]:
            j = i
            while j+1 < n and above[j+1]:
                j += 1
            runs.append((i, j, col[i:j+1].sum()))
            i = j+1
        else:
            i += 1
    if not runs:
        return 0, []
    # keep runs that are a real column: wide enough AND enough ink vs the biggest
    maxink = max(r[2] for r in runs)
    Wn = len(col)
    pages = [r for r in runs if (r[1]-r[0]) > 0.07*Wn and r[2] > 0.20*maxink]
    spans = [(round(a/Wn, 2), round(b/Wn, 2)) for a, b, _ in pages]
    return len(pages), spans

if __name__ == "__main__":
    paths = sys.argv[1:] or sorted(glob.glob("processed/cropped/p*.jpg"))
    # if given page ids, map to originals via manifest
    import csv
    man = {r["page_id"]: r["orig_path"] for r in csv.DictReader(open("dataset/manifest.csv"))}
    from collections import Counter
    dist = Counter()
    for p in paths:
        pid = os.path.splitext(os.path.basename(p))[0]
        orig = man.get(pid, p)
        n, spans = page_columns(orig)
        dist[n] += 1
        print(f"{pid}: {n} page(s)  {spans}")
    print("\ndistribution:", dict(dist))
