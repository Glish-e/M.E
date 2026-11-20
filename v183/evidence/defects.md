# evidence/defects.md — ONE merged defect table (both audits + owner reproductions)
# THIS copy ships with phase 3: every status below is the FINAL verified state.

Source of IDs: the phase prompt cites master_py_v1_1_0___Technical_Audit.md (A1..A15) and
master_py_deep_audit_findings.md (HIGH-01..05, MEDIUM-06..18). NEITHER audit file was provided
(owner directed to continue; see analysis_phase1.md). Only the IDs the prompt itself cites are
listed below, with the prompt's/owner's description and my verified status. IDs A1, A5, A7-A13
and HIGH/MEDIUM items other than those cited are UNKNOWN to me — not fixed, not claimed.
A15's description is taken from the phase-3 prompt ("a registered layer runs or fails loudly,
never silently skipped") — the audit file itself remains absent.

| ID (source) | Prompt/owner description | Phase | Status |
| --- | --- | --- | --- |
| A2 (Tech audit) | MASTER_STUBS=1 not loud enough: no STUBBED banner in render | 1 | FIXED (item 9) |
| A3 (Tech audit) | Vetoed/gate-failed name keeps uncapped conviction (72) with AVOID | 1 | FIXED (item 6) |
| A4 (Tech audit) | Offline guard missing for quality source=auto | 2 | FIXED (item 2) |
| A6 (Tech audit) | Quality scored nothing still exits 0 | 1 | FIXED (item 7) |
| A14 (Tech audit) | _fit measures raw width incl. ANSI; colour self-test fails | 1 | FIXED (item 8) |
| A15 (Tech audit) | registered layers silently skipped: build_layers iterated a hardcoded order tuple, so a 4th registered layer never ran | 3 | FIXED: build_layers/run_pipeline/fuse/renderer/JSON all iterate LAYER_REGISTRY in insertion order; unknown --only/--skip exit 64 at parse time; overlay/sizer stages wired end to end; gate-proven by a dummy registered layer (evidence/phase3_gate.txt GATE 3) |
| owner repro 1 | NaN quality score => LONG, conviction 100, grade A | 1 | FIXED (items 1/6, matrix) |
| owner repro 2 | Vetoed quality-80 => AVOID but conviction 72 | 1 | FIXED (item 6) |
| owner repro 3 | Final sort by conviction only (~1264) | 1 | FIXED (item 6) |
| owner repro 4 | selftest 53 tests, 1 FAIL colour test, 1 skip | 0 | Reproduced differently: 0 FAIL in sandbox (width-dependent); deterministic red test added, root cause fixed |
| prompt item 1b | "x or default" swallows zero / crashes on NaN (confidence, conviction_leverage, n_quarters) | 1 | FIXED (item 2) |
| prompt item 1c | earnings loop: one bad ticker kills whole layer | 1 | FIXED (item 3) |
| prompt item 1d | scorecard: missing score crashes render; missing p_next shows 0% | 1 | FIXED (item 4) |
| prompt item 1e | JSON allows NaN; CSV formula injection unescaped | 1 | FIXED (item 5) |
| prompt item 1a | --timeout nan / --min-conviction nan accepted | 1 | FIXED (item 1) |
| prompt 2.1 | _deadline_call is a soft deadline, unnamed; late worker can write after fusion | 2 | FIXED |
| prompt 2.3 | meds.FORCE_SNAPSHOT + QE_DATA_DIR/QE_CACHE_DIR never restored (state leak) | 2 | FIXED |
| prompt 2.4 | earnings prefetch hard-codes 4 workers | 2 | FIXED |
| prompt 2.5 | earnings cache status not read from the real (default) directory | 2 | FIXED |
| prompt 2.6 | --check mixes concerns; exits 0 with a missing engine | 2 | FIXED |
| prompt 2.7 | --warm --skip macro,quality still runs earnings | 2 | FIXED |
| prompt 2.8 | empty/stale macro snapshot reported OK | 2 | FIXED |
| prompt 2.9 | staples/discretionary collapsed in macro mapping | 2 | FIXED (ETF-level split, CONFIG untouched) |
| prompt 2.10 | earnings per-signal status vocabulary ("E layer off") | 2 | FIXED |
| prompt 2.11 | p_next_big unlabelled; conviction undefined; missing-E LONG undisclosed | 2 | FIXED |

UNVERIFIED (engine file absent): any claim about earnings_engine.py internals (cache dir default,
_fetch/_px_fetch patch points beyond what master already does, __version__ absence) — see HANDOFF.

## Phase 4 defects (found because earnings_engine.py v3 finally arrived)

| ID | Description | Status |
| --- | --- | --- |
| P4-D1 | _dstr stringified pd.Timestamp.date as a BOUND METHOD ("<bound method ...>"); the no-lookahead guard `last_s > as_of` then rejected EVERY real-engine earnings row as future-dated (all 57 funnel names MISSING_DATA, layer ERROR). Phases 1-3 never saw it: the fakes used datetime.date. | FIXED (red test test_dstr_handles_real_engine_timestamps -> _dstr calls .date() when callable + truncates to YYYY-MM-DD); pilot date 1 rebuilt, earnings=OK |
| P4-D2 | master's L3 adapter was written blind (engine absent) against an API that v3 does not have: no plan()/Analysis.plan (default run: "plan unavailable"; --earnings-backtest: layer ERROR via a.plan), accuracy verdict required a missing `auc_lo` (every real verdict degenerated to WEAK, halving E's fusion weight via EARNINGS_WEAK_SCALE), _backtest_summary expected a score>= DataFrame shape v3 never returns (silent None) | FIXED adapter-side only (H1): _plan_map wraps eng.signals() with the NOW-chip freshness rule applied adapter-side (v3 has no max-age param); verdict mirrors v3's ladder (SIGNAL/MIXED via oos_brier_skill); _backtest_summary maps v3's summary Series; --explain omits the stop price v3 never sends. Red: evidence/phase4_red.txt (5 tests) -> green: phase4_green.txt (157) |
| P4-D3 | Two phase-3 tests asserted the engine-ABSENT path by relying on the file's absence; with the engine present they failed | FIXED: _Mods(False) blocks an import via sys.modules[name]=None — absence is simulated, not environmental |
| P4-D4 | ml_dataset._shift_months day-carry produced invalid/drifted dates (Feb 31; 31->30->28 drift) — caught by test_month_grid | FIXED: lands on the target month's last day (inputs are floored month-ends) |
| P4-D5 | ml_dataset.next_event stringified Timestamp events via the same .date-method trap as P4-D1 | FIXED with _ev_str (shared pattern); test_next_event_window |

UNVERIFIED entries from phases 1-3 about earnings_engine.py internals are now RESOLVED against the
real v3 file (see reuse_report.md + the live runs): no __version__ (docstring v3 reported, drift
undetectable — still true), cache_dir default ~/.earnings_engine_cache, _fetch/_px_fetch instance
seams (offline guard verified live pattern), analyze(as_of=, accuracy=, trade=) signature, p_next_big
emitted only via calibration. The RUNBOOK's old "eng.plan" references were stale documentation of an
engine that never had plan(); replaced by signals() in v1.3.1.

## Phase 5 defects (found red-first / by the pilot training run)

| ID | Description | Status |
| --- | --- | --- |
| P5-D1 | MLLayer/RiskLayer read `d.macro_sector` from Decision — the attribute lives on Candidate and on the quality signal's facts, so both layers ERRORed on every run (AttributeError salvaged loudly, no silent damage; found in the red run) | FIXED: risk sizes on d.sector; the ML macro-ETF mapping reads the quality signal's macro_sector fact (bucket vocabulary preserved) |
| P5-D2 | ml_train's raw-score baseline fed NaN engine scores into the rank correlation (below-gate names have NaN q_score) -> baseline IC silently NaN, so "beats the baseline" was unjudgeable | FIXED: baseline rows with a NaN raw score are dropped from the baseline metrics only (n reported); the model still imputes them |
| P5-D3 | _inner_oof indexed ug[(f+1)*len/n_folds] — off the end on the last fold (IndexError on every training run); single-class inner train slices also crashed LogisticRegression | FIXED: clamped slice bounds + skip single-class folds + in-sample fallback (_fit_z) when no inner fold fits (tiny samples; OOS judgement still uses held-out months) |
| P5-D4 | verdict "beats" had no minimum-OOS-sample condition: the macro head scored IC +0.368 on 35 OOS rows and would have been activatable on noise | FIXED: beats IFF n_oos >= 100 (a priori) AND IC > 0 AND > raw-score baseline AND Brier skill > 0; verdict_why states which condition failed |
| P5-D5 | Platt Newton iterations overflowed exp() on separated inner-OOF logits (RuntimeWarning, extreme a) | FIXED: logit argument clipped to ±500 inside the iteration |

No engine file was edited for any of these (H1): P5-D1 is master-side; P5-D2..D5 are ml_train-side.

## phase 6 (final) defects — found by the red runs, all fixed + tested
| id | defect | fix | test |
|---|---|---|---|
| P6-D1 | offline guard set earnings `_px_fetch`; the real v3 price fetcher is `_pfetch` — the px guard was a silent no-op (offline prices could still hit the network) | both attribute names guarded/wrapped; caught by an online-side AttributeError the moment the adapter touched the real engine | TestOfflineFastFail, TestNetModes (transport observed at call time) |
| P6-D2 | meds has no transport seam and calls yfinance directly — offline runs opened sockets for meds price inputs whenever yfinance is installed | yfinance made ABSENT (sys.modules valve, restored) for offline runs; meds serves the materialised snapshot (0.2 s, zero sockets) | TestOfflineNoSockets (real meds, blocked sockets) |
| P6-D3 | per-layer elapsed charged the whole run's wall to every prefetch layer (the "macro 77.9s" artifact) | per-layer completion stamps (done[name]) | TestPerLayerTiming |
| P6-D4 | quality's YfinancePriceClient bypasses default_transport — offline runs with yfinance present fetched prices over the network despite the transport guard | the engine's own availability seam swapped for the run (chart client + blocked transport serve caches) | TestOfflineFastFail.test_offline_yfinance_path_disabled |
| P6-D5 | doctor hash-check key mismatch (earnings_engine.py vs 'earnings') — "(ENGINES.sha256 absent)" while the file existed | normalised key at parse time | TestDoctor |
| P6-D6 | freeze copied quality caches one level too shallow for --cache-dir replay to find them | copy into <d>/cache/quality/cache/<ns> | TestFreezeReplay + real-engine replay (identical) |

---

# FINAL ROUND (v1.7.0) defect register — seeded in PHASE 0 (2026-11-13)

Base: v1.5.0 re-based with the v1.4.1 fixes ported (step0_plan.md).
Statuses: OPEN = seeded, not yet worked. The historical tables above are
the v1.1.0->v1.5.0 lineage record and stay untouched. Evidence pointers
are to phase-0 artifacts (phase0_fact_checks.md / phase0_baseline.txt /
port_map.md) unless dated later.

| ID | Description (verified in phase 0) | Evidence | Status | Target phase |
|----|-----------------------------------|----------|--------|--------------|
| B-1 | sklearn '_loss' GBM load failure on mismatched sklearn (owner saw it on 1.9.1; sidecars pickled with 1.5.2). Does NOT reproduce in THIS sandbox (sklearn 1.5.2 installed = pickling version; loads OK, 0.32 s) — the defect is environment-dependent and stands. v1.5.0 already pins sklearn_version before the sidecar unpickle; the pinned-requirements + version-aware-loading work and a red test with a doctored pin are still required. | F4; phase0_baseline.txt | FIXED in phase 1 | 1 |
| B-2 | Fragile tests: exactly 7 fail under ambient MASTER_NET=offline MASTER_STUBS=1 (TestStreams 1; TestNetModes 2; TestManifestHeader, TestCacheStatusRealDir, TestDegradationMatrixFinal, TestProvenanceSurfaces 1 each); +5 more with sklearn/joblib blocked (TestSidecarPin x3 FAIL, TestMLTrain x2 ERROR — v1.4.1's NEW-2 reproduced); + date-fragile TestFreshness x2 (and 3 more at 2025-02-01). | phase0_baseline.txt (all runs pasted) | FIXED in phase 1 | 1 |
| B-3 | In-sample calibration fallback _fit_z (ml_train.py:289 def, called at :423 and :491 — plus its GBM twin at :469 — the prompt's exact sites). MATERIAL: v1.5.0's shipped validation_e.json claims 381 OOS rows where v1.4.1 correctly reports 0 usable (all folds calibration-insufficient); q claims 435 vs 261 usable. Port = v1.4.1's M3 + retrain with honest numbers. | F13, F15 | FIXED in phase 3 (M3 port + the honest retrain: q 261 usable / e 0 / macro 35, all "insufficient evidence" — evidence/phase3_retrain.txt) | 3 |
| B-4 | M4/M5 gates absent: no MIN_OOS_PERIODS (>=12 usable OOS periods), no verdict_basis (identical-rows baseline comparison), --activate performs no hash verification (v1.5.0 ml_train.py:518/687-707 vs v141:109/562/578/791-813). | F14 | FIXED in phase 3 (M4 gates + identical-rows verdict basis + digests; M5 hash-bound reports verified at load AND --activate; GBM sidecars pinned; the two deferred fixture updates landed with it — evidence/fixture_changes.md items 2-3) | 3 (port) + 5 (gates on real data — the phase-5 backtest re-states them) |
| B-5 | Version-label drift: HANDOFF/CHANGELOG call ml_train "1.1.0-pinned" and ml_dataset "1.1.0-dryrun"; the files' __version__ are 1.0.0/1.0.0 and every sidecar pin says ml_train 1.0.0; dataset manifest still stamps master 1.3.1 (its build-time truth). Code and sidecars are mutually consistent — the docs are wrong, and master.py never checks ml_train_version at load. | F12 | FIXED in phase 1 (ml_train half; the ml_dataset "1.1.0-dryrun" doc drift is recorded under C-5) | 1 |
| B-6 | The v1.4.1 port itself: B1-B8, M1-M5, P-5 + the 35 regression tests + the 8 hunt scripts (v1.5.0 ships none of them). Function-level map with conflict risks: port_map.md. | port_map.md | CLOSED — decision layer in phase 2 (B1-B6, B8-atomic, P-5, the hunt scripts), ML layer in phase 3 (M1-M5, B8 load hardening, +21 tests, the two deferred fixtures). The only v1.4.1 items NOT ported are the ones v1.4.1 shipped as owner proposals (B-7's P-1..P-6 opt-ins) — not ports by design. Per-item records: port_map.md PHASE 2 + PHASE 3 EXECUTION RECORDS. | 2 (done) + 3 (done) |
| B-7 | Weird rules, all verified reproducing on v1.5.0: (a) E_MISSING_HAIRCUT 0.90 missing-E advantage (master.py:236/2452/2633; ~36% pilot rows); (b) under-invested book / unreachable DD veto (eff/8 at :2136, RISK_MAX_EST_DD 0.30 at :2151; observed gross 7-30%); (c) stop_px None (:1620) + EARNINGS_TP 0.15 (:326) vs engine default 0.20 (earnings_engine.py:840/918); (d) no ADV guard (0 grep hits); (e) door rounding (round(...,1) at :2522 then >= 60 at :2558); (f) no cost/slippage model; (g) weak-E 0.5 silent scale (footer says x0.5; v1.4.1's effective-weight P-5 line absent). Fixes are the spec 3.2-3.4 opt-ins (P-1..P-6 defaults pre-set); none may change defaults without the backtest evidence + owner approval. | F6-F11 | CLOSED in phase 4: (a) --ruleset v2 opt-in, fill E_MISSING_V2=0.0, invariant + fuzz I5b (0/4800), legacy default labelled in the header; (b) --sizing vol_target opt-in with looser-than-norm labels, DD-guard-can-fire PROVEN by test (legacy hostile book veto fires; vol_target fires when the target is looser than the DD envelope); (c-stop) vol-based stop EARNINGS_STOP_K=2.0 with W_NO_VOL_NO_STOP; (c-TP) EARNINGS_TP now the single source for analyze/backtest AND signals (test asserts both read the same value); (d) ADV feasibility probe run: UNAVAILABLE, loud W_ADV_UNAVAILABLE (doctor + probe), nothing faked; (e) unrounded doors behind v2, flip count reported (stub 0/56 door-only, 5/71 full v2; real pilot 2/60 door-only, 10/76 full v2); (g) 0.5 kept + ablation reported without tuning. (f) costs/slippage stays the C-4 release-notes obligation + the §5 backtest's conventions (later phases). Evidence: phase4_gate.txt / rules_changes.md / phase4_sensitivity_sweep.txt / phase4_adv_probe.txt | 4 (done) |
| B-8 | Speed unmeasured against the spec Section 7 targets (this sandbox: import 128-132 ms, suite 11.2 s, quick+offline 33.4 s cold; build-machine claims differ — machine-bound, recorded honestly). Benchmark + targets + equivalence gate. | F17; phase0_baseline.txt | OPEN | 8 |
| B-9 | Unverified items: full-universe dataset build never run (12-date tech pilot only); Finnhub response shapes inside quality.py; meds PIT approximate; online-vs-offline identity on a real cache (D3); cross-sector real-data behaviour; ADV availability (P-4); cold-run variance. Each must end the round either VERIFIED or DISCLOSED in the release notes. | F19 | OPEN | 4-9 |
| B-10 | CLI: glued cells confirmed on real width-40 render ("83 A88 A", "79 A72 B", "nodat", "81 A·…"); no column engine; no goldens; (the v1.6.0 lineage's 19 goldens and its date-hard-coding golden are NOT on this base — the spec Section 8 goldens must be built date-free from the start). | F18 | OPEN | 9 |
| C-1 | master_v1_4_1.zip + Master_Engine_MASTER_PROMPT.md were absent from upload/ when phase 0 began (only master_final.zip); they arrived mid-phase (timestamps Nov 13 18:55). No work was fabricated in the gap; interim fact list = the phase prompt's B-seed, then re-checked against the real spec. | phase0_baseline.txt header | DISCLOSED | — |
| C-2 | v1.4.1's scripts/test_env_matrix.py defines FakeDate but never installs it — its "date pinned" matrix rows were plain re-runs; the v1.4.1 date-independence evidence is unproven by that artifact. Phase 1 ports the matrix with REAL pinning (and must survive pandas Timestamp interop — see the harness artifacts in phase0_env_matrix_partial.txt). | phase0_baseline.txt (meta-finding) | FIXED in phase 1 (ported in-tree with module-level date pinning; pandas-safe; green) | 1 |
| C-3 | v1.5.0 suite is not date-hermetic: pinned non-today dates flip cache freshness and online-mode tests attempt REAL network refreshes (partial log shows the [plan] refresh lines); plus genuine date-fragile tests (TestFreshness x2, TestAsOfPropagation, TestNoLookahead, TestMlDataset at 2025-02-01). | phase0_env_matrix_partial.txt | FIXED in phase 1 (date cells green; no test touches the network in any cell) | 1 |
| C-4 | v1.5.0's rewritten RUNBOOK dropped the costs/slippage disclosure that v1.4.1's RUNBOOK carries ("10 bps/side in the phase-4 study; treat all output as gross of costs"). The live engine has no cost model — the disclosure must be restored (and extended by the backtest's cost conventions) in the release RUNBOOK. | F11 | OPEN | 9 |
| C-5 | Phase-1 finding: B-5's drift has an ml_dataset half — v1.5.0 docs also claimed "ml_dataset.py v1.0.1 -> v1.1.0-dryrun" while ml_dataset.py ships __version__ 1.0.1 and the dataset manifest stamps master 1.3.1 (both its build-time truths). ml_dataset is functionally unchanged in phase 1, so no version bump was invented for it; the RELEASE handoff (phase 9) must state ml_dataset 1.0.1 plainly and stop repeating the "1.1.0-dryrun" claim. | phase1 evidence (this file) | DISCLOSED (owner-visible; fix due phase 9) | 9 |
| C-6 | FILLED + FIXED (phase 3): the env-matrix harness's "sklearn blocked" cell was not fully hermetic — in a sequential run the earlier cells leave sklearn.* SUBMODULES in sys.modules, so `from sklearn.X import Y` imports (the _pipe used by feature selection) still succeeded and the cell could report green while not actually blocking; surfaced by phase 3's new per-fold selection test, fixed by purging every cached submodule at cell setup (scripts/test_env_matrix.py) + making the selection test skip cleanly where sklearn is genuinely absent (B7). Prior phase-1/2 matrix "blocked cell green" lines were therefore partially unverified for submodule-import surfaces — their OTHER surfaces (top-level `import sklearn` checks, loaders, CLI) were and remain genuinely covered; the phase-3 re-run (phase3_env_matrix.txt) is the first fully-hermetic paste. | phase3 evidence | FIXED in phase 3 | 3 |
| C-7 | Phase-3 finding: the honest retrain leaves the shipped e-head UNCALIBRATED (identity calib, final_calibration=uncalibrated_insufficient_inner_oof, 0 usable OOS rows — all 5 folds insufficient under the e-head's 5-month inner embargo on a 12-group pilot) and the q/macro heads at "insufficient evidence". The artifacts are HONEST and inert (SHADOW, refusal-safe at load), but the phase-9 release notes must state plainly that NO head is validated and the e-head ships unusable-pending-data — never "calibrated with 0 rows". The gates stay the gates: 12 usable periods is unreachable on the pilot by design. | evidence/phase3_retrain.txt | OPEN (release-notes obligation) | 9 |

Phase-0 note on the historical tables above: they document the v1.5.0
lineage (phases 1-6 of the earlier build) and are accurate for it; the
v1.4.1 lineage's equivalent table ships inside master_v1_4_1.zip. The
two defect vocabularies do not overlap (A-*/P4-*/P5-*/P6-* vs B*/M*/P-5).

## Phase 4 (FINAL ROUND) defects — B-7 close-out + hunt findings

| ID | Description | Status |
|---|---|---|
| P4-H1 | Per-name reason label "(weak x0.5)" hard-coded the CONFIG value (EARNINGS_WEAK_SCALE): the label could lie the moment the key changed while the arithmetic followed the key. Found by the phase-4 hunt (label-drift class). | FIXED: interpolated `f"(weak x{CONFIG['EARNINGS_WEAK_SCALE']:g})"`; red test test_weak_reason_label_interpolates (0.7 case) |
| P4-H2 | Same class: "(damped x0.5)" hard-coded MACRO_DEGRADED_DAMP in the macro reason line. | FIXED: interpolated; red test test_damped_reason_label_interpolates (0.6 case) |
| P4-H3 | Same class: the --explain fusion line hard-coded 0.5 twice ("W_E×0.5×e" and the renormaliser "/ (W_Q + W_E*0.5)"). | FIXED: interpolated (same red tests cover the render path indirectly; explain line rewrites with CONFIG) |
| P4-H4 | DISCLOSED (not a code defect): under ruleset v2 the conservative fill flows through the SAME weak-verdict renormalisation, so a missing-E name scores 0.788q when the layer verdict is WEAK vs 0.65q otherwise — still below every observed-E name (fill 0 <= any e >= 0), but the interaction is non-obvious and is documented in rules_changes.md + the E_MISSING_V2 rationale. | DISCLOSED |
| P4-H5 | DD veto boundary: a vol_target book sitting exactly AT its target has est_dd == RISK_MAX_EST_DD by construction; the strict `>` comparison could veto on a 1-ulp float rounding (est_dd 0.30000000000000004). | FIXED: +1e-9 tolerance on the comparison; disclosed in rules_changes.md item 3; the legacy hostile-book veto still fires at est_dd ~1.69 (test_vol_target_keeps_the_dd_veto) |
| P4-H6 | ADV (B-7d): the feasibility probe (scripts/adv_probe.py) verified NO readable price feed carries a Volume column (earnings px cache = close only; quality client = Close/Adj Close/Stock Splits; engine sources have zero Volume references). The ADV cap and min-ADV exclusion are therefore NOT implemented and are NOT estimated — the fact ships loudly as W_ADV_UNAVAILABLE (doctor line + probe output). | CLOSED (loud disclosure; guard pending an engine-side volume feed — owner decision; the §3.4 liquidity-limit grid cell is UNANSWERABLE until then) |
| P4-H7 | lint_hunt new constant: 365.0 in _stop_price (calendar-day scaling of the annualised vol to the engine's calendar-day hold window). Magic-number scan flags it; it is documented in the EARNINGS_STOP_K rationale (the engine's hold_days is calendar days). | DISCLOSED (documented constant) |

Notes: the door-rounding flip counts, the weak-E ablation numbers and the
looser-than-norm arithmetic are evidence, not defects (phase4_gate.txt /
phase4_sensitivity_sweep.txt). The cost/slippage model (B-7f) remains the
C-4 release-notes obligation plus the §5 backtest conventions (later
phases). No engine file was touched (ENGINES.sha256 MATCH x3).

| P4-H8 | Evidence-file name collision: the FINAL ROUND's phase-4 artifacts (phase4_gate/green/config_diff.txt) overwrote the v1.5.0 lineage's same-named phase-4 artifacts during this phase (and this round's phase 3 had already overwritten lineage phase3_green.txt in the prior context). Found by the phase-4 pre-zip tree-vs-wip_phase3.zip content diff. | FIXED within the phase: the lineage originals restored byte-for-byte from wip_phase3.zip as evidence/lineage_phase4_{gate,green,config_diff}.txt and lineage_phase3_green.txt; pristine copies also remain inside master_final.zip; the phase-4 deliverable keeps the phase4_* names (the phase3_green.txt precedent). Nothing lost; disclosed here and in PHASE_STATE.md. |

## Phase 5 (FINAL ROUND) defects — C-1..C-5 close-out + findings

| ID | Description | Status |
|---|---|---|
| C-1 | Colour was auto-only (TTY + NO_COLOR + TERM!=dumb in make_style): no force flag, no precedence, no depth, no Windows VT, no explanation — the owner's plain-white run. | FIXED: full --color/--no-color/--plain switch with the tested precedence table (always beats NO_COLOR/pipes; NO_COLOR beats FORCE in auto; capable markers override dumb), depth detection, ctypes VT with honest fallback, ONE dim reason line on AUTO-off, --doctor colour diagnostic (phase5_gate_doctor.txt) |
| C-2 | Hard-to-read report: green check next to DEGRADED; glued Q/E cells ('NODATAn/sel'); bare '?'; cryptic 'SHADOW(n 974)'; 14-day macro cache labelled OK (FRESHNESS_MACRO_MAX_AGE_D=45); stub banner without SYNTHETIC. | FIXED: bright palette + glyph+word; DEGRADED = yellow ▲; display-width cell padding with mandatory separators; n/a cells; 'SHADOW (n=974 train rows)'; STALE_STATUS_DAYS=7 display status (never OK); SYNTHETIC banner + stub labels + DATA SOURCES |
| C-3 | Layout: width ceiling 110 (no 160 tier); header could wrap a lone status word; magic '?'/vstub tokens; glue risk with wide chars. | FIXED: MAX_TERM_WIDTH 160 (disclosed); provenance cells wrap as units; _disp_width/_pad (ANSI+wide-char aware); column-drop priority tested at 40/70/110/160; 'SYNTHETIC-stub' labels; all macro-card lines width-safe |
| C-4 | No goldens; rendering regressions invisible. | FIXED: 12 byte-exact goldens from frozen-clock stub runs; date-guard with failing negative control; strip_ansi(colour)==plain; locale/terminal/sklearn independence; regen only via --regen. Disclosed masking: dates -> FROZEN-DATE, durations -> Xs (P5-H4) |
| C-5 | Errors invisible: no ERRORS & WARNINGS block; the cryptic 'provider_errors:...' tail; exit codes conflicted with the owner's table. | FIXED: registry-backed block ending every run (layer/code/what/why/exact fix); STDERR mirror; --debug-gated tracebacks; per-provider diagnosis; DATA SOURCES + macro path; the NEW exit-code contract (64->2, 2->4, 1->70) mapped in CHANGELOG/--help/--doctor; 12 injected-fault tests |
| P5-H1 | Evidence-name collision (P4-H8 class): the v1.5.0 lineage's own phase5_* evidence (8 files + analysis_phase5.md) shared this round's names. | FIXED preemptively: byte-copies to evidence/lineage_phase5_*.{txt,md} BEFORE this round wrote its phase5_* files; pristine originals also inside master_final.zip and wip_phase0..3.zip. Nothing lost. |
| P5-H2 | The owner's 'vstub' token: not present in SOURCE (grep across all *.py = no hits — the phase-5 discovery record is accurate for source), but the RENDER composed engine-version 'stub' with a 'v' prefix in the layers/engines lines ('ml_train vstub'), which is exactly what the owner saw. | FIXED: stub layers' versions render as 'SYNTHETIC-stub' in both the engines row and the layer chips (out.stubbed guard), so the token cannot reappear; locked by the stub goldens. |
| P5-H3 | W_UNUSUAL: two recurring warnings do not classify (the earnings 'no __version__' drift note; 'accuracy: not run (empty shortlist)') — honest but generic entries with the 'python3 master.py --debug' fix. | DISCLOSED: adding dedicated codes for cosmetic notes is an owner decision; the scanner test guarantees no code is ever missing from the registry meanwhile. |
| P5-H4 | Goldens mask two volatile byte classes after capture (ISO dates -> FROZEN-DATE; wall-clock durations -> Xs) — golden hygiene, disclosed in scripts/make_goldens.py header + CHANGELOG + here. Behaviour stays date-deterministic via the frozen clock; nothing else is masked. | DISCLOSED (by design) |

Standing OPEN items carried: C-4 (costs/slippage disclosure — release
notes + §5 backtest conventions), C-7 (release-notes wording for the
uncalibrated e-head), B-8/B-9/B-10 (later phases). Engines untouched
(ENGINES.sha256 MATCH x3, re-verified in phase5_engines_sha256.txt).


## Phase 6 (FINAL ROUND) defects — the integration backtest

| ID | Description | Status |
|---|---|---|
| P6-H1 | PRNG call shape: _bt_rng returns a function but _bt_boot_ci called rng.randrange — first shakedown run died exit 70 (AttributeError). | FIXED (caught by the red-test shakedown run before any evidence run; rng() % m now) |
| P6-H2 | MDD peak snapshot: the printed peak index was the FINAL series peak, not the peak AT the drawdown (peak_i kept updating). | FIXED (peak_at captured at the drawdown; the 0.001 MDD now correctly labelled window 2 -> 3 — the liquidation-cost dip) |
| P6-H3 | avg holding counted total date-memberships, not consecutive run-lengths (wording said "consecutive"). | FIXED (run-length scan; 3.03 consecutive month-ends) |
| P6-H4 | The bootstrap seeds line printed a literal "{_BT_BOOT_SEED}" (an unfixed f-string segment). | FIXED |
| P6-H5 | Metric lines printed raw float reprs (Sharpe 1.4208906507426198). | FIXED (_bt_fm: .3f, None/nan -> n/a) |
| P6-OBS | During 4 defensive-regime month-ends the macro risk budget held the book 100% cash — the LONG basket earned exactly zero while EW rode the drawdowns. | OBSERVATION (real recorded behaviour, not a defect; visible in phase6_backtest_run.txt per-date table) |

Carried OPEN: B-8, B-9 (full-universe build — W_BT_FIXTURE_ONLY + owner
command), B-10, C-4 (live-engine cost disclosure, release notes), C-7.
Engines untouched (ENGINES.sha256 MATCH x3 after the phase).


## Phase 7 (FINAL ROUND) defects — B-8/B-9 close-out

| ID | Description | Status |
|---|---|---|
| P7-H1 | run_freeze quality-copy loop double-decremented the byte budget (b3 grew AND left shrank per file — effective cap FREEZE_MAX_BYTES/2), then skipped every remaining namespace SILENTLY while copied_b < cap kept the "cap hit" warning off: a budget-starved freeze masqueraded as complete and replay failed on the missing sec_submissions/prices_v2 cache. Found through the real B-9 freeze/replay run (replay exit 4, cache miss) — root-caused, red test, fixed (single counting + starved flag + meds-tree starvation reporting + in-place file counting). | FIXED (test_freeze_budget_starved_is_flagged_loudly; real re-verification in phase7_freeze_replay.txt: dedicated-cache freeze -> replay exit 0 identical; tamper -> 65) |
| P7-OBS | sec.gov 403 (Forbidden) rejects quality's default contactless User-Agent from this sandbox; the documented SEC_USER_AGENT env var ("research-screener admin@example.com") restores access. Not an engine defect (fair-access policy); the RUNBOOK gains the row at phase 9. | DISCLOSED (env note in perf_p7.txt; RUNBOOK row due phase 9) |

Carried OPEN: B-9's remaining unverified items end at phase 9 as
DISCLOSED in the release notes (full-universe build never run — the
backtest and the dataset carry the loud warnings; Finnhub shapes/
cross-sector real behaviour — same root cause). B-10 -> phase 8.
C-4/C-7 unchanged (release notes, phase 9). Engines untouched
(ENGINES.sha256 MATCH x3).


## Phase 8 (FINAL ROUND) defects — B-10 close-out + hunt findings

| ID | Description | Status |
|---|---|---|
| P8-H1 | diff_checks.py D1 required the stub --json run to exit 0 — contradicted by the phase-5 exit-code contract (a degraded stub run with warnings exits 1 BY DESIGN). Found on the first phase-8 run (rc=2). | FIXED: D1 accepts 0/1 (2/4/65/70 still fail) with the contract justification inline; final run rc=0 |
| P8-H2 | rules_register_check.py's DOCUMENTED negative control (--master /tmp/corrupt_master.py) crashed with ModuleNotFoundError: the out-of-repo master copy could not import codes.py. The control had therefore never actually executed on this base — a dead control. | FIXED: the tool puts the REPO ROOT on sys.path for the exec (removed after); negative control now runs, catches the planted key and FAILs with exit 1 (phase8_rules_register.txt) |
| P8-H3 | Env-matrix leap/Sunday cells caught test_backtest_rerun_calls_run_pipeline using HARD-CODED past dates — under a pinned "today" earlier than the fixture dates, as-of validation fails (exit 2). Date-fragile new test. | FIXED: fixture dates are now RELATIVE to master.date.today() (pin-aware); matrix all cells green |
| P8-H4 | Env-matrix leap cell caught test_only_quality_imports_nothing_else reading the AMBIENT cache state: the fake quality module's default CACHE_DIR is the real data/cache, whose mtime under a pinned FUTURE clock trips the 135d freshness gate -> exit 1 on a test that asserts a clean 0. Environment-leaky assertion (green only while the operator's disk cache is empty — phase 5's matrix passed for that reason). | FIXED: --cache-dir AND the fake's CACHE_DIR point at an empty temp dir (R2 note inline: same assertion, zero machine-state input; hermeticity fix per the phase-5 precedent — holes are fixed, never skipped) |
| P8-D1 | lint_hunt's DEAD-CONFIG-KEYS heuristic flags 3 keys (CONF_DIGITS, EARNINGS_NATIVE_GRADES, STUB_WARM_BUDGET_S). All 3 are indirect/generic reads (bands key through _native_grade) or register-disclosed not-read keys; the rules register classifies all 3 DISCLOSED (83 live / 3 disclosed / 0 dead). | DISCLOSED (tool false-positive class; no code change) |
| P8-D2 | fuzz I1-ml-scaled-range: 1231 violations — the out-of-contract suite carried DISCLOSED since phase 2 (byte-identical count to the v1.4.1 reference; the port's fidelity proof). | DISCLOSED (carried; unchanged count) |

CONFIG diff discipline (the phase-8 gate): v1.5.0 vs current shows EXACTLY
the 8 disclosed lines — 7 additions (RISK_FALLBACK_RHO phase 2; RULESET,
E_MISSING_V2, EARNINGS_STOP_K, RISK_SIZING_MODE, RISK_VOL_TARGET phase 4;
STALE_STATUS_DAYS phase 5) + 1 value change (MAX_TERM_WIDTH 110->160,
phase 5) — every one listed in evidence/rules_changes.md (which now also
registers the two phase-6 W_BT_* codes as registry-only additions).
ZERO undisclosed changes. Suite 432 green (300+ requirement met with real
tests; nothing padded or weakened — the two matrix hermeticity fixes
STRENGTHENED two tests). Env matrix ALL 9 CELLS GREEN. Engines untouched
(phase8_engines_sha256.txt: MATCH x3).


## Phase 9 (FINAL ROUND) — release close-outs

| ID | Description | Status |
|---|---|---|
| C-4 | The live engine has no cost model; the disclosure must be restored (and extended by the backtest's cost conventions) in the release RUNBOOK. | CLOSED: RUNBOOK.md header line + HANDOFF costs disclosure (live output is GROSS of costs; the backtest applies 10 bps/side with 5/10/25/50 sensitivity per the prereg) |
| C-5 | ml_dataset "1.1.0-dryrun" doc drift; the release handoff must state ml_dataset 1.0.1 plainly. | CLOSED: the release HANDOFF states "ml_train v1.1.0; ml_dataset v1.0.1" |
| C-7 | The e-head ships uncalibrated-pending-data; release notes must say so plainly, never "calibrated with 0 rows". | CLOSED: the HANDOFF ML paragraph carries the exact wording |

No OPEN items remain at release: every register row is FIXED or
DISCLOSED. Engines untouched (ENGINES.sha256 MATCH x3, re-verified in
the clean-dir verification).

| P9-H1 | The clean-dir verification caught test_freeze_budget_starved_is_flagged_loudly passing for the WRONG REASON in a warm tree: a leftover 'quality' module in sys.modules bound CACHE_DIR at its own creation time, so the freeze read the REAL data/cache (starving there, incidentally) instead of the test's temp dir; in a cache-free tree the test failed outright. | FIXED: the test pops the leftover module, sets QE_DATA_DIR (the value _layer_cache_dirs actually reads on a stubbed run) and lays out <QE_DATA_DIR>/cache/<ns>/ — it now starves its OWN fixture in any tree; clean-dir re-verification ALL GREEN |

## v1.8.0 (workstream W0) — defects opened by the entry check

| ID | Description | Status |
|---|---|---|
| D-18-001 | final_master_d.zip ships two evidence files whose sha256 do not match its own MANIFEST.txt: evidence/phase6_backtest.json (zip fb36bcb1…, manifest 74831218…) and evidence/phase6_backtest_report.md (zip d26a2110…, manifest d30ccee…). Root cause: the zip's phase6 evidence was produced by a backtest re-run in a tree the manifest was never rebuilt for (the zip's json references a "…/work/w18/…" dataset path and CONFIG hash 04293ea1…, both inconsistent with the manifest built on the work/wip tree). Found by scripts/release_gate.py at entry (evidence/plan_v18.md F6). Impact: evidence-text packaging defect only — no engine, code or decision surface touched (suite 436 OK in the same unzip). Fix: v1.8.0 W7 rebuilds MANIFEST after the last edit and re-runs the gate on a CLEAN UNPACK of final_master_e.zip itself (not the working tree). | DEFERRED → fixed in W7 (W0) |

## v1.8.0 (workstream W2) — defects opened/fixed during the speed pass

| ID | Description | Status |
|---|---|---|
| D-18-002 | The CONFIG identity hash (backtest report 'current' hash; ml_dataset manifest config_hash_master; ml_train ds['_cfg_hash']) used json.dumps(default=str) on a CONFIG containing 8 frozensets — str(frozenset) order follows PYTHONHASHSEED, so the hash differed in EVERY process (observed 5 distinct values across 5 runs of the same tree). 'Build-time vs current' hash comparisons in reports and manifests were therefore noise. Found while profiling W2 (the backtest before/after diff kept moving on an unchanged line). Fix: me.core._canonical_json shared recipe (sets -> sorted lists), applied in me/backtest._bt_config_hash, ml_dataset.py, ml_train.py; report line now discloses the recipe change; RED->GREEN test TestConfigHashDeterministic (seeds 1/2/random subprocesses must agree). Side note: part of D-18-001's evidence ('current 04293ea1' vs wip's 'e0b4df46') was this noise — the file-hash mismatches in D-18-001 stand regardless. | FIXED (W2) |

## v1.8.0 (workstream W7) — defects found/fixed during release

| ID | Description | Status |
|---|---|---|
| D-18-003 | The v1.8.0 module split silently WIDENED the set of modules reading date.today() (me/cli validation, me/render header), but the env-matrix and the suite's _pin_today pinned only master/ml_dataset/ml_train — three pinned-date cells then validated as-of dates against the REAL clock (2026-06-30 rejected as 'future' under the 2025-02-01 pin). Found by the W7 matrix run (3 errors in the Sunday cell); fixed by widening both pin loops to the me/* modules (date-less modules skipped, never given a bogus attr); matrix re-run ALL CELLS GREEN. | FIXED (W7) |

## v1.8.1 defects (final_master_f)

| id | defect | status |
|---|---|---|
| D-181-1 | The net guard's preflight TCP-probed the REAL engine hosts under the suite's MASTER_NET=online pins (found by grepping the suite log for 'preflight: api'); three real DNS+TCP touches happened before the fix. | FIXED — preflight is skipped whenever MASTER_NET is pinned online/offline (the documented hermeticity valve), a SET MASTER_NET_PREFLIGHT_HOSTS (even empty) overrides the CONFIG list, and the suite's _run pins it empty; final suite log: 0 real-host preflight lines. |
| D-181-2 | In script mode (python3 test_master.py) master's _stubbed_registry imports a FRESH test_master module, so the hanging-layer test's STUB_LAYERS mutation was invisible to master (the test passed only under -m unittest). | FIXED — the test patches the documented REGISTRY seam (master._stubbed_registry), which is module-instance-independent; disclosed in the test comment. |
| D-181-3 | scripts/config_diff.py loads both trees in ONE process, so for the me/* split the second load reuses the first tree's me.core CONFIG — the diff printed EMPTY (false PASS). | FIXED (workaround, not an engine/edit of the gate): evidence/v181_config_diff_v180.txt loads each tree in its own subprocess with values canonicalised through me.core._canonical_json (sets sorted) — 13 additions + 1 value change, the exact disclosed set. The gate script itself is unchanged (pre-existing tool). |
| D-181-4 | The goldens needed a SECOND regeneration after the version bump (v1.8.0-dev -> v1.8.1 changed header bytes). | FIXED — regenerated; disclosed in evidence/v181_goldens_justification.md. |
| D-181-5 | The funnel/overlay/sizer TimeoutError salvages still said "timeout after 900s" when the RUN BUDGET had actually bound them (message-only inconsistency with the prefetch/layers phases). | FIXED — all timeout handlers now use the run-budget wording when the budget bound them. |

## v1.8.2 defects (final_master_g)

| id | defect | status |
|---|---|---|
| D-182-1 | HANDOFF.txt's v1.8.1 F4 claim ("cadence-aware STALE: 18 d macro = refresh-due, not stale") was OVERSTATED: only the [plan] banner had the cadence wording; the header/SUMMARY/W_STALE_CACHE surfaces still said STALE at 19 d (W0 fact c). | FIXED — W3 makes the display cadence-aware everywhere (refresh-due vs STALE vs refresh-failed, refresh_failed provenance key); the v1.8.2 HANDOFF states the true scope. |
| D-182-2 | Routine messages still classified W_UNUSUAL (W0 fact d): empty shortlist, scenario renormalized, macro DEGRADED, credit OFF, earnings accuracy, bare quality flag words, equal-weight fallback, UNTRAINED pipeline copy. | FIXED — W4: 7 new codes + 5 classifier patterns + the engine's real flag vocabulary; stub/offline/outage runs now emit ZERO W_UNUSUAL (tested, incl. the pinned-date old-cache path). |
| D-182-3 | OWNER_RUN.md added CFLT as "energy" and PSTG as "utilities" although quality groups both under tech (W0 fact f); the shipped overrides CSV carried an EXAMPLE1 row. | FIXED — W6: the commands use tech; universe_override.py warns on a sector/engine-group mismatch (fail-soft); the CSV ships header-only. |
| D-182-4 | No separate --net flag: --mode mixed depth presets and data modes (W0 fact g). | FIXED — W5: --net {auto,online,offline} with exit-2 conflict checks; --mode compatibility test-pinned. |
| D-182-5 | v1.8.1's flat RUN_BUDGET_S=1200 silently CLIPPED legitimate deep runs (3600 s layer budget) and --warm runs (WARM_TIMEOUT_S 3600) at 1200 s. | FIXED — W1: RUN_BUDGET_BY_DEPTH (quick 600 / standard 1200 / deep 4500); disclosed in the CONFIG diff and net_bounds.md. |
| D-182-6 | Per-host brownout trip measured 184.4 s (cap 30, K 5, 3 attempts) and the three host families trip SEQUENTIALLY: 3 x 184.4 = 553 s, far over the 300 s standard / 180 s quick targets; the consecutive-only breaker never trips intermittent hosts (30 alternating calls left it closed). | FIXED — W1: rate rule (window 20, rate 0.5, timeouts 2x) + NET_BROWNOUT_S=120 global failed-attempt budget + NET_PREFLIGHT_TOTAL_S=10; bounds written and test-asserted (net_bounds.md). |
| D-182-7 | quality's yfinance path (YfinancePriceClient._download, _detect_sector_yfinance) bypassed every master wrapper in online runs (W0 fact e). | FIXED — W2: runtime engine-seam wrappers (breaker + cap via abandoned-daemon thread + ledger, contract preserved); real yfinance remains UNVERIFIED (absent in the agent env) — owner_net_check.sh/.ps1 extended. The first wrapper design raised on timeout (violating the (None, err) contract); the red tests caught it and the shipped wrapper returns tuples only. |
| D-182-8 | The loopback fault server's plan semantics ("last status repeats") made [500, 200] mean "500 once, then 200 forever" — an intermittent-host test would silently not alternate. | FIXED — _fault_srv supports "cycle:500,200" (alternates forever); the intermittent tests use it. |
| D-182-9 | Under pinned dates the matrix exposed two more W_UNUSUAL producers: the pipeline-level "<layer> data STALE: ..." warning and the per-name "no earnings report since ..." warning. | FIXED — both classify as W_STALE_CACHE; regression test test_offline_old_cache_zero_unusual added. |
| D-182-10 | scripts/config_diff.py again printed a false EMPTY for the me/-split CONFIG (same root cause as D-181-3, re-hit for the v1.8.2 comparison). | FIXED — scripts/config_diff_v182.py loads each tree in its own subprocess with set-repr normalisation: exactly the 6 new knobs + 7 rationale updates. |
| D-182-11 | A W1 test used an f-string variable (`i`) undefined in its loop; the NameError was swallowed by assertRaises(Exception), so the test "passed" without exercising anything (found when the debug run disagreed with the test result). | FIXED — variable bound; lesson logged: assertRaises(Exception) hides NameError, so fault-test assertions must be positive (wall/count/state), not only "raised something". |
| D-182-12 | KNOWN LIMIT (DISCLOSED, not fixed): a DNS-hang outage with preflight disabled (MASTER_NET=online, the hermeticity valve) is bounded at ~17 s by the knobs — marginally over the 15 s outage target — because getaddrinfo has no timeout parameter. | DISCLOSED — evidence/net_bounds.md states it plainly; the default preflight path bounds the whole pass at 10 s. |
| D-182-13 | KNOWN LIMIT (DISCLOSED): the EARNINGS yahoo provider receives the real yfinance module as a parameter; when yfinance uses curl_cffi those calls are covered only by the (absent) requests-level guard, not the seam wrapper. | DISCLOSED — evidence/net_paths.md; the owner net_check prints curl_cffi importability. |
