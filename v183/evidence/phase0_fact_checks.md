evidence/phase0_fact_checks.md — PHASE 0 task 3: re-verification of the spec
Section 1.2 facts against v1.5.0 (the re-base candidate).

Scope note (honest): the spec's 1.2 was written against v1.4.1. The phase-0
prompt asks for each fact to be re-verified against v1.5.0; where the fact
describes v1.4.1 itself I verified it against the v1.4.1 tree too. The
Master_Engine_MASTER_PROMPT.md arrived mid-phase (defect C-1) — before it
arrived, the phase prompt's B-1..B-9 seed list was used as the interim fact
list; both were then checked against the real spec text. Nothing below was
silently trusted from any handoff.

Legend: REPRODUCES = the fact holds as stated on the named tree.
        DOES NOT REPRODUCE = it does not hold as stated (details given).
        BLOCKED = cannot be decided with the available inputs.

--------------------------------------------------------------------------------
F1. File inventory and sizes (spec: master.py ~4,470; meds 14.7.0 ~9,600;
    quality 3.4.1 ~16,000; earnings v3 ~1,130; ml_dataset 1.0.1; ml_train
    1.0.1; test_master.py 221 tests)
--------------------------------------------------------------------------------
$ wc -l master.py meds.py quality.py earnings_engine.py ml_dataset.py ml_train.py test_master.py
v1.4.1:  4469 / 9604 / 15994 / 1134 / 904 / 871 / 4030      -> REPRODUCES (v1.4.1)
v1.5.0:  5422 / 9604 / 15994 / 1134 / 947 / 751 / 4304      -> engines identical;
         master.py grew per its own final-phase HANDOFF (4,239 -> 5,422).
$ grep -n "^__version__" master.py ml_train.py ml_dataset.py
v1.4.1:  master.py 1.4.1 · ml_train.py 1.0.1 · ml_dataset.py 1.0.1   -> REPRODUCES
v1.5.0:  master.py 1.5.0 · ml_train.py 1.0.0 · ml_dataset.py 1.0.0
         NOTE: v1.5.0's HANDOFF/CHANGELOG LABEL these "1.1.0-pinned" /
         "1.1.0-dryrun" but the files themselves say 1.0.0 -> see F12 (B-5).
Test counts: v1.4.1 suite runs 221 (real, OK); v1.5.0 suite runs 256
(real, OK). scripts/ inventory differs: v1.4.1 ships the six hunt tools
(build_manifest, decision_path, diff_checks, fuzz_decisions, lint_hunt,
sensitivity_sweep, rules_register_check, test_env_matrix); v1.5.0 ships
only bench.py, config_diff.py, p4_pit_probes.py -> the hunt tooling is a
PORT ITEM (part of B-6), not a v1.5.0 feature.

--------------------------------------------------------------------------------
F2. Engine hashes match ENGINES.sha256; engines read-only
--------------------------------------------------------------------------------
REPRODUCES on BOTH trees (see phase0_baseline.txt; GATE PASS). The three
hashes are identical across the siblings. No engine file touched in
phase 0.

--------------------------------------------------------------------------------
F3. "221 of 221 tests pass (Python 3.12, scikit-learn 1.9.1, numpy 2.5.4)"
--------------------------------------------------------------------------------
PARTLY REPRODUCES: 221/221 pass HERE (real run, 8.947 s, OK) but under
Python 3.12.16 / sklearn 1.5.2 / numpy 2.1.3 — this sandbox does not have
sklearn 1.9.1 or numpy 2.5.4, so that specific environment is UNVERIFIED.
The v1.5.0 suite: 256/256 OK here (as-is).

--------------------------------------------------------------------------------
F4. sklearn '_loss' GBM load failure (B-1); artifacts pickled with 1.5.2
--------------------------------------------------------------------------------
DOES NOT REPRODUCE in this environment — and that is consistent with the
fact as stated: the sidecars were pickled WITH sklearn 1.5.2, which is
exactly what is installed here.
$ python3 -c "import joblib, sklearn; m = joblib.load('ml_data/models/head_q.joblib'); print('load OK:', type(m).__name__, sklearn.__version__)"
load OK: HistGradientBoostingClassifier | sklearn 1.5.2        (0.32 s)
$ master.py --doctor -> "ml  q SHADOW · e SHADOW · macro SHADOW"
-> heads load as SHADOW, no '_loss' error. The failure mode is real for
   OTHER sklearn versions (owner observed it on 1.9.1); the defect stands
   as the P0 compatibility item (version-aware loading / retrain path),
   to be closed in Phase 1 with a test that simulates the mismatched-
   sklearn load (v1.5.0 already refuses wrong-sklearn pins: test_wrong_sklearn_untrained
   + test_sklearn_absent_gbm_head_untrained exist and pass as-is).

--------------------------------------------------------------------------------
F5. Scoring defaults that must stay the default
--------------------------------------------------------------------------------
REPRODUCES on v1.5.0 (all 8 keys, real grep with line numbers):
  W_Q 0.65 (master.py:233) · W_E 0.35 (:235) · E_MISSING_HAIRCUT 0.90 (:236)
  EARNINGS_WEAK_SCALE 0.5 (:238) · MACRO_TILT_GAIN 0.10 (:240)
  MIN_QUALITY 40.0 (:244) · ACTION_LONG_AT 60.0 (:285) · ACTION_WATCH_AT 45.0 (:286)

--------------------------------------------------------------------------------
F6. Weird rule: missing earnings beats bad earnings (B-7a)
--------------------------------------------------------------------------------
REPRODUCES on v1.5.0. master.py:2452-2454:
    return q * CONFIG["E_MISSING_HAIRCUT"]              # E missing  -> 0.90*q
    return W_Q*q + W_E*e                                # E present  -> 0.65q+0.35e
Missing E wins whenever e < (0.90-0.65)/0.35 * q = 0.714*q — the spec's
own arithmetic, unchanged in code. The pre-sort ranking uses the same
haircut (master.py:2633: q_sig.score * E_MISSING_HAIRCUT * mult).
Pilot missing-E rate: ml_data/manifest.json nan_rate e_score = 0.3583
(~36%, matches spec). Fix is the opt-in --ruleset v2 (spec 3.2 P-1) — a
Phase 2 deliverable, default stays legacy + loud UNVALIDATED label.

--------------------------------------------------------------------------------
F7. Weird rule: under-invested book / unreachable DD veto (B-7b)
--------------------------------------------------------------------------------
REPRODUCES on v1.5.0 (code shape): RISK_MIN_EFFECTIVE_BETS=8.0
(master.py:407), eff-bets scaling k = eff/8 (:2136-2137), est_dd veto vs
RISK_MAX_EST_DD 0.30 (:2151), 2x ann vol estimate. Observed deployment in
THIS sandbox: offline smoke run -> "risk: gross 30% of 1.35 budget · cash
70%"; stub quick run -> "gross 7% of 1.00 budget · cash 93% · eff bets 1.8".
v1.4.1's hunt quantified 12-34% deployment and an est-DD ceiling ~0.26 <
0.30 (its HANDOFF P-2) — consistent with the code path here. The B2
RISK_FALLBACK_RHO disclosure (v1.4.1) is NOT in v1.5.0 (grep: 0 hits;
v141: master.py:435) — part of the B-6 port. Fix direction = spec 3.3
P-2 (vol_target opt-in) — Phase 3.

--------------------------------------------------------------------------------
F8. Weird rule: no stop-loss in the live plan; TP 15% vs engine 20% (B-7c)
--------------------------------------------------------------------------------
REPRODUCES on v1.5.0, at the exact lines the prompts cite:
  master.py:1620   "stop_px": None                       (phase prompt said ~1620)
  v1.4.1 master.py:1357  "stop_px": None                 (spec said ~1357)
  master.py:326    EARNINGS_TP = 0.15  ("eng.plan take-profit")
  master.py:1722   take_profit=CONFIG["EARNINGS_TP"] passed to eng.signals()
  earnings_engine.py:918  signals(..., take_profit: Optional[float] = 0.20, ...)
  earnings_engine.py:840  backtest(..., take_profit: Optional[float] = 0.20, ...)
-> live plan uses master CONFIG 0.15; the engine's own default/backtest is
0.20. Fix = one CONFIG source of truth (spec 3.4) — Phase 2/3. No engine
edit required (the engine receives the value as a parameter).

--------------------------------------------------------------------------------
F9. Weird rule: no liquidity/ADV guard (B-7d)
--------------------------------------------------------------------------------
REPRODUCES on v1.5.0: grep -ci "adv|average daily|dollar volume|liquidity"
master.py -> 0 matches (same in v1.4.1). ADV availability from existing
feeds remains UNVERIFIED (no live cache in this sandbox) — the spec's P-4
feasibility probe is the Phase 3 deliverable.

--------------------------------------------------------------------------------
F10. Weird rule: rounding at the LONG door (B-7e)
--------------------------------------------------------------------------------
REPRODUCES on v1.5.0. master.py:2522:
    d.conviction = round(max(0.0, min(100.0, _base_conviction(q, e, weak) * mv["mult"])), 1)
then master.py:2558 compares d.conviction >= ACTION_LONG_AT (60.0).
A true 59.96 displays/decides as 60.0 -> LONG. Same in v1.4.1 (:2366) — a
SHARED defect (not a v1.4.1 fix); the spec's P-6 opt-in unrounded door is
the Phase 2 deliverable.

--------------------------------------------------------------------------------
F11. Weird rule: no cost/slippage model; weak-E 0.5 scale
--------------------------------------------------------------------------------
No cost/slippage model in the live engine: REPRODUCES on v1.5.0 (no cost
model anywhere in master.py; RUNBOOK rewritten by the final phase no
longer mentions costs at all — whereas v1.4.1's RUNBOOK carries the "10
bps/side in the phase-4 study, treat all output as gross of costs"
section. v1.5.0 LOST that disclosure -> recorded as defect C-4).
Weak-E 0.5 scale: REPRODUCES (EARNINGS_WEAK_SCALE 0.5, renormalised blend
master.py:2455-2456; footer prints "weak-E x0.5" every run). The v1.4.1
P-5 disclosure upgrade ("weak x0.5 ACTIVE — E weight 35% -> 21%",
v1.4.1 master.py:3328-3334) is ABSENT from v1.5.0 (grep: 0 hits) ->
P-5 disclosure is a port item (B-6); the 0.5 value itself stays (owner
decision P-5, spec Section 10).

--------------------------------------------------------------------------------
F12. B-5: ml_train version mismatch ("1.1.0-pinned vs sidecars 1.0.0")
--------------------------------------------------------------------------------
REPRODUCES as a documentation/artifact version drift, not a load failure:
  v1.5.0 HANDOFF.txt + CHANGELOG.md label ml_train "v1.0.0 -> v1.1.0-pinned"
    and ml_dataset "v1.0.1 -> v1.1.0-dryrun";
  the FILES say __version__ = "1.0.0" (ml_train.py:59, ml_dataset.py:77);
  every shipped sidecar pin says ml_train_version '1.0.0',
  master_version '1.5.0', sklearn_version '1.5.2', dataset_sha256
  'e1e325ea0589' (real npz inspection, all three heads);
  ml_data/manifest.json (dataset manifest) still says master_version
  '1.3.1' / ml_dataset_version '1.0.0' — true for WHEN the pilot dataset
  was built (phase 4), stale as a current-tree stamp.
-> code and sidecars are mutually consistent (both 1.0.0); the mismatch is
   the doc label vs everything else, plus no ml_train_version check at
   load (master.py checks sidecar_sha256 + sklearn_version only, :1847-1857).
   Phase 1 must make ONE version source authoritative (requirements.txt +
   pins checked at load) and reconcile the docs.

--------------------------------------------------------------------------------
F13. B-3: in-sample calibration fallback (_fit_z, ml_train.py ~423, ~491)
--------------------------------------------------------------------------------
REPRODUCES on v1.5.0 at the EXACT lines: _fit_z defined at ml_train.py:289,
called at :423 (inside the walk-forward fold loop — "tiny train window
fallback") and :491 (final refit). v1.4.1 REMOVED it (M3: folds without
inner-OOF calibration are marked "insufficient", contribute no probability;
grep v141/ml_train.py -> "_fit_z" appears only in a comment).
MATERIAL IMPACT (real artifacts): v1.5.0's shipped validation_e.json claims
n_oos_rows=381 where v1.4.1's correctly claims 0 (all 5 folds calibration-
insufficient); the q head claims 435 OOS rows vs v1.4.1's 261 usable.
v1.5.0's validation numbers are therefore computed over folds carrying
in-sample calibration — the exact defect M3 exists to remove.

--------------------------------------------------------------------------------
F14. B-4: M4/M5 gates missing (>=12 usable OOS periods; hash-bound activation)
--------------------------------------------------------------------------------
REPRODUCES on v1.5.0:
  M4 — grep MIN_OOS_PERIODS ml_train.py -> 0 hits (v1.4.1: :109
       MIN_OOS_PERIODS = 12, enforced at :562/:578); v1.5.0 judges only
       n_oos >= 100 (ml_train.py:518) with no usable-periods floor and no
       verdict_basis block (v1.4.1's validation jsons carry
       verdict_basis; v1.5.0's do not — real json diff).
  M5 — v1.5.0's --activate (:687-707) refuses on missing/failing report
       but performs NO hash verification of report-vs-model; v1.4.1's
       --activate checks model_sha256 + dataset_sha256 + joblib_sha256
       (v141/ml_train.py:791-813) and re-pins after the state rewrite
       (:840-842). v1.5.0 npz sidecars DO pin sklearn_version +
       sidecar_sha256 (its own final-phase mechanism) — partial overlap,
       different key names ("sidecar_sha256" vs v1.4.1's "joblib_sha256"),
       no activation binding.

--------------------------------------------------------------------------------
F15. ML state numbers (spec 1.2: q 261/3 IC -0.416 Brier -0.805; e 0; macro
     35/5 IC +0.368; all SHADOW; ~1.2 effective months)
--------------------------------------------------------------------------------
REPRODUCES on v1.4.1 (real jsons: q n_oos_rows 261 / n_oos_periods 3;
e 0/0; macro 35/5 — matches the spec exactly).
On v1.5.0 the numbers are DIFFERENT AND CONTAMINATED by B-3 (q 435 rows
from 5 folds, e 381 rows from folds that v1.4.1 marks calibration-
insufficient; macro 35 rows, 9 features, "not needed (9 <= 20)").
Dataset facts re-verified from ml_data/manifest.json + npz: 90 tickers x
12 month-ends = 1,080 rows; 47 stock features; 9 macro features (real npz
feature_names count: 47); survivorship warning present; ~36% missing E.
All heads SHADOW on both trees; no ACTIVE head anywhere.

--------------------------------------------------------------------------------
F16. select_features leak (spec 1.2 last bullet, v1.6.0; B-3/M2-adjacent)
--------------------------------------------------------------------------------
REPRODUCES on v1.5.0 — and it matters MORE than the spec's wording: v1.4.1
never had feature selection (M2 was a no-op there: "select_features DOES
NOT EXIST on this base"), but v1.5.0 ADDED it (ml_train.py:370
select_features, FEATURE_CAP=20): importance is the mean |standardised
coef| over ALL walk-forward folds' TRAIN windows (ml_train.py:381-389),
then ONE fixed feature set is applied to every fold. For fold k, the
ranking was informed by later folds' training windows, which include
periods that are TEST periods for fold k -> the spec's "selection on
pooled training windows instead of inside each fold" leak, by
construction. The shipped validation jsons record exactly this method
("mean |standardised coef| over 5 TRAIN-fold fits"). The M2 port is
therefore a REAL fix on v1.5.0 (selection inside each fold + per-fold
feature lists + perturbation test), not a documentation item.

--------------------------------------------------------------------------------
F17. Speed claims (spec 1.2: 5-name 78-144 s; cold 10-25 min; v1.6.0 3.8 s)
--------------------------------------------------------------------------------
BLOCKED (v1.6.0 does not exist; its numbers are not checkable). What IS
measured HERE (real): v1.5.0 import+version 128-132 ms (claimed 16 ms on
the build machine); suite 11.2 s; quick+offline smoke 33.4 s total with
this sandbox's cold caches (claimed 5.8 s on the build machine with warm
quality caches — different cache state AND machine; both facts recorded,
no conclusion drawn). Full benchmark = Phase 8 (B-8), after correctness.

--------------------------------------------------------------------------------
F18. CLI glued cells / narrow widths (spec 1.2; B-10)
--------------------------------------------------------------------------------
REPRODUCES on v1.5.0. Real width-40 stub render (this sandbox):
    #  TICKER ACTION CONV     Q     E
    1  AAPL   LONG   ███░ 83 A88 A  nodata
    2  MU     LONG   ███░ 79 A72 B  81 A·…
    3  NVDA   LONG   ███░ 71 B80 A  44 C
The Q cell glues grade+score+grade ("A88 A"), E truncates mid-word
("nodat", "A·…"). Same glue appears in the full-width report ("87 A88 A",
"HIGH_ACCRUA…", "macro +1.…"). v1.5.0 has NO column engine and NO goldens
(the v1.6.0 features the spec describes). B-10 opened for this; the spec
Section 8 column engine + date-free goldens are the Phase 9 deliverable.

--------------------------------------------------------------------------------
F19. B-9 unverified items — re-checked, all still open
--------------------------------------------------------------------------------
From v1.5.0's HANDOFF "NOT DONE / UNVERIFIED" + this session:
  - full-universe ML dataset build: NOT run (only --dry-run exists; the
    shipped dataset is the 12-date tech pilot) -> still open, Phase 4.
  - Finnhub response shapes inside quality.py: still UNVERIFIED (no
    captured live payload; engine-disclosed).
  - meds PIT: still approximate (manifest pit_verified.meds = false;
    pit_mode printed every run).
  - online-vs-offline decision identity on a REAL cache (diff_checks D3):
    UNVERIFIED here too (no quality/earnings caches in this sandbox;
    offline smoke degraded honestly instead).
  - cold-run network variance: carries over (single cold smoke here).
  - NEW (found this phase): v1.5.0 RUNBOOK lost the costs/slippage
    disclosure (C-4); v1.4.1's env-matrix date pinning is dead code (C-2);
    v1.5.0 suite not date-hermetic (C-3). All three recorded in defects.md.

--------------------------------------------------------------------------------
SUMMARY
--------------------------------------------------------------------------------
Reproduces on v1.5.0: F5-F11 (all weird rules + defaults), F12 (as doc
drift), F13 (exact lines), F14, F16, F18, F19.
Does not reproduce HERE (with reason): F4 (sklearn 1.5.2 installed = the
pickling version — failure is version-dependent, defect stands), F3's
specific sklearn 1.9.1/numpy 2.5.4 environment (absent here).
Different-and-explained: F1 (sizes per each tree's own history), F15
(v1.5.0's ML numbers contaminated by the B-3 fallback — not comparable).
Blocked: F17's v1.6.0-only numbers.
No mismatch between the spec and the trees was found that indicates the
spec was describing anything other than these two codebases; every
"did not reproduce" case is an environment fact, reported plainly.
