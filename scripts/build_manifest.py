#!/usr/bin/env python3
"""Build the dataset manifest: one row per source image. This is the spine.
Transcription/dedup/translation columns get filled by later stages."""
import os, csv, hashlib, re
from PIL import Image, ImageFile, ImageOps
ImageFile.LOAD_TRUNCATED_IMAGES = True  # tolerate Turate p.25's 11-byte tail

RAW = "raw/Archivio diocesano"
OUT = "dataset/manifest.csv"
os.makedirs("dataset", exist_ok=True)

rows = []
for dirpath, _, files in os.walk(RAW):
    for f in sorted(files):
        if not f.lower().endswith((".jpg", ".jpeg")):
            continue
        p = os.path.join(dirpath, f)
        register = os.path.relpath(dirpath, RAW)
        with open(p, "rb") as fh:
            sha = hashlib.sha256(fh.read()).hexdigest()[:12]
        try:
            with ImageOps.exif_transpose(Image.open(p)) as im:  # honor rotation flags
                w, h = im.size
                readable = "ok"
        except Exception as e:
            w = h = 0
            readable = f"ERR:{e}"
        rows.append({
            "page_id": "",  # assigned below, stable order
            "register": register,
            "orig_path": p,
            "filename": f,
            "width": w, "height": h,
            "megapixels": round(w * h / 1e6, 1),
            "bytes": os.path.getsize(p),
            "sha12": sha,
            "readable": readable,
            "dup_group": "",          # filled after text-based dedup
            "mccatmus": "",           # transcription status per engine
            "transkribus": "",
            "gemini": "",
            "reconciled": "",
            "translated": "",
        })

# stable page ids: preserve any already assigned in the existing manifest (keyed by
# register+filename) so prior pages NEVER renumber; assign new sequential ids
# (continuing past the current max) to newly-added images only. This makes ingestion
# additive — re-running after dropping in new folders won't disturb finished pages.
existing, maxn = {}, 0
if os.path.exists(OUT):
    for r0 in csv.DictReader(open(OUT)):
        existing[(r0["register"], r0["filename"])] = r0["page_id"]
        m = re.match(r"p(\d+)$", r0.get("page_id", "") or "")
        if m:
            maxn = max(maxn, int(m.group(1)))
rows.sort(key=lambda r: (r["register"], r["filename"]))
for r in rows:                                       # freeze existing pages
    r["page_id"] = existing.get((r["register"], r["filename"]), "")
n = maxn
for r in rows:                                       # number new pages, in stable order
    if not r["page_id"]:
        n += 1
        r["page_id"] = f"p{n:03d}"

with open(OUT, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

# summary
print(f"manifest: {OUT}  ({len(rows)} images)")
print(f"unreadable: {sum(1 for r in rows if r['readable'] != 'ok')}")
print("\nresolution sanity (real megapixels) by register:")
from collections import defaultdict
agg = defaultdict(list)
for r in rows:
    agg[r["register"]].append(r["megapixels"])
for reg in sorted(agg):
    mp = agg[reg]
    print(f"  {len(mp):3d} pages  {min(mp):4.1f}-{max(mp):4.1f} MP   {reg}")
