# analysis_phase4.md — written BEFORE any phase-4 edit (evidence; no code dumps)

Carry-in: phase-3 output (master.py v1.3.0, 3,545 lines; test_master.py
2,293 lines, 143 tests green after this phase's environment change — see
below). earnings_engine.py v3 (1,134 lines) UPLOADED and now sitting next
to master.py; both audit MDs still absent. Sandbox facts probed today:
network OK (Yahoo 104 ms); SEC EDGAR 403 with default UA but 200 with a
descriptive UA (SEC_USER_AGENT required); FRED fredgraph.csv reachable;
yfinance installed this session; NO background process survives between
tool calls (a nohup'd live run died silently) => the dataset builder MUST
cache per date to disk and resume (the spec already demands this).

## 0 · Phase-3 re-verification done first ("make sure u did everything well")
- test_master.py in the p4 tree with earnings_engine.py present: 2 FAILs,
  both tests asserting the engine-ABSENT path by relying on the file's
  absence (TestCheckSections missing-engine, TestManifestHeader MISSING).
  Fixed by making absence simulated, not environmental: _Mods now accepts
  False = block the import via sys.modules[name]=None. 143/143 green now;
  the 4 RealEngineContract tests that were LIVE SKIPs now RUN for real.
- Live pipeline probe WITHOUT SEC_USER_AGENT: quality 0/3 (sec_edgar
  cik_map_failed, 403). With UA set: works (verified below). L3 live path
  hits the adapter gap described next.

## 1 · L3 adapter vs the REAL earnings_engine v3 (code wins, HANDOFF notes it)
Probes (greps on upload/earnings_engine.py, all line numbers real):
- NO plan() method and NO Analysis.plan field. Analysis = scores, accuracy,
  calibration, tests, backtest(BacktestResult), signals(DataFrame), errors,
  params (:461-). master._plan calls eng.plan(...) -> AttributeError every
  default run (caught -> "plan unavailable", NOW chip + trigger mode dead);
  with --earnings-backtest, a.plan raises INSIDE the try -> whole layer
  ERROR (master.py:1268, :1312).
- eng.signals(tickers, hold_days, take_profit, stop_loss, min_score,
  entry_lag) exists (:918) — the real "what to hold now" API: action
  "LONG (day N of D)" / "skip (score < min)" / "ENTER (next session
  close)" / "closed (target)", entry_date, entry_px, planned_exit,
  target_px, event_date. No stop_px, no days_since, no max_age_days param
  (EARNINGS_MAX_AGE must be applied adapter-side).
- _accuracy_verdict reads "auc_lo" (master.py:1127); v3's validate summary
  has lift_vs_base, rank_corr, oos_brier_skill and NO auc (:824-836) ->
  verdict degenerates to WEAK even with strong lift (would halve E's
  fusion weight dataset-wide via EARNINGS_WEAK_SCALE). v3's own verdict
  ladder is n<60/n_hi<30 -> NOT ENOUGH; lift>=1.5 & corr>=0.10 -> SIGNAL
  unless oos_brier_skill<=0 -> MIXED (:263-271).
- _backtest_summary expects a DataFrame with "score>=" rows and
  vs_SPY%/ci_lo%/ci_hi% (master.py:1182-1197); v3's BacktestResult.summary
  is a Series (picked_n, picked_mean_excess, edge, edge_t, edge_basis,
  by_rating) -> blanket except returns None silently today.
- Everything else in the adapter matches v3: analyze(as_of=, accuracy=,
  trade=) signature, scores columns (incl. p_next_big via calibration),
  eng.errors, cache_dir attr, _fetch/_px_fetch seams (offline guard OK).
PLAN (H1 adapters only, H4 red-green first): update _fake_earnings in
test_master.py to mirror the REAL v3 contract (signals not plan; no auc;
BacktestResult shape) + new contract tests (NOW chip via mapped signals;
verdict ladder; backtest warning from v3 summary; max-age applied
adapter-side; --earnings-backtest no longer ERRORs) -> red -> fix master:
_plan wraps eng.signals into the plan_row vocabulary the rest of master
already speaks; a.signals replaces a.plan; _accuracy_verdict mirrors v3's
ladder; _backtest_summary maps v3's summary Series. No CONFIG value
changes; EARNINGS_MAX_AGE stays (applied adapter-side, documented).

## 2 · STEP A capability map (verified by grep/read, lines real)
- meds.build_ml_dataset (:8803) + CLI --ml (:9472): macro panel features +
  basket one-hots + regime one-hots + realized leverage, Y = NEXT-MONTH
  NET PORTFOLIO return of the regime basket (Backtester), 5y chunks ->
  macro_ml.npz. NOT our row unit (month vs ETF x month) nor our target
  (basket net return vs per-ETF beats-SPY). ADAPT: reuse master's macro
  adapter (regime_now(as_of) via MacroLayer) for features; build y_m
  labels from the shared price source. Do not build a parallel regime
  feature pipeline.
- meds.regime_now(as_of) (:7917): floors as_of to last completed month
  end; data_tier api|public|cache|snapshot; pit_mode approximate_pit_lag
  (_apply_pit_lags :823). Backtester (:4716), span (:8488), mrs_at
  (:7749), ticker_score (:8001). CLI: --audit/--from/--to/--ticker/--ml/
  --pit-manifest (no "regime history" subcommand per se; span/--audit is
  the history surface).
- quality.get_quality_score (as_of, universe_refs, progress) (:6619) ->
  dict; _scored_universe (:6579) whole-universe memo per (as_of, source,
  fingerprint); scan_main (:6900) single-date universe scan with RESUME
  state (--max-fetch, scan_state.json) + optional snapshot CSV;
  forward_main/evaluate (:7500/:7277) snapshot-pair forward-return
  harness (PriceLookup: adjusted close preferred, window from snapshot
  dates, GROSS spreads, delisting counted); _pit_validate (:7615) freeze-
  date PIT harness; FundamentalsView (:4394) = the PIT engine (fact
  visible iff availability date <= as_of; filings after 16:00 ET wait a
  day; no-filing facts dropped+counted); config_hash (:370); snapshots
  (write/read/list :6383+); build_market (:4779) cuts prices at as_of
  (splits collected through fetch, then bars filtered <= as_of).
- earnings_engine: history/prices (cached), score(as_of) via _window
  (quarters public strictly before as_of, provider lag), validate()
  walk-forward, backtest() per-event forward returns vs SPY, signals(),
  export (csv/json/parquet). CLI is flag-based, NO subcommands (the
  prompt's "earnings_engine backtest/plan" does not exist as such).
- master.py: no np.save/sklearn/dataset code (grep clean); the pipeline
  (run_pipeline, funnel, fuse, MacroState, LayerSignal.facts) IS the
  feature source; --as-of reaches all three layers; month_end_floor;
  --sectors all + earnings_top override give the full-pool funnel.
- Nothing anywhere builds (ticker, as-of) feature/label rows => BUILD
  ml_dataset.py; everything else REUSE/ADAPT (see reuse_report.md).

## 3 · STEP B PIT proofs to RUN (not assume)
- earnings: score(tickers, as_of=X) twice -> byte-identical; _window proof:
  max history date < as_of on a live sample; provider lag note (yahoo=0,
  finnhub=45d).
- quality: get_quality_score(t, as_of=X) twice -> identical; provenance
  trace (--explain) shows available_date <= as_of and filing_date used
  (not period_end); boundary probe: score just before vs just after a
  filing's availability date changes only after it is public.
- meds: regime_now(as_of=X) twice -> identical; report data_tier/pit_mode
  honestly (approximate vintage: series fetched now, cut at as_of with
  PIT lags) => meds labelled PIT_APPROXIMATE, quality PIT_VERIFIED
  (filing-date machinery + boundary probe), earnings PIT_VERIFIED
  (window + determinism + future-dated rejection already in master).
- Prices: labels use strictly-after-as-of closes; quality bars <= as_of
  (code-verified + probe); adjusted close stated in manifest.

## 4 · STEP C design decisions (ml_dataset.py)
- Drive master.run_pipeline per as-of date (adapters only; the REAL
  funnel/fusion, not a re-implementation) with a synthetic Namespace:
  --sectors all (full active universe = the STANDARD pool), peers=builtin,
  earnings_top = pool size (funnel never truncates: E features for every
  quality-OK name; below-gate names honestly carry e_missing=1), mode
  standard fields, timeout large, quiet. Harvest: ctx.regime (MacroState),
  quality signals (score/pillars/flags/rank/coverage), earnings signals
  (score/p_next_big/facts), decisions (conviction). Cache each date to
  ml_data/cache/dates/<as_of>.json; resume skips cached dates (crash-safe
  against the sandbox killing processes).
- Features ~X: Q score, 6 pillars, q_rank, q_coverage, q_flag_count,
  q_veto, E score, p_next_big, beat_rate, last4_big, streak_big,
  qtrs_since_big, days_since_last_earnings, conviction, macro tilt (per
  name), macro confidence, dominance, leverage, credit_on, regime one-hot
  (2), sector one-hot (11), + *_missing for E-side/Q-side NaN-ables, +
  within-date rank-normalised copies of the key continuous features.
  NaN stays NaN (float32 X).
- Targets (DESIGN_NOTES.md gets the full argument + rejects): y_q = 63
  TRADING-day forward return beats SPY (quality is slow); y_e = beats SPY
  over ~30 trading days after the NEXT earnings event strictly after
  as_of (NaN if no event in window); y_m = sector ETF beats SPY next
  calendar month (ETF_TO_SECTORS keys minus SPY = 7 ETFs). Raw ret_21 /
  ret_63 stored so other targets can be rebuilt. Price field: Yahoo
  adjusted close (earnings_engine.prices, auto_adjust) for tickers+SPY+
  ETFs; delisted/unpriced names recorded in the manifest, never dropped
  silently; universe delisted/renamed refs listed in the manifest.
- Default date range EXCLUDES month-ends whose 63td label window extends
  past today (end = month_end_floor(today) - 3 months) => pilot dates
  2025-07-31 .. 2026-06-30, all fully labelable. --freq monthly|quarterly.
- Output ml_data/dataset_v1.npz (np.savez_compressed, all arrays
  non-object dtypes so allow_pickle=False works): X float32,
  feature_names, tickers, as_of datetime64[D], sector, y_q, y_e, ret_21,
  ret_63, group, + additive extras documented in DESIGN_NOTES (event_date,
  label_end_63, q_missing/e_missing for the embargo check).
  Macro block: macro_X, macro_feature_names, macro_etf, macro_as_of,
  y_m, macro_group (+ macro_ret_1m extra). manifest.json: schema version,
  engine + master versions, config hashes (master CONFIG + quality
  config_hash), date range, row counts, NaN rate per feature,
  pit_verified per engine, survivorship + delisting disclosure,
  price field, embargo statement.
- --verify FILE: loads with allow_pickle=False; checks shapes/dtypes/
  key parity; days_since_last_earnings >= 0; event_date > as_of;
  label_end_63 vs next as-of overlap (states the embargo: purge =
  63 trading days; monthly freq overlaps 2 next dates, quarterly none);
  class balance per target (fails degenerate); NaN rates match manifest.
- --workers/--offline/--cache-dir honoured by passing through to the
  master Namespace (offline -> master's existing guards, cache miss =
  honest error). Live progress line on stderr per date + per-name
  quality progress via the existing callback seam.

## 5 · Gates for this phase
reuse_report.md written; PIT status per engine reported with run
evidence; ml_dataset --verify passes on the pilot; 12-date pilot reloads
cleanly; suite green (existing 143 + new contract/dataset tests, red
first where behavior changed); zip + HANDOFF with REUSE DECISIONS, PIT
STATUS, TARGETS + why, and exact run commands with expected time.
