#!/usr/bin/env python3
"""One-off: write Claude's reconciled draft into the `correct` column of the
4 validation pages. [?]=uncertain token, [...]/[…]=illegible, [skip]=seg fragment
(not a real text line). Diplomatic: abbreviations kept (d.l, fig.o, q., 8bre)."""
import csv

DRAFTS = {
"p002a": {
 "L001":"Pietro de gusti[?] [...] padre d'famiglia",
 "L002":"Antonia[?] moglie del ditto",
 "L003":"[skip]","L004":"[skip]","L005":"[skip]","L006":"[skip]",
 "L007":"[…] fig. del ditto, Natali [?] d'gennaro 156[?]",
 "L008":"[…] del ditto, nata ali 13[?] di marzo 1563",
 "L009":"[…] del ditto, nata ali [?] di maggio 1577",
 "L010":"[Bernardino?] Montegabio[?] detto [...] di [...] Pietro",
 "L011":"Lucia[?] moglie del ditto",
 "L012":"Galeazzo[?] fig. del ditto, nato ali 8 febraro 1565",
 "L013":"Paulina fig. del ditto, nata ali 19 giugno 1569",
 "L014":"Madalena fig. del ditto, nata ali 6 maggio 1572",
 "L015":"Caterina[?] fig. del ditto, nata ali 12 de agosto 1574",
 "L016":"Ursina fig. del ditto, nata ali 8 d'8bre 1576",
 "L017":"Antonia fig. del ditto, nata ali [?] d'febraro 1578",
 "L018":"Fran.co d'clerici del Bertino",
 "L019":"Lucia Nepote del ditto e fig.a del q. Pietro Bertino",
 "L020":"Gioane Nepote e fig.o del q. Pietro, nato ali [?] 156[?]",
 "L021":"Ursula Nepote e fig.a del q. Gio: Angelo Bertino, nata ali 15 d'8bre [?]",
 "L022":"Antonia Nepote e fig.a del q. Gio: Angelo, Natali 23 marzo 156[?]",
 "L023":"Gio: Maria Nepote e fig.a del q. Gio: Angelo, Natali 25 d'luglio 1571",
},
"p002b": {
 "L001":"Gioane Montegabio[?] del darlono[?] padre[?] de badinolo[?]",
 "L002":"Catharina moglie del ditto Gioane",
 "L003":"Margarita fig.a del ditto, nata ali 16 d'8bre 1578",
 "L004":"Andrea di Cadimolo[?] [...] del q. Gioane",
 "L005":"Margarita moglie del ditto Andrea",
 "L006":"Ant.o fra[tello] del soprascritto Gioane",
 "L007":"[skip]",
 "L008":"Andrea fig.o del soprascritto Gioane",
 "L009":"Cristoforo Montegabio detto [...] del darlono[?], padre d'famiglia",
 "L010":"Madalena moglie del ditto [Cristoforo]",
 "L011":"Gio: Maria fig.a del ditto Cristoforo",
 "L012":"Stefano fig.o del ditto Cristoforo",
 "L013":"Madalena fig.a del ditto, nata ali 20 ottobre [15]62",
 "L014":"Margarita fig.a del ditto, nata ali 6 gennaro 1577[?]",
 "L015":"Fran.co [...] de quelli del darlono",
 "L016":"Catharina moglie del ditto",
 "L017":"Ambrosio fig.o del ditto, nato ali 8 giugno [15]63",
 "L018":"Gioane fig.o del ditto, nato ali 15 d'8bre 1563",
 "L019":"[skip]",
 "L020":"[skip]",
 "L021":"Thomaso[?] fig.o del ditto, nato di 30 aprile 1573",
 "L022":"Gio: Maria fig.a del ditto, nata li 28 d'aprile 1576",
 "L023":"[skip]",
 "L024":"Gio: Angelo fig.o del ditto, nato ali 26 d'gennaro 1579",
},
"p003a": {
 "L001":"Balhamina[?] ditta à coverta[?]",
 "L002":"Gio: Pietro fig.o della detta Balhamina[?]",
 "L003":"Catharina moglie de ditto Gio: Pietro",
 "L004":"[skip]",
 "L005":"Margarita fig.a del ditto, Natali 6[?] aprile [?]",
 "L006":"Bernardo[?] de coverto[?] fig.o della [...] Balhamina[?]",
 "L007":"Lucia moglie d'ditto Bernardo[?]",
 "L008":"[skip]","L009":"[skip]",
 "L010":"[Jacomo?] Torchono[?] della bagra[?], padre d'famiglia",
 "L011":"Margarita sua moglie",
 "L012":"Gioane fig.o del ditto",
 "L013":"Lucia fig.a del ditto",
 "L014":"[skip]",
 "L015":"[Angela?] fig.a del ditto, nata ali 8 d'8bre 163[?]",
 "L016":"[…] fig.o del ditto, nato ali [?] maggio 167[?]",
 "L017":"Catharina[?] fig.a del ditto, Natali 24 settembre 169[?]",
 "L018":"Cristoforo d'Paulono[?] delli Garfui[?]",
 "L019":"Gio: Angelo detto il Cono[?] delli Cortai[?]",
 "L020":"Jacomino[?] delli Bartu[?]",
 "L021":"[skip]","L022":"[skip]",
},
"p003b": {
 "L001":"Gio: Angelo Gasparono[?] el Sanegada[?], padre d'famiglia",
 "L002":"[Tomasina?] moglie del ditto",
 "L003":"Simono[?] fig.o del ditto, Natali 20 di novembre 156[?]",
 "L004":"[…] fig.o del ditto, nato ali 28 d'8bre 1568",
 "L005":"[skip]",
 "L006":"[…] del ditto, Natali 20 d'8bre 157[?]",
 "L007":"[…] fig.o del ditto, Natali 20 d'8bre 1575",
 "L008":"[skip]",
 "L009":"Bernardino fig.o del ditto, nato ali 20 giugno 1578",
 "L010":"Bartola[?] fratello del ditto",
 "L011":"Joanina moglie d'ditto Bartola",
 "L012":"[skip]",
 "L013":"Margarita fig.a del ditto, nata ali 12 d'8bre 1575[?]",
 "L014":"[skip]",
 "L015":"Gioane fig.o del ditto, nato ali 25 d'ottobre 157[?]",
 "L016":"Ambrosio fratello del ditto [Bartola]",
 "L017":"Gio: Maria Gasparono el Peveranda[?], padre d'famiglia",
 "L018":"Elisabetta moglie d'ditto",
 "L019":"Gio: Ant.o fig.o d'ditto, nato ali 20 d'8bre 1570",
 "L020":"[skip]","L021":"[skip]",
 "L022":"Gio: Batta[?] fig.o di ditto, nato di 26 ottobre 1575",
 "L023":"[skip]",
 "L024":"Togno del pino[?] il mala ongumba[?], padre d'famiglia",
 "L025":"Angelina moglie del ditto",
 "L026":"[skip]",
 "L027":"Margarita[?] del ditto, nata ali 28 settembre[?] 1573[?]",
},
}

for pid, corr in DRAFTS.items():
    path = f"gold/{pid}/correct.tsv"
    rows = list(csv.DictReader(open(path), delimiter="\t"))
    n = 0
    for r in rows:
        if r["line"] in corr:
            r["correct"] = corr[r["line"]]; n += 1
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter="\t")
        w.writeheader(); w.writerows(rows)
    print(f"{pid}: filled {n}/{len(rows)} lines")
