# CHANGELOG — master.py

One entry per delivered phase. Evidence for every claim lives in each
phase's `evidence/` directory; zips are `wip_w*.zip` / `final_master_*.zip`.

## v1.8.3 (STAGE-2 FIXES F1-F12) — final_master_h.zip
- Base: final_master_g.zip (v1.8.2, 605 tests). Engines UNTOUCHED
  (ENGINES.sha256 x3 match at entry AND exit). 605 -> 644 tests, red
  first (the standalone drivers in download/stage1_out/proposed_tests/
  were RED on v1.8.2), none weakened or removed. Owner decisions per
  finding: APPROVE F1, F3, F5, F6, F7, F9, F11, F12; docs-only F4, F8,
  F10; F2's design question (NOT_SELECTED vs MISSING_DATA fill) DEFERRED
  to the owner's v2 backtest — the legacy subsidy maths is UNTOUCHED and
  pinned by test. Version surfaces: master v1.8.3; ml_dataset v1.0.1;
  ml_train v1.1.0 (both unchanged). Evidence: evidence/v183_*.txt,
  evidence/net_bounds.md (F1 re-measured), evidence/README.md (NEW: what
  is real-network-proven vs loopback-only),
  evidence/v183_goldens_justification.md.
- **F1 DNS preflight watchdog (HIGH)**: getaddrinfo now resolves in a
  daemon thread joined by min(per-host budget, remaining total); a stuck
  resolver is abandoned (capped at _DNS_ABANDON_MAX=8 per pass), the
  host is marked dead with the honest 'dns timeout' note and NEVER
  retried past the budget. v1.8.2 checked the budget only BETWEEN hosts
  (a permanently hung resolver stalled the run forever — measured);
  fast-resolver notes/latency/attempts semantics are byte-identical.
- **F11 wrap_fetch capped**: the earnings provider call runs under the
  same _run_capped daemon watchdog as the yfinance wrappers — a hung
  provider (any transport, incl. curl_cffi inside newer yfinance) is
  abandoned at min(NET_CALL_CAP_S, remaining run budget), the host's
  breaker force-opens, and the honest 'timed out' URLError flows into
  the existing retry/ledger path (previously unbounded: measured).
- **F3 v2 WEAK fill**: under ruleset v2 the fixed missing-E fill is
  scored on UN-renormalised weights — a missing name's base is
  WEAK-invariant (Q80: 52.00 WATCH under both verdicts; v1.8.2 lifted
  it to 63.03 LONG purely from the run-wide WEAK verdict). Legacy
  ruleset byte-identical (pinned grid test).
- **F7 degenerate ratios**: Sortino/profit factor report None below 3
  losing windows (the shipped pilot's ONE -0.1% window produced 791.285
  / 1371.55); every ratio carries '(low power, n=N)' while independent
  windows < 8; n_neg rides the metrics JSON; the 6-date lockbox is
  labelled 'uninformative'; NO gate boolean changed and _bt_verdict is
  byte-for-byte untouched (proven by diff).
- **F12 rerun NaN exit 70**: _bt_boot_ci([]) returns (None, None) (was
  (nan, nan) -> allow_nan=False ValueError, exit 70 — observed once on
  a real online rerun); every backtest JSON/runlog dump passes a
  recursive NaN->None scrub (C-6 holds for every field).
- **F6 --bt-ablate macro_cap|macro_mult|macro_all (opt-in)**: what-if
  over the RECORDED rows only (no re-decisions, no network, nothing
  written); prints the damp=1.0 assumption, per-date + aggregate excess
  vs EW and the one-episode disclosure. Shipped-pilot readout:
  macro_cap flips 11 demoted WATCH rows (2025-10-31..2026-01-31);
  aggregate excess vs EW as-recorded +0.0111 vs ablated -0.0298 — the
  defensive demotions were PROTECTIVE in the single episode (still not
  validated evidence).
- **F5 W_CONSUMER_MERGED (new code)**: one warning per run when
  unbucketed consumer names are scored under an XLP/XLY long (either
  basket lifts every consumer name ~+10%); --bucket splits the pools.
  Scores unchanged.
- **F9 ADV-unchecked marker**: sizer weights render '12%*' with the
  footnote when advs was not passed; additive JSON field adv_checked
  per decision (C-6 additive).
- **F2e header disclosure (display-only)**: 'earnings prior: N/M names
  scored with E missing (...)' in the report header; decision hash
  unchanged. F2c (the fill design) stays DEFERRED to the owner's v2
  backtest.
- **F4/F8/F10 docs+register truth pass**: CYCLICAL_SECTORS' inert
  financials/specialty disclosed (REACHABILITY note + a value-level
  register gate with a negative control); master.py:1786's wrong
  consumer comment fixed; version stamps from me/core.__version__
  (requirements*.txt said v1.7.0-dev); _risk_budget/RISK_CAP_DEGRADED
  docs now say APPLIED (they are); CHANGELOG 604->605 corrected;
  ADVANCED.md ML table now carries the SHIPPED validation numbers (q 261
  OOS rows, pooled IC -0.487 vs base-rate +0.0377; e 0; macro 35) with
  the two-estimator note; evidence/README.md (NEW) separates
  real-network proofs from loopback-only ones; root-safe mocked twin
  for the unwritable-cache test (skipIf euid 0; no assertion loosened).
- CONFIG diff vs v1.8.2: NONE (no new keys, no value changes — the fixes
  read existing keys or use module constants). Decision hash
  a023714c... UNCHANGED (loopback proof, evidence/v183_decision_hash).

## v1.8.2 (HARDENING PASS W0-W7) — final_master_g.zip
- Base: final_master_f.zip (v1.8.1, 544 tests). Engines UNTOUCHED (S1;
  ENGINES.sha256 x3 match at entry AND exit). 544 -> 605 tests, red
  first, none weakened or removed. Version surfaces: master v1.8.2;
  ml_dataset v1.0.1; ml_train v1.1.0 (both unchanged). Evidence:
  evidence/plan_v182.md (W0 entry facts, all CONFIRMED),
  evidence/net_bounds.md (W1), evidence/net_paths.md (W2 census),
  evidence/v182_goldens_justification.md, evidence/claims_audit.md,
  evidence/defects.md.
- **W1 worst-case bounds**: RUN_BUDGET_BY_DEPTH (quick 600 / standard
  1200 / deep 4500 s — v1.8.1's flat 1200 s silently clipped legit deep
  and --warm runs at 1200 s; MASTER_RUN_BUDGET_S still wins). Breaker
  second trip rule: failure RATE over a rolling window
  (NET_BREAKER_WINDOW_N=20, NET_BREAKER_RATE=0.5, timeouts count
  NET_BREAKER_TIMEOUT_WEIGHT=2x) so intermittent hosts trip; the
  consecutive rule stays. NET_BROWNOUT_S=120 (global failed-attempt
  wall budget; measured per-host brownout trip 184.4 s x 3 host
  families = 553 s blew the targets). NET_PREFLIGHT_TOTAL_S=10 caps the
  whole preflight pass (DNS-hang outage). Written bounds + measured
  loopback numbers: evidence/net_bounds.md (me/netguard.py
  worst_case_bound is the single source of truth the tests assert).
- **W2 yfinance + transports**: net_paths.md re-censused with the four
  transports; quality's yfinance bypass (YfinancePriceClient._download,
  _detect_sector_yfinance) wrapped from master with the same breaker +
  NET_CALL_CAP_S deadline (abandoned-daemon-thread cap; the engine's
  (None, err) contract preserved) + ledger — RUNTIME class/module
  attribute swaps restored after the run, never a file edit. Tested with
  a FAKE yfinance (hang/raise/succeed); real yfinance UNVERIFIED
  (absent in the agent env) — scripts/owner_net_check.sh/.ps1 now print
  the yfinance version, curl_cffi importability and one timed capped
  call into owner_results/net_check.txt.
- **W3 cadence-aware STALE display**: header/SUMMARY/warnings now
  distinguish "older than its publication cadence" (macro 45d monthly /
  quality 135d quarterly / earnings 5d daily — FRESHNESS_* keys) from
  "refresh failed" (net-guard ledger evidence, refresh_failed in the
  additive JSON provenance key). A monthly macro at 18-45d with no
  failed refresh shows refresh-due (current for its cadence), NOT STALE,
  and emits no W_STALE_CACHE; a real failed refresh or over-cadence age
  is still STALE. The doctor is unchanged. Corrects HANDOFF's overstated
  v1.8.1 F4 claim (it was banner-only).
- **W4 no routine W_UNUSUAL**: 10 new codes (W_CREDIT_OFF,
  W_MACRO_DEGRADED, W_MACRO_UNAVAILABLE, W_SHORTLIST_EMPTY,
  W_SCENARIO_RENORMALIZED, W_EARNINGS_ACCURACY, W_EARNINGS_BACKTEST +
  W_STALE_CACHE reworded); the classifier covers every message a
  stub/offline/outage run emits (verified: zero W_UNUSUAL in all three)
  and the codes/docs drift test passes.
- **W5 --net flag**: --net {auto,online,offline} as its own flag;
  --mode keeps its exact v1.8.1 semantics (compatibility test-pinned);
  conflicting data-mode sources (--net with --mode auto/online/offline
  or --offline) are a clear exit-2 usage error; --net online keeps the
  exit-3 probe contract. docs/CLI.md + --help updated; freeze manifest
  records net_flag (additive).
- **W6 dead tickers**: OWNER_RUN.md now uses quality's real group for
  CFLT/PSTG (tech — the old energy/utilities would silently move them
  between comparison pools); scripts/universe_override.py WARNS on a
  sector/engine-group mismatch (reads quality's GROUPS, fails soft);
  the shipped CSV is header-only (no EXAMPLE1 row).
- S7 proof: decision hashes unchanged (scripts/decision_hash_v181.py,
  evidence/v182_decision_hash.txt); CONFIG diff discloses every new key
  (runtime knobs only; no decision input changed). No secrets; runtime
  state (data/fetch_ledger.jsonl, data/negative_cache.json) never ships.

## v1.8.1 (M.E. FINAL ROUND — NETWORK RESILIENCE + REVIEW FIXES) — final_master_f.zip
- Base: final_master_e.zip (v1.8.0-dev, entry sha256 8f0204e5...caaf8;
  474 tests). Engines UNTOUCHED (R1; ENGINES.sha256 x3 match at entry
  AND exit). Version surfaces: master v1.8.1; ml_dataset v1.0.1;
  ml_train v1.1.0.
- **N1 run budget**: RUN_BUDGET_S (1200 s, disclosed; MASTER_RUN_BUDGET_S
  is the CI valve). Layer budgets clamp to it; after it the run renders
  what it has (salvaged layers say "run budget exhausted"); the SCRIPT
  exit path sweeps stuck non-daemon workers and os._exit()s within
  seconds (subprocess-proven; library calls return normally).
- **N2 preflight**: per-host DNS+TCP probe (2 s budget, 2 retries with
  backoff+jitter) of the six engine hosts (evidence/net_paths.md);
  MASTER_NET_PREFLIGHT_HOSTS / MASTER_NET=online|offline are the
  hermeticity valves (the suite pins them; the agent never touched the
  real network).
- **N3 per-host circuit breaker**: closed -> open after NET_BREAKER_K
  consecutive transient/auth failures -> instant fail during the
  NET_BREAKER_COOLDOWN_S cooldown -> half-open single probe; dead
  preflight hosts open immediately. Wrapping: quality.default_transport
  (engine seam), earnings _fetch/_pfetch/_px_fetch (instance hooks),
  and — for the seamless paths (meds FRED, earnings finnhub requests) —
  DISCLOSED process-level guards (urllib.request.urlopen +
  requests.Session.request), installed per online run, restored after.
- **N4 fetch ledger**: every attempt recorded (host, layer, item,
  ok/fail, error class, latency, retries); FETCH HEALTH block at the end
  of EVERY run (per host + per layer + totals + "recovered n of m" +
  skipped items with (item, why, fix)); additive JSON key fetch_health;
  live progress line "net ok N | fail M | skip K"; the ledger dumps to
  data/fetch_ledger.jsonl per online run.
- **N5 classification**: PERMANENT (404/410, delisted, bad ticker) =
  never retried + negative cache with TTL in a master-owned file
  (data/negative_cache.json); TRANSIENT (timeout, 429, 5xx, reset) =
  backoff retries honouring Retry-After under the NET_RETRY_BUDGET_S
  run budget; CONFIG (401/403, missing key) = no retry + fix message.
  NET_CALL_CAP_S clamps the engines' 45-300 s request timeouts.
- **N6 skip-don't-die**: failed items are skipped and LISTED; layers
  report coverage ("76/90"); auto mode with a dead network falls back
  to offline-from-cache with a clear banner + W_NET_FALLBACK_CACHE;
  --mode online keeps its exit-3 contract; every layer keeps LIVE /
  CACHE(age) / UNAVAILABLE provenance.
- **N7 codes**: W_FETCH_FAILED, W_HOST_BREAKER_OPEN, W_ITEM_SKIPPED,
  W_RETRY_BUDGET, W_NET_FALLBACK_CACHE, W_RUN_BUDGET, W_ENGINE_NO_VERSION,
  W_PEERS_WATCHLIST, W_QUALITY_FLAG (all with why/fix; docs/ADVANCED.md
  table regenerated; exit codes unchanged by default).
- **N8 fault tests, loopback only, red first** (evidence/v181_red.txt ->
  v181_green.txt): accept-never-answer, refused, 429+Retry-After, 500s,
  404-for-some, mixed; wall-time-under-budget, ok/fail/skip counts,
  breaker opens/closes, prompt exit, no traceback without --debug.
- **N9 deferred retry + --retry-failed**: after a layer's main pass,
  transient-failed items get ONE more attempt after
  NET_DEFER_COOLDOWN_S (unless the host breaker is open); recovered
  items are re-scored (quality re-call, earnings public analyze()
  subset); --retry-failed reads the last run's ledger and re-fetches
  ONLY failed transient items (permanent never; healthy never).
- **F1** gate 3 wiring per prereg AMENDMENT 2 (2026-11-19, appended
  BEFORE the code ran): REAL --bt-spy series computes the SPY half
  (net Sharpe @10bps vs SPY Sharpe over the same dates + net MDD <=
  SPY MDD + 1e-9; <12-date overlap or SYNTHETIC files keep the exact
  UNANSWERABLE label). No threshold change.
- **F2** forgiving wizard: unique prefixes, space-or-comma separators,
  bare number = n-th listed group, difflib suggestion (never a guess),
  WIZARD_RETRIES=6 per-question budget; the stale "3 strikes -> loud 64"
  docstring replaced by the true exit-2 contract.
- **F3** orphan codes registered (see N7 list) so W_UNUSUAL is rare.
- **F4** cadence-aware STALE: the [plan] banner separates
  refresh-due (18 d monthly macro) from stale-data (>45 d cadence);
  provenance STALE reasons split "older than cadence" vs "refresh
  failed/overdue".
- **F5** plan banner freshness by the REAL engine TTLs
  ("0/10 fresh by TTL (7d) · 10 due refresh") — presence counts gone.
- **F6** PREFETCH_ALL_MAX 60 -> 150 (the ONE ordered CONFIG value
  change; disclosed; the config gate re-pointed with justification).
- **F7** requirements.txt pins numexpr >= 2.14.1 (tested here) +
  bottleneck >= 1.4.0 (optional, absent here, disclosed as such) and
  --strict / --lenient opt-in exit policies (default contract
  unchanged).
- **F8** data/universe_overrides.csv template +
  scripts/universe_override.py (add/list/remove; the CFLT/PSTG owner
  lines are in OWNER_RUN.md) + master-side negative caching (N5).
- Owner pack: scripts/owner_net_check.sh/.ps1 (OWNER_RUN.md step 0 —
  run FIRST when slow); scripts/capture_sim_fetch_health.py (the
  docs/CLI.md SIMULATED FETCH HEALTH sample); scripts/decision_hash_v181.py.
- Gates: 544 tests (70 new, red-first) OK; env matrix 9 cells green;
  decision hashes UNCHANGED with the network layer on and healthy;
  goldens regenerated with written justification; CONFIG diff vs
  v1.8.0 = 13 additions + 1 ordered value change only; rules register
  100 live / 0 dead; RUNBOOK 120 lines; HANDOFF 3,117 chars; JSON
  additive-only.

## v1.8.0-dev (M.E. FINAL ROUND, W2-W6) — speed, UI, backtest dates, opt-in risk, data/ML tooling
- Base: the W1 tree. Version surfaces (unchanged): ml_dataset v1.0.1,
  ml_train v1.1.0.
- **W2**: npz-member hoist in the backtest (fixture 0.83 s -> 0.31 s,
  R9-labelled); D-18-002 FOUND+FIXED (the CONFIG identity hash str()'ed
  8 frozensets in PYTHONHASHSEED order — different in every process;
  now canonicalised: me.core._canonical_json shared by me/backtest,
  ml_dataset, ml_train); persistent HTTP cache DECLINED with reasons
  (master owns no data fetch — probes only; the read-only engines own
  the fetches and their caches); scripts/owner_bench.sh/.ps1 (7 cells,
  owner-run).
- **W3** (goldens regenerated with a per-change written justification:
  labelled data: cells, no glued/mid-word-cut layer names, packed DATA
  SOURCES cells, separator-glued wraps, the SUMMARY card, grouped
  --help, --md/--html exports, _Progress ETA + Ctrl-C resume hint).
- **W4**: --bt-start/--bt-end month-end sub-windows (descriptive R19,
  printed beside the full-span numbers; outside-dataset windows point
  at the owner ml_dataset build); every backtest run appends to
  evidence/backtest_runlog.jsonl; absent flags = identical output.
- **W5** (opt-in, binding tests): ADV participation guard (advs kwarg;
  loud W_ADV_UNAVAILABLE), the live cost-model footer line (GROSS + the
  2 x 10 bps estimate; goldens: that line only), --bt-breaker
  (RISK_DD_BREAKER_DD/cooldown what-if), --bt-spy + the owner fetch
  script, the stress report on windows present in the data. CONFIG
  additions disclosed in evidence/rules_changes.md (3 keys, opt-in).
- **W6**: datasets declare data_provenance; ml_train AND --backtest
  REFUSE SYNTHETIC/unprovenanced datasets (unit-test valve
  MASTER_ALLOW_SYNTHETIC=1, loudly labelled; the suite's fixtures now
  DECLARE themselves synthetic); ml_train writes
  stability_<head>.json; the shipped pilot's manifest migrated
  additively to its TRUE REAL-API provenance; the owner pack: OWNER_RUN
  .md, owner_long_history.sh/.ps1 (resumable free-tier build +
  coverage), owner_retrain.sh/.ps1, verify_owner_results.py (negative
  control fails on a corrupted file).
- Gates after every workstream: 474 tests OK (was 436; never fewer);
  fuzz byte-identical; freeze/replay exit 0; the frozen decision hash
  2734886b...972595 unchanged; engines untouched.

## v1.8.0-dev (M.E. FINAL ROUND, W1) — master.py split into me/ modules behind the same entry point
- Base: final_master_d.zip (v1.7.0-dev release). Version surfaces
  (unchanged this phase): ml_dataset v1.0.1, ml_train v1.1.0. master
  bumped to 1.8.0-dev; the ONLY golden change is the header version string
  (12/12 goldens diff = exactly that one line; evidence/
  w18_goldens_diff.txt + w18_goldens_justification.md).
- **THE SPLIT** (R15-proven): master.py 7,381 lines -> 3,902 + me/core.py
  (CONFIG registry, datatypes, shared helpers, atomic writes,
  _engines_sha256; leaf, stdlib-only imports) / me/errors.py
  (MasterError, _phase, the lazy codes.py registry) / me/risk.py
  (size_portfolio, risk_ctx_out, _ann_vol, _rho_bar) / me/render.py
  (strip_ansi .. json_payload; ANSI consts) / me/cli.py (parser, mode
  presets, _validate_ns) / me/backtest.py (_BT_*, run_backtest).
  master.py re-exports every moved name (same objects: master.X is
  me.Y.X — pinned by TestModuleSplitV18 identities), keeps the layers,
  registry, fuse, pipeline, freeze/replay, doctor, wizard, main, and
  aliases sys.modules['master'] in script mode so the two sanctioned
  late-bound seams (me/cli._layer_registry, me/backtest.
  _master_run_pipeline) never double-execute the file.
- **Behaviour proof (R15)**: decision hash of the frozen stub ranking
  UNCHANGED (2734886b...972595 before == after); fuzz_decisions.py
  output byte-identical (22,000 cases); freeze/replay exit 0; 436
  tests green + 4 new (440) — no test weakened, none dropped.
- **W0 facts re-verified** (evidence/plan_v18.md): the 63-td vs 21-day
  "backtest discrepancy" is NOT two backtests — 63 td is the
  preregistered q-head label horizon (master.py _BT_WINDOW_TD, prereg
  line 69) and 21 td is the macro horizon + the td/month constant in
  the independent-window count; engines call FOUR hosts (FRED keyed,
  SEC EDGAR keyless, Finnhub keyed, Yahoo/yfinance keyless);
  final_master_d.zip shipped 2 evidence files mismatching its own
  MANIFEST (D-18-001; fixed by the v1.8.0 manifest rebuild + gate on
  a clean unpack).
- **Lint (R10-offline)**: pyflakes clean except master.py's intentional
  re-export block (77 'imported but unused' = the compat contract);
  dead code removed (base_i, today, m locals, 3 stray f-strings);
  rules_register_check.py + lint_hunt.py production scope extended to
  master.py + me/ (v1.8.0); the register checker's --master exec now
  snapshots/restores the shared me.core CONFIG singleton (the negative
  control could otherwise leak its planted key into the real tree —
  found and fixed this phase, negative control re-verified red->green).
- Entry point, flags, exit codes, JSON/CSV schemas: UNCHANGED
  (additions only in later workstreams). Engines untouched
  (ENGINES.sha256 MATCH x3 re-verified at entry; W1 never opens them).

## v1.7.0-dev (FINAL ROUND, phase 9) — C-6 exports contracts + docs/CLI.md, the ONE-PAGE RUNBOOK, the release package (C-4/C-5/C-7 closed in the release notes)
- Base: wip_phase8.zip. Version surfaces: ml_train v1.1.0, ml_dataset
  v1.0.1 (stated plainly in the release HANDOFF — the "1.1.0-dryrun"
  doc drift is closed).
- **C-6**: JSON never contains NaN (null used; allow_nan=False since
  phase 1 — now LOCKED by test_json_never_contains_nan) and the JSON/CSV
  schemas are UNCHANGED vs v1.5.0 EXCEPT additions (frozen baseline key
  sets captured from work/v15; test_json_schema_only_additions /
  test_csv_schema_only_additions). docs/CLI.md written with REAL
  captured output: the ANSI colour sample (each SGR sequence spelled
  <ESC>[..m — screenshot-free) plus the plain version, both from
  `python3 master.py MU NVDA --mode quick --offline` on this build.
- **D RUNBOOK**: RUNBOOK.md replaced with the ONE-PAGE runbook — 116
  lines (<= 120, locked by test_runbook_is_one_page + the release gate),
  day-to-day commands ONLY, every one executed this session with the
  real last lines and real times pasted in; 8 sections (install/doctor,
  runs incl. the wizard transcript and the sector scan, offline+freeze
  +replay, backtest, ML with SHADOW in one line and --activate
  manual-only, tests, exports and where files land, and the
  TROUBLESHOOTING TABLE: the 10 most likely errors, each with the exact
  message the CLI printed this session and the one-line fix — incl.
  white text -> --color always, sklearn mismatch, network down, stale
  cache, unwritable cache, missing earnings, sec.gov 403 ->
  SEC_USER_AGENT, NO-GO exit 4, replay mismatch 65, freeze cap).
  EVERYTHING else relocated verbatim to docs/ADVANCED.md (the code
  registry table included; test_docs_table_matches_registry re-pointed
  there with an R2 note — the sync guarantee is unchanged; nothing was
  deleted).
- **E RELEASE**: scripts/release_gate.py (phase 7) now PASSES on the
  tree: HANDOFF 3112 pure-ASCII chars (<= 3500, no "PLACEHOLDER", the
  ZIP SHA256 release wording — the value is printed with the delivery,
  never embedded), ml_train version agreement everywhere, RUNBOOK <= 120
  lines, MANIFEST complete (213 files, every sha256 verified), no
  nested release zip. HANDOFF rewritten as the release digest with the
  C-4 costs disclosure (live output is GROSS of costs; the backtest
  applies 10 bps/side) and the C-7 e-head wording (UNCALIBRATED-pending-
  data, never "calibrated with 0 rows"). Clean-dir verification: the
  zip unpacked to a fresh directory, python3 test_master.py (435 OK),
  the env matrix (ALL 9 CELLS GREEN), --doctor and sha256sum -c
  ENGINES.sha256 (MATCH x3) — real output pasted in
  evidence/phase9_clean_dir_verify.txt. Deliverable: final_master_d.zip
  (sha256 printed in the final message; computed after the zip is final,
  not embedded in it).
- Suite 432 -> 435 (3 C-6 export-contract locks). Engines untouched
  (ENGINES.sha256 MATCH x3).

## v1.7.0-dev (FINAL ROUND, phase 8) — B-10: the six robustness scripts run, findings fixed or DEFERRED-disclosed, CONFIG diff discipline clean
- Base: wip_phase7.zip. Version surfaces: ml_train.py v1.1.0 (unchanged;
  sidecar pins stay true).
- Six scripts, run twice (first pass -> fixes -> final pass), all real
  outputs in evidence/phase8_*: lint_hunt rc=0 · fuzz_decisions rc=0
  (22000 cases, I1 carried DISCLOSED, I5b 0/4800) · sensitivity_sweep
  rc=0 · diff_checks rc=0 (after P8-H1) · rules_register_check PASS +
  negative control catches the planted dead key (after P8-H2 fixed the
  control's own harness) · test_env_matrix ALL 9 CELLS GREEN (after
  P8-H3/P8-H4 fixed the two hermeticity holes it caught — a date-fragile
  new test and an environment-leaky exit assertion; both strengthened,
  not skipped).
- CONFIG diff (v1.5.0 vs current): EXACTLY the 8 disclosed
  rules_changes.md lines (7 additions + MAX_TERM_WIDTH 110->160), zero
  undisclosed changes.
- Suite 432 green (300+ met with real tests). rules_changes.md extended
  with the phase-6 W_BT_* codes (registry-only additions).
- Engines untouched (ENGINES.sha256 MATCH x3, phase8_engines_sha256.txt).

## v1.7.0-dev (FINAL ROUND, phase 7) — B-8 speed honesty + B-9 verify-or-mark + a real freeze-budget fix
- Base: wip_phase6.zip. Version surfaces: ml_train.py v1.1.0 (unchanged
  this phase; sidecar pins stay true).
- **B-8 (speed, Q8)**: measured on this sandbox with the commands shown
  (evidence/perf_p7.txt + phase7_bench_partial.txt): warm single name
  4.2 s (target <= 5 s MET) · warm 5-name 5.2 s (<= 15 s MET) · warm
  single-sector tech 16.3 s (<= 60 s MET) · backtest re-run 0.5 s (MET)
  · import 0.14 s wall / 17 ms cumulative · selftest 432 tests 16.8 s ·
  stub 0.38 s. The full-universe warm standard run did NOT complete in
  the session's 560-580 s command budget (~114/643 names warmed); the
  v1.5.0 lineage's measured 73 s (perf_after.txt) is cited as the
  reference with the owner command to reproduce. bench.py run twice —
  [a][b][c] pasted, [d] time-boxed honestly. No decision code was
  touched for speed; the freeze/replay gate is the bit-for-bit
  equivalence proof.
- **B-9 item 1 (D3, online-vs-offline identity)**: VERIFIED on a real
  cache — evidence/phase7_online_offline_identity.txt: online quick run
  (14.1 s) then offline replay of the cache it wrote (2.8 s): 5 decisions
  (ticker, action, conviction) identical bit-for-bit.
- **B-9 item 2 (freeze/replay)**: VERIFIED with real runs —
  evidence/phase7_freeze_replay.txt: dedicated-cache freeze (39 files
  23.0 MB, quality 16 files) -> replay exit 0 "5 names identical"
  (2.8 s, fully offline); tampered manifest -> exit 65 with the exact
  mismatch printed.
- **B-9 item 3 (ZERO-INET)**: re-run pasted —
  evidence/phase7_zero_inet.txt: TestOfflineNoSockets x2 +
  TestRiskLayer.test_offline_run_no_sockets_with_shadow_models OK (zero
  AF_INET/AF_INET6 sockets constructed in offline runs).
- **B-9 item 4 (the release gate)**: NEW scripts/release_gate.py — the
  phase-9 packaging gate (HANDOFF <= 3500 ASCII chars, no PLACEHOLDER,
  ZIP SHA256 release wording, ml_train version agreement, RUNBOOK <=
  120 lines, MANIFEST completeness, no nested final zip). Run against
  the phase-7 tree it FAILS exactly on the phase-9 obligations
  (evidence/phase7_release_gate.txt) — the designed mechanism: a
  leftover placeholder can never ship. Suite tests pin the gate logic
  on synthetic trees (TestReleaseGatePhase7, 5 tests).
- **P7-H1 (real-run finding, FIXED)**: run_freeze's quality-copy loop
  double-decremented the budget (b3 grew AND left shrank) — an effective
  cap of FREEZE_MAX_BYTES/2 — then silently skipped every remaining
  namespace while copied_b < cap kept the "cap hit" warning OFF: a
  budget-starved freeze masqueraded as complete and replay failed on
  the missing sec_submissions/prices_v2. Fix: single-counting +
  starvation flag (capped = over-cap OR starved OR snap-starved); the
  note now always carries the cap warning when anything was skipped.
  Red test test_freeze_budget_starved_is_flagged_loudly. Also: files
  already in place (dedicated --cache-dir inside the freeze dir) now
  count as copied instead of silently no-op-ing on SameFileError.
- Environment finding (documented, no engine change): sec.gov 403s
  quality's default contactless User-Agent from this sandbox; setting
  the documented SEC_USER_AGENT env var fixes it (required for online
  SEC fetches; RUNBOOK row lands at phase 9).
- Suite 426 -> 432 (6 new: 1 freeze-starvation + 5 release-gate).
  Engines untouched (ENGINES.sha256 MATCH x3 re-verified).

## v1.7.0-dev (FINAL ROUND, phase 6) — §5 integration backtest: --backtest (B-7f/C-4 conventions executed; Q5 honestly PARTLY)
- Base: wip_phase5.zip (verified content-identical before work started;
  engines untouched: ENGINES.sha256 MATCH x3 re-verified this phase).
- Version surfaces: ml_train.py v1.1.0 (unchanged this phase — the
  backtest consumes recorded decisions; sidecar pins stay true).
- New: `master.py --backtest` (+ `--backtest-rerun`, `--backtest-dataset`,
  `--backtest-out`) — the preregistration-locked integration backtest.
  The DECISIONS are the actual code's: the recorded per-date harvests of
  REAL run_pipeline runs (ml_data/cache/dates/*.json, REAL-DERIVED
  cached) or, with --backtest-rerun, DIRECT run_pipeline calls through
  the same Namespace shape the dataset builder uses — no second decision
  path exists (test_backtest_rerun_calls_run_pipeline /
  test_backtest_uses_recorded_decisions_without_rerun). EARNINGS_TP is
  read from CONFIG at run time and echoed (single source of truth;
  test_backtest_echoes_config_earnings_tp). Execution conventions per
  prereg §6: equal-weight LONG book, entries at the next window open,
  10 bps/side baseline with 5/10/25/50 sensitivity, cash earns zero, no
  leverage; lockbox = last 6 month-ends evaluated once; every metric
  carries the effective independent window count (~4).
- The verdict is honest and preregistered: gates 1/2/3/4 FAIL (12/36
  rebalances; IC mean -0.0482, 95% CI [-0.1547, +0.0662]; EW Sharpe
  2.000 vs LONG 1.421 and SPY: NOT AVAILABLE; 2/3 excess groups), gates
  5/6 PASS — so the report's first line is "no edge demonstrated", Q5 =
  PARTLY (fixture-class: the full-universe build was never run, B-9
  carried; W_BT_FIXTURE_ONLY). SPY prints "SPY: NOT AVAILABLE", never a
  fabricated benchmark; ML variants: "not run — no validated head".
- preregistration.md: dated AMENDMENT 1 pins the dataset sha256 BEFORE
  the first evidence result was read (sequence disclosed inside it).
- New codes W_BT_DATE_SKIPPED / W_BT_FIXTURE_ONLY registered in codes.py
  + the RUNBOOK registry table (scanner/docs tests green).
- Suite 419 -> 426 (7 phase-6 tests, red-first: all 7 failed as captured
  before implementation). evidence/: phase6_backtest_run.txt (the real
  official run, exit 0), phase6_backtest_report.md + .json, prereg
  amendment. MANIFEST rebuilt for the phase-6 tree.
- In-phase bug fixes (all caught before the official evidence run, each
  by a red test or the shakedown run): PRNG call shape, MDD peak-index
  snapshot, avg-holding run-lengths, bootstrap f-string literal,
  float-repr formatting — recorded as P6-H1..P5 in evidence/defects.md.

## v1.7.0-dev (FINAL ROUND, phase 5) — C-1..C-5: colour switch, readable+colourful report, layout tiers, goldens, visible errors + the new exit-code contract
- Base: wip_phase4.zip (verified byte-identical 156/156 files before work
  started).
- Version surfaces: ml_train.py v1.1.0 (unchanged this phase — render/CLI
  work only, no contract change; the shipped sidecars' pins stay true).
  master.py and test_master.py carry the tree version v1.7.0-dev.
- Red-first: 71 phase-5 tests written and captured failing
  (65 RED: 19 FAIL + 46 ERROR; 6 pre-green regression anchors listed in
  evidence/phase5_red.txt) BEFORE any implementation.
- **C-1 colour switch**: `--color {auto,always,never}` + `--no-color` +
  `--plain`; full precedence table (always beats NO_COLOR and pipes; in
  auto: NO_COLOR beats FORCE_COLOR/CLICOLOR_FORCE, which beat TERM=dumb;
  WT_SESSION/TERM_PROGRAM/ConEmuANSI count as capable), tested row by
  row. Depth detection truecolor/256/16 — same bright 16-colour palette
  at every depth. Windows VT enable via ctypes with an honest fallback
  reason; AUTO-off prints ONE dim reason line with the fix ("colour off:
  stdout is not a TTY — use --color always"). `--doctor` gained the
  colour diagnostic (isatty stdout/stderr, TERM, COLORTERM, NO_COLOR,
  FORCE_COLOR, CLICOLOR_FORCE, platform, depth, decision + reason).
- **C-2 readable + colourful**: bright palette (green ok/LONG, yellow
  warn/DEGRADED/STALE, red error/AVOID, cyan headers+layer names,
  magenta ML/SHADOW); glyph+word pairs everywhere (a DEGRADED layer is a
  yellow ▲, never a green check); score bars coloured on the ACTION door
  thresholds; one-line plain-English VERDICT under the header; LEGEND
  line; bare `?`/`n/sel`/`nodata` cells replaced by `n/a` (reasons travel
  in warnings); STALE is a display status (age > STALE_STATUS_DAYS=7,
  new CONFIG key, display-only — the FRESHNESS_* logic gates are
  untouched); the ML line says "SHADOW (n=974 train rows)".
- **C-3 layout**: MAX_TERM_WIDTH 110 -> 160 (disclosed VALUE CHANGE,
  evidence/rules_changes.md) so the tested ladder is 40/70/110/160;
  cells are padded by DISPLAY width (ANSI-aware, wide-char aware, new
  `_disp_width`/`_pad`) with a mandatory >=1 space separator — the
  "NODATAn/sel" glue is structurally gone; column-drop priority as width
  shrinks: REASONS (>=120) -> FLAGS (>=100) -> MACRO (>=80) -> WT/SECTOR
  (>=70), # /TICKER/ACTION/CONV/Q/E never drop; the header's provenance
  cells wrap as UNITS (a status word can never strand alone); the stub
  engines row renders "SYNTHETIC-stub" (the owner's cryptic "vstub" is
  gone); every macro-card line is width-safe.
- **C-4 goldens**: `goldens/golden_{colour,plain,ascii}_{40,70,110,160}.txt`
  — 12 byte-exact fixtures from REAL CLI stub runs (MASTER_STUBS=1,
  MASTER_NET=offline) under a FROZEN CLOCK (2026-11-13), regenerated ONLY
  via `scripts/make_goldens.py --regen`. Disclosed masking (and nothing
  else): ISO dates -> FROZEN-DATE (no golden contains a date — the guard
  test has a failing negative control), wall-clock durations -> Xs.
  Tested: byte-exact re-capture, strip_ansi(colour)==plain, SYNTHETIC
  marker, locale/terminal independence (LC_ALL/TERM/COLUMNS), sklearn
  independence (blocking shim).
- **C-5 errors visible**: every run ends with ERRORS & WARNINGS (layer ·
  stable CODE · what · why · EXACT fix command; clean = green "0 errors,
  0 warnings"); errors mirror to STDERR; no traceback without --debug
  (new flag); per-provider network diagnosis (the owner's cryptic
  "provider_errors:NETWORK_ERROR; sec_edgar=cik_map_failed;
  yahoo_chart=net:offline" tail is now a classified entry with a fix);
  W_RATE_LIMIT honours Retry-After text; DATA SOURCES line (layer ->
  live/cache/SYNTHETIC -> age + the macro path: FRED key -> API, no key
  -> public fredgraph.csv — a missing FRED key is NOT an error);
  `codes.py` = the CENTRAL registry (module + RUNBOOK table) with a
  scanner test + negative control.
- **The exit-code contract changed deliberately** (owner's mandate;
  old->new in --help and --doctor):
  **64 → 2** (usage/config), **2 → 4** (no result/NO-GO),
  **1 → 70** (unexpected internal error), 0 = clean,
  1 = degraded (result produced + warnings, incl. ml head UNAVAILABLE),
  3 = network, 65 = replay, 130 = Ctrl-C. Affected tests were re-pointed
  to the NEW contract with justification comments (R2: no test deleted,
  no assertion weakened — each still asserts the exact expected code);
  run_replay accepts the replayed run's degraded exit 1 (the ranking
  comparison is the gate).
- CONFIG: +STALE_STATUS_DAYS 7 (display-only); MAX_TERM_WIDTH 110 -> 160
  (disclosed value change); zero other changes — the phase-8 CONFIG diff
  must verify exactly these (evidence/phase5_config_diff.txt).
- Suite 348 -> 419 (+71 phase-5 tests; no test deleted). Engines
  untouched (ENGINES.sha256 re-verified). 12 injected-fault tests cover:
  network down, rate limit, stale cache, missing sklearn, corrupt model,
  missing earnings, W_ADV_UNAVAILABLE, W_RHO_FALLBACK, legacy-rule
  warnings, engine hash mismatch, unwritable cache, no-result NO-GO.

## v1.7.0-dev (FINAL ROUND, phase 3) — B-3 + B-4: the ML half of B-6 (M1-M5 ports, ML gates, load hardening), honest retrain
- Base disclosure: every fix below is the matching **v1.4.1 item ported
  BY FUNCTION NAME** onto the v1.5.0 tree, each with its test written
  against this tree FIRST (red: evidence/phase3_red.txt — 23 of the 25
  phase-3 tests failed on the as-shipped tree; the 2 pre-green
  companions are the GBM sidecar-pin pair, green since phase 1's own
  B-1 pinning). Suite 288 -> 309 (+21; no test deleted; the two
  DEFERRED v1.4.1 fixture updates from phase 2 landed with M5 exactly
  as recorded; every contract change justified in
  evidence/fixture_changes.md items 5-9). CONFIG UNCHANGED
  (MIN_OOS_PERIODS / FEATURE_CAP are ml_train constants, not keys —
  diff vs v1.5.0 still shows only phase 2's RISK_FALLBACK_RHO).
- Version surfaces: ml_train.py v1.1.0 (the phase-1-established truth
  for docs + sidecar pins; the M1-M5 contract change is recorded HERE,
  and the phase-9 release notes restate every final version — no
  per-phase bumps, per the phase-2 convention). master.py and
  test_master.py carry the tree version v1.7.0-dev.
- **B-3 / M3 — the in-sample calibration fallback is GONE**: `_fit_z`
  and its two call sites plus the GBM twin (predict_proba on the train
  rows) are deleted. A fold whose inner-OOF cannot calibrate carries
  NO probability (`calibration: insufficient`), is EXCLUDED from the
  pooled metrics, and cannot support any positive verdict; the final
  refit without inner OOF ships identity calibration disclosed as
  `final_calibration: uncalibrated_insufficient_inner_oof`. A grep
  test locks the path out of the source.
- **B-4 / M4 — the verdict gates**: `beats` now requires >= 12 USABLE
  OOS periods AND >= 100 usable rows AND a final model calibrated on
  inner OOF AND IC beating zero AND the raw-engine baseline AND
  positive Brier skill; a failed sample gate yields **"insufficient
  evidence"** naming the failed condition. The model-vs-baseline
  comparison is on **IDENTICAL rows and periods in every branch** (the
  v1.4.1 GBM-winner hole — winner on all-usable rows vs baseline on a
  subset — is closed, disclosed in port_map.md), and the report carries
  `verdict_basis` with **row-set digests** (`model_rowset_sha256` /
  `baseline_rowset_sha256`) so equality is machine-checkable.
- **B-4 / M5 — hash-bound reports + activation**: every validation
  report carries `model_sha256` (sha256 of the npz written) +
  `dataset_sha256`; `--activate` verifies the model hash BEFORE
  parsing the npz (a tampered file refuses cleanly, exit 2), requires
  matching dataset pins on BOTH sides (stricter than v1.4.1 — an npz
  with no dataset pin is a malformed artifact, refused), requires the
  GBM sidecar pin, then rewrites state and RE-BINDS the report to the
  activated artifact. master's `_ml_load_head` verifies the same pins
  for ACTIVE heads (any mismatch downgrades to SHADOW with the
  reason). SHADOW stays the default; activation is manual only, never
  implied by a good score (tested: a head that EARNS `beats` still
  ships SHADOW until the owner runs `--activate`).
- **M1 — target-aware inner embargo**: the inner CV's embargo is
  ceil(label horizon / 21) per head (q 3m / e 5m / macro 1m, from
  ml_dataset's own constants) — the hard-coded 1-month rule that let
  inner-fold label windows overlap the inner test month (and
  contaminate the C choice + the Platt calibration) is gone; the leak
  channel is quantified in test_m1_leaking_embargo_inflates_inner_score.
- **M2 — selection INSIDE each training fold** (FEATURE_CAP=20 kept):
  `select_features_fold` ranks |standardised coef| on THAT fold's own
  train window only; the v1.5.0 pooled-across-folds ranking (which
  read later test periods' training data — the F16 leak) is deleted;
  the final refit selects on all labeled rows (the shipped model,
  disclosed); every fold record carries its feature list and the
  report carries the per-fold records. The **perturbation test**
  proves it: flip the test-fold labels AND jitter the feature values
  of the last group (in no training fold's train window) — every
  fold's selected set is bit-identical (evidence/
  phase3_perturbation.txt).
- **B8's ML-load half**: `_ml_load_head` REFUSES a non-finite
  `base_rate` (must be in (0,1)) or a non-finite `calib_a`/`calib_b`;
  `_ml_predict` returns None for a non-finite probability so the
  head's contribution DROPS with a loud note (macro map guarded);
  `_ml_adjustment` carries the isfinite belt.
- **The honest retrain** (evidence/phase3_retrain.txt, same invocation
  as phase 1's): q 261 usable OOS rows (was 435 via the fallback), IC
  -0.416; e **0 usable rows** (was 381 — all five folds
  calibration-insufficient under the e-head's 5-month inner embargo);
  macro 35 usable rows, IC +0.368. All three verdicts: **"insufficient
  evidence"** (the 12-usable-period gate is unreachable on a 12-group
  pilot by design) — the numbers match v1.4.1's honest outcome and all
  three heads ship SHADOW. No head is validated; nothing was dressed
  up.
- **C-6 (found + fixed this phase)**: the env-matrix harness's
  "sklearn blocked" cell leaked sklearn.* SUBMODULES across sequential
  cells, so `from sklearn.X import Y` imports were never actually
  blocked; fixed by purging cached submodules at cell setup
  (scripts/test_env_matrix.py) — the phase-3 matrix paste
  (evidence/phase3_env_matrix.txt, 9 cells ALL GREEN, the blocked cell
  294 ran + 2 clean skips) is the first fully-hermetic one.

## v1.7.0-dev (FINAL ROUND, phase 2) — B-6 decision-layer half: B1-B6, B8 atomic writes, P-5, the 8 hunt scripts
- Base disclosure: every fix below is the matching **v1.4.1 item ported
  BY FUNCTION NAME** onto the v1.5.0 tree (which had re-inherited the
  v1.4.0 shapes at every one of these sites), each with the v1.4.1 test
  written against this tree FIRST (red: evidence/phase2_red.txt,
  phase2_fuzz_red.txt, phase2_rules_register_red.txt). Suite 263 -> 288
  (+25; no test deleted, no assertion weakened; one authoring correction
  disclosed in evidence/fixture_changes.md).
- Version surfaces: ml_train.py v1.1.0 (unchanged this phase — atomic-write
  hardening only, no contract change; the shipped sidecars' pins stay
  true). master.py and test_master.py carry the tree version v1.7.0-dev.
- **B1 sizer unusable vols**: inf/NaN/<=0 vols are unusable inputs ->
  treated like MISSING vols (peer median / equal-weight fallback) with a
  visible note — never a silent zero weight and never the
  ZeroDivisionError an all-inf book produced on the v1.5.0 tree.
- **B2 silent guard-off disclosure + RISK_FALLBACK_RHO**: when vols
  exist but rho is unavailable (1-2 names, <42 overlapping rows, a
  correlation error, or a non-finite rho_bar) the correlation cap stays
  OFF and the est-DD uses the new documented CONFIG key
  RISK_FALLBACK_RHO (0.5 — the ONLY CONFIG addition; diff vs
  v1.5.0-as-shipped in evidence/phase2_config_diff.txt), disclosed in
  notes + a footer line + JSON (rho_fallback/rho_used). Books with a
  real rho: untouched (asserted). The disclosure also reaches v1.5.0's
  NEW surfaces: the JSON summary and the freeze manifest's new "risk"
  block, so offline/replay outputs carry it.
- **Stable W_* warning codes**: every guard-off / fallback now PRINTS
  and RECORDS a short stable code — W_RHO_FALLBACK, W_UNUSABLE_VOL,
  W_EQW_FALLBACK, W_BUDGET_STANDDOWN, W_DD_VETO, W_FUTURE_REPORT,
  W_BLOCKED_REASSERT — in the sized dict, the footer lines, the JSON
  summary and the freeze manifest (the phase-5 ERRORS & WARNINGS block
  reads these).
- **B3 non-finite budget -> stand-down veto** (same shape as the
  low-budget stand-down); risk_ctx_out emits null, never NaN, so --json
  stays strictly parseable; non-finite rho_bar rejected as unavailable.
- **B4 NOW chip bounded BOTH sides** (0 <= days <= EARNINGS_MAX_AGE): a
  future-dated report is status `open` plus a loud `future_report`
  warning re-raised through the earnings signal (tested with a pinned
  clock).
- **B5 overlay re-assert of blocked rows for ALL rows**: the overlay
  pass re-asserts blocked rows (AVOID + below-WATCH cap) once per
  decision BEFORE consulting any overlay signal — hand-built blocked +
  LONG/WATCH states can no longer survive (the ported fuzz proves it:
  2984+2861 violations -> 0).
- **B6 dead CONFIG keys**: MODES["standard"] resolves from
  EARNINGS_TOP_K / LAYER_TIMEOUT_S at import AND at _apply_mode time
  (the two v1.4.1 dead keys re-deadened by the v1.5.0 final phase are
  LIVE again); EARNINGS_NATIVE_GRADES / CONF_DIGITS documented
  not-read in their rationales; NEW census finding STUB_WARM_BUDGET_S
  (a v1.5.0-only key) disclosed not-read. scripts/rules_register_check.py
  ported WITH its negative control (--master PATH; a planted dead key
  fails the check, exit 1) and an in-suite lock. Register: 77 live / 3
  disclosed / 0 dead.
- **B8 atomic writes everywhere (write temp + fsync + rename)**: --csv,
  the freeze manifest, the materialised meds snapshot, the ml_dataset
  cache/manifest/npz, the ml_train model npz + joblib sidecar +
  validation reports — a crash mid-write leaves the PREVIOUS file
  intact and no .tmp litter (injected-failure tests on every site
  family, including the v1.5.0-specific freeze/snapshot writers).
- **P-5 disclosure**: the layer-status line states the EFFECTIVE
  earnings weight when the weak verdict halves it ("weak x0.5 ACTIVE —
  E weight 35% -> 21%"); the 0.5 value itself stays an owner decision.
- **The 8 hunt scripts** now ship on this tree (v1.5.0 shipped none):
  fuzz_decisions.py (I3 carries the hardened B5 contract; seed 88117
  kept; post-port state = v1.4.1's: 1 disclosed out-of-contract suite,
  1231 I1-ml-scaled-range, count identical to v1.4.1's run),
  rules_register_check.py, decision_path.py, lint_hunt.py,
  sensitivity_sweep.py (RISK_FALLBACK_RHO swept like every numeric
  key), diff_checks.py (D4 rewritten for this base: freeze/replay
  exist; the parity harness is in the suite), build_manifest.py.
- Rule behaviour UNCHANGED: sensitivity sweep profile matches the v8
  hunt (upstream/display keys zero-effect on decisions); CONFIG diff
  shows the one key and no value changes; env matrix 9 cells green,
  288 tests each, 0 skipped. The two v1.4.1 ml_train fixture updates
  are DEFERRED with justification (they attach to M5, phase 3 —
  evidence/fixture_changes.md).

## v1.7.0-dev (FINAL ROUND, phase 1) — B-1/B-2/B-5
- **B-1 version-aware model loading (spec §3.1)**: the model manifest now
  pins the FULL training environment — sklearn, numpy, joblib AND python
  versions (v1.5.0 pinned sklearn only) — in every head npz AND in the
  validation report's pins block. On any mismatch the head is marked
  UNAVAILABLE with a one-line reason, the head is skipped, the run
  CONTINUES degraded and exits 1 (new exit-1 semantic, documented in the
  --help header; the sklearn-1.9.1-loading-a-1.5.2-pickle '_loss' path
  can no longer be reached). Integrity gates run BEFORE any dependency
  import or unpickle: no sidecar file -> UNTRAINED; no sha256 pin or a
  hash mismatch -> refused (tampered/stale) — provably before unpickling
  (poisoned-sidecar test with a live pickle bomb). _ml_predict unpickles
  ONLY the sha256-verified bytes captured at load time — the file on disk
  is never re-read (no TOCTOU). --doctor now reports head states through
  the real loader (UNAVAILABLE + reason, not a fake SHADOW). ml_train
  --activate keeps the ORIGINAL training pins (whichever machine flips
  the state bit must not rewrite them). Heads retrained in THIS
  environment with the full pin set; the retrain is deterministic —
  metrics byte-identical to the v1.5.0 artifacts — and all three heads
  still fail validation honestly and ship SHADOW (no tuning;
  evidence/phase1_retrain.txt).
- **B-2 hermetic test suite**: every test pins and restores what it needs.
  MASTER_NET is pinned per-run by the _run helper (default online for
  fake-engine auto runs; auto/None pin it ABSENT for the probe paths) —
  the suite no longer inherits the operator's MASTER_NET/MASTER_STUBS
  (v1.5.0: 6 failures under ambient MASTER_NET=offline + TestStreams under
  MASTER_STUBS=1). Tests never touch the network (the env valve skips the
  probe; memos are set where the probe path is under test). Date logic is
  deterministic: date-sensitive tests pin the clock on master, ml_dataset,
  ml_train and the test module itself (_pin_today) — the GLOBAL datetime
  module is never patched (that breaks pandas Timestamp.date(); it is how
  the v1.4.1 harness faked date independence — defect C-2). Version
  fixtures read the RUNTIME versions, never literals (the hard-coded
  '1.5.2' in TestSidecarPin was the reviewer's sklearn-1.9.1 failure).
  Tests that are not about the ml layer run with an EMPTY per-call models
  dir (the shipped heads' sklearn loadability must not decide their exit
  code). With sklearn/joblib genuinely absent the trainer refuses
  honestly (exit 2 + reason) and --activate stays sklearn-free; those
  branches are asserted, never skipped. scripts/test_env_matrix.py is
  back in-tree and GREEN in every cell: baseline, MASTER_NET=offline,
  MASTER_STUBS=1, offline+stubs, sklearn+joblib blocked, and four pinned
  dates (Monday / year end / Sunday / leap 2028-02-29 — v1.4.1's
  "2026-02-29" was not a real date; that cell never ran).
- **B-5 version-surface alignment**: ml_train.py v1.1.0 — the docs claim
  is finally real. (The v1.5.0 handoff/changelog said "1.1.0-pinned"
  while the code and every shipped sidecar said 1.0.0 — the bump never
  landed; that drift was the defect.) TestVersionSurfaces locks the four
  surfaces — code __version__, every sidecar's ml_train_version pin, the
  CHANGELOG top-section claim and the HANDOFF claim — so they can never
  drift apart again. master.py moves to v1.7.0-dev (the FINAL ROUND
  line); retrained sidecars pin master_version 1.7.0-dev + the new
  trainer version.

## v1.5.0 (final phase) — offline-first, measurably better online, modes
- **Offline-first (§2)**: every run carries per-layer PROVENANCE — source
  (cache/network/mixed/stub), data_as_of, age_days, status (OK/STALE/
  MISSING_DATA/ERROR/DISABLED/NOT_SELECTED) — in the report header + one
  compact line per layer, in `--json` `layers[].provenance`, and in
  freeze manifests. Freshness rules as CONFIG keys with rationale:
  macro 45 d (monthly), quality 135 d (quarterly + filing lag), earnings
  prices 5 d, plus a per-name flag when no earnings report for 135 d.
  STALE keeps data and score, shows age + reason, never silently OK.
- **Offline = last cached truth, zero sockets**: earnings engine gets an
  infinite cache TTL adapter-side (any cached file serves, age labelled);
  meds reads the materialised `meds_snapshot/` (built by online runs from
  meds' own hash-verified cache, 22 FRED series, shipped) through its own
  snapshot tier; yfinance is made ABSENT for offline runs (meds and
  quality both call it directly — it owns its sockets); a quick+offline
  run is 5.8 s and the socket-blocked gate run opens zero INET sockets
  with decisions identical to online. Offline never writes (test-enforced).
- **Two latent phase-5 defects found and fixed** (evidence/
  final_real_runs.txt): the offline guard patched earnings `_px_fetch`
  while the real engine's price fetcher is `_pfetch` (the px guard was a
  silent no-op); and meds' price inputs bypassed the offline guard
  entirely (no transport seam; caught only because this phase's gate
  blocks sockets for real).
- **Better online (§3)**: `[plan] refresh plan:` one-liner (what is
  cached, what will be fetched — stale/missing only), `[refresh]`
  after-run report (per-layer seconds, data age before→after), per-request
  retries with backoff+jitter (0.5/1.5 s ±20%) on the quality transport
  and earnings fetch seams — transient classes only, 4xx≠429 never
  retried, 429 left to the engine's Retry-After; a failed refresh is
  never worse than offline (engine fallbacks see a normal dead request).
  Per-layer timings now measure each layer's OWN completion (the old code
  charged the whole wall clock to every prefetch layer — the "macro
  77.9s" mystery in the handoff).
- **Modes (§4)**: `--mode auto|online|offline` (default auto: one 2 s
  DNS+TCP probe, no payload, memoised per process, never at import,
  skipped for offline; `--offline` stays the alias; quick/standard/deep
  keep their depth meaning). Explicit online without network exits 3
  with the fix in the message. Stub runs keep their own loud banner.
  `MASTER_NET=online|offline|auto` is the documented CI/hermeticity valve.
- **Freeze/replay (§5)**: `--freeze DIR` writes manifest.json (args,
  versions, ENGINES hashes, provenance, ranking) + capped cache copies
  (exact when the run uses `--cache-dir DIR/warm`; quality's cache files
  are engine-internal hash names so per-ticker copies are impossible —
  documented); `--replay DIR` reruns fully offline and exits 65 on ANY
  ranking/conviction difference. Verified with real engines: identical
  replay, tampered-cache replay fails loudly.
- **ML safety (§7)**: GBM sidecars pinned (sha256 + sklearn + master
  versions in npz AND validation json); master never unpickles an
  unhashed/mismatched file (tampered / wrong-sklearn / missing →
  UNTRAINED with one-line reason). Feature cap 20 per head, selected by
  importance on TRAINING folds only; all three heads retrained on the
  pilot (q 20 feats, e 20, macro 9) — verdicts unchanged and honest:
  all still fail, all stay SHADOW. `ml_dataset.py --dry-run` prints
  dates/tickers/expected rows/time (measured basis)/disk; disk-space
  check before long builds; resumability messages unchanged.
- **--doctor (§8)**: one screen — engines + ENGINES.sha256 match, libs,
  cache age+verdict per layer, network probe, ML head states, free disk,
  `NEXT: <action>`; exit 0/2. `--help` ends with 8 real examples.
- **Perf (§6, evidence/perf_*.txt + perf_delta.md)**: import 16 ms
  (already lazy — verified no numpy/sklearn/pandas at import), stub run
  0.4 s, warm offline standard 77.9→75.2 s (floor = quality's engine-
  internal universe pass, H1), quick+offline 5.8 s (the fast tier), cold
  online network-bound 148→156 s (±5% variance). No master-side
  optimisation cleared the 10 % bar on the warm path — examined and
  documented, not applied (H1 protects the real cost centre).
  Regression guard: stub run must stay under STUB_WARM_BUDGET_S 10 s.
- **Degradation matrix (§2.5) test-enforced**: missing macro cache →
  MISSING_DATA + neutral tilt; per-name quality gaps → existing no-score
  path; missing earnings → ×0.90 haircut; sklearn absent/sidecar
  missing/tampered → that head UNTRAINED + one warning; read-only cache
  in online mode → clear exit-2 error with the fix, never a traceback.
- CONFIG: +14 keys (NET_MODES, NET_MODE_DEFAULT, PROBE_HOST/PORT/
  BUDGET_S, 4 FRESHNESS_*, RETRY_MAX_ATTEMPTS, RETRY_BACKOFF_S,
  FREEZE_MAX_BYTES, STUB_WARM_BUDGET_S), zero existing keys changed
  (H2; config diff vs the ORIGINAL v1.1.0 baseline = additions + the
  already-disclosed MIN_TERM_WIDTH 72→40 only — evidence/
  final_config_diff.txt). New exit codes 3 (network required) and 65
  (replay mismatch). Engines byte-identical to phase 5 (ENGINES.sha256).
- Tests: 186 → 256 (70 new; red-first evidence/final_red.txt), 0 skipped.

## v1.4.0 (phase 5) — ML heads (SHADOW) + risk sizer; L1..L5 all real
- **LAYER_REGISTRY runs five layers by default**: `ml` (MLLayer, order 4,
  stage `overlay`) and `risk` (RiskLayer, order 5, stage `sizer`) are
  registered; the wizard, manifest header, `--only`/`--skip` and `--json`
  pick them up automatically.
- **MLLayer**: calibrated per-head probabilities (q/e/macro) from
  `ml_data/models/head_*.npz`. States UNTRAINED → SHADOW → ACTIVE; SHADOW
  logs p WITH sample size and changes no decision; ACTIVE requires an npz
  ACTIVE stamp AND a validation report with verdict "beats" (else
  downgrade + warning); adjustment bounded ±`ML_ADJ_MAX` 5.0 (inside the
  generic `OVERLAY_MAX_ADJ` 10), never on veto/gate AVOIDs. Pure-numpy
  inference on the same features ml_dataset extracts (`record_from_parts`
  — parity by construction); a model consuming a label-window feature is
  refused at load (leakage gate).
- **RiskLayer**: inverse-vol sizing on LONG names (earnings-engine price
  adapter, offline-guarded), name cap 10% of budget, sector cap 35%,
  correlation-aware gross cap (effective bets vs 8), estimated-max-DD
  portfolio veto (2x ann vol, > 30% ⇒ all cash); weights ≥ 0, Σ ≤
  `ctx.risk_budget`, cash explicit, WATCH/AVOID/blocked = 0, atomic
  assignment; equal-weight fallback (DEGRADED) when no price history.
  All limits are CONFIG entries with rationale strings.
- **NEW ml_train.py v1.0.0**: expanding-window walk-forward trainer
  (group = as-of month; purge+embargo ≥ label horizon from the dataset
  manifest), light C grid via inner group-CV, Platt calibration on
  train-internal OOF, GBM kept only if it beats logistic on pooled OOS
  monthly rank IC; judged on per-month rank IC + decile spread + Brier
  skill vs the base rate and the raw engine score; verdict needs n_oos ≥
  100 (a priori). Ships every head SHADOW; `--activate` refuses (exit 2)
  without a passing report.
- Output: WT column (width ≥ 70) when the sizer ran; ML OVERLAY line;
  risk portfolio footer lines; `--json` `ml_state`/`heads`/`portfolio` +
  per-decision `overlays.ml` (p, n, adj, state). New flag `--ml-models`.
- ml_dataset.py: `record_from_parts()` extracted — ONE feature source for
  dataset build and live inference (harvest delegates to it).
- CONFIG: +13 keys (3 ML_*, 10 RISK_*), zero existing keys changed (H2;
  evidence/phase5_config_diff.txt). Tests 157 → 186 (0 skipped).
- Pilot training result (honest): q/e heads FAIL OOS (IC −0.28/−0.18; the
  raw q_score baseline scores +0.19); macro IC +0.37 on only 35 OOS rows
  < 100 minimum. All three ship SHADOW; activation refused. Full-universe
  build needed before any head can earn ACTIVE.

## v1.3.1 (phase 4) — L3 adapter repaired to the real engine + ML dataset maker
- earnings_engine.py v3 arrived: adapter rewritten to its REAL API
  (signals() is the live plan; verdict ladder without auc; v3 summary
  Series mapping). Defect P4-D1 (Timestamp `.date` bound-method trap)
  rejected every real earnings row as future-dated — found live in the
  pilot, fixed red-first.
- **NEW ml_dataset.py v1.0.0**: (ticker, as_of) feature/label rows via the
  real pipeline (STANDARD pools, funnel opened), per-date disk cache with
  resume, labels from adjusted closes strictly after as-of; npz +
  manifest.json with PIT status and survivorship warning; `--verify`.
- PIT proven by probes: earnings VERIFIED, quality VERIFIED (filing-date
  cut, boundary probe), meds APPROXIMATE (today's vintage; manifest
  pit_verified=false). 12-date tech-pool pilot: 1,080 ticker rows + 84
  macro rows, reloads cleanly.
- Suite 143 → 157; engines + pilot npz first shipped inside the zip.

## v1.3.0 (phase 3) — real layer registry, wizard, one-pass renderer
- LAYER_REGISTRY is real (A15): build_layers/run_pipeline/fuse/renderer/
  JSON iterate registered layers; a registered layer runs or fails loudly.
- Startup wizard (no-args TTY): scope > sectors > cap band > discover N >
  layers > depth > confirm; every choice also a flag (`--sectors`,
  `--cap`, `--discover`); the confirm line prints the exact command.
- Output: manifest header, layer progress, sector table, company table
  (rank/action/conviction/Q/E/flags/reasons), ONE footer ("score, not
  probability"); `--no-color`/`--ascii`/`--width` 40..110 honoured; ANSI
  stripped when piped; results stdout / progress stderr. DISCLOSED CHANGE:
  MIN_TERM_WIDTH 72 -> 40 (a documented, gate-tested narrow-width tier;
  display only, never a fusion input).
- ~1,700 lines of tests + fakes moved from master.py into test_master.py
  (master.py 4,579 → 3,545 lines).
- Fusion defect fixes carried from phase 1-2 verifications: NaN conviction
  defence, veto/gate AVOID conviction cap + table order by action first.

## v1.2.0 (phases 1+2) — correctness repair pass
- Finite-sanitisation defence in depth (NaN/inf/out-of-range can never
  reach fusion), per-layer failure isolation with partial salvage, as-of
  plumbing to all three layers, no-lookahead guard on future-dated L3
  output, offline guards per engine (meds FORCE_SNAPSHOT, quality
  transport swap, earnings fetch seams), P2-3 env/module mutation
  restores, explicit missing-E vocabulary, CSV formula-injection
  neutralisation, redaction of secrets in errors.
- CONFIG gained rationale strings for every tunable; selftest grew to 143
  tests; RUNBOOK rewritten to match verified behaviour.

## v1.1.0 (baseline) — the uploaded starting point
- The 3,474-line layered screener as received (selftest 53 tests).
