# evidence/net_paths.md — EVERY network call in the three engines
# (v1.8.1 N3; v1.8.2 W2 census + the yfinance wrappers)

Built by grepping the SHIPPED trees (v1.8.0 final_master_e.zip entry
sha256 8f0204e56fc6703c53cae3251183277dc6704bf16b4647e56f404092315caaf8;
line numbers re-verified on the v1.8.2 tree final_master_g for the
master/me/ sides — the engines stay read-only (R1): no engine line below
is edited; ENGINES.sha256 matched at entry and exit both releases).

## Transport inventory (the four transports the engines can use)

| transport | used by | file:line | master coverage |
|---|---|---|---|
| urllib (urlopen) | meds FRED keyed + public CSV; quality default_transport + YahooChartPriceClient | meds.py:1592, meds.py:1953, quality.py:2001, quality.py:3502-3511 | engine seam (quality default_transport) + PROCESS-LEVEL urlopen guard |
| requests | earnings finnhub provider | earnings_engine.py:106 | instance hooks (_fetch/_pfetch/_px_fetch) + PROCESS-LEVEL requests guard |
| yfinance | quality YfinancePriceClient._download + _detect_sector_yfinance; earnings yahoo providers | quality.py:3172-3181, quality.py:15664-15665; earnings_engine.py:87/117 | v1.8.2: engine-seam wrappers (below); when yfinance uses requests internally the requests guard ALSO covers it |
| curl_cffi | never imported by the engines directly — yfinance may use it internally when installed | (inside the yfinance package) | covered at the ENGINE-SEAM level (the wrapper bounds the call regardless of the transport inside); a curl_cffi call inside anything NOT behind a wrapped seam would bypass the process guards (disclosed limit, unchanged) |

## Host inventory (the six real hosts)

| host | engine(s) | role |
|---|---|---|
| api.stlouisfed.org | meds | FRED keyed API (series/observations) |
| fred.stlouisfed.org | meds | FRED public CSV (fredgraph.csv) |
| www.sec.gov | quality | SEC ticker map (company_tickers.json) |
| data.sec.gov | quality | SEC submissions + XBRL companyfacts |
| query1/query2.finance.yahoo.com | quality, earnings (yfinance + chart client) | Yahoo chart API |
| finnhub.io | quality, earnings | Finnhub earnings/financials |

Key presence: FRED optional (no key -> public CSV tier), SEC_USER_AGENT
recommended, FINNHUB_API_KEY optional (provider auto-skips without it).
yfinance: ABSENT from requirements-lock.txt (optional; requirements.txt
documents it) — ABSENT in the tested environment, so every yfinance
claim here is [UNVERIFIED: owner runs scripts/owner_net_check.sh].

## meds.py (macro layer) — 2 fetch paths

| call | file:line | timeout | wrappable without editing it? |
|---|---|---|---|
| keyed FRED API urlopen | meds.py:1592 (req built from BASE_URL meds.py:1467) | 45 s (fred_timeout, meds.py:1034/1475) | NO engine seam (class-local urlopen) -> master PROCESS-LEVEL urllib guard |
| public fredgraph.csv urlopen | meds.py:1953 (PUBLIC_CSV_URL meds.py:1468) | min(45,30)=30 s (meds.py:2035) | same: process-level urllib guard |
| meds self-test urlopen | meds.py:9189/9225/9260 | 15 s | meds' own CLI selftest only — master never reaches these |

Notes: meds has NO transport seam (unlike quality). All meds urlopen
paths are covered by the process-level guard — disclosed as N3 requires.

## quality.py (quality layer) — 1 transport seam + the yfinance bypass

| call | file:line | timeout | wrappable without editing it? |
|---|---|---|---|
| default_transport urlopen | quality.py:2001 (`timeout or HTTP_TIMEOUT_SECONDS`; HTTP_TIMEOUT_SECONDS=30, quality.py:571) | 30 s | YES — module seam quality.default_transport (master swaps it offline/retry/guard: master.py:581-590) |
| YfinancePriceClient._download (yf.Ticker().history) | quality.py:3163-3192 (the yfinance call at quality.py:3179; `available()` import guard quality.py:3157) | engine-internal | YES — the class attribute is the engine's own test seam; v1.8.2 wraps it (master.py:600-606: NetGuard.wrap_yfinance_download — breaker + NET_CALL_CAP_S deadline via an abandoned-daemon-thread cap + ledger; ONE attempt; the (None, err) contract preserved). YahooChartPriceClient's OVERRIDE of _download (quality.py:3451+) is untouched — it goes through default_transport. |
| _detect_sector_yfinance (yf.Ticker(t).info) | quality.py:15661-15668 (call at 15664-15665) | none (engine best-effort) | YES — module attribute; v1.8.2 wraps it (master.py:607-612: NetGuard.wrap_yfinance_sector — same policy, None-on-failure contract preserved) |

Hosts through default_transport: www.sec.gov (ticker map
quality.py:2611), data.sec.gov (submissions quality.py:2612,
companyfacts quality.py:2613), finnhub.io (quality.py:2201 _FINNHUB_BASE),
query1/query2.finance.yahoo.com (quality.py:3421 _YAHOO_CHART_HOSTS).
Engine-own guards: AUTH_ERROR breaker for finnhub (quality.py:556/
2500-2537), per-request diagnostics + cache fallback, Retry-After pacing.
subprocess.run(timeout=300) sites (quality.py:10021/10905/10918/10956/
11065/11079/13498/13504/13510) are quality's OWN self-test harness (no
network) — not wrapped (disclosed).

## earnings_engine.py (earnings layer) — 2 provider families

| call | file:line | timeout | wrappable without editing it? |
|---|---|---|---|
| finnhub provider requests.get | earnings_engine.py:106 (`https://finnhub.io/api/v1/stock/earnings`, timeout=10) | 10 s | YES twice over: master wraps the engine instance hooks _fetch/_pfetch/_px_fetch (instance attrs, master.py) AND the process-level requests guard covers the raw call |
| yahoo providers (yfinance) | earnings_engine.py:87 yahoo_provider, earnings_engine.py:117 yahoo_prices | n/a | yfinance ABSENT in the tested env (honest provider error); when installed the yfinance import inside the engine uses the requests stack -> requests guard; the master-side yfinance wrappers cover quality's path (the earnings yahoo provider takes `yf` as a parameter from master's adapter, which passes the REAL module — a disclosed gap: those calls are covered only by the requests-level guard, not the seam wrapper) |

Engine-own retry: history()/prices() try twice with a 0.5 s sleep
(earnings_engine.py:628-637, 668-676) plus a per-instance in-memory
_fail negative cache (no TTL — master's N5 negative cache adds the
cross-run, TTL-bounded persistence; the engine's own is untouched).

## Master-side guards actually installed (v1.8.2, me/netguard.py)

1. quality.default_transport wrapper (existing seam; ledger + breaker +
   classification + retry budget + Retry-After honouring + the v1.8.2
   brownout/rate rules).
2. earnings instance hooks _fetch/_pfetch/_px_fetch (same full policy).
3. PROCESS-LEVEL urllib.request.urlopen wrapper — per run (online /
   auto-live only), restored after: per-host breaker (consecutive K +
   v1.8.2 rate rule), per-call timeout clamp to NET_CALL_CAP_S, ledger,
   transient retry with backoff+jitter honouring Retry-After, run-budget
   deadline check, brownout fail-wall accounting. Covers every meds FRED
   path and any urllib call the engines make. Disclosed: it patches the
   stdlib in the master process, never an engine file.
4. PROCESS-LEVEL requests.Session.request wrapper (same policy; covers
   earnings finnhub and yfinance-when-it-uses-requests). Same disclosure.
5. NEW v1.8.2 (W2): YfinancePriceClient._download + _detect_sector_yfinance
   engine-seam wrappers (breaker + cap + ledger, one attempt, contract
   preserved) — installed for online runs with a guard, class/module
   attribute swaps restored after the run (master.py:591-612). Disclosed
   as RUNTIME wrappers, never file edits.

Not wrapped (disclosed limits): quality's own self-test subprocess
harness (no network); a curl_cffi call inside the EARNINGS yahoo provider
(yfinance passed as a parameter there — covered only by the requests
guard if yfinance uses requests; the seam wrappers cover quality's path
only) — labelled a known limit; meds/yfinance remain absent in the tested
environment, so the real-yfinance behaviour is
[UNVERIFIED: scripts/owner_net_check.sh prints the yfinance version,
curl_cffi importability and one timed capped call into
owner_results/net_check.txt].
