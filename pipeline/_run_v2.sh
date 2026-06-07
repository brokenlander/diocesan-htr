#!/usr/bin/env bash
# Sampler launcher for the v2.1 HTR run. Resumable: run() SKIPS any page that already has a final.
# This script does NOT self-detach — the CALLER must launch it detached so it survives harness
# teardown (the hourly VERIFY_LOOP watchdog does exactly this):
#   setsid bash pipeline/_run_v2.sh >> pipeline/run_v2.log 2>&1 </dev/null & disown
# ORDER: new-coverage registers FIRST (X44/X5/X51 are mostly undone) so the scarce ~250-req/day
# gemini-3.1-pro quota buys brand-new pages first; finished pages are skipped for free.
cd ~/forge/latin
exec env PYTHONUNBUFFERED=1 PYTHONPATH=scripts .venv/bin/python3 -u \
  pipeline/gemini_htr.py run \
  x-44-1583 x-5-1642-74 x-51 x-4-1574 x-18-1570-79 x-20-1583 turate
