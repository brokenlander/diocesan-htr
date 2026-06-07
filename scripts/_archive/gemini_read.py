#!/usr/bin/env python3
"""Send page images to Gemini as an independent second READER (image-grounded).

Output is a candidate Claude adjudicates against the image + gold — NEVER auto-trusted.
Reads key from ~/.config/gemini.key. Writes one <pid>.txt per page under the given outdir
(default gold/models/gemini/), plus echoes to stdout.

Usage: python scripts/gemini_read.py [--model M] [--out DIR] p202 p122 ...
"""
import sys, os, json, base64, urllib.request
import paths

KEY = open(os.path.expanduser("~/.config/gemini.key")).read().strip()

SYSTEM = (
    "You are a diplomatic transcriber of early-modern (1570s-1680s) Italian diocesan "
    "manuscripts (parish registers and ecclesiastical decrees, Como/Milan area). The hand "
    "is hard early-modern cursive; the language is Latin and/or early-modern Lombard Italian. "
    "You transcribe ONLY what is on the page, grounded in the pixels."
)

# Context the model should USE the way a human paleographer would — to disambiguate, not
# to invent. Recurring proper nouns directly fight name-hallucination (e.g. Fagnani, not
# 'Zagnari'). CAUTION baked in: prefer a known name ONLY when the pixels are ambiguous;
# never force an unclear word to match — an honest [?] beats a confident wrong guess.
SHARED_CTX = (
    "ARCHIVE CONTEXT (use to disambiguate, never to force a reading):\n"
    "- Recurring SURNAMES (prefer when a surname is ambiguous, else [?]): Fagnani, "
    "Gibelli / de Gibellis, Crivelli / Crivello, Seraphini / Serafini, Vicecomes (Visconti), "
    "Carcano, Bonelli.\n"
    "- Recurring PLACES: Gerenzano (the parish; Latinised 'Gerensadii' / 'Gerensade'), "
    "Olgiate, Busto Arsizio ('Busti Arsicii'), Milano, Como, Saronno.\n"
    "- Period archbishop of Milan: Melchiorre Crivelli ('Melchior Criuello').\n"
    "- Money/measures: soldi (sol.), denari, modii (mod.), misure, pertiche (pert.), tavole (tab.).\n"
)
REG_CTX = {
    "x-4-1574":
        "DOCUMENT: parish benefice / tithe (decime) and land register for Gerenzano, with "
        "ordination records. Stock formulae: 'Et più possia una terra detta ...', "
        "'coherenzia de due parte Strada, dall'altra ...', 'fui promosso all'ordine ...'.",
    "x-18-1570-79":
        "DOCUMENT: includes status-animarum HOUSEHOLD LISTS. Stock formulae: 'Nella casa "
        "del[li] ...', 'Nella istessa casa habitano', '<name> sua moglie / sua figlia / suo "
        "figlio d'età d'anni <N>'. Ages sit in a right-hand margin column (often omit from the line).",
    "x-20-1583":
        "DOCUMENT: Latin benefice/tithe decrees + property bounds for Gerenzano. Stock: "
        "'pecia una terrae perticarum ...', 'cui coheret ab una parte ... ab alia ...', "
        "'Praepositura Gerensadii', 'solvere tenetur singulis annis', chapel-fabric decrees.",
    "x-44-1583":
        "DOCUMENT: Latin property register + benefice obligations. Stock: 'Pecia (una/alia) "
        "campi, ubi dicitur ...', 'cui coheret ...', 'solvit quot annis dictae Praepositurae "
        "solidos ...', 'absque aliquo onere suo'.",
    "x-5-1642-74":
        "DOCUMENT: Latin episcopal/synodal VISITATION decrees. Stock: 'Servetur Decretum "
        "Synodi Dioecesanae', 'Perficiatur ...', chapel furnishings, masses, processions.",
    "turate":
        "DOCUMENT: Stato delle anime (status animarum / census of souls), 1679, Italian. "
        "Households: 'Nella casa di ...', head then 'sua moglie', 'figlio/a ... d'età d'anni <N>'.",
}

def context_for(pid):
    return SHARED_CTX + "\n" + REG_CTX.get(paths.page_slug(pid), "")
RULES = (
    "Transcribe the MAIN TEXT BODY of this page, one output line per line of writing.\n"
    "RULES:\n"
    "1. Diplomatic: keep the scribe's abbreviations exactly as written (do NOT expand them).\n"
    "2. Uncertain word -> append [?] to it. Illegible run -> [...]. Never guess a name or "
    "number to make it read smoothly; an honest [?] is required and valued.\n"
    "3. Silently OMIT struck-through / crossed-out text. Do NOT describe or mention deletions.\n"
    "4. Ignore marginal notes and folio numbers; transcribe only the main text column.\n"
    "5. OUTPUT FORMAT: the transcription ONLY. No preamble, no commentary, no reasoning, "
    "no notes, no translation, no markdown. Just the transcribed lines, nothing else."
)

def read_page(pid, model):
    b64 = base64.b64encode(open(paths.cropped(pid), "rb").read()).decode()
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"parts": [
            {"text": context_for(pid)},
            {"text": RULES},
            {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
        ]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 8192,
        },
    }
    if model.startswith("gemini-3"):  # thinkingLevel is a Gemini-3-only param
        payload["generationConfig"]["thinkingConfig"] = {"thinkingLevel": "low"}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={KEY}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        resp = json.load(urllib.request.urlopen(req, timeout=180))
        cand = resp["candidates"][0]
        parts = cand.get("content", {}).get("parts", [])
        txt = "".join(p.get("text", "") for p in parts).strip()
        fin = cand.get("finishReason", "")
        if fin and fin != "STOP":
            txt += f"\n[finishReason={fin}]"
        return txt or f"[EMPTY resp: {json.dumps(resp)[:200]}]"
    except Exception as e:
        body = getattr(e, "read", lambda: b"")()
        return f"[ERROR: {e} {body[:200]}]"

def main(argv):
    model = "gemini-3.1-pro-preview"
    outdir = "gold/models/gemini"
    while argv and argv[0].startswith("--"):
        if argv[0] == "--model": model = argv[1]
        elif argv[0] == "--out": outdir = argv[1]
        argv = argv[2:]
    os.makedirs(outdir, exist_ok=True)
    force = "--force" in argv
    argv = [a for a in argv if a != "--force"]
    for pid in argv:
        dest = f"{outdir}/{pid}.txt"
        if not force and os.path.exists(dest):
            prev = open(dest).read()
            if "[ERROR" not in prev and "[EMPTY" not in prev and prev.strip():
                print(f"===== {pid} (cached) =====", flush=True); continue
        txt = read_page(pid, model)
        with open(f"{outdir}/{pid}.txt", "w", encoding="utf-8") as f:
            f.write(txt + "\n")
        print(f"===== {pid} ({model}) =====\n{txt}\n", flush=True)

if __name__ == "__main__":
    main(sys.argv[1:])
