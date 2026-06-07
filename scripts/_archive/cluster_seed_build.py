#!/usr/bin/env python3
"""Build the combined CLUSTER fine-tune seed from Claude-reconciled labels.

Reads gold/cluster-1570s/seed_labels.json ({pid: {L###: text}}), writes a sibling
<L>.gt.txt next to each labeled line strip (strips live under each register's own
gold/<slug>/<pid>/lines/), and emits manifests:
  seed_all.txt          all labeled strips (one .png path per line)
  seed_<slug>.txt       per-register manifest (for per-register `ketos test`)
under gold/models/cluster-1570s/. Prints per-register line counts.

Usage: python scripts/cluster_seed_build.py
"""
import json, os, collections
import paths

SEED = "gold/cluster-1570s/seed_labels.json"
OUT = paths.model_dir("cluster-1570s")

def main():
    labels = json.load(open(SEED))
    os.makedirs(OUT, exist_ok=True)
    by_reg = collections.defaultdict(list)
    allpngs = []
    for pid, lines in labels.items():
        if pid.startswith("_"):
            continue
        sl = paths.page_slug(pid)
        for lid, text in lines.items():
            png = f"{paths.gold(pid)}/lines/{lid}.png"
            if not os.path.exists(png):
                print(f"  MISSING {png}"); continue
            with open(png.replace(".png", ".gt.txt"), "w", encoding="utf-8") as f:
                f.write(text.strip() + "\n")
            by_reg[sl].append(png); allpngs.append(png)
    allpngs.sort()
    with open(f"{OUT}/seed_all.txt", "w") as f:
        f.write("\n".join(allpngs) + "\n")
    for sl, pngs in sorted(by_reg.items()):
        with open(f"{OUT}/seed_{sl}.txt", "w") as f:
            f.write("\n".join(sorted(pngs)) + "\n")
    print(f"TOTAL {len(allpngs)} labeled lines")
    for sl, pngs in sorted(by_reg.items()):
        print(f"  {sl:16s} {len(pngs)}")
    print(f"manifests -> {OUT}/seed_all.txt + seed_<slug>.txt")

if __name__ == "__main__":
    main()
