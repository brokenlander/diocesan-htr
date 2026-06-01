#!/usr/bin/env python3
"""Prepare per-line GOLD artifacts for the given pages.

Segments each cropped page ONCE, then runs McCATMuS and TRIDIS on the SAME lines
so their reads align row-for-row. Emits, per page, under gold/<pid>/:
  - <pid>.alto.xml   ALTO (line geometry + McCATMuS text) — the training skeleton
  - lines/L###.png   dewarped per-line image strips (for review)
  - correct.tsv      the editable correction sheet (line, mccatmus, tridis,
                     transkribus, correct) — `correct` is the authoritative column
  - review.html      side-by-side line image + candidates + editable field,
                     with an "Export corrected TSV" button

Workflow: gold_prep.py -> correct (edit correct.tsv, or review.html + export)
          -> gold_finalize.py  (injects corrected text into ALTO for ketos train)

Usage: python scripts/gold_prep.py p001 p002 ...
"""
import sys, os, glob, dataclasses, html
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True
from kraken import blla, rpred, serialization
from kraken.lib import models, vgsl, segmentation

SEG_MODEL = os.path.join(os.path.dirname(blla.__file__), "blla.mlmodel")
TRIDIS = "models/Tridis_v2_Medieval_EarlyModern.mlmodel"

def mccatmus_path():
    hits = glob.glob(os.path.expanduser("~/.local/share/htrmopo/**/McCATMuS*.mlmodel"),
                     recursive=True)
    if not hits:
        sys.exit("McCATMuS model not found")
    return hits[0]

HTML_HEAD = """<!doctype html><meta charset=utf-8><title>gold {pid}</title>
<style>
body{{font:14px/1.4 system-ui;margin:1.5rem;max-width:1100px}}
table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ccc;padding:4px 6px;vertical-align:top}}
img.line{{height:42px;image-rendering:auto}}
.cand{{color:#666;font-size:12px;white-space:pre-wrap}}
textarea{{width:100%;font:14px monospace;border:1px solid #bbb}}
button{{font:15px system-ui;padding:.5rem 1rem;margin:1rem 0}}
.ln{{color:#999;font-size:11px}}
</style>
<h2>Gold correction — {pid}</h2>
<p>Edit the <b>correct</b> column against the line image. Markers: <code>[?]</code> uncertain word,
<code>[…]</code> illegible, <code>[margin: …]</code> marginalia. Keep abbreviations as written
(diplomatic). When done, click Export and save over <code>correct.tsv</code>.</p>
<button onclick="exp()">Export corrected TSV</button>
<table><tr><th>#</th><th>line image</th><th>candidates (McCATMuS / TRIDIS)</th><th>correct</th></tr>
"""
HTML_TAIL = """</table>
<button onclick="exp()">Export corrected TSV</button>
<script>
function exp(){
 let rows=[['line','mccatmus','tridis','transkribus','correct'].join('\\t')];
 document.querySelectorAll('tr[data-line]').forEach(tr=>{
   const g=n=>tr.dataset[n]||'';
   const c=tr.querySelector('textarea').value.replace(/\\t/g,' ').replace(/\\n/g,' ');
   rows.push([g('line'),g('mc'),g('tr'),g('tk'),c].join('\\t'));
 });
 const b=new Blob([rows.join('\\n')+'\\n'],{type:'text/tab-separated-values'});
 const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='correct.tsv';a.click();
}
</script>
"""

def esc(s):
    return html.escape(s or "")

def write_html(outdir, pid, rows):
    parts = [HTML_HEAD.format(pid=pid)]
    for lid, mc, tr in rows:
        parts.append(
            f'<tr data-line="{lid}" data-mc="{esc(mc)}" data-tr="{esc(tr)}" data-tk="">'
            f'<td class=ln>{lid}</td>'
            f'<td><img class=line src="lines/{lid}.png"></td>'
            f'<td class=cand>MC: {esc(mc)}\nTR: {esc(tr)}</td>'
            f'<td><textarea rows=2>{esc(mc)}</textarea></td></tr>')
    parts.append(HTML_TAIL)
    with open(f"{outdir}/review.html", "w") as f:
        f.write("".join(parts))

def main(pids):
    seg_model = vgsl.TorchVGSLModel.load_model(SEG_MODEL)
    mc = models.load_any(mccatmus_path(), device="cpu")
    tr = models.load_any(TRIDIS, device="cpu")
    for pid in pids:
        src = f"processed/cropped/{pid}.jpg"
        if not os.path.exists(src):
            print(f"{pid}: no cropped image, skipping"); continue
        im = Image.open(src).convert("RGB")
        seg = blla.segment(im, model=seg_model, device="cpu")
        mc_preds = list(rpred.rpred(mc, im, seg))
        tr_preds = list(rpred.rpred(tr, im, seg))

        outdir = f"gold/{pid}"; linedir = f"{outdir}/lines"
        os.makedirs(linedir, exist_ok=True)

        # ALTO skeleton (line geometry + McCATMuS text)
        results = dataclasses.replace(seg, lines=mc_preds, imagename=f"{pid}.jpg")
        alto = serialization.serialize(results=results, image_size=im.size, template="alto")
        with open(f"{outdir}/{pid}.alto.xml", "w", encoding="utf-8") as f:
            f.write(alto)

        # per-line dewarped image strips + correction rows
        line_imgs = [li for li, _ in segmentation.extract_polygons(im, seg)]
        rows = []
        for i, lineimg in enumerate(line_imgs):
            lid = f"L{i+1:03d}"
            lineimg.convert("RGB").save(f"{linedir}/{lid}.png")
            mctxt = mc_preds[i].prediction if i < len(mc_preds) else ""
            trtxt = tr_preds[i].prediction if i < len(tr_preds) else ""
            rows.append((lid, mctxt, trtxt))

        with open(f"{outdir}/correct.tsv", "w", encoding="utf-8") as f:
            f.write("line\tmccatmus\ttridis\ttranskribus\tcorrect\n")
            for lid, mctxt, trtxt in rows:
                clean = lambda s: (s or "").replace("\t", " ")
                f.write(f"{lid}\t{clean(mctxt)}\t{clean(trtxt)}\t\t{clean(mctxt)}\n")

        write_html(outdir, pid, rows)
        print(f"{pid}: {len(rows)} lines -> {outdir}/ "
              f"(review.html, correct.tsv, {pid}.alto.xml, lines/)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: gold_prep.py p001 [p002 ...]")
    main(sys.argv[1:])
