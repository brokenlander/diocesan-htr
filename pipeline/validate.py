#!/usr/bin/env python3
"""
validate.py — structural lints over finalized transcriptions. Flags pages for re-review.
NOT a correctness oracle — it catches mechanical/structural anomalies only.

  PYTHONPATH=scripts .venv/bin/python3 pipeline/validate.py <slug|pids...>

Checks per page (on reconciled/<pid>.txt, falling back to legacy draft/<pid>.txt):
  - unbalanced [ ] brackets
  - a raw '?' that is not part of the '[?]' uncertainty marker (possible un-flagged guess)
  - census heuristic (ITALIAN status-animarum registers only — skipped for the Latin x-5/x-51):
    lines naming a person (figlio/figlia/moglie/...) should carry an age or an explicit [?]
  - meta.review_recommended flags
Note: at n_samples=1 (the v2.1 default) the agreement-based meta flags are inert — the Claude
verify step is the real review gate; these are structural lints only. Exits 0 always (advisory).
"""
import sys, json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import paths

# Census/age heuristics are tuned to the Italian status-animarum registers; meaningless for Latin decrees.
LATIN_SLUGS = {"x-5-1642-74", "x-51"}
REL = re.compile(r"\b(fig\.?l[oa]|figli?[oa]?|moglie|mogliera|mogliere|nepote|nipote|fr\.?ll?o|sorella|cognat[ao]|massaro|vedoua|vedova)\b", re.I)
# require a real age signal — a number or an explicit anni/età/mesi form (not a stray capital L / 'pt').
AGE = re.compile(r"(d'?\s*anni|d'?\s*et[aà]|di mesi|\bmesi\b|\banni\b|\bet[aà]\b|\d)")

def check(pid):
    slug = paths.page_slug(pid)
    t = ROOT / "processed" / "transcriptions" / slug
    f = t / "reconciled" / f"{pid}.txt"
    if not f.exists():
        f = t / "draft" / f"{pid}.txt"
    if not f.exists():
        return [f"{pid}: no draft/final"]
    text = f.read_text()
    issues = []
    if text.count("[") != text.count("]"):
        issues.append("unbalanced brackets")
    for m in re.finditer(r"\?", text):
        if text[max(0, m.start()-1):m.start()+1] != "[?":
            issues.append("raw '?' (un-flagged guess?)"); break
    for ln in text.splitlines():
        if REL.search(ln) and not AGE.search(ln) and "[?]" not in ln and "[...]" not in ln:
            issues.append(f"census line w/o age: {ln[:50]!r}")
            break
    meta = t / "meta" / f"{pid}.json"
    if meta.exists():
        m = json.loads(meta.read_text())
        if m.get("review_recommended"):
            issues.append("meta.review_recommended=" + ",".join(m.get("flags", [])))
    return [f"{pid}: {i}" for i in issues]

def expand(args):
    croot = ROOT / "processed" / "cropped"; out = []
    for a in args:
        out += sorted(p.stem for p in (croot / a).glob("*.jpg")) if (croot / a).is_dir() else [a]
    return out

if __name__ == "__main__":
    flagged = 0
    for pid in expand(sys.argv[1:]):
        for line in check(pid):
            print(line); flagged += 1
    print(f"--- {flagged} flag(s) ---")
