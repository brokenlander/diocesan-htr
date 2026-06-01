#!/usr/bin/env python3
"""Bootstrap round: run a fine-tuned model over all Turate pages and harvest the
HIGH-CONFIDENCE lines as pseudo-gold (line image + the model's own text). These
join the human-seed gold to train the next model. Self-training: the model that
learned the hand now labels more of it, and we keep only what it's confident about.

Writes gold_harvest/<pid>/L###.png + .gt.txt for kept lines, prints a confidence
histogram, and writes a combined manifest (seed gold + harvest) for v2 training.
"""
import os, csv, glob, statistics
import numpy as np
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True
from kraken import blla
from kraken.lib import vgsl, segmentation
from kraken.tasks import RecognitionTaskModel
from kraken.configs import RecognitionInferenceConfig

SEG_MODEL = os.path.join(os.path.dirname(blla.__file__), "blla.mlmodel")
V1 = sorted(glob.glob("gold/models/turate_v1/best_*.safetensors"))[-1]
SEED = {"p001", "p002a", "p002b", "p003a", "p003b"}   # human-reviewed gold (keep as-is)
CONF_MIN = 0.85          # keep lines whose mean char-confidence >= this
MINLEN = 5               # ignore very short lines (margin bits)
HARVEST = "gold_harvest"

def main():
    seg_model = vgsl.TorchVGSLModel.load_model(SEG_MODEL)
    v1 = RecognitionTaskModel.load_model(V1)
    cfg = RecognitionInferenceConfig()
    turate = [r["page_id"] for r in csv.DictReader(open("dataset/pages.csv"))
              if "Turate" in r["register"]]
    targets = [p for p in turate if p not in SEED]
    print(f"v1: {V1}\nharvesting {len(targets)} pages (seed {len(SEED)} kept as gold)\n")

    all_conf, kept, seen_pages = [], 0, 0
    for pid in targets:
        src = f"processed/cropped/{pid}.jpg"
        if not os.path.exists(src):
            continue
        im = Image.open(src).convert("RGB")
        seg = blla.segment(im, model=seg_model, device="cpu")
        recs = list(v1.predict(im=im, segmentation=seg, config=cfg))
        line_imgs = [li for li, _ in segmentation.extract_polygons(im, seg)]
        outdir = f"{HARVEST}/{pid}"; os.makedirs(outdir, exist_ok=True)
        pkept = 0
        for i, rec in enumerate(recs):
            if i >= len(line_imgs):
                break
            text = (rec.prediction or "").strip()
            conf = float(np.mean(rec.confidences)) if getattr(rec, "confidences", None) else 0.0
            all_conf.append(conf)
            if conf >= CONF_MIN and len(text) >= MINLEN:
                lid = f"L{i+1:03d}"
                line_imgs[i].convert("RGB").save(f"{outdir}/{lid}.png")
                with open(f"{outdir}/{lid}.gt.txt", "w", encoding="utf-8") as f:
                    f.write(text + "\n")
                pkept += 1
        kept += pkept; seen_pages += 1
        print(f"  {pid}: {pkept}/{len(recs)} lines kept (conf>={CONF_MIN})", flush=True)

    # confidence histogram
    print(f"\nharvested {kept} lines from {seen_pages} pages")
    if all_conf:
        a = np.array(all_conf)
        print("conf distribution: " + "  ".join(
            f"{t:.2f}:{(a>=t).sum()}" for t in [0.7, 0.8, 0.85, 0.9, 0.95]))

    # combined manifest: seed gold gt.txt + harvested gt.txt
    seed_pngs = [f"{p}" for sid in SEED
                 for p in glob.glob(f"gold/{sid}/lines/*.gt.txt")]
    seed_pngs = [p.replace(".gt.txt", ".png") for p in seed_pngs]
    harvest_pngs = [p.replace(".gt.txt", ".png")
                    for p in glob.glob(f"{HARVEST}/*/*.gt.txt")]
    with open("gold/models/v2_trainfiles.txt", "w") as f:
        f.write("\n".join(seed_pngs + harvest_pngs) + "\n")
    print(f"v2 training set: {len(seed_pngs)} seed + {len(harvest_pngs)} harvest "
          f"= {len(seed_pngs)+len(harvest_pngs)} lines -> gold/models/v2_trainfiles.txt")

if __name__ == "__main__":
    main()
