evidence/port_map.md — PHASE 0 task 4: function-level port map,
v1.4.1 -> v1.5.0 (result to be named v1.7.0).

METHOD AND ITS LIMITS (read first)
- Neither zip ships a v1.4.0 tree (both carry only baseline/master_v1_1_0.py),
  so a literal `diff v1.4.0 v1.4.1` and `diff v1.4.0 v1.5.0` cannot be run.
  This map is built from:
  (a) v1.4.1's own CHANGELOG.md + HANDOFF.txt — the authoritative, function-
      named record of what v1.4.1 changed relative to its v1.4.0 base;
  (b) v1.5.0's CHANGELOG.md + HANDOFF.txt — the same for the final phase;
  (c) a REAL computed inventory diff between the two sibling trees
      (defs and test functions, this session):
        master.py    v141-only defs: _sha256_file
                     wip-only defs:  24 (net modes, probe, provenance,
                     freeze/replay/doctor, retries, snapshot, refresh plan)
        ml_train.py  v141-only defs: _inner_embargo_months, _inner_splits,
                     _label_horizon_td
                     wip-only defs:  _fit_z, select_features
        ml_dataset.py v141-only defs: _atomic_savez, _atomic_write_text
                     wip-only defs:  dry_run
        tests        186 common (the v1.4.0 base) · 35 v1.4.1-only (PORT
                     THESE) · 69 v1.5.0-only (keep, make env-robust)
  Every line reference below was verified by grep/read in this session.
- Conclusion from (c): the v1.5.0 final phase did NOT touch any B1-B6 fix
  site (sizer, NOW chip, overlay pass, MODES keys, _write_csv) — the port
  is mechanically clean, with the conflicts called out per row below.

--------------------------------------------------------------------------------
PORT TABLE (each row = one v1.4.1 fix; port = red test first, then fix)
--------------------------------------------------------------------------------
| ID | v1.4.1 change (function, v141 line) | v1.5.0 counterpart (wip line) | Conflict risk | Tests to port (red-first) |
|----|--------------------------------------|--------------------------------|---------------|---------------------------|
| B1 | size_portfolio: inf/NaN/<=0 vols -> MISSING semantics (peer-median / equal-weight fallback + note); no ZeroDivisionError on all-inf book (v141 master.py:1844) | size_portfolio (wip master.py:2083), same v1.4.0 shape (eff/8 at 2136-2137, est_dd at 2151) | LOW — sizer untouched by the final phase; port lands verbatim. Fuzz (v8 hunt: 75 all-inf ZeroDivision + 353 NaN-budget hits) re-creates the RED evidence on wip | test_b1_all_inf_vols_degrade_not_crash, test_b1_one_inf_vol_gets_peer_median_weight_and_note, test_b1_nan_and_negative_vols_treated_as_missing, test_b1_mixed_unusable_vols_never_leak_nan |
| B2 | silent guard-off disclosure: rho unavailable (1-2 names / <42 rows / corr error / non-finite rho_bar) -> notes + footer line + JSON rho_fallback/rho_used; DD estimate uses new CONFIG RISK_FALLBACK_RHO=0.5 (v141:435, 1961) | size_portfolio (wip:2083); NO RISK_FALLBACK_RHO key in wip CONFIG (grep: 0 hits) | LOW-MED — the disclosure lines must ALSO appear in v1.5.0's NEW surfaces (provenance lines, refresh report, freeze manifest JSON) so offline/replay outputs carry them; those surfaces did not exist in v1.4.1 | test_b2_two_names_rho_none_uses_fallback_rho_and_discloses, test_b2_single_name_book_discloses_and_estimates_dd, test_b2_rho_bar_short_history_returns_none, test_b2_rho_exception_path_discloses_through_layer |
| B3 | non-finite budget -> stand-down veto; risk_ctx_out emits null not NaN (JSON parseable); non-finite rho_bar rejected (v141:1992) | risk_ctx_out (wip:2162) | LOW — wip's JSON writer already null-sanitises (v1.2.0 defence) but the stand-down path is absent | test_b3_nan_budget_is_a_stand_down, test_b3_inf_budget_is_a_stand_down, test_b3_nonfinite_rho_bar_is_treated_as_unavailable |
| B4 | NOW chip bounded BOTH sides 0 <= days <= EARNINGS_MAX_AGE; future-dated report -> status open + future_report warning through signal warnings (v141:1346, 4 hits) | NOW-chip block (wip:1600-1615) — upper bound ONLY (wip:1609); zero future_report mentions; stop_px None row at wip:1620 unchanged | LOW-MED — warning must flow through v1.5.0's new per-name flag + stale-name reason surfaces too, and into provenance JSON | test_b4_now_chip_rejects_future_dated_reports, test_b4_future_report_warning_reaches_the_signal |
| B5 | _apply_overlays re-asserts blocked rows (AVOID + below-WATCH cap) once per decision BEFORE consulting signals (v141:2467, re-assert 2478-2489) | _apply_overlays (wip:2638) — no re-assert (grep "re-assert": 0 hits in wip) | LOW — overlay stage unchanged in v1.5.0; check the 69 wip-only tests for assertions the re-assert could flip (none known; fuzz is the oracle) | test_b5_blocked_long_is_reasserted_avoid_by_overlays, test_b5_consistent_blocked_row_is_untouched |
| B6 | dead CONFIG keys made live: MODES["standard"] reads EARNINGS_TOP_K + LAYER_TIMEOUT_S at import AND at _apply_mode time; EARNINGS_NATIVE_GRADES/CONF_DIGITS disclosed not-read; NEW scripts/rules_register_check.py (65 live / 2 disclosed / 0 dead) | MODES (wip:334) hard-codes standard {timeout 900.0, earnings_top 25} — keys dead AGAIN; _apply_mode (wip:4517) | HIGH — wip's _apply_mode was rewritten to carry EITHER net mode OR depth preset (final-phase H9 decision); the key-liveness fix must land inside that dual-purpose resolver. Register census numbers will differ (wip CONFIG grew +14 keys) — PASS condition stays "every key LIVE or DISCLOSED" | test_b6_mode_keys_drive_the_standard_mode, test_b6_documented_keys_disclose_their_status + port rules_register_check.py (its negative control catches a planted dead key) |
| B7 | suite determinism: 4 pinned dates green; MASTER_STUBS pinned in direct-main() tests; ml_train classes SKIP cleanly with sklearn/joblib blocked; scripts/test_env_matrix.py | test_master.py (wip: 4,304 lines, 256 tests) | HIGH — the fragile tests on wip are the FINAL PHASE'S OWN 69: the 7 named (offline+stubs), 5 sklearn-blocked, plus date-fragile TestFreshness/… (fact-check F19/C-3). Port v1.4.1's pinning technique onto the NEW tests + a WORKING env matrix (v141's FakeDate is dead code — C-2; the real pinning must also survive pandas Timestamp interop) | no single test: the gate is the env matrix (4 dates + blocked deps + 3 ambient envs, all green/skip-clean) |
| B8 | ML load hardening + atomic writes: base_rate finite in (0,1) + calib_a/b finite at load, REFUSED (v141 _ml_load_head:1541-1570); non-finite probability drops head (v141 _ml_predict:1632); atomic writes via tmp+os.replace — _write_csv (v141:4081), ml_dataset cache/manifest/npz (v141 _atomic_savez/_atomic_write_text), ml_train model+report (5 os.replace sites; v141 total 1+4+5) | _ml_load_head (wip:1815, has sidecar-pin + sklearn-version checks but NO finite base_rate/calib checks), _ml_predict (wip:1892), _write_csv (wip:4636); wip os.replace count: 0 / 0 / 0 across master/ml_dataset/ml_train | MEDIUM — wip ADDED new artifact writers v1.4.1 never saw (freeze manifest, meds snapshot materialisation, replay copies): atomic-write discipline must extend to them too ("atomic writes everywhere", spec 3.1); load checks slot in beside wip's existing pin checks | test_b8_bad_base_rate_refused_at_load, test_b8_nonfinite_calib_refused_at_load, test_b8_nan_probability_drops_head_with_note, test_b8_adjustment_skips_nonfinite_parts, test_b8_write_csv_crash_leaves_previous_file, test_b8_ml_train_save_model_crash_leaves_previous_file, test_b8_ml_dataset_atomic_helpers_crash_safe |
| M1 | inner-CV embargo target-aware: _inner_embargo_months(head) = ceil(label horizon/21) (q 3m / e 5m / macro 1m) from _label_horizon_td; _inner_splits exposed + property-tested; wired through _inner_oof(..., embargo_months) (v141 ml_train.py:128, 284, 302, 421) | _inner_oof (wip:248) — no embargo parameter; _inner_splits/_inner_embargo_months/_label_horizon_td absent | LOW-MED — wip's ml_train changed around FEATURE_CAP + sidecar pins; the inner-CV core is v1.4.0-shaped | test_m1_inner_embargo_is_target_aware, test_m1_no_inner_label_window_overlap, test_m1_leaking_embargo_inflates_inner_score |
| M2 | (v1.4.1: no selection existed — "M2: select_features DOES NOT EXIST on this base"; ported per-fold feature lists + perturbation test) | wip ADDED select_features (wip ml_train.py:370, FEATURE_CAP=20): pooled-importance over ALL folds' train windows -> ONE fixed feature set -> the spec's pooled-selection leak EXISTS on v1.5.0 (fact-check F16; the shipped validation jsons record "over 5 TRAIN-fold fits") | HIGH — this is a REAL fix on v1.5.0, not a no-op port: selection must move INSIDE each fold (per-fold ranking on that fold's train window only), report per-fold feature lists, add the perturbation test. The shipped feature_selection report format changes; the three wip-only tests on selection (test_select_features_cap_and_train_only, test_retrained_heads_respect_cap, test_small_feature_set_untouched) move to the per-fold contract — fixture/contract change with written justification (spec 3.1 M2 requires it), no weakened assertion | test_m2_per_fold_features_recorded_and_label_independent (+ updated selection tests) |
| M3 | _fit_z in-sample calibration fallback REMOVED (3 sites); insufficient folds -> no probability, excluded from pooled metrics; final refit ships identity calib + final_calibration disclosed (v141 ml_train.py:431 comment — the only _fit_z mention) | _fit_z defined wip:289, called wip:423 (fold loop) and wip:491 (final refit) — the phase prompt's line numbers exactly | MEDIUM — removing it changes OOS counts materially (e-head 381 -> 0 usable, q 435 -> ~261-style; fact-check F13/F15): the shipped validation jsons + npz metrics become stale -> RETRAIN on the pilot as-is belongs in the SAME phase, reporting honest numbers (v1.4.1 did exactly this; no data fabricated) | test_m3_insufficient_folds_get_no_calibrated_probability, test_m3_calibrated_folds_still_work |
| M4 | beats verdict needs >= 12 USABLE OOS periods (MIN_OOS_PERIODS=12, v141:109, 562, 578) + calibrated final model + model-vs-raw-engine on IDENTICAL rows/time groups (verdict_basis in report) | wip ml_train.py: min_oos=100 only (:518, verdict text :551); no MIN_OOS_PERIODS, no verdict_basis (absent from shipped jsons) | LOW — additive constant + verdict conditions + report fields | test_m4_beats_needs_12_usable_oos_periods, test_m4_baseline_compared_on_identical_rows |
| M5 | hash-bound activation: report carries model_sha256 + dataset_sha256, verified at load AND --activate; GBM sidecars carry joblib_sha256 pin verified at load; --activate re-pins after the sanctioned state rewrite (v141 ml_train.py:654, 791-813, 840-842) | wip npz pins: sklearn_version + sidecar_sha256 + master_version + dataset_sha256 (its own final-phase mechanism, master.py:1847-1857 checks sidecar sha + sklearn); --activate (wip:687-707) refuses on missing/failing report but does NO hash verification; naming differs (sidecar_sha256 vs joblib_sha256) | MEDIUM — reconcile to ONE canonical key set (spec 3.1: "report carries model_sha256 and dataset_sha256, verified at load and at --activate"); keep wip's sklearn pin; adopt v141's activation checks + re-pin | test_m5_active_requires_hash_bound_report, test_m5_gbm_sidecar_pin_required_and_verified |
| P-5 | scorecard states the effective earnings weight when the weak verdict halves it: "weak x0.5 ACTIVE — E weight 35% -> 21%" (v141:3328-3334) | wip has only the "(weak x0.5)" suffix (wip:2484); no effective-weight line | LOW — render area moved (one-pass renderer + provenance lines); port the line into the wip scorecard segment | test_weak_e_states_effective_weight |

--------------------------------------------------------------------------------
ALSO PORTED AS PART OF B6/B7 (new files, zero code conflict)
--------------------------------------------------------------------------------
scripts/: decision_path.py, lint_hunt.py, sensitivity_sweep.py,
fuzz_decisions.py, diff_checks.py, rules_register_check.py,
build_manifest.py, test_env_matrix.py (WITH the C-2 fix: install the
FakeDate for real, handle pandas Timestamp interop). v1.5.0 ships none of
them. Sequencing note: running fuzz_decisions.py on wip BEFORE the port
reproduces the v8-hunt RED evidence (blocked-row pass-throughs ~464+410,
all-inf ZeroDivision ~75, NaN-budget ~353 on the v1.4.0 base) — that IS
the red-first proof for B1/B3/B5; after the port the same fuzz must report
the v1.4.1 post-fix state (1 disclosed out-of-contract suite).

--------------------------------------------------------------------------------
NOT PORT ITEMS (identical defects in BOTH trees -> B-7, phases 2-3, spec 3.2-3.4)
--------------------------------------------------------------------------------
E_MISSING_HAIRCUT 0.90 missing-E advantage (P-1 ruleset v2) · door
rounding (P-6 unrounded compare) · stop_px None (P-3 stops) · EARNINGS_TP
0.15 vs engine 0.20 (single CONFIG source) · under-invested book /
unreachable DD veto (P-2 vol_target) · no ADV guard (P-4 probe) · weak-E
0.5 value (P-5 ablation only). Porting these from v1.4.1 is a no-op BY
DESIGN — v1.4.1 shipped them as OWNER DECISIONS (proposals), not fixes.

--------------------------------------------------------------------------------
PHASE-1 EXECUTION ORDER (red-first discipline)
--------------------------------------------------------------------------------
1. requirements.txt + requirements-lock.txt (spec 3.1 P0; B-1/B-5).
2. Run ported fuzz/hunt scripts on wip AS-IS -> capture RED (B1/B3/B5).
3. Port B1+B2+B3 (sizer) -> green + fuzz clean.
4. Port B4 (NOW chip), B5 (re-assert), B6 (MODES + register script).
5. Port B8 (load checks + atomic writes incl. freeze/snapshot writers).
6. Port M1, M3, M4, M5, M2-in-fold (ml_train) + retrain heads on the
   pilot as-is; paste honest numbers (expect q ~261/3 fails, e 0 fails,
   macro 35/5 fails — the v1.4.1 outcome, no better).
7. Port P-5 line; port + FIX the env matrix; make the 7+5 fragile tests
   env-robust; suite green under all B7 conditions.
8. ENGINES.sha256 re-check; CONFIG diff vs v1.5.0 must show ONLY
   RISK_FALLBACK_RHO (+ any spec-mandated additions) with rationale.
Estimated suite size after phase 1: 256 + 35 ported + new P0 tests
(spec 9 wants >= 300 by release; phase 1 does not need to reach it alone).

--------------------------------------------------------------------------------
PHASE 1 EXECUTION RECORD (2026-11-13/14, appended after the phase closed)
--------------------------------------------------------------------------------
The phase-1 prompt scoped THIS phase to B-1, B-2, B-5 (the P0
compatibility/hygiene slice of the map above), not the full B-6 port.
What actually happened, mapped to the plan:

- Item 1 DONE: requirements.txt + requirements-lock.txt shipped (spec
  3.1 P0), with MINIMUM==TESTED stated honestly (no invented floors;
  the B-1 loader is the fail-closed enforcement).
- Item 7 (ml/env half) DONE ahead of the rest:
  * scripts/test_env_matrix.py ported IN-TREE with the C-2 fix (the
    clock is pinned by patching master/ml_dataset/ml_train .date — the
    global datetime module is never touched, so pandas Timestamp keeps
    working; v1.4.1's harness never installed its FakeDate at all).
  * The 7 named offline/stubs failures + the sklearn-1.9.1 hard-code +
    the 5 sklearn-blocked failures + the date-fragile tests: all made
    hermetic (env pinning in _run/_pin_env, runtime-version fixtures,
    _pin_today clock pinning, empty per-call ml models dir, honest
    trainer refusal when sklearn is absent). Matrix: ALL CELLS GREEN
    (evidence/phase1_env_matrix.txt).
- B-1 (the spec 3.1 loader half) DONE: four-version pin set
  (sklearn/numpy/joblib/python) in every npz + report; UNAVAILABLE
  state + exit 1; sha256-before-unpickle (poisoned-bomb proof);
  verified-bytes-only unpickle; doctor via the real loader; retrained
  heads with honest failing numbers.
- B-5 DONE: ml_train.py 1.1.0 real; TestVersionSurfaces locks the four
  surfaces. The ml_dataset "1.1.0-dryrun" doc half -> defect C-5
  (phase 9).
- Items 2-6 + 8 (B1-B8/M1-M5/P-5 ports, fuzz hunt, CONFIG diff) NOT
  STARTED this phase — they remain B-6 (OPEN) with the sequencing
  above. The env-matrix port is the one B-6 item that had to land early
  because it IS the B-2 gate.

Suite: 256 -> 263 tests (+7: four version-mismatch tests, poisoned-
sidecar proof, two UNAVAILABLE-exit-1 pipeline tests, version-surfaces
lock; net of the rewritten TestSidecarPin set). 263 passed, 0 skipped,
in every matrix cell.

--------------------------------------------------------------------------------
PHASE 2 EXECUTION RECORD (2026-11-14, appended after the phase closed)
--------------------------------------------------------------------------------
Scope per the phase-2 prompt: the decision-layer ports (its 8-item PORT
LIST) + the accounting below. Every port = v1.4.1 test written against
the v1.5.0 tree FIRST (RED), then the function ported by name, then
GREEN. RED evidence: evidence/phase2_red.txt (23 of the 25 new tests
failed on the as-shipped tree; the 2 that passed are the no-regression
companions — consistent blocked rows untouched, short-history rho already
None — both still green after the port) + phase2_fuzz_red.txt (ported
fuzz on the unported tree: 75 all-inf ZeroDivision, 353+353 NaN-budget
weight/weight-invalid, 2984+2861 blocked-row pass-throughs, 85
future-report-NOW; identical numbers to the v8-hunt profile) +
phase2_rules_register_red.txt (5 dead keys: the four v1.4.1 B6 keys
RE-INTRODUCED by v1.5.0 + STUB_WARM_BUDGET_S, a v1.5.0-only dead key the
v1.4.1 register never saw).

ITEM DISPOSITION (the prompt's accounting — B1-B8, M1, M3-M5, P-5):
- B1  PORTED HERE (phase 2). size_portfolio: _usable_vol, unusable vols
      -> MISSING semantics (peer median / equal-weight + note); all-inf
      book degrades (was ZeroDivisionError on this tree). Tests
      test_b1_* x4, W_UNUSABLE_VOL / W_EQW_FALLBACK codes.
- B2  PORTED HERE. rho unavailable (1-2 names / <42 rows / broad except /
      non-finite rho_bar) -> correlation cap OFF + est-DD at
      CONFIG[RISK_FALLBACK_RHO] (0.5, the ONE CONFIG addition — diff vs
      v1.5.0 shows exactly that key and nothing else,
      evidence/phase2_config_diff.txt), disclosed in notes + footer +
      JSON (rho_fallback/rho_used) + the stable W_RHO_FALLBACK code,
      carried into v1.5.0's NEW surfaces: JSON summary warn_codes and
      the freeze manifest's new "risk" block (offline/replay carry the
      disclosure — the conflict note below the port table). Tests
      test_b2_* x4.
- B3  PORTED HERE. non-finite budget -> stand-down veto (no plan, clear
      reason, W_BUDGET_STANDDOWN); risk_ctx_out emits null not NaN
      (_jf); non-finite rho_bar -> treated as unavailable (B2 path).
      Tests test_b3_* x3.
- B4  PORTED HERE. _map_plan_row window bounded BOTH sides
      (0 <= days <= EARNINGS_MAX_AGE); future-dated report -> status
      open + future_report warning re-raised by _earnings_signal
      (W_FUTURE_REPORT code). Pinned-clock tests test_b4_* x2.
- B5  PORTED HERE. _apply_overlays re-asserts blocked rows (AVOID +
      below-WATCH cap, W_BLOCKED_REASSERT) once per decision BEFORE any
      overlay signal is consulted — ALL rows (v1.4.1's own first version
      covered only rows with a signal; the fuzz caught it). Tests
      test_b5_* x2 + the fuzz I3 hardened invariant.
- B6  PORTED HERE. MODES["standard"] resolves from EARNINGS_TOP_K /
      LAYER_TIMEOUT_S at import AND at _apply_mode time; rationales
      disclose EARNINGS_NATIVE_GRADES / CONF_DIGITS not-read; PLUS the
      phase-2 census finding STUB_WARM_BUDGET_S (v1.5.0-only dead key)
      disclosed not-read (enforced by the TEST SUITE, not production).
      scripts/rules_register_check.py ported WITH its negative control
      (--master PATH + planted dead key -> exit 1) and locked by
      TestRulesRegisterCheck. Post-port census: 77 live / 3 disclosed /
      0 dead (80 keys; v1.4.1's own census was 65/2/0 on a smaller
      CONFIG — the numbers differ as predicted, the PASS condition is
      identical). Tests test_b6_* x2.
- B7  SPLIT: the env-matrix + hermeticity half LANDED IN PHASE 1 (the
      B-2 gate); the remaining half — the hunt scripts — PORTED HERE:
      fuzz_decisions.py (first, for the RED evidence), rules_register_
      check.py, decision_path.py, lint_hunt.py, sensitivity_sweep.py,
      diff_checks.py, build_manifest.py = the "8 hunt scripts" of B-6
      (test_env_matrix.py was the 8th, ported in phase 1). All run on
      this tree (evidence/phase2_*); decision_path/lint/sweep needed
      only header + note adaptations — every seed/literal verified
      present by name first.
- B8  SPLIT: the ATOMIC-WRITES half PORTED HERE (the prompt's port-list
      item 6, extended beyond v1.4.1 to v1.5.0's own new writers):
      _write_csv, the freeze manifest, the materialised meds snapshot,
      ml_dataset cache/manifest/npz (_atomic_write_text/_atomic_savez),
      ml_train npz + joblib sidecar + validation reports — all
      write-temp + fsync + rename with injected-failure tests proving
      the previous file survives and no .tmp litter remains
      (TestAtomicWritesB8 x5: the 3 v1.4.1 tests + freeze manifest +
      meds snapshot crash tests). The ML-LOAD-HARDENING half (finite
      base_rate/calib_a/b at load -> REFUSED; non-finite probability
      drops the head) is Phase 3 with the M-ports — it is ml_train/
      MLLayer load logic, the phase-2 port list did not include it, and
      it must land with its own red tests.
- M1  PHASE 3 (ml_train inner-embargo target-awareness; not in the
      phase-2 port list; recorded here as the accounting the prompt
      asked for).
- M2  PHASE 3 (select_features in-fold fix — a v1.5.0-specific real fix,
      not a v1.4.1 item; listed for completeness).
- M3  PHASE 3 (in-sample calibration fallback removal + retrain with
      honest numbers; defects.md B-3).
- M4  PHASE 3 (>= 12 usable OOS periods + verdict_basis; defects.md B-4).
- M5  PHASE 3 (hash-bound activation + --activate hash verification;
      defects.md B-4; the two v1.4.1 fixture updates attach to it —
      evidence/fixture_changes.md items 2-3, DEFERRED with justification).
- P-5 PORTED HERE (the disclosure line): the layer-status line states
      the EFFECTIVE earnings weight when the weak verdict halves it
      ("weak x0.5 ACTIVE — E weight 35% -> 21%"), ported into the wip
      one-pass renderer's weak block. Test test_weak_e_states_effective_
      weight. (The P-5 VALUE question — whether 0.5 is right — stays an
      owner decision; only the disclosure ported, as on v1.4.1.)

Test count: 263 -> 288 (+25: 11 sizer B1/B2/B3, 6 B4/B5/B6, 5 atomic
writes, 1 P-5 weak-E disclosure, 2 rules-register incl. negative
control). 288 passed / 0 failed / 0 skipped in every env-matrix cell
(evidence/phase2_env_matrix.txt). The ported fuzz post-port state equals
v1.4.1's: 1 disclosed out-of-contract suite (I1-ml-scaled-range 1231),
all hardening suites 0 (phase2_fuzz_green.txt). Sensitivity sweep re-run
(phase2_sensitivity_sweep.txt): rule behaviour UNCHANGED vs v1.5.0 on
the shared keys (the sweep's own zero-effect list matches the v8
profile — upstream/display keys, plus RISK_FALLBACK_RHO which moves the
est-DD estimate + disclosure, not the weights — by design, asserted by
test_b2_*).

--------------------------------------------------------------------------------
PHASE 3 EXECUTION RECORD (2026-11-13/14, appended after the phase closed)
--------------------------------------------------------------------------------
Scope per the phase-3 prompt (B-3, B-4) + the phase-2 accounting that
aimed M1/M2/M3/M4/M5 and B8's ML-load-hardening half here. Every port =
the v1.4.1 test written against this tree FIRST (RED:
evidence/phase3_red.txt: 23 of 25 phase-3 tests red on the as-shipped
tree; the 2 pre-green companions are the GBM sidecar-pin tests — the
v1.5.0 tree ALREADY pinned sidecars in phase 1's B-1 work, so those two
assertions held before this phase; recorded as companions, not as new
evidence), then the function ported by name, then GREEN (309/309).

ITEM DISPOSITION (the ML half of B-6 — B-6 is now CLOSED):
- M1  PORTED. _label_horizon_td / _inner_embargo_months (q 3 / e 5 /
      macro 1, from ml_dataset's own Y_*_TD constants) / _inner_splits /
      _inner_oof(..., embargo_months) replace the hard-coded 1-month
      inner embargo. Tests test_m1_* x3 (leak channel quantified).
      CONFLICT RESOLVED: wip's _inner_oof body was otherwise the
      v1.4.0 shape, so the port is the v141 function verbatim with the
      wip sklearn-refusal prologue kept.
- M2  PORTED WITH A REAL REWRITE (the port_map's predicted HIGH
      conflict): v1.5.0 had ADDED pooled select_features + FEATURE_CAP
      (the F16 leak v1.4.1 never had — v1.4.1 selected nothing). The
      v1.4.1 contract ("per-fold feature lists + perturbation test")
      lands as select_features_fold(X, y, feats, train_idx, cap): each
      walk-forward fold ranks |standardised coef| on ITS OWN train
      window; the final refit selects on all labeled rows (the shipped
      model — disclosed in the report); the old pooled function is
      DELETED. Tests: test_m2_per_fold_features_recorded_and_label_
      independent + THE perturbation test (test_m2_selection_
      perturbation_test_fold_only: last-group labels flipped + feature
      values jittered -> every fold's selected set bit-identical;
      evidence/phase3_perturbation.txt) + the rewritten TestFeatureCap
      (contract move justified in evidence/fixture_changes.md item 5).
- M3  PORTED (= B-3). _fit_z deleted (def + both call sites) AND its
      GBM twin (the .fit(X[tr]).predict_proba(X[tr]) calibration
      fallback); insufficient folds -> p NaN, excluded from pooled
      metrics (oos["ok"]); final refit uncalibrated -> identity calib +
      final_calibration=uncalibrated_insufficient_inner_oof, can never
      support activation; metrics_block(empty) = honest n=0 block.
      Tests test_m3_* x3 incl. the grep-style source test (no _fit_z /
      no predict_proba-on-train patterns). The honest retrain then
      reproduced v1.4.1's numbers exactly (q 261 / e 0 / macro 35
      usable; v1.5.0's 435/381/35 were fallback products).
- M4  PORTED + strengthened (disclosed). MIN_OOS_PERIODS=12; enough =
      n>=100 AND periods>=12 AND final_calib=="inner_oof"; the verdict
      vocabulary gains "insufficient evidence" for failed sample gates
      naming the failed condition (the phase-3 prompt's explicit
      wording; v1.4.1 shipped only beats/fails — the judged-negative
      "fails" is kept for when the gates PASS but IC/Brier do not).
      verdict_basis{model_rowset_sha256, baseline_rowset_sha256} added
      beyond v141's {n_rows, n_periods, note} so row-set equality is
      machine-checkable from the report alone. IDENTICAL-ROWS: v141's
      latent hole (GBM winner judged on all-usable rows vs baseline on
      cmp rows) is closed — when use_gbm, BOTH the winner block and the
      baseline block are recomputed on cmp ∩ gbm-valid; the capture
      test (test_m4_baseline_compared_on_identical_rows) proves the
      two metrics_block calls received the exact same (y, groups)
      arrays and the digest matches. Tests: the four gate tests +
      identical-rows + SHADOW-until-manual-activate.
- M5  PORTED + one strengthening (disclosed): reports carry
      model_sha256 (full 64-hex, sha of the npz written) +
      dataset_sha256 (the npz's own 12-hex pin — the v1.5.0 schema's
      convention, like-for-like on both sides of every check);
      --activate verifies the model hash BEFORE np.load (tampered file
      refuses cleanly), then dataset pins on BOTH sides (v141 allowed
      empty==empty — closed here: an npz without a dataset pin is a
      malformed artifact), then the GBM sidecar pin
      (sidecar_sha256 — wip's key name kept; v141 called it
      joblib_sha256; master.py already reads wip's name), then the
      sanctioned state rewrite + report re-bind. master's _ml_load_head
      gains v141's ACTIVE-state verification (verdict + both hashes,
      downgrade-to-SHADOW with reason) beside wip's own sidecar/version
      gates. Tests: tampered-file refusal + restore-pass, wrong-hash
      negatives in both branches of test_activate_refused, load-side
      tamper matrix, the GBM pin pair.
- B8's ML half PORTED: _ml_load_head finite base_rate in (0,1) +
      finite calib_a/b REFUSED (logistic_np) — before any state
      handling; _ml_predict non-finite -> None; _ml_adjustment isfinite
      belt; MLLayer.run dropped-count warning + "p_q/p_e dropped
      (non-finite)" segments + macro good-ETF filter. PORT NOTE: the
      ctx_out macro map needed a round(None) guard (v141's surface
      would crash on a None probability once _ml_predict could return
      one — a latent defect in the port surface itself, fixed with the
      port). Tests test_b8_* x4 (+ the m5/b8 companions).
- The two DEFERRED fixtures (fixture_changes.md items 2-3) landed
      exactly as promised: _mk_ml_model hash-bound report + calib/ds
      kwargs; test_activate_refused wrong-model-hash / wrong-dataset-
      hash negative cases in both branches (the no-sklearn branch's
      minimal npz now carries the pins it always implied).
- NEW BEYOND THE PORT (C-6, found by the new selection test): the
      env-matrix harness's blocked cell leaked sklearn.* submodules
      across sequential cells -> `from sklearn.X import Y` imports were
      never actually blocked (phase-1/2's blocked-cell green line was
      partially unverified for submodule surfaces). Fixed in
      scripts/test_env_matrix.py (submodule purge) + the selection
      test now skips cleanly where sklearn is absent. The phase-3
      matrix paste is the first fully-hermetic one.

The NOT-PORT list is unchanged: B-7's P-1..P-6 are owner-decision
opt-ins (spec 3.2-3.4), never v1.4.1 fixes. ML dataset v2 (spec §4)
stays with B-9's phases 4-9. Suite 288 -> 309; CONFIG unchanged.
