#!/usr/bin/env python3
"""Build the X5 fine-tune SEED from Claude-reconciled labels.

Reads gold/<x5>/seed_labels.json, writes a sibling <L>.gt.txt next to each
labeled line strip, and emits a DETERMINISTIC train/val split (every Nth line
to val) so the v3-warm-start vs stock-McCATMuS runs train on identical data.

Outputs (under gold/models/x-5-1642-74/):
  seed_train.txt, seed_val.txt   manifests of .png paths (path-mode training)
Usage: python scripts/x5_seed_build.py
"""
import json, os
import paths

SL = "x-5-1642-74"
GOLD = f"gold/{SL}"
OUT = paths.model_dir(SL)
VAL_EVERY = 5  # every 5th labeled line -> validation (~20%)

def main():
    labels = json.load(open(f"{GOLD}/seed_labels.json"))
    os.makedirs(OUT, exist_ok=True)
    pngs = []
    for pid, lines in labels.items():
        if pid.startswith("_"):
            continue
        for lid, text in lines.items():
            png = f"{GOLD}/{pid}/lines/{lid}.png"
            if not os.path.exists(png):
                print(f"  MISSING {png}"); continue
            with open(png.replace(".png", ".gt.txt"), "w", encoding="utf-8") as f:
                f.write(text.strip() + "\n")
            pngs.append(png)
    pngs.sort()
    train = [p for i, p in enumerate(pngs) if i % VAL_EVERY != 0]
    val   = [p for i, p in enumerate(pngs) if i % VAL_EVERY == 0]
    with open(f"{OUT}/seed_train.txt", "w") as f:
        f.write("\n".join(train) + "\n")
    with open(f"{OUT}/seed_val.txt", "w") as f:
        f.write("\n".join(val) + "\n")
    print(f"labeled {len(pngs)} lines -> {len(train)} train / {len(val)} val")
    print(f"manifests: {OUT}/seed_train.txt , {OUT}/seed_val.txt")

if __name__ == "__main__":
    main()
