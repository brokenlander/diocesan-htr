#!/usr/bin/env python3
"""Regenerate gold/<pid>/review.html from correct.tsv: each line's image strip
beside the McCATMuS/TRIDIS candidates and the editable `correct` draft, with an
Export button to download the corrected TSV. Run after editing correct.tsv.

Usage: python scripts/gold_review.py p001 p002a ...   (default: all gold/ pages)
"""
import sys, os, csv, glob, html

HEAD = """<!doctype html><meta charset=utf-8><title>gold {pid}</title>
<style>body{{font:14px system-ui;margin:1.2rem}}table{{border-collapse:collapse}}
td,th{{border:1px solid #ccc;padding:4px 6px;vertical-align:top}}img{{height:46px}}
.c{{color:#888;font-size:11px;white-space:pre-wrap}}textarea{{width:360px;font:14px monospace}}
.sk textarea{{color:#bbb}}</style>
<h2>{pid} — verify draft against each line image</h2>
<p>Fix the <b>correct</b> box where wrong (esp. names/ages/dates). <code>[?]</code>=uncertain,
<code>[…]</code>=illegible, <code>[skip]</code>=not a real text line. Diplomatic: keep d.l, fig.o, q., 8bre.
Then <button onclick="exp()">Export corrected TSV</button> and save over correct.tsv.</p>
<table><tr><th>#</th><th>line image</th><th>McCATMuS / TRIDIS</th><th>correct (draft)</th></tr>
"""
TAIL = """</table>
<script>
function exp(){
 let out=[['line','mccatmus','tridis','transkribus','correct'].join('\\t')];
 document.querySelectorAll('tr[data-line]').forEach(tr=>{
   const g=n=>tr.dataset[n]||'';
   const c=tr.querySelector('textarea').value.replace(/[\\t\\n]/g,' ');
   out.push([g('line'),g('mc'),g('tr'),g('tk'),c].join('\\t'));
 });
 const b=new Blob([out.join('\\n')+'\\n'],{type:'text/tab-separated-values'});
 const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='correct.tsv';a.click();
}
</script>"""

def regen(pid):
    tsv = f"gold/{pid}/correct.tsv"
    if not os.path.exists(tsv):
        print(f"{pid}: no correct.tsv"); return
    rows = list(csv.DictReader(open(tsv), delimiter="\t"))
    e = lambda s: html.escape(s or "")
    parts = [HEAD.format(pid=pid)]
    for r in rows:
        cor = r.get("correct", "")
        cls = " class=sk" if cor == "[skip]" else ""
        parts.append(
            f'<tr data-line="{r["line"]}" data-mc="{e(r["mccatmus"])}" '
            f'data-tr="{e(r["tridis"])}" data-tk="{e(r.get("transkribus",""))}">'
            f'<td>{r["line"]}</td><td><img src="lines/{r["line"]}.png"></td>'
            f'<td class=c>MC: {e(r["mccatmus"])}\nTR: {e(r["tridis"])}</td>'
            f'<td{cls}><textarea rows=2>{e(cor)}</textarea></td></tr>')
    parts.append(TAIL)
    open(f"gold/{pid}/review.html", "w").write("".join(parts))
    print(f"{pid}: review.html regenerated ({len(rows)} lines)")

if __name__ == "__main__":
    pids = sys.argv[1:] or [os.path.basename(os.path.dirname(p))
                            for p in glob.glob("gold/*/correct.tsv")]
    for pid in sorted(pids):
        regen(pid)
