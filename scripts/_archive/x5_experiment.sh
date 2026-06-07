#!/usr/bin/env bash
# X5 warm-start experiment: fine-tune the SAME 40-line seed two ways and compare.
#   A) base = stock McCATMuS         (cold start on a new hand)
#   B) base = Turate v3 (0.8782)     (warm start — does Italian-cursive adaptation transfer to Latin decrees?)
# Same arrow + same SEED + same -p => identical train/val split => the val-accuracy delta is the answer.
set -e
cd "$(dirname "$0")/.."
PY=.venv/bin
OUT=gold/models/x-5-1642-74
ARROW=$OUT/seed.arrow
MCCATMUS=$(find ~/.local/share/htrmopo -name 'McCATMuS*.mlmodel' | head -1)
V3=gold/models/turate/v3/best_0.8782.safetensors
# -d/-s are TOP-LEVEL flags (before subcommand). Fixed seed => identical partition both runs.
COMMON="train -f binary --resize union -p 0.8 -q early --lag 5 --min-epochs 3 -N 60 -r 0.0001"

echo "===== RUN A: stock McCATMuS base ====="
rm -rf $OUT/A_stock; mkdir -p $OUT/A_stock
$PY/ketos -d cpu -s 42 $COMMON -i "$MCCATMUS" -o $OUT/A_stock/model "$ARROW" 2>&1 | tee $OUT/A_stock.log

echo "===== RUN B: Turate v3 warm-start ====="
rm -rf $OUT/B_v3; mkdir -p $OUT/B_v3
$PY/ketos -d cpu -s 42 $COMMON -i "$V3" -o $OUT/B_v3/model "$ARROW" 2>&1 | tee $OUT/B_v3.log

echo "===== SUMMARY ====="
echo "A (stock McCATMuS) best:"; grep -aoE 'val accuracy[^0-9]*[0-9.]+|accuracy [0-9.]+' $OUT/A_stock.log | tail -3
echo "B (v3 warm-start)  best:"; grep -aoE 'val accuracy[^0-9]*[0-9.]+|accuracy [0-9.]+' $OUT/B_v3.log | tail -3
ls -t $OUT/A_stock/*.safetensors $OUT/B_v3/*.safetensors 2>/dev/null
