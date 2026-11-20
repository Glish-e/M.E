evidence/PHASE_STATE.md — running phase ledger for the v1.7.0 build.

## PHASE 0 — lock the plan and the facts (no code changes)

Date: 2026-11-13 (Africa/Casablanca). Base: v1.5.0 (master_final.zip,
sha256 70004fdc15e5b5d88d7f5c81bc970005e4c9e8f6417523b913532e35438d6807)
held in a clean copy at work/wip; sibling reference v1.4.1
(master_v1_4_1 (1).zip, sha256
d085c7839ad7e0a9430ce39061de3019e800f002fad5703be8ebfe111cbc2e05)
unpacked at work/v141.

WHAT WAS DONE (phase-0 prompt tasks 1-7)
- Task 1: both zips unpacked into separate folders; sha256 recorded
  (above). v1.4.1 + the master prompt arrived mid-phase (defect C-1,
  disclosed). Extracted v1.5.0 tree verified file-by-file against its
  shipped MANIFEST.txt: 99/99 OK, 0 mismatches, 0 unlisted
  (evidence/phase0_tree_check.txt).
- Task 2: evidence/step0_plan.md — re-base on v1.5.0, port every v1.4.1
  fix by function name each with its test (red first), result named
  v1.7.0; phase list 0-9 with the defect IDs each phase closes
  (B-1..B-10, C-1..C-6 space).
- Task 3: evidence/phase0_fact_checks.md — every spec Section 1.2 fact
  re-verified against v1.5.0 (and v1.4.1 where the fact describes it)
  with commands and outputs; each marked REPRODUCES / DOES NOT
  REPRODUCE (with reason) / BLOCKED. Headline: all weird rules and
  defaults reproduce; the sklearn '_loss' failure does not manifest
  here (sklearn 1.5.2 = the pickling version — environment fact, defect
  stands); v1.5.0's ML validation numbers are contaminated by the B-3
  in-sample fallback (e head: 381 claimed vs 0 usable on v1.4.1);
  v1.5.0's own select_features HAS the pooled-selection leak the spec
  attributes to v1.6.0.
- Task 4: evidence/port_map.md — function-level port map, one row per
  v1.4.1 fix (B1-B8, M1-M5 — M2 included with justification — and the
  P-5 disclosure), with v1.4.1 function names + line anchors, the
  matching v1.5.0 functions + line anchors, conflict risks (B6/M2/B7 =
  HIGH, B8/M5 = MEDIUM, rest LOW), the 35 regression tests to port by
  name, and the phase-1 execution order. Method and its limits stated
  up front (no v1.4.0 tree ships in either zip; the map is built from
  both changelogs + a real computed def/test inventory diff of the two
  siblings: 186 common tests, 35 v1.4.1-only, 69 v1.5.0-only).
- Task 5: evidence/phase0_baseline.txt — environment (Python 3.12.16,
  numpy 2.1.3, scikit-learn 1.5.2, joblib 1.5.3, scipy 1.14.1, pandas
  2.2.3, yfinance absent, network reachable) and the REAL baseline:
  v1.5.0 as-is = "Ran 256 tests in 11.165s / OK" (selftest entry point:
  256 in 11.182s OK); v1.4.1 in the same sandbox = "Ran 221 tests in
  8.947s / OK". Plus the B7-condition runs (offline+stubs: FAILED
  failures=7 — the seven named tests; offline only: 6; stubs only: 1;
  sklearn+joblib blocked: 4 failures + 3 errors), date-pinned matrix
  partial log, offline smoke run (exit 0, honest degradation, 33.4 s),
  doctor, import timing 128-132 ms. Nothing was fixed.
- Task 6: evidence/defects.md extended with the FINAL ROUND register:
  B-1..B-9 seeded OPEN (as instructed) + B-10 (CLI glue/goldens) + C-1
  (DISCLOSED) + C-2/C-3/C-4 (OPEN) + C-5/C-6 reserved. Historical
  lineage tables preserved untouched.
- Task 7: evidence/preregistration.md written BEFORE any backtest/ML
  run (phase 0 runs none): hypotheses, full-universe scope, date-range
  + lockbox rules, walk-forward scheme, PIT/label conventions,
  backtest conventions (costs 10 bps/side baseline, next-open entries,
  cash earns zero), the spec 5.8 + Section 6 pass/fail gates, the
  definition of "no edge demonstrated", and the no-tampering rule
  (dated, signed amendments only).

TEST NAMES ADDED IN PHASE 0: none — phase 0 changes no code. The 35
v1.4.1 test names to port (red-first) are listed in port_map.md.

COMMANDS RUN WITH REAL OUTPUT: all pasted in evidence/phase0_baseline.txt
(plus phase0_tree_check.txt, phase0_env_matrix_partial.txt,
phase0_fact_checks.md). Key last lines:
  v1.5.0 suite:   "Ran 256 tests in 11.165s / OK"
  v1.4.1 suite:   "Ran 221 tests in 8.947s / OK"
  offline+stubs:  "Ran 256 tests in 10.678s / FAILED (failures=7)"
  ENGINES gate:   "meds.py MATCH ... quality.py MATCH ...
                   earnings_engine.py MATCH / ENGINES.sha256 GATE: PASS"
  offline smoke:  "...empty shortlist: nothing passed the quality gate"
                  exit=0
  doctor:         "ml  q SHADOW · e SHADOW · macro SHADOW (all fail
                  validation — SHADOW, no decision changed)"

WHAT IS NOT VERIFIED (phase 0)
- The spec's 1.9.1-sklearn environment (not installable here); the
  '_loss' failure therefore not reproduced live (B-1 stands on the
  owner's observation + the pickled-version fact).
- v1.6.0/master_v7.zip (does not exist on this side) — any v1.6.0-only
  claim (19 goldens, 3.8 s warm single name, the -0.079 IC study) is
  BLOCKED, not contradicted.
- Online-vs-offline decision identity on a real warm cache (no
  quality/earnings caches in this sandbox; D3 stays open).
- ADV availability from existing feeds (P-4 probe is phase 3).
- Full env matrix ambient section was cut by the sandbox 600 s command
  limit (partial log kept); the three ambient conditions were re-run
  directly instead and are pasted in phase0_baseline.txt.
- The date-pinned runs carry TWO harness artifacts (FakeDate vs pandas
  Timestamp), disclosed and excluded from the defect counts.

OPEN ITEMS (carried)
- Phase 1 needs: master prompt + v1.4.1 zip remain in upload/ (present
  now); the port itself (B-6) with fuzz-RED first; requirements pins;
  retrain with honest numbers.
- Defects B-1..B-10, C-2..C-4 all OPEN with target phases in
  defects.md.
- The shipped MANIFEST.txt still describes the 99 v1.5.0 files; the
  phase-0 evidence files added by this phase are NOT in it (WIP zip,
  not a release; MANIFEST is rebuilt at phase 9 per spec Section 9).

GATE (phase 0): ENGINES.sha256 check pasted above and in
phase0_baseline.txt / phase0_tree_check.txt — PASS on both trees;
defects.md and preregistration.md exist. Deliverable: wip_phase0.zip
(sha256 printed in the phase-0 delivery message).

================================================================================
PHASE 1 of 10 — B-1 (version-aware loading), B-2 (hermetic suite),
B-5 (version surfaces) — closed 2026-11-13T21:00Z (sandbox clock), tree v1.7.0-dev
================================================================================

WHAT CHANGED (code, all red-first — see evidence/phase1_b1_b5_red.txt,
evidence/phase1_b2_red.txt for the RED state against v1.5.0-as-shipped)
- master.py (v1.5.0 -> v1.7.0-dev):
  * _ml_load_head: integrity gates reordered to run BEFORE any dep
    import or unpickle; four-version pin compare (sklearn/numpy/joblib/
    python) -> head UNAVAILABLE with reason (skipped, run continues);
    missing joblib/sklearn -> UNAVAILABLE (was UNTRAINED-worded); the
    sha256-verified sidecar BYTES are captured at load.
  * _ml_predict: unpickles ONLY those verified bytes (BytesIO — the
    file on disk is never re-read; no TOCTOU past the hash gate).
  * MLLayer.run: UNAVAILABLE head state + ctx_out["unavailable"];
    _resolve_exit: ml-unavailable -> exit 1 (run continued), after the
    exit-2 NO-GO gates; --help exit-code legend updated.
  * run_doctor: head states through the REAL loader — "q UNAVAILABLE
    (sklearn 1.5.2 != trained-on 1.9.1)" demonstrated on the real CLI.
- ml_train.py (1.0.0 -> 1.1.0): save_model pins the four versions in
    every npz AND the report pins block; --activate keeps the ORIGINAL
    training pins (pin_versions=False; activation is sklearn-free);
    train_head refuses honestly (exit 2 + reason) when sklearn is
    absent — data-sufficiency refusals stay sklearn-independent.
- test_master.py (256 -> 263 tests): hermeticity helpers (_pin_env,
    _pin_today, _runtime_versions); _run pins MASTER_NET + an empty
    per-call ml models dir; TestSidecarPin rewritten on runtime
    versions + the new B-1 tests; TestMLUnavailable (exit-1 pipeline
    behavior); TestVersionSurfaces (B-5 four-surface lock);
    TestStreams/TestWizardEntry/TestNetModes/TestFreshness/
    TestMLTrain/TestAsOfPropagation/TestNoLookahead/TestMlDataset made
    hermetic; test_sklearn_absent_gbm_head_unavailable reworded.
- scripts/test_env_matrix.py: PORTED from v1.4.1 WITH the C-2 fix
    (module-level date pinning; the global datetime module is never
    patched — v1.4.1's harness never installed its FakeDate at all).
    Also fixed v1.4.1's "2026-02-29" leap cell (not a real date; the
    real leap day 2028-02-29 is used).
- requirements.txt + requirements-lock.txt (spec 3.1 P0): MINIMUM ==
    TESTED, stated honestly; no invented floors — the B-1 loader is the
    fail-closed enforcement. yfinance documented as optional/absent.
- CHANGELOG.md + HANDOFF.txt: v1.7.0-dev section; B-5 surfaces aligned
    (the old v1.5.0 header kept verbatim below a HISTORICAL marker).

RETRAIN (numbers exactly as they came out; no tuning; defaults only;
evidence/phase1_retrain.txt)
- q:     gbm_joblib, 1044 train rows, 435 OOS rows, 5 folds, embargo 3m
         — monthly rank IC -0.284, decile spread -0.279, Brier skill
         -0.407, verdict FAILS (baseline raw-score IC +0.186). SHADOW.
- e:     gbm_joblib, 974 train rows, 381 OOS rows, 5 folds — monthly
         rank IC -0.183, decile spread -0.395, Brier skill -0.135,
         verdict FAILS (baseline raw IC -0.150). SHADOW.
- macro: logistic_np, 84 train rows, 35 OOS rows, 5 folds — monthly
         rank IC +0.368, decile spread +0.333, Brier skill +0.006,
         verdict FAILS (n_oos 35 < 100). SHADOW.
- Deterministic retrain: metrics and sidecar sha256 IDENTICAL to the
  v1.5.0 artifacts (same seed/data/sklearn) — the v1.5.0 e-head "381
  OOS rows" claim reproduces; the B-3 calibration-fallback question
  (v1.4.1 says 0 usable) stays OPEN, untouched by phase 1.
- No head ACTIVE; --activate refusal behavior unchanged (tested).

GATES (paste sources)
- Env matrix (B-2 gate): evidence/phase1_env_matrix.txt — 9 cells
  (baseline / MASTER_NET=offline / MASTER_STUBS=1 / offline+stubs /
  sklearn+joblib blocked / four pinned dates 2027-03-01, 2026-12-31,
  2025-02-01, 2028-02-29), 263 tests each, ALL CELLS GREEN, 0 skipped.
  Nothing was NOT RUN.
- The 7+1 named v1.5.0 failures green in every cell (they are part of
  the 263): TestSidecarPin.test_pin_ok_loads, TestCacheStatusRealDir.
  test_default_dir_cold_fetch_reported_cold, TestDegradationMatrixFinal.
  test_readonly_cache_is_clear_error_online, TestManifestHeader.
  test_header_rows_present, TestNetModes.test_explicit_online_without_
  network_exits_3, TestNetModes.test_probe_skipped_for_offline,
  TestProvenanceSurfaces.test_same_json_schema_every_mode, TestStreams.
  test_stdout_results_stderr_progress_and_piped_plain.
- Suite: 263 passed, 0 failed, 0 skipped (pytest AND master.py
  --selftest).
- ENGINES.sha256: meds.py 5e64b60da86d2e759f1f506e8c9dfdc5acfed32c...
  quality.py f123fb4e36ad298d0c662d0b36d71bb98ea80ef42760714d3b7133b...
  earnings_engine.py 8e31e53248531584898ebfd266347775874b93d3440d12...
  -> sha256sum -c ENGINES.sha256: all three OK (pasted in
  phase1_tree_check.txt; the full tree check + MANIFEST rebuild record
  lives there too).

DEFECTS (defects.md updated)
- B-1 FIXED (phase 1). B-2 FIXED (phase 1). B-5 FIXED (phase 1) —
  the ml_dataset doc half recorded as C-5 (DISCLOSED, fix due phase 9).
- C-2 FIXED (the matrix port). C-3 FIXED (date cells green; no test
  touches the network in any cell — the ambient online-refresh problem
  no longer exists because tests pin MASTER_NET per run).
- B-3, B-4, B-6 (7 remaining hunt scripts + 35 ported tests), B-7,
  B-8, B-9, B-10, C-4, C-6 unchanged (OPEN).

NOTES / LIMITS (honest)
- The owner's sklearn 1.9.1 environment is still not installable here;
  the '_loss' failure is simulated by pin mismatches (0.0.1-fake) and
  by blocking the imports — the mechanism (refuse before unpickle,
  UNAVAILABLE, exit 1) is fully tested, the exact sklearn error string
  is not reproduced live.
- Exit 1 fires only for UNAVAILABLE (environment/version) heads, per
  the phase-1 spec; integrity REFUSED heads (tampered sha) remain
  loud-warning + exit 0 as in v1.5.0 (disclosed here).
- ml_dataset "v1.1.0-dryrun" doc drift -> C-5 (phase 9), NOT silently
  rewritten (ml_dataset.py is functionally unchanged; inventing a bump
  would repeat B-5's mistake in the other direction).
- master_version pins in the retrained sidecars say 1.7.0-dev; the
  release (phase 9) retrains/pins the final 1.7.0.
- The matrix harness pins the clock on master/ml_dataset/ml_train and
  the test module — NOT on the read-only engines (meds/quality/
  earnings keep the real clock). Tests exercising engine-internal
  freshness do so through master's adapter paths; engine-clock
  dependence of test_real_meds_offline... is disclosed: it asserts
  both branches by design and passed in every cell.

DELIVERABLE
- wip_phase1.zip (this tree; sha256 in the delivery message) +
  MANIFEST.txt rebuilt for the current tree (WIP manifest; the release
  manifest is rebuilt at phase 9 per spec Section 9).

PHASE 1 STATUS: COMPLETE

================================================================================
PHASE 2 of 10 — B-6 (decision-layer half): B1-B6, B8 atomic writes, P-5,
the 8 hunt scripts — closed 2026-11-14 (sandbox clock), tree v1.7.0-dev
================================================================================

INPUT: wip_phase1.zip (this tree; spot-verified at phase start: ENGINES
all three MATCH, 7-file hash sample vs the zip = 0 differences, suite
263/263 green + selftest OK before any edit).

WHAT CHANGED (all red-first — RED evidence: evidence/phase2_red.txt,
23/25 new tests failing on the tree as shipped, plus the ported fuzz on
the unported tree phase2_fuzz_red.txt and the register census
phase2_rules_register_red.txt; GREEN: 288/288)

master.py:
- size_portfolio: B1+B2+B3 ported by function name from v1.4.1 (the
  v1.5.0 tree had re-inherited the v1.4.0 shapes — all-inf book =
  ZeroDivisionError, inf vol = silent zero weight, NaN budget = NaN
  weights into JSON, rho unavailable = silent guard-off, non-finite
  rho_bar = NaN eff/DD). New: every guard-off/fallback records a stable
  W_* code (W_RHO_FALLBACK, W_UNUSABLE_VOL, W_EQW_FALLBACK,
  W_BUDGET_STANDDOWN, W_DD_VETO) in out["warn_codes"] — printed in the
  footer and carried in the JSON summary so the phase-5 ERRORS &
  WARNINGS block can consume them.
- risk_ctx_out: v1.4.1 shape (null never NaN via _jf; rho_fallback
  footer line carrying W_RHO_FALLBACK; rho_fallback/rho_used/
  warn_codes JSON fields; veto line carries its codes).
- CONFIG: +RISK_FALLBACK_RHO 0.5 (the ONE addition — the diff vs
  v1.5.0-as-shipped shows exactly 1 added key, 0 removed, 0 value
  changes; 6 rationale-text-only disclosure updates:
  evidence/phase2_config_diff.txt). MODES["standard"] now resolves from
  EARNINGS_TOP_K/LAYER_TIMEOUT_S at import AND _apply_mode re-resolves
  at apply time (the two dead keys are LIVE again); EARNINGS_NATIVE_
  GRADES / CONF_DIGITS rationales disclose not-read (v1.4.1 B6 texts);
  STUB_WARM_BUDGET_S (a v1.5.0-only key the v1.4.1 register never saw,
  found by the phase-2 census) disclosed not-read — enforced by the
  suite, not production.
- _map_plan_row: B4 — NOW window bounded BOTH sides; future-dated report
  -> status open + future_report warning; _earnings_signal re-raises it
  (W_FUTURE_REPORT code).
- _apply_overlays: B5 — re-asserts EVERY blocked row (AVOID + below-
  WATCH cap, W_BLOCKED_REASSERT) once per decision BEFORE consulting
  any overlay signal (v1.4.1's first version covered only rows with a
  signal; the fuzz invariant caught it — same lesson honored here).
- _write_csv / run_freeze (manifest.json + the new "risk" disclosure
  block so OFFLINE REPLAY carries the guard-off disclosure) /
  _materialise_meds_snapshot (per-file atomic) — all write-temp + fsync
  + rename (_atomic_write_text / _atomic_write_bytes helpers).
- Layer-status renderer: P-5 — the weak line now states the EFFECTIVE
  earnings weight ("weak x0.5 ACTIVE — E weight 35% -> 21%").
ml_dataset.py: _atomic_write_text/_atomic_savez ported (with the
phase-2 fsync extension) at the cache-json / dataset-npz / manifest
sites.
ml_train.py: save_model writes the joblib sidecar and the npz
atomically (tmp + fsync + rename); validation reports atomic
(_atomic_write_text).
scripts/: all 8 hunt scripts now on this tree — fuzz_decisions.py
(fuzz I3 carries the hardened B5 contract, seed 88117 kept:
justification in evidence/fixture_changes.md), rules_register_check.py
(--master PATH + planted-dead-key negative control, locked by
TestRulesRegisterCheck), decision_path.py, lint_hunt.py,
sensitivity_sweep.py (RISK_FALLBACK_RHO swept like every numeric key),
diff_checks.py (D4 rewritten: freeze/replay EXIST here — the parity
harness is in the suite), build_manifest.py. Every seed/literal was
verified present BY NAME before porting (port_map.md execution record).
test_master.py: 263 -> 288 tests (+25, no test deleted, no assertion
weakened; one disclosed authoring correction before first green —
fixture_changes.md item 4): TestSizerHardeningB1B2B3 (11),
TestHardeningB4B5B6 (6), TestAtomicWritesB8 (5 — the 3 v1.4.1 tests +
freeze-manifest and meds-snapshot crash tests on v1.5.0's own writers),
TestWeakEDisclosure (P-5), TestRulesRegisterCheck (real register PASS +
negative control FAIL).

GATES (paste sources — all real runs)
- Env matrix: evidence/phase2_env_matrix.txt — 9 cells (baseline /
  MASTER_NET=offline / MASTER_STUBS=1 / offline+stubs / sklearn+joblib
  blocked / four pinned dates 2027-03-01, 2026-12-31, 2025-02-01,
  2028-02-29), 288 tests each, ALL CELLS GREEN, 0 skipped.
- Suite: 288 passed, 0 failed, 0 skipped (pytest AND master.py
  --selftest).
- Fuzz (seed 88117): phase2_fuzz_red.txt -> phase2_fuzz_green.txt.
  Post-port state IDENTICAL in shape to v1.4.1's: 1 disclosed
  out-of-contract suite (I1-ml-scaled-range, 1231 violations — the same
  count as v1.4.1's post-fix run: direct calls of _ml_scaled outside
  its guarded contract); every hardening suite 0.
- Rules register: phase2_rules_register_red.txt (5 dead: the four
  v1.4.1 B6 keys re-introduced by v1.5.0 + STUB_WARM_BUDGET_S) ->
  phase2_rules_register_green.txt (77 live / 3 disclosed / 0 dead;
  PASS). Negative control: planted ZZ_PLANTED_DEAD_KEY -> exit 1
  naming the key (unit test + CLI run).
- CONFIG diff vs v1.5.0-as-shipped: phase2_config_diff.txt — ONLY
  RISK_FALLBACK_RHO added; MODES standard preset byte-identical
  (behaviour unchanged, source of truth changed).
- Sensitivity sweep / decision path / lint hunt / diff checks re-run:
  phase2_sensitivity_sweep.txt / phase2_decision_path.txt /
  phase2_lint_hunt.txt / phase2_diff_checks.txt (D1 table/JSON/CSV
  agree + determinism IDENTICAL; D3 stays UNVERIFIED — no real cache in
  this sandbox).
- ENGINES.sha256: meds.py / quality.py / earnings_engine.py all three
  MATCH (re-checked at phase end; the engines were never opened for
  editing — full paste in phase2_tree_check.txt).

ACCOUNTING (prompt requirement; full record in port_map.md)
- Ported HERE: B1, B2, B3, B4, B5, B6 (keys + register script),
  B8-atomic-writes (incl. v1.5.0's own writers), B7's hunt-script half
  (matrix half was phase 1), P-5.
- Phase 3: M1, M2, M3, M4, M5, and B8's ML-load-hardening half (finite
  base_rate/calib at load, non-finite probability drops the head) —
  all ml_train-side, to land with their own red tests + the honest
  retrain.
- The two v1.4.1 fixture updates (the _mk_ml_model hash-bound report +
  the --activate negative cases): DEFERRED with justification
  (evidence/fixture_changes.md items 2-3 — they attach to M5, whose
  gate does not exist on this tree yet; fixtures left byte-identical,
  nothing weakened).

DEFECTS (defects.md updated)
- B-6: decision-layer half DONE (status records the split; ML half is
  phase 3). B-7(g)'s disclosure half closed by the P-5 port (the 0.5
  VALUE remains an owner decision). B-4 gained the phase-3 obligation
  note for the deferred fixtures. B-3, B-8, B-9, B-10, C-4, C-5, C-6
  unchanged.

NOTES / LIMITS (honest)
- W_* codes are recorded (sized dict + JSON summary + freeze manifest +
  the printed footer lines) but the ERRORS & WARNINGS BLOCK itself is
  phase 5's deliverable; phase 2 ships the codes it will read.
- The freeze manifest gained an additive "risk" block (schema stays 1;
  replay reads args/ranking and ignores unknown keys — verified by the
  freeze/replay tests staying green).
- The rules-register census counts differ from v1.4.1's (80 keys vs 67:
  the v1.5.0 CONFIG grew); the PASS condition is identical and now also
  covers the v1.5.0-only key the v1.4.1 register never saw.
- The sweep honestly reports RISK_FALLBACK_RHO as zero-effect on
  weights (it moves the est-DD estimate + its disclosure only — by
  design; test_b2_* asserts exactly that role).
- I1-ml-scaled-range (1231) is pre-existing disclosed out-of-contract
  behavior IDENTICAL on v1.4.1 and this tree; not a phase-2 regression
  (count matches to the violation).

DELIVERABLE
- wip_phase2.zip (this tree + rebuilt WIP MANIFEST.txt; sha256 printed
  in the delivery message; the release manifest is rebuilt at phase 9).

PHASE 2 STATUS: COMPLETE

================================================================================
PHASE 3 of 10 — B-3 + B-4 (the ML half of B-6: M1-M5 ports, ML gates,
load hardening, the two deferred fixtures) — closed 2026-11-14 (sandbox
clock), tree v1.7.0-dev
================================================================================

INPUT: wip_phase2.zip (this tree; verified at phase start: the zip's 137
files == work/wip byte-for-byte, 0 differences; ENGINES.sha256 all three
MATCH; suite 288/288 green before any edit; PHASE 2 marked COMPLETE).

SCOPE (the phase-3 prompt) + the phase-2 accounting obligations that
landed with it (port_map.md's "Phase 3: M1, M2, M3, M4, M5 and B8's
ML-load-hardening half" + evidence/fixture_changes.md items 2-3):
B-3, B-4 closed; M1, M2, M3, M4, M5 ported BY FUNCTION NAME from
master_v1_4_1.zip with the v1.4.1 tests written against this tree FIRST
(RED: evidence/phase3_red.txt — 23 of the 25 phase-3 tests failed or
erred on the as-shipped tree; the 2 that passed are the GBM sidecar-pin
companions, green already because v1.5.0's own §7.1 pinning predates
this phase — no test was written green-by-construction).

WHAT LANDED
- ml_train.py (the ML half of B-6):
  * M1 target-aware inner embargo: _label_horizon_td (q 63 td / e 93 /
    macro 21 from ml_dataset's own constants) -> _inner_embargo_months
    (q 3 / e 5 / macro 1) -> _inner_splits(groups, embargo) ->
    _inner_oof(..., embargo_months) — the hard-coded 1-month inner
    embargo that let inner-fold label windows overlap the inner test
    month is gone. Tests test_m1_* x3 (the leak-channel demonstration
    included: lag-1/2 label correlation 0.45+ vs the decaying channel).
  * M3 no in-sample calibration fallback: the _fit_z function and its
    fold-loop + final-refit call sites AND its GBM twin (predict_proba
    on the train rows) are REMOVED. A fold without inner-OOF calibration
    carries calibration="insufficient", p=NaN, and is EXCLUDED from the
    pooled metrics (oos["ok"] mask); the final refit ships identity
    calib disclosed as final_calibration=
    "uncalibrated_insufficient_inner_oof" and can never support
    activation. metrics_block(empty) is a legal honest n=0 block.
    Tests test_m3_* x3 incl. the grep-style source test.
  * M2 per-fold feature selection (FEATURE_CAP=20 kept): select_features_
    fold(X, y, feats, train_idx) ranks by |standardised coef| on THAT
    fold's train window only; the old pooled-across-folds ranking (which
    read later test periods' training data — F16) is gone; the final
    refit selects on all labeled rows (the shipped model — disclosed);
    every fold record carries its feature list; the report carries
    per_fold + selected + the method note. Tests: the perturbation test
    (test-fold labels AND feature values perturbed -> every fold's
    selection bit-identical; evidence/phase3_perturbation.txt paste) +
    the rewritten TestFeatureCap.
  * M4 the verdict gates: MIN_OOS_PERIODS=12; beats IFF >= 12 USABLE
    OOS periods AND >= 100 usable OOS rows AND final model calibrated
    via inner OOF AND monthly IC > 0 AND > raw-engine baseline IC AND
    Brier skill > 0 — otherwise "insufficient evidence" naming the
    failed condition(s) (the phase-3 prompt's vocabulary; v1.4.1's
    "fails"-with-why is kept for the judged-negative case). The report
    gains n_oos_periods / n_insufficient_folds / final_calibration /
    verdict_basis{model_rowset_sha256, baseline_rowset_sha256, note} —
    the model-vs-baseline comparison is on IDENTICAL rows in every
    branch (the v1.4.1 GBM-winner hole — winner on all-usable rows vs
    baseline on cmp rows — is closed and disclosed in port_map.md);
    logistic-vs-GBM is also identical-rows. Tests: the four gate tests
    (11 periods / 96 rows < 100 / no calibration / all-pass ->
    "beats" allowed, SHADOW until the MANUAL --activate) +
    test_m4_baseline_compared_on_identical_rows (capture-proof: the
    model call and the baseline call received the EXACT same rows and
    groups; the digest recomputed from the capture matches the report).
  * M5 hash-bound reports + activation: the trainer binds each report
    (model_sha256 = sha256 of the npz just written; dataset_sha256 =
    the npz's own 12-hex dataset pin — same convention both sides);
    --activate verifies the model hash BEFORE parsing the npz (a
    tampered file refuses cleanly), requires a non-empty dataset pin on
    BOTH sides (stricter than v1.4.1 — disclosed), requires the GBM
    sidecar pin, then rewrites state + re-binds the report to the
    ACTIVATED artifact. SHADOW stays the default; nothing automatic.
    Tests: tampered-file refusal + restore-then-pass, the two deferred
    fixture updates (below), and master-side load verification.
- master.py (B8's ML-load hardening + M5 load side):
  * _ml_load_head: finite base_rate in (0,1) REFUSED; finite calib_a/b
    REFUSED (logistic_np); the ACTIVE-state report check now verifies
    verdict == beats AND report.dataset_sha256 == npz pin (non-empty)
    AND report.model_sha256 == sha256(npz) — else downgrade to SHADOW
    with the reason (port of v141's _ml_load_head; the v1.5.0 sidecar
    pin + version pins + verified-bytes unpickle stay as-is).
  * _ml_predict: non-finite probability -> None (the head's
    contribution DROPS); _ml_adjustment: isfinite belt; MLLayer.run:
    dropped-count warning + "p_q/p_e dropped (non-finite)" p_note
    segments + the macro good-ETF filter + a round(None) guard on the
    ctx_out macro map (a latent crash v1.4.1's port surface exposed).
  * _sha256_file helper ported (v141's).
- The two DEFERRED v1.4.1 fixtures landed exactly as recorded in
  evidence/fixture_changes.md items 2-3: _mk_ml_model's validation
  report is hash-bound to the npz it just writes (+ calib_a/calib_b /
  dataset_sha kwargs); test_activate_refused_without_passing_report
  gained the wrong-model-hash (rc 2) and wrong-dataset-hash (rc 2)
  negative cases in BOTH its sklearn and no-sklearn branches.
- C-6 (the reserved defect slot) is now USED: (a) the env-matrix
  harness's blocked cell was not fully hermetic — sequential cells left
  sklearn.* SUBMODULES in sys.modules so `from sklearn.X import Y`
  imports still succeeded; purged now (surfaced by phase 3's selection
  test, fixed scripts/test_env_matrix.py); (b) the selection test skips
  cleanly where sklearn is genuinely absent (B7 contract).

RETRAIN (honest numbers, the phase gate's requirement —
evidence/phase3_retrain.txt, same invocation as phase 1's):
  q     1044 train rows -> 261 usable OOS rows, 3 usable periods,
        2 insufficient folds, monthly rank IC -0.416, Brier skill
        -0.805, verdict "insufficient evidence" (shipped SHADOW, GBM
        winner on identical rows)
  e      974 train rows ->   0 usable OOS rows (ALL 5 folds
        calibration-insufficient under the e-head's 5-month inner
        embargo), verdict "insufficient evidence" (logistic, identity
        numbers reported as NaN — no fabricated metrics)
  macro   84 train rows ->  35 usable OOS rows, 5 usable periods,
        IC +0.368, Brier skill +0.006, verdict "insufficient evidence"
CONTRAST: v1.5.0's own retrain (evidence/phase1_retrain.txt) claimed q
435 / e 381 / macro 35 "OOS rows" — the e-head's 381 were in-sample
calibration fallback products (B-3's exact material). The new numbers
match v1.4.1's honest outcome (261 / 0 / 35). NO head passes: the
12-usable-period gate is unreachable on a 12-group pilot (max 5 test
folds) — that IS the honest result, and all three ship SHADOW.

GATE PASTES (all in evidence/):
- phase3_red.txt (red-first) · phase3_green.txt (309/309 OK) ·
  phase3_env_matrix.txt (9 cells ALL GREEN: 309 in the four env cells
  and all four pinned dates; the blocked-deps cell 294 ran + 2 clean
  skips after the C-6 submodule purge) · phase3_perturbation.txt (the
  M2 proof: every fold's selected set bit-identical under test-fold
  label+value perturbation; the permanent tests + the side-by-side
  generator paste) · phase3_retrain.txt (above) · phase3_tree_check.txt
  (ENGINES.sha256 sha256sum -c OK x3 + per-file MATCH paste; suite
  OK; the retrained heads SHADOW; CONFIG diff vs v1.5.0 = ZERO key
  changes, only phase-2's seven rationale disclosures).
- ML reports carry model_sha256 + dataset_sha256 (verified equal to the
  actual npz bytes at retrain time — checked in-tree after the retrain:
  q/e/macro all MATCH; verdict_basis digests equal).

ACCOUNTING (B-6 is now FULLY closed on both halves):
- Ported HERE (phase 3): M1, M2, M3, M4, M5 + B8's ML-load-hardening
  half (finite base_rate/calib at load, non-finite probability drops
  the head, adjustment isfinite belt) + the two deferred fixtures.
- B-6's full checklist now reads: B1-B8 (phase 2 decision layer + B8
  atomic writes), M1-M5 + B8-ML (phase 3), P-5 (phase 2), the 35
  regression tests (phase 2's share) + 21 new phase-3 tests, the 8
  hunt scripts (phase 1-2). The v1.4.1 port list is COMPLETE except the
  items v1.4.1 itself shipped as owner proposals (B-7's P-1..P-6 opt-
  ins — spec 3.2-3.4, NOT ports by design).
- Suite 288 -> 309 (+21: 16 in TestMLGatesPhase3, 4 in TestMLLoadB8,
  +1 TestFeatureCap perturbation case; net of the rewritten selection
  tests; no test deleted; fixture changes justified in
  evidence/fixture_changes.md).

DEFECTS (defects.md updated)
- B-3 -> FIXED (phase 3). B-4 -> FIXED (phase 3). B-6 -> CLOSED (both
  halves done; port_map.md's execution records name every item).
- C-6 -> FILLED + FIXED (the matrix hermeticity hole + the clean skip).
- C-7 opened: the shipped e-head is UNCALIBRATED (identity calib) and
  its verdict is "insufficient evidence" — the artifact is honest but
  inert; the release notes (phase 9) must state that the e-head ships
  UNUSABLE-pending-data, not "calibrated with 0 rows".
- B-7 (b, c-stop, d), B-8, B-9, B-10, C-4, C-5 unchanged (later
  phases per the plan).

NOTES / LIMITS (honest)
- The report's dataset_sha256 is the npz's 12-hex sha PREFIX (the
  v1.5.0 schema's own convention — v1.4.1 identical); both sides of
  every check compare like-for-like, so the pin is exact within its
  width, and the FULL 64-hex model_sha256 is on the same report.
- The M4 strengthening over v1.4.1 (GBM winner re-based to the shared
  row set) and the stricter --activate dataset pin are deliberate
  prompt-driven deltas, disclosed in port_map.md's execution record.
- The verdict vocabulary is three-valued now (beats / insufficient
  evidence / fails); --activate still accepts ONLY "beats" (the load
  side likewise). A forged "beats" with TRUE hashes still activates —
  activation is the owner's manual act on the owner's machine; the
  hashes bind the report to the artifacts, they do not certify the
  verdict's honesty (that is what the metrics blocks are for).
- The retrained q-head is a GBM winner: its joblib sidecar carries the
  sidecar_sha256 pin; the loader's verified-bytes unpickle path covers
  it (TestSidecarPin + the new pin tests).
- "ML dataset v2" (spec §4: full universe, PIT fundamentals, 36+
  month-ends) is NOT this phase — it is the later workstream B-9
  tracks (phases 4-9); the pilot dataset (12 dates, tech sector) is
  what the honest retrain used, as disclosed.

DELIVERABLE
- wip_phase3.zip (this tree + the rebuilt WIP MANIFEST.txt; sha256
  printed in the delivery message; the release manifest is rebuilt at
  phase 9).

PHASE 3 STATUS: COMPLETE

## PHASE 4 — B-7 close-out: the weird rules (P-1..P-6 + hunt)

Date: 2026-11-14 (Africa/Casablanca). Input: wip_phase3.zip (verified
byte-identical to this tree before work started: 143/143 files, sha256
match, no extras). Spec: 3.2-3.4 + section 10 defaults. Red-first
discipline throughout; every item below has its failing test pasted in
evidence/phase4_red.txt (35 red: 17 FAIL + 18 ERROR) before the fix.

WHAT WAS DONE (phase-4 prompt items 1-8)
- Item 1 (P-1, missing-E): CONFIG RULESET ("legacy" default) +
  E_MISSING_V2 (0.0) + --ruleset {legacy,v2}. v2 scores a missing E as
  the FIXED conservative fill through the SAME blend (weak
  renormalisation included). Invariant tests: base(missing) <=
  base(observed) for every observed E >= 0, weak and non-weak, through
  _base_conviction AND through the full fuse; fuzz invariant I5b added to
  scripts/fuzz_decisions.py (4800 fuzzed (q,e,weak) cases, 0 violations).
  Legacy stays default and the header prints, verbatim:
  "RULESET legacy - missing-E advantage ACTIVE (UNVALIDATED)"; v2 prints
  the fill. CLI override is set once per run with a _CfgKeyRestore guard
  (P2-3 discipline — test_ruleset_run_no_config_leak).
- Item 2 (P-3, stop): CONFIG EARNINGS_STOP_K (2.0, pre-registered
  mid-grid; the spec 5.8 grid backtest is later-phase work) +
  _stop_price(): stop = entry x (1 - k x ann vol x sqrt(hold/365)), vol =
  the sizer's trailing-126-td estimate off the engine's OWN price cache
  (EarningsLayer._plan_map fetches it per planned name; offline serves the
  cache). "No vol -> no stop" prints [W_NO_VOL_NO_STOP] + a fix command
  on the signal warning — never a silent None (skip/closed rows with no
  entry price carry no stop and no warning: nothing to stop). The stop is
  DISPLAY/plan information only — no decision logic reads it.
- Item 3 (B-7c, TP): EarningsLayer.run now passes hold_days /
  take_profit / min_score from CONFIG to eng.analyze(...) — the trade
  backtest and the live signals() plan read the SAME EARNINGS_TP (the
  engine's own 0.20 default is never reached). Tests record the full
  kwargs of BOTH calls and assert equality + CONFIG flow-through + a
  grep-proof that no hard-coded take_profit survives in master.py.
- Item 4 (P-2, sizing): CONFIG RISK_SIZING_MODE ("legacy" default) +
  RISK_VOL_TARGET (0.15) + --sizing {legacy,vol_target}.
  size_portfolio(..., mode=): vol_target keeps the SAME inverse-vol
  weights, name cap, sector cap and DD veto, but expresses the
  correlation awareness as a volatility target — gross multiplier g =
  min(target / (budget x unit-vol), 1) on the ABSOLUTE scale (the same
  scale the legacy est-DD veto compares; no leverage). DD-guard-can-fire
  is PROVEN: legacy hostile book (12 names, 300% vols, rho 0.10) vetoes
  (test_vol_target_keeps_the_dd_veto + the live paste in the gate); under
  vol_target the veto fires exactly when the target is looser than the DD
  envelope (VOL_TARGET=0.25 -> est_dd 0.50 > 0.30 -> stand-down, with the
  envelope note; test_vol_target_veto_can_fire_too). With the shipped
  coherent CONFIG the at-target est_dd EQUALS the veto line (structural
  property, disclosed). Every looser-than-legacy deployment prints
  "looser than norm by X%" with X computed from the two actual grosses
  (test_looser_than_norm_label_and_arithmetic reproduces the label
  exactly). Edge inputs tested: zero/one names, all-inf/NaN vols,
  NaN/negative budget, sector extremes. Legacy mode is byte-identical
  (test_legacy_mode_is_unchanged).
- Item 5 (P-4, ADV): FEASIBILITY PROBE FIRST, as demanded:
  scripts/adv_probe.py checks the engine px-cache CSV columns AND both
  engine sources for a Volume column. Verdict: ADV UNAVAILABLE — no
  readable feed carries volume, so the ADV cap and min-ADV exclusion are
  NOT implemented and NOT estimated; the fact is LOUD
  ([W_ADV_UNAVAILABLE] on the --doctor adv line + the probe banner) and
  the §3.4 liquidity-limit grid cell is marked UNANSWERABLE pending an
  engine-side volume feed (owner decision; engines untouched).
- Item 6 (P-6, doors): the doors compare UNROUNDED conviction under
  ruleset v2 (display stays rounded; Decision gains conviction_raw; the
  overlay pass re-gates on the raw value too; _cap_avoid_conviction caps
  raw as well so a blocked row can never re-cross a door). FLIP COUNT
  reported on the fixtures: stub universe 0/56 door-comparable decisions
  flip on the isolated rounding rule (5/71 change under FULL v2 =
  fill + doors); real pilot rows (latest date, 76 names): 2/60 flip
  door-only, 10/76 under full v2 (evidence/phase4_sensitivity_sweep.txt
  + the unit tests prove the door CAN flip: 59.98->60.0 legacy LONG vs
  v2 WATCH; 44.9605->45.0 legacy WATCH vs v2 AVOID).
- Item 7 (P-5, weak-E): the 0.5 value and its disclosure are KEPT; the
  ablation was run on the stub universe weak-path cases (scale 0.25:
  1/8 action flips, max conviction move 6.7; 0.75: 0/8, 5.4; 1.0: 0/8,
  9.8) and reported WITHOUT tuning — no winner picked, any change is an
  owner proposal.
- Item 8 (hunt): lint_hunt re-run (one new flagged constant: 365.0 in
  _stop_price — documented in the CONFIG rationale); manual hunt found
  the label-drift class: "(weak x0.5)", "(damped x0.5)" and the explain
  arithmetic hard-coded CONFIG values (P4-H1..H3 — all FIXED with red
  tests); the v2-weak interaction (P4-H4) and the veto epsilon (P4-H5)
  disclosed; P4-H6/P4-H7 registered. All in defects.md.

ALSO PRODUCED (the prompt's deliverable requirement)
- evidence/rules_changes.md: EVERY phase-4 CONFIG addition with its
  default + where production reads it, plus every NOT-a-CONFIG behaviour
  change (stop on live plan rows, TP single source incl. the backtest
  0.20->0.15 alignment, the +1e-9 veto boundary tolerance, label
  interpolations, funnel prior unification, the header RULESET row) and
  the two new stable W_ codes — so the Phase 8 CONFIG diff can verify
  "only disclosed additions" mechanically (phase4_config_diff.txt: 6
  VALUE lines, all <absent>->addition; zero existing values changed).

TESTS
- Suite 309 -> 348 (+39 phase-4 tests in 6 classes; no test deleted).
  Red run pasted (phase4_red.txt); green pasted (phase4_green.txt, 348
  OK). Fuzz: seed 88117, 22000 cases, I5b added, 0 violations
  (phase4_fuzz.txt; the one reported I1-ml-scaled-range finding is the
  unchanged phase-2 baseline finding, byte-identical).
- Env matrix re-run: ALL CELLS GREEN incl. sklearn-blocked cell
  (phase4_env_matrix.txt). ENGINES.sha256: meds/quality/earnings_engine
  all MATCH (phase4_engines_sha256.txt) — no engine file touched.
- Rules register: 82 live / 3 disclosed / 0 dead, PASS
  (all 5 new keys LIVE).

DEFECTS (defects.md updated)
- B-7 -> CLOSED in phase 4 (itemised per sub-letter; (f) costs stays the
  C-4 release-notes obligation + the §5 backtest conventions).
- New: P4-H1..P4-H7 (three label-drift FIXES, three DISCLOSED, one
  CLOSED-as-disclosure).

NOTES / LIMITS (honest)
- The stop, the ruleset and the sizing mode are LIVE-SURFACE additions,
  not backtested ones: the spec's take-profit x stop-k x hold grid and
  the legacy-vs-vol_target comparison run in the §5 backtest phases;
  defaults stay pre-registered (mid-grid k=2.0, coherent target 0.15,
  legacy ruleset/sizer) precisely so nothing was picked by results.
- vol_target's DD veto is structurally unreachable at the shipped
  coherent CONFIG (realized vol <= target => est_dd <= RISK_MAX_EST_DD =
  the line): the veto remains as the guard for looser owner targets, and
  the coherence note fires before any at-target veto would.
- The flip counts are fixture-level (stub universe + the pilot's latest
  date), not the §5 backtest — the spec asks for the backtest numbers on
  a representative run AND the backtest; the latter is later-phase work
  tracked by B-9.
- ADV: the probe verdict is environment-honest (this sandbox's engine
  cache is cold; the source-level absence of any Volume column is the
  decisive fact and holds regardless of cache warmth).

NOTES ON EVIDENCE FILE NAMES (disclosed, fixed within this phase)
- The v1.5.0 lineage's own phase-4 artifacts (phase4_gate.txt /
  phase4_green.txt / phase4_config_diff.txt — the OLD build's reuse/PIT
  gate, its green run and its CONFIG diff) collided with this round's
  phase-4 names. They were overwritten by the FINAL ROUND files during
  this phase and RESTORED immediately under lineage-prefixed names:
  evidence/lineage_phase4_gate.txt, lineage_phase4_green.txt,
  lineage_phase4_config_diff.txt (byte-copies from wip_phase3.zip; the
  pristine originals also remain inside master_final.zip). The same was
  done for lineage_phase3_green.txt (overwritten by this round's phase 3
  in the lost prior context — recovered here for the same reason).
  No lineage artifact is lost from the v1.7.0 tree; defects.md carries
  the note as P4-H8.

DELIVERABLE
- wip_phase4.zip (this tree + the rebuilt WIP MANIFEST.txt; sha256
  printed in the delivery message; the release manifest is rebuilt at
  phase 9).

PHASE 4 STATUS: COMPLETE

================================================================================
PHASE 5 of 10 — C-1..C-5: colour switch, readable+colourful report, layout
tiers + goldens, visible errors + the new exit-code contract — closed
2026-11-14 (Africa/Casablanca). Input wip_phase4.zip VERIFIED byte-identical
(156/156 files, sha256 per file) before any work started.
================================================================================

WHAT WAS DONE (phase-5 prompt items C-1..C-5; red-first throughout —
65 of the 71 phase-5 tests were captured FAILING/ERRORING on the phase-4
tree BEFORE implementation: evidence/phase5_red.txt; the 6 pre-green
companions are listed there as regression anchors)

C-1 COLOUR SWITCH (closed)
- --color {auto,always,never} + --no-color + --plain; conflict is a usage
  error; precedence table implemented in _colour_choice() and tested ROW
  BY ROW (always beats NO_COLOR/pipes/dumb; auto: NO_COLOR beats
  FORCE_COLOR/CLICOLOR_FORCE which beat TERM=dumb; WT_SESSION/
  TERM_PROGRAM/ConEmuANSI are capable markers; FORCE_COLOR="0"/"" does
  not force). Depth: truecolor/256/16 detected, SAME bright 16-colour
  semantic palette at every depth. Windows VT via ctypes (no new
  dependency) with an honest fallback reason; posix returns (None,
  "not Windows"). AUTO-off prints exactly ONE dim top line with reason +
  fix ("colour off: stdout is not a TTY — use --color always"); explicit
  never/--plain is silent. NEVER emits escapes into a non-colour stream
  in auto (pipe test) while --color always works through pipes (the
  cat -v capture is the proof). --doctor gained the full colour
  diagnostic (isatty stdout/stderr, TERM, COLORTERM, NO_COLOR,
  FORCE_COLOR, CLICOLOR_FORCE, platform, depth, decision + reason).

C-2 READABLE + COLOURFUL (closed; boxed layout, chips, macro card,
sector table, decision table, risk footer and ALL flags kept)
- Bright palette: green ok/LONG/OK, yellow warn/WATCH/DEGRADED/STALE,
  red error/AVOID/veto, cyan headers+layer names, magenta ML/SHADOW,
  dim secondary, bold titles+tickers; never colour alone (glyph+word
  pairs); bars coloured on the ACTION door thresholds (single source).
- The DEGRADED layer lead is now its OWN status glyph (yellow ▲) — the
  green-check-next-to-DEGRADED bug is dead (red test first).
- One-line plain-English VERDICT under the header ("0 LONG / 0 WATCH /
  2 AVOID — quality had no data (...)") + a LEGEND line.
- No bare '?' / 'n/sel' / 'nodata': cells say n/a, reasons travel in
  warnings/REASONS.
- Staleness is a status: STALE_STATUS_DAYS=7 (new CONFIG, display-only;
  the FRESHNESS_* logic gates untouched) — a 14-day-old macro cache now
  reads "STALE 14d" in yellow, never OK.
- ML line: "SHADOW (n=974 train rows)" in magenta (was "SHADOW(n 974)").
- Stub renders say SYNTHETIC (banner + DATA SOURCES + 'SYNTHETIC-stub'
  engine labels — the owner's render-level 'vstub' token is gone; P5-H2).

C-3 LAYOUT (closed)
- MAX_TERM_WIDTH 110 -> 160 (DISCLOSED VALUE CHANGE, rules_changes.md);
  --width range message follows CONFIG. Widths 40/70/110/160 all tested:
  no two values join (cells padded by DISPLAY width with mandatory >=1
  space; _disp_width/_pad are ANSI-aware and wide-char aware — CJK rows
  bounded), ellipsis truncation everywhere.
- Tested column-drop priority: REASONS (>=120) -> FLAGS (>=100) ->
  MACRO (>=80) -> WT/SECTOR (>=70); # / TICKER / ACTION / CONV / Q / E
  never drop. (The 70-95 tier changed from FLAGS-at-70 to MACRO-at-80:
  display-only, R2-justified test updates.)
- Header provenance cells wrap as UNITS (a lone status word can never
  strand); every macro-card line is width-safe (the 'excluded (credit
  OFF)' line used to overflow at 40 — red test first).

C-4 MODES + GOLDENS (closed)
- Modes: colour (--color always), --plain (= --no-color: no decoration
  beyond the box — the report adds none, asserted), --ascii (pure ASCII,
  box becomes +---+, no Unicode).
- goldens/golden_{colour,plain,ascii}_{40,70,110,160}.txt — 12
  byte-exact fixtures from REAL CLI stub runs (MASTER_STUBS=1,
  MASTER_NET=offline) under a FROZEN CLOCK (2026-11-13) via
  scripts/make_goldens.py; regeneration ONLY with --regen (refuses
  otherwise — tested). DISCLOSED masking, nothing else: ISO dates ->
  FROZEN-DATE (no golden contains a date; the guard test has a FAILING
  negative control — an injected date IS detected), wall-clock
  durations -> Xs. Tested: byte-exact re-capture; strip_ansi(colour) ==
  plain; SYNTHETIC present; locale/terminal independence (LC_ALL, TERM,
  COLUMNS); sklearn independence (blocking shim). Goldens never touch
  locale/terminal/sklearn: stub layers import none of them.

C-5 ERRORS MUST BE VISIBLE (closed)
- EVERY run ends with ERRORS & WARNINGS: entries carry layer · stable
  CODE · what · why · the EXACT fix command (the fix is never truncated
  away — it renders on its own line); clean = green "0 errors, 0
  warnings". Errors ALSO go to STDERR (one line per error, both in
  report and --json mode). No traceback without --debug (new flag;
  --verbose kept as alias).
- Per-provider network diagnosis: the owner's exact tail
  ("provider_errors:NETWORK_ERROR; sec_edgar=cik_map_failed;
  yahoo_chart=net:offline") now renders as classified entries
  (E_NET_OFFLINE / W_NET_DOWN / W_RATE_LIMIT with Retry-After honoured
  in the text). DATA SOURCES line: layer -> live/cache/SYNTHETIC -> age
  (+STALE) and the macro path (FRED key -> API; no key -> public
  fredgraph.csv; cache with AGE when cold). A missing FRED key is NOT
  an error.
- Central code registry: codes.py (module) + the RUNBOOK table — every
  entry has severity/layer/what/why/fix; the scanner test fails if a
  used code is missing or lacks a fix, with a negative control; the
  docs test fails if RUNBOOK drifts from the registry.
- 12 injected-fault tests: network down, rate limit, missing/stale
  cache, missing sklearn, corrupt model (head UNAVAILABLE), missing
  earnings, W_ADV_UNAVAILABLE, W_RHO_FALLBACK, legacy-rule warnings
  (RULESET label + W_NO_VOL_NO_STOP), engine hash mismatch, unwritable
  cache, no-result NO-GO — each asserts the entry, the code and the fix
  command.
- EXIT CODES (deliberate contract change, mapped in CHANGELOG, --help
  and --doctor; every affected test re-pointed with an R2 justification
  comment — no test deleted, no assertion weakened): 0 clean · 1
  degraded (result produced + warnings, incl. ml head UNAVAILABLE) ·
  2 usage/config (was 64) · 3 network · 4 no result/NO-GO (was 2) · 65
  replay · 70 unexpected internal (was 1) · 130 Ctrl-C. doctor/--check
  health failure = 1. run_replay ACCEPTS a replayed run's exit 1 (the
  ranking comparison is the gate; 4+ is still a replay failure). Each
  code has a real triggering run pasted (phase5_gate_exit_codes.txt:
  0/1/2/3/4 live; 65/70/130 via the suite tests that trigger them).
- --doctor stays ONE screen: colour diagnostic, exit-code table, engine
  hashes, head states, cache ages, network probe, NEXT action.

TESTS
- Suite 348 -> 419 (+71 phase-5 tests; no test deleted). Red run pasted
  (phase5_red.txt: 65 RED — 19 FAIL + 46 ERROR — plus the 6 pre-green
  anchors); green pasted (phase5_green.txt, 419 OK). Env matrix re-run
  ALL 9 CELLS GREEN (phase5_env_matrix.txt; the two hermeticity holes it
  caught — a date-sensitive exit assertion and a MASTER_NET-leaking
  exit-3 test — were fixed, not skipped). ENGINES.sha256: meds/quality/
  earnings_engine all MATCH (phase5_engines_sha256.txt) — no engine
  touched. CONFIG diff vs the phase-4 tree: exactly the disclosed pair
  (MAX_TERM_WIDTH 110->160, STALE_STATUS_DAYS added —
  phase5_config_diff.txt).

DEFECTS (defects.md updated)
- C-1..C-5 -> FIXED. New: P5-H1 (lineage phase5_* collision, fixed
  preemptively), P5-H2 ('vstub' render-level reproduction, fixed),
  P5-H3 (W_UNUSUAL for two cosmetic notes, disclosed), P5-H4 (golden
  masking, disclosed by design). C-4/C-7 (release-notes obligations)
  and B-8/B-9/B-10 carried.

NOTES / LIMITS (honest)
- Windows VT: coded per spec with ctypes + capability markers, tested
  against fakes on posix (success, failure, not-applicable paths); NOT
  verified on a real Windows console in this sandbox — owner command:
  `python3 master.py --doctor` on the Windows terminal (the colour
  diagnostic prints the VT note + the decision with its reason).
- Truecolor/256 depths: detected and reported; the palette is
  intentionally the SAME 16-colour semantics at every depth (per spec),
  so no depth-specific rendering exists to verify visually.
- The stub goldens pin the RENDER of stub data; real-engine renders
  still vary with live data (by design — goldens are C-4 fixtures, not
  a live-data snapshot).
- W_UNUSUAL is the honest catch-all for unclassifiable warnings
  (P5-H3): two known cosmetic notes currently land there.
- The exit-code change is a CONTRACT change: external scripts keyed on
  the old 64/2/1 must be re-pointed (the doctor exit table + CHANGELOG
  carry the mapping; the owner's own table matches the new contract).

DELIVERABLE
- wip_phase5.zip (this tree + the rebuilt WIP MANIFEST.txt; sha256
  printed in the delivery message; the release manifest is rebuilt at
  phase 9).

PHASE 5 STATUS: COMPLETE


## PHASE 6 — the §5 integration backtest (FINAL ROUND)

Date: 2026-11-14 (Africa/Casablanca). Base: the phase-5 tree (verified
content-identical to wip_phase5.zip; the zip's two empty cache dirs
data/, meds_cache/ carry no files).

WHAT WAS DONE
- master.py --backtest (+ --backtest-rerun/--backtest-dataset/
  --backtest-out): consumes the recorded per-date run_pipeline harvests
  (ml_data/cache/dates/*.json, REAL-DERIVED cached) or re-decides via
  DIRECT run_pipeline calls; prereg §6 conventions executed (equal-weight
  LONG book, next-open windows, 10 bps/side + 5/10/25/50, cash zero, no
  leverage); prereg §7 gates graded; prereg §3 lockbox (last 6 month-ends)
  evaluated exactly once, after the amendment, with no tuning following.
- preregistration.md AMENDMENT 1 (dated): dataset sha256 pinned before
  the first evidence result was read; the red-test sequence disclosed
  inside it.
- Tests 419 -> 426, red-first (7 RED captured; 6 assert failures + 1
  error). Codes W_BT_DATE_SKIPPED/W_BT_FIXTURE_ONLY registered (codes.py
  + RUNBOOK table + scanner/docs tests).
- The official evidence run: evidence/phase6_backtest_run.txt (exit 0,
  0.5 s, offline, zero sockets) — verdict "no edge demonstrated", Q5 =
  PARTLY; every gate number and ablation disclosure lives there and in
  phase6_backtest_report.md/.json. No engine touched
  (ENGINES.sha256 MATCH x3 re-verified after the phase).
- Observation (not a defect): during the 4 defensive-regime month-ends
  the macro risk budget held the book 100% cash — real recorded behaviour
  of the macro layer, visible in the per-date table.

DEFECTS
- In-phase fixes (P6-H1..H5, all caught pre-evidence by red tests or the
  shakedown run): PRNG call shape; MDD peak-index snapshot; avg-holding
  consecutive run-lengths; bootstrap seed f-string literal; float-repr
  formatting. B-9's full-universe build stays OPEN (the backtest runs
  fixture-class only — loud W_BT_FIXTURE_ONLY + owner command). C-4's
  release-notes obligation narrows: the backtest's cost conventions now
  exist; the LIVE engine still has no cost model and the release notes
  must still say so. C-7 unchanged.

DELIVERABLE
- wip_phase6.zip (this tree + rebuilt WIP MANIFEST.txt; sha256 printed
  in the delivery message).

PHASE 6 STATUS: COMPLETE


## PHASE 7 — B-8 speed honesty + B-9 verify-or-mark (FINAL ROUND)

Date: 2026-11-14 (Africa/Casablanca). Base: the phase-6 tree.

WHAT WAS DONE
- B-8: real measurements on this sandbox (commands in the evidence):
  import 0.14 s wall / 17 ms cumulative; selftest 432 tests 16.8 s; stub
  0.38 s; warm single name 4.2 s; warm 5-name 5.2 s; warm single-sector
  tech 16.3 s; backtest re-run 0.5 s. Full-universe warm standard run:
  not completed in the 560-580 s per-command budget (twice attempted,
  honestly recorded; lineage reference 73 s + owner command). bench.py
  run twice — [a][b][c] pasted (phase7_bench_partial.txt), [d] killed by
  the session budget (exit 124). Q8 = MEASURED, machine-bound, targets
  MET except the full-universe number (unmeasured here, command shown).
- B-9 (1): online-vs-offline identity on a real cache VERIFIED
  (scripts/phase7_online_offline.py; 5 decisions identical).
- B-9 (2): freeze/replay with real runs VERIFIED (exit 0 identical;
  tamper -> exit 65). The P7-H1 budget bug was found THROUGH this real
  run (replay failed -> root-caused -> red test -> fix -> re-verified).
- B-9 (3): zero-socket tests re-run OK (phase7_zero_inet.txt).
- B-9 (4): scripts/release_gate.py (the placeholder mechanism) + 5
  suite tests pinning its logic; real-tree run FAILs on the phase-9
  obligations exactly as designed (phase7_release_gate.txt).
- Caches warmed this session (real network, SEC_USER_AGENT set):
  watchlist 22 + tech pool 92 names; data/cache excluded from zips via
  build_manifest.py (runtime state, not release files).

DEFECTS
- P7-H1 (FIXED, red-tested): freeze budget double-count + silent
  starvation (see CHANGELOG). P7-OBS: sec.gov 403s contactless UA —
  documented, env var is the fix, RUNBOOK row due phase 9.

DELIVERABLE
- wip_phase7.zip (sha256 printed in the delivery message).

PHASE 7 STATUS: COMPLETE


## PHASE 8 — B-10 robustness close-out (FINAL ROUND)

Date: 2026-11-14 (Africa/Casablanca). Base: the phase-7 tree.

WHAT WAS DONE
- The six scripts run on the new version, twice (first pass -> findings
  -> fixes -> final pass), every output pasted to evidence/phase8_*:
  lint_hunt (rc=0; 3 dead-key lines = P8-D1 disclosed), fuzz_decisions
  (rc=0; 22000 cases; I1 carried DISCLOSED; I5b 0/4800), sensitivity_sweep
  (rc=0; every CONFIG sweep line clean; W_Q/W_E/E_MISSING_HAIRCUT real
  sensitivities reported as evidence), diff_checks (rc=0 after P8-H1;
  D1 table/JSON/CSV agree + determinism IDENTICAL; D2 API shapes OK;
  D3 VERIFIED on the real cache via the phase-7 scripted comparison;
  D4 features present + suite harness), rules_register_check (PASS:
  83 live / 3 disclosed / 0 dead) + its negative control (the planted
  ZZ_PLANTED_DEAD_KEY is caught, FAIL, exit 1 — after P8-H2 fixed the
  control's own harness), test_env_matrix (ALL 9 CELLS GREEN, 432 tests
  per cell, after P8-H3/P8-H4 fixed the two date/cache hermeticity holes
  the matrix caught).
- CONFIG diff (v1.5.0 vs current): exactly the 8 disclosed rules_changes.md
  lines, zero undisclosed (phase8_config_diff.txt).
- Tests: 432 green (300+ met with real tests); no padding, no weakening;
  the two fixes strengthened tests.
- ENGINES.sha256 MATCH x3 (phase8_engines_sha256.txt) — no engine touched.

DELIVERABLE
- wip_phase8.zip (sha256 printed in the delivery message).

PHASE 8 STATUS: COMPLETE


## PHASE 9 — C-6 + D + E: the release package (FINAL ROUND)

Date: 2026-11-14 (Africa/Casablanca). Base: the phase-8 tree.

WHAT WAS DONE
- C-6: export-contract locks (3 tests: JSON never NaN; JSON/CSV schema
  = v1.5.0 frozen baselines + additions only); docs/CLI.md with the
  real ANSI colour sample (SGR spelled out, screenshot-free) + the plain
  version, both captured this session.
- D: RUNBOOK.md -> the ONE-PAGE runbook (116 lines; every command
  executed this session with real last lines + times; 8 sections; the
  10-row troubleshooting table with exact CLI messages); everything
  else relocated verbatim to docs/ADVANCED.md; the registry docs test
  re-pointed; test_runbook_is_one_page added.
- E: HANDOFF.txt rewritten (3112 pure-ASCII chars; no PLACEHOLDER; the
  ZIP SHA256 release wording; ml_train agreement; C-4/C-5/C-7 closed in
  it); release_gate.py PASS on the tree; the release manifest rebuilt
  (213 files, ALL MATCH); clean-dir verification pasted
  (evidence/phase9_clean_dir_verify.txt); final_master_d.zip built with
  its sha256 printed in the delivery message (never embedded).
- NOTE: phases 6/7/8 were executed in THIS session (their execution
  debt from the lost-context series is disclosed in the phase-6/7/8
  sections above; every phase's evidence and zip are real).

PHASE 9 STATUS: COMPLETE

- Clean-dir verification (the phase-9 gate): final_master_d.zip unpacked
  to an empty directory -> python3 test_master.py: Ran 436 tests in
  17.1s OK; env matrix ALL 9 CELLS GREEN (436 per cell, 421+2 skipped
  in the sklearn-blocked cell); --doctor healthy (engines+hashes OK,
  network reachable, heads SHADOW); sha256sum -c ENGINES.sha256 MATCH x3
  (evidence/phase9_clean_dir_verify.txt; the transcript lives OUTSIDE
  the zip by design - a zip cannot carry its own verification record
  without an infinite regress).
- The release zip: download/final_master_d.zip, sha256 printed in the
  final delivery message (never embedded in the zip).

## M.E. v1.8.0 — W1 (module split + code quality)

Date: 2026-11-18 (Africa/Casablanca). Base: final_master_d.zip (sha256
86a62fca9930ffd7e9e2371ed13eb918243b73030af1265fd138c97bf4898da9).
Rules: R1-R24 as v1.8.0; engines never opened (sha256sum -c OK x3 at
entry, evidence/w18_entry_engines.txt).

DONE
- W0 (entry): plan_v18.md with the re-verified §2 facts (63/21-td story
  corrected with prereg line 69 + master.py:6309 pointers; 4 API hosts
  listed with key requirements; MANIFEST 214 entries; suite 436 OK
  non-root; master.py 7,381 lines). Defect D-18-001 opened (the shipped
  zip's 2 evidence files mismatch its own MANIFEST).
- W1 (split): RED first (test_master.TestModuleSplitV18 — 1 failure + 2
  errors, evidence/w18_red.txt), then the deterministic executor
  scripts/w18_split_exec.py (boundary-asserted line moves; evidence/
  w18_split_analysis.txt shows the AST dependency matrix driving the
  boundaries). Result: master.py 7,382 -> 3,902 lines; me/core.py 1,156,
  me/render.py 1,257, me/backtest.py 617, me/cli.py 316, me/risk.py 385,
  me/errors.py 52, me/__init__.py 4.
- R15 proof: fuzz_decisions.py output byte-identical to the W0 baseline
  (22,000 cases, seed 88117); freeze/replay exit 0; the frozen ranking's
  decision hash 2734886b39877ad67586b0a11c278ad4e199a91d8dbca8993ff5fb8f
  2972595 UNCHANGED before/after the split AND after the dead-code pass.
- Goldens regenerated with the ONLY change = header version string
  (evidence/w18_goldens_diff.txt, 12 files, one line each; justification
  in evidence/w18_goldens_justification.md).
- Tests: 436 -> 440 (+4: test_me_modules_importable_and_reexported,
  test_me_modules_no_master_import_at_module_level,
  test_me_public_api_documented, test_script_entry_survives_split). No
  assertion weakened; the no-master-import test checks MODULE level
  only (the two late-bound seams import master inside functions BY
  DESIGN — disclosed in the test docstring).
- Lint: pyflakes clean on me/*.py; master.py carries 77 intentional
  re-export 'unused import' warnings (the compat contract — listed as a
  known limit, not silenced); dead code removed (base_i, today, m
  locals; 3 f-strings without placeholders); compileall clean;
  lint_hunt.py DEAD-CONFIG-KEYS now scans master.py + me/ (0 dead);
  rules_register_check.py same scope update + CONFIG-singleton
  snapshot/restore around --master exec (the negative control's planted
  key could leak into the real tree after the split — fixed and the
  negative control re-verified FAILing as designed).
- CHANGELOG v1.8.0-dev entry added. docs/CLI.md and docs/ADVANCED.md
  describe the CLI surface and behaviour, not file layout (verified by
  grep — no stale single-file claims to correct); their full refresh is
  W7 deliverable. RUNBOOK commands all name master.py, which stays the
  entry point — unchanged.

NOT VERIFIED (owner-run, R11/R12): nothing in W1 needs the network; all
checks ran offline in this sandbox. Real-data speed belongs to W2's
owner bench script.

OPEN (for later workstreams): W2 speed pass, W3 UI fixes (data: line
"stub n/a OK n/a", name truncation "ml_train SYNTHETI...", wrapped-line
indentation — all reproduced in evidence/plan_v18.md), W4 --bt-start/
--bt-end, W5 risk controls, W6 owner tooling, W7 release.

W1 STATUS: COMPLETE

## M.E. v1.8.0 — W2 (speed, agent-safe)

Date: 2026-11-18. Base: the W1 tree (wip_w1.zip, 71ea3135...).

DONE
- Profiles (R9-labelled fixtures; evidence/w18_perf.md): stub pipeline
  0.422 s (0.333 s = importing the stub harness in test_master.py, by
  contract; left alone); backtest 0.83 s; ml_train 3.82 s (3.03 s =
  sklearn import chain; fit 0.52 s); ml_dataset --verify 0.30 s
  (import-dominated).
- THE code-owned hotspot: me/backtest re-read each npz member per row
  (3,170 NpzFile.__getitem__ calls = 0.50 s of 0.74 s). Fixed by hoist-
  ing as_of/ret_63/tickers once before the loop. Before/after table in
  evidence/w18_perf.md: --backtest 0.83 -> 0.31 s (-62%, fixture);
  backtest report byte-identical apart from the config-hash line (now
  deterministic — see D-18-002).
- D-18-002 (FOUND in W2): the CONFIG identity hash was PYTHONHASHSEED-
  dependent (8 frozensets str()'ed in arbitrary order; 5 different
  hashes observed across 5 identical-tree runs). Fixed with the shared
  me.core._canonical_json recipe in me/backtest + ml_dataset + ml_train;
  RED->GREEN TestConfigHashDeterministic (2 subprocesses, seeds 1 vs 2
  vs random). The backtest report now says pre-v1.8.0 build hashes are
  not comparable.
- Persistent HTTP cache with TTL: DECLINED with reasons (master owns no
  data fetch — probes only; the engines own the fetches and their
  caches, and they are read-only, R1). In evidence/w18_perf.md.
- scripts/owner_bench.sh + scripts/owner_bench.ps1 (bash -n verified,
  executable bit set): 7 cells incl. the online standard run and the
  dataset build that only the owner can time. Output lands in
  owner_results/ — AWAITING OWNER DATA.
- Gates after W2: suite 442 OK (436 + 6 new v1.8.0 tests); fuzz
  byte-identical; freeze/replay exit 0; frozen decision hash
  2734886b...972595 unchanged.

W2 STATUS: COMPLETE (real-data speed = AWAITING OWNER DATA by design)

## M.E. v1.8.0 — W3 (CLI and UI)

Date: 2026-11-18. Base: the W2 tree (wip_w2.zip, 242eee78...).

DONE (RED first: test_master.TestUiFixesV18, 9 tests, 7 failures + 2
errors on the W2 tree — evidence in the suite run; then GREEN)
- FIX 1 'data: stub n/a OK n/a': header provenance cells are now
  LABELLED ('macro: stub · as-of n/a · OK · age n/a') and degrade by
  dropping FIELDS (96/64 width tiers), never slicing one.
- FIX 2 'ml_train SYNTHETI...': layer rows assemble cell-by-cell with
  drop-by-priority (extra -> cache -> elapsed); the engine-name column
  shortens on word/hyphen boundaries (_shorten_word) and every kept
  cell keeps >=1 space before the next — no glued cells at
  40/70/110/160 (test iterates all four).
- FIX 3 wrapped lines: _wrap glues separators to the FOLLOWING word —
  no dangling '·' at end-of-line, no separator-led continuation lines.
- FIX 3b DATA SOURCES: per-layer cells packed as units between ' · '
  (was one hard-truncated string cutting 'risk SYNTHET…' at w40).
- ADD summary card (_summary_card): verdict counts · risk class (the
  MacroState regime_class — never a dataclass repr, caught by the
  width-bounded tests) · warnings count · top picks; width-bounded by
  progressive field append.
- ADD --md FILE / --html FILE (me/render render_markdown/render_html;
  master writes them atomically after the report; additive flags R16;
  escaped HTML, no external assets, CONF_DIGITS formats via _fmt_num).
- ADD grouped --help: 7 argument groups (run selection / depth & speed
  / data source / layers & fusion / output & format / diagnostics /
  backtest & ml) — same flags, defaults, exit codes; display regrouping
  only.
- ADD _Progress ETA (label/total keywords; tick() paints 'name: i/n ·
  Xs · ETA Ys') and the Ctrl-C resume hint (_resume_hint: rerun the
  same command / --mode offline serves warm caches / --warm fills the
  rest) printed with exit 130.
- VERIFY --explain: already exists since v1.5 (_explain_block,
  per-layer breakdown + fusion arithmetic + provenance) — covered by
  test_stop_surfaces_in_signal_and_explain and the layout tests; not
  re-implemented, per R3.
- Goldens regenerated with a written justification per change
  (evidence/w18_w3_goldens_justification.md + w18_w3_goldens_diff.txt);
  colour==plain at every width re-verified by the generator and suite.

GATES: 451 tests OK (442 + 9 new W3 tests); fuzz output byte-identical
to baseline; freeze/replay exit 0, 5/5 identical; frozen decision hash
2734886b...972595 unchanged; ENGINES untouched (re-checked at the W3
checkpoint: sha256sum -c OK x3, evidence/w18_w3_engines.txt).

W3 STATUS: COMPLETE

## M.E. v1.8.0 — W4 (--bt-start/--bt-end: backtest on specific dates)

Date: 2026-11-18. Base: the W3 tree (wip_w3.zip, 96decd2c...).

DONE (RED first: test_master.TestBacktestWindowV18, 6 tests, all 6
failed on the W3 tree; then GREEN; full suite 457 OK — no-lookahead
tests included and green)
- me/cli.py: --bt-start/--bt-end YYYY-MM-DD (month-ends) in the
  'backtest & ml:' help group (additive flags, R16).
- me/backtest.py run_backtest: window validation (month-end format,
  start<=end) exiting 2 with exact reasons; empty-window case exits 2
  AND points the owner at `python3 ml_dataset.py --start/--end/--freq`
  (dates outside the dataset are an owner network build — the message
  says so); the descriptive window block printed BESIDE the full-span
  metrics with the R19 label 'descriptive sub-window — never a verdict;
  sub-windows are regime slices, reported as description only, never as
  evidence of skill'; window means over the same 63-td label windows
  with the 10 bps baseline.
- The runlog: evidence/backtest_runlog.jsonl — EVERY run appends one
  JSON line (ts, dates, window null-or-{start,end}, full/net/gross
  means, window net mean, config_hash, dataset); append-only.
- Absent flags: report body byte-identical
  (test_absent_flags_output_unchanged compares the full report body
  against the pre-W4 capture); decision hash/fuzz unaffected (render +
  backtest-only surface; fuzz byte-identical re-run in the W4 gate
  below).

W4 GATES: 457 tests OK; fuzz output byte-identical to baseline;
freeze/replay exit 0 (5/5); frozen decision hash 2734886b...972595
unchanged; ENGINES.sha256 OK x3 at checkpoint.

W4 STATUS: COMPLETE

## M.E. v1.8.0 — W5 (risk and sizing, opt-in)

Date: 2026-11-18. Base: the W4 tree (wip_w4.zip, 099aea42...).

DONE (RED first: test_master.TestRiskV18, 9 tests, 6 failures + 1 error
on the W4 tree; then GREEN; suite 466 OK)
- EXISTING controls re-verified as binding (tests already green since
  the v1.5/phase-4 port): position cap RISK_MAX_NAME_W, sector cap
  RISK_MAX_SECTOR_W (test: weights <= caps, capped-name asserts),
  vol_target opt-in sizing with the R20 'looser than norm by X%' label,
  the est-DD veto.
- NEW ADV participation guard (RISK_ADV_MAX_PARTICIPATION, opt-in via
  the sizer's advs kwarg — budget-unit ADVs; binds in
  test_adv_guard_binds_with_data: 0.2-unit ADV caps the name to 0.02;
  advs={} fires the loud W_ADV_UNAVAILABLE per name; advs ABSENT =
  byte-identical legacy path, R15). The pipeline-level loud ADV warning
  stays where phase 4 put it: --doctor's W_ADV_UNAVAILABLE line + the
  adv_probe verdict (no volume feed exists in the engines' caches —
  engine-side change out of scope, R1).
- NEW live cost model (W5 spec: 'shows gross and net'): the risk footer
  line 'costs: live plan is GROSS of costs — est round-trip 2 x 10
  bps/side ~0.20% one-off on the deployed X% (the backtest nets the
  same 10 bps/side; estimate, not a net-return claim)' — goldens
  regenerated with the written justification
  (evidence/w18_w5_goldens_justification.md; diff = that line only).
- NEW drawdown circuit-breaker with cooldown (--bt-breaker opt-in;
  RISK_DD_BREAKER_DD 0.10 / RISK_DD_BREAKER_COOLDOWN_W 2): walks the
  10-bps net equity curve, cash for the cooldown after the threshold
  crosses, then re-entry; prints 'breaker fired on N window(s) ... '
  or 'never fired on this curve' — a descriptive what-if, the
  preregistered default backtest unchanged (test_breaker_is_optin_only).
- NEW SPY series support: --bt-spy FILE + scripts/owner_fetch_spy.py
  (owner-run, Yahoo v8 chart endpoint, atomic write, exit 2 and
  nothing written on failure); the backtest aligns 3-month SPY window
  returns on the same month-end as-of dates, prints the series note +
  LONG-minus-SPY excess; SYNTHETIC-labelled files stay descriptive
  (R7) — a REAL owner series also answers prereg gate 3's SPY half
  (stated in the line). Absent file: 'SPY: NOT AVAILABLE' unchanged.
- NEW stress report on windows present in the dataset (descriptive,
  R19): the defensive/cash stretch, worst rolling 3-window net stretch
  + worst single window.
- CONFIG additions disclosed in evidence/rules_changes.md (3 opt-in
  keys, zero value changes); runlog now carries the window + breaker +
  spy fields? (window only — breaker/spy noted in the runlog via the
  standard flags record? NO: kept to the W4 fields; the breaker/spy
  runs append their own lines — runlog carries window; a breaker/spy
  marker added in a follow-up if the owner asks).

W5 GATES: 466 tests OK; fuzz byte-identical; freeze/replay exit 0;
frozen decision hash 2734886b...972595 unchanged; ENGINES OK x3.

W5 STATUS: COMPLETE

## M.E. v1.8.0 — W6 (data and ML tooling)

Date: 2026-11-18. Base: the W5 tree (wip_w5.zip, 0d67120a...).

DONE (RED first: test_master.TestW6DataTooling, 8 tests, all RED on the
W5 tree; then GREEN; suite 474 OK)
- REFUSALS (R7): ml_train AND --backtest REFUSE datasets whose manifest
  data_provenance is SYNTHETIC or absent — 4 RED->GREEN tests (two per
  tool, temp-dataset copies with mutated manifests). The unit-test valve
  MASTER_ALLOW_SYNTHETIC=1 lets the suite's own SYNTHETIC panels run
  (R7: fixtures are legal in unit tests, labelled loudly: the backtest
  prints 'SYNTHETIC DATASET ALLOWED... never a verdict', ml_train prints
  the same to stderr); production calls refuse by default. The suite's
  phase-6/phase-3 fixtures now DECLARE themselves SYNTHETIC in sibling
  manifest.json files (honest labelling instead of silent undeclared
  fixtures).
- ml_dataset.py writes data_provenance into every NEW manifest
  (class REAL-API unless MASTER_STUBS, apis list, note); the SHIPPED
  pilot's manifest was migrated additively to its TRUE provenance
  (REAL-API — phase-5 real-run evidence; the npz is untouched).
- FEATURE-STABILITY REPORT: ml_train writes stability_<head>.json
  beside validation_<head>.json — per-feature selection frequency
  across the walk-forward folds (per-fold train-window selection, M2);
  descriptive only, never a tuning signal (test asserts the file + keys
  on the shipped fixture).
- OWNER PACK (R12/W6): OWNER_RUN.md (43 lines, one page, commands in
  order incl. the verify step); scripts/owner_long_history.sh/.ps1
  (resumable ~10-year build under free-tier limits: 6 dates/pass,
  quota-exhaustion stops cleanly with the resume message, coverage line
  after every pass); scripts/owner_retrain.sh/.ps1 (retrain on the
  owner's sklearn — fixes the shipped-head 1.5.2-vs-1.9.1 mismatch;
  heads stay SHADOW, --activate stays manual);
  scripts/verify_owner_results.py (schema/rows/sha256/no-future-dates/
  provenance per file + the NEGATIVE CONTROL: a corrupted spy file
  must FAIL, exit 1, naming the corrupt file — test asserts exactly
  that). bash -n verified on all .sh.

W6 GATES: 474 tests OK; fuzz byte-identical; freeze/replay exit 0;
frozen decision hash 2734886b...972595 unchanged; ENGINES OK x3.

W6 STATUS: COMPLETE

## M.E. v1.8.0 — W7 (release)

Date: 2026-11-18. Base: the W6 tree (wip_w6.zip, b2e2544a...).

DONE
- RUNBOOK.md refreshed for v1.8.0 (120 lines = the gate limit; every
  quoted line re-executed this session; the wizard transcript's new home
  is prose + ADVANCED.md; v1.7.0-baseline commands keep their real
  2026-11-14 outputs, v1.8.0 surfaces carry 2026-11-18 outputs).
- HANDOFF.txt rewritten (3,415 ASCII chars, no PLACEHOLDER, ml_train
  1.1.0 agreement, the ZIP-SHA256 release wording, the known limits
  incl. the 77 intentional re-exports and the AWAITING OWNER DATA pack).
- docs/CLI.md (v1.8.0 flags + notes) and docs/ADVANCED.md (v1.8.0
  section: module map, runlog, provenance refusals, the owner pack,
  fixture-vs-real discipline) refreshed; CHANGELOG gained the W2-W6
  consolidated entry beside W1's.
- scripts/test_env_matrix.py: pin loops widened to the me/* modules
  (D-18-003 — the split had widened the clock readers; the Sunday cell
  caught it) + label updated. MATRIX: ALL 9 CELLS GREEN (474 per cell;
  459 + 2 skipped in the sklearn-blocked cell) — pasted in
  evidence/w18_env_matrix.txt.
- Final battery: suite 474 OK; fuzz byte-identical to the W0 baseline;
  freeze/replay exit 0 (5/5 identical); frozen decision hash
  2734886b...972595 unchanged; ENGINES.sha256 OK x3 (exit check).
- MANIFEST rebuilt (ALL MATCH); release_gate.py PASS; clean-dir
  verification on a fresh unpack of final_master_e.zip (suite + gate +
  engines + doctor) — evidence/w18_clean_dir_verify.txt; the zip's
  sha256 printed in the delivery message only, never inside the zip.

W7 STATUS: COMPLETE

---
## v1.8.1 (2026-11-19) — NETWORK RESILIENCE + REVIEW FIXES -> final_master_f.zip

Input final_master_e.zip (entry sha256 8f0204e56fc6703c53cae3251183277d
c6704bf16b4647e56f404092315caaf8; ENGINES.sha256 x3 MATCH at entry).
Workflows (checkpoints in download/: wip_v181_w0.zip, wip_v181_w1.zip
[tests red], wip_v181_w2.zip [green]):

- W0 facts re-verified with file:line (evidence/plan_v181.md): the six
  problem facts (900 s layer budget, soft deadline never kills workers,
  45-300 s engine timeouts, no per-host breaker, partial retry wrappers,
  non-daemon workers delaying exit) and all eight review-fix facts.
  evidence/net_paths.md maps EVERY engine network call + wrappability.
  prereg AMENDMENT 2 (dated, signed) appended BEFORE the F1 code ran.
- W1 the 70 new tests written RED-first (evidence/v181_red.txt).
- W2 me/netguard.py + CONFIG (13 additions + the ordered F6 value
  change) + master wiring; full suite GREEN (evidence/v181_green.txt,
  544 tests).
- W3 F1-F8 landed (tests green; F6 config-gate re-point justified).
- W4 codes registry (9 new), docs/ADVANCED.md table regenerated,
  docs/CLI.md + the SIMULATED FETCH HEALTH capture, RUNBOOK 120 lines,
  HANDOFF 3,117 chars, OWNER_RUN.md (net check step 0, overrides
  command, retry-failed), scripts/owner_net_check.sh/.ps1,
  scripts/universe_override.py, data/universe_overrides.csv,
  requirements.txt pins (F7).
- W5 gates: env matrix 9 cells green (evidence/v181_env_matrix.txt);
  decision hashes UNCHANGED with the network layer on and healthy
  (evidence/v181_decision_hash.txt, hash a023714c...c35e8 on both
  trees); CONFIG diff vs v1.8.0 = 13 additions + 1 value change only
  (evidence/v181_config_diff_v180.txt); rules register 100 live /
  0 dead; lint + fuzz green; goldens regenerated with written
  justification (evidence/v181_goldens_justification.md); red-team
  five checks (evidence/v181_redteam.md). Engines re-hashed at exit.

## v1.8.2 hardening pass (final_master_g) — COMPLETE

- W0 entry: all facts a-h CONFIRMED with file:line (evidence/plan_v182.md);
  ENGINES.sha256 matched at entry (hashes in plan_v182.md); MANIFEST 272/272;
  544 tests green x3 envs at entry.
- W1: RUN_BUDGET_BY_DEPTH + rate rule + NET_BROWNOUT_S + NET_PREFLIGHT_TOTAL_S;
  bounds written and test-asserted (evidence/net_bounds.md; 20 new tests).
- W2: yfinance engine-seam wrappers (fake-module tests; owner scripts
  extended); net_paths.md re-censused.
- W3: cadence-aware STALE display + refresh_failed provenance key.
- W4: zero W_UNUSUAL in stub/offline/outage runs (incl. pinned-date
  old-cache); 7 new codes; drift green.
- W5: --net flag with exit-2 conflicts; --mode compat-pinned.
- W6: OWNER_RUN tech groups; mismatch warning (fail-soft); header-only CSV.
- W7: version 1.8.2; RUNBOOK exactly 120 lines; HANDOFF 3,494 chars;
  goldens regenerated + justified; matrix 9 cells green (605 tests x9,
  evidence/v182_env_matrix.txt); decision hash UNCHANGED
  (evidence/v182_decision_hash.txt, a023714c...c35e8 both trees); CONFIG
  diff vs v1.8.1 = exactly the 6 new knobs
  (evidence/v182_config_diff_vs_v181.txt); claims audit
  (evidence/claims_audit.md); defects D-182-1..13 (evidence/defects.md);
  engines re-hashed at exit; manifest rebuilt; zip + sha256 after the
  last edit.
