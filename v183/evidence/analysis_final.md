# analysis_final.md — offline-first + better-online + modes (FINAL PHASE)
Pre-work, written BEFORE any coding. Base = phase-5 output (master v1.4.0,
186 tests green, rerun here: "Ran 186 tests ... OK"). No engine file edited;
ENGINES.sha256 = the phase-5 zip's own MANIFEST values (verified above):
meds 5e64b60d..., quality f123fb4e..., earnings 8e31e532... .

## How each engine caches / fetches (grep + probe, not assumption)
- quality.py: import-time env QE_DATA_DIR (default data/), QE_CACHE_DIR
  (default DATA_DIR/cache), QE_SNAPSHOT_DIR, QE_SCAN_STATE. Module globals
  DATA_DIR/CACHE_DIR/SNAPSHOT_DIR/SCAN_STATE_PATH — master already redirects
  them per-run via _AttrRestore (QualityLayer._redirect_quality_paths).
  source="auto|fixtures|sec|yfinance". ONE transport seam: quality.
  default_transport(url, headers, timeout) -> (status, payload, retry_after,
  detail) with D6 statuses (AUTH_ERROR/RATE_LIMITED/NO_DATA/PROVIDER_ERROR/
  SCHEMA_ERROR/NETWORK_ERROR); RATE_LIMITED honors Retry-After INSIDE the
  engine. Documented rate caps: FINNHUB_CALLS_PER_MIN=50, YAHOO_CALLS_PER_MIN
  =40 (env-overridable). Disk caches are namespaced per source; price cache
  refetches when the OLDEST per-bar stamp exceeds PRICE_CACHE_TTL_DAYS=5
  (D23). On a blocked transport the engine's own diagnostics keep serving
  disk caches and report honest per-item failures (the phase-2 finding; the
  offline guard relies on exactly this).
- meds.py: DATA_DIR from MACRO_ENGINE_DATA_DIR; verified cache meds_cache/
  cache.json.gz next to meds.py (SHA-256-checked, TTL 24 h, written ONLY
  with MEDS_CACHE=1); snapshot tier = snapshot/fred/*.csv next to meds.py,
  forced by FORCE_SNAPSHOT (env MEDS_FORCE_SNAPSHOT or module attr);
  MACRO_ENGINE_SNAPSHOT env is AUTHORITATIVE for the snapshot location when
  set. FRED key from FREDAPI/FRED_API_KEY/... env. now() exposes
  effective_as_of (floored month-end) + data_tier api|public|cache|snapshot.
  meds_cache dir is FIXED next to meds.py (no env) — cache-only = snapshot
  mode; no transport seam to wrap for retries (H1: no edit).
- earnings_engine.py: EarningsEngine(cache=True, cache_ttl_hours=12.0,
  cache_dir=None -> ~/.earnings_engine_cache). history cache file
  {provider}_{T}_{quarters}.csv; price cache px_yahoo_{T}_{YYYYMM}.csv;
  both disk+memory cached; TTL-expired file -> refetch (stale file NOT
  served). _fetch/_px_fetch are instance attrs (swappable callables);
  analyze(tickers, as_of, accuracy, trade) + signals() (one small price
  download, live runs only). Constructor params are the sanctioned adapter
  surface: offline passes the raiser attrs; an INFINITE cache_ttl_hours is
  the clean "serve any cached file, whatever its age" switch for offline.
  No documented rate limit (Yahoo unofficial) — master caps at --workers
  and says so (3.6).

## Where master decides cache vs network today
- Offline guard (P2-2/P2-3, all adapter-level): --offline sets
  meds.FORCE_SNAPSHOT, swaps quality.default_transport -> _offline_transport
  (engine's own NETWORK_ERROR path), earnings _fetch/_px_fetch ->
  _offline_raiser; every mutation registered in `restores`, undone in
  run_pipeline's finally. Socket-blocked test exists (TestOfflineNoSockets).
- Prefetch: ALL layers prefetch concurrently (ThreadPoolExecutor(3)) with
  per-layer budgets; _soft_deadline_call is the wall-clock guard;
  funnel layers run after L1+L2; overlay/sizer after fusion. Fusion reads
  _snapshot_results (P2-1 late-write freeze). So 3.2's "overlap layer
  prefetch" is ALREADY the design; the ~78 s user run = cold fetches inside
  concurrently-running layers, not sequential layers (both macro and
  quality ended at 77.9 s — the same wall clock).
- --warm: macro+quality only, WARM_TIMEOUT_S budget. --check: importable /
  configured / cache-ready / provider-ready probe sections. --earnings-
  prefetch all: ThreadPool honouring --workers (P2-4 fixed, confirmed).
- Cache status per layer: res.cache cold/warm via _dir_stamp before/after
  (quality + earnings); macro maps data_tier. [plan] banner prints cache
  ages + honest ETA. No provenance/as-of per layer exists yet — that is the
  gap section 2.1 fills.

## Already there that I will reuse (no re-invention)
Offline guard trio + restores machinery; _snapshot_results; concurrent
prefetch + budgets; _cache_age_h/_dir_stamp; quality path redirection
(QE_* envs per run); earnings cache_dir flag; MACRO_SNAPSHOT_MAX_AGE_H
DEGRADED rule (48 h snapshot file age — complements, not replaces, the new
45-day DATA-age rule: different objects); engine-exposed dates
(meds.effective_as_of, earnings row.last_date); _redact for error classes;
status vocabulary incl. MISSING_DATA/NOT_SELECTED/DISABLED; exit-code table
0/1/2/64/130; --check sections; wizard; MASTER_STUBS banner discipline.

## Prompt vs code — contradictions (code wins, handled as follows)
1. "--mode auto|online|offline, default auto" vs --mode quick|standard|deep
   (run presets, default standard). Resolution: --mode accepts ALL six;
   quick/standard/deep keep their preset meaning (net mode defaults auto);
   auto/online/offline set the network mode with depth=standard. Default
   flag value becomes auto (identical depth to today + probing). --offline
   stays the alias. CONFIG["MODES"] (H2-frozen) untouched; new NET_MODES /
   NET_MODE_DEFAULT keys added.
2. "earnings prefetch was hard-coded to 4 earlier; confirm it is fixed" —
   confirmed fixed already (workers from ctx.flags, P2-4). No change.
3. "overlap layer prefetch" — already concurrent since phase 3; the slow
   part is inside-layer fetching. Optimisation effort goes where the
   profile points (6.x), not into re-parallelising.
4. Prompt's status list includes STALE; today's signal vocabulary has no
   STALE. STALE becomes the LAYER-provenance freshness status (and a
   per-signal warning + reason), never a score change — "keeps the data
   and the score but shows the age and a reason".
5. ml_train.py looked corrupted in one bash view (HEADS[head] rendering):
   file is intact (ast.parse OK; `[h`/`[m` display artifact of the shell);
   no repair needed.
6. Exit code for "--mode online without network": new code 3 "network
   required" (documented in the exit table); replay mismatch -> 65.
   No existing code reused for a different meaning.

## Freshness defaults checked against real cadences (2.2)
- macro: meds floors to month-end; a fresh pull can legitimately sit ~31 d
  behind on the 1st of a month. 45 d = one monthly cycle + slack. KEEP 45.
- quality: filings are quarterly; SEC filing lag ~30-45 d after quarter
  end; 135 d = a full quarter + filing lag. Applied to the newest cache
  mtime (fetch stamp — quality exposes no per-run newest-filing date; the
  engine's own STALE_DATA/stale_shares flags gate individual names and are
  already carried as warnings). KEEP 135, basis = cache fetch stamp,
  disclosed in the report line.
- earnings: prices are daily; the engine's own price refetch window is
  PRICE_CACHE_TTL_DAYS=5 in quality and cache_ttl_hours=12 in earnings
  engine. 5 calendar days for price history KEEP; "earnings date passed
  since the cache was written" = plan/row event_date newer than the
  history cache file mtime (live runs), flagged per name.
