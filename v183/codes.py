"""codes.py — the CENTRAL code registry (phase 5, C-5).

Every stable error/warning code master.py (or its scripts) can emit lives
HERE, with: severity, the owning layer, what it means, why it fires, and
the EXACT fix command. The RUNBOOK carries the same table (docs section
"ERROR & WARNING CODE REGISTRY"); TestCodesRegistry fails if a code used
in the code base is missing here, if an entry lacks a fix command, or if
the docs table drifts from this module.

Registry invariants:
  * code names are stable strings (never renumbered, never reused);
  * severity is "error" (something failed; run may still produce a result)
    or "warning" (run continued with a disclosed degradation);
  * every fix command is a copy-pasteable python3 invocation (or names the
    owner action when no command applies);
  * CONFIG keys that merely LOOK like codes (W_E, W_Q) are excluded via
    CONFIG_KEYS — they are weights, not codes.

This module is data only: no imports, no side effects, safe to import from
tests, doctor, and the renderer.
"""

REGISTRY: dict[str, dict[str, str]] = {
    # ── errors: a layer or gate failed ──────────────────────────────────
    "E_LAYER": {
        "severity": "error", "layer": "any",
        "what": "a layer ended in ERROR state",
        "why": "the engine raised, timed out, or returned no usable payload",
        "fix": "python3 master.py --doctor (engine/health probe names the real blocker)"},
    "E_NO_RESULT": {
        "severity": "error", "layer": "pipeline",
        "what": "no result / NO-GO: nothing usable was produced",
        "why": "quality scored 0 names or every layer failed (exit code 4)",
        "fix": "python3 master.py --doctor then python3 master.py --warm --mode online"},
    "E_NET_DOWN": {
        "severity": "error", "layer": "net",
        "what": "network required but unreachable",
        "why": "explicit --mode online with a failed probe (exit code 3)",
        "fix": "python3 master.py --mode offline (cached truth) or --mode auto"},
    "E_NET_OFFLINE": {
        "severity": "error", "layer": "providers",
        "what": "providers failed with NETWORK_ERROR under offline mode",
        "why": "offline guard disables sockets; a cache miss has no fallback",
        "fix": "python3 master.py --warm (fill caches) or --mode online"},
    "E_CACHE_UNWRITABLE": {
        "severity": "error", "layer": "cache",
        "what": "cache dir not writable for an online run (exit code 2)",
        "why": "read-only cache root: online runs must be able to refresh",
        "fix": "python3 master.py --cache-dir /tmp/qe (writable) or --mode offline"},
    "E_HASH_MISMATCH": {
        "severity": "error", "layer": "engines",
        "what": "engine file hash differs from ENGINES.sha256",
        "why": "an engine was edited after the release hash was pinned",
        "fix": "python3 master.py --doctor (then sha256sum -c ENGINES.sha256 "
               "— restore the engine from the release zip)"},
    "E_USAGE": {
        "severity": "error", "layer": "cli",
        "what": "bad usage or config (exit code 2)",
        "why": "argument validation failed before any layer ran",
        "fix": "python3 master.py --help (the message names the exact flag)"},
    # ── warnings: run continued with a disclosed degradation ────────────
    "W_NET_OFFLINE": {
        "severity": "warning", "layer": "net",
        "what": "offline mode selected: zero sockets, cache truth only",
        "why": "explicit offline (or MASTER_NET=offline); ages are labelled",
        "fix": "python3 master.py --warm --mode online (refresh the caches)"},
    "W_NET_DOWN": {
        "severity": "warning", "layer": "providers",
        "what": "a provider request failed on the network (result still served)",
        "why": "DNS/TLS/connectivity failure while other sources or caches answered",
        "fix": "python3 master.py --mode offline (cached truth, ages shown)"},
    "W_RATE_LIMIT": {
        "severity": "warning", "layer": "providers",
        "what": "provider rate limit (HTTP 429)",
        "why": "too many requests; provider asked to slow down (Retry-After honoured)",
        "fix": "python3 master.py --mode offline (retry after the Retry-After window)"},

    # ── v1.8.1 · network resilience (N1-N9) + review fixes (F3) ─────────
    "W_FETCH_FAILED": {
        "severity": "warning", "layer": "net",
        "what": "one or more fetches failed after retries",
        "why": "host unreachable / timeouts / 5xx persisted past the retry "
               "budget; the item was skipped, the run continued",
        "fix": "python3 master.py --retry-failed (re-fetch only the failed "
               "transient items), then rerun"},
    "W_HOST_BREAKER_OPEN": {
        "severity": "warning", "layer": "net",
        "what": "a host's circuit breaker is open (calls fail fast)",
        "why": "NET_BREAKER_K consecutive failures opened the breaker; the "
               "cooldown (NET_BREAKER_COOLDOWN_S) gates one half-open probe",
        "fix": "wait for the cooldown then rerun; python3 "
               "scripts/owner_net_check.sh verifies per-host reachability"},
    "W_ITEM_SKIPPED": {
        "severity": "warning", "layer": "any",
        "what": "an item was skipped and listed (item, why, fix)",
        "why": "permanent failure (404/delisted/bad ticker) or an exhausted "
               "retry budget — the layer reports coverage (scored/total)",
        "fix": "check the ticker; dead names: python3 "
               "scripts/universe_override.py add TICKER sector delisted"},
    "W_RETRY_BUDGET": {
        "severity": "warning", "layer": "net",
        "what": "the run's total retry-time budget is exhausted",
        "why": "backoff sleeps + Retry-After waits + deferred cooldowns drew "
               "NET_RETRY_BUDGET_S to zero; later failures skip retries",
        "fix": "rerun when the network is back: python3 master.py "
               "--retry-failed"},
    "W_NET_FALLBACK_CACHE": {
        "severity": "warning", "layer": "net",
        "what": "auto mode fell back to offline-from-cache",
        "why": "the auto-mode network probe failed; cached truth is served "
               "with ages labelled (--mode online keeps its exit-3 contract)",
        "fix": "python3 scripts/owner_net_check.sh (per-host reachability; "
               "run it first when a run is slow), then rerun online"},
    "W_RUN_BUDGET": {
        "severity": "warning", "layer": "pipeline",
        "what": "the overall run budget (RUN_BUDGET_S) was exhausted",
        "why": "the run rendered what it had after the budget; unfinished "
               "layers were salvaged/skipped, the process exited promptly",
        "fix": "python3 master.py --retry-failed (caches were still "
               "filling in the background), then rerun; or raise "
               "MASTER_RUN_BUDGET_S / RUN_BUDGET_S deliberately"},
    "W_ENGINE_NO_VERSION": {
        "severity": "warning", "layer": "earnings",
        "what": "earnings engine exposes no __version__ attribute",
        "why": "drift between the shipped engine and the tested one is "
               "undetectable through the attribute; the docstring version is "
               "reported instead",
        "fix": "python3 master.py --doctor (ENGINES.sha256 is the real "
               "integrity gate — sha256sum -c ENGINES.sha256)"},
    "W_PEERS_WATCHLIST": {
        "severity": "warning", "layer": "quality",
        "what": "quality ranks are relative to the watchlist only",
        "why": "--peers watchlist / --mode quick: rough percentiles against "
               "the requested names, not the engine's sector pools",
        "fix": "python3 master.py --mode standard (honest sector-pool "
               "ranks)"},
    "W_QUALITY_FLAG": {
        "severity": "warning", "layer": "quality",
        "what": "the quality engine flagged a name (e.g. ALTMAN_DISTRESS)",
        "why": "the engine's own per-name flags surfaced through the "
               "adapter (its thresholds are read-only engine policy)",
        "fix": "python3 master.py <ticker> --explain <ticker> (the per-layer "
               "breakdown names the driving metrics)"},
    "W_STALE_CACHE": {
        "severity": "warning", "layer": "cache",
        "what": "a served cache is stale for its display threshold",
        "why": "newest input older than STALE_STATUS_DAYS (7d) AND either "
               "past its publication cadence (macro 45d monthly, quality "
               "135d quarterly, earnings 5d daily) or with a failed refresh "
               "this run; inside the cadence with no failure the report "
               "shows 'refresh-due' instead and emits no warning",
        "fix": "python3 master.py --warm (refresh the caches; an offline "
               "run shows the ages by design)"},
    "W_HEAD_UNAVAILABLE": {
        "severity": "warning", "layer": "ml",
        "what": "ml head UNAVAILABLE in this environment (run continued)",
        "why": "sklearn/numpy/joblib/python version mismatch, missing sklearn, "
               "or a corrupt/incompatible model file",
        "fix": "python3 ml_train.py (retrain on this environment's versions)"},
    "W_EARNINGS_MISSING": {
        "severity": "warning", "layer": "earnings",
        "what": "earnings data missing for one or more names",
        "why": "fewer than 4 usable quarters or the provider failed",
        "fix": "python3 master.py --warm (fill the earnings cache)"},
    "W_ADV_UNAVAILABLE": {
        "severity": "warning", "layer": "risk",
        "what": "ADV liquidity guard UNAVAILABLE",
        "why": "no readable feed carries volume; nothing faked (owner decision pending)",
        "fix": "python3 scripts/adv_probe.py (see the probe verdict for the feed gap)"},
    "W_CONSUMER_MERGED": {
        "severity": "warning", "layer": "macro",
        "what": "unbucketed consumer names share the merged XLP+XLY view",
        "why": "XLP and XLY both map 'consumer' at strength 1.0 "
               "(me/core.py ETF_TO_SECTORS): a long in EITHER basket lifts "
               "every unbucketed consumer name ~+10% conviction; staples "
               "and discretionary are not separated without --bucket",
        "fix": "python3 master.py --bucket staples,discretionary ... "
               "(split the consumer pools; bucketed names keep their own ETF)"},
    "W_RHO_FALLBACK": {
        "severity": "warning", "layer": "risk",
        "what": "correlation fallback to the conservative rho assumption",
        "why": "not enough overlapping price history for a real correlation",
        "fix": "python3 master.py --warm (more price history => real rho)"},
    "W_UNUSABLE_VOL": {
        "severity": "warning", "layer": "risk",
        "what": "a name's volatility was unusable (dropped or pooled)",
        "why": "no usable price history for the trailing window",
        "fix": "python3 master.py --warm (fill the price cache)"},
    "W_EQW_FALLBACK": {
        "severity": "warning", "layer": "risk",
        "what": "sizer fell back to equal weights",
        "why": "the volatility-weighted path was impossible (all vols unusable)",
        "fix": "python3 master.py --warm (fill the price cache)"},
    "W_BUDGET_STANDDOWN": {
        "severity": "warning", "layer": "risk",
        "what": "risk budget stand-down: no positions sized",
        "why": "budget NaN/zero/non-finite, or the DD envelope veto fired",
        "fix": "python3 master.py --doctor (risk CONFIG review)"},
    "W_DD_VETO": {
        "severity": "warning", "layer": "risk",
        "what": "drawdown veto fired (guard, working as designed)",
        "why": "estimated drawdown crossed RISK_MAX_EST_DD on the stated line",
        "fix": "python3 master.py --doctor (RISK_MAX_EST_DD review — the guard is correct)"},
    "W_FUTURE_REPORT": {
        "severity": "warning", "layer": "earnings",
        "what": "an earnings report dated in the future was rejected",
        "why": "clock skew or a bad as-of; PIT discipline refuses future facts",
        "fix": "python3 master.py --as-of <YYYY-MM-DD> (pin the correct clock)"},
    "W_BLOCKED_REASSERT": {
        "severity": "warning", "layer": "ml",
        "what": "the overlay re-asserted a blocked row's AVOID",
        "why": "an overlay tried to un-block a vetoed row; the guard restored it",
        "fix": "python3 master.py --doctor (overlay bounds review — guard is correct)"},
    "W_NO_VOL_NO_STOP": {
        "severity": "warning", "layer": "earnings",
        "what": "live plan carries no stop price",
        "why": "no usable price history for the trailing-126-td vol estimate",
        "fix": "python3 master.py --warm (fill the price cache so the vol stop exists)"},
    "W_SYNTHETIC": {
        "severity": "warning", "layer": "pipeline",
        "what": "SYNTHETIC stub layers rendered (not real engine data)",
        "why": "MASTER_STUBS=1 / hermetic test mode — never for decisions",
        "fix": "python3 master.py (unset MASTER_STUBS for real engine data)"},
    "W_UNUSUAL": {
        "severity": "warning", "layer": "pipeline",
        "what": "a warning could not be classified",
        "why": "text did not match a known pattern and carries no bracketed code",
        "fix": "python3 master.py --debug (capture the exact text and report it)"},
    "W_FRED_KEY_ABSENT": {
        "severity": "warning", "layer": "macro",
        "what": "FRED key absent: public fredgraph.csv path used",
        "why": "FREDAPI/FRED_API_KEY unset — the public CSV path is used instead "
               "(this is NOT an error by itself)",
        "fix": "python3 master.py (set FREDAPI in the env for the API path — optional)"},
    "W_BT_DATE_SKIPPED": {
        "severity": "warning", "layer": "backtest",
        "what": "a backtest date was skipped: no recorded decision record",
        "why": "ml_data/cache/dates/<date>.json is absent and --backtest-rerun "
               "was not given — the date is excluded LOUDLY, never silently",
        "fix": "python3 master.py --backtest --backtest-rerun (re-decide the "
               "date via run_pipeline and write its record)"},
    "W_BT_FIXTURE_ONLY": {
        "severity": "warning", "layer": "backtest",
        "what": "the backtest ran on fixture-class evidence only",
        "why": "the dataset is the shipped tech-pool pilot (or fewer than 36 "
               "dates) — the prereg full-universe verdict set was never built",
        "fix": "python3 ml_dataset.py --dates 36 --sectors all (owner: full "
               "network build, hours) then python3 master.py --backtest"},
    # ── v1.8.2 · no routine W_UNUSUAL (W4): every message a stub/offline/
    #    outage run emits carries a stable code with a why and a fix ───────
    "W_CREDIT_OFF": {
        "severity": "warning", "layer": "macro",
        "what": "credit terms excluded — macro conviction damped",
        "why": "the meds engine excludes its credit terms (no honest credit "
               "read this month); the scenario keeps its other terms at "
               "reduced conviction leverage — not trade-grade, disclosed",
        "fix": "python3 master.py --doctor (macro data review; credit "
               "returns when the engine's credit read does)"},
    "W_MACRO_DEGRADED": {
        "severity": "warning", "layer": "macro",
        "what": "macro layer DEGRADED (engine-reported warnings)",
        "why": "the meds engine reported data-quality warnings (stale or "
               "partial series); the regime keeps a damped confidence",
        "fix": "python3 master.py --warm (refresh the macro snapshot)"},
    "W_MACRO_UNAVAILABLE": {
        "severity": "warning", "layer": "macro",
        "what": "no regime context (macro missing or failed)",
        "why": "the macro layer produced no state: tilt n/a and the risk "
               "budget is capped at 1.0 (the conservative path)",
        "fix": "python3 master.py --doctor (macro engine/snapshot check)"},
    "W_SHORTLIST_EMPTY": {
        "severity": "warning", "layer": "earnings",
        "what": "earnings shortlist empty: nothing passed the quality gate",
        "why": "L3 runs only on L1+L2 survivors; zero survivors means L3 "
               "did not run (layer DEGRADED, honestly reported)",
        "fix": "python3 master.py --doctor (quality gate review) or widen "
               "the pool: python3 master.py --sectors all"},
    "W_SCENARIO_RENORMALIZED": {
        "severity": "warning", "layer": "macro",
        "what": "a macro scenario score was renormalized (terms excluded)",
        "why": "the engine's safe_weighted_score excluded failed series and "
               "renormalized the retained terms; retained weight below 70% "
               "is disclosed, never silent",
        "fix": "python3 master.py --doctor (the scenario panel names the "
               "failed series)"},
    "W_EARNINGS_ACCURACY": {
        "severity": "warning", "layer": "earnings",
        "what": "earnings layer accuracy verdict (descriptive)",
        "why": "the engine's own hit-rate verdict of high-rated names vs "
               "base names — descriptive context for the L3 signal",
        "fix": "python3 master.py MU --explain MU (per-name earnings "
               "evidence)"},
    "W_EARNINGS_BACKTEST": {
        "severity": "warning", "layer": "earnings",
        "what": "opt-in per-ticker price backtest summary",
        "why": "--earnings-backtest: naive edge statistics (clustered "
               "events overstate t) — descriptive only, never a verdict",
        "fix": "python3 master.py MU --earnings-backtest (opt-in flag; "
               "see the caveat in the warning text)"},
}

# CONFIG keys that look like codes but are weights/fills (excluded from
# scanning).
CONFIG_KEYS = {"W_E", "W_Q", "W_RHO", "W_VOL", "E_MISSING_V2",
              "E_MISSING_HAIRCUT"}

_CODE_TOKEN_RE = __import__("re").compile(r"\b([WE]_[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\b")


def scan_source(text: str) -> set:
    """Every code-shaped token (W_*/E_*) in a piece of Python source.

    Deliberately over-matches (comments and strings included): a code that
    appears anywhere in the file must be in the registry. CONFIG_KEYS are
    subtracted by the caller."""
    return set(_CODE_TOKEN_RE.findall(text))


def docs_table() -> str:
    """The registry as the RUNBOOK markdown table (kept next to the
    hand-written copy; the test asserts they carry the same rows)."""
    lines = ["| code | severity | layer | what | why | fix |",
             "|---|---|---|---|---|---|"]
    for code, e in sorted(REGISTRY.items()):
        lines.append(f"| {code} | {e['severity']} | {e['layer']} "
                     f"| {e['what']} | {e['why']} | `{e['fix']}` |")
    return "\n".join(lines)
