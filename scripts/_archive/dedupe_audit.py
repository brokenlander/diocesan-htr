#!/usr/bin/env python3
"""Perceptual near-duplicate audit for the Archivio diocesano scans.
Conservative: flags only pages whose phash AND dhash are both very close
(genuine re-shots), and reports clusters for human review — deletes nothing.
"""
import os, sys
from collections import defaultdict
from PIL import Image
import imagehash

ROOT = "Archivio diocesano"
PHASH_MAX = 6   # Hamming distance on 64-bit hash; tight = only near-identical
DHASH_MAX = 6   # require BOTH to agree -> avoids merging similar-but-distinct pages

records = []  # (path, phash, dhash, size_bytes, dims)
for dirpath, _, files in os.walk(ROOT):
    for f in sorted(files):
        if not f.lower().endswith((".jpg", ".jpeg")):
            continue
        p = os.path.join(dirpath, f)
        try:
            with Image.open(p) as im:
                im.draft("L", (256, 256))  # fast load
                g = im.convert("L")
                ph = imagehash.phash(g)
                dh = imagehash.dhash(g)
                dims = im.size
        except Exception as e:
            print(f"!! could not read {p}: {e}", file=sys.stderr)
            continue
        records.append((p, ph, dh, os.path.getsize(p), dims))

print(f"scanned {len(records)} images\n")

# union-find clustering within each folder (bursts live in the same folder)
parent = list(range(len(records)))
def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]; i = parent[i]
    return i
def union(a, b):
    parent[find(a)] = find(b)

by_dir = defaultdict(list)
for idx, r in enumerate(records):
    by_dir[os.path.dirname(r[0])].append(idx)

for idxs in by_dir.values():
    for a in range(len(idxs)):
        for b in range(a + 1, len(idxs)):
            i, j = idxs[a], idxs[b]
            if (records[i][1] - records[j][1]) <= PHASH_MAX and \
               (records[i][2] - records[j][2]) <= DHASH_MAX:
                union(i, j)

clusters = defaultdict(list)
for idx in range(len(records)):
    clusters[find(idx)].append(idx)

dup_groups = [c for c in clusters.values() if len(c) > 1]
extra = sum(len(c) - 1 for c in dup_groups)
print(f"near-duplicate clusters: {len(dup_groups)}   redundant shots: {extra}\n")

for c in sorted(dup_groups, key=lambda c: records[c[0]][0]):
    print("CLUSTER (same page, multiple shots):")
    for idx in sorted(c, key=lambda i: -records[i][3]):  # biggest file first = likely best
        p, ph, dh, sz, dims = records[idx]
        print(f"   {sz/1e6:6.2f}MB  {dims[0]}x{dims[1]}  {p}")
    print()

uniq = len(records) - extra
print(f"=> estimated unique pages: {uniq}  (from {len(records)} images)")
