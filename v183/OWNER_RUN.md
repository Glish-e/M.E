# OWNER_RUN.md — the one-page owner runbook (v1.8.1)

Run these ON YOUR MACHINE (network + API keys: FREDAPI or FRED_API_KEY,
SEC_USER_AGENT recommended, FINNHUB_API_KEY optional). The agent never
runs them (R11); until each step's output returns, its result is
AWAITING OWNER DATA — never faked. Verify everything you return:

`python3 scripts/verify_owner_results.py` (exit 0 = trust; the
--negative-control run must exit 1 naming its corrupt file).

WHEN A RUN IS SLOW OR EVERY ENGINE FAILS, run step 0 first — it names
the dead host in seconds (master's per-host circuit breaker then fails
fast on it; an auto run falls back to offline-from-cache):

0. `bash scripts/owner_net_check.sh` — per-host reachability + latency +
   key-presence (NAMES only, never values) into
   owner_results/net_check.txt. PowerShell: owner_net_check.ps1.

Commands, in order:
1. `python3 master.py --doctor` — health: engines+hashes, env NAMES
   (never values), cache ages, network probe, ML head states.
2. `python3 master.py MU NVDA AAPL --mode quick` — first real run
   (bounded by the RUN_BUDGET_S run budget: after it the run renders
   what it has and exits within seconds).
3. `bash scripts/owner_long_history.sh 120 all` — the resumable
   ~10-year dataset build (PowerShell: owner_long_history.ps1).
   Free-tier friendly: 6 new month-ends per pass, quota-exhaustion
   stops cleanly (finished dates stay cached — just re-run), a
   coverage line prints after every pass.
4. `bash scripts/owner_retrain.sh` — retrain the ML heads on YOUR
   sklearn (the shipped ones were trained on 1.5.2; retraining here
   re-pins them). Heads stay SHADOW; activation stays manual:
   `python3 ml_train.py --activate q` (refuses unless the validation
   verdict earns it).
5. `python3 scripts/owner_fetch_spy.py` — fetch the SPY monthly series
   into owner_results/spy_monthly.json, then:
   `python3 master.py --backtest --bt-spy owner_results/spy_monthly.json`
   (answers prereg gate 3's SPY half per AMENDMENT 2 — a REAL series
   computes the comparison; without the file the backtest honestly
   prints SPY: NOT AVAILABLE).
6. `python3 master.py --backtest` — the full-span integration backtest;
   sub-windows: `--bt-start/--bt-end YYYY-MM-DD` (month-ends,
   descriptive only); the what-if breaker: `--bt-breaker`.
7. `bash scripts/owner_bench.sh` — real-data timings into
   owner_results/bench_*.txt (stub/offline/online/backtest/train/build).
8. DEAD TICKERS (a 404 name is listed in FETCH HEALTH with the fix):
   `python3 scripts/universe_override.py add CFLT tech delisted "owner-verified dead 2026-11"`
   then `python3 scripts/universe_override.py add PSTG tech delisted "owner-verified dead 2026-11"`
   (v1.8.2 W6: both sit in quality's TECH group — a wrong sector would
   silently move a name between comparison pools; the tool now WARNS on
   a sector/engine-group mismatch and the shipped CSV is header-only.
   master's negative cache already stops refetching them for the TTL;
   the override row removes them from the ACTIVE universe for good).
   `--retry-failed` before that re-fetches any TRANSIENT failures the
   last run recorded: `python3 master.py --retry-failed`.
9. Zip owner_results/ and return it; then, here:
   `python3 scripts/verify_owner_results.py` (the negative control
   `--negative-control` must FAIL — it corrupts a file on purpose).

Notes: the engines (meds.py/quality.py/earnings_engine.py) are
read-only — ENGINES.sha256 must match before and after every step
(`sha256sum -c ENGINES.sha256`). Conviction is a score, not a
probability; this is a research screener, not investment advice, and
no live trades are placed.
