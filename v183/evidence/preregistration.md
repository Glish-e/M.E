evidence/preregistration.md — PHASE 0 task 7.
Written BEFORE any backtest or ML training/evaluation run in this build
(phase 0 runs none; the first eligible run is in phase 5/6/7). Hashed
into the release manifest at phase 9 per spec Section 9.

Reconciliation note (disclosed): two interactive choices were made while
the master prompt was believed missing: universe = full universe, and
thresholds = "in-tree gates" as a fallback. The master prompt then
arrived (defect C-1). Its Section 5.8 / Section 6 gates govern and are
locked below; they strictly SUBSUME the in-tree ladder (n_oos >= 100,
IC > 0, beats the raw-score baseline, Brier skill > 0 are all contained
in Section 6). The full-universe choice matches spec Section 4 and
stands. Nothing here was chosen after seeing any result in this build.

------------------------------------------------------------------------------
1. HYPOTHESES
------------------------------------------------------------------------------
H1 (strategy): the five-layer M.E. ranking (quality x earnings x macro,
ML overlays only if a head passes the Section 6 gates, risk-sized LONG
book) carries incremental, out-of-sample, cost-adjusted predictive
information versus (a) the raw quality-score ranking, (b) an equal-weight
book of the same universe, and (c) SPY — measurable as positive mean
monthly cross-sectional rank IC with a 95% interval excluding zero, and
superior risk-adjusted LONG-basket performance.
H1-per-head (ML): each trained head (q, e, macro) improves on the
original rule-based baseline on IDENTICAL out-of-sample rows and time
groups.
H0: any required gate failing = "no edge demonstrated". H0 is an
acceptable, reportable outcome. Nothing will be tuned to avoid it.

------------------------------------------------------------------------------
2. UNIVERSE
------------------------------------------------------------------------------
- Verdict dataset: ALL sectors (every macro-mapped sector plus
  healthcare, financials, REITs, specialty) via the quality engine's
  pools; historical universe membership BY DATE; delisted names included
  where a data source exists. If no free source for delisted prices or
  membership is obtainable, the gap is documented precisely, the
  survivorship bias is BOUNDED (direction + rough size), and the
  manifest keeps the survivorship warning. Never silently today's
  constituents for past dates.
- Smoke fixture only (never counted for verdicts): the shipped 12-date
  tech-pool pilot (90 tickers, 1,080 rows, 47 stock + 9 macro features,
  ~36% missing E, ~1.2 effective independent months).

------------------------------------------------------------------------------
3. DATE RANGES AND LOCKBOX
------------------------------------------------------------------------------
- Monthly month-end as-of dates. Target span: the 36 most recent
  completed month-ends at dataset build freeze (built no earlier than
  2023-11-30 and ending no later than 2026-10-31 under the phase-0
  calendar; the ACHIEVED list is frozen in the dataset manifest BEFORE
  any training/backtest run, and the manifest's sha256 is appended to
  this file — dated and signed — at that moment, before results exist).
- If engines cannot serve a date, the date is skipped with a logged
  reason recorded in the manifest; fewer than 36 achieved month-ends
  means Q1 stays PARTLY and every head verdict stays fails-by-
  insufficiency. No date is added or moved after the first result.
- LOCKBOX: the most recent 6 achieved month-ends are held out of ALL
  development tuning; evaluated exactly once, at the end (phase 7), with
  settings frozen; reported even if bad.

------------------------------------------------------------------------------
4. WALK-FORWARD SCHEME (ML heads)
------------------------------------------------------------------------------
- Expanding-window, chronological, per head; group = as-of month; never
  shuffled across time.
- Outer purge + embargo >= the label horizon (from the dataset manifest,
  which encodes 63 trading days for q, 63+30 for e, 21 for macro).
- Inner CV: target-aware embargo per head (ceil(horizon_td / 21): q 3
  months, e 5 months, macro 1 month — the M1 port); calibration fitted
  on inner out-of-fold predictions ONLY; an uncalibrated fold
  contributes NO probability and is excluded from pooled metrics (M3).
- Feature selection INSIDE each fold (M2 port; v1.5.0's pooled
  selection is the defect being removed), with a perturbation test
  proving feature choice is label-independent of the test fold.
- GBM kept only if it beats logistic on pooled OOS monthly rank IC.
- Deterministic seeds everywhere; artifacts atomic; dataset sha256
  pinned in every model bundle and validation report.

------------------------------------------------------------------------------
5. LABELS AND PIT RULES
------------------------------------------------------------------------------
y_q: 1 if the 63-trading-day forward return beats SPY. y_e: 1 if the
30-trading-day return after the NEXT earnings event (first event
strictly after as-of, within 63 td) beats SPY. y_m: 1 if the sector ETF
beats SPY over the next calendar month. Fundamentals keyed by
filing/accepted date; prices cut at as-of; macro series from real-time
vintages where available (ALFRED), otherwise flagged "today's vintage —
approximate" in the manifest AND in every report that uses it. Missing
never imputed with information inside the leaky window; imputation
fitted on train folds only. A look-ahead sentinel test must pass
(perturb all data after t; decisions at t do not change).

------------------------------------------------------------------------------
6. INTEGRATED BACKTEST CONVENTIONS (spec 5.1-5.5)
------------------------------------------------------------------------------
- Monthly rebalances, chronological, the ACTUAL M.E. decision code at
  each date (not a re-implementation); ML shadow predictions logged.
- Execution: signals at close of t, trades at NEXT OPEN (fixed
  convention); costs 10 bps/side BASELINE with sensitivity at 5, 10, 25
  and 50 bps; slippage a documented function of volatility and ADV
  (zero if the ADV probe finds ADV unavailable — stated, not faked);
  cash earns ZERO (chosen: conservative; T-bill alternative not used);
  no leverage; no fractional impossibilities.
- Strategies compared on identical dates/costs: full rule-based M.E.;
  M.E. without ML (identical while all heads SHADOW — stated as such);
  M.E. with ML ONLY IF some head passed the Section 6 gates (else "not
  run — no validated head"); SPY; equal-weight of the same universe.
  Ablations: quality-only, earnings-only, no-macro, legacy vs v2
  missing-E, legacy vs vol_target sizing, rounded vs unrounded door.
- Metrics (net of costs, gross beside): CAGR, annualised vol, Sharpe,
  Sortino, max drawdown with dates, win rate, profit factor, turnover,
  average holding period, transaction costs, slippage, average cash %,
  sector exposure over time, performance by macro regime and by
  calendar year, rank IC per month, top-minus-bottom-quintile spread,
  hit rate of LONG vs universe median.
- Statistics: block bootstrap confidence intervals (overlap-aware);
  the number of independent periods stated next to every metric; the
  count of strategy variants tried disclosed; deflated / trial-adjusted
  Sharpe if more than a handful of variants were run.

------------------------------------------------------------------------------
7. PASS / FAIL GATES (locked; spec 5.8 + Section 6)
------------------------------------------------------------------------------
ML head promotion (ALL required, per head): >= 12 usable OOS periods;
>= 100 genuinely OOS observations; positive mean OOS rank IC with a
bootstrap interval reported; improvement over the rule baseline on
identical rows/time groups; positive Brier skill; stable sign across
>= 3 sub-periods or regimes; passes on the lockbox. Every head ships
SHADOW; activation additionally requires the hash-bound validation
report AND the owner running --activate by hand. Never on training
accuracy; never automatic. Final user-facing language until then:
"Shadow signal, not validated".

Integrated backtest, Q5 = YES only if ALL hold (out-of-sample, net of
the 10 bps baseline cost): (1) >= 36 monthly rebalances; (2) positive
mean monthly rank IC with the LOWER bound of the 95% interval above 0;
(3) the LONG basket beats the equal-weight universe AND SPY on
risk-adjusted terms — Sharpe AND drawdown, not return alone; (4)
positive excess return in at least 3 distinct regimes or years;
(5) the result survives 25 bps costs; (6) the lockbox is consistent in
sign. Any failure => Q5 = NO/PARTLY with the sentence "no edge
demonstrated", the confidence interval, and the effective sample sizes.

Environment pin (recorded phase 0): Python 3.12.16, numpy 2.1.3,
scikit-learn 1.5.2, joblib 1.5.3, scipy 1.14.1, pandas 2.2.3; to be
frozen in requirements-lock.txt (phase 1).

------------------------------------------------------------------------------
8. NO-TAMPERING RULE
------------------------------------------------------------------------------
After the first result from any preregistered run is observed, NOTHING
in this file may be edited in place: no threshold, window, universe,
date range, cost, metric, gate, or convention. Any necessary change is
a dated, signed AMENDMENT appended at the bottom of this file, with the
original text left intact and the reason stated. Thresholds, windows,
universes and dates are never tuned to make a number look good; "no
edge demonstrated" is a legitimate final answer and will be reported as
plainly as a pass.

Signed: the executing agent (Z.ai) for the owner, 2026-11-13
(Africa/Casablanca).

AMENDMENTS:
1. 2026-11-14 (Africa/Casablanca), the executing agent (Z.ai), phase 6.
   Dataset pin BEFORE the first backtest evidence run: the backtest
   evaluates the SHIPPED pilot dataset ml_data/dataset_v1.npz,
   sha256 e1e325ea0589807ad3a6b6814cb8739a2d6d23ee8ac0242229b1c9f901c3543b
   (shipped inside master_final.zip / the v1.5.0 lineage; built 2026-11-08,
   its own manifest records config_hash_master 16abf8cdc21f21a9 — that
   lineage predates this build's phase 0). No threshold, window, universe,
   date range, cost, metric, gate or convention in this file changes. The
   recorded per-date decision harvests this dataset ships
   (ml_data/cache/dates/*.json) are the REAL run_pipeline outputs its
   build captured; this build adds --backtest to CONSUME them (plus a
   --backtest-rerun path that calls run_pipeline directly) — it adds no
   second decision path. Sequence disclosed: the phase-6 unit tests were
   implemented red-first and their green run (suite-level) executed the
   dataset once as a test fixture; its numbers were neither inspected nor
   tuned before this pin; the official evidence run
   (evidence/phase6_backtest.json) follows this amendment and is the
   first result read.

2. 2026-11-19 (Africa/Casablanca), the executing agent (Z.ai), v1.8.1
   review fix F1. WIRING amendment only — no threshold, window,
   universe, date range, cost, metric or convention changes.
   Gate "3_beats_ew_and_spy" is pinned in this file as requiring BOTH
   the equal-weight comparison AND the SPY comparison. The shipped code
   could evaluate only the EW half: me/backtest.py:467 hard-capped the
   gate with a literal `and False` ("SPY half unanswerable here") and
   the detail label said "SPY: NOT AVAILABLE (gate unanswerable — Q5
   capped)". The v1.8.0 build DID add the owner tool to answer it
   (scripts/owner_fetch_spy.py -> --bt-spy owner_results/spy_monthly.json),
   so the cap is stale wiring, not a threshold choice. Amendment, fixed
   BEFORE the first run of the new code:
   - With a REAL --bt-spy series loaded (owner-fetched SPY monthly
     closes, JSON; unit tests use SYNTHETIC loopback series labelled
     SYNTHETIC — never presented as real):
       pass(gate 3) = beats_ew  AND  net Sharpe @10bps over the
       dataset month-end dates  >  SPY Sharpe over the SAME dates  AND
       net max drawdown @10bps <= SPY max drawdown + 1e-9.
     SPY Sharpe/MDD are computed on the SPY monthly returns restricted
     to the dataset's rebalance dates (mean/std*sqrt(12) on monthly
     simple returns, matching the book's monthly convention; MDD on the
     compounded SPY total-return index). If the SPY file overlaps fewer
     than 12 of the dataset's dates, the gate stays UNANSWERABLE and the
     overlap count is printed.
   - With NO --bt-spy file: the label stays exactly
     "SPY: NOT AVAILABLE (gate unanswerable — Q5 capped)" and the gate
     does not pass on the SPY half (the EW half alone never passes
     gate 3). This is the status quo, preserved.
   - The verdict formula (_bt_verdict: Q5 = YES only if all six gates
     hold) is unchanged; nothing else in this file changes.
   Sequence disclosed: this amendment is written before any run of the
   new gate code (tests were written red-first against the CURRENT
   capped behaviour; the F1 fix lands after this amendment and the first
   observed result of the new code is the green test run + the shipped
   evidence/phase6_backtest.json re-check, which still runs with NO
   --bt-spy file and therefore must reproduce the UNANSWERABLE label
   unchanged).
