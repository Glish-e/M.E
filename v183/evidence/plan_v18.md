# plan_v18.md — W0 entry baseline (M.E. v1.8.0)

Date: 2026-11-18 (Africa/Casablanca). Input: download/final_master_d.zip
(sha256 86a62fca9930ffd7e9e2371ed13eb918243b73030af1265fd138c97bf4898da9,
226 files, all entry mtimes 2026-11-14 15:57). Unzipped clean to
work/w18 and everything below ran THERE, as user `z` (uid 1001,
non-root).

## Rule book working mode (R1-R24)

- R1 engines read-only: ENGINES.sha256 checked at entry — pasted in
  evidence/w18_entry_engines.txt (meds.py OK, quality.py OK,
  earnings_engine.py OK). Will be re-checked at exit.
- R10/R11 agent-safe only: unit tests, stub runs (MASTER_STUBS=1),
  offline runs on the zip's caches, linters, profilers on fixtures,
  golden regeneration. Nothing that needs the network — owner scripts
  instead (R12). R13: no keys in the zip; only .env.example ships.
- R14 red-then-green for every fix/feature; suite count never drops
  (baseline 436). R15: freeze/replay + fuzz_decisions.py before/after
  each refactor step; CONFIG diff additions only
  (scripts/config_diff.py). R16: flags/schemas add only; JSON never
  NaN. R22: wip_w{0..7}.zip checkpoint after each workstream, sha256
  computed AFTER the last edit. R23: defects.md entries with IDs.
- Plan per workstream: W1 module split (R14/R15/R17 small steps),
  W2 agent-safe profiling (R9 labels on fixture timings), W3 UI
  (goldens re-justified in writing, R16 additive), W4 --bt-start/--end
  (R19 descriptive label, no-lookahead tests kept green), W5 risk
  controls opt-in (R20 binding tests + looser-than-norm labels),
  W6 owner tooling + synthetic-refusal (R7), W7 release (RUNBOOK<=120,
  HANDOFF<=3500, MANIFEST full rebuild, env matrix pasted, zip sha256
  printed in the final message only).

## Baseline (all VERIFIED this session)

- Suite in the clean unzip, non-root: `python3 test_master.py` →
  "Ran 436 tests in 24.711s / OK" (evidence/w18_baseline_suite.txt).
- ENGINES.sha256 entry check: 3/3 OK (see entry file).
- master.py = 7,381 lines / 374,865 bytes; meds.py 9,604;
  quality.py 15,994; earnings_engine.py 1,134 (engines, read-only);
  test_master.py 7,998; ml_dataset.py 985; ml_train.py 1,046; codes.py
  195. 194 top-level classes/functions in master.py.
- MANIFEST.txt header "# files: 214"; release gate on the tree FAILS
  for 2 entries (see fact F6 / defect D-18-001).
- master.py __version__ = "1.7.0-dev" (master.py:201); ml_train 1.1.0
  (sidecars pin it).
- sklearn in this sandbox = 1.5.2 (same as the pinned head versions),
  numpy 2.1.3.

## Section-2 facts re-verified (CONFIRMED / DIFFERS / NOT RUN)

F1 "436 tests pass as a normal user; one fails as root (read-only
   dir); ENGINES.sha256 matches; MANIFEST has 214 entries."
   → CONFIRMED in the parts runnable here: 436/OK as uid 1001
   (pasted); ENGINES OK x3 (pasted); MANIFEST header says 214 entries.
   The as-root failure is NOT RUN (no root in this sandbox; R5 label).
   See D-18-001 for the MANIFEST caveat.

F2 "The final backtest used 63-trading-day windows while the Phase 8
   backtest used 21-day windows. Reason unknown."
   → DIFFERS (wrong reading, evidence below). There is ONE backtest
   implementation (master.py --backtest, phase 6). It evaluates the
   DATASET's label windows, and the preregistered q-head label horizon
   is 63 trading days: evidence/preregistration.md:69 "which encodes
   63 trading days for q, 63+30 for e, 21 for macro"; master.py:6309
   `_BT_WINDOW_TD = 63.0  # the pilot label horizon (63 trading days)`;
   the shipped run report says "63-td overlapping label windows"
   (evidence/phase6_backtest_report.md:6). The "21" numbers are
   (a) the macro head's label horizon (prereg line 69) and (b) the
   trading-days-per-month constant used only to COUNT independent
   windows: master.py:6638 `n_indep = max(1, round(len(rows) * 21.0 /
   _BT_WINDOW_TD))`. No 21-day-window backtest exists anywhere in the
   tree (greps in evidence/w18_fact2_greps.txt). The prereg is
   unchanged (nothing to change — no conflict found).

F3 "master.py --backtest has NO date flags; ml_dataset.py has
   --start/--end/--freq/--dates."
   → CONFIRMED: master.py --help shows --backtest/--backtest-rerun/
   --backtest-dataset/--backtest-out and NO date flags; ml_dataset.py
   --help shows --start/--end/--dates/--freq. (W4 adds --bt-start/
   --bt-end additively, R16.)

F4 "The engines call FRED, SEC EDGAR, Yahoo and Finnhub. The owner
   says they use three APIs."
   → CONFIRMED that the code calls FOUR HTTP sources; the three the
   owner means are the registered services (greps in
   evidence/w18_fact4_greps.txt):
   - FRED (meds.py): api.stlouisfed.org/fred/series/observations —
     KEY REQUIRED (env FREDAPI/FRED_API_KEY/FRED_API/FRED_APIKEY,
     meds.py:270); a no-key public fallback exists
     (fred.stlouisfed.org/graph/fredgraph.csv, meds.py:1468).
   - SEC EDGAR (quality.py): data.sec.gov/submissions + xbrl/
     companyfacts + www.sec.gov/files/company_tickers.json — NO KEY
     (public; courtesy User-Agent).
   - Finnhub (quality.py + earnings_engine.py):
     finnhub.io/api/v1/stock/earnings — KEY REQUIRED
     (FINNHUB_API_KEY).
   - Yahoo (yfinance + query1.finance.yahoo.com/v8 chart calls for
     SPY, in meds.py/quality.py/earnings_engine.py/master.py) — NO
     KEY. This is the price history source; likely the one the owner
     is not counting as a "registered" API.

F5 "The shipped q-head fails to load on sklearn 1.9.1 (trained on
   1.5.2); the version guard marks it UNAVAILABLE."
   → CONFIRMED (code + pin verified; the 1.9.1 failure itself is the
   owner's environment, not reproducible here): head_q.npz pins
   sklearn_version=1.5.2 / numpy 2.1.3 / ml_train 1.1.0; master.py:2101
   "§3.1 (B-1) version-aware loading" — a mismatched pin returns
   "UNAVAILABLE — {label} ..." and the head is SKIPPED, never a crash;
   the guard is covered by existing tests
   (test_master.py:5191 test_version_mismatch_run_continues_exit_one,
   4631/4648 absent-sklearn test). Sandbox sklearn is 1.5.2 so heads
   load here. W6's owner retrain script addresses the owner side.

F6 (new, found by this entry check — R23) MANIFEST integrity in the
   SHIPPED zip: `python3 scripts/release_gate.py` → "[FAIL] MANIFEST
   hashes all match — evidence/phase6_backtest.json,
   evidence/phase6_backtest_report.md". The zip carries copies whose
   sha256s are fb36bcb1…/d26a2110… while its own MANIFEST.txt records
   74831218…/d30ccee… (the hashes of the work/wip tree's later
   versions — the zip's phase6_backtest.json also references a
   "dataset": ".../work/w18/..." path and CONFIG "current_hash
   04293ea1…", i.e. it was produced by a re-run in a tree the manifest
   was not rebuilt for). Logged as defect D-18-001 (status: will be
   FIXED in W7 — v1.8.0 rebuilds MANIFEST after the last edit and the
   gate re-runs on the shipped tree; the two files are evidence text,
   not code, and the mismatch does not touch engines or decisions).

F7 "master.py is very large: measure with wc."
   → CONFIRMED: 7,381 lines / 374,865 bytes (pasted in the baseline
   block above).

## Defects opened at entry

- D-18-001 (DEFERRED→W7): shipped final_master_d.zip MANIFEST
  mismatch on 2 evidence files — detail in F6 above; fix = W7 full
  manifest rebuild + post-zip gate re-run on a clean unpack of
  final_master_e.zip itself.

## Baseline artifacts to compare against after each workstream

- Suite: 436 tests OK (w18_baseline_suite.txt).
- fuzz_decisions.py rc=0 baseline (evidence/w18_fuzz_baseline.txt).
- freeze/replay: `MASTER_STUBS=1 python3 master.py --mode quick
  --tickers ... --freeze /tmp/w18_f0` then `--replay /tmp/w18_f0`
  exit 0 (decision-hash gate, R15); captured before W1 step 1.
- Goldens: goldens/*.txt regenerate via scripts/make_goldens.py only
  with a written justification (R16/R3 discipline).
