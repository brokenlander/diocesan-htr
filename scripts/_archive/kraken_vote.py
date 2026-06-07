#!/usr/bin/env python3
"""
kraken_vote.py — GATED proper-name vote from local kraken models (McCATMuS + TRIDIS v2).
STATUS: spec stub, DISABLED. Do NOT wire into the pipeline until benchmark.py proves it helps.

Rationale (user directive 2026-06-02 "keep using McCATMuS for names — but make sure it is useful!"):
kraken is context-blind (~0.77 CER ceiling on 2 MP) and its CRNN errors correlate, so it must NOT
be a general reader or a vote-count padder. The ONLY hypothesis worth testing is narrow:

    "At a disagreement locus that is a PROPER NAME, does an independent kraken read of that
     line-crop break the tie better than Gemini self-consistency alone?"

Gate (config.json kraken.enabled flips to true ONLY when this passes):
  1. Build gold/benchmark/<slug>/ (>=10 human-checked pages, names verified).
  2. benchmark.py compares, on those pages, proper-name accuracy of:
        A) Gemini-only reconcile
        B) Gemini reconcile + kraken name-vote at disagreement loci
     Promote kraken ONLY if B beats A on names by a real margin (and doesn't hurt elsewhere).
  3. Record the verdict in HANDOVER + config.kraken.benchmark_result.

Mechanics (when built): segment.py line-crops → run each crop through:
  MODEL=$(find ~/.local/share/htrmopo -name 'McCATMuS*.mlmodel' | head -1)
  kraken -i <line.png> <out.txt> segment -bl ocr -m "$MODEL"          # + models/Tridis_v2…mlmodel
→ emit per-line candidate strings to processed/transcriptions/<slug>/kraken/<pid>.json, to be
  offered to the reconciler ONLY for name-token disambiguation.
"""
import sys
if __name__ == "__main__":
    sys.exit("kraken_vote.py is a GATED spec stub — prove value via benchmark.py first.")
