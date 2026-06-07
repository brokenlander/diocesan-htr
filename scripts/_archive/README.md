# scripts/_archive — superseded tooling (kept for reference, not in any active path)

These scripts ran during the v1/v2/v3 **local fine-tune + ensemble** era. They are **not part of the
current v2.1 pipeline** (ONE Gemini-3.1-Pro read at `thinking=low` → Claude reconciles vs the image;
see `pipeline/gemini_htr.py` and `HANDOVER.md`). Archived 2026-06 when the local engines were benched.

**Why benched:** McCATMuS + TRIDIS (Kraken) score ~40–60% CER on the 2 MP phone-photo cursive that is
the whole remaining backlog — context-blind and noisy ("Alessandro Franco" → "A'estandre bra ner").
They add no usable signal to reconciliation. See `pipeline/config.json` → `kraken` block.

**Revive only if** fine-tuning becomes viable again (e.g. a GPU appears, or for the 12 MP Turate scans).

| group | files |
|---|---|
| Local-engine readers / batch | `transcribe_mccatmus.py`, `predict_v2.py`, `kraken_vote.py`, `segment.py` |
| Gold-correction (per-line) | `gold_prep.py`, `gold_finalize.py`, `gold_review.py`, `strip_montage.py`, `_fill_batch.py`, `_recon_batch.py` |
| Ensemble + fine-tune builders | `ensemble_pass.py`, `build_v3_gold.py`, `cluster_seed_build.py`, `x5_seed_build.py`, `x5_experiment.sh`, `bootstrap_harvest.py`, `v3_disagreement.py`, `benchmark.py` |
| Diagnostics (one-off) | `seg_inspect.py`, `detect_spreads.py`, `dedupe_audit.py` |
| Migrations / drafts (already run) | `reorg_by_register.py` (slug reorg, done), `translate_turate.py` (Turate-only translation draft) |
| v1 Gemini reader (superseded) | `gemini_read.py` — direct precursor of `pipeline/gemini_htr.py` |

The **active** keep-set lives in `scripts/`: `paths.py` (imported by the live pipeline),
`build_manifest.py`, `crop_pages.py` (the preprocessing spine).
