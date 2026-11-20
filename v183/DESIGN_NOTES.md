# DESIGN_NOTES.md — ml_dataset.py v1 (phase 4)

Companion to `ml_dataset.py`; the reuse decisions live in
`evidence/reuse_report.md`, the PIT proofs in `evidence/phase4_pit_probes.txt`.

## Targets — chosen and why (one line each, arguments below)

- **y_q = 1 if the 63-TRADING-day forward return beats SPY.** Quality
  (ROIC / margins / balance-sheet pillars) is a SLOW signal: factor drift
  studies put quality-spread horizons at one to three months, and master's
  own fusion treats quality as the slow 0.65-weight layer. 63 trading days
  ≈ one quarter matches the earnings-cycle cadence the quality score
  actually updates on.
- **y_e = 1 if the ~30-trading-day return after the NEXT earnings event
  beats SPY (entry = first trading close after the report; event must fall
  within the 63-td window after as_of; NaN if no event).** The earnings
  engine's own thesis is post-earnings drift after BIG beats; its backtest
  rule (entry_lag=1, hold 90 calendar days, +20% take-profit) is a TRADE
  rule, not a label — the label keeps the engine's entry convention (the
  first tradable close after the announcement, fair for before-open AND
  after-close reporters) with a fixed 30-td window so every event is
  measured identically and no take-profit path dependence enters the
  target.
- **y_m = 1 if the sector ETF beats SPY over the next calendar month.**
  meds is a MONTHLY regime engine (as-of floors to the last completed
  month end; the basket trades next month), so the macro head must be
  scored at the horizon the engine itself trades.
- **Raw ret_21 and ret_63 are stored** so any other target (cross-sectional
  ranks, volatility-adjusted windows, longer quality drift) can be rebuilt
  from the same rows without re-fetching.

### Alternatives rejected
- *Absolute positive return (y = ret > 0):* mixes the market regime into
  every label; the beat-SPY form is regime-neutral and matches how the
  screener will be used (rank names, not time the market).
- *Quality-quintile spread labels (quality.py evaluate()-style):* that is
  an evaluation of the QUALITY ENGINE, not a per-name label; it discards
  the 80% of names outside the top/bottom buckets.
- *The earnings engine's own trade simulation as the label (exit on
  take-profit/stop):* path-dependent exits leak the RULE into the target;
  a fixed window measures the signal, not the rule.
- *meds build_ml_dataset's next-month basket NET return:* a portfolio
  return of the whole long/short basket with costs — wrong unit (month,
  not ETF x month) and it embeds the engine's own sizing.
- *Multi-month y_m (63 td like y_q):* the regime basket rotates monthly;
  a 3-month macro label would straddle two different signal vintages.
- *Dropping rows without a y_e event:* the spec says NaN, and the missing
  pattern itself is informative (event timing is a feature, not noise).

## Features (X, 47 columns; `feature_names` in the npz is authoritative)

Q block: q_score, q_rank_pct (rank/pool — the STANDARD sector-pool
percentile position), q_coverage, q_flag_count, q_veto, six pillar scores.
E block: e_score, p_next_big, beat_rate, last4_big, streak_big,
qtrs_since_big, days_since_last_earnings, e_confidence. Fusion:
conviction. Macro (per name): macro_tilt, macro_confidence,
macro_leverage, macro_credit_on, regime one-hots (defensive, risk_on).
Sector one-hots (11). Missing flags: q_missing, e_missing,
p_next_big_missing, days_since_missing (e_missing=1 is exactly "below the
quality gate or unscoreable" because the funnel is opened to every gated
name — the funnel never truncates in this dataset). Within-date
rank-normalised copies (r_*) of the six key continuous features —
cross-sectionally comparable, NaN preserved.

**Per-head budget (the ~30 tip):** y_q head — q block + pillars (13),
conviction, macro block (6), sector one-hots (11), r_q_score/r_conviction
(2) = 33 columns, drop sector one-hots to 10 by using a baseline sector if
you need <=30. y_e head — e block (8), q_score, conviction, macro block
(6), e_missing/days flags, r_e_score, r_p_next_big = ~20. y_m head — the
9 macro features only. The npz carries everything; heads SELECT, the
dataset does not pre-truncate (H2 spirit: no hidden tuning).

## Labels — price field and delisting

Price field: **Yahoo daily adjusted close** (split+dividend adjusted,
`earnings_engine.prices`, auto_adjust=True) for tickers, SPY and the seven
sector ETFs — ONE source for every number so y_q/y_e/y_m are comparable.
Feature-side prices are cut at as-of by the engines (proven); label-side
prices are strictly after as-of (entry basis = last close <= as_of, exit =
the 21st/63rd trading row after it). A name whose series is too short for
the horizon (delisted mid-window, young listing, no Yahoo data) keeps its
row with NaN targets and is listed in the manifest
(`delisting_and_gaps.forward_price_gap_names` + the universe's own
delisted/renamed members) — recorded, never dropped silently. The universe
itself is today's active listing set: survivorship-biased by construction
and labelled as such in the manifest and every summary.

## Date grid and the label-horizon embargo

Default end = floor(today) − 3 months, so every included month-end has a
COMPLETE 63-td forward window (no truncated-label rows by design; NaN
labels then mean genuine data gaps, not calendar truncation). Monthly
grids OVERLAP by construction (63 td > 1 month): consecutive dates share
label price windows, so walk-forward training needs purge+embargo >= 63
trading days (3 monthly periods; quarterly grids need 1) and rows must be
grouped by `group`, never shuffled across time. Quarterly grids do not
overlap (63 td fits inside one quarter) — `--verify` hard-checks that when
the grid is quarterly and states the embargo when monthly. `event_date`
and `label_end_63` are stored per row precisely so the embargo can be
audited from the file alone.

## Pilot scope (STEP D): the tech STANDARD pool

The pilot scores `--sectors tech` — the quality engine's active tech
universe (~94 names) with the standard sector-pool percentile basis
(peers=builtin, pools never truncated, funnel opened to every gated name).
This is NOT quick mode (no watchlist ranks). Reason: measured cost. Each
historical as-of needs a fresh price window per name (the price cache
merges ranges but each new window-end is one Yahoo call), so the full
671-name universe x 12 monthly dates is ~8,000 quality price fetches —
measured at the shared limiter's pace that is 2.5-4 hours of fetching;
the tech pool is ~1,100 fetches (~40-60 min) and exercises every code
path identically. The full-universe build is the SAME command with
`--sectors all` (documented in the HANDOFF with the expected time).

## Build mechanics

Per as-of date, ml_dataset builds the same Namespace the CLI builds
(`--sectors ... --as-of ... --mode standard`), opens `--earnings-top` to
every gated name, runs the REAL `master.run_pipeline` and harvests the
layer signals — adapters only, engines never edited. Each date's harvest
is cached to `ml_data/cache/dates/<as_of>.json`; a killed run re-invokes
and resumes (`--max-dates N` bounds one invocation; `--restart` forces a
rebuild). `--offline` passes through to master's existing guards
(engine cache miss = honest error, recorded per date). `--cache-dir`
redirects quality+earnings caches (master's own --cache-dir semantics).
Progress lines go to stderr; the summary to stdout.
