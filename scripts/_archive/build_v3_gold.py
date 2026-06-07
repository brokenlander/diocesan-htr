#!/usr/bin/env python3
"""Build v3 training data from Claude's reconciled column across all gold pages.
Writes gold/<pid>/lines/L###.gt.txt from ensemble.tsv `reconciled`, cleaning
markers ([?] -> stripped, [inferred] -> content, [...]/[skip] -> excluded), and
emits a manifest. v3 trains on these vs stock McCATMuS."""
import csv, glob, os, re

def clean(raw):
    t = (raw or "").strip()
    if not t or t == "[skip]" or t.startswith("[margin"):
        return None
    if "[…]" in t or "[...]" in t:
        return None
    t = re.sub(r"\[([^\]]*?)\?\]", r"\1", t)
    t = t.replace("[?]", "")
    t = re.sub(r"\[([^\]]*?)\]", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t or None

pngs = []
kept = dropped = 0
for tsv in sorted(glob.glob("gold/p*/ensemble.tsv")):
    linedir = os.path.join(os.path.dirname(tsv), "lines")
    for old in glob.glob(f"{linedir}/*.gt.txt"):
        os.remove(old)
    for r in csv.DictReader(open(tsv), delimiter="\t"):
        img = f"{linedir}/{r['line']}.png"
        if not os.path.exists(img):
            continue
        txt = clean(r.get("reconciled"))
        if txt is None:
            dropped += 1; continue
        with open(f"{linedir}/{r['line']}.gt.txt", "w", encoding="utf-8") as f:
            f.write(txt + "\n")
        pngs.append(img); kept += 1

with open("gold/models/v3_trainfiles.txt", "w") as f:
    f.write("\n".join(pngs) + "\n")
print(f"v3 gold: {kept} clean training lines ({dropped} dropped as uncertain/junk) "
      f"from {len(glob.glob('gold/p*/ensemble.tsv'))} pages")
print("-> gold/models/v3_trainfiles.txt")
