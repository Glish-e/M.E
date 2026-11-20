M.E. integration backtest — preregistration-locked evaluation (final phase §5)
========================================================================
verdict    no edge demonstrated
           Q5 = PARTLY — real out-of-sample decisions and labels, but the prereg full universe was never built (B-9 carried; owner command below) and SPY is unavailable
evidence   FIXTURE-CLASS: the shipped 12-date tech-pool pilot (90 names, 1080 rows) — the prereg's smoke fixture, never the full-universe verdict set
dates      12 month-ends 2025-08-31..2026-07-31 · 63-td overlapping label windows · ~4 independent label windows (stated per prereg §6: every metric above carries this n)
decisions  REAL-DERIVED (cached) — the recorded harvests of REAL run_pipeline runs
config     build-time CONFIG hash 16abf8cdc21f21a9 · current 59961633d3e77380 — the additions are exactly the disclosed evidence/rules_changes.md items (phase-8 diff discipline); no recorded decision was re-derived · hash recipe v1.8.0 (D-18-002): sets canonicalised — pre-v1.8.0 build hashes are not comparable
           EARNINGS_TP 0.15 (CONFIG, single source — engine + backtest read the same key) · RULESET legacy · costs 10 bps/side baseline (5/10/25/50 sensitivity) · next-open windows · cash earns zero · no leverage
ML         M.E. with ML: not run — no validated head (every shipped head is SHADOW, uncalibrated/insufficient)
           M.E. without ML == the recorded strategy — identical while all heads are SHADOW, stated as such
SPY        SPY: NOT AVAILABLE — no benchmark series in the pilot (gate 3's SPY half unanswerable; never faked)

per-date (gross 63-td window returns; entry at the next window open — the label window starts the trading day after as-of):
date        elig long      ic     long_gross  ew_gross  traded  regime
2025-08-31    87   10  -0.0959  +0.0243   +0.1167  1.000  risk_on
2025-09-30    87   11  -0.0952  +0.0261   +0.0648  0.091  risk_on
2025-10-31    87    0  -0.2514       n/a   +0.0291  1.000  defensive
2025-11-30    87    0  -0.2136       n/a   +0.0742  0.000  defensive
2025-12-31    87    0  -0.2477       n/a   +0.0732  0.000  defensive
2026-01-31    87    0  -0.2304       n/a   +0.1973  0.000  defensive
2026-02-28    87   13  -0.1394  +0.3885   +0.3787  1.000  risk_on
2026-03-31    87   13  -0.1505  +0.4662   +0.4256  0.154  risk_on
2026-04-30    87   13  +0.1762  +0.2218   +0.1163  0.154  risk_on
2026-05-31    87   10  +0.3062  +0.0709   +0.0020  0.408  risk_on
2026-06-30    87   10  +0.2711  +0.1243   +0.0487  0.000  risk_on
2026-07-31    87   11  +0.0920  +0.0528   +0.0886  0.473  risk_on

metrics (net of the 10 bps baseline, gross beside; overlapping windows, ~4 independent):
  rank IC         mean -0.0482 · 95% CI [-0.1547, +0.0662] · 4/12 months positive
  LONG basket     gross mean +0.1146/window · net mean +0.1142 · Sharpe 1.421 (low power, n=4) · Sortino n/a (n_neg<3) (low power, n=4) · n_neg 1
  EW universe     mean +0.1346 · Sharpe 2.000 (low power, n=4) · MDD 0.000 (LONG: 0.001)
  max drawdown    0.001 (window 2 -> 3) · win rate 0.667 · profit factor n/a (n_neg<3) (low power, n=4)
stress windows present in this dataset (descriptive, R19 — what the data contains, never a claim about regimes it does not):
  defensive/cash stretch  2025-10-31..2026-01-31
  worst rolling 3-window net -0.0003 (2025-10-31..2025-12-31) · worst single window -0.0010 (2025-10-31)
  top-bottom Q    mean spread -0.1068/window (quintile size 17)
  hit vs median   0.540 (LONG names beating the universe median)
  turnover        mean traded notional 0.357/window · avg holding 3.033 consecutive month-ends · cash dates 4/12 (avg cash 33%)
  sector exposure 100% tech every date (the pilot's universe — the prereg's cross-sector breadth was never built)
costs sensitivity (bps -> net mean/window, Sharpe):
      5 bps             -> +0.1144 · Sharpe 1.423 (low power, n=4)
     10 bps (baseline)  -> +0.1142 · Sharpe 1.421 (low power, n=4)
     25 bps             -> +0.1137 · Sharpe 1.415 (low power, n=4)
     50 bps             -> +0.1128 · Sharpe 1.405 (low power, n=4)
groups (net@10bps vs EW excess):
  2025: 5 dates · net +0.0097 · excess -0.0619
  2026: 7 dates · net +0.1889 · excess +0.0093
  regime defensive: 4 dates · net -0.0003 · excess -0.0937
  regime risk_on: 8 dates · net +0.1714 · excess +0.0163
lockbox (last 6 month-ends, evaluated once, no tuning follows): net sign + (full period +) · mean IC +0.0926 — consistent — uninformative (6 dates, one sign)
ablations (same recorded data, re-ranked — no re-decisions):
  quality-only IC  -0.1490
  earnings-only IC +0.0608
  v2 missing-E vs legacy  NOT RUN — re-deciding dates needs the engine caches (gone; REAL-DERIVED records only) — owner: python3 master.py --backtest --backtest-rerun --ruleset v2
  vol_target sizing        NOT RUN — the pilot's records carry no sizer weights — owner: python3 master.py --backtest --backtest-rerun --sizing vol_target
  rounded vs unrounded door NOT RUN — records store the rounded display conviction only — owner: python3 master.py --backtest --backtest-rerun --ruleset v2
gates (prereg §7 — Q5 = YES only if ALL pass):
  1_rebalances_ge_36           FAIL  12/36 month-end rebalances
  2_ic_lower_bound_positive    FAIL  mean rank IC -0.0482 · 95% CI [-0.1547, +0.0662] · positive 4/12
  3_beats_ew_and_spy           FAIL  vs EW: Sharpe 1.421 vs 2.000, MDD 0.001 vs 0.000 — does not beat EW; SPY: NOT AVAILABLE (gate unanswerable — Q5 capped; only 0 of the dataset's dates in the file)
  4_excess_3_groups            FAIL  positive net excess vs EW in 2 distinct year/regime groups (2 years, 2 regimes)
  5_survives_25bps             PASS  net mean @25bps +0.1137 · Sharpe 1.415 (low power, n=4)
  6_lockbox_consistent         PASS  last 6 dates: net sign + vs full + · IC +0.0926
variants tried in this run: 1 (the preregistered rule-based M.E.; ablations above are disclosures, not tuned variants) · seeds fixed (bootstrap 11/2000)
written phase6_backtest.json + phase6_backtest_report.md in 2.5s
