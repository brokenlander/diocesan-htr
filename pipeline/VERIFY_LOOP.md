# Autonomous VERIFY LOOP — per-wake playbook

You are running unattended (cron, hourly). **Work autonomously. Do NOT ask questions. Never stop to confirm.**
Goal: turn each page's banked *valid* Gemini read into a verified final, image-grounded, honestly.

## ⚠️ Input source — use ONLY valid v2 reads
- The page's read is `processed/transcriptions/<slug>/candidates/<pid>.s1.json`.
- **It is VALID only if** it parses as JSON with a non-empty `lines` array. **REJECT** any read whose text
  begins with `[ERROR` or contains a 429/quota message — those are stubs.
- **Do NOT use `gold/models/gemini/<pid>.txt`** — for the undone registers those are **429 error stubs**.
  Only the v2 `candidates/` reads, produced by the running sampler, are real.
- The loop goes only as fast as the **sampler** banks reads — **quota-bound** (~250 req/day, rolling 24h;
  bursts then autostops). With the skip-finished fix the sampler now spends quota only on the ~74 real
  gaps, so the backlog clears in roughly one good quota window, not a steady trickle.

## Each wake: do ONE batch (up to ~10 pages), then stop (the cron re-fires hourly)
1. **Orient.** Read `HANDOVER.md` §2 (architecture) + the register's `registers/<slug>/context.md`.
2. **Pick the batch.** Up to **10** pages that have a VALID candidate (above) AND no final
   (`processed/transcriptions/<slug>/reconciled/<pid>.txt` absent).
   Priority: `x-44-1583` → `x-5-1642-74` → `x-51` → `x-4-1574` (p209→) → any other slug missing finals.
3. **Verify each** (the gold step):
   - Read `candidates/<pid>.s1.json` + the cropped image `processed/cropped/<slug>/<pid>.jpg` + `registers/<slug>/context.md`.
   - Reconcile against the PIXELS: fix misread names/numbers via the context glossary; keep honest
     `[?]`(word)/`[...]`(run); **never invent**; confirm blank/sparse pages are blank (bleed-through is NOT text).
   - Write `processed/transcriptions/<slug>/reconciled/<pid>.txt`.
   - **Flag-don't-guess:** if sparse / faded / name-&-number-dense / many `[?]`, append `"<pid>  <reason>"`
     to `processed/transcriptions/_REVIEW_QUEUE.txt` for the human to check later.
4. **Report GLOBAL PROGRESS (every wake — the user wants to see this).** Compute:
   `done = number of files in processed/transcriptions/*/reconciled/*.txt`
   `total = number of files in processed/cropped/*/*.jpg` (= 383)
   `pct = round(100*done/total)`.
   Append `"<ISO-time> verified <pids> | GLOBAL <done>/<total> = <pct>%"` (or `"<ISO-time> idle — waiting on
   sampler | GLOBAL <done>/<total> = <pct>%"`) to `pipeline/verify_loop.log`, AND **state the same
   `GLOBAL <done>/<total> = <pct>%` line in your user-facing message** so it shows in the wake summary.
5. **Idle vs done.**
   - If NO valid-candidate-without-final pages this wake: log idle (with the GLOBAL % line) and STOP
     (do NOT delete the cron — the sampler will bank more).
   - ONLY if EVERY cropped page has a final (done == total): write `"ALL VERIFIED <time> | GLOBAL 100%"`
     to the log and HANDOVER, then `CronList` → `CronDelete` the verify-loop job, and stop.

## SAMPLER WATCHDOG (every wake)
If pages still lack reads AND no process matching `gemini_htr.py run` is alive
(`ps -eo pid,args | grep '[g]emini_htr.py run'`), relaunch it:
`setsid bash /home/infra/forge/latin/pipeline/_run_v2.sh >> /home/infra/forge/latin/pipeline/run_v2.log 2>&1 </dev/null & disown`

## ⚠️ TURATE special case — 3-WAY reconcile (names matter; don't trust Gemini blindly)
Turate (`turate`, the 12 MP *status animarum* / le anime) is being RE-VERIFIED. For each Turate page,
reconcile THREE sources against the **12 MP image**: (1) the new Gemini read `candidates/<pid>.s1.json`,
(2) the McCATMuS-informed reference `processed/transcriptions/turate/pre_gemini/<pid>.txt` (good on names),
(3) the pixels. **On names/ages, where Gemini and pre_gemini disagree, the IMAGE decides — do NOT default
to Gemini** (the fine-tuned McCATMuS was decent here). Write `reconciled/<pid>.txt`; flag every name/age
disagreement to `_REVIEW_QUEUE.txt`. Do these AFTER the X-folder backlog (lowest priority, but required
before declaring 100%).

## Rules
- McCATMuS / TRIDIS are BENCHED (noise on 2MP) — not part of the pipeline; don't reach for them.
- Never re-do a page that already has a final (don't churn the v1-verified set). The sampler enforces
  this too: `run()` skips any page with a `reconciled/<pid>.txt`.
- Correct beats rushed; if genuinely unreadable → `[...]` and flag. Honesty > coverage.
- Route around the harness tmpfs ENOSPC bug: write check-output to a project file and Read it.
