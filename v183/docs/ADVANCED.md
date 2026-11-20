# docs/ADVANCED.md — the deep runbook (relocated from RUNBOOK.md at phase 9)

The one-page RUNBOOK.md carries the day-to-day commands. EVERYTHING
else lives here, unchanged (relocated, nothing deleted). Sections below
keep their original numbering and content from the phase-8 tree.


last verified: 2026-11-08 (every command below was executed; times and
last lines are real outputs from this build)

> Research screener, not investment advice. The universe is
> survivorship-biased and every run says so in its footer.

**Contents** — [1 what](#1-what-this-is) · [2 quick start](#2-quick-start) ·
[3 layer map](#3-layer-map) · [4 modes](#4-modes) · [5 cookbook](#5-cookbook) ·
[6 reading output](#6-reading-the-output) · [7 data+cache](#7-data-and-cache) ·
[8 ML heads](#8-ml-heads) · [9 risk layer](#9-risk-layer) ·
[10 exit codes](#10-exit-codes) · [11 troubleshooting](#11-troubleshooting) ·
[12 trust](#12-trust-and-limits) · [13 glossary](#13-glossary)

---

## 1. What this is

A five-layer equity research screener (macro → quality → earnings → ML →
risk) you can run on a laptop, fully offline, in seconds, with every number
labelled by where its data came from and how old it is.

It is NOT: investment advice, a probability model, or a live trading
system. Conviction is a 0-100 heuristic score. Nothing here has beaten its
baselines out of sample yet (the ML heads all fail validation and stay
SHADOW).

## 2. Quick start

    # 1) install: python 3.12+, pandas/numpy; optional: scikit-learn,
    #    joblib (only the GBM SHADOW heads want them), yfinance (online
    #    price inputs). Set a SEC contact once:
    export SEC_USER_AGENT="Your Name you@example.com"

    # 2) first run — ONLINE quick pass (fills the quality/earnings caches
    #    you will live off; the shipped meds_snapshot already covers macro):
    python3 master.py --mode quick        # 7.0 s warm
    #    last line: research screener, not investment advice · survivorship-
    #    biased universe · timings 7.0s (macro 4.8s · quality 4.8s · ...)

    #    (A fresh install has no quality cache: an offline run BEFORE this
    #    step exits 2 with the honest NO-GO "quality scored 0/22 names —
    #    sec_edgar=cik_map_failed …". That is the design — nothing is
    #    invented offline. Warm once, then offline is 5.8 s forever.)

    # 3) first OFFLINE run (zero sockets, ages labelled):
    python3 master.py --mode quick --offline          # 5.8 s
    #    last line: … timings 5.8s (macro 3.8s · quality 3.8s · …)

    # 4) the standard pass (whole quality universe, warm):
    python3 master.py                                 # ~78 s warm, 8-25 min cold

    # 5) a healthy output looks like (real run):
    #  MASTER v1.5.0 · mode standard · net online (probe ok 8 ms) · ...
    #  data: macro cache 2026-10-31·8d OK | quality cache 2026-11-08·0d OK ...
    #   ✓ L1 macro ... ● OK    ✓ L2 quality ... ▲ DEGRADED  16/22 scored
    #  0 LONG · 4 WATCH · 1 AVOID — with warnings: earnings accuracy ...

    # 6) if it is not: python3 master.py --doctor  (one screen, ends with
    #    NEXT: <the single most useful action>). See §11 for specifics.

## 3. Layer map

    L1 macro   meds.py          regime gate + sector tilts; FRED monthly
      │                         (meds_cache/, materialised meds_snapshot/)
      ▼
    L2 quality quality.py      0-100 quality score, sector percentile
      │                         ranks, vetoes; SEC quarterly filings
      ▼                         (data/cache/, ~1.7 GB warm)
    L3 earnings earnings_engine timing score + plan on the top-K funnel;
      │                         earnings events + daily prices
      ▼                         (~/.earnings_engine_cache/)
    L4 ml      ml_train.py     SHADOW calibrated probabilities only —
      │                         never changes a decision (§8)
      ▼
    L5 risk    master.py       weights for LONG names, caps, cash, vetoes

## 4. Modes

`--mode` carries either the DATA mode or the DEPTH preset (they compose via
flags: `--mode quick --offline`, or `--mode standard --mode online` is the
same as `--mode online` for depth purposes).

| mode | what it does | data age | when to use | exit behaviour |
|---|---|---|---|---|
| offline | cached truth only, zero sockets, ages labelled, never writes | whatever the cache says (shown per layer) | plane, weekend, data paranoia, CI | never falls back to network; missing data = honest MISSING_DATA |
| online | refreshes stale/missing items only; retries transient errors | minutes old | you have the network and want freshness | `--mode online` with no network exits 3, never silently offline |
| auto (default) | one 2 s probe (DNS+TCP, no payload) picks online/offline | either | always | banner says which and why |
| quick (depth) | quality ranks vs the watchlist only, L3 top-10 | — | fast pass (5.8 s offline) | normal |
| standard (depth) | full sector-pool ranks, L3 top-25 | — | the real pass | normal |
| deep (depth) | 3600 s budget, L3 top-40, prefetch all | — | overnight | normal |
| stubs (`MASTER_STUBS=1`) | deterministic fake layers, loud banner | none | testing, demos | separate banner, never mixes silently |

## 5. Cookbook (every command executed; time measured on this build)

| # | goal | command | time | look for |
|---|---|---|---|---|
| 1 | default watchlist | `python3 master.py` | 78 s warm / 8-25 min cold | header `net online (probe ok …)`, `data:` row, timings footer |
| 2 | chosen tickers | `python3 master.py MU NVDA AAPL` | ~14 s warm | same decisions offline: `--mode offline` (12.7 s, identical) |
| 3 | fast pass | `python3 master.py --mode quick --offline` | 5.8 s | the whole chain, rough watchlist ranks |
| 4 | sectors | `python3 master.py --sectors tech --earnings-top 3 --mode quick --offline` | 13 s | 90-name tech pool, `SECTOR` column |
| 5 | cap band | `--cap mega` | — | honest exit 64 today: no market-cap data in refs (never silent) |
| 6 | explain a name | `python3 master.py MU --explain MU --mode quick --offline` | ~2 s | per-layer pillars, plan, provenance, fusion line |
| 7 | JSON | `python3 master.py MU NVDA --json` | ~14 s | `provenance` per layer, `net_mode`, `refresh` |
| 8 | warm the cache | `python3 master.py --warm` | ~80 s | `warm-up done — quality cache …` on stderr |
| 9 | freeze | `python3 master.py MU NVDA AAPL --mode quick --freeze /tmp/f1 --cache-dir /tmp/f1/warm` | ~20 s | `[freeze] … 39 files 15.7 MB` |
| 10 | replay | `python3 master.py --replay /tmp/f1` | 3.8 s | `replay OK: 3 names identical … fully offline` |
| 11 | doctor | `python3 master.py --doctor` | ~4 s | one screen + `NEXT: …` |
| 12 | train heads | `python3 ml_train.py --dataset ml_data/dataset_v1.npz --out ml_data/models` | ~40 s | three heads SHADOW, verdict `fails` (honest) |
| 13 | dataset plan | `python3 ml_dataset.py --dry-run` | 1 s | dates/tickers/rows/time/disk, builds nothing |

Real last lines you should match (trimmed):

    # 1  timings 77.7s (macro 75.5s · quality 75.5s · earnings 0.2s · ml 1.6s · risk 0.0s)
    # 6  quality data STALE: STALE_DATA — SECTOR_PEER_FALLBACK  (that is NEE's
    #    honest stale reason — run `python3 master.py NEE --explain NEE …` to see it)
    # 8  warm-up done — quality cache last write 1.3h ago; next: python master.py …
    # 10 replay OK: 3 names identical to the frozen manifest (3.8s, fully offline)
    # 12 [ml_train] head macro: logistic_np · 84 train rows · 35 OOS rows … verdict fails

Also worth knowing: `--check` (env + probe report), `python3 scripts/bench.py
--tag after` (speed table; see evidence/perf_*.txt), `--csv out.csv`,
`--min-conviction 50`, `--width 40..110`, `--no-color --ascii` for phones.

## 6. Reading the output

Real sample (standard online run, trimmed to what matters):

    MASTER v1.5.0 · mode standard · net online (probe ok 8 ms) · as of …
    data: macro cache 2026-10-31·8d OK | quality cache 2026-11-08·0d OK | …
     ✓ L1 macro     meds v14.7.0       75.5s  warm ● OK
         data cache · as-of 2026-10-31 · age 8d · OK
     ✓ L2 quality   quality v3.4.1     75.5s  warm ▲ DEGRADED  16/22 scored
         data cache · as-of 2026-11-08 · age 0d · OK
    L1 MACRO ── Credit Crunch & Liquidity Squeeze · Crisis
      conf 0.92 · lev 1.35x · risk budget 1.35 · LONG XLU XLP
     #  TICKER SECTOR ACTION CONV   Q      E      WT   MACRO FLAGS REASONS
     1  MU     tech   WATCH  71 B   80 A   52 B   0%   -0.5  –    Q 80 (A) rank 1/95 …
    20  NEE    util   AVOID   0 F   STALE  n/sel  0%   +1.0  …    quality data STALE: …
    0 LONG · 4 WATCH · 1 AVOID
    risk: gross 0% of 1.35 budget · cash 100%
    warnings: … HD: no earnings report since 2026-05-19 (173d) — a report
       date has likely passed since the cache was written

- **conviction** 0-100 heuristic = 0.65·Q + 0.35·E (missing-E ×0.90,
  weak-E ×0.5 renormalised) × macro tilt (±10% max). **A score, not a
  probability** — the footer repeats it every run. Under `--ruleset v2`
  a missing E is scored as the fixed conservative fill `E_MISSING_V2=0`
  on the un-renormalised weights (F3, v1.8.3): a missing name's base is
  WEAK-invariant and never rides the weak-tape renormalisation across a
  door (Q80 missing stays 52 WATCH, never 63 LONG).
- **merged consumer view** unbucketed consumer names are scored on the
  merged XLP+XLY view: when either basket is long, every consumer name's
  conviction is lifted ~+10% (`W_CONSUMER_MERGED`, v1.8.3). `--bucket
  staples,discretionary` separates the pools so a staples-long tape no
  longer lifts discretionary names (and vice versa).
- **action** LONG ≥ 60, WATCH ≥ 45, else AVOID (frozen thresholds).
- **grade** A/B/C/D/F bands on the conviction (75/60/45/30).
- **STALE** the layer kept its data and score but prints the age + reason;
  it never silently reads as fresh. The `data …` lines and the header
  `data:` row are the provenance: source (cache/network/mixed/stub),
  as-of date, age in days, status.
- **flags** engine warnings (e.g. `HIGH_ACCRUALS`); only
  `NEGATIVE_EQUITY` and `ALTMAN_DISTRESS` veto.
- **WT** the risk layer's weight for LONG names (0% here: credit-crunch
  regime, no LONGs, all cash — a deliberate stand-down, not a bug). A
  `*` on a WT cell marks the weight **ADV-unchecked** (v1.8.3, F9): the
  price feeds carry no volume, so the participation cap cannot bind
  (`W_ADV_UNAVAILABLE`); the JSON field `adv_checked` says the same.

## 7. Data and cache

| layer | where | size (measured) | freshness rule (CONFIG) |
|---|---|---|---|
| macro | `meds_cache/cache.json.gz` + materialised `meds_snapshot/` (shipped) | 0.6 MB | STALE if `effective_as_of` > **45 d** (monthly cadence) |
| quality | `data/cache/{cik_map,sec,sec_submissions,prices_v2}/` | ~1.7 GB warm | STALE if cache stamp > **135 d** (quarterly + filing lag) |
| earnings | `~/.earnings_engine_cache/*.csv` | ~5 MB | STALE if price history > **5 d**; per-name flag when no report for **135 d** |
| ML models | `ml_data/models/` | ~1 MB | pinned: sha256 + sklearn + master version |

- Refresh: just run online (`--mode auto` default) — the `[plan] refresh
  plan:` line says what is cached, the `[refresh]` line after the run says
  what actually got younger (`quality 41d -> 0d`).
- Offline never writes; it serves the last cached truth and labels the age.
- Clear a cache: delete the directory (safe — it refills online). Move it:
  `--cache-dir DIR` (quality+earnings). meds' cache lives next to `meds.py`
  by design (engine rule).
- Freeze an exact copy: cookbook #9 (the dedicated `--cache-dir` inside the
  freeze dir is what makes it exact — quality's cache files are
  engine-internal hash names, so per-ticker copies are not possible).

## 8. ML heads

Three heads ship (q, e, macro), all **SHADOW**: probabilities are logged
with their sample size, no decision changes. All three return verdict
"insufficient evidence" on the shipped 12-date pilot (v1.8.3, F8: the
numbers below are the SHIPPED validation files
`ml_data/models/validation_*.json` — the earlier table quoted the pre-B-3
report whose pooled feature selection read later test periods
(contaminated); those numbers are retained nowhere):

| head | model | n_oos | pooled OOS rank IC | baseline rank IC | verdict |
|---|---|---|---|---|---|
| q | gbm (pinned sidecar) | 261 (3 OOS periods) | -0.487 | +0.0377 (base-rate) | insufficient evidence |
| e | logistic (pinned sidecar) | 0 (0 OOS periods) | n/a | n/a | insufficient evidence |
| macro | logistic (pinned sidecar) | 35 (5 OOS periods) | +0.314 (monthly mean +0.368) | +0.298 (base-rate) | insufficient evidence |

NOTE (two different estimators, so the numbers stop looking
contradictory): the table above is the ML head's model-vs-baseline rank
IC over OOS periods; the backtest's "quality-only IC -0.1490" is the
quality SCORE vs the forward label over the 12 recorded month-end dates
(me/backtest.py) — a different estimator on a different sample. Neither
is out-of-sample evidence of edge: the pilot's 3-12 OOS periods sit far
below every sample-size gate.

Why ACTIVE is blocked: the a-priori rule needs monthly rank IC above BOTH
baselines AND positive Brier skill AND n_oos ≥ 100 — on 12 monthly dates
nothing qualifies (and the pilot sample warning says so in every report).
What unblocks it: the full-universe dataset (`ml_dataset.py`, cookbook #13
without `--dry-run`, resumable, hours), 60+ dates, then `ml_train.py`, one
head at a time. `--activate` refuses without a `beats` report whose
model_sha256 / dataset_sha256 pins match the model file and its training
dataset exactly (hash-bound activation, exit 2 on any mismatch — a
tampered file refuses before it is even parsed); a `beats` verdict itself
needs >= 12 usable OOS periods AND >= 100 usable rows AND a final model
calibrated on inner OOF — on the 12-date pilot every head honestly lands
at "insufficient evidence" and ships SHADOW. Sidecars are sha256-pinned;
a tampered or wrong-sklearn sidecar loads as
UNTRAINED with a one-line reason — never unpickled on trust.

## 9. Risk layer in plain words

L5 turns LONG names into weights inside the macro risk budget: inverse-vol
start, 10% single-name cap, 35% sector cap, a correlation-aware gross cap
(effective bets), and an estimated-drawdown veto (>30% est. DD ⇒ all
cash). Weights are fractions OF the budget; cash is explicit. The
estimated DD is **an estimate, not a probability**. Vetoes (budget < 0.25)
stand down to 100% cash, loudly.

## 10. Exit codes (phase-5 contract)

| code | meaning | was |
|---|---|---|
| 0 | clean run | 0 |
| 1 | degraded: result produced + warnings (incl. ml head UNAVAILABLE) | 0/1 |
| 2 | usage/config error (bad flag, bad value, unwritable cache) | 64 |
| 3 | network required (`--mode online`) but unreachable | 3 |
| 4 | no result / NO-GO (quality scored nothing / every layer failed) | 2 |
| 65 | replay mismatch (freeze dir does not reproduce) | 65 |
| 70 | unexpected internal error (traceback only with `--debug`) | 1 |
| 130 | Ctrl-C (names the phase it was in) | 130 |

Deliberate contract change (owner's mandate): **64 → 2**, **2 → 4**,
**1 → 70**; every affected test was re-pointed with justification
(R2). `--doctor` prints this table on every run.

## 10b. Error & warning code registry (central: codes.py)

Every stable code master can emit, with its layer, meaning and EXACT fix
command (generated from codes.py — the registry test fails if a code
used in the code base is missing here or lacks a fix):

| code | severity | layer | what | why | fix |
|---|---|---|---|---|---|
| E_CACHE_UNWRITABLE | error | cache | cache dir not writable for an online run (exit code 2) | read-only cache root: online runs must be able to refresh | `python3 master.py --cache-dir /tmp/qe (writable) or --mode offline` |
| E_HASH_MISMATCH | error | engines | engine file hash differs from ENGINES.sha256 | an engine was edited after the release hash was pinned | `python3 master.py --doctor (then sha256sum -c ENGINES.sha256 — restore the engine from the release zip)` |
| E_LAYER | error | any | a layer ended in ERROR state | the engine raised, timed out, or returned no usable payload | `python3 master.py --doctor (engine/health probe names the real blocker)` |
| E_NET_DOWN | error | net | network required but unreachable | explicit --mode online with a failed probe (exit code 3) | `python3 master.py --mode offline (cached truth) or --mode auto` |
| E_NET_OFFLINE | error | providers | providers failed with NETWORK_ERROR under offline mode | offline guard disables sockets; a cache miss has no fallback | `python3 master.py --warm (fill caches) or --mode online` |
| E_NO_RESULT | error | pipeline | no result / NO-GO: nothing usable was produced | quality scored 0 names or every layer failed (exit code 4) | `python3 master.py --doctor then python3 master.py --warm --mode online` |
| E_USAGE | error | cli | bad usage or config (exit code 2) | argument validation failed before any layer ran | `python3 master.py --help (the message names the exact flag)` |
| W_ADV_UNAVAILABLE | warning | risk | ADV liquidity guard UNAVAILABLE | no readable feed carries volume; nothing faked (owner decision pending) | `python3 scripts/adv_probe.py (see the probe verdict for the feed gap)` |
| W_BLOCKED_REASSERT | warning | ml | the overlay re-asserted a blocked row's AVOID | an overlay tried to un-block a vetoed row; the guard restored it | `python3 master.py --doctor (overlay bounds review — guard is correct)` |
| W_BT_DATE_SKIPPED | warning | backtest | a backtest date was skipped: no recorded decision record | ml_data/cache/dates/<date>.json is absent and --backtest-rerun was not given — the date is excluded LOUDLY, never silently | `python3 master.py --backtest --backtest-rerun (re-decide the date via run_pipeline and write its record)` |
| W_BT_FIXTURE_ONLY | warning | backtest | the backtest ran on fixture-class evidence only | the dataset is the shipped tech-pool pilot (or fewer than 36 dates) — the prereg full-universe verdict set was never built | `python3 ml_dataset.py --dates 36 --sectors all (owner: full network build, hours) then python3 master.py --backtest` |
| W_BUDGET_STANDDOWN | warning | risk | risk budget stand-down: no positions sized | budget NaN/zero/non-finite, or the DD envelope veto fired | `python3 master.py --doctor (risk CONFIG review)` |
| W_CONSUMER_MERGED | warning | macro | unbucketed consumer names share the merged XLP+XLY view | XLP and XLY both map 'consumer' at strength 1.0 (me/core.py ETF_TO_SECTORS): a long in EITHER basket lifts every unbucketed consumer name ~+10% conviction; staples and discretionary are not separated without --bucket | `python3 master.py --bucket staples,discretionary ... (split the consumer pools; bucketed names keep their own ETF)` |
| W_DD_VETO | warning | risk | drawdown veto fired (guard, working as designed) | estimated drawdown crossed RISK_MAX_EST_DD on the stated line | `python3 master.py --doctor (RISK_MAX_EST_DD review — the guard is correct)` |
| W_EARNINGS_MISSING | warning | earnings | earnings data missing for one or more names | fewer than 4 usable quarters or the provider failed | `python3 master.py --warm (fill the earnings cache)` |
| W_ENGINE_NO_VERSION | warning | earnings | earnings engine exposes no __version__ attribute | drift between the shipped engine and the tested one is undetectable through the attribute; the docstring version is reported instead | `python3 master.py --doctor (ENGINES.sha256 is the real integrity gate — sha256sum -c ENGINES.sha256)` |
| W_EQW_FALLBACK | warning | risk | sizer fell back to equal weights | the volatility-weighted path was impossible (all vols unusable) | `python3 master.py --warm (fill the price cache)` |
| W_FETCH_FAILED | warning | net | one or more fetches failed after retries | host unreachable / timeouts / 5xx persisted past the retry budget; the item was skipped, the run continued | `python3 master.py --retry-failed (re-fetch only the failed transient items), then rerun` |
| W_FRED_KEY_ABSENT | warning | macro | FRED key absent: public fredgraph.csv path used | FREDAPI/FRED_API_KEY unset — the public CSV path is used instead (this is NOT an error by itself) | `python3 master.py (set FREDAPI in the env for the API path — optional)` |
| W_FUTURE_REPORT | warning | earnings | an earnings report dated in the future was rejected | clock skew or a bad as-of; PIT discipline refuses future facts | `python3 master.py --as-of <YYYY-MM-DD> (pin the correct clock)` |
| W_HEAD_UNAVAILABLE | warning | ml | ml head UNAVAILABLE in this environment (run continued) | sklearn/numpy/joblib/python version mismatch, missing sklearn, or a corrupt/incompatible model file | `python3 ml_train.py (retrain on this environment's versions)` |
| W_HOST_BREAKER_OPEN | warning | net | a host's circuit breaker is open (calls fail fast) | NET_BREAKER_K consecutive failures opened the breaker; the cooldown (NET_BREAKER_COOLDOWN_S) gates one half-open probe | `wait for the cooldown then rerun; python3 scripts/owner_net_check.sh verifies per-host reachability` |
| W_ITEM_SKIPPED | warning | any | an item was skipped and listed (item, why, fix) | permanent failure (404/delisted/bad ticker) or an exhausted retry budget — the layer reports coverage (scored/total) | `check the ticker; dead names: python3 scripts/universe_override.py add TICKER sector delisted` |
| W_NET_DOWN | warning | providers | a provider request failed on the network (result still served) | DNS/TLS/connectivity failure while other sources or caches answered | `python3 master.py --mode offline (cached truth, ages shown)` |
| W_NET_FALLBACK_CACHE | warning | net | auto mode fell back to offline-from-cache | the auto-mode network probe failed; cached truth is served with ages labelled (--mode online keeps its exit-3 contract) | `python3 scripts/owner_net_check.sh (per-host reachability; run it first when a run is slow), then rerun online` |
| W_NET_OFFLINE | warning | net | offline mode selected: zero sockets, cache truth only | explicit offline (or MASTER_NET=offline); ages are labelled | `python3 master.py --warm --mode online (refresh the caches)` |
| W_NO_VOL_NO_STOP | warning | earnings | live plan carries no stop price | no usable price history for the trailing-126-td vol estimate | `python3 master.py --warm (fill the price cache so the vol stop exists)` |
| W_PEERS_WATCHLIST | warning | quality | quality ranks are relative to the watchlist only | --peers watchlist / --mode quick: rough percentiles against the requested names, not the engine's sector pools | `python3 master.py --mode standard (honest sector-pool ranks)` |
| W_QUALITY_FLAG | warning | quality | the quality engine flagged a name (e.g. ALTMAN_DISTRESS) | the engine's own per-name flags surfaced through the adapter (its thresholds are read-only engine policy) | `python3 master.py <ticker> --explain <ticker> (the per-layer breakdown names the driving metrics)` |
| W_RATE_LIMIT | warning | providers | provider rate limit (HTTP 429) | too many requests; provider asked to slow down (Retry-After honoured) | `python3 master.py --mode offline (retry after the Retry-After window)` |
| W_RETRY_BUDGET | warning | net | the run's total retry-time budget is exhausted | backoff sleeps + Retry-After waits + deferred cooldowns drew NET_RETRY_BUDGET_S to zero; later failures skip retries | `rerun when the network is back: python3 master.py --retry-failed` |
| W_RHO_FALLBACK | warning | risk | correlation fallback to the conservative rho assumption | not enough overlapping price history for a real correlation | `python3 master.py --warm (more price history => real rho)` |
| W_RUN_BUDGET | warning | pipeline | the overall run budget (RUN_BUDGET_S) was exhausted | the run rendered what it had after the budget; unfinished layers were salvaged/skipped, the process exited promptly | `python3 master.py --retry-failed (caches were still filling in the background), then rerun; or raise MASTER_RUN_BUDGET_S / RUN_BUDGET_S deliberately` |
| W_STALE_CACHE | warning | cache | a served cache is stale for its display threshold | newest input older than STALE_STATUS_DAYS (7d) AND either past its publication cadence (macro 45d monthly, quality 135d quarterly, earnings 5d daily) or with a failed refresh this run; inside the cadence with no failure the report shows 'refresh-due' instead and emits no warning | `python3 master.py --warm (refresh the caches; an offline run shows the ages by design)` |
| W_SYNTHETIC | warning | pipeline | SYNTHETIC stub layers rendered (not real engine data) | MASTER_STUBS=1 / hermetic test mode — never for decisions | `python3 master.py (unset MASTER_STUBS for real engine data)` |
| W_UNUSABLE_VOL | warning | risk | a name's volatility was unusable (dropped or pooled) | no usable price history for the trailing window | `python3 master.py --warm (fill the price cache)` |
| W_UNUSUAL | warning | pipeline | a warning could not be classified | text did not match a known pattern and carries no bracketed code | `python3 master.py --debug (capture the exact text and report it)` |
| W_CREDIT_OFF | warning | macro | credit terms excluded — macro conviction damped | the meds engine excludes its credit terms (no honest credit read this month); the scenario keeps its other terms at reduced conviction leverage — not trade-grade, disclosed | `python3 master.py --doctor (macro data review; credit returns when the engine's credit read does)` |
| W_MACRO_DEGRADED | warning | macro | macro layer DEGRADED (engine-reported warnings) | the meds engine reported data-quality warnings (stale or partial series); the regime keeps a damped confidence | `python3 master.py --warm (refresh the macro snapshot)` |
| W_MACRO_UNAVAILABLE | warning | macro | no regime context (macro missing or failed) | the macro layer produced no state: tilt n/a and the risk budget is capped at 1.0 (the conservative path) | `python3 master.py --doctor (macro engine/snapshot check)` |
| W_SHORTLIST_EMPTY | warning | earnings | earnings shortlist empty: nothing passed the quality gate | L3 runs only on L1+L2 survivors; zero survivors means L3 did not run (layer DEGRADED, honestly reported) | `python3 master.py --doctor (quality gate review) or widen the pool: python3 master.py --sectors all` |
| W_SCENARIO_RENORMALIZED | warning | macro | a macro scenario score was renormalized (terms excluded) | the engine's safe_weighted_score excluded failed series and renormalized the retained terms; retained weight below 70% is disclosed, never silent | `python3 master.py --doctor (the scenario panel names the failed series)` |
| W_EARNINGS_ACCURACY | warning | earnings | earnings layer accuracy verdict (descriptive) | the engine's own hit-rate verdict of high-rated names vs base names — descriptive context for the L3 signal | `python3 master.py MU --explain MU (per-name earnings evidence)` |
| W_EARNINGS_BACKTEST | warning | earnings | opt-in per-ticker price backtest summary | --earnings-backtest: naive edge statistics (clustered events overstate t) — descriptive only, never a verdict | `python3 master.py MU --earnings-backtest (opt-in flag; see the caveat in the warning text)` |


## 10c. Colour switch (phase 5, C-1)

`--color auto|always|never` (default auto) · `--no-color` = never ·
`--plain` = no colour and no decoration beyond the box (= `--no-color`).

Precedence (each row tested):

| flags/env | result |
|---|---|
| `--color always` | ON — beats NO_COLOR, pipes and TERM=dumb |
| `--color never` / `--no-color` / `--plain` | OFF (deliberate: silent) |
| auto + `NO_COLOR` set (non-empty) | OFF — beats FORCE_COLOR |
| auto + `FORCE_COLOR`/`CLICOLOR_FORCE` (non-empty, not "0") | ON — beats TERM=dumb |
| auto + not a TTY | OFF + ONE dim reason line with the fix |
| auto + `TERM=dumb` (no capable marker) | OFF + reason line |
| auto + TTY, no env | ON |

Windows: VT processing enabled via ctypes (no new dependency), with an
honest fallback reason if it fails. WT_SESSION / TERM_PROGRAM /
ConEmuANSI count as capable terminals. Depth: truecolor (COLORTERM) ->
256 (`*256color`) -> 16 — the palette is the SAME bright 16-colour set
at every depth. `--doctor` prints the full colour diagnostic.

## 11. Troubleshooting (symptom → cause → fix)

| symptom | cause | fix |
|---|---|---|
| `macro … STALE 45d+` | meds data older than a month | run online once (`--warm`), then offline is fast again |
| `credit OFF — not trade-grade` | meds says credit crunch | by design: tilt damped, some scenarios excluded |
| `no quality score (NO_DATA …)` | name outside the 682-name universe / no filings | `--sector T=group` to pin a pool; check §12 |
| bare `F 0` gone, reason shown | that IS the fix (stale names must explain themselves) | read the reason line; `--explain T` for the full story |
| `network required` exit 3 | `--mode online` with no network | `--mode offline` or drop the flag (auto) |
| `sidecar sha256 mismatch` | tampered/stale GBM model file | retrain (`ml_train.py`) — head stays UNTRAINED, run continues |
| `sklearn 1.x != trained-on …` | environment drifted vs the pinned model | pin the training env or retrain locally |
| timeouts, `quality timed out` | cold cache + slow providers | rerun (cache resumes); or `--warm`; or `--mode quick` now |
| `possibly delisted; no price data` (yfinance) | engine noise for dead tickers | harmless warning; names score without market metrics |
| empty watchlist / `no equity tickers left` | only sleeve ETFs given | add real tickers |
| wizard appears | no arguments + real TTY | that is the design; pipes/CI get the default run |
| slow first run (8-25 min) | cold universe fetch (~1.3 s/name) | one-time; afterwards ~78 s standard / 5.8 s quick |
| `cache dir(s) not writable` exit 2 | read-only cache root in online mode | `--cache-dir` elsewhere, or `--mode offline` (read-only) |
| `*** STUBBED RUN ***` banner | `MASTER_STUBS=1` in the environment | intended for tests; unset it for real data |
| `REPLAY MISMATCH` exit 65 | tampered cache or partial freeze | re-freeze with a dedicated `--cache-dir` (cookbook #9) |

## 12. Trust and limits

- Point-in-time: earnings engine verified; quality verified (its own
  1000+ embedded tests); meds PIT approximate (true vintages need a FRED
  key; `pit_mode` printed every run).
- Survivorship bias: yfinance/current listings — every run prints it.
- UNVERIFIED here: nothing in this build — the sandbox had network, so the
  online path, cold fetches, freeze/replay and the probe were all run for
  real (evidence/final_real_runs.txt). Finnhub response shapes remain
  UNVERIFIED inside quality.py (no captured payload, engine-disclosed).
- Never run against real data: the full-universe ML dataset build
  (hours; `--dry-run` first), and any ACTIVE ML head (all fail validation).
- The meds snapshot shipped in the zip is a materialised copy of the
  verified FRED cache from this build (2026-11-08); its age is labelled on
  every offline run and it STALEs past 45 days.

## 13. Glossary

conviction — the 0-100 fusion score (not a probability) · provenance —
source + as-of + age + status per layer · STALE — kept data, shown age ·
MISSING_DATA — honestly absent, never invented · funnel — L3 runs only on
the top-K L1+L2 survivors · WT — risk-layer weight · snapshot — frozen FRED
inputs meds can serve offline · materialised — copied from meds' verified
cache into meds' own snapshot layout · freeze/replay — reproducibility pair
· SHADOW — logged, never decides · embargo — train/test time gap ·
effective bets — N/(1+(N-1)·ρ) · NEXT — doctor's one actionable step

## v1.8.0 additions (W0-W7)

- **Module split (W1)**: master.py 7,381 -> ~3,900 lines; the moved code
  lives in me/core.py (CONFIG + datatypes + shared helpers + atomic
  writes + _canonical_json), me/errors.py (MasterError, _phase, the lazy
  codes registry), me/risk.py (size_portfolio + risk context), me/render
  .py (strip_ansi .. json_payload + the md/html exports), me/cli.py
  (the parser, grouped by task), me/backtest.py (_BT_* + run_backtest).
  master.py re-exports every moved name (same objects — `master.X` is
  `me.Y.X`); the two late-bound seams (me/cli._layer_registry, me/backtest
  ._master_run_pipeline) import master INSIDE functions, and script
  mode aliases sys.modules['master'] so `python3 master.py` never
  double-executes the file. Engines never touched.
- **The runlog (W4)**: evidence/backtest_runlog.jsonl — append-only, one
  JSON line per backtest run (ts, dates, window, means, breaker/spy,
  config_hash, dataset).
- **Provenance + refusals (W6)**: every dataset manifest carries
  data_provenance {class REAL-API|SYNTHETIC, apis}; ml_train and
  --backtest REFUSE anything but REAL-API (unit-test valve
  MASTER_ALLOW_SYNTHETIC=1 — the report then says SYNTHETIC in capitals).
- **Owner pack (W6/W2)**: OWNER_RUN.md is the one-page order;
  owner_long_history.sh/.ps1 (resumable free-tier build: 6 dates/pass,
  quota-exhaustion stops cleanly, coverage line per pass);
  owner_retrain.sh/.ps1 (retrain on your sklearn — the shipped heads pin
  1.5.2); owner_bench.sh/.ps1 (7 timing cells); owner_fetch_spy.py
  (Yahoo v8 monthly closes -> owner_results/spy_monthly.json);
  verify_owner_results.py (schema/no-future-dates/provenance + the
  negative control that must FAIL on a corrupted file).
- **Fixture-vs-real discipline**: every sandbox timing is labelled
  (evidence/w18_perf.md, R9); real speed lives only in owner_results/.
