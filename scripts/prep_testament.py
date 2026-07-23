#!/usr/bin/env python3
"""prep_testament.py — build reader inputs for the 'Testamento Ambrogio Fagnani' register.

These pages are NOT photos: they are the native 200 ppi scans extracted from the source
PDF (pdfimages -j; the PDF has no text layer, and rendering above 200 ppi only upscales).
No cropping is needed (already page-bounded); instead apply the enhancement chain that
proved out on the first (mis-filed) attempt: grayscale + autocontrast + 2x LANCZOS
upscale + unsharp. Writes processed/cropped/<slug>/<pid>.jpg and merges dataset/pages.csv
(side=single, kept_pct=100.0 — nothing is discarded, only enhanced).

Usage: PYTHONPATH=scripts .venv/bin/python3 scripts/prep_testament.py [pid ...]   (default: all 14)
"""
import os, csv, sys
from PIL import Image, ImageFile, ImageOps, ImageFilter
ImageFile.LOAD_TRUNCATED_IMAGES = True
import paths

MANIFEST  = "dataset/manifest.csv"
PAGES_CSV = "dataset/pages.csv"
OUTDIR    = "processed/cropped"
REGISTER  = "Testamento Ambrogio Fagnani"

def enhance(im):
    g = ImageOps.autocontrast(ImageOps.grayscale(im))
    g = g.resize((g.width * 2, g.height * 2), Image.LANCZOS)
    return g.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))

def main(subset):
    rows = [r for r in csv.DictReader(open(MANIFEST)) if r["register"] == REGISTER]
    if subset:
        rows = [r for r in rows if r["page_id"] in subset]
    sl = paths.slug(REGISTER)
    outdir = os.path.join(OUTDIR, sl)
    os.makedirs(outdir, exist_ok=True)
    pages = []
    for r in rows:
        pid = r["page_id"]
        with ImageOps.exif_transpose(Image.open(r["orig_path"])) as im:
            enhance(im).save(os.path.join(outdir, pid + ".jpg"), quality=92)
        pages.append({"page_id": pid, "photo_id": pid, "side": "single",
                      "register": REGISTER, "cropped": f"{OUTDIR}/{sl}/{pid}.jpg",
                      "src": r["orig_path"], "kept_pct": 100.0})
        print(f"{pid}  enhanced (gray+autocontrast+2x+unsharp)  {sl}")
    prior = list(csv.DictReader(open(PAGES_CSV))) if os.path.exists(PAGES_CSV) else []
    done = {p["photo_id"] for p in pages}
    merged = [r for r in prior if r.get("photo_id") not in done] + pages
    merged.sort(key=lambda r: r["page_id"])
    with open(PAGES_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(pages[0].keys()))
        w.writeheader(); w.writerows(merged)
    print(f"{PAGES_CSV}: +{len(pages)} page(s); {len(merged)} rows total")

if __name__ == "__main__":
    main(set(a for a in sys.argv[1:] if not a.startswith("-")) or None)
