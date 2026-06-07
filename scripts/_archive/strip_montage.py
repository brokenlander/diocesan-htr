#!/usr/bin/env python3
"""Montage the SUBSTANTIAL line strips of gold-prepped pages for Claude reconciliation.

For each page, stacks its line strips (those whose McCATMuS candidate is >= MINLEN chars,
i.e. full lines not fragments) with their L### ids, so Claude can read a whole page's
worth of lines in one image and label them in order. Writes /tmp/<pid>_gold.png.

Usage: python scripts/strip_montage.py [--minlen N] p180 p202 ...
"""
import sys, csv, os
import paths
from PIL import Image, ImageDraw

def montage(pid, minlen):
    d = paths.gold(pid)
    tsv = f"{d}/correct.tsv"
    if not os.path.exists(tsv):
        print(f"{pid}: no correct.tsv (prep it first)"); return
    rows = list(csv.DictReader(open(tsv), delimiter="\t"))
    sub = [r["line"] for r in rows if len((r["mccatmus"] or "").strip()) >= minlen]
    if not sub:
        print(f"{pid}: no substantial strips"); return
    imgs = [(lid, Image.open(f"{d}/lines/{lid}.png").convert("RGB")) for lid in sub]
    W = max(im.width for _, im in imgs)
    H = sum(im.height for _, im in imgs) + 12 * len(imgs)
    c = Image.new("RGB", (W + 62, H), "white"); dr = ImageDraw.Draw(c); y = 0
    for lid, im in imgs:
        dr.text((3, y + 8), lid, fill="red"); c.paste(im, (58, y)); y += im.height + 12
    out = f"/tmp/{pid}_gold.png"; c.save(out)
    print(f"{pid}: {len(imgs)} strips -> {out}")

if __name__ == "__main__":
    args = sys.argv[1:]
    minlen = 20
    if args and args[0] == "--minlen":
        minlen = int(args[1]); args = args[2:]
    for pid in args:
        montage(pid, minlen)
