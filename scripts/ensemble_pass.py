#!/usr/bin/env python3
"""Ensemble pass for Claude's reconciliation. For each page: segment ONCE, run
v2 + McCATMuS + TRIDIS on the SAME lines (aligned), extract line strips, and write
gold/<pid>/ensemble.tsv (line, v2, mccatmus, tridis, reconciled[=v2 prefill]) plus a
review.html showing the full page image + each line strip beside the 3 candidates and
an editable 'reconciled' box. Claude then fills `reconciled` per line using the image
+ cross-page context. Local only.

Usage: python scripts/ensemble_pass.py p001 p004a ...   (default: all Turate pages)
"""
import os, sys, csv, glob, html
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True
from kraken import blla
from kraken.lib import vgsl, segmentation
from kraken.tasks import RecognitionTaskModel
from kraken.configs import RecognitionInferenceConfig

SEG = os.path.join(os.path.dirname(blla.__file__), "blla.mlmodel")
V2 = sorted(glob.glob("gold/models/turate_v2/best_*.safetensors"))[-1]
MC = glob.glob(os.path.expanduser("~/.local/share/htrmopo/**/McCATMuS*.mlmodel"), recursive=True)[0]
TR = "models/Tridis_v2_Medieval_EarlyModern.mlmodel"

HEAD = """<!doctype html><meta charset=utf-8><title>{pid}</title>
<style>body{{font:14px system-ui;margin:1rem;max-width:1300px}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ccc;padding:3px 6px;vertical-align:top}}img.l{{height:42px}}
.c{{font-size:11px;color:#777;white-space:pre-wrap}}textarea{{width:300px;font:13px monospace}}
#pg{{max-width:48%;float:right;border:1px solid #aaa;margin-left:1rem}}</style>
<h2>{pid} — reconcile against image (v2 / McCATMuS / TRIDIS as candidates)</h2>
<img id=pg src="../../processed/cropped/{pid}.jpg">
<table><tr><th>#</th><th>strip</th><th>v2</th><th>McCATMuS</th><th>TRIDIS</th><th>reconciled</th></tr>
"""

def main(pids):
    seg_model = vgsl.TorchVGSLModel.load_model(SEG)
    cfg = RecognitionInferenceConfig()
    print("loading v2/McCATMuS/TRIDIS...", flush=True)
    eng = {"v2": RecognitionTaskModel.load_model(V2),
           "mc": RecognitionTaskModel.load_model(MC),
           "tr": RecognitionTaskModel.load_model(TR)}
    for pid in pids:
        src = f"processed/cropped/{pid}.jpg"
        if not os.path.exists(src):
            print(f"{pid}: missing"); continue
        im = Image.open(src).convert("RGB")
        seg = blla.segment(im, model=seg_model, device="cpu")
        preds = {k: list(m.predict(im=im, segmentation=seg, config=cfg)) for k, m in eng.items()}
        line_imgs = [li for li, _ in segmentation.extract_polygons(im, seg)]
        outdir = f"gold/{pid}"; linedir = f"{outdir}/lines"; os.makedirs(linedir, exist_ok=True)
        rows = []
        n = len(line_imgs)
        for i in range(n):
            lid = f"L{i+1:03d}"
            line_imgs[i].convert("RGB").save(f"{linedir}/{lid}.png")
            g = lambda k: (preds[k][i].prediction.strip() if i < len(preds[k]) else "")
            rows.append((lid, g("v2"), g("mc"), g("tr")))
        with open(f"{outdir}/ensemble.tsv", "w", newline="") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow(["line", "v2", "mccatmus", "tridis", "reconciled"])
            for lid, v2, mc, tr in rows:
                w.writerow([lid, v2, mc, tr, v2])      # prefill reconciled with v2
        e = lambda s: html.escape(s or "")
        parts = [HEAD.format(pid=pid)]
        for lid, v2, mc, tr in rows:
            parts.append(f'<tr><td>{lid}</td><td><img class=l src="lines/{lid}.png"></td>'
                         f'<td>{e(v2)}</td><td class=c>{e(mc)}</td><td class=c>{e(tr)}</td>'
                         f'<td><textarea rows=2>{e(v2)}</textarea></td></tr>')
        parts.append("</table>")
        open(f"{outdir}/review.html", "w").write("".join(parts))
        print(f"{pid}: {n} lines -> gold/{pid}/ensemble.tsv + review.html", flush=True)

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        args = [r["page_id"] for r in csv.DictReader(open("dataset/pages.csv"))
                if "Turate" in r["register"]]
    main(args)
