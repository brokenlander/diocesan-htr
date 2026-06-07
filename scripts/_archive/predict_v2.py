#!/usr/bin/env python3
"""Run a kraken recognizer (default: cluster v2) over pages and print per-line reads.

Uses the SAME blla segmentation as gold_prep (deterministic), so the L### ids line
up with each page's correct.tsv. For the Claude review pass: shows the model's read
of UNSEEN pages so we can verify against the image and harvest only correct lines.

Usage: python scripts/predict_v2.py [--model PATH] p122 p129 ...
"""
import sys, os
import paths
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True
from kraken import blla, rpred
from kraken.lib import models, vgsl

SEG = os.path.join(os.path.dirname(blla.__file__), "blla.mlmodel")
DEFAULT = "gold/models/cluster-1570s/v2/best.mlmodel"

def main(argv):
    model = DEFAULT
    if argv and argv[0] == "--model":
        model = argv[1]; argv = argv[2:]
    seg_model = vgsl.TorchVGSLModel.load_model(SEG)
    rec = models.load_any(model, device="cpu")
    for pid in argv:
        src = paths.cropped(pid)
        if not os.path.exists(src):
            print(f"{pid}: no image"); continue
        im = Image.open(src).convert("RGB")
        seg = blla.segment(im, model=seg_model, device="cpu")
        preds = list(rpred.rpred(rec, im, seg))
        print(f"=== {pid} ===")
        for i, p in enumerate(preds):
            print(f"L{i+1:03d}\t{p.prediction}")

if __name__ == "__main__":
    main(sys.argv[1:])
