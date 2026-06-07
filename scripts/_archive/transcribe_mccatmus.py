#!/usr/bin/env python3
"""Batch McCATMuS (Kraken) transcription over all cropped pages.

Loads the segmentation and recognition models ONCE (per-page CLI invocation
would reload them 359 times), then for each page: baseline-segment -> recognize.
Resumable: skips pages whose output already exists. One .txt per page.

Usage:
  python scripts/transcribe_mccatmus.py            # all pages (resumable)
  python scripts/transcribe_mccatmus.py --limit 1  # smoke-test on first page
"""
import os, sys, glob, time
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True
from kraken import blla, rpred
from kraken.lib import models, vgsl

CROPPED = "processed/cropped"
OUTDIR = "processed/transcriptions/mccatmus"
SEG_MODEL_PATH = os.path.join(os.path.dirname(blla.__file__), "blla.mlmodel")

def find_rec_model():
    hits = glob.glob(os.path.expanduser(
        "~/.local/share/htrmopo/**/McCATMuS*.mlmodel"), recursive=True)
    if not hits:
        sys.exit("McCATMuS model not found; run: kraken get 10.5281/zenodo.13788177")
    return hits[0]

def main(limit=None):
    os.makedirs(OUTDIR, exist_ok=True)
    print("loading models...", flush=True)
    seg_model = vgsl.TorchVGSLModel.load_model(SEG_MODEL_PATH)
    rec_model = models.load_any(find_rec_model(), device="cpu")

    pages = sorted(glob.glob(os.path.join(CROPPED, "p*.jpg")))
    if limit:
        pages = pages[:limit]
    total = len(pages)
    processed = 0          # transcribed this run (excludes skips) for timing
    t0 = time.time()
    for i, path in enumerate(pages, 1):
        pid = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(OUTDIR, pid + ".txt")
        if os.path.exists(out):
            continue
        try:
            im = Image.open(path).convert("RGB")
            seg = blla.segment(im, model=seg_model, device="cpu")
            rec = rpred.rpred(rec_model, im, seg)
            text = "\n".join(r.prediction for r in rec)
            with open(out, "w") as f:
                f.write(text + "\n")
            processed += 1
            rate = (time.time() - t0) / processed
            eta = rate * (total - i)
            print(f"[{i}/{total}] {pid}  {len(text.splitlines()):2d} lines  "
                  f"{rate:.0f}s/pg  ETA {eta/60:.0f}m", flush=True)
        except Exception as e:
            print(f"[{i}/{total}] {pid}  ERROR: {e}", flush=True)
    print(f"\ndone: {processed} newly transcribed, "
          f"{total} total pages in scope", flush=True)

if __name__ == "__main__":
    lim = None
    if "--limit" in sys.argv:
        lim = int(sys.argv[sys.argv.index("--limit") + 1])
    main(lim)
