#!/usr/bin/env python3
"""Turn corrected gold into Kraken training data (kraken 'path' format).

Reads gold/<pid>/correct.tsv and writes the `correct` text of each line to its
line-image sibling gold/<pid>/lines/L###.gt.txt. Then train with:
    ketos train -f path -d cpu --threads 16 -o model gold/*/lines/*.png

Lines whose `correct` is empty or '[skip]' are excluded (segmentation junk:
stray strokes, the 'co' column, bare folio numbers you don't want to train on).

Usage: python scripts/gold_finalize.py p001 p002a ...   (default: all gold/ pages)
"""
import sys, os, csv, glob, re

def clean_for_training(raw):
    """Return a training-clean line, or None to EXCLUDE it.
    Excludes junk ([skip]/empty), marginalia, and any line with an illegible gap
    ([...]/[…]) — you can't train on a line with a hole. Strips uncertainty: a
    [guess?] or [inferred] becomes its bare content (we train on our best read)."""
    t = (raw or "").strip()
    if not t or t == "[skip]" or t.startswith("[margin"):
        return None
    if "[…]" in t or "[...]" in t:            # illegible gap -> can't use the line
        return None
    t = re.sub(r"\[([^\]]*?)\?\]", r"\1", t)  # [guess?] -> guess
    t = t.replace("[?]", "")                  # bare uncertainty marker
    t = re.sub(r"\[([^\]]*?)\]", r"\1", t)    # [inferred] -> inferred
    t = re.sub(r"\s+", " ", t).strip()
    return t or None

def finalize(pid):
    tsv = f"gold/{pid}/correct.tsv"
    linedir = f"gold/{pid}/lines"
    if not os.path.exists(tsv):
        print(f"{pid}: no correct.tsv"); return (0, 0)
    written = skipped = 0
    # clear stale gt.txt first
    for old in glob.glob(f"{linedir}/*.gt.txt"):
        os.remove(old)
    for row in csv.DictReader(open(tsv), delimiter="\t"):
        lid = row["line"]
        txt = clean_for_training(row.get("correct"))
        img = f"{linedir}/{lid}.png"
        if not os.path.exists(img):
            continue
        if txt is None:                       # junk / illegible / uncertain -> exclude
            skipped += 1
            continue
        with open(f"{linedir}/{lid}.gt.txt", "w", encoding="utf-8") as f:
            f.write(txt + "\n")
        written += 1
    print(f"{pid}: {written} training lines, {skipped} skipped")
    return (written, skipped)

if __name__ == "__main__":
    pids = sys.argv[1:] or [os.path.basename(os.path.dirname(p))
                            for p in glob.glob("gold/*/correct.tsv")]
    tot = [0, 0]
    for pid in sorted(pids):
        w, s = finalize(pid); tot[0] += w; tot[1] += s
    print(f"\ntotal: {tot[0]} training lines, {tot[1]} skipped across {len(pids)} pages")
