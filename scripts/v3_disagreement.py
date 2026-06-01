#!/usr/bin/env python3
"""After v3 trains: run it over every Turate page, align to Claude's reconciled
column, and surface ONLY the lines worth re-judging — where v3 genuinely adds
signal rather than echoing my own guesses:

  GAP-FILL : my reconciliation had an illegible gap ([...]) but v3 (which was NOT
             trained on those lines) produced a substantive read. Real new candidate.
  DISAGREE : I flagged the line uncertain ([?]) AND v3 differs from my read. Worth a look.

Skips: lines where I was confident (no markers) — v3 agreeing there is circular
(it was trained on my reconciliation), and lines I marked [skip].
Writes gold/models/v3_review.tsv for Claude to re-judge (zooming line strips as needed).
"""
import csv, glob, os, difflib, re
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True
from kraken import blla
from kraken.lib import vgsl
from kraken.tasks import RecognitionTaskModel
from kraken.configs import RecognitionInferenceConfig

SEG = os.path.join(os.path.dirname(blla.__file__), "blla.mlmodel")
V3 = sorted(glob.glob("gold/models/turate_v3/best_*.safetensors"))[-1]

def strip_markers(t):
    t = re.sub(r"\[([^\]]*?)\?\]", r"\1", t or "")
    t = t.replace("[?]", "")
    t = re.sub(r"\[([^\]]*?)\]", r"\1", t)
    return re.sub(r"\s+", " ", t).strip()

def main():
    seg_model = vgsl.TorchVGSLModel.load_model(SEG)
    v3 = RecognitionTaskModel.load_model(V3)
    cfg = RecognitionInferenceConfig()
    out = []
    for tsv in sorted(glob.glob("gold/p*/ensemble.tsv")):
        pid = os.path.basename(os.path.dirname(tsv))
        rows = list(csv.DictReader(open(tsv), delimiter="\t"))
        im = Image.open(f"processed/cropped/{pid}.jpg").convert("RGB")
        seg = blla.segment(im, model=seg_model, device="cpu")
        preds = list(v3.predict(im=im, segmentation=seg, config=cfg))
        for i, r in enumerate(rows):
            recon = r["reconciled"]
            v3txt = preds[i].prediction.strip() if i < len(preds) else ""
            if recon == "[skip]":
                continue
            is_gap = "[...]" in recon or "[…]" in recon
            is_unc = "[?]" in recon
            if not (is_gap or is_unc):
                continue                      # I was confident -> v3 echo is circular
            sim = difflib.SequenceMatcher(None, strip_markers(recon), v3txt).ratio()
            if is_gap and len(v3txt) >= 5:
                out.append((pid, r["line"], "GAP-FILL", recon, v3txt))
            elif is_unc and sim < 0.7:
                out.append((pid, r["line"], "DISAGREE", recon, v3txt))
    with open("gold/models/v3_review.tsv", "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["pid", "line", "flag", "reconciled", "v3"])
        w.writerows(out)
    g = sum(1 for o in out if o[2] == "GAP-FILL")
    print(f"flagged {len(out)} lines for re-judging: {g} GAP-FILL, {len(out)-g} DISAGREE")
    print("-> gold/models/v3_review.tsv")

if __name__ == "__main__":
    main()
