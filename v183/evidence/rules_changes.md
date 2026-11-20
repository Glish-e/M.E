# evidence/rules_changes.md — the phase-4 CONFIG/behaviour change register

Purpose: Phase 8's CONFIG diff must be able to verify "only disclosed
additions" mechanically. This file lists EVERY CONFIG key phase 4 added
(with its default and where production reads it) AND every behaviour
change that is NOT a CONFIG value change. Anything not in this file that
shows up in a future CONFIG diff is an UNDISCLOSED change and a defect.

Baseline for the diff: v1.5.0 master.py (work/v15). The phase-4 diff
(evidence/phase4_config_diff.txt) shows 6 VALUE lines, ALL of them
`<absent> -> addition` (zero existing values changed). One of the six
(RISK_FALLBACK_RHO) is the PHASE 2 addition — listed there for the
cumulative diff, not added here.

## CONFIG additions in phase 4 (5 keys)

| key | default | read in production by | why this default |
|---|---|---|---|
| RULESET | `"legacy"` | `_ruleset()` / `_missing_fill()` / `_door_value()` (fusion, funnel, overlays, header, explain); `_apply_mode` (CLI `--ruleset` default); `_build_context` + `_CfgKeyRestore` (run flags, P2-3 restore) | P-1/P-6: legacy stays the default until backtest evidence + owner approval (spec §10 table); `--ruleset v2` is the opt-in |
| E_MISSING_V2 | `0.0` | `_missing_fill()` (the v2 fixed conservative missing-E fill) | the ONLY value for which base(missing E) <= base(any observed E) holds for every observed E >= 0 (the spec §3.2 invariant); chosen a priori, never tuned |
| EARNINGS_STOP_K | `2.0` | `_stop_price()` (live-plan stop formula); `_map_plan_row` (warning gate); `EarningsLayer._plan_map` (skip vol fetch when 0) | P-3: the pre-registered MID-grid value of {1.5, 2.0, 3.0}; the spec §5.8 grid backtest (later phase) chooses by pre-registered OOS rules — no result was used to pick 2.0 |
| RISK_SIZING_MODE | `"legacy"` | `RiskLayer.run` + `StubRiskLayer.run` (passed as `size_portfolio(mode=...)`); `_apply_mode` (CLI `--sizing` default); `_build_context` flags; `risk_ctx_out` (JSON `sizing_mode`) | P-2: legacy is the default (spec §10); `--sizing vol_target` opts in |
| RISK_VOL_TARGET | `0.15` | `size_portfolio` vol_target solve (the ABSOLUTE portfolio-vol target) | coherent with the legacy risk envelope by construction: at target, est max DD = RISK_DD_FACTOR x 0.15 = 0.30 = exactly RISK_MAX_EST_DD at ANY budget; pre-registered coherence, not a result-tuned value |

All five are LIVE in the rules register (82 live / 3 disclosed / 0 dead,
scripts/rules_register_check.py PASS).

## Behaviour changes that are NOT CONFIG values (disclosed)

1. **Live plan rows now carry a vol-based stop** (P-3): every earnings
   plan row with an entry price gets `stop_px = entry x (1 - k x ann vol
   x sqrt(hold/365))` (k = EARNINGS_STOP_K, default 2.0). Rows with no
   usable vol ship `stop_px=None` PLUS the loud
   `[W_NO_VOL_NO_STOP]` warning with a fix command — never a silent
   None. This ADDS a displayed field to the live plan (the NOW-chip /
   --explain plan line gains "· stop X.XX"); it changes NO decision
   (action/conviction/weight logic never reads stop_px).
2. **EARNINGS_TP is now the single source for the BACKTEST too** (B-7c):
   `EarningsLayer.run` passes `hold_days/take_profit/min_score` from
   CONFIG to `eng.analyze(...)`, so the trade backtest and the live
   signals() plan read the same value. The backtest's effective TP moved
   from the engine's own default 0.20 to CONFIG's 0.15 — that is the
   inconsistency being closed (the live plan was already 0.15; the live
   behaviour is unchanged). The value 0.15 itself is unchanged and stays
   an owner decision.
3. **DD veto boundary tolerance +1e-9** (P-2): the est-DD veto comparison
   gained a 1-ulp tolerance so a vol_target book sitting exactly AT its
   target (est_dd == RISK_MAX_EST_DD by construction) is not vetoed by
   float noise. Organic legacy books are ~1e-3 from the line; the legacy
   verdict is unchanged for all of them (asserted by the unchanged legacy
   test expectations, incl. test_vol_target_keeps_the_dd_veto which still
   fires at est_dd ~1.69 >> 0.30).
4. **Label interpolations (hunt fix)**: the per-name reason strings
   "(weak x0.5)" and "(damped x0.5)" and the --explain weak arithmetic
   line now interpolate CONFIG values instead of hard-coding 0.5 — the
   displayed numbers were equal before and stay equal at the shipped
   defaults; the labels can no longer lie if a key changes.
5. **Funnel prior unified**: `funnel_shortlist` now computes its
   pre-earnings score via `_base_conviction(q, None, False) * mult` —
   under legacy this is EXACTLY the old `q * E_MISSING_HAIRCUT * mult`
   (byte-identical arithmetic; asserted by the unchanged funnel tests);
   under ruleset v2 it is the conservative-fill blend, so the funnel and
   the fusion can never disagree about "E assumed missing".
6. **Header gains the RULESET row** on every run: legacy prints
   `RULESET legacy - missing-E advantage ACTIVE (UNVALIDATED)`, v2 prints
   the fill value. A new always-on disclosure line, not a behaviour
   change.

## New stable warning codes (the phase-5 ERRORS & WARNINGS vocabulary)

- `W_NO_VOL_NO_STOP` — a live plan row had an entry price but no usable
  volatility estimate, so no stop could be computed (code + fix command
  printed on the signal warning).
- `W_ADV_UNAVAILABLE` — the ADV liquidity guard is NOT implemented
  because no readable feed carries volume (doctor line + probe output;
  nothing faked).

## Opt-in semantics (nothing flips without an explicit flag)

- `--ruleset v2` (or owner CONFIG flip of RULESET): missing-E conservative
  fill + unrounded doors. Default legacy, labelled.
- `--sizing vol_target` (or owner CONFIG flip of RISK_SIZING_MODE):
  vol-targeted gross with looser-than-norm labels. Default legacy.
- `EARNINGS_STOP_K = 0` would turn the stop off (the only default-changed
  surface is the ADDED stop line; see item 1 above).

## Not changed (explicitly)

- EARNINGS_WEAK_SCALE stays 0.5 with its disclosure (P-5: value kept;
  ablation reported in evidence/phase4_sensitivity_sweep.txt — weak-path
  flips 1/8 cases at 0.25, 0/8 at 0.75 and 1.0; no winner picked).
- E_MISSING_HAIRCUT stays 0.90 and stays the default ruleset's rule.
- eff/8 correlation cap, name/sector caps, RISK_MAX_EST_DD, RISK_DD_FACTOR,
  MIN_QUALITY, doors 60/45: untouched values.
- meds.py / quality.py / earnings_engine.py: untouched (ENGINES.sha256
  MATCH on all three; evidence/phase4_engines_sha256.txt).

---

# PHASE 5 append — the C-1..C-5 CONFIG/behaviour change register

Baseline for this diff: the phase-4 tree (master.py inside
wip_phase4.zip). The phase-5 diff (evidence/phase5_config_diff.txt)
shows exactly TWO lines — the one VALUE CHANGE and the one ADDITION
below; nothing else moved.

## CONFIG changes in phase 5 (1 addition + 1 value change)

| key | default | read in production by | why this default |
|---|---|---|---|
| STALE_STATUS_DAYS (ADDED) | `7` | `_prov_status()` (report layer/provenance lines + DATA SOURCES) and the doctor cache line — DISPLAY ONLY | the spec's example threshold ("e.g. macro > 7d"): staleness is a STATUS; a served source older than this shows yellow STALE + age, never a green OK. Display-only by design: the FRESHNESS_* gates that gate LOGIC keep their pre-registered values (45/135/5/135) untouched — this key never feeds a decision. |
| MAX_TERM_WIDTH (VALUE CHANGE 110 -> 160) | `160` | `_validate_ns` (--width range), `make_style` (width clamp) | the C-3 mandate tests the ladder 40/70/110/160; 110 refused width 160. Display only; never a fusion input. Disclosed as a VALUE CHANGE — the phase-8 cumulative CONFIG diff must show exactly this one value change from phase 5. |

## Behaviour changes that are NOT CONFIG values (all display/CLI; fusion untouched)

1. **Colour switch (C-1)**: `--color {auto,always,never}` + `--plain`
   (= --no-color, no decoration beyond the box) + `--debug`; precedence
   table incl. FORCE_COLOR/CLICOLOR_FORCE, NO_COLOR, TERM=dumb,
   WT_SESSION/TERM_PROGRAM/ConEmuANSI; depth detection (truecolor/256/16,
   same semantic palette); Windows VT via ctypes with honest fallback;
   AUTO-off prints ONE dim reason line with the fix.
2. **Exit-code contract (C-5, deliberate)**: 64 -> 2 (usage/config),
   2 -> 4 (no result/NO-GO), 1 -> 70 (unexpected), 0 clean, 1 degraded
   (result + warnings incl. ml head UNAVAILABLE), 3/65/130 unchanged;
   doctor/--check health failure = 1; run_replay ACCEPTS a replayed
   run's exit 1 (ranking comparison stays the gate); selftest failure
   stays 1. Mapped in CHANGELOG/--help/--doctor; affected tests
   re-pointed with justification comments.
3. **Render (C-2/C-3)**: bright palette + glyph+word pairs; DEGRADED
   lead is ▲ (was a green ✓); coloured bars on ACTION door thresholds;
   VERDICT + LEGEND lines; n/a replaces '?', 'n/sel', 'nodata' cells;
   STALE display status; ML line "SHADOW (n=974 train rows)" in magenta;
   column-drop priority REASONS(>=120)/FLAGS(>=100)/MACRO(>=80)/
   WT+SECTOR(>=70) — the 70-95 tier changed from "FLAGS at >=70" to
   "FLAGS at >=100" (display only); display-width padding + mandatory
   cell separators (no glued values); header provenance cells wrap as
   units; stub engine versions render "SYNTHETIC-stub" (the render-level
   source of the owner's 'vstub' token — the version string "stub"
   composed with a 'v' prefix); macro-card lines width-safe.
4. **Errors (C-5)**: ERRORS & WARNINGS block ends every run (layer ·
   stable code · what · why · exact fix); errors mirror to STDERR;
   traceback only with --debug; provider/network/rate-limit/stale
   classification; DATA SOURCES line + macro path (FRED key -> API; no
   key -> public fredgraph.csv; missing key is NOT an error);
   codes.py central registry + RUNBOOK table; earnings missing list
   surfaces as one W_EARNINGS_MISSING entry; E_LAYER why prefers the
   first signal warning (provider errors live on signals).
5. **New files**: codes.py, goldens/ (12 fixtures),
   scripts/make_goldens.py (regen only via --regen; masks ISO dates ->
   FROZEN-DATE and wall-clock durations -> Xs, nothing else — disclosed).

Rule behaviour, fusion arithmetic, engines: UNCHANGED (ENGINES.sha256
MATCH x3 re-verified; env matrix 9 cells green x 419 tests).

## Phase 6 additions (backtest surface — no CONFIG change)

No CONFIG key was added or changed in phases 6-8. The integration
backtest introduced two stable WARNING codes (registry-only additions,
codes.py + the RUNBOOK table; the CONFIG diff above stays exactly the 8
disclosed lines):

| code | what | fired by |
|---|---|---|
| W_BT_DATE_SKIPPED | a backtest date was skipped: no recorded decision record | master.py --backtest when ml_data/cache/dates/<date>.json is absent and --backtest-rerun was not given — the date is excluded LOUDLY, never silently |
| W_BT_FIXTURE_ONLY | the backtest ran on fixture-class evidence only | master.py --backtest when the dataset is the shipped tech-pool pilot (or fewer than 36 dates) — the prereg full-universe verdict set was never built (B-9 carried; the owner command prints) |

CLI additions (flags, not CONFIG): --backtest, --backtest-rerun,
--backtest-dataset, --backtest-out (phase 6); no defaults changed.

## v1.8.0 additions (W5, opt-in risk controls)

| key | default | read by (production) | disclosed behaviour |
| --- | --- | --- | --- |
| RISK_DD_BREAKER_DD | 0.10 | me/backtest.py (only with --bt-breaker) | drawdown circuit-breaker threshold on the backtest net equity curve; opt-in flag, preregistered default backtest unchanged |
| RISK_DD_BREAKER_COOLDOWN_W | 2 | me/backtest.py (only with --bt-breaker) | cooldown windows in cash after the breaker fires, then re-entry |
| RISK_ADV_MAX_PARTICIPATION | 0.10 | me/risk.py size_portfolio (only via the advs kwarg) | ADV participation cap; binds only when the owner supplies ADV data (budget units); W_ADV_UNAVAILABLE otherwise |

Zero existing CONFIG values changed; the three additions are opt-in
(flag / kwarg), so the legacy paths are byte-identical (R15 identity
tests + the frozen decision hash gate).

---

# v1.8.1 append — NETWORK RESILIENCE (N1-N9) + REVIEW FIXES (F1-F8)

Baseline for this diff: the v1.8.0 tree (final_master_e.zip, extracted
and loaded in its own process; values canonicalised so frozenset order
can never fake a change — evidence/v181_config_diff_v180.txt). The
v1.8.1 CONFIG diff is exactly: 13 ADDITIONS + 1 VALUE CHANGE (the F6
order below). Nothing else moved.

## CONFIG additions (13 keys, all me/core.py _cfg with rationale)

| key | default | read in production by | why this default |
|---|---|---|---|
| RUN_BUDGET_S | 1200.0 | run_pipeline (layer-budget clamp + run-budget salvage/skip), me/netguard (run deadline), _exit_sweep | N1: 20 min bounds a cold standard run (~minutes) while a black-holed network can never run to the old per-layer ~1000 s pattern; MASTER_RUN_BUDGET_S env is the CI valve |
| NET_PREFLIGHT_S | 2.0 | NetGuard.preflight (online runs) | N2: a dead host is known within seconds |
| NET_PREFLIGHT_RETRIES | 2 | NetGuard.preflight | N2: 1 + 2 attempts with backoff+jitter |
| NET_PREFLIGHT_HOSTS | the 6 engine hosts | run_pipeline setup (online only) | built from evidence/net_paths.md — every host the three engines call; MASTER_NET_PREFLIGHT=0 / MASTER_NET_PREFLIGHT_HOSTS are the test valves |
| NET_BREAKER_K | 5 | CircuitBreaker (N3) | five consecutive transient/auth failures open a host's breaker; item-level 404s never count |
| NET_BREAKER_COOLDOWN_S | 30.0 | CircuitBreaker (N3) | cooldown before the single half-open probe |
| NET_CALL_CAP_S | 30.0 | NetGuard.wrap_urlopen (timeout clamp) | clamps the engines' 45-300 s timeouts so no single call can outlive the run budget |
| NET_RETRY_BUDGET_S | 45.0 | RetryClock | N5: total retry-time budget per run (backoff + Retry-After + deferred cooldowns draw from it) |
| NET_DEFER_COOLDOWN_S | 1.5 | deferred_pass (N9) | cooldown before the ONE deferred retry attempt |
| NET_NEG_CACHE_PATH | "data/negative_cache.json" | NegCache | N5/F8: master-owned negative cache; permanent failures not refetched until the TTL expires |
| NET_NEG_CACHE_TTL_S | 21600.0 | NegCache.put | 6 h — a day-part: long enough to keep a dead ticker out of every rerun, short enough to pick up a fix |
| FETCH_LEDGER_PATH | "data/fetch_ledger.jsonl" | run_pipeline finally (dump), retry_failed (read) | N4/N9: every online run's ledger; --retry-failed reads only its failed transient items |
| WIZARD_RETRIES | 6 | _Ask (wizard) | F2: the per-question retry budget (was a hard-coded 3) |

## CONFIG VALUE CHANGE (1, ordered by the prompt)

| key | old | new | why |
|---|---|---|---|
| PREFETCH_ALL_MAX | 60 | 150 | F6 (explicitly ordered): --earnings-prefetch all is honoured for sector pools — a 60-name cap starved them. No threshold/door/weight touched. |

## Behaviour changes that are NOT CONFIG values (disclosed)

1. **Net guard install lifecycle** (N1-N9): online (non-stub) runs
   create me/netguard.NetGuard, install the PROCESS-LEVEL guards
   (urllib.request.urlopen + requests.Session.request; disclosed in
   evidence/net_paths.md — no engine file edited, R1), preflight the six
   hosts, and uninstall + save the negative cache + dump the ledger in
   run_pipeline's finally. Offline/stub runs install nothing.
2. **Layer budgets clamped to the run budget** (N1): after RUN_BUDGET_S
   the remaining layers are salvaged/skipped with the "run budget
   exhausted" message; _exit_sweep flushes and exits the PROCESS within
   seconds even with stuck non-daemon workers (never a hang).
3. **Quality per-name loop** (N5/N6/N9): PERMANENT exceptions (404) ->
   negative-cache + [W_ITEM_SKIPPED] + no retry; TRANSIENT -> deferred
   retry after the cooldown (re-scored through the same engine call);
   ctx_out gains coverage "scored/total" and the skipped list. The v1.8.0
   loop is byte-identical when no guard is installed (offline/stub).
4. **Earnings layer** (N6/N9): coverage + skipped ctx_out; transient
   fetch failures recorded by wrap_fetch get ONE deferred attempt and a
   PUBLIC analyze() re-run on the recovered subset.
5. **FETCH HEALTH** (N4): every run's report ends with the block (hosts
   + totals + recovered + skipped items) and the JSON gains the
   additive "fetch_health" key (never NaN); the quality progress line
   carries "net ok N | fail M | skip K".
6. **Auto-mode dead network** (N6): a failed auto probe falls back to
   offline-from-cache with a CLEAR banner + W_NET_FALLBACK_CACHE;
   --mode online keeps its exit-3 contract unchanged.
7. **--strict / --lenient** (F7): OPT-IN exit policies (default = the
   documented contract; strict: degraded->2; lenient: degraded->0; NO-GO
   4 and usage 2 never forgiven).
8. **--retry-failed** (N9): new CLI command (exit 0/1/2) reading the
   last ledger; permanent failures never retried.
9. **Wizard forgiving** (F2): unique prefixes, space-or-comma
   separators, bare number = n-th listed group, difflib suggestion
   (never a guess), WIZARD_RETRIES budget; the stale "3 strikes -> loud
   64" docstring replaced with the true exit-2 contract.
10. **F1 gate 3 wiring** per prereg AMENDMENT 2 (2026-11-19, appended
    BEFORE the code ran): a REAL --bt-spy series computes the SPY half
    (Sharpe @10bps vs SPY over the same dates + net MDD <= SPY MDD +
    1e-9); SYNTHETIC files and <12-date overlap keep the exact
    UNANSWERABLE label. No threshold change.
11. **F3 classifier codes**: W_ENGINE_NO_VERSION / W_PEERS_WATCHLIST /
    W_QUALITY_FLAG (+ W_FETCH_FAILED, W_HOST_BREAKER_OPEN,
    W_ITEM_SKIPPED, W_RETRY_BUDGET, W_NET_FALLBACK_CACHE, W_RUN_BUDGET
    in codes.py with why/fix) — W_UNUSUAL becomes rare.
12. **F4/F5 banner + provenance**: the [plan] banner estimates
    freshness with the REAL engine TTLs (quality 7 d, earnings 12 h,
    meds 24 h) and the macro cadence (45 d): "90/90 cached" can never
    precede a cold pass; "refresh-due" (18 d) is not "stale-data"
    (50 d); provenance STALE reasons split 'older than cadence' from
    'refresh failed/overdue'.
13. **F8**: data/universe_overrides.csv template ships (header + one
    inert unknown-ticker example row — the engine records it as an
    unknown override, no universe effect) and
    scripts/universe_override.py is the owner command
    (add/list/remove; the prompt's CFLT/PSTG lines are in OWNER_RUN.md).
14. **requirements.txt pins** (F7): numexpr >= 2.14.1 (present in the
    tested set) and bottleneck >= 1.4.0 (OPTIONAL, ABSENT here — floor
    is pandas' own documented minimum, UNVERIFIED here per the
    MINIMUM==TESTED rule, disclosed as such).

## Not changed (explicitly)

- W_Q/W_E, E_MISSING_HAIRCUT, doors 60/45, MIN_QUALITY, every
  FRESHNESS_* gate, RISK_* keys: untouched. No door threshold, missing-E
  haircut or weight was retuned on the 12-date fixture.
- Engine TTLs: untouched (meds 24 h cache, quality sec 7 d, earnings
  12 h) — the banner READS them, never changes them.
- No per-name engine parallelism was added; no new ML models.
- Exit codes: the default contract is unchanged (0/1/2/3/4/65/70/130);
  --strict/--lenient are opt-in.
- meds.py / quality.py / earnings_engine.py: untouched (R1;
  ENGINES.sha256 re-verified at W5).
