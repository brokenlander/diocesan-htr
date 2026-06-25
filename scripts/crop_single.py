#!/usr/bin/env python3
"""crop_single.py — robust SINGLE-LEAF crop for the 2019 ~13 MP parish-archive batch.

These photos are loose documents laid on a dark table, ONE leaf per photo (NOT open
books). We bound the DOCUMENT SHEET — the dominant bright region against the dark
background — and crop to it with padding. Deliberately:
  - NO spread-splitting (that mangled single leaves in the Turate-tuned crop_pages.py),
  - a safety FLOOR: if the detected box is implausibly small (detection went wrong) or
    nearly the whole frame, fall back to the FULL frame — we never clip document text.
One crop per photo -> processed/cropped/<slug>/<pid>.jpg ; merges dataset/pages.csv.

Usage: PYTHONPATH=scripts .venv/bin/python3 scripts/crop_single.py <pid> [pid ...] [--preview]
"""
import os, csv, sys
import numpy as np
from scipy.ndimage import label, binary_closing, binary_opening
from PIL import Image, ImageFile, ImageOps
ImageFile.LOAD_TRUNCATED_IMAGES = True
import paths

MANIFEST  = "dataset/manifest.csv"
PAGES_CSV = "dataset/pages.csv"
OUTDIR    = "processed/cropped"
ANALYZE_MAX = 1600     # downscale long edge to this for analysis
PAD         = 0.02     # pad the detected box by this fraction (generous; never clip)
OTSU_FLOOR  = 95       # never threshold below this (paper is bright; avoids cutting into midtones)
MIN_KEEP    = 0.45     # box < this fraction of frame -> detection suspect -> FULL frame
MAX_KEEP    = 0.98     # box > this -> no meaningful trim -> FULL frame

def load_oriented(path):
    return ImageOps.exif_transpose(Image.open(path))

def _otsu(gray):
    """Classic Otsu threshold on a uint8 image (bimodal: dark table vs bright paper)."""
    hist = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
    total = gray.size
    sum_total = (np.arange(256) * hist).sum()
    sumB = wB = 0.0
    maxvar, thresh = -1.0, 128
    for t in range(256):
        wB += hist[t]
        if wB == 0:
            continue
        wF = total - wB
        if wF == 0:
            break
        sumB += t * hist[t]
        mB = sumB / wB
        mF = (sum_total - sumB) / wF
        var = wB * wF * (mB - mF) ** 2
        if var > maxvar:
            maxvar, thresh = var, t
    return thresh

def detect_document_box(path):
    """Return (box, kept_ratio, mode). box bounds the main document sheet."""
    with load_oriented(path) as im:
        W, H = im.size
        g = im.convert("L")
        scale = min(1.0, ANALYZE_MAX / max(W, H))
        if scale < 1.0:
            g = g.resize((max(1, int(W * scale)), max(1, int(H * scale))))
        lum = np.asarray(g)
    full = ((0, 0, W, H), 1.0)
    T = max(_otsu(lum), OTSU_FLOOR)
    paper = lum > T
    if paper.mean() < 0.02:                                  # almost nothing bright
        return (*full, "fallback-no-paper")
    paper = binary_closing(paper, structure=np.ones((5, 5)), iterations=2)   # fill text holes
    paper = binary_opening(paper, structure=np.ones((3, 3)), iterations=1)   # drop specks
    lbl, n = label(paper)
    if n == 0:
        return (*full, "fallback-no-component")
    sizes = np.bincount(lbl.ravel()); sizes[0] = 0           # ignore background label
    main = int(sizes.argmax())
    ys, xs = np.where(lbl == main)
    inv = 1.0 / scale
    x0, x1, y0, y1 = xs.min() * inv, xs.max() * inv, ys.min() * inv, ys.max() * inv
    bw, bh = x1 - x0, y1 - y0
    x0 = max(0, x0 - bw * PAD); x1 = min(W, x1 + bw * PAD)
    y0 = max(0, y0 - bh * PAD); y1 = min(H, y1 + bh * PAD)
    box = (int(x0), int(y0), int(x1), int(y1))
    ratio = ((box[2] - box[0]) * (box[3] - box[1])) / (W * H)
    if ratio < MIN_KEEP:
        return (*full, f"fallback-small({ratio:.2f})")
    if ratio > MAX_KEEP:
        return (*full, "fullframe-no-trim")
    return box, ratio, "crop"

def main(subset, preview):
    rows = list(csv.DictReader(open(MANIFEST)))
    if subset:
        rows = [r for r in rows if r["page_id"] in subset]
    if not rows:
        print("!! no manifest rows matched the given pids — refusing to write (check the pid list)")
        sys.exit(2)
    pages, modes = [], {}
    for r in rows:
        pid = r["page_id"]
        box, ratio, mode = detect_document_box(r["orig_path"])
        modes[mode.split("(")[0]] = modes.get(mode.split("(")[0], 0) + 1
        sl = paths.slug(r["register"])
        outdir = os.path.join(OUTDIR, sl)
        os.makedirs(outdir, exist_ok=True)
        with load_oriented(r["orig_path"]) as im:
            crop = im.crop(box)
            crop.save(os.path.join(outdir, pid + ".jpg"), quality=92)
            if preview:
                t = crop.copy(); t.thumbnail((900, 900))
                t.save(os.path.join(outdir, pid + "_preview.jpg"))
        pages.append({"page_id": pid, "photo_id": pid, "side": "single",
                      "register": r["register"], "cropped": f"{OUTDIR}/{sl}/{pid}.jpg",
                      "src": r["orig_path"], "kept_pct": round(ratio * 100, 1)})
        print(f"{pid:7s} kept {ratio*100:5.1f}%  [{mode}]  {sl}")
    # merge pages.csv additively (keep rows for photos NOT in this run)
    fieldnames = ["page_id", "photo_id", "side", "register", "cropped", "src", "kept_pct"]
    prior = list(csv.DictReader(open(PAGES_CSV))) if os.path.exists(PAGES_CSV) else []
    done = {p["photo_id"] for p in pages}
    merged = [r for r in prior if r.get("photo_id") not in done] + pages
    merged.sort(key=lambda r: r["page_id"])
    with open(PAGES_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader(); w.writerows(merged)
    print(f"\nmodes: {modes}")
    print(f"{PAGES_CSV}: +{len(pages)} page(s) this run; {len(merged)} total")

if __name__ == "__main__":
    args = sys.argv[1:]
    preview = "--preview" in args
    ids = [a for a in args if not a.startswith("-")]
    main(set(ids) or None, preview)
