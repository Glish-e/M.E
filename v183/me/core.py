"""me/core.py — the shared core of the M.E. orchestrator (v1.8.0 split
from master.py §0-§3.1): the CONFIG registry (every tunable with its
one-line rationale — changing any needs walk-forward evidence, never
in-sample tuning), the run datatypes (MacroState/Candidate/LayerSignal/
LayerResult/Decision/Context/LayerProvenance/RunOutput), the small
shared helpers (finite/normalise/month-end/redaction), the net-mode
probe + retry wrappers + meds snapshot machinery, the env/attr/config
restore guards (two runs in one process leak no state), _Progress, and
the pure macro/decision glue (macro_tilt/macro_view/_ruleset/
_base_conviction) plus the atomic-write and ENGINES.sha256 helpers.
Leaf module: imports stdlib only; never imports master."""
from __future__ import annotations

# ════════════════════════════════════════════════════════════════════════
#  § 0 · IMPORTS + VERSION (stdlib only; pandas/numpy come with the engines)
# ════════════════════════════════════════════════════════════════════════
import calendar
import os
import re
import sys
import time
import json
import types
from typing import Any, Callable
from dataclasses import dataclass, field
from pathlib import Path

__version__ = "1.8.3"


# ════════════════════════════════════════════════════════════════════════
#  § 1 · CONFIG — every tunable + one-line rationale (priors, fixed a priori;
#         changing any of them needs walk-forward evidence, never in-sample
#         tuning — same idea as quality._param)
# ════════════════════════════════════════════════════════════════════════
CONFIG: dict[str, Any] = {}
_RATIONALE: dict[str, str] = {}


def _cfg(name: str, value: Any, rationale: str) -> Any:
    """Register one documented tunable (name -> value + rationale)."""
    CONFIG[name] = value
    _RATIONALE[name] = rationale
    return value


def _canonical_json(obj: Any) -> str:
    """Deterministic JSON render of a CONFIG-like tree: every
    set/frozenset becomes a SORTED list, tuples become lists, dict keys
    become strings. Without this, str(frozenset(...)) order follows
    PYTHONHASHSEED and any hash built on it changes every process
    (D-18-002: the v1.7.0 'config hash' did exactly that)."""
    def canon(o: Any) -> Any:
        if isinstance(o, (set, frozenset)):
            vals = [canon(x) for x in o]
            vals.sort(key=lambda v: json.dumps(v, sort_keys=True,
                                              default=str))
            return vals
        if isinstance(o, dict):
            return {str(k): canon(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [canon(x) for x in o]
        return o
    return json.dumps(canon(obj), sort_keys=True, default=str)


def config_rationales() -> dict[str, str]:
    """Name -> rationale for every tunable (docs + selftest)."""
    return dict(_RATIONALE)


# -- engines ---------------------------------------------------------------
_cfg("TESTED_VERSIONS", {"meds": "14.7.0", "quality": "3.4.1", "earnings": "3"},
     "Engine versions this master was built and tested against; a different "
     "one prints a warning in the header and on stderr.")
_cfg("ENGINE_VERSION_ATTRS", {"meds": "__version__", "quality": "ENGINE_VERSION",
                              "earnings": "__version__"},
     "Module attribute looked up for each version (earnings has none -> the "
     "docstring version '3' is reported and drift cannot be detected).")
# -- fusion priors ---------------------------------------------------------
_cfg("W_Q", 0.65, "Quality share of the blended base; quality is the slower, "
                  "higher-signal layer. W_Q + W_E must sum to 1 (selftest).")
_cfg("W_E", 0.35, "Earnings share of the blended base (timing layer).")
_cfg("E_MISSING_HAIRCUT", 0.90, "With no earnings score the conviction is "
     "Q*0.90: missing means no information, a mild penalty only.")
_cfg("RULESET", "legacy", "P-1 / P-6 (spec 3.2, phase 4): the ruleset "
     "selector. legacy = the shipped v1.5.0 rules: missing-E keeps the "
     "x0.90 advantage (missing beats observed E whenever e < 0.714*q) and "
     "the LONG/WATCH doors compare ROUNDED conviction. v2 = missing-E is "
     "scored as the fixed conservative fill E_MISSING_V2 through the SAME "
     "blend (invariant-tested: missing never outranks an observed E) and "
     "the doors compare UNROUNDED conviction (display stays rounded). "
     "Default legacy until backtest evidence + owner approval; --ruleset v2 "
     "is the opt-in and the header labels the active ruleset either way.")
_cfg("E_MISSING_V2", 0.0, "P-1 (spec 3.2, phase 4): the FIXED conservative "
     "E a missing-E name is scored at under ruleset v2. 0.0 = the floor of "
     "the engine's 0-100 E scale, and the ONLY value for which "
     "base(missing E) <= base(any observed E) holds for EVERY observed "
     "E >= 0 (the spec 3.2 invariant); any higher fill would let a name "
     "with observed E below the fill rank below the missing name — the "
     "exact subsidy legacy exhibits at e < 0.714*q. Chosen a priori (the "
     "invariant IS the choice), not tuned on any result.")
_cfg("EARNINGS_WEAK_SCALE", 0.5, "W_E is halved (then renormalised) while the "
     "engine's own walk-forward verdict is WEAK/NO SIGNAL or NOT ENOUGH DATA.")
_cfg("MACRO_TILT_GAIN", 0.10, "A full tilt (+1) moves conviction by +10% at "
     "most; macro tilts, it never vetoes.")
_cfg("MACRO_DEGRADED_DAMP", 0.5, "Halve the tilt EFFECT (the displayed tilt "
     "is unchanged) when macro is DEGRADED or credit is OFF.")
_cfg("MIN_QUALITY", 40.0, "Hard quality gate: below 40 (quality's own D band) "
     "a name is not ownable, whatever earnings says.")
_cfg("VETO_FLAGS", frozenset(("NEGATIVE_EQUITY", "ALTMAN_DISTRESS")),
     "Quality flags that veto ownership regardless of score; every other "
     "flag is shown as a warning only.")
_cfg("CYCLICAL_SECTORS", frozenset(("tech", "industrials", "materials",
     "financials", "communication", "specialty")),
     "Sectors that suffer most in a defensive regime (tilt -0.5). "
     "REACHABILITY (v1.8.3): 'financials' and 'specialty' have NO entry "
     "in ETF_TO_SECTORS, so macro_tilt returns None for them BEFORE the "
     "cyclical test — their -0.5 is currently INERT (documented, kept "
     "for the day an ETF mapping is added; the register gate checks "
     "this note).")
_cfg("ETF_TO_SECTORS", {
    "XLE": (("energy", 1.0),),
    "XLU": (("utilities", 1.0),),
    "XLP": (("consumer", 1.0),),
    "XLY": (("consumer", 1.0),),
    "XLI": (("industrials", 1.0),),
    "QQQ": (("tech", 1.0), ("communication", 1.0)),
    "SPY": (("energy", 0.5), ("utilities", 0.5), ("consumer", 0.5),
            ("industrials", 0.5), ("tech", 0.5), ("communication", 0.5),
            ("materials", 0.5)),
    "DBC": (("energy", 0.5), ("materials", 0.5)),
}, "Macro ETF vocabulary -> quality sector keys; strength 1.0 = strong, "
   "0.5 = weak (tilt halved). SPY covers only the ETF-mapped equity sectors, "
   "so healthcare/financials/reits/specialty stay macro-silent.")
_cfg("SLEEVE_ETFS", frozenset(("TLT", "BIL", "SGOV")),
     "Non-equity rates/cash sleeve: shown on the macro card, never sent to "
     "L2/L3.")
_cfg("DEFENSIVE_SCENARIOS", frozenset(("HARD_LANDING", "CREDIT_CRUNCH",
     "STAGFLATIONARY_DRAG")), "meds defensive_regimes; regime_now() has no "
     "regime_class, so the master derives it with this set.")
_cfg("NEUTRAL_KEY", "NEUTRAL_WAIT_AND_SEE",
     "meds' Neutral scenario key (derived regime_class 'neutral').")
# -- native grade bands (never reused across layers) ------------------------
_cfg("MASTER_GRADES", ((75.0, "A"), (60.0, "B"), (45.0, "C"), (30.0, "D"),
                       (0.0, "F")),
     "The ONLY unified scale: master conviction bands.")
_cfg("QUALITY_NATIVE_GRADES", ((80.0, "A"), (60.0, "B"), (40.0, "C"),
                               (25.0, "D"), (0.0, "F")),
     "quality.py's own published bands — shown only on the quality layer.")
_cfg("EARNINGS_NATIVE_GRADES", ((70.0, "A"), (50.0, "B"), (30.0, "C"),
                                (10.0, "D"), (0.0, "F")),
     "earnings_engine's own _rating bands (documented vocabulary). The "
     "production adapter shows the engine's OWN rating string verbatim and "
     "never re-scores through these bands; they are consumed by the test "
     "suite's signal builders and the band-ordering gate, and by any future "
     "adapter that must derive a letter from a numeric engine score. "
     "v1.4.1 (B6) port: documented as not-read-in-production — the rules "
     "register (scripts/rules_register_check.py) carries it as DISCLOSED.")
# -- actions ----------------------------------------------------------------
_cfg("ACTION_LONG_AT", 60.0, "Conviction needed for LONG.")
_cfg("ACTION_WATCH_AT", 45.0, "Conviction needed for WATCH.")
_cfg("MAX_REASONS", 5, "Short reason strings carried per decision.")
_cfg("RISK_CAP_DEGRADED", 1.0, "risk_budget cap when macro is DEGRADED, "
     "credit OFF or quality LOW; APPLIED as the sizer budget cap "
     "(master.py RiskLayer -> size_portfolio).")
# -- sectors ----------------------------------------------------------------
_cfg("QUALITY_SECTORS", frozenset(("financials", "industrials", "healthcare",
     "tech", "consumer", "energy", "utilities", "materials", "reits",
     "communication", "specialty")),
     "The 11 quality sector keys (static copy so the CLI can validate "
     "--sector/watchlist columns without importing quality.py).")
_cfg("SECTOR_ORDER", ("tech", "communication", "consumer", "industrials",
     "energy", "utilities", "materials", "healthcare", "financials", "reits",
     "specialty"), "Display order of the sector-tilt card line.")
_cfg("SECTOR_ABBR", {"tech": "tech", "communication": "comm", "consumer": "cons",
     "industrials": "indu", "energy": "energy", "utilities": "util",
     "materials": "mats", "healthcare": "health", "financials": "fin",
     "reits": "reits", "specialty": "spec", "staples": "stap",
     "discretionary": "disc"}, "6-char sector labels for the table.")
_cfg("STAPLES_SET", frozenset(
    "DG DLTR COST WMT TGT KR SFM KO PEP MNST KDP PG CL KMB CHD CLX ENR GIS "
    "K CPB CAG SJM HRL MKC HSY TSN MO PM EL COTY BJ GO SPTN UNFI CHEF USFD "
    "SYY PFGC ANDE ADM BG INGR DAR".split()),
    "Owner-curated staples half of quality's merged consumer group "
    "(GICS-aligned approximation); used only when --bucket is active.")
_cfg("DISCRETIONARY_SET", frozenset(
    "HD LOW TJX ROST BURL MCD SBUX YUM CMG DRI DPZ QSR WING TXRH NKE LULU "
    "DECK CROX SKX UA UAA VFC HBI PVH RL ULTA F GM YUMC PLAY FIVE OLLI "
    "TSLA AMZN BKNG ABNB DASH EBAY".split()),
    "Owner-curated discretionary half of the consumer group (GICS-aligned "
    "approximation: autos, retail, restaurants, apparel, broadline e-comm); "
    "see STAPLES_SET.")
_cfg("EXPLAIN_METRICS", ("roic", "gross_profitability", "operating_margin",
     "fcf_margin", "net_debt_ebitda", "altman_z", "ebitda_yield", "fcf_yield",
     "accruals_ratio", "shareholder_yield"),
     "Headline metric shortlist for --explain (quality returns ~30).")
# -- earnings funnel ---------------------------------------------------------
_cfg("EARNINGS_TOP_K", 25, "L3 runs only on the K best L1+L2 survivors — "
     "saves most Yahoo calls and avoids 429s. v1.4.1 (B6) port, phase 2: "
     "this key IS the standard-mode --earnings-top default (MODES reads "
     "it at import AND at _apply_mode time; quick/deep keep their own "
     "presets 10/40).")
_cfg("EARNINGS_PLAN_MIN", 50.0, "eng.plan min_score (the engine's tested rule).")
_cfg("EARNINGS_HOLD_DAYS", 90, "eng.plan hold window (swing/position horizon).")
_cfg("EARNINGS_TP", 0.15, "eng.plan take-profit. Phase 4 (B-7c): the ONE "
     "source of truth for the take-profit — passed to BOTH the engine's "
     "live signals() call and the analyze(trade=True) backtest, so the "
     "live plan and the backtest can never disagree (the engine's own "
     "0.20 default is never reached because master always supplies this "
     "value; the engine file stays untouched).")
_cfg("EARNINGS_STOP_K", 2.0, "P-3 (spec 3.4, phase 4): live-plan stop = "
     "entry x (1 - k x annualised vol x sqrt(hold_days/365)) with k from "
     "this key (hold_days calendar = EARNINGS_HOLD_DAYS, vol = the sizer's "
     "126-td trailing annualised vol off the engine's price cache — the "
     "same estimate the risk layer uses). 2.0 is the pre-registered "
     "MID-grid value of the spec's {off,1.5,2.0,3.0} grid; the grid "
     "backtest (spec 5.8, later phase) chooses by pre-registered OOS rules "
     "— no result has been used to pick 2.0. No vol -> no stop, with a "
     "visible W_NO_VOL_NO_STOP warning (code + fix command), never a "
     "silent None.")
_cfg("EARNINGS_MAX_AGE", 10, "NOW chip needs a report <= 10 days old.")
_cfg("EARNINGS_QUARTERS", 40, "EarningsEngine history depth (~10y).")
# -- orchestration -----------------------------------------------------------
_cfg("DEFAULT_WORKERS", 4, "Earnings pool size; keep <= 4 to share Yahoo "
     "politely with quality/meds (a warning is printed above that).")
_cfg("LAYER_TIMEOUT_S", 900, "STANDARD-mode per-layer wall-clock budget "
     "(prefetch + run); --mode quick/deep use their own presets. v1.4.1 "
     "(B6) port, phase 2: this key IS the standard-mode --timeout default "
     "(MODES reads it at import AND at _apply_mode time), so the key and "
     "the preset can never drift apart.")
_cfg("MODES", {
    "quick": {"timeout": 300.0, "peers": "watchlist", "earnings_top": 10,
              "earnings_prefetch": "none"},
    "standard": {"timeout": float(CONFIG["LAYER_TIMEOUT_S"]),
                 "peers": "builtin",
                 "earnings_top": int(CONFIG["EARNINGS_TOP_K"]),
                 "earnings_prefetch": "none"},
    "deep": {"timeout": 3600.0, "peers": "builtin", "earnings_top": 40,
             "earnings_prefetch": "all"},
}, "Run presets: what each --mode sets unless the user passes the flag "
   "explicitly. quick trades exact sector ranks for a small comparison pool "
   "(the watchlist itself); standard keeps honest sector pools; deep is the "
   "long research pass. standard mirrors the v1.0.0 defaults exactly and "
   "v1.4.1 (B6) resolves from CONFIG[EARNINGS_TOP_K]/[LAYER_TIMEOUT_S] at "
   "import AND at _apply_mode time, so the two formerly dead keys are now "
   "the single source of truth for the standard preset.")
_cfg("MODE_DEFAULT", "standard", "Default run mode (honest sector-pool ranks; "
     "the [plan] banner teaches quick/deep/warm when the cache is cold).")
_cfg("WARM_TIMEOUT_S", 3600.0, "--warm budget: cache filling is the point, so "
     "it gets the deep-style long wall clock (explicit --timeout wins).")
_cfg("COLD_S_PER_NAME", (0.8, 2.0), "Observed cold-fetch seconds per universe "
     "name (rate-limited providers, shared with macro) — only used for the "
     "[plan] banner's ETA range, never for any decision.")
_cfg("WARM_ETA_RANGE_S", (60.0, 300.0), "Warm-run ETA range shown in the [plan] "
     "banner (memo + disk caches, no provider fetches except expired prices).")
_cfg("PRICE_TTL_H", 12.0, "quality's price cache TTL — above this age the "
     "[plan] banner warns that prices will re-fetch (slower pass).")
_cfg("PREFETCH_ALL_MAX", 150, "v1.8.1 (F6, ordered change 60 -> 150): "
     "--earnings-prefetch all is honoured only when the watchlist is <= "
     "this many names, so sector pools warm (a 60-name cap starved them).")
_cfg("PROBE_TIMEOUT_S", 6.0, "--check per-source probe timeout.")
_cfg("MACRO_SNAPSHOT_MAX_AGE_H", 48.0,
     "A meds snapshot (offline / force-snapshot mode) older than this is "
     "reported DEGRADED, never OK: meds' own cache TTL is 24 h, so 48 h = "
     "two missed refresh cycles before master calls the regime stale. "
     "Disclosure gate on the macro card; the tilt is damped like any other "
     "DEGRADED macro and it is never a per-ticker fusion input.")
_cfg("OVERLAY_MAX_ADJ", 10.0,
     "An overlay layer (stage 'overlay', L4-style) may move a conviction by "
     "at most this much per name — a bound, not a weight: the core fusion "
     "(0.65*Q + 0.35*E) is never touched (H2), veto/gate AVOIDs are never "
     "adjusted, and the clamp is disclosed in the reasons line. 10 points = "
     "one grade band: enough to matter, never enough to manufacture LONG "
     "from a name fusion scored below the door.")
# -- ML overlay (L4, phase 5) ------------------------------------------------
_cfg("ML_MODELS_DIR", "ml_data/models",
     "Where MLLayer looks for head_{q,e,macro}.npz + validation_*.json "
     "(written by ml_train.py; --ml-models overrides). An absent/empty dir "
     "is the UNTRAINED state, never an error.")
_cfg("ML_ADJ_MAX", 5.0,
     "The ML overlay's own conviction_adj bound (±5, half the generic "
     "OVERLAY_MAX_ADJ): an ACTIVE head may nudge, never re-rank a book. "
     "Applied on top of the generic clamp, so the effective bound is "
     "min(ML_ADJ_MAX, OVERLAY_MAX_ADJ).")
_cfg("ML_FORBIDDEN_FEATURES", frozenset(
     ("ret_21", "ret_63", "y_q", "y_e", "y_m", "macro_ret_1m",
      "event_date", "label_end_63")),
     "Feature names a model may NEVER use: they are derived from prices "
     "AFTER the as-of date (the label window), so loading a model that "
     "consumes one is refused loudly (leakage guard, phase-5 gate).")
# -- risk sizer (L5, phase 5) ------------------------------------------------
_cfg("RISK_VOL_LOOKBACK_TD", 126,
     "Trading days of daily returns behind each name's annualised volatility "
     "(~6 months): long enough to be stable, short enough to react to a "
     "regime change; matches the label horizon order of magnitude.")
_cfg("RISK_CORR_LOOKBACK_TD", 126,
     "Trading days behind the average pairwise correlation (the "
     "equicorrelation model): same window as vol so both describe the same "
     "market regime.")
_cfg("RISK_MIN_HISTORY_TD", 42,
     "Below this many price rows a name's vol is not trusted; it falls back "
     "to the median vol of the priced names (never an invented number).")
_cfg("RISK_MAX_NAME_W", 0.10,
     "Max single-name weight as a fraction of the risk budget: a 10% cap "
     "means one idea can never dominate the book, whatever its conviction.")
_cfg("RISK_MAX_SECTOR_W", 0.35,
     "Max summed weight per quality sector as a fraction of the risk "
     "budget: sector concentration is the classic screener failure mode "
     "(tech-only books); 35% allows a deliberate tilt, not a bet.")
_cfg("RISK_MIN_EFFECTIVE_BETS", 8.0,
     "Gross exposure is capped at budget * effective_bets/8 where "
     "effective_bets = N/(1+(N-1)*rho_bar): a perfectly correlated book "
     "(rho->1, eff->1) deploys at most 1/8 of the budget. 8 independent "
     "bets is the level at which a capped book deploys fully.")
_cfg("RISK_DD_FACTOR", 2.0,
     "Estimated max drawdown = this factor x annualised portfolio vol (a "
     "rough stress heuristic for equity portfolios, not a VaR): it is an "
     "ESTIMATE shown with its inputs, never a probability (H5).")

_cfg("RISK_DD_BREAKER_DD", 0.10,
     "v1.8.0 (W5): opt-in --bt-breaker drawdown circuit-breaker threshold "
     "on the backtest's NET equity curve (only with the flag; the "
     "preregistered default backtest is unchanged).")
_cfg("RISK_DD_BREAKER_COOLDOWN_W", 2,
     "v1.8.0 (W5): after the breaker fires, the book stays in cash this "
     "many windows (label windows) before re-entering — a cooldown, not "
     "a permanent stand-down.")
_cfg("RISK_ADV_MAX_PARTICIPATION", 0.10,
     "v1.8.0 (W5): opt-in ADV liquidity guard (sizer kwarg advs=): a "
     "name's weight is capped at this fraction of its average daily "
     "volume (ADV in budget units). Binds only when the owner supplies "
     "ADV data; without data the loud W_ADV_UNAVAILABLE warning fires "
     "(the phase-4 probe found no volume feed in the engines' caches).")
_cfg("RISK_MAX_EST_DD", 0.30,
     "Portfolio veto threshold: if the estimated max drawdown exceeds 30% "
     "even after the correlation cap, every weight goes to 0 (all cash) and "
     "the veto is disclosed. 30% = the point where recovery needs +43%.")
_cfg("RISK_MIN_BUDGET", 0.25,
     "A macro risk budget below 0.25 (from meds' conviction_leverage, "
     "degraded-capped at 1.0) is a stand-down signal: the sizer vetoes new "
     "deployment instead of placing token positions.")
_cfg("RISK_FALLBACK_RHO", 0.5,
     "v1.4.1 port (B2, phase 2): the conservative equicorrelation used by "
     "the est-DD estimate when vols exist but rho is unavailable (1-2 "
     "names, <42 overlapping rows, a correlation error, or a non-finite "
     "rho_bar). The correlation cap itself stays OFF in that state — both "
     "facts are DISCLOSED (note + footer + JSON rho_fallback/rho_used + the "
     "stable W_RHO_FALLBACK code), never silent. 0.5 is a documented "
     "conservative assumption, not a rule change: books with a real rho are "
     "untouched (asserted by test_b2_*).")
_cfg("RISK_MAX_PRICE_NAMES", 60,
     "The sizer fetches price history for at most this many LONG names "
     "(conviction order) — the same Yahoo-politeness ceiling as "
     "PREFETCH_ALL_MAX; overflow names fall back to the median vol.")
_cfg("RISK_SIZING_MODE", "legacy", "P-2 (spec 3.3, phase 4): the sizing "
     "mode. legacy = the shipped sizer: inverse-vol weights, name cap, "
     "sector cap, correlation-aware gross cap eff/8, est-DD veto. "
     "vol_target = the opt-in mode: the SAME weights/caps, but the "
     "correlation-aware scaling is expressed as a volatility target — "
     "gross is solved so the estimated portfolio vol (equicorrelation, "
     "the same inputs) hits RISK_VOL_TARGET, capped at the budget (no "
     "leverage); name cap, sector cap and the DD veto are kept. Any "
     "looser-than-legacy deployment prints a 'looser than norm by X%' "
     "note with X computed from the actual numbers. Default legacy; "
     "--sizing vol_target opts in.")
_cfg("RISK_VOL_TARGET", 0.15, "P-2 (spec 3.3, phase 4): target annualised "
     "portfolio vol for the vol_target sizing mode (fraction of budget "
     "deployed x vol). 0.15 coheres with the legacy risk envelope by "
     "construction: at target, est max DD = RISK_DD_FACTOR x 0.15 = 0.30 "
     "= exactly RISK_MAX_EST_DD (the legacy veto line). Pre-registered "
     "coherence, not a result-tuned value.")
# -- net modes / freshness / retry / freeze (final phase) --------------------
_cfg("NET_MODES", ("auto", "online", "offline"),
     "The data-mode half of --mode (quick/standard/deep stay the depth "
     "presets): auto probes the network once (2 s budget, DNS+TCP, no "
     "payload) and picks online/offline; online/offline are explicit.")
_cfg("NET_MODE_DEFAULT", "auto",
     "Default --mode: auto = the standard depth preset + one cheap probe "
     "deciding online vs offline. Identical depth behaviour to v1.4.0's "
     "no-flag default; only the network policy is new.")
_cfg("PROBE_HOST", "fred.stlouisfed.org",
     "The one stable host the auto-mode probe resolves and connects to "
     "(TCP 443, no payload, no request): a source the macro engine itself "
     "uses, so reachability here means reachability for the real fetch.")
_cfg("PROBE_PORT", 443, "Probe TCP port (https).")
_cfg("PROBE_BUDGET_S", 2.0,
     "Total budget for the auto-mode probe (DNS + TCP). Beyond this the "
     "run is offline — a stalled DNS server must never stall a screener.")
_cfg("FRESHNESS_MACRO_MAX_AGE_D", 45,
     "macro (monthly FRED data, meds floors to month-end): STALE when the "
     "engine's own effective_as_of is older than 45 days = one monthly "
     "cycle + slack. STALE keeps the data and the score, shows the age.")
_cfg("FRESHNESS_QUALITY_MAX_AGE_D", 135,
     "quality (quarterly SEC fundamentals): STALE when the cache fetch "
     "stamp is older than 135 days = a full quarter + the SEC filing lag "
     "(~30-45d). Per-name staleness is the engine's own STALE_DATA flags.")
_cfg("FRESHNESS_EARNINGS_PRICE_MAX_AGE_D", 5,
     "earnings (event-driven, daily prices): STALE when the price history "
     "fetch stamp is older than 5 calendar days (quality's own price TTL "
     "is 5 days; the earnings engine's is 12 h).")
_cfg("FRESHNESS_EARNINGS_EVENT_MAX_D", 135,
     "Per-name flag: no earnings row newer than a quarter + filing lag "
     "means a report date has passed since the cache was written (the "
     "engine exposes no calendar; this is the honest cadence bound).")
_cfg("RETRY_MAX_ATTEMPTS", 3,
     "Per-request attempts in online mode (1 + 2 retries) for the "
     "transport/fetch seams master can wrap adapter-side (quality "
     "default_transport, earnings _fetch/_px_fetch). 4xx other than 429 "
     "never retry; 429 is left to the engines' own Retry-After handling.")
_cfg("RETRY_BACKOFF_S", (0.5, 1.5),
     "Backoff before retry 1 and retry 2, plus +-20% jitter, so parallel "
     "workers do not resynchronise on the provider.")
# -- v1.8.1 · network resilience (N1-N9) --------------------------------------
_cfg("RUN_BUDGET_S", 1200.0,
     "N1: the OVERALL run wall-clock budget for a STANDARD-depth run (and "
     "the fallback for unknown depths): after it the run renders what it "
     "has, salvages unfinished layers and the process exits within seconds "
     "even if a worker is stuck (MASTER_RUN_BUDGET_S env overrides it for "
     "tests/CI). v1.8.2 (W1): the depth-derived value lives in "
     "RUN_BUDGET_BY_DEPTH; this key stays the disclosed standard value and "
     "the fallback (S7: runtime knob, listed in the CONFIG diff).")
_cfg("RUN_BUDGET_BY_DEPTH", {"quick": 600.0, "standard": 1200.0,
                             "deep": 4500.0},
     "v1.8.2 (W1): the OVERALL run budget derived from the depth preset "
     "(MASTER_RUN_BUDGET_S env still wins; RUN_BUDGET_S is the fallback for "
     "unknown depths). quick 600 s = 2x its 300 s per-layer preset (measured "
     "real quick runs 6-25 s, stub 0.3 s: 24x+ headroom); standard 1200 s = "
     "the unchanged v1.8.1 RUN_BUDGET_S; deep 4500 s = its 3600 s layer "
     "preset + 900 s slack — v1.8.1's flat 1200 s silently CLIPPED a legit "
     "deep layer at 1200 s (the depth-derived budget fixes that). Display/"
     "budget only; never a fusion input.")
_cfg("NET_PREFLIGHT_S", 2.0,
     "N2: per-host preflight TCP probe budget (DNS+connect, no payload) "
     "before the layers run in online/auto-live mode; a dead host is "
     "known within seconds, not minutes.")
_cfg("NET_PREFLIGHT_RETRIES", 2,
     "N2: preflight retries per host with backoff+jitter (1 + 2 attempts).")
_cfg("NET_PREFLIGHT_HOSTS", (
         ("api.stlouisfed.org", 443), ("fred.stlouisfed.org", 443),
         ("www.sec.gov", 443), ("data.sec.gov", 443),
         ("query1.finance.yahoo.com", 443), ("finnhub.io", 443)),
     "N2: the host list preflighted (built from evidence/net_paths.md — "
     "every host the three engines call). A dead host OPENS its breaker "
     "immediately (fail fast). MASTER_NET_PREFLIGHT=0 disables preflight "
     "(the hermeticity valve for tests/CI).")
_cfg("NET_BREAKER_K", 5,
     "N3: per-host circuit breaker — consecutive fetch failures (transient "
     "or auth classes; item-level 404s do NOT count) before the host's "
     "breaker OPENS and every call fails instantly.")
_cfg("NET_BREAKER_WINDOW_N", 20,
     "v1.8.2 (W1): the breaker's SECOND trip rule — the rolling window of "
     "the last N calls per host over which the weighted failure RATE is "
     "compared to NET_BREAKER_RATE (intermittent ok/fail hosts never "
     "accumulate K consecutive failures; the consecutive rule stays).")
_cfg("NET_BREAKER_RATE", 0.5,
     "v1.8.2 (W1): trip when weighted failures in the rolling window reach "
     "RATE * WINDOW (timeouts count NET_BREAKER_TIMEOUT_WEIGHTx). 0.5 with "
     "N=20: 10 plain failures — or 5 timeouts — inside the last 20 calls.")
_cfg("NET_BREAKER_TIMEOUT_WEIGHT", 2.0,
     "v1.8.2 (W1): a TIMEOUT failure counts this much in the rate rule (a "
     "timeout burned a full NET_CALL_CAP_S of wall; a fast 5xx did not).")
_cfg("NET_BROWNOUT_S", 120.0,
     "v1.8.2 (W1): the GLOBAL brownout budget — the total wall time the run "
     "may spend inside FAILED attempts (successful attempts never count) "
     "before EVERY breaker is force-opened and all further calls fail "
     "fast. Measured per-host brownout trip (cap 30 s, K 5, 3 attempts): "
     "184.4 s, x3 sequential host families = 553 s > the 300 s standard / "
     "180 s quick targets — this knob bounds the whole run at 120 s of "
     "failed wall (bound: 10 + 120 + 30 + 1.5 + 1 = 162.5 s < 180 s). 0 "
     "disables the guard (not recommended).")
_cfg("NET_PREFLIGHT_TOTAL_S", 10.0,
     "v1.8.2 (W1): the WHOLE preflight pass is capped at this wall time — "
     "hosts not probed before it runs out are marked dead (breaker open, "
     "fail fast, honest note): a DNS-hang outage cannot stretch preflight "
     "to hosts x 3 x NET_PREFLIGHT_S. Bounds the outage case: 10 + 1.5 + "
     "slack = 12.5 s < the 15 s target. 0 disables the cap (v1.8.1 "
     "behaviour).")
_cfg("NET_BREAKER_COOLDOWN_S", 30.0,
     "N3: breaker cooldown: after it the host goes half-open and exactly "
     "ONE probe goes through; success closes, failure re-opens.")
_cfg("NET_CALL_CAP_S", 30.0,
     "N3/N1: the master process guard clamps every engine request "
     "timeout to this (min(engine timeout, cap)) so a 45-300 s engine "
     "timeout can never stall the run past the budget.")
_cfg("NET_RETRY_BUDGET_S", 45.0,
     "N5: the TOTAL retry-time budget per run (backoff sleeps, "
     "Retry-After waits, deferred cooldowns all draw from it).")
_cfg("NET_DEFER_COOLDOWN_S", 1.5,
     "N9: cooldown before the deferred retry pass (ONE more attempt for "
     "transient-failed items after their layer's main pass).")
_cfg("NET_NEG_CACHE_PATH", "data/negative_cache.json",
     "N5/F8: the master-owned negative-cache file (layer:item -> why/fix/"
     "until-TTL). PERMANENT failures (404/delisted/bad ticker) are not "
     "refetched until the TTL expires.")
_cfg("NET_NEG_CACHE_TTL_S", 21600.0,
     "N5: negative-cache entry TTL (6 h: a day-part, long enough to keep "
     "a dead ticker out of every rerun, short enough to pick up a fix).")
_cfg("FETCH_LEDGER_PATH", "data/fetch_ledger.jsonl",
     "N4/N9: every online run dumps its fetch ledger here (jsonl) — the "
     "input --retry-failed reads to re-fetch ONLY the failed transient "
     "items of the last run.")
_cfg("WIZARD_RETRIES", 6,
     "F2: the wizard's per-question retry budget (invalid answers before "
     "the honest exit 2), forgiving prefixes/close-matches/numbers first.")
_cfg("FREEZE_MAX_BYTES", 268435456,
     "--freeze copies at most this many bytes of engine cache files into "
     "the freeze dir (256 MB): a standard-mode quality pool is ~1.7 GB, so "
     "freeze is EXACT for quick/watchlist-peer runs and size-capped (with "
     "a loud note) for standard/deep pools.")
_cfg("STUB_WARM_BUDGET_S", 10.0,
     "Regression guard: a warm MASTER_STUBS run on the default watchlist "
     "must finish in well under this (measured 0.3s; 10s = 30x headroom) "
     "or the suite fails — stub runs are the fast tier by contract. NOT "
     "currently read by PRODUCTION master.py: the budget is enforced by "
     "the test suite (TestStubWarmBudget), so the register discloses it as "
     "not-read-in-production rather than counting it live (phase-2 census "
     "finding on the v1.5.0 tree; v1.4.1's register never saw this key).")
# -- CLI defaults -------------------------------------------------------------
_cfg("DEFAULT_TOP", 20, "Table rows shown by default.")
_cfg("DEFAULT_MIN_CONV", 0.0, "Hide rows below this conviction (table/csv).")
_cfg("DEFAULT_WATCHLIST", ("MU", "NVDA", "AAPL", "AMD", "META", "COST", "HD",
     "TSLA", "JPM", "GS", "UNH", "LLY", "XOM", "CVX", "CAT", "HON", "NEE",
     "LIN", "PLD", "AMT", "VZ", "TMUS"),
     "Default watchlist when no tickers are given: liquid names across all "
     "11 quality sectors (mega-caps resolve via quality's curated map).")
# -- terminal -----------------------------------------------------------------
_cfg("MIN_TERM_WIDTH", 40, "Terminal width floor. Phase 3 lowered this "
     "72 -> 40: --width 40 is a documented, gate-tested tier now (widths "
     "40/70/110) — the renderer drops columns at narrow widths instead of "
     "silently rendering 40 as 72. Display only; never a fusion input.")
_cfg("MAX_TERM_WIDTH", 160, "Terminal width ceiling. Phase 5 (C-3) raised "
     "110 -> 160: the owner's terminal runs at 96 cols and the tested tier "
     "ladder is 40/70/110/160; disclosed as a VALUE CHANGE in "
     "evidence/rules_changes.md (phase 8 CONFIG diff must verify it). "
     "Display only; never a fusion input.")
_cfg("BAR_COLS", 10, "Cells in a conviction/confidence bar.")
_cfg("STALE_STATUS_DAYS", 7, "Phase 5 (C-2) DISPLAY staleness threshold: a "
     "served source older than this shows yellow STALE + age in the report "
     "(e.g. macro > 7d), never a green OK. Display-only label — the "
     "FRESHNESS_* gates that actually gate logic/decisions are untouched "
     "and stay the pre-registered values; this key never feeds a decision.")
_cfg("CONF_DIGITS", {"conviction": 1, "score": 0, "mult": 3, "time": 1},
     "INTENDED render precision per quantity. NOT currently read: the "
     "renderer hardcodes its formats (conviction 1dp, score 0dp, mult 3dp, "
     "time 1dp — the same values, kept stable across --json). Kept as the "
     "register's honest statement of intent, disclosed not-read per v1.4.1 "
     "(B6); scripts/rules_register_check.py carries it as DISCLOSED.")


# ════════════════════════════════════════════════════════════════════════
#  § 2 · TYPES — dataclasses (slots) shared by every layer
# ════════════════════════════════════════════════════════════════════════
@dataclass(slots=True)
class MacroState:
    """Parsed L1 output (portfolio-level). regime is None while L1 is down."""
    status: str = "OK"                 # OK|DEGRADED|ERROR (engine or derived)
    scenario_key: str = ""
    scenario_name: str = ""
    regime_class: str = "neutral"      # risk_on|neutral|defensive
    cycle_phase: str = ""
    confidence: float = 0.0
    dominance: float = 0.0
    conviction_leverage: float = 1.0
    credit: str = ""                   # ON|OFF
    quality_tier: str = ""             # HIGH|MED|LOW (now() only)
    data_tier: str = ""                # api|public|cache|snapshot
    pit_mode: str = ""
    effective_as_of: str = ""          # floored month-end, always printed
    trade_month: str = ""              # next trade month
    longs: tuple[str, ...] = ()        # equity ETFs only (sleeve removed)
    shorts: tuple[str, ...] = ()
    sleeve: tuple[str, ...] = ()       # TLT/BIL/SGOV inside the basket longs
    warnings: tuple[str, ...] = ()
    excluded: tuple[str, ...] = ()     # scenarios excluded when credit OFF
    runner_up: str = ""
    source: str = ""                   # now|regime_now
    engine_version: str = ""

    @property
    def degraded_for_damp(self) -> bool:
        """True when the tilt EFFECT must be damped (DEGRADED or credit OFF)."""
        return self.status == "DEGRADED" or self.credit == "OFF"


@dataclass(slots=True)
class Candidate:
    """One input name; sector is resolved by L2 (or the --sector override)."""
    ticker: str
    sector_arg: str | None = None      # --sector T=<group>
    bucket: str | None = None          # --bucket T=staples|discretionary
    sector: str = ""                   # resolved group key / scoring pool
    macro_sector: str = ""             # macro vocabulary key (staples/discretionary stay separate: P2-9)


@dataclass(slots=True)
class LayerSignal:
    """One layer's verdict for one ticker (never a score when the engine
    returned none — honesty gate). Statuses: OK | DEGRADED | MISSING |
    MISSING_DATA | NOT_SELECTED | DISABLED | ERROR (P2-10: the earnings
    vocabulary is explicit about WHY there is no score)."""
    ticker: str
    layer: str
    score: float | None = None
    grade: str = "-"
    status: str = "OK"                 # OK|DEGRADED|MISSING|ERROR
    confidence: float = 1.0
    flags: tuple[str, ...] = ()
    facts: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    source: str = ""
    as_of: str = ""


@dataclass(slots=True)
class LayerResult:
    """One layer's outcome for the whole run."""
    name: str
    status: str = "OK"                 # OK|DEGRADED|ERROR
    stage: str = ""
    order: int = 0
    elapsed_s: float = 0.0
    cache: str = "n/a"                 # warm|cold|n/a
    signals: dict[str, LayerSignal] = field(default_factory=dict)
    ctx_out: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    engine_version: str = ""
    version_tested: str = ""


@dataclass(slots=True)
class Decision:
    """The fused verdict for one ticker. weight is filled by a sizer layer
    (L5-style); blocked marks a veto/gate AVOID overlays must never adjust.
    Phase 4 (P-6): conviction_raw is the UNROUNDED fused conviction — the
    value the LONG/WATCH doors compare under ruleset v2 (conviction stays
    the ROUNDED display value everywhere else)."""
    ticker: str
    sector: str
    action: str = "AVOID"              # LONG|WATCH|AVOID
    conviction: float = 0.0
    grade: str = "F"
    layers: dict[str, LayerSignal] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    weight: float | None = None
    blocked: str = ""                   # "" | "veto" | "gate" | "no quality score"
    conviction_raw: float | None = None  # phase 4: unrounded door value
    adv_checked: bool | None = None     # F9 (v1.8.3): None = sizer did not run


@dataclass(slots=True)
class Context:
    """Run context; layers READ ctx and write only their LayerResult.ctx_out."""
    as_of: str | None = None
    tickers: list[Candidate] = field(default_factory=list)
    regime: MacroState | None = None
    risk_budget: float = 1.0
    flags: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LayerProvenance:
    """Per-layer data provenance for ONE run (final phase, §2.1): where the
    data came from, how old the newest input actually used is, and the
    freshness verdict. source: cache | network | mixed | stub | none.
    status uses the existing vocabulary plus STALE (keeps data and score,
    shows age and reason — never silently OK). basis names WHERE data_as_of
    came from (engine output field or cache mtime).
    v1.8.2 (W3): refresh_failed records whether THIS run's refresh attempts
    for the layer failed (net-guard ledger evidence, online runs only) —
    the display then says STALE 'refresh failed' instead of a cadence
    judgement, and the JSON carries it (additive key)."""
    layer: str = ""
    source: str = "none"          # cache|network|mixed|stub|none
    data_as_of: str = ""          # YYYY-MM-DD ("" unknown)
    age_days: int | None = None
    status: str = "OK"            # OK|STALE|MISSING_DATA|ERROR|DISABLED|NOT_SELECTED
    reason: str = ""
    basis: str = ""
    refresh_failed: bool = False   # v1.8.2 (W3): fetch attempts failed this run

    def as_dict(self) -> dict[str, Any]:
        return {"source": self.source, "data_as_of": self.data_as_of,
                "age_days": self.age_days, "status": self.status,
                "reason": self.reason, "basis": self.basis,
                "refresh_failed": self.refresh_failed}


@dataclass(slots=True)
class RunOutput:
    """Everything one run produced (rendered once at the end)."""
    ctx: Context
    results: dict[str, LayerResult] = field(default_factory=dict)
    decisions: list[Decision] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    exit_code: int = 0
    exit_reason: str = ""
    stubbed: bool = False
    provenance: dict[str, LayerProvenance] = field(default_factory=dict)
    net_mode: str = ""                 # resolved: online|offline|"" (stubs/off)
    net_probe: str = ""                # "probe ok 140 ms" / "probe failed: ..."
    refresh: dict[str, Any] = field(default_factory=dict)  # §3.5 refresh report
    # v1.8.1 (N4): the FETCH HEALTH payload (additive JSON key; rendered
    # every run; None never — always at least the empty totals + note).
    fetch_health: dict[str, Any] = field(default_factory=dict)


# ════════════════════════════════════════════════════════════════════════
#  § 3 · ADAPTERS — shared helpers, Layer protocol, MacroLayer/QualityLayer/
#         EarningsLayer, LAYER_REGISTRY (L4 'ml' / L5 'risk' append later)
# ════════════════════════════════════════════════════════════════════════
# ── § 3.1 · small shared helpers ─────────────────────────────────────────
_TICKER_RE = re.compile(r"[A-Z0-9][A-Z0-9-]{0,11}\Z")
_REDACT_RE = re.compile(r"(api_key|token|apikey)=[^&\s'\"<>]+", re.I)
_SECRET_VARS = ("FREDAPI", "FRED_API_KEY", "FRED_API", "FRED_APIKEY",
                "SEC_USER_AGENT", "FINNHUB_API_KEY", "FINAPI")


def _redact(text: str) -> str:
    """Never print api_key/token values, SEC contacts or key material."""
    out = _REDACT_RE.sub(r"\1=***", str(text))
    for name in _SECRET_VARS:
        v = os.environ.get(name, "")
        if v and v in out:
            out = out.replace(v, "***")
    return out


def _norm_ticker(text: str) -> str | None:
    """Mirror of quality.normalize_ticker (BRK.B -> BRK-B); None if invalid."""
    cand = (text or "").strip().upper().replace(".", "-")
    return cand if _TICKER_RE.match(cand) else None


def _finite(x: Any, lo: float, hi: float) -> float | None:
    """Coerce to a float inside [lo, hi]; None for NaN/inf/non-numeric/
    out-of-range (phase-1 hardening: an invalid number becomes MISSING,
    never NaN — NaN compares False against every threshold and once reached
    fuse() it produced conviction 100 / grade A / LONG)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or not (lo <= v <= hi):          # v != v == NaN; range excludes inf
        return None
    return v


def _fin_int(x: Any, lo: int, hi: int, default: int = 0) -> int:
    """_finite for integer facts; default (0) when invalid — int(NaN) would
    raise and kill the whole layer."""
    v = _finite(x, float(lo), float(hi))
    return int(v) if v is not None else default


def month_end_floor(iso: str) -> str:
    """Floor to the last COMPLETED month end (mirrors meds._decision_month_end):
    mid-month -> previous month end; a date that IS a month end stays."""
    y, m, d = (int(x) for x in iso.split("-"))
    last = calendar.monthrange(y, m)[1]
    if d >= last:
        return f"{y:04d}-{m:02d}-{last:02d}"
    py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
    return f"{py:04d}-{pm:02d}-{calendar.monthrange(py, pm)[1]:02d}"


def _native_grade(bands_key: str, score: float | None) -> str:
    if score is None:
        return "-"
    for cut, letter in CONFIG[bands_key]:
        if float(score) >= cut:
            return letter
    return "F"


def _exc(e: BaseException) -> str:
    return _redact(f"{type(e).__name__}: {e}")[:200]


def _ctx_note(ctx: Context, msg: str) -> None:
    note = ctx.flags.get("note")
    if callable(note):
        note(msg)


def _dir_stamp(path: str) -> tuple[bool, float]:
    """(exists, newest mtime) of a cache dir — warm/cold detection.
    Walks the tree RECURSIVELY: engine caches write inside subdirectories
    (data/cache/prices_v2/T.csv), which never touch the parent's mtime."""
    try:
        newest = 0.0
        found = False
        for p in Path(path).rglob("*"):
            found = True
            try:
                if p.is_file():
                    newest = max(newest, p.stat().st_mtime)
            except OSError:
                pass
        return found, newest
    except OSError:
        return False, 0.0


def _touched(before: tuple[bool, float] | None, path: str) -> bool:
    if before is None or not before[0]:
        return True   # dir was absent before -> anything now means a write
    exists, newest = _dir_stamp(path)
    return (not exists and before[0]) or newest > before[1] + 1e-6 or (not exists)


def _cache_age_h(path: str) -> float | None:
    """Age in hours of the newest file under a cache dir; None when absent.
    Informational only ([plan] banner + --check), never a decision input."""
    exists, newest = _dir_stamp(path)
    if not exists or newest <= 0:
        return None
    return max(0.0, (time.time() - newest) / 3600.0)


def _offline_raiser(*_a: Any, **_k: Any) -> Any:
    """Adapter-only offline guard for earnings_engine: a cache miss becomes
    an honest error instead of a network call (instance attrs, never a file
    edit; cache file names are unchanged)."""
    raise RuntimeError("offline mode: cache miss, network disabled")


def _offline_transport(url: str, headers: dict | None = None,
                       timeout: float | None = None):
    """P2-2 (A4): offline guard for quality — swapped in as
    quality.default_transport for the duration of one --offline run (and
    restored afterwards). Every network attempt becomes the engine's OWN
    NETWORK_ERROR transport class, so quality's per-request diagnostics and
    cache fallbacks behave exactly as on a dead network: honest errors,
    disk caches still served, never invented data."""
    return "NETWORK_ERROR", None, None, "offline mode: network disabled by master"


# ── § 3.1b · net modes: probe, retry wrappers, meds snapshot (final phase) ─
def _net_probe(budget_s: float | None = None) -> tuple[bool, str]:
    """One DNS + TCP probe to PROBE_HOST (no payload, no request, no
    socket left open). Returns (reachable, note) — the note is the banner
    text ('probe ok 140 ms' / 'probe failed: <reason>'). Never raises;
    never called at import time; skipped entirely for --mode offline."""
    budget = float(budget_s if budget_s is not None else CONFIG["PROBE_BUDGET_S"])
    t0 = time.monotonic()
    try:
        import socket
        deadline = t0 + budget
        infos = socket.getaddrinfo(CONFIG["PROBE_HOST"], CONFIG["PROBE_PORT"],
                                   proto=socket.IPPROTO_TCP)
        if not infos:
            return False, "probe failed: no address resolved"
        left = max(0.05, deadline - time.monotonic())
        with socket.create_connection(infos[0][4], timeout=left):
            pass
        ms = (time.monotonic() - t0) * 1000.0
        return True, f"probe ok {ms:.0f} ms"
    except Exception as e:
        return False, f"probe failed: {_exc(e)[:90]}"


def _retry_sleep(attempt: int) -> float:
    """Backoff for retry N (1-based) with +-20% jitter (§3.3)."""
    base = CONFIG["RETRY_BACKOFF_S"][min(attempt - 1, len(CONFIG["RETRY_BACKOFF_S"]) - 1)]
    import random
    return base * (0.8 + 0.4 * random.random())


def _retrying_quality_transport(base: Callable[..., Any]) -> Callable[..., Any]:
    """§3.3: wrap quality's transport seam (default_transport) with per-
    request retries. Retries ONLY the engine's transient classes
    (NETWORK_ERROR, PROVIDER_ERROR); 4xx classes (AUTH_ERROR/NO_DATA/
    SCHEMA_ERROR) and RATE_LIMITED are returned immediately — 429 retry
    pacing is the ENGINE's own Retry-After logic, which a wrapper would
    only double. Failures after the last retry return the engine's own
    failure tuple, so quality's cache fallbacks see a normal dead request
    (a failed refresh can never be worse than offline)."""
    transient = {"NETWORK_ERROR", "PROVIDER_ERROR"}

    def transport(url: str, headers: dict | None = None,
                  timeout: float | None = None):
        result = None
        for attempt in range(1, int(CONFIG["RETRY_MAX_ATTEMPTS"]) + 1):
            result = base(url, headers=headers, timeout=timeout)
            status = result[0] if isinstance(result, tuple) and result else ""
            if status not in transient:
                return result
            if attempt < int(CONFIG["RETRY_MAX_ATTEMPTS"]):
                time.sleep(_retry_sleep(attempt))
        return result
    transport._master_retry = True        # idempotence marker (two runs, one process)
    return transport


def _retrying_fetch(fn: Callable[..., Any], label: str) -> Callable[..., Any]:
    """§3.3: wrap an earnings-engine provider callable (_fetch/_px_fetch)
    with the same retry policy. A urllib HTTPError with a 4xx code other
    than 429 is re-raised immediately (no retry); everything else retries
    up to RETRY_MAX_ATTEMPTS with backoff+jitter, then raises the engine's
    own exception (its cache/diagnostic paths take over from there)."""

    def fetch(*a: Any, **k: Any):
        last: Exception | None = None
        for attempt in range(1, int(CONFIG["RETRY_MAX_ATTEMPTS"]) + 1):
            try:
                return fn(*a, **k)
            except Exception as e:
                code = getattr(e, "code", None)
                if isinstance(code, int) and 400 <= code < 500 and code != 429:
                    raise                      # 4xx (not 429): stop retrying
                last = e
                if attempt < int(CONFIG["RETRY_MAX_ATTEMPTS"]):
                    time.sleep(_retry_sleep(attempt))
        raise last if last is not None else RuntimeError(f"{label}: fetch failed")
    fetch._master_retry = True
    return fetch


def _meds_snapshot_root() -> Path:
    """Master-owned materialised meds snapshot dir (next to master.py).
    WRITTEN only by online runs (cache maintenance, §3.5); READ only by
    offline runs (§2.6 — offline never writes)."""
    return Path(__file__).resolve().parent.parent / "meds_snapshot"


def _prepare_meds_snapshot(meds_mod: types.ModuleType) -> str | None:
    """OFFLINE (read-only): pick the snapshot dir meds will be pointed at —
    the master-materialised one when present, else meds' own repo snapshot
    when it exists, else None (macro degrades honestly to MISSING_DATA).
    Never writes, never fetches."""
    root = _meds_snapshot_root()
    if (root / "fred").is_dir() and any((root / "fred").glob("*.csv")):
        return str(root)
    own = getattr(meds_mod, "DATA_DIR", "data")
    mod_file = getattr(meds_mod, "__file__", None)      # fake modules: absent
    cands = [Path(own) / "snapshot", Path("snapshot")]
    if mod_file:
        cands.insert(0, Path(mod_file).resolve().parent / "snapshot")
    for cand in cands:
        if (cand / "fred").is_dir():
            return str(cand)
    return None


def _materialise_meds_snapshot(meds_mod: types.ModuleType,
                               dest: Path | None = None) -> tuple[int, str]:
    """ONLINE cache maintenance (§3.5): materialise meds' verified cache
    entries (fred/<SID>.csv bodies, read through meds' OWN hash-verified
    VerifiedCache.get) into the snapshot layout meds itself reads via
    MACRO_ENGINE_SNAPSHOT. Read-only on the engine side; writes only under
    master's own meds_snapshot/ dir. Returns (n_files, note). No network,
    no engine file edits (H1)."""
    dest = dest or _meds_snapshot_root()
    vc = getattr(meds_mod, "VerifiedCache", None)
    if vc is None:
        return 0, "meds exposes no VerifiedCache — snapshot not materialised"
    try:
        payload = vc()._load_all()          # engine's own SHA-256-verified load
    except Exception as e:
        return 0, f"meds cache unreadable ({_exc(e)[:80]}) — snapshot not materialised"
    names = [n for n in payload if isinstance(n, str)
             and n.startswith("fred/") and n.endswith(".csv")]
    if not names:
        return 0, "meds verified cache has no fred/*.csv entries (run online once with MEDS_CACHE=1)"
    fred_dir = dest / "fred"
    fred_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for name in names:
        got = vc().get(name, max_age_days=None)   # age-agnostic: last cached truth
        if got is None:
            continue
        body, _meta = got
        try:
            # B8 (phase-2 port): atomic per-file write — a crash mid-write
            # leaves the PREVIOUS cached truth intact, never a truncated CSV.
            _atomic_write_bytes(fred_dir / name.split("/", 1)[1], body)
            written += 1
        except OSError:
            pass
    if not written:
        return 0, "no fred entries could be written — snapshot not materialised"
    return written, (f"materialised {written} FRED series into {dest.name}/ "
                     f"(offline macro = last cached truth, age-labelled)")


def _offline_yfinance_reason() -> str:
    return ("offline mode: master disabled the yfinance price path "
            "(socket-free guarantee, §2.4) — quality's own chart client + "
            "the blocked transport serve caches and fail honestly")


class _SysModuleBlock:
    """P2-3 pattern for sys.modules: make ONE import raise ImportError for
    THIS run (offline: yfinance must look ABSENT — meds and quality both
    call it directly and it owns its sockets), restored afterwards."""

    def __init__(self, name: str, why: str) -> None:
        self.name, self.why = name, why
        self.prev = sys.modules.get(name, _MISSING_SENTINEL)
        sys.modules[name] = None               # None => ImportError on import

    def undo(self) -> None:
        if self.prev is _MISSING_SENTINEL:
            sys.modules.pop(self.name, None)
        else:
            sys.modules[self.name] = self.prev


_MISSING_SENTINEL = object()


class _EnvRestore:
    """P2-3: set one env var for THIS run; undo restores the previous value
    (two runs in one process must not leak state)."""

    def __init__(self, name: str, value: str) -> None:
        self.name = name
        self.prev = os.environ.get(name)
        self.had = name in os.environ
        os.environ[name] = value

    def undo(self) -> None:
        if self.had:
            os.environ[self.name] = self.prev            # type: ignore[index]
        else:
            os.environ.pop(self.name, None)


class _AttrRestore:
    """P2-3: set one module attribute for THIS run (meds.FORCE_SNAPSHOT,
    quality.default_transport, quality.*_DIR) and restore it afterwards —
    the adapter pattern the engines themselves sanction; never a file edit."""

    def __init__(self, mod: types.ModuleType, attr: str, value: Any) -> None:
        self.mod, self.attr = mod, attr
        self.prev = getattr(mod, attr, None)
        self.had = hasattr(mod, attr)
        setattr(mod, attr, value)

    def undo(self) -> None:
        if self.had:
            setattr(self.mod, self.attr, self.prev)
        else:
            try:
                delattr(self.mod, self.attr)
            except AttributeError:
                pass


class _CfgKeyRestore:
    """Phase 4 (P-1, P2-3 pattern): set ONE CONFIG key for THIS run (the
    CLI's --ruleset override) and restore the shipped value afterwards —
    two runs in one process never leak the override into each other."""

    def __init__(self, key: str, value: Any) -> None:
        self.key = key
        self.prev = CONFIG.get(key)
        self.had = key in CONFIG
        CONFIG[key] = value

    def undo(self) -> None:
        if self.had:
            CONFIG[self.key] = self.prev
        else:
            CONFIG.pop(self.key, None)


def _restore_all(restores: list) -> None:
    """Undo guards in reverse order (run_pipeline's finally hook)."""
    for g in reversed(restores):
        try:
            g.undo()
        except Exception:
            pass


class _Progress:
    """ONE in-place stderr line per running layer; silent when stderr is not
    a TTY or --quiet is set (same technique as quality.score_main).
    v1.1.0: kill(owner) silences one layer's callback forever (a timed-out
    layer's stuck thread must not keep painting over the next layer's line
    or leak a stray counter after the table prints); stop() silences all.
    v1.8.0 (W3): optional label/total give the line an ETA (elapsed *
    remaining/done) and out= lets tests capture it without a TTY."""

    def __init__(self, quiet: bool = False, *, label: str = "",
                 total: int = 0, out: Any = None,
                 now: Any = None) -> None:
        self.off = bool(quiet) or (out is None and not sys.stderr.isatty())
        self._last = 0
        self._dead: set[str] = set()
        self._label = str(label)
        self._total = int(total)
        self._done = 0
        self._out = out
        self._now = now or time.monotonic
        self._t0 = self._now()

    def alive(self, owner: str) -> bool:
        """False once kill(owner) — checked inside each layer's callback."""
        return owner not in self._dead

    def kill(self, owner: str) -> None:
        self._dead.add(owner)
        self.clear()

    def stop(self) -> None:
        """Permanent silence (called once the pipeline result is final)."""
        self.off = True
        self.clear()

    def tick(self, n: int = 1, *, now: Any = None) -> None:
        """Advance the counter by n and repaint with ETA when a total is
        known (ETA = elapsed * (total-done)/done; none before the first
        tick — no division by zero, no invented rate)."""
        self._done += int(n)
        t = (now or self._now)()
        elapsed = max(t - self._t0, 0.0)
        line = (f"{self._label}: {self._done}/{self._total} · "
                f"{elapsed:.0f}s" if self._label else None)
        if line:
            if self._total > 0 and self._done > 0:
                line += (f" · ETA "
                         f"{elapsed * (self._total - self._done) / self._done:.0f}s")
            self.set(line)

    def set(self, text: str) -> None:
        if self.off or not text:
            return
        sink = self._out if self._out is not None else sys.stderr
        sink.write("\r" + text + " " * max(self._last - len(text), 0))
        if self._out is None:
            sys.stderr.flush()
        self._last = len(text)

    def clear(self) -> None:
        if self.off or self._last == 0:
            return
        sink = self._out if self._out is not None else sys.stderr
        sink.write("\r" + " " * self._last + "\r")
        if self._out is None:
            sys.stderr.flush()
        self._last = 0


def _resume_hint(phase: str) -> str:
    """v1.8.0 (W3): the one-line resume hint printed with the Ctrl-C exit
    (130) — caches keep every completed unit of work, offline serves what
    is warm, --warm fills the rest."""
    return (f"resume: rerun the same command (phase '{phase}' keeps its "
            "finished work in the caches) — add --mode offline to serve "
            "what is warm now, or --warm to fill the rest first")


def _engine_version(name: str, mod: types.ModuleType) -> tuple[str, str, bool]:
    """(shown, tested, differs) for an imported engine module."""
    tested = CONFIG["TESTED_VERSIONS"][name]
    got = str(getattr(mod, CONFIG["ENGINE_VERSION_ATTRS"].get(name, "__version__"), "") or "")
    if not got:
        got = tested    # engine exposes no version; drift is undetectable
    return got, tested, got != tested


_BUCKET_ETF = {"staples": "XLP", "discretionary": "XLY"}


def macro_tilt(state: MacroState | None, sector: str) -> float | None:
    """+1/+0.5 when a mapped ETF is long (weak mappings halved); -0.5 when
    defensive AND cyclical AND not long-aligned; 0 otherwise; None =
    macro-silent (no ETF vocabulary for the sector, or the layer is down /
    has no scenario) — healthcare/financials/reits/specialty are always
    silent (trap 3). P2-9: --bucket pools get their own ETF (XLP/XLY)."""
    if state is None or state.status == "ERROR" or not sector \
            or not state.scenario_key:      # P2-8: no scenario -> no context
        return None
    if sector in _BUCKET_ETF:               # P2-9: bucket granularity
        etf = _BUCKET_ETF[sector]
        if etf in set(state.longs):
            return 1.0
        if state.regime_class == "defensive" and sector == "discretionary":
            return -0.5
        return 0.0
    mapped: dict[str, float] = {}
    for etf, pairs in CONFIG["ETF_TO_SECTORS"].items():
        strengths = [s for sec, s in pairs if sec == sector]
        if strengths:
            mapped[etf] = max(strengths)
    if not mapped:
        return None
    longs = set(state.longs)
    hits = [s for etf, s in mapped.items() if etf in longs]
    if hits:
        return max(hits)
    if state.regime_class == "defensive" and sector in CONFIG["CYCLICAL_SECTORS"]:
        return -0.5
    return 0.0


def macro_view(state: MacroState | None, sector: str) -> dict[str, Any]:
    """{tilt, damp, mult, mapped} for one sector (fusion + render + json)."""
    tilt = macro_tilt(state, sector)
    if tilt is None:
        return {"tilt": None, "damp": 1.0, "mult": 1.0, "mapped": ""}
    damp = (CONFIG["MACRO_DEGRADED_DAMP"] if state is not None and state.degraded_for_damp
            else 1.0)
    mapped = ""
    if sector in _BUCKET_ETF:               # P2-9: name the bucket's own ETF
        etf = _BUCKET_ETF[sector]
        if etf in set(state.longs or ()):   # type: ignore[union-attr]
            mapped = f"{etf}(bucket)"
    if not mapped:
        mapped = ", ".join(
            f"{etf}({'strong' if s >= 1.0 else 'weak'})"
            for etf, pairs in CONFIG["ETF_TO_SECTORS"].items()
            for sec, s in pairs if sec == sector and etf in set(state.longs or ()))  # type: ignore[union-attr]
    if not mapped and tilt < 0:
        mapped = "defensive regime"
    return {"tilt": tilt, "damp": damp,
            "mult": round(1.0 + CONFIG["MACRO_TILT_GAIN"] * tilt * damp, 4),
            "mapped": mapped}


def _macro_signal(ticker: str, state: MacroState | None, mv: dict) -> LayerSignal:
    t = mv["tilt"]
    grade = "-" if t is None else (f"{t:+.1f}" if t else "0.0")
    status = "ERROR" if (state is None or state.status == "ERROR") else state.status
    return LayerSignal(
        ticker=ticker, layer="macro", score=None, grade=grade, status=status,
        facts={"tilt": t, "damp": mv["damp"], "mult": mv["mult"], "mapped": mv["mapped"],
               "scenario": state.scenario_key if state else "",
               "class": state.regime_class if state else ""},
        source="meds", as_of=(state.effective_as_of if state else ""))


def _ruleset() -> str:
    """The ACTIVE ruleset (phase 4): one read-point so fuse, funnel,
    overlay and explain agree, and tests/fuzz can flip it in one place."""
    return str(CONFIG["RULESET"])


def _missing_fill() -> float | None:
    """ruleset v2's fixed conservative missing-E value (E_MISSING_V2);
    None under legacy (the x0.90 haircut path applies instead)."""
    return (float(CONFIG["E_MISSING_V2"]) if _ruleset() == "v2" else None)


def _door_value(d: Decision) -> float:
    """The conviction the action doors compare (phase 4, P-6): the
    UNROUNDED fused value under ruleset v2, the rounded display value
    under legacy (the shipped behaviour, byte-for-byte)."""
    if _ruleset() == "v2" and d.conviction_raw is not None:
        return d.conviction_raw
    return d.conviction


def _base_conviction(q: float, e: float | None, weak: bool) -> float:
    """§4.3 base before the macro multiplier."""
    fill = _missing_fill()
    if e is None and fill is not None:
        # P-1 (phase 4) + F3 (v1.8.3): ruleset v2 scores a missing E as
        # the FIXED conservative fill on the UN-renormalised weights — the
        # weak renormalisation exists to discount OBSERVED earnings on a
        # weak tape, not to lift unscored names (Q80: 52 WATCH, never
        # 63 LONG). base(missing) is WEAK-invariant and still <= base(any
        # observed E >= 0) for every verdict (equality at E=0 preserved:
        # the un-renormalised 52.00 <= the renormalised 63.03).
        return CONFIG["W_Q"] * q + CONFIG["W_E"] * fill
    if e is None:
        return q * CONFIG["E_MISSING_HAIRCUT"]
    if not weak:
        return CONFIG["W_Q"] * q + CONFIG["W_E"] * e
    we = CONFIG["W_E"] * CONFIG["EARNINGS_WEAK_SCALE"]
    return (CONFIG["W_Q"] * q + we * e) / (CONFIG["W_Q"] + we)


_CSV_DANGER = ("=", "+", "-", "@")


def _csv_safe(cell: Any) -> Any:
    """P1-5: neutralise spreadsheet formula injection — a STRING cell that
    starts with = + - @ gets a leading apostrophe (OWASP guidance); numeric
    cells pass through untouched so -0.5 stays a number."""
    if isinstance(cell, str) and cell[:1] in _CSV_DANGER:
        return "'" + cell
    return cell


def _atomic_write_text(path: "Path | str", text: str) -> None:
    """B8 (v1.4.1 port + the phase-2 fsync extension): write temp + fsync +
    rename so a crash mid-write leaves the PREVIOUS file intact and never a
    truncated artifact that a later run would load as garbage. The temp
    file is removed on failure. Used for the freeze manifest and any other
    text artifact master writes."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _atomic_write_bytes(path: "Path | str", data: bytes) -> None:
    """B8: the binary twin of _atomic_write_text (meds snapshot CSVs):
    write temp + fsync + rename; a crash leaves the previous truth intact."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _engines_sha256() -> dict[str, str]:
    """Current sha256 of the three engine files (H1: they are never edited
    by master; the values ship in ENGINES.sha256)."""
    import hashlib
    out: dict[str, str] = {}
    here = Path(__file__).resolve().parent.parent   # project root (me/)
    for name, fn in (("meds", "meds.py"), ("quality", "quality.py"),
                     ("earnings", "earnings_engine.py")):
        p = here / fn
        try:
            out[name] = hashlib.sha256(p.read_bytes()).hexdigest()
        except OSError:
            out[name] = ""
    return out


