#!/usr/bin/env python3
"""One-time: move existing flat outputs into per-register (slug) subfolders.
Idempotent-ish (skips if already moved). All current pages are Turate -> 'turate'."""
import csv, os, shutil, glob
from paths import slug

rows = list(csv.DictReader(open("dataset/pages.csv")))
pid2slug = {r["page_id"]: slug(r["register"]) for r in rows}

def mv(src, dst):
    if os.path.exists(src) and not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        shutil.move(src, dst); return 1
    return 0

n = 0
for pid, sl in pid2slug.items():
    n += mv(f"processed/cropped/{pid}.jpg", f"processed/cropped/{sl}/{pid}.jpg")
    for eng in ["reconciled", "mccatmus", "tridis", "transkribus", "trocr"]:
        n += mv(f"processed/transcriptions/{eng}/{pid}.txt",
                f"processed/transcriptions/{sl}/{eng}/{pid}.txt")
    n += mv(f"processed/translations/{pid}.txt", f"processed/translations/{sl}/{pid}.txt")
    if os.path.isdir(f"gold/{pid}"):
        os.makedirs(f"gold/{sl}", exist_ok=True); n += mv(f"gold/{pid}", f"gold/{sl}/{pid}")
    if os.path.isdir(f"gold_harvest/{pid}"):
        os.makedirs(f"gold_harvest/{sl}", exist_ok=True); n += mv(f"gold_harvest/{pid}", f"gold_harvest/{sl}/{pid}")

# combined docs
mv("processed/transcriptions/turate_reconciled.txt", "processed/transcriptions/turate/reconciled_combined.txt")
mv("processed/translations/turate_italiano.txt", "processed/translations/turate/italiano_combined.txt")

# models: gold/models/turate_v{1,2,3} -> gold/models/turate/v{1,2,3}; loose files -> gold/models/turate/
os.makedirs("gold/models/turate", exist_ok=True)
for d in glob.glob("gold/models/turate_v*"):
    if os.path.isdir(d):
        n += mv(d, f"gold/models/turate/{os.path.basename(d).replace('turate_', '')}")
for f in glob.glob("gold/models/*"):
    if os.path.isfile(f):
        n += mv(f, f"gold/models/turate/{os.path.basename(f)}")

# update pages.csv cropped column to the new location
for r in rows:
    r["cropped"] = f"processed/cropped/{pid2slug[r['page_id']]}/{r['page_id']}.jpg"
with open("dataset/pages.csv", "w", newline="") as fo:
    w = csv.DictWriter(fo, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)

print(f"moved {n} items into register subfolders; pages.csv cropped paths updated")
