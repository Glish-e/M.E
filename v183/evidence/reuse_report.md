# reuse_report.md — Phase 4 STEP A: capability discovery (read-only, no coding)

Method: the spec's grep list run over every file in the folder
(evidence/phase4_discovery_greps.txt has the full counts), full reads of
master.py / earnings_engine.py, targeted reads of quality.py (15,994 lines)
and meds.py (9,604 lines), and every engine's --help actually RUN
(transcript in evidence/phase4_cli_surfaces.txt). Zero hits anywhere for
sklearn / joblib / pickle — no ML code exists in any engine. Exactly one
np.savez exists (meds macro_ml.npz). master.py has no dataset code.

CLI reality vs the prompt's examples (code wins): earnings_engine.py has NO
subcommands (flag-based CLI; `backtest()`/`signals()` are module APIs, there
is no `plan`); quality.py has scan/score/validate/livecheck/selftest; meds.py
is flag-based (--audit/--from/--to/--ticker/--ml/--pit-manifest) — there is
no `regime history` subcommand, span() + --audit is the history surface.

| capability | file:function:line | point-in-time safe (how proved) | output format | decision | why |
|---|---|---|---|---|---|
| per-(ticker,as_of) quality score, pillars, flags, sector rank | quality.get_quality_score :6619 via _scored_universe :6579, score_universe :6052 | YES — filing-availability cut (FundamentalsView :4394, fact_available_date :4301); RUN: deterministic twice, 3,072 traced facts all available_date<=as_of, boundary probe on accession 0000723125-24-000019 (evidence/phase4_pit_probes.txt) | dict | REUSE | exactly the STANDARD-pool feature source; master's QualityLayer already adapts it |
| sector percentile pools (the STANDARD pool) | quality score_universe :6052 + _assign_sector_ranks :6245 | same as above | per-name dict | REUSE | "standard, never quick" is precisely peers=builtin sector pools; master --sectors selects them |
| whole-universe scan with resume | quality.scan_main :6900 (scan_state.json, --max-fetch) | single-date scorer, same PIT core | terminal + optional snapshot CSV | ADAPT (pattern only) | resumable cold passes inspired ml_dataset's per-date cache; scan itself scores ONE date and cannot join L1/L3/labels |
| forward-return evaluation harness | quality.evaluate :7277 + PriceLookup :7207 | label pattern: adjusted close preferred, window from snapshot dates, GROSS spreads, delisting counted | dict report | ADAPT (pattern) | its row unit is snapshot PAIRS for quintile spreads, not (ticker,as_of) rows; labels here need per-name horizons |
| PIT validation harness | quality._pit_validate :7615 (--freeze-date, in/out-sample) | its own proof harness for the quality engine | JSON report | NOT USED for build | validates the engine's own historical scoring; phase-4 STEP B probes cover our need |
| per-event EPS surprise, walk-forward accuracy, p_next_big | earnings_engine _metrics_arr :160, _calibrate :236, validate :781 | YES — _window :640 cuts quarters to date+provider-lag < as_of; RUN: deterministic twice, max public quarter < as_of (MU 2024-06-26 vs as_of 2024-06-30) | DataFrame | REUSE | the E features AND p_next_big come straight from master's EarningsLayer calling analyze(as_of=) |
| per-event backtest, forward returns vs SPY | earnings_engine.backtest :840 (_simulate :352, entry_lag=1) | YES — event scores use only public quarters; entry = first trading day after the report | BacktestResult | ADAPT (window convention) | y_e copies the entry convention (first trading day after the event) but uses a fixed ~30-trading-day drift window vs SPY, not the take-profit rule |
| daily price source (adjusted close) + cache | earnings_engine.prices :266 / yahoo_prices :84 (auto_adjust=True), px CSV cache | prices are a label INPUT; labels use closes strictly after as_of by construction | pd.Series | REUSE | ONE fetch per ticker covers every date (start->today); same source for tickers, SPY and the sector ETFs keeps y_q/y_e/y_m comparable |
| macro regime per as_of | meds.regime_now :7917 (as-of floor :7735, _apply_pit_lags :823) | APPROXIMATE — deterministic on every consumed field, but series are fetched at TODAY's vintage and cut at as_of (pit_mode=approximate_pit_lag, the engine's own label); RUN-verified | dict | REUSE (labelled) | master's MacroLayer already adapts it; dataset manifest carries pit_verified.meds=false |
| macro ML dataset | meds.build_ml_dataset :8803 + CLI --ml :9472 | macro panel aligned month t -> next-month basket return | macro_ml.npz (X/y chunks) | NOT REUSED (parallel rejected) | wrong row unit (month, not ETF x month) and wrong target (regime basket NET portfolio return, not per-ETF beats-SPY); its panel features stay inside meds. Our macro features come from master's macro adapter instead — no parallel regime pipeline built |
| regime history/backtest | meds span :8488, mrs_at :7749, Backtester :4716 | engine-internal | DataFrames | NOT USED | the regime strategy's own history, not a (ticker,as_of) feature source |
| orchestration: funnel, fusion, conviction, as-of plumbing | master.run_pipeline :2059, fuse_candidate :1516, funnel_shortlist :1617 | as-of reaches all three layers; future-dated L3 output rejected (tested) | RunOutput | REUSE | ml_dataset drives the REAL pipeline per date — adapters only, no reimplementation |
| month-end date math | master.month_end_floor :541 | pure | str | REUSE | the date grid |
| config hashes | quality.config_hash :370; master CONFIG :192 | static | str | REUSE | dataset manifest provenance |
| quality snapshots | quality write/read_snapshot :6383+ | single-date score CSVs | CSV | NOT USED | per-date cache needs the L1+L2+L3 harvest + label inputs, not quality-only rows |
| (ticker, as_of) feature/label rows -> npz | NOTHING anywhere | — | — | BUILD ml_dataset.py | the actual gap: no file assembles cross-layer features and forward labels |

REUSE DECISIONS (one line each, for the HANDOFF):
- quality features: REUSE via master's QualityLayer (standard sector pools).
- earnings features + p_next_big: REUSE via master's EarningsLayer (analyze
  as_of; funnel opened to every gated name — no truncation).
- macro features: REUSE via master's MacroLayer (regime_now as_of), labeled
  PIT_APPROXIMATE.
- price/event source for labels: REUSE earnings_engine.prices + .history.
- y_e window convention: ADAPT the engine's entry lag (first trading day
  after the event) with a fixed 30-td drift window vs SPY.
- meds --ml macro_ml.npz: NOT REUSED — wrong unit/target; documented so no
  parallel macro pipeline gets built later.
- quality scan/validate/pit harnesses: NOT USED for the build (single-date /
  engine-self-validation tools); their resume + PIT patterns were copied.
