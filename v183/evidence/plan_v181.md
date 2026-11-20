# evidence/plan_v181.md — v1.8.1 NETWORK RESILIENCE + REVIEW FIXES plan

## W0 baseline (verified this session, real commands)

Input zip: download/final_master_e.zip
sha256 8f0204e56fc6703c53cae3251183277dc6704bf16b4647e56f404092315caaf8
269 entries. Extracted to work/v181.

- ENGINES.sha256 entry-side match (cat vs sha256sum meds.py quality.py
  earnings_engine.py): meds 5e64b60d…c437b, quality f123fb4e…b31215,
  earnings 8e31e532…45b0e0 — all three MATCH.
- `python3 test_master.py` (work/v181, no root): "Ran 474 tests in
  37.904s — OK". Baseline test count 474 (gate: >= 474 + new).

## PROBLEM facts re-verified with file:line (all CONFIRMED)

1. LAYER_TIMEOUT_S=900 per layer — me/core.py:221 ("STANDARD-mode
   per-layer wall-clock budget"); standard preset passes it as the
   per-layer timeout (me/core.py:229, me/cli.py:246). CONFIRMED.
2. _soft_deadline_call stops WAITING but never kills the worker —
   master.py:2103-2118 (docstring: "the worker thread itself is NEVER
   killed"; ex.shutdown(wait=False) leaves it running). CONFIRMED.
3. Engine request timeouts 45-300 s — meds.py:1034 fred_timeout=45.0
   (urlopen meds.py:1592), public CSV 30 s (meds.py:2035/1953);
   quality.py:571 HTTP_TIMEOUT_SECONDS=30 (urlopen quality.py:2001);
   earnings_engine.py:106 requests.get(..., timeout=10);
   quality.py:10021+ subprocess timeout=300 = quality's OWN selftest
   harness (no network in master runs). CONFIRMED.
4. No per-host circuit breaker — grep shows only the backtest
   --bt-breaker what-if (me/backtest.py:636-834, me/core.py:315-319).
   CONFIRMED.
5. Master retry wrappers cover only some fetch paths —
   quality.default_transport (master.py:559-566), earnings instance
   hooks _fetch/_pfetch/_px_fetch (master.py:885-893), risk prices
   (master.py:1472-1474); meds has NO retry wrapper (macro layer only
   sets offline guards, master.py:339-372); yfinance paths bypass
   default_transport. CONFIRMED.
6. Non-daemon worker threads delay interpreter exit —
   ThreadPoolExecutor threads are non-daemon (3.12) and
   threading._shutdown JOINS them at exit; ex.shutdown(wait=False)
   never stops one. A stuck worker (e.g. 45-300 s engine timeout, or a
   socket accept-hang with the engine's own timeout still running)
   keeps the process alive after master stopped waiting. CONFIRMED by
   construction (to be PROVEN by the N1/N8 tests).

Why the owner's ~1000 s run: standard mode -> per-layer budget 900 s +
soft deadline + per-request 45 s timeouts (and engine-internal retries)
-> the run waits out the full layer budget with every host black-holing;
meds has no master-side retry/breaker so every FRED call burns its own
45 s timeout; the process then lingered on stuck non-daemon threads.

## REVIEW FIX facts re-verified (re-verify each first — done)

- F1 me/backtest.py:467 `"pass": bool(beats_ew) and False,` — CONFIRMED
  (the literal is in gate "3_beats_ew_and_spy"). Amendment 2 (dated,
  signed) appended to evidence/preregistration.md BEFORE the new gate
  code runs.
- F2 wizard — CONFIRMED: _wiz_sectors splits ONLY on commas
  (master.py:3628), no unique-prefix match, no bare-number = n-th
  group, no difflib close match, no per-question retry budget (3
  strikes hard-fail, master.py:3578-3592); stale docstring: _Ask says
  "3 strikes -> loud 64" but raises MasterError(..., 2)
  (master.py:3591-3592); me/cli.py:2 still says "bad usage exits 64,
  never 2" (that one is ABOUT argparse usage and stays true; the
  WIZARD docstring is the stale one — fixed with the wording made
  true: wizard failures exit 2, argparse usage exits 64).
- F3 orphan warnings — CONFIRMED: "earnings engine exposes no
  __version__..." (master.py:987-988), "quality ranks are relative to
  the {N}-name watchlist only..." (master.py:2729-2731), quality flags
  such as ALTMAN_DISTRESS ride res.warnings from the signal adapter
  (master.py:422-446) — none carries a code the classifier knows
  (me/render.py:862-889) so all classify W_UNUSUAL.
- F4 cadence-blind STALE — CONFIRMED in the [plan] banner:
  master.py:2450-2451 marks macro "stale" when meds_cache is older
  than 24 HOURS regardless of the monthly cadence (a monthly FRED
  series 18 days old is "stale" there while layer_provenance uses
  FRESHNESS_MACRO_MAX_AGE_D=45, me/core.py:383); the provenance STALE
  reason also mixes "older than cadence" and "refresh failed" in one
  label.
- F5 plan banner counts PRESENCE not freshness — CONFIRMED:
  _refresh_plan_line (master.py:2457-2464) counts sec/ files
  (min(qcached,pool)) and earnings csv presence; "90/90 cached" can
  precede a cold pass.
- F6 PREFETCH_ALL_MAX=60 — CONFIRMED me/core.py:253.
- F7 requirements.txt has no numexpr/bottleneck minimums — CONFIRMED
  (only numpy/pandas/scikit-learn/joblib/scipy/requests). No
  --strict/--lenient exit policy exists.
- F8 dead tickers — CONFIRMED: overrides CSV is
  ticker,sector,status,note (quality.py:1695-1730,
  load_overrides/get_universe), env QE_UNIVERSE_OVERRIDES or
  data/universe_overrides.csv; no template ships, no owner command
  documents adding CFLT/PSTG; master has no negative cache (N5).

## DO NOT list honoured

No W_Q/W_E/missing-E haircut/door-threshold retunes on the 12-date
fixture; engine TTLs untouched; no per-name engine parallelism added;
no new ML models. The only CONFIG value CHANGE is PREFETCH_ALL_MAX
60 -> 150 (F6, explicitly ordered); everything else is additions.

## Build order (R17 small steps; checkpoints after each workflow)

- W0 this file + net_paths.md + prereg AMENDMENT 2 -> checkpoint zip.
- W1 new tests RED first (N8 loopback fault suite + N1/N4/N5/N9 asserts
  + F-tests where independent) — evidence/v181_red.txt.
- W2 me/netguard.py (ledger, per-host breaker, error classification,
  negative cache, retry budget, preflight, urlopen/requests process
  guards) + CONFIG additions + master wiring (N1 run budget + prompt
  exit, N2 preflight, N3 breaker, N4 FETCH HEALTH render/JSON/live
  line, N5/N6 skip-don't-die + coverage + auto-fallback banner + LIVE/
  CACHE(age)/UNAVAILABLE provenance, N7 codes, N9 deferred retry +
  --retry-failed) -> suite GREEN.
- W3 F1-F8 -> red evidence captured in W1/F section, then fixes.
- W4 codes.py registry, docs/CLI.md (+SIMULATED FETCH HEALTH capture),
  docs/ADVANCED.md, RUNBOOK (<=120 lines), HANDOFF (<=3,500 chars),
  CHANGELOG, OWNER_RUN.md, scripts/owner_net_check.sh/.ps1,
  data/universe_overrides.csv template + owner command,
  requirements.txt pins + --strict/--lenient.
- W5 gates: full suite, env matrix, decision-hash invariance (netguard
  on + healthy loopback == baseline hashes), ENGINES.sha256 re-check,
  MANIFEST, final_master_f.zip + sha256, PHASE_STATE append.

## Owner-run boundary (R10-R13)

The agent runs: unit tests, loopback-only fault simulations
(127.0.0.1), stub runs, offline/cache runs, linters, golden regen.
The agent NEVER runs: real network, real API fetches, real dataset
builds. scripts/owner_net_check.sh/.ps1 + OWNER_RUN.md carry the real
per-host reachability check; their results are AWAITING OWNER DATA
until returned.
