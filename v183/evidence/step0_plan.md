evidence/step0_plan.md — PHASE 0 task 2: the Step 0 plan of record.

BASE DECISION (locked)
----------------------
RE-BASE ON v1.5.0 (master_final.zip, sha256
70004fdc15e5b5d88d7f5c81bc970005e4c9e8f6417523b913532e35438d6807) and
PORT every v1.4.1 fix (master_v1_4_1 (1).zip, sha256
d085c7839ad7e0a9430ce39061de3019e800f002fad5703be8ebfe111cbc2e05) BY
FUNCTION NAME, each with its regression test, written RED first, then
fixed, then GREEN. The result is named v1.7.0.

Rationale: the phase prompt overrides the spec's Section 1.1 scenario
table (master_v7.zip / v1.6.0 does not exist on this side; the two
available zips are siblings, both descended from v1.4.0). v1.5.0 carries
the offline-first modes, --doctor, --freeze/--replay, meds snapshot,
quick tier and provenance lines but LACKS the v1.4.1 fixes; v1.4.1
carries fixes B1-B8, M1-M5, P-5 (221 tests) but lacks all offline-first
features. Neither alone is the best version — exactly the situation the
spec's scenario 1 describes, with v1.5.0 standing in for the unavailable
v1.6.0. Function-level port map: evidence/port_map.md. Fact
re-verification: evidence/phase0_fact_checks.md. Baseline:
evidence/phase0_baseline.txt.

Inviolables carried into every phase: the three engine files are
read-only (ENGINES.sha256 pasted at each phase end); no live trades; no
secrets; conviction is a score, never a probability; no test weakened or
deleted (fixture changes need written line-by-line justification);
honesty contract Section 0 governs every claim ("no edge demonstrated"
is an acceptable result; nothing tuned to look good).

PHASE LIST 0-9 AND THE DEFECT IDs EACH PHASE CLOSES
---------------------------------------------------
Defect register: evidence/defects.md (B-1..B-10, C-1..C-6 space).
Spec workstream references in brackets.

PHASE 0 (this one) — lock the plan and the facts. [spec Step 0]
  Unpack both zips + hashes; verify tree vs MANIFEST; ENGINES gate;
  re-verify spec 1.2 facts; baseline suite runs (as-is + B7 conditions);
  function-level port map; seed the defect register; write the
  preregistration BEFORE any backtest/ML run. Closes: nothing (seeds
  B-1..B-10, C-1..C-4; discloses C-1 as resolved-on-arrival).

PHASE 1 — P0 reliability + the full v1.4.1 port. [spec 3.1]
  requirements.txt/-lock (version pins); version-aware model loading
  (ml_train_version checked at load; the '_loss'-class mismatched-sklearn
  path proven RED with a doctored pin, then refused cleanly); per-head
  failure isolation re-proven; port B1-B8 + M1-M5 + P-5 with the 35
  regression tests (port_map.md order: fuzz-RED first); port + FIX the
  hunt scripts and env matrix; retrain heads on the pilot as-is and paste
  the honest numbers; reconcile the version labels (docs vs code).
  CLOSES: B-6, B-1, B-5, C-2, C-3; most of B-2; the M4/M5 half of B-4.

PHASE 2 — P1 correctness of calculations. [spec 3.2 + 3.4 TP]
  --ruleset v2 (conservative fixed E; invariant + fuzz tests; legacy
  stays default with the loud UNVALIDATED header); unrounded LONG door
  behind the same opt-in; weak-E ablation harness; EARNINGS_TP single
  source of truth (master CONFIG drives both live plan and the coming
  backtest harness; engine untouched).
  CLOSES: B-7 items (a) missing-E advantage, (e) door rounding, (c-TP
  half) 15-vs-20, (g) weak-E disclosure/ablation.

PHASE 3 — P1 risk sizing + earnings trade management. [spec 3.3 + 3.4]
  vol_target opt-in sizing (looser-than-norm notes); reachable DD guard
  (hostile-volatility test + est_dd distribution on real runs); ADV
  feasibility probe (P-4: implement only if genuinely available);
  sizer-extreme tests (invalid budgets, zero/one name, all-inf vols —
  extending the B1 port); stops (P-3: k x annualised vol scaled to the
  holding period; "no vol -> no stop, visible warning"); hold_days
  wiring + surface; execution realism knobs for the backtest.
  CLOSES: B-7 items (b) under-invested book / unreachable DD veto, (d)
  no ADV guard (or its honest "ADV unavailable" disclosure), stop_px
  None (P-3).

PHASE 4 — ML dataset v2 build. [spec Section 4]
  Full universe (all sectors + historical membership where a source
  exists, delisted names where obtainable — otherwise the survivorship
  bound documented, never today's constituents silently); >= 36
  month-ends; PIT by filing date; per-feature missingness/provenance;
  atomic writes; manifest + sha256. Kicked off as a long-running build
  with resume; the tech pilot stays the smoke fixture.
  CLOSES: the dataset half of B-9; produces the Q1 evidence.

PHASE 5 — ML trainer v2 + validation under the Section 6 gates.
  Retrain all heads on the v2 dataset (per-fold selection — M2 port from
  phase 1 — target-aware embargo, no in-sample calibration); per-head
  verdicts against the prereg gates; reports/ML_VALIDATION_REPORT.md;
  every head SHADOW unless it GENUINELY passes.
  CLOSES: B-4 fully (the gates now judge real data); Q2 evidence.

PHASE 6 — integrated point-in-time portfolio backtest engine. [spec 5.1-5.5, 5.10]
  backtest_engine.py + master.py --backtest; the ACTUAL decision code at
  each rebalance; look-ahead sentinel test; costs/slippage execution
  realism (10 bps/side baseline; 5/25/50 sensitivity); strategies +
  ablations of 5.4; metrics of 5.5; tests on SYNTHETIC fixtures first.
  CLOSES: nothing by itself — builds Q5/Q6 evidence.

PHASE 7 — backtest on real data + statistics + lockbox. [spec 5.6-5.9]
  Run the backtest over the preregistered window; block bootstrap CIs;
  trial-count disclosure; deflated Sharpe if variants were many; lockbox
  evaluated ONCE with settings frozen; reports/BACKTEST_REPORT.md;
  preregistration verdict ("no edge demonstrated" is an acceptable
  outcome and will be reported as such).
  CLOSES: Q5/Q6 evidence; the measurement half of B-9.

PHASE 8 — speed. [spec Section 7]
  scripts/benchmark.py (cold/warm, single/5-name/sector/all + backtest);
  targets (warm single <= 5 s, warm 5-name <= 15 s, warm sector <= 60 s,
  backtest re-run in minutes); every change behind the bit-for-bit
  equivalence gate; zero-socket offline test kept green.
  CLOSES: B-8.

PHASE 9 — CLI + testing + release: final_master_d.zip. [spec Sections 8-9; Section 11]
  Column engine (no glued cells at widths 40/70/110/160), colour/plain/
  ASCII, byte-exact goldens containing NO dates, docs/CLI.md; suite >=
  300 green on the pinned dates/envs of Section 9; README.md,
  RELEASE_NOTES.md, reports/*, requirements*, HANDOFF <= 3,500 chars,
  MANIFEST + ENGINES.sha256, one-page runbook, ten-question scorecard,
  final message in the Section 11 format; zip sha256 printed.
  CLOSES: B-10, the remainder of B-2 (if any), C-4 (RUNBOOK costs
  disclosure restored), B-9's residue (verified or disclosed), and
  produces the final_master_d.zip deliverable.

DEFECT ID SPACE (allocated; full register in evidence/defects.md)
-----------------------------------------------------------------
B-1 sklearn '_loss' load failure · B-2 fragile tests (7 named + deps-
blocked + date-fragile) · B-3 _fit_z in-sample calibration fallback ·
B-4 M4/M5 gates · B-5 version-label drift (1.1.0-pinned vs 1.0.0) ·
B-6 the v1.4.1 port itself · B-7 weird rules (7 sub-items) · B-8 speed ·
B-9 unverified items · B-10 CLI glue/goldens (spec Sections 1.2/8).
C-1 missing uploads at phase-0 start (disclosed, resolved on arrival) ·
C-2 v1.4.1 env-matrix dead date pinning · C-3 v1.5.0 suite not
date-hermetic · C-4 v1.5.0 RUNBOOK lost the costs disclosure ·
C-5, C-6 reserved for defects found in later phases.

SCHEDULING NOTE (one deviation, disclosed): spec Section 12 orders the
integrated backtest (its item 4) before ML dataset quality (its item 5).
This plan runs the dataset build (phase 4) BEFORE the backtest engine
(phases 6-7) because the backtest consumes the dataset and the build is
the long pole (hours, resumable). Workstreams 3.1-3.4 keep the spec's
exact order (phases 1-3). If the owner objects, phases 4 and 6 can swap
with no other change.

OWNER DECISIONS ALREADY PRE-SET (spec Section 10 defaults; no question
needed unless a NEW decision outside this table blocks work): P-1
ruleset v2 opt-in · P-2 vol_target opt-in · P-3 stops = k x sizer vol ·
P-4 ADV probe first · P-5 weak-E 0.5 kept + ablation · P-6 unrounded
door opt-in.
