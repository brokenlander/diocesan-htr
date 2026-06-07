#!/usr/bin/env python3
"""
segment.py — Tier-2 deep mode: kraken `blla` baseline segmentation → per-line image crops.
STATUS: spec stub (not yet implemented). Build when a flagged page needs line-level reading.

Why: on dense 2 MP cursive, a tight LINE crop is read far more accurately by Gemini than the
whole page. Tier-2 = segment → transcribe each line-crop with N Gemini reads → reconcile per line
→ assemble. Used ONLY for pages the reconcile step flags (low agreement / sparse / name-dense).

Plan:
  in : processed/cropped/<slug>/<pid>.jpg
  run: kraken -i <page> <out.json> segment -bl        # blla baselines (tested GOOD ENOUGH on
                                                       #  p001/p100/p350; misses tiny margin numbers)
  out: processed/segmented/<slug>/<pid>/line_XX.png   # one crop per baseline polygon
       processed/segmented/<slug>/<pid>/lines.json    # bbox + reading order
Notes: keep kraken pins (kraken==7.0.2, numpy<2.3, scipy==1.15.3). CPU only.
Then pipeline/gemini_htr.py (a future `run-lines` mode) reads each crop. Margin numbers that blla
misses stay the job of the full-page read + Claude.
"""
import sys
if __name__ == "__main__":
    sys.exit("segment.py is a spec stub — see docstring. Implement for Tier-2 deep mode.")
