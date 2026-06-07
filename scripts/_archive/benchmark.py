#!/usr/bin/env python3
"""
benchmark.py — measure whether a pipeline component actually HELPS. The gate behind every
"keep using X?" decision (esp. kraken/McCATMuS for names). STATUS: spec stub.

Truth set: gold/benchmark/<slug>/<pid>.txt = human-checked transcriptions (names verified).
Build it by hand-correcting a representative >=10-page sample per register/hand.

Metrics (computed per page, then aggregated):
  - CER / WER  (overall character / word error rate vs gold)
  - NAME accuracy: precision/recall on proper-name tokens (capitalised surnames/places/people
    from registers/<slug>/context.md) — THIS is the metric kraken must move.
  - hallucination rate: tokens in output absent from gold (esp. on sparse pages)
  - lacuna honesty: are [?]/[...] placed where gold shows the text is genuinely hard?

Comparisons it must support:
  A) gemini-only reconcile          (current default)
  B) gemini + kraken name-vote      (the McCATMuS hypothesis)
  C) N=3 vs N=5 samples             (is "hard" mode worth it?)
  D) page-level vs Tier-2 line-level (is deep mode worth it, and where?)

Output: a table + a verdict line written to HANDOVER and config (e.g. kraken.benchmark_result).
Rule: a component stays in the pipeline ONLY if it wins on its target metric without regressing
others. Measure, don't assume.
"""
import sys
if __name__ == "__main__":
    sys.exit("benchmark.py is a spec stub — needs gold/benchmark/<slug>/ truth set first.")
