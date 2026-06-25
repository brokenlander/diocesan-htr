#!/usr/bin/env python3
"""
gemini_htr.py — ironclad, repeatable HTR pipeline for the diocesan archive.

ONE model only: Gemini 3.x Pro (see pipeline/config.json). NEVER 2.5, NEVER Flash.

Gemini does the heavy lifting; Claude (the in-session agent) is the final image gate.

  sample      N diversified diplomatic reads per page (default N=1, temp>0)   -> candidates/<pid>.sN.json
  agree       pure-Python aggregation of the N candidate(s) into meta/ (NO API call) -> meta/<pid>.json
  run         sample + agree; resumable — SKIPS any page that already has a Claude-written
              final reconciled/<pid>.txt, so it never re-reads (or re-bills) a finished page
  reconcile   OPTIONAL/LEGACY: one Gemini image-grounded reconcile of the candidates; spends
              1 extra Gemini call/page; NOT in the default path                -> draft/ + meta/
  status      progress per register

The CLAUDE VERIFY step is NOT in this script (it is the in-session adjudication):
  read the IMAGE + candidates/<pid>.s1.json + meta/<pid>.json(flags) + registers/<slug>/context.md
  -> fix names/numbers via cross-page knowledge, confirm blanks, finalise
  -> write reconciled/<pid>.txt  (this FINAL is what `run` checks to skip an already-done page).

Usage:
  PYTHONPATH=scripts .venv/bin/python3 pipeline/gemini_htr.py run x-4-1574
  PYTHONPATH=scripts .venv/bin/python3 pipeline/gemini_htr.py run p209 p210 --hard
  PYTHONPATH=scripts .venv/bin/python3 pipeline/gemini_htr.py status x-4-1574
"""
import sys, os, json, time, base64, difflib, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import paths  # page_slug(pid), cropped(pid)

CFG = json.loads((ROOT / "pipeline" / "config.json").read_text())
MODEL = CFG["model"]
KEY = Path(os.path.expanduser(CFG["key_file"])).read_text().strip()
API = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}"

# ---------------------------------------------------------------- prompts
SYSTEM = """You are an expert palaeographer producing a DIPLOMATIC transcription of a
manuscript page from a Lombard parish/diocesan archive (parish of Gerenzano, Pieve d'Appiano,
diocese of Milan). The material spans c. 1430-1850 (late-medieval notarial Latin, early-modern
Lombard-clerical Italian, and 19th-century administrative Italian). The hands are hard cursive;
identify the period/language of THIS page from the script and content, and transcribe accordingly.

ABSOLUTE RULES (a wrong guess is worse than an honest gap):
- Transcribe ONLY what is actually written. Never invent, complete, or "improve" text.
- Preserve the scribe's spelling, abbreviations and word forms verbatim (do NOT modernise).
  Keep the abbreviation marks; you MAY expand inside [square brackets], e.g. p[er], q[uon]d[am].
- One uncertain WORD -> append [?]. An illegible RUN -> [...]. Never fill these with a guess.
- Omit text the scribe struck through (mention it in `notes`, do not put it in `lines`).
- Marginalia, headers in another hand, folio numbers and notarial stamps -> `notes`, not `lines`.
- BLANK/SPARSE-PAGE GUARD: if the page is blank or has only a few words (a label, a folio number),
  set page_state accordingly and transcribe ONLY those few real words. NEVER hallucinate a full
  page onto a sparse page. Bleed-through from the facing leaf is NOT text.
- Use the CONTEXT glossary to resolve hard proper names/places/formulae, but ONLY when the pixels
  support it. The image ALWAYS wins over the glossary.
Return STRICT JSON for the given schema. Put transcription text in NO field but `lines[].text`."""

SAMPLE_FRAMINGS = [
    "Transcribe every line, top to bottom, exactly as written.",
    "Transcribe the page, paying special attention to PROPER NAMES, PLACES and NUMBERS; mark any you are unsure of with [?].",
    "Transcribe the page, paying special attention to ABBREVIATIONS and line-final hyphenation; preserve them faithfully.",
    "Transcribe the page line by line; for any word you cannot read with confidence use [?] and for illegible runs use [...].",
    "Transcribe the page conservatively: when in doubt prefer [?] over a guess; report layout/marginalia in notes.",
]

LINE_ITEM = {"type": "OBJECT", "properties": {
    "text": {"type": "STRING"},
    "confidence": {"type": "STRING", "enum": ["high", "medium", "low"]},
}, "required": ["text", "confidence"]}

SAMPLE_SCHEMA = {"type": "OBJECT", "properties": {
    "page_state": {"type": "STRING", "enum": ["full", "sparse", "blank"]},
    "language": {"type": "STRING"},
    "lines": {"type": "ARRAY", "items": LINE_ITEM},
    "notes": {"type": "STRING"},
}, "required": ["page_state", "lines", "notes"]}

# RECON_LINE / RECON_SCHEMA: used ONLY by the legacy reconcile() escape hatch, not the v2.1 default path.
RECON_LINE = {"type": "OBJECT", "properties": {
    "text": {"type": "STRING"},
    "confidence": {"type": "STRING", "enum": ["high", "medium", "low"]},
    "agreement": {"type": "STRING", "enum": ["all", "majority", "split"]},
}, "required": ["text", "confidence", "agreement"]}

RECON_SCHEMA = {"type": "OBJECT", "properties": {
    "page_state": {"type": "STRING", "enum": ["full", "sparse", "blank"]},
    "language": {"type": "STRING"},
    "lines": {"type": "ARRAY", "items": RECON_LINE},
    "disagreement_loci": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "line_index": {"type": "INTEGER"},
        "variants": {"type": "ARRAY", "items": {"type": "STRING"}},
        "chosen": {"type": "STRING"},
        "reason": {"type": "STRING"},
    }, "required": ["line_index", "variants", "chosen"]}},
    "notes": {"type": "STRING"},
}, "required": ["page_state", "lines", "disagreement_loci", "notes"]}

# ---------------------------------------------------------------- paths
def slug_of(pid): return paths.page_slug(pid)

def cropped_path(pid):
    try:
        p = Path(paths.cropped(pid))
        if p.exists(): return p
    except Exception:
        pass
    return ROOT / "processed" / "cropped" / slug_of(pid) / f"{pid}.jpg"

def tdir(pid):
    d = ROOT / "processed" / "transcriptions" / slug_of(pid)
    for sub in ("candidates", "meta", "reconciled"):  # 'draft' is created on demand by legacy reconcile()
        (d / sub).mkdir(parents=True, exist_ok=True)
    return d

def context_for(pid):
    f = ROOT / CFG["context_dir"] / slug_of(pid) / "context.md"
    return f.read_text() if f.exists() else ""

# ---------------------------------------------------------------- gemini
class QuotaExhausted(Exception):
    """A quota condition that won't clear by retrying (per-DAY cap, or any 429 that survives every
    retry: sticky per-minute cap, depleted credits, unrecognised quotaId) → autostop the run
    cleanly so the watchdog relaunches it later, instead of churning the register in dead backoff."""
    pass

class BlockedResponse(Exception):
    """A deterministic non-answer (prompt/safety block, empty candidates, finishReason != STOP,
    MAX_TOKENS). Retrying cannot help — fail this page fast instead of burning the retry budget."""
    pass

def call_gemini(parts, schema, temperature, max_tokens=None):
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens or CFG["max_output_tokens"],
            "responseMimeType": "application/json",
            "responseSchema": schema,
        },
    }
    if MODEL.startswith("gemini-3"):
        body["generationConfig"]["thinkingConfig"] = {"thinkingLevel": CFG["thinking_level"]}
    url = API.format(m=MODEL, k=KEY)
    data = json.dumps(body).encode()
    last = None
    for attempt in range(CFG["retries"]):
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=CFG["request_timeout_s"]) as r:
                resp = json.loads(r.read())
            cands = resp.get("candidates") or []
            if not cands:
                raise BlockedResponse(f"no candidates (promptFeedback={resp.get('promptFeedback')})")
            cand = cands[0]
            fr = cand.get("finishReason")
            if fr not in (None, "STOP"):
                raise BlockedResponse(f"finishReason={fr}")  # SAFETY/RECITATION/MAX_TOKENS → don't retry
            txt = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
            out = json.loads(txt)
            time.sleep(CFG.get("pace_seconds", 0))  # self-throttle to stay under RPM
            return out
        except BlockedResponse:
            raise  # deterministic non-answer — surface to caller, never retry
        except urllib.error.HTTPError as e:
            errbody = e.read().decode()
            last = f"HTTP {e.code}: {errbody[:300]}"
            if e.code == 429 and ("per_day" in errbody or "PerDay" in errbody or "per_model_per_day" in errbody):
                raise QuotaExhausted(last)  # daily cap → autostop cleanly (don't spin through every page)
            if e.code in (429, 500, 502, 503) and attempt < CFG["retries"] - 1:
                wait = min(CFG.get("rate_limit_max_wait_s", 300), 30 * (2 ** attempt)) if e.code == 429 \
                    else 5 * (attempt + 1)
                print(f"     {e.code}; backoff {wait}s"); time.sleep(wait); continue
            if e.code == 429:
                # a 429 that never cleared across all retries (sticky per-minute cap, depleted credits,
                # or an unrecognised quotaId): autostop cleanly rather than churn the rest of the register
                # in ~12 min of dead backoff each. The hourly watchdog relaunches when the window frees.
                raise QuotaExhausted(last)
            raise RuntimeError(last)
        except Exception as e:
            last = str(e)
            if attempt < CFG["retries"] - 1:
                time.sleep(5 * (attempt + 1)); continue
            raise RuntimeError(last)

def img_part(pid):
    b = base64.b64encode(cropped_path(pid).read_bytes()).decode()
    return {"inline_data": {"mime_type": "image/jpeg", "data": b}}

# ---------------------------------------------------------------- stages
def sample(pid, n, force=False):
    d = tdir(pid); ctx = context_for(pid); ip = img_part(pid)
    for i in range(1, n + 1):
        out = d / "candidates" / f"{pid}.s{i}.json"
        if out.exists() and not force:
            continue
        framing = SAMPLE_FRAMINGS[(i - 1) % len(SAMPLE_FRAMINGS)]
        prompt = f"CONTEXT for this register (resolve hard reads with it; image wins):\n{ctx}\n\nTASK: {framing}"
        res = call_gemini([ip, {"text": prompt}], SAMPLE_SCHEMA, CFG["sample_temperature"])
        res["_framing"] = framing
        out.write_text(json.dumps(res, ensure_ascii=False, indent=1))
        print(f"  sample {pid} s{i} [{res.get('page_state')}, {len(res.get('lines',[]))} lines]")

def _cand_text(c):
    return "\n".join(l["text"] for l in c.get("lines", []))

def reconcile(pid, force=False):
    # LEGACY / OPTIONAL escape hatch: spends 1 extra Gemini call/page to have GEMINI reconcile the
    # candidates. NOT part of the v2.1 default path (run = sample + agree; CLAUDE is the reconciler).
    print("  [legacy] reconcile(): spends 1 Gemini call/page — not the v2.1 default (Claude reconciles vs image).")
    d = tdir(pid)
    (d / "draft").mkdir(parents=True, exist_ok=True)
    draft_f = d / "draft" / f"{pid}.txt"
    meta_f = d / "meta" / f"{pid}.json"
    if draft_f.exists() and meta_f.exists() and not force:
        old = json.loads(meta_f.read_text())
        if old.get("pipeline_version") == CFG["pipeline_version"]:
            return
    cands = sorted((d / "candidates").glob(f"{pid}.s*.json"))
    if not cands:
        raise RuntimeError(f"no candidates for {pid} — run sample first")
    cand_objs = [json.loads(c.read_text()) for c in cands]
    block = "\n\n".join(f"--- CANDIDATE {i+1} (page_state={c.get('page_state')}) ---\n{_cand_text(c)}"
                        for i, c in enumerate(cand_objs))
    ctx = context_for(pid)
    prompt = (f"CONTEXT for this register:\n{ctx}\n\n"
              f"You are given {len(cand_objs)} independent transcriptions of THIS SAME page, by "
              f"different reads. Produce the SINGLE BEST diplomatic transcription, DEFERRING TO THE "
              f"IMAGE at every point. Where candidates differ, choose what the pixels support; if it "
              f"cannot be resolved, use [?] (word) or [...] (run) rather than guessing. Mark each "
              f"line's agreement (all/majority/split) and list the disagreement loci. Apply the same "
              f"blank/sparse-page guard: do not invent text on a sparse page.\n\nCANDIDATES:\n{block}")
    res = call_gemini([img_part(pid), {"text": prompt}], RECON_SCHEMA, CFG["reconcile_temperature"])

    draft_text = "\n".join(l["text"] for l in res.get("lines", []))
    # programmatic agreement: mean similarity of the reconciled draft vs each candidate
    sims = [difflib.SequenceMatcher(None, draft_text, _cand_text(c)).ratio() for c in cand_objs]
    agreement = round(sum(sims) / len(sims), 3) if sims else 0.0
    low_conf = sum(1 for l in res.get("lines", []) if l.get("confidence") == "low")
    flags = []
    if res.get("page_state") != "full": flags.append(f"page_state={res.get('page_state')}")
    if agreement < CFG["agreement_review_threshold"]: flags.append(f"low_agreement={agreement}")
    if res.get("disagreement_loci"): flags.append(f"disagreement_loci={len(res['disagreement_loci'])}")
    if low_conf: flags.append(f"low_conf_lines={low_conf}")

    draft_f.write_text(draft_text + ("\n" if draft_text else ""))
    meta = {
        "pid": pid, "slug": slug_of(pid),
        "pipeline_version": CFG["pipeline_version"], "prompt_version": CFG["prompt_version"],
        "model": MODEL, "n_samples": len(cand_objs),
        "sample_temperature": CFG["sample_temperature"], "reconcile_temperature": CFG["reconcile_temperature"],
        "thinking_level": CFG["thinking_level"], "stage": "gemini-reconciled-draft",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "page_state": res.get("page_state"), "language": res.get("language"),
        "page_agreement": agreement, "candidate_similarities": [round(s, 3) for s in sims],
        "review_recommended": bool(flags), "flags": flags,
        "lines": res.get("lines", []), "disagreement_loci": res.get("disagreement_loci", []),
        "notes": res.get("notes", ""),
        "verify": None,  # Claude fills: {"date":..,"changes":[..],"final_confidence":..}
    }
    meta_f.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    tag = "REVIEW" if flags else "clean"
    print(f"  reconcile {pid} [{tag}] agreement={agreement} {' '.join(flags)}")

def agree(pid, force=False):
    """Pure-Python, NO API: aggregate the N samples into meta/ for the CLAUDE reconcile step.
    Reconciler = Claude (in-session), reading candidates/ + image. Gemini reconcile is dropped
    from the default path (saves 1 call/page) and kept only as the optional `reconcile` command."""
    d = tdir(pid)
    meta_f = d / "meta" / f"{pid}.json"
    if meta_f.exists() and not force:
        old = json.loads(meta_f.read_text())
        if old.get("pipeline_version") == CFG["pipeline_version"] and str(old.get("stage", "")).startswith("awaiting"):
            return
    cands = sorted((d / "candidates").glob(f"{pid}.s*.json"))
    if not cands:
        raise RuntimeError(f"no candidates for {pid} — run sample first")
    objs = [json.loads(c.read_text()) for c in cands]
    texts = [_cand_text(o) for o in objs]
    pairs = [(i, j) for i in range(len(texts)) for j in range(i + 1, len(texts))]
    sims = [difflib.SequenceMatcher(None, texts[i], texts[j]).ratio() for i, j in pairs]
    agreement = round(sum(sims) / len(sims), 3) if sims else 1.0
    states = [o.get("page_state") for o in objs]
    page_state = max(set(states), key=states.count) if states else None
    flags = []
    if page_state != "full": flags.append(f"page_state={page_state}")
    if agreement < CFG["agreement_review_threshold"]: flags.append(f"inter_sample_agreement={agreement}")
    if len(set(states)) > 1: flags.append("page_state_disagreement")
    meta = {
        "pid": pid, "slug": slug_of(pid),
        "pipeline_version": CFG["pipeline_version"], "prompt_version": CFG["prompt_version"],
        "model": MODEL, "reconciler": "claude", "n_samples": len(objs),
        "sample_temperature": CFG["sample_temperature"], "thinking_level": CFG["thinking_level"],
        "stage": "awaiting-claude-reconcile", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "page_state": page_state, "inter_sample_agreement": agreement,
        "candidate_files": [c.name for c in cands],
        "review_recommended": bool(flags), "flags": flags,
        "sample_notes": [o.get("notes", "") for o in objs],
        "verify": None,  # Claude fills after reconciling candidates+image -> reconciled/<pid>.txt
    }
    meta_f.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"  agree {pid} [{'REVIEW' if flags else 'clean'}] inter_sample={agreement} {' '.join(flags)}")

def run(pid, hard=False, force=False):
    # DEFAULT path: Gemini SAMPLES only; CLAUDE reconciles from candidates+image (no Gemini reconcile call).
    # Skip pages that ALREADY have a Claude-reconciled final — otherwise the sampler re-reads (and re-bills)
    # the ~235 pages finalized in the v1 era that never got a v2 candidate marker, burning the daily quota
    # on finished work before it ever reaches the genuinely-undone pages.
    final = tdir(pid) / "reconciled" / f"{pid}.txt"
    if final.exists() and not force:
        return
    sample(pid, CFG["n_samples_hard"] if hard else CFG["n_samples"], force=force)
    agree(pid, force=force)

# ---------------------------------------------------------------- cli
def expand(args):
    out = []
    croot = ROOT / "processed" / "cropped"
    for a in args:
        if (croot / a).is_dir():
            out += sorted(p.stem for p in (croot / a).glob("*.jpg"))
        else:
            out.append(a)
    return out

def status(args):
    croot = ROOT / "processed" / "cropped"
    slugs = [a for a in args if (croot / a).is_dir()] or sorted(p.name for p in croot.iterdir() if p.is_dir())
    for s in slugs:
        total = len(list((croot / s).glob("*.jpg")))
        t = ROOT / "processed" / "transcriptions" / s
        meta = len(list((t / "meta").glob("*.json"))) if (t / "meta").exists() else 0
        final = len(list((t / "reconciled").glob("*.txt"))) if (t / "reconciled").exists() else 0
        print(f"{s:16} cropped={total:4}  agreed/awaiting-claude={meta:4}  reconciled(final)={final:4}")

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    rest = [a for a in sys.argv[2:] if not a.startswith("--")]
    hard = "--hard" in sys.argv; force = "--force" in sys.argv
    if cmd == "status":
        status(rest); return
    pids = expand(rest)
    if not pids:
        print("no pids/slug given"); sys.exit(1)
    fn = {"sample": lambda p: sample(p, CFG["n_samples_hard"] if hard else CFG["n_samples"], force),
          "agree": lambda p: agree(p, force),
          "reconcile": lambda p: reconcile(p, force),  # optional Gemini reconcile (legacy/unattended)
          "run": lambda p: run(p, hard, force)}.get(cmd)
    if not fn:
        print(f"unknown cmd {cmd}"); sys.exit(1)
    for pid in pids:
        try:
            print(f"[{cmd}] {pid}")
            fn(pid)
        except QuotaExhausted as e:
            print(f"[AUTOSTOP] daily Gemini quota exhausted at {pid} — stopping cleanly; "
                  f"relaunch after the window resets to resume. ({e})")
            sys.exit(0)
        except Exception as e:
            print(f"  !! {pid}: {e}")
            # surface deterministically-failing pages so they aren't silently re-attempted (and re-billed)
            # forever; the human/Claude verify step picks them up from the review queue.
            try:
                with (ROOT / "processed" / "transcriptions" / "_REVIEW_QUEUE.txt").open("a") as fh:
                    fh.write(f"{pid}\t[sampler-error] {e}\n")
            except Exception:
                pass

if __name__ == "__main__":
    main()
