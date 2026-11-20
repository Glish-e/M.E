# analysis_phase5.md — ML heads (SHADOW), risk sizer, final verification
Pre-work, written BEFORE any coding. Base = the phase-4 output (master v1.3.1,
ml_dataset v1.0.0, pilot ml_data/dataset_v1.npz, reuse_report.md, DESIGN_NOTES).

## ANALYSIS FIRST — trainer / calibrator / walk-forward / accuracy in the engines
- earnings_engine._calibrate :236 — score bucket -> P(next quarter is a big
  beat), shrunk toward the base rate (k=20 pseudo-observations), forced
  non-decreasing; consumed by validate() :781 (walk-forward, rate each past
  quarter using only earlier quarters) and its 60/40 OOS Brier-skill check.
  ADAPT: ml_train's validation report reuses the bucket+shrink+monotone DISPLAY
  for calibration transparency, but the SHIPPED calibrator is Platt (2 params,
  exportable into the pure-numpy model file). Rejected importing _calibrate
  itself: it calibrates the engine's own score for its own target (next big
  beat), not our y_q/y_e/y_m — the heads need a generic calibrator.
- earnings_engine.validate :781 / backtest :840 — the walk-forward PATTERN
  (score each period from earlier data only) is the pattern ml_train's
  expanding-window loop applies at as-of-group granularity. No code reuse:
  different row unit (engine quarters/trades vs (ticker, as_of) ML rows).
- quality.evaluate :7277 / _pit_validate :7615 — quintile-spread evaluation
  and the engine's own PIT harness: patterns only (their row units are
  snapshot pairs and engine scores). The spread metric idea (top-minus-bottom)
  is reused as a METRIC, not code.
- meds Backtester :4716 / span :8488 — the regime strategy's own history; NOT
  USED (phase-4 reuse_report decision, unchanged).
- Phase-4 discovery (grep evidence, unchanged): zero sklearn/joblib/pickle
  anywhere in the engines; no cross-sectional per-(ticker,as_of) trainer
  exists. BUILD ml_train.py is the gap — the same conclusion reuse_report
  reached for the dataset maker.

## master.py touch points (line numbers = the phase-4 file)
| function/class | callers | current | planned change |
|---|---|---|---|
| LAYER_REGISTRY :1437 | build_layers, wizard :3554, _validate_ns :3233, json, manifest | 3 layers | + "ml" MLLayer(order 4, stage overlay) + "risk" RiskLayer(order 5, stage sizer). A15 untouched: build_layers already iterates the registry; a registered layer runs or fails loudly |
| _apply_overlays :1724 | _run_pipeline_inner :2280 | applies facts["conviction_adj"], ±OVERLAY_MAX_ADJ, skips blocked | + one SHADOW log line when the signal has facts["p_note"] and no adj — no change to the adj path |
| _run_pipeline_inner :2264-2297 | run_pipeline | overlay + sizer stage loops ALREADY EXIST (phase 3) | none — the rails are there |
| Decision.weight :481 | _decisions_table, json :3022, csv :3276 | always None | RiskLayer fills it (LONG>0, others 0.0, cash explicit) |
| Context.risk_budget :491 | set from macro ctx_out :2234 | macro-driven budget | RiskLayer consumes it (sum(weights) <= budget invariant) |
| CONFIG §1 :207 | everything | OVERLAY_MAX_ADJ 10.0, RISK_CAP_DEGRADED 1.0 already exist | + ML_MODELS_DIR, ML_ADJ_MAX 5.0, ML_FORBIDDEN_FEATURES; + RISK_* limits (vol/corr lookbacks, name/sector caps, min effective bets, DD factor/max, min budget, max price names) — each with a rationale string; the H2-frozen pins untouched (config_diff evidence) |
| _decisions_table :2664 | render_report | no weight column | + "WT" column at width >= 70 when any decision.weight is not None; width 40 unchanged |
| _footer :2787 | render_report | already iterates ctx_out["portfolio"] lines | + one ml-state disclosure line when the ml layer ran |
| json_payload :2988 | --json | weight + generic overlays dict already emitted | + p/adj/state/n in the overlays entry; risk portfolio summary in the risk layer entry |
| build_parser :3074 | CLI | --only/--skip help names 3 layers | help names 5; new --ml-models DIR flag (wizard parity: every choice a flag) |
| _layer_module :2539 | manifest header | meds/quality/earnings | + ml->ml_train, risk->master mappings |
| _stubbed_registry :1455 | MASTER_STUBS runs | STUB_LAYERS has 3 stubs | test_master.py gains StubMLLayer + StubRiskLayer (H3: fakes live in tests) |

## New code
- master.MLLayer (stage "overlay"): loads ml_data/models/head_{q,e,macro}.npz
  with allow_pickle=False and infers in PURE NUMPY (dot product + Platt) —
  inference needs no sklearn and no network (offline-safe by construction).
  States: UNTRAINED (no model file / forbidden feature / import failure —
  never a crash), SHADOW (signals + p with sample size logged, NO
  conviction_adj — changes no decision), ACTIVE (npz state=ACTIVE AND
  validation_{head}.json exists AND its verdict beats baselines; otherwise
  downgraded to SHADOW with a loud warning). adj = ML_ADJ_MAX *
  (W_Q*s_q + W_E*s_e + MACRO_TILT_GAIN*s_m) / (sum of available weights),
  s_h = (p_h - base_h)/max(base_h, 1-base_h), clamped to
  ±min(ML_ADJ_MAX, OVERLAY_MAX_ADJ) on top of the generic clamp.
  Feature parity: builds the SAME per-date record ml_dataset.harvest() builds
  and calls the SAME date_features()/macro_features() — parity by construction.
- master.RiskLayer (stage "sizer"): prices through the earnings-engine
  adapter (same cache-dir + offline-guard pattern as EarningsLayer._engine
  :1285 — REUSE of the one blessed price source); pure core size_portfolio()
  = inverse-vol weights -> name cap -> sector cap -> correlation-aware gross
  cap (effective bets = N/(1+(N-1)*rho)) -> est-DD portfolio veto
  (est_dd = RISK_DD_FACTOR * annualised portfolio vol). Weights are assigned
  ATOMICALLY (all at once after every cap; a timeout/error leaves weight=None,
  never a half-sized book). Offline or fetch failure -> equal-weight fallback
  inside the same caps, DEGRADED + warning (no invented vols).
- ml_train.py (BUILD): expanding-window walk-forward per head over the npz
  (group = as-of month id; purge+embargo >= label horizon read from the
  dataset manifest — 3 monthly periods); light tuning (C grid by inner
  time-split); Platt calibration on inner-OOF predictions; logistic first,
  gradient boosting tried and kept ONLY if it beats logistic on pooled OOS
  rank IC; baselines = base rate and the raw engine score (q_score/e_score/
  tilt_mean); verdict rule fixed a priori (pooled OOS rank IC above BOTH
  baselines AND positive Brier skill vs base rate). --activate HEAD refuses
  without a passing validation report. Models carry version + training-window
  stamp + dataset sha256 + config hash.
- ml_dataset.py: + record_from_parts(as_of, regime, decisions); harvest()
  delegates to it. ONE feature source for dataset and live inference; MLLayer
  imports ml_dataset lazily (absent file -> UNTRAINED, not a crash).

## Tests (red first, then green; evidence/phase5_{red,green}.txt)
TestMLStates (UNTRAINED runs+DEGRADED; SHADOW changes no decision — deep
compare action/conviction/grade/weight/order vs a run without ml; ACTIVE
without report downgraded; ACTIVE bounded ±5; blocked AVOID never adjusted),
TestMLLeakage (model with a forbidden feature name refused; ml_train raises on
an embargo-violating split), TestMLTrain (synthetic dataset: embargo honored,
save/reload inference parity, calibrated p in [0,1]), TestRiskProps (weights
>= 0; sum <= budget; blocked=0; WATCH/AVOID=0; name+sector caps; high-corr
gross cap; DD veto zeroes the book; explicit cash; equal-weight fallback;
atomic on failure), TestStubEndToEnd5Layers (MASTER_STUBS with 5 layers:
weights + portfolio footer + json), widths 40/70/110 with weights, wizard
5-layer prompt via scripted stdin, socket-blocked offline run with SHADOW
models present, CONFIG sanity (rationales) auto-extended.

## Honesty gates carried into phase 5
H5: conviction stays a 0-100 heuristic; a model probability is shown only
post-calibration and always WITH its sample size; the footer line is
untouched. H2: no frozen pin changes (config_diff evidence; new keys only).
H7: anything not run is reported UNVERIFIED, never claimed.
