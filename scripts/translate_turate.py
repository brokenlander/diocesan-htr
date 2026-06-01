#!/usr/bin/env python3
"""Modern-Italian normalization of the reconciled Turate Stato delle anime — an
interpretive edition: abbreviations expanded, spelling regularized, kept in Italian.
The register is highly formulaic, so a pattern-based pass renders it faithfully and
consistently. Surnames kept as written; uncertainty markers ([?], [...]) pass through.
DRAFT — mirrors the transcription's uncertainties; finalize after the gold is verified.

reconciled/<pid>.txt -> processed/translations/<pid>.txt + turate_italiano.txt
"""
import re, glob, os

RULES = [
    # formulaic openers / structure
    (r"Copia d\.?lo Stato d\.?lle anime di Tur[aà]\.?",
     "Copia dello Stato delle anime di Turate"),
    (r"et Cassine sotto poste a d\.?o luoco", "e le cassine annesse al detto luogo"),
    (r"\bAlli (\d+) d'agosto", r"Il \1 agosto"),
    (r"\bco tutta la sua fam[ig]?[il]+ia\b", "con tutta la sua famiglia"),
    # months (early-modern: 7bre=sett 8bre=ott 9bre=nov Xbre/10bre=dic)
    (r"\bd'?7bre\b", "settembre"), (r"\bd'?8bre\b", "ottobre"),
    (r"\bd'?9bre\b", "novembre"), (r"\bd'?(?:X|10)bre\b", "dicembre"),
    (r"\bgenar[oi]\b", "gennaio"), (r"\bgennar[oi]\b", "gennaio"),
    (r"\bfeb+ra?r[oi]\b", "febbraio"), (r"\bmag+i?o\b", "maggio"),
    (r"\bmarg[oi]\b", "marzo"), (r"\blug?clio\b", "luglio"),
    # dates
    (r"\bNat[ao]li\b", "nato il"), (r"\bNat[ao] ali\b", "nat\\g<0>"),  # placeholder; fixed below
    # relations / honorifics
    (r"\bpadre d[e'i ]*fam\w+", "padre di famiglia"),
    (r"\bpre d[e'i ]*fam\w+", "padre di famiglia"),
    (r"\bmadre d[e'i ]*fam\w+", "madre di famiglia"),
    (r"\bmoglie altre volte del q\.", "già moglie del fu"),
    (r"\bmoglie d'?(?:el|i) ?ditto\b", "moglie del detto"),
    (r"\bmoglie del detto\b", "moglie del detto"),
    (r"\bfratel+o del\b", "fratello del"),
    (r"\bsorel+a del+a?\b", "sorella della"), (r"\bsorel+a d'", "sorella di "),
    (r"\bcugnat([ao])\b", r"cognat\1"),
    (r"\bnora\b", "nuora"),
    (r"\bNepot[ae]\b", "nipote"),
    (r"\bdel q\.", "del fu"), (r"\bdel quondam\b", "del fu"),
    (r"\bd'?(?:el|i) ?ditt[oa]\b", "del detto"), (r"\bd\.?l ditto\b", "del detto"),
    (r"\bdel+a ditta\b", "della detta"), (r"\bdel+a detta\b", "della detta"),
    (r"\bsopra ?scritto\b", "soprascritto"),
    # forename / title expansions (surnames left alone)
    (r"\bGio(?:ane|an)?:?\s*", "Giovanni "),
    (r"\bAnt\.o\b", "Antonio"), (r"\bFran\.co\b", "Francesco"), (r"\bFran\.\b", "Francesco"),
    (r"\bBatta\b", "Battista"), (r"\bGieronimo\b", "Girolamo"), (r"\bAeronimo\b", "Girolamo"),
    (r"\bMadona\b", "Madonna"), (r"\bM\.o\b", "Messer"), (r"\bMo\b", "Messer"),
    (r"\bM\[esser\]\b", "Messer"), (r"\bM\[adona\]\b", "Madonna"), (r"\bM\[astro\]\b", "Mastro"),
    (r"\bfig\.?l?o\b|\bfiglo\b", "figlio"), (r"\bfig\.?a\b", "figlia"), (r"\bfig\.\b", "figlio/a"),
    (r"\bsuo fig\b", "suo figlio"), (r"\bsua fig\b", "sua figlia"),
]

def normalize(line):
    t = line
    t = re.sub(r"\bNat[ao] ali\b", "nato il", t, flags=re.IGNORECASE)
    t = re.sub(r"\bNat[ao] di\b", "nato il", t, flags=re.IGNORECASE)
    t = re.sub(r"\bnat([ao]) ali\b", r"nat\1 il", t, flags=re.IGNORECASE)
    for pat, repl in RULES:
        if "placeholder" in repl or "\\g<0>" in repl:
            continue
        t = re.sub(pat, repl, t, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", t).strip()

def main():
    os.makedirs("processed/translations", exist_ok=True)
    pages = sorted(glob.glob("processed/transcriptions/reconciled/p*.txt"),
                   key=lambda p: (len(os.path.basename(p)), p))
    combined = ["STATO DELLE ANIME DI TURATE — 1679  ·  EDIZIONE INTERPRETATIVA (italiano moderno)",
                "(normalizzazione automatica della trascrizione riconciliata; cognomi invariati; "
                "[?]=incerto [...]=illeggibile; provvisoria fino alla verifica)",
                "=" * 70, ""]
    for src in pages:
        pid = os.path.basename(src)[:-4]
        out = [normalize(l) for l in open(src).read().splitlines() if l.strip()]
        with open(f"processed/translations/{pid}.txt", "w") as f:
            f.write("\n".join(out) + "\n")
        combined.append(f"--- {pid} ---"); combined += out; combined.append("")
    open("processed/translations/turate_italiano.txt", "w").write("\n".join(combined))
    print(f"normalized {len(pages)} pages -> processed/translations/ (+ turate_italiano.txt)")

if __name__ == "__main__":
    main()
