#!/usr/bin/env python3
"""split_spread.py — manually split a genuine two-page spread photo that
crop_pages.py failed to split (e.g. one leaf's ink too faint for the band
filter: capture-3 p634 kept only the left page and DROPPED the right one).

Lossless by construction: the photo is EXIF-oriented and cut at a given gutter
fraction with OVERLAP margin on both halves — no ink detection, no trimming, so
nothing can be cropped away. Replaces the photo's row(s) in dataset/pages.csv
with the a/b rows and removes a stale single-crop <pid>.jpg if present.

Usage: PYTHONPATH=scripts .venv/bin/python3 scripts/split_spread.py <photo_id> [gutter_frac=0.5] [overlap=0.03]
"""
import os, csv, sys
from PIL import Image, ImageFile, ImageOps
ImageFile.LOAD_TRUNCATED_IMAGES = True
import paths

MANIFEST  = "dataset/manifest.csv"
PAGES_CSV = "dataset/pages.csv"
OUTDIR    = "processed/cropped"

def main(photo_id, frac=0.5, overlap=0.03):
    row = next(r for r in csv.DictReader(open(MANIFEST)) if r["page_id"] == photo_id)
    sl = paths.slug(row["register"])
    outdir = os.path.join(OUTDIR, sl)
    os.makedirs(outdir, exist_ok=True)
    pages = []
    with ImageOps.exif_transpose(Image.open(row["orig_path"])) as im:
        W, H = im.size
        if W <= H:
            print(f"WARNING: {photo_id} oriented {W}x{H} is portrait — is it really a spread?")
        cut = int(W * frac); ov = int(W * overlap)
        halves = {"a": (0, 0, min(W, cut + ov), H), "b": (max(0, cut - ov), 0, W, H)}
        for side, box in halves.items():
            pid = photo_id + side
            im.crop(box).save(os.path.join(outdir, pid + ".jpg"), quality=92)
            ratio = (box[2]-box[0]) * (box[3]-box[1]) / (W*H)
            pages.append({"page_id": pid, "photo_id": photo_id, "side": side,
                          "register": row["register"], "cropped": f"{OUTDIR}/{sl}/{pid}.jpg",
                          "src": row["orig_path"], "kept_pct": round(ratio*100, 1)})
            print(f"{pid:7s} kept {ratio*100:5.1f}%  {sl}  (manual split @ {frac}, overlap {overlap})")
    stale = os.path.join(outdir, photo_id + ".jpg")
    if os.path.exists(stale):
        os.remove(stale)
        print(f"removed stale single crop {stale}")
    prior = list(csv.DictReader(open(PAGES_CSV))) if os.path.exists(PAGES_CSV) else []
    merged = [r for r in prior if r.get("photo_id") != photo_id] + pages
    merged.sort(key=lambda r: r["page_id"])
    with open(PAGES_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(pages[0].keys()))
        w.writeheader(); w.writerows(merged)
    print(f"{PAGES_CSV}: {photo_id} -> {photo_id}a/{photo_id}b; {len(merged)} rows total")

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(1)
    main(a[0], float(a[1]) if len(a) > 1 else 0.5, float(a[2]) if len(a) > 2 else 0.03)
