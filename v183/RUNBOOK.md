# master.py RUNBOOK — v1.8.2 (one page)

Every command below was executed on this build (v1.8.0 baseline
2026-11-14; v1.8.1 2026-11-19; v1.8.2 hardening 2026-11-20) — quoted
lines are real last lines and times. Deep reference: docs/ADVANCED.md
(design notes, the code registry table, long procedures) and
evidence/net_bounds.md (network worst-case bounds). RESEARCH SCREENER —
no live trades are placed; the live plan is GROSS of costs (the footer
shows the 2 x 10 bps round-trip ESTIMATE; the backtest nets the
preregistered 10 bps/side, 5/10/25/50 sensitivity).

## 1. Install + check

    pip install -r requirements.txt     # numexpr/bottleneck floors pinned (F7)
    python3 master.py --doctor           # 0.8 s
    engines   meds ok v14.7.0  quality ok v3.4.1  earnings ok v3  (hashes match)
    network   reachable (8 ms)
    NEXT: python3 master.py --warm (first cache fill)

## 2. Run

    python3 master.py MU --mode quick          # 6.4 s
     1  MU  tech  WATCH  ████████░░░░ 69 B  80 A  n/a  0%  -0.5
    python3 master.py --tickers MU,NVDA,AAPL,AMD,META --mode quick   # 10.8 s
    python3 master.py --sectors tech --mode quick --top 5    # 24.6 s
     0 LONG · 33 WATCH · 57 AVOID · 85 hidden (--top 5 / min-conviction 0)

quick vs standard vs deep = depth presets; the DATA mode also has its
own flag: --net auto|online|offline (v1.8.2; conflicts with --mode
auto/online/offline or --offline are a clear exit-2 usage error; --net
online keeps the exit-3 probe contract). Slow run / every engine
failing? Step 0 of OWNER_RUN.md (scripts/owner_net_check.sh) names the
dead host in seconds; the breaker (consecutive OR rate trip) fails
fast, the brownout guard (NET_BROWNOUT_S) bounds a hanging network.
The run budget is depth-derived (quick 600 / standard 1200 / deep
4500 s, RUN_BUDGET_BY_DEPTH; MASTER_RUN_BUDGET_S still overrides);
worst-case bounds: evidence/net_bounds.md.

## 3. Offline and replay

Offline = cached truth only, zero sockets, ages labelled (within the
publication cadence and healthy = refresh-due, not STALE — v1.8.2):

    python3 master.py MU NVDA --mode quick --offline      # 5.2 s

Freeze + replay (the reproducibility gate; a DEDICATED cache makes the
freeze exact):

    python3 master.py MU NVDA --mode quick --cache-dir /tmp/f1/cache \
        --freeze /tmp/f1 && python3 master.py --replay /tmp/f1
    replay OK: 2 names identical to the frozen manifest (2.0s, offline)

## 4. Backtest (v1.8.1: gate 3's SPY half is COMPUTED from a real series)

    python3 master.py --backtest             # 0.2 s (recorded decisions)
    verdict    no edge demonstrated
    SPY        SPY: NOT AVAILABLE — no benchmark series in the pilot
               (gate 3's SPY half unanswerable; never faked)

    python3 scripts/owner_fetch_spy.py    # [owner, network] then:
    python3 master.py --backtest --bt-spy owner_results/spy_monthly.json
    # REAL series computes the SPY half; SYNTHETIC never does (R7)
    python3 master.py --backtest --bt-start 2026-02-28 --bt-end 2026-05-31
    python3 master.py --backtest --bt-breaker
Dates outside the dataset = OWNER ml_dataset.py --start/--end/--freq.
Every run logs to evidence/backtest_runlog.jsonl.

## 5. ML

    python3 ml_dataset.py --dates 3 --sectors tech --out /tmp/ml   # 13m40s
    python3 ml_train.py --dataset ml_data/dataset_v1.npz --out /tmp/models
    l_train] head macro: 35 usable OOS rows · IC +0.368 · verdict
    insufficient evidence · shipped SHADOW; heads: SHADOW in master too

Every head ships SHADOW (a shadow signal, not validated — it changes no
ranking). `--activate` is manual-only, owner-run, hash-bound.

## 6. Tests

    python3 test_master.py          # Ran 605 tests in 42.9s — OK
    python3 master.py --selftest    # the same suite

## 7. Exports

    python3 master.py MU NVDA --csv out.csv      # -> out.csv (3 rows)
    python3 master.py MU NVDA --json            # -> stdout, one object
    python3 master.py MU NVDA --md r.md --html r.html
Files land ONLY where you point them. JSON never carries NaN (the
v1.8.2 additive keys are "fetch_health" and provenance's
"refresh_failed"; schema locked by tests).

## 8. Network resilience (v1.8.1; v1.8.2 bounds in net_bounds.md)

    python3 master.py MU --mode quick     # bounded by the run budget: after
    # it the run renders what it has and the PROCESS exits within seconds
    python3 master.py --retry-failed      # re-fetch ONLY the last run's
    # failed transient items (404 tickers are NEVER retried)
    python3 master.py MU --strict/--lenient   # degraded -> exit 2 (CI) / 0
Every run ends with FETCH HEALTH (per host/layer ok/fail/skip + totals +
"recovered n of m" + skipped items with the fix; sample: docs/CLI.md).

## 9. Troubleshooting (exact message → one-line fix)

| exact CLI message (abbrev.) | fix |
|---|---|
| colour off: NO_COLOR is set — unset NO_COLOR or use --color always | unset NO_COLOR, or pass --color always |
| ml heads UNAVAILABLE = version/environment mismatch — retrain with ml_train.py | retrain with this tree's ml_train.py (sklearn pins differ) |
| providers failed with NETWORK_ERROR under offline mode (sec_edgar/yahoo_chart=net:offline) | cache miss offline: python3 master.py --warm (fill caches) or --mode online |
| W_STALE_CACHE — cache past its cadence (macro 45d monthly / quality 135d quarterly / earnings 5d daily) or a failed refresh (v1.8.2: within cadence + healthy = refresh-due, NO warning) | python3 master.py --warm (refresh the caches) |
| cache dir not writable for an online run (exit 2) | python3 master.py --cache-dir /tmp/qe (writable) or --mode offline |
| W_EARNINGS_MISSING — fewer than 4 usable quarters or the provider failed | python3 master.py --warm (fill the earnings cache) |
| sec_edgar=cik_map_failed (sec.gov 403s the default contactless UA) | export SEC_USER_AGENT="your-name you@example.com" |
| master: exit 4 — no result / NO-GO: quality scored 0/N names | python3 master.py --warm (then rerun; the offline guard refused the misses) |
| REPLAY MISMATCH (exit 65) / [freeze] cap 256 MB hit | re-freeze with a DEDICATED cache: --freeze D --cache-dir D/warm (exact) |
| W_HOST_BREAKER_OPEN — host breaker open (calls fail fast) | wait for the cooldown; bash scripts/owner_net_check.sh verifies per-host |
| W_ITEM_SKIPPED — item skipped (404/delisted, listed with the fix) | python3 scripts/universe_override.py add TICKER sector delisted "note" (warns on a sector/engine-group mismatch, v1.8.2) |
| W_RUN_BUDGET — run budget exhausted (rendered what it had) | python3 master.py --retry-failed, then rerun (caches kept filling) |
| W_NET_FALLBACK_CACHE — auto mode: network probe failed | offline-from-cache served with ages; --mode online keeps exit 3 |

Registry (every code, full text): docs/ADVANCED.md § registry table.
