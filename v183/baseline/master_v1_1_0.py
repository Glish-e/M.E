"""
master.py — layered equity research screener (orchestrator), v1.1.0
===================================================================
WHAT IT IS
  One single-file orchestration engine that runs three EXISTING engines in a
  fixed order and fuses them into ONE ranked, explainable decision table in
  the terminal:

    L1 macro    meds.py            regime / risk / favoured sectors      monthly
    L2 quality  quality.py         which companies are worth owning      quarterly
    L3 earnings earnings_engine.py big EPS beats + fresh catalyst        event
    L4 AI/ML    reserved (stage "overlay")   — not built, plugs in later
    L5 risk     reserved (stage "sizer")     — not built, plugs in later

  Fusion is rule-based and fully explainable: hard quality gate -> conviction
  (0.65*Q + 0.35*E, haircuts when E is missing/weak) -> macro tilt multiplier
  -> action LONG / WATCH / AVOID with per-ticker reasons. Output is a RESEARCH
  SCREENER, never investment advice and never an alpha claim.

LAZY ENGINES
  `import master` has no side effects. Engines are imported by module name
  from the SAME FOLDER, lazily inside each adapter, only when that layer is
  selected: `--only quality` never imports the other two. Never edit the
  engine files — adapters only.

SETUP
  Python >= 3.10, stdlib + pandas + numpy (the engines need them anyway).
  Put master.py next to meds.py / quality.py / earnings_engine.py.
  Keys (optional): FREDAPI (or FRED_API_KEY) in env or .env next to meds.py;
  SEC_USER_AGENT recommended; FINNHUB_API_KEY optional (free key auto-off).
  Caches live where each engine puts them (meds: meds_cache/ next to meds.py;
  quality: data/ under the working dir; earnings: ~/.earnings_engine_cache);
  `--cache-dir DIR` redirects quality + earnings (meds is fixed).

RUN MODES (v1.1.0) — pick the run you have time for
  --mode quick      minutes even on a cold cache: quality ranks are computed
                    over the watchlist itself (--peers watchlist), L3 funnel
                    top-10, 300s/layer budget. Rough percentiles, by design.
  --mode standard   (default) honest sector-pool ranks; minutes once caches
                    are warm; the FIRST cold pass scores the whole universe
                    (~643 names, 10-25 min) — see the [plan] banner it prints.
  --mode deep       the long run: 3600s/layer, L3 top-40 + history prefetch.
  --warm            cache maintenance: macro+quality only, long budget, fills
                    the disk caches so the next standard run is fast.
  Any explicit flag (--timeout/--peers/--earnings-top/--earnings-prefetch)
  overrides its mode preset.

EIGHT MOST USEFUL COMMANDS
  python master.py --mode quick                   fast pass, cold-cache safe
  python master.py                                standard run (warm: minutes)
  python master.py --warm                         day-0 cache fill, then rerun
  python master.py MU NVDA AAPL AMD META          score five names
  python master.py --explain MU                   full per-layer breakdown
  python master.py --as-of 2026-06-30 --json      point-in-time run, machine output
  python master.py --check                        health probe (versions/env/probes)
  python master.py --selftest                     stubbed tests, no network

EXIT CODES (same convention as meds.py)
  0 ok (DEGRADED included) · 1 unexpected · 2 no result / NO-GO (one line)
  64 bad usage (before any network call) · 130 Ctrl-C (names the phase).

NOTES
  --offline forces the macro snapshot (meds.FORCE_SNAPSHOT) and disables
  network in the earnings adapter (cache-miss becomes an honest error);
  quality serves from its caches when warm. stdout = results only;
  progress/warnings go to stderr. The default run writes NOTHING to disk
  (only --csv, and the engines' own caches, ever write).

SELFTEST
  `--selftest` runs stdlib unittest with stub adapters; live checks print
  LIVE SKIP and never fake data. Env MASTER_STUBS=1 swaps the three real
  adapters for deterministic stub layers (used by the selftest's end-to-end
  cases; handy for hacking on the render/CLI without any engine or network).

RESERVED (do not implement yet)
  L4 "ml"    : Layer with stage="overlay"; adds LayerSignal("ml", ...) and a
               bounded conviction_adj; must declare its features' as-of date.
  L5 "risk"  : Layer with stage="sizer"; reads Decision list + ctx.risk_budget,
               fills Decision.weight, may veto; adds portfolio footer lines.
  A --layers registry flag makes extra layers appear in the header/--json.

CHANGELOG v1.1.0
  Run modes (--mode quick|standard|deep) + --warm cache-fill run; a [plan]
  stderr banner printed BEFORE any layer runs (exact quality pool size, cache
  ages, cold-pass ETA and the faster alternative — the first cold run no
  longer looks "stuck"); mode-driven defaults for --timeout/--peers/
  --earnings-top/--earnings-prefetch (explicit flags still win); timed-out
  layer progress lines are silenced instead of leaking after the table;
  the NO-GO exit reason now names the ERROR layer's real cause (timeout),
  not the cosmetic earnings-version note; cache warm/cold detection walks
  the cache tree recursively (inner writes were invisible before); quality
  universe refs are built once and reused (plan banner + prefetch).
CHANGELOG v1.0.0
  Initial: 3 adapters, rule fusion, funnel (1 macro -> N quality -> top-K
  earnings), parallel prefetch, honesty gates (DEGRADED/credit OFF/stale
  never hidden), no-lookahead as-of plumbing, ASCII/colour render, --json
  stable schema, --csv opt-in, --check, --selftest with stubs.
"""
from __future__ import annotations

# ════════════════════════════════════════════════════════════════════════
#  § 0 · IMPORTS + VERSION (stdlib only; pandas/numpy come with the engines)
# ════════════════════════════════════════════════════════════════════════
import argparse
import calendar
import importlib
import json
import os
import re
import shutil
import sys
import time
import types
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Protocol

__version__ = "1.1.0"
__all__ = ["LAYERS", "LAYER_REGISTRY", "Context", "Candidate", "LayerSignal",
           "LayerResult", "Decision", "MacroState", "fuse", "run_pipeline",
           "main"]


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
     "Sectors that suffer most in a defensive regime (tilt -0.5).")
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
     "earnings_engine's _rating bands — shown only on the earnings layer.")
# -- actions ----------------------------------------------------------------
_cfg("ACTION_LONG_AT", 60.0, "Conviction needed for LONG.")
_cfg("ACTION_WATCH_AT", 45.0, "Conviction needed for WATCH.")
_cfg("MAX_REASONS", 5, "Short reason strings carried per decision.")
_cfg("RISK_CAP_DEGRADED", 1.0, "risk_budget cap when macro is DEGRADED, "
     "credit OFF or quality LOW; exported for the future sizer, not applied.")
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
     "saves most Yahoo calls and avoids 429s.")
_cfg("EARNINGS_PLAN_MIN", 50.0, "eng.plan min_score (the engine's tested rule).")
_cfg("EARNINGS_HOLD_DAYS", 90, "eng.plan hold window (swing/position horizon).")
_cfg("EARNINGS_TP", 0.15, "eng.plan take-profit.")
_cfg("EARNINGS_MAX_AGE", 10, "NOW chip needs a report <= 10 days old.")
_cfg("EARNINGS_QUARTERS", 40, "EarningsEngine history depth (~10y).")
# -- orchestration -----------------------------------------------------------
_cfg("DEFAULT_WORKERS", 4, "Earnings pool size; keep <= 4 to share Yahoo "
     "politely with quality/meds (a warning is printed above that).")
_cfg("LAYER_TIMEOUT_S", 900, "STANDARD-mode per-layer wall-clock budget "
     "(prefetch + run); --mode quick/deep use their own presets.")
_cfg("MODES", {
    "quick": {"timeout": 300.0, "peers": "watchlist", "earnings_top": 10,
              "earnings_prefetch": "none"},
    "standard": {"timeout": 900.0, "peers": "builtin", "earnings_top": 25,
                 "earnings_prefetch": "none"},
    "deep": {"timeout": 3600.0, "peers": "builtin", "earnings_top": 40,
             "earnings_prefetch": "all"},
}, "Run presets: what each --mode sets unless the user passes the flag "
   "explicitly. quick trades exact sector ranks for a small comparison pool "
   "(the watchlist itself); standard keeps honest sector pools; deep is the "
   "long research pass. standard mirrors the v1.0.0 defaults exactly.")
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
_cfg("PREFETCH_ALL_MAX", 60, "--earnings-prefetch all is honoured only when "
     "the watchlist is <= this many names.")
_cfg("PROBE_TIMEOUT_S", 6.0, "--check per-source probe timeout.")
# -- CLI defaults -------------------------------------------------------------
_cfg("DEFAULT_TOP", 20, "Table rows shown by default.")
_cfg("DEFAULT_MIN_CONV", 0.0, "Hide rows below this conviction (table/csv).")
_cfg("DEFAULT_WATCHLIST", ("MU", "NVDA", "AAPL", "AMD", "META", "COST", "HD",
     "TSLA", "JPM", "GS", "UNH", "LLY", "XOM", "CVX", "CAT", "HON", "NEE",
     "LIN", "PLD", "AMT", "VZ", "TMUS"),
     "Default watchlist when no tickers are given: liquid names across all "
     "11 quality sectors (mega-caps resolve via quality's curated map).")
# -- terminal -----------------------------------------------------------------
_cfg("MIN_TERM_WIDTH", 72, "Terminal width floor.")
_cfg("MAX_TERM_WIDTH", 110, "Terminal width ceiling.")
_cfg("BAR_COLS", 10, "Cells in a conviction/confidence bar.")
_cfg("CONF_DIGITS", {"conviction": 1, "score": 0, "mult": 3, "time": 1},
     "Render precision per quantity (stable across --json).")


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
    macro_sector: str = ""             # macro vocabulary key (bucket -> consumer)


@dataclass(slots=True)
class LayerSignal:
    """One layer's verdict for one ticker (never a score when the engine
    returned none — honesty gate)."""
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
    """The fused verdict for one ticker. weight stays None until L5 exists."""
    ticker: str
    sector: str
    action: str = "AVOID"              # LONG|WATCH|AVOID
    conviction: float = 0.0
    grade: str = "F"
    layers: dict[str, LayerSignal] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    weight: float | None = None


@dataclass(slots=True)
class Context:
    """Run context; layers READ ctx and write only their LayerResult.ctx_out."""
    as_of: str | None = None
    tickers: list[Candidate] = field(default_factory=list)
    regime: MacroState | None = None
    risk_budget: float = 1.0
    flags: dict[str, Any] = field(default_factory=dict)


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


class _Progress:
    """ONE in-place stderr line per running layer; silent when stderr is not
    a TTY or --quiet is set (same technique as quality.score_main).
    v1.1.0: kill(owner) silences one layer's callback forever (a timed-out
    layer's stuck thread must not keep painting over the next layer's line
    or leak a stray counter after the table prints); stop() silences all."""

    def __init__(self, quiet: bool = False) -> None:
        self.off = bool(quiet) or not sys.stderr.isatty()
        self._last = 0
        self._dead: set[str] = set()

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

    def set(self, text: str) -> None:
        if self.off or not text:
            return
        sys.stderr.write("\r" + text + " " * max(self._last - len(text), 0))
        sys.stderr.flush()
        self._last = len(text)

    def clear(self) -> None:
        if self.off or self._last == 0:
            return
        sys.stderr.write("\r" + " " * self._last + "\r")
        sys.stderr.flush()
        self._last = 0


def _engine_version(name: str, mod: types.ModuleType) -> tuple[str, str, bool]:
    """(shown, tested, differs) for an imported engine module."""
    tested = CONFIG["TESTED_VERSIONS"][name]
    got = str(getattr(mod, CONFIG["ENGINE_VERSION_ATTRS"].get(name, "__version__"), "") or "")
    if not got:
        got = tested    # engine exposes no version; drift is undetectable
    return got, tested, got != tested


# ── § 3.2 · Layer protocol + base class ──────────────────────────────────
class Layer(Protocol):
    name: str            # "macro" | "quality" | "earnings" | later "ml"/"risk"
    order: int
    stage: str           # "gate" | "score" | "overlay" | "sizer"
    def prefetch(self, ctx: Context) -> None: ...
    def run(self, ctx: Context, cands: list[Candidate]) -> LayerResult: ...


class LayerBase:
    """Partial-result salvage: run() stashes its LayerResult early and mutates
    it as tickers complete, so a per-layer timeout keeps partial results."""
    name: str = "?"
    order: int = 0
    stage: str = "score"

    def __init__(self) -> None:
        self._partial: LayerResult | None = None

    def prefetch(self, ctx: Context) -> None:      # optional, worker thread
        return None

    def _begin(self, engine_version: str = "", version_tested: str = "") -> LayerResult:
        res = LayerResult(name=self.name, stage=self.stage, order=self.order,
                          engine_version=engine_version, version_tested=version_tested)
        self._partial = res
        return res

    def _salvage(self, note: str) -> LayerResult:
        res = self._partial or LayerResult(name=self.name, stage=self.stage,
                                           order=self.order, status="ERROR")
        res.status = "ERROR"
        res.warnings = tuple(dict.fromkeys((*res.warnings, _redact(note)[:200])))
        return res


# ── § 3.3 · MacroLayer (L1, meds) ────────────────────────────────────────
_PAREN_RE = re.compile(r"\(([^()]+)\)\s*\Z")
_PLAIN_ETF_RE = re.compile(r"[A-Z0-9^=\-]{1,10}\Z")


def _etf_of(label: str) -> str:
    """'Energy (XLE)' -> XLE; 'S&P 500 (SPY)' -> SPY; bare labels pass through."""
    m = _PAREN_RE.search(label or "")
    if m:
        return m.group(1).strip().upper()
    t = (label or "").strip().upper()
    return t if _PLAIN_ETF_RE.match(t) else ""


def _parse_macro(raw: dict, source: str, version: str) -> MacroState:
    """now()/regime_now() dict -> MacroState (never raises)."""
    if raw.get("error") is not None:
        st = MacroState(status="ERROR", source=source, engine_version=version)
        st.warnings = (_redact(str(raw.get("error")))[:200],)
        return st
    st = MacroState(source=source, engine_version=version)
    st.scenario_key = str(raw.get("scenario_key") or "")
    st.scenario_name = str(raw.get("name") or "")
    st.cycle_phase = str(raw.get("cycle_phase") or "")
    st.confidence = float(raw.get("confidence") or 0.0)
    st.dominance = float(raw.get("dominance") or 0.0)
    st.conviction_leverage = float(raw.get("conviction_leverage") or 1.0)
    st.data_tier = str(raw.get("data_tier") or "")
    st.pit_mode = str(raw.get("pit_mode") or "")
    st.effective_as_of = str(raw.get("as_of") or "")
    st.trade_month = str(raw.get("month") or raw.get("next_trade_month") or "")
    st.credit = str(raw.get("credit") or ("OFF" if raw.get("credit_signal") == "OFF" else "ON"))
    st.quality_tier = str(raw.get("quality") or "")
    st.warnings = tuple(_redact(str(w))[:160] for w in (raw.get("warnings") or ()))
    st.excluded = tuple(raw.get("excluded_scenarios") or ())
    st.runner_up = str(raw.get("runner_up") or "")
    basket = raw.get("basket") or {}
    longs = tuple(x for x in (_etf_of(l) for l in basket.get("longs", [])) if x)
    shorts = tuple(x for x in (_etf_of(l) for l in basket.get("shorts", [])) if x)
    sleeve = CONFIG["SLEEVE_ETFS"]
    st.sleeve = tuple(x for x in longs if x in sleeve)      # rates/cash held LONG
    st.longs = tuple(x for x in longs if x not in sleeve)
    st.shorts = shorts          # an active short (TLT) is a rates bet, never the sleeve
    st.status = str(raw.get("status") or ("DEGRADED" if (st.credit == "OFF"
                  or st.warnings or raw.get("errors")) else "OK"))
    if raw.get("regime_class"):
        st.regime_class = str(raw["regime_class"])
    elif st.scenario_key in CONFIG["DEFENSIVE_SCENARIOS"]:
        st.regime_class = "defensive"
    elif st.scenario_key == CONFIG["NEUTRAL_KEY"]:
        st.regime_class = "neutral"
    else:
        st.regime_class = "risk_on"
    if st.credit == "OFF" and not st.excluded:
        st.excluded = ("CREDIT_CRUNCH", "EARLY_CYCLE_RE_ACCELERATION")
    return st


def _risk_budget(state: MacroState) -> float:
    """Exported for the future L5 sizer (not applied to any sizing now)."""
    if state.status == "ERROR":
        return 1.0
    lev = float(state.conviction_leverage or 1.0)
    if state.degraded_for_damp or state.quality_tier == "LOW":
        return min(lev, CONFIG["RISK_CAP_DEGRADED"])
    return min(lev, 2.0)


class MacroLayer(LayerBase):
    """L1 regime gate. meds is called ONCE per run, on one dedicated thread,
    never concurrently (the engine is not thread-safe)."""
    name = "macro"
    order = 1
    stage = "gate"

    def __init__(self) -> None:
        super().__init__()
        self._raw: dict | None = None
        self._source = "now"
        self._mod: types.ModuleType | None = None

    def prefetch(self, ctx: Context) -> None:
        import meds                                   # lazy; macro only
        self._mod = meds
        if ctx.flags.get("offline"):
            meds.FORCE_SNAPSHOT = True                # module attr, never a file edit
        try:
            self._raw = (meds.now() if ctx.as_of is None
                         else meds.regime_now(as_of=ctx.as_of))
            self._source = "now" if ctx.as_of is None else "regime_now"
        except Exception as e:                        # adapter boundary
            self._raw = {"error": _exc(e)}

    def run(self, ctx: Context, cands: list[Candidate]) -> LayerResult:
        ver, tested, differs = _engine_version("meds", self._mod or types.ModuleType("meds"))
        res = self._begin(ver, tested)
        state = _parse_macro(self._raw or {}, self._source, ver)
        res.status = state.status
        res.warnings = state.warnings
        res.cache = {"api": "cold", "public": "cold", "cache": "warm"}.get(state.data_tier, "n/a")
        res.ctx_out = {"macro": state, "risk_budget": _risk_budget(state)}
        if differs:
            res.warnings = (*res.warnings, f"meds v{ver} != tested v{tested}")
        return res


# ── § 3.4 · QualityLayer (L2, quality) ───────────────────────────────────
def _quality_signal(cand: Candidate, r: dict) -> LayerSignal:
    """quality result dict -> LayerSignal (score only when the engine said OK)."""
    word = str(r.get("status") or "ERROR")
    score = r.get("score")
    ok = word == "OK" and isinstance(score, (int, float))
    pool = str(r.get("sector") or "")
    flags = tuple(str(f) for f in (r.get("flags") or ()))
    metrics = r.get("metrics") or {}
    notes = [str(n) for n in (r.get("notes") or [])[:4]]
    facts: dict[str, Any] = {
        "engine_status": word, "sector": pool,
        "macro_sector": "consumer" if pool in ("staples", "discretionary") else pool,
        "rank": r.get("rank_in_sector"), "coverage": r.get("coverage"),
        "pillars": dict(r.get("pillars") or {}),
        "data_source": str(r.get("data_source") or ""), "model": str(r.get("model") or ""),
        "metrics_top": {k: round(float(metrics[k]), 2) for k in CONFIG["EXPLAIN_METRICS"]
                        if isinstance(metrics.get(k), (int, float))},
        "notes": notes,
        "pool_size": r.get("_pool_size"),
    }
    return LayerSignal(
        ticker=cand.ticker, layer="quality",
        score=(round(float(score), 1) if ok else None),
        grade=(_native_grade("QUALITY_NATIVE_GRADES", score) if ok else "-"),
        status={"OK": "OK", "ERROR": "ERROR"}.get(word, "MISSING"),
        flags=flags, facts=facts,
        warnings=tuple(flags) + tuple(notes[:2]),
        source=str(r.get("data_source") or "")[:40],
        as_of=str(r.get("as_of") or ""))


class QualityLayer(LayerBase):
    """L2 selector. ONE shared universe_refs list (the identical object for
    every call): the first get_quality_score scores the whole universe, the
    rest are the engine's in-process memo hits."""
    name = "quality"
    order = 2
    stage = "score"

    def __init__(self) -> None:
        super().__init__()
        self._refs: list | None = None
        self._refs_built: bool = False
        self._refs_warnings: list[str] = []
        self._stamp: tuple[bool, float] | None = None
        self._pinned: dict[str, str] = {}
        self._cache_dir = ""

    # -- universe -------------------------------------------------------- #
    def peek_refs(self, ctx: Context) -> list | None:
        """Build the universe refs ONCE, early — the [plan] banner needs the
        exact pool size before any layer starts, and prefetch reuses the same
        list (no double build). None when the engine/universe is unavailable;
        prefetch then surfaces the real error."""
        if not self._refs_built:
            try:
                self._refs = self._build_refs(ctx)
            except Exception as e:                 # engine import failure etc.
                self._refs = None
                if not self._refs_warnings:
                    self._refs_warnings.append(f"universe build failed: {_exc(e)}")
            self._refs_built = True
        return self._refs

    def _build_refs(self, ctx: Context) -> list:
        import quality
        refs: list = []
        seen: set[str] = set()
        for cand in ctx.tickers:
            out = quality.build_inline_universe(cand.ticker, cand.sector_arg, None, False)
            base, sector, _scope, warns, err = out
            if err or not base:
                self._refs_warnings.append(
                    f"{cand.ticker}: {err or 'no refs'} — pass --sector {cand.ticker}=<group> "
                    f"(groups: {', '.join(sorted(CONFIG['QUALITY_SECTORS']))})")
                continue
            self._refs_warnings += [f"{cand.ticker}: {w}" for w in (warns or ())]
            take = base
            if cand.bucket and sector == "consumer":
                bucket_set = CONFIG["STAPLES_SET" if cand.bucket == "staples" else "DISCRETIONARY_SET"]
                subset = sorted(set(getattr(quality, "GROUPS", {}).get("consumer", ())) & bucket_set)
                if subset:
                    take = quality.build_inline_universe(
                        cand.ticker, cand.sector_arg, ",".join(subset), False)[0]
                    self._pinned[cand.ticker] = cand.bucket
                else:
                    self._refs_warnings.append(
                        f"{cand.ticker}: --bucket {cand.bucket} matched 0 consumer names; full consumer peers kept")
            elif cand.bucket:
                self._refs_warnings.append(f"{cand.ticker}: --bucket ignored ({sector} is not consumer)")
            if ctx.flags.get("peers") == "watchlist":
                take = take[:1]                    # the target only (rough scores)
            for r in take:
                if r.ticker not in seen:
                    seen.add(r.ticker)
                    refs.append(r)
        if self._pinned:                          # split consumer pools globally
            for i, r in enumerate(refs):
                pool = self._pinned.get(r.ticker) if r.sector == "consumer" else None
                if pool is None and r.sector == "consumer":
                    if r.ticker in CONFIG["STAPLES_SET"]:
                        pool = "staples"
                    elif r.ticker in CONFIG["DISCRETIONARY_SET"]:
                        pool = "discretionary"
                if pool:
                    refs[i] = quality.TickerRef(r.ticker, pool, r.status, r.note, r.evidence)
        return refs

    # -- engine loop ------------------------------------------------------ #
    def prefetch(self, ctx: Context) -> None:
        import quality
        ver, tested, differs = _engine_version("quality", quality)
        res = self._begin(ver, tested)
        if differs:
            res.warnings = (*res.warnings, f"quality v{ver} != tested v{tested}")
        self._cache_dir = str(getattr(quality, "CACHE_DIR", "data/cache"))
        self._stamp = _dir_stamp(self._cache_dir)
        self._refs = self.peek_refs(ctx)          # built once (plan banner)
        if not self._refs:
            self._refs_warnings.append("universe refs empty — nothing to score")
        pool_sizes: dict[str, int] = {}
        for r in self._refs or ():
            pool_sizes[getattr(r, "sector", "")] = pool_sizes.get(getattr(r, "sector", ""), 0) + 1
        prog = ctx.flags.get("progress")
        t0 = time.monotonic()
        for cand in ctx.tickers:
            try:
                r = quality.get_quality_score(
                    cand.ticker, as_of=ctx.as_of, source=ctx.flags.get("source", "auto"),
                    universe_refs=self._refs,
                    progress=(lambda p, n, t: prog.set(
                        f"quality: {p}/{n} {t} · {time.monotonic() - t0:.0f}s")
                        if prog.alive("quality") else None) if prog else None)
                r["_pool_size"] = pool_sizes.get(str(r.get("sector") or ""), 0)
                sig = _quality_signal(cand, r)
            except Exception as e:                 # ticker failure never kills the layer
                _ctx_note(ctx, f"quality {cand.ticker}: {_exc(e)}")
                sig = LayerSignal(cand.ticker, "quality", status="ERROR",
                                  warnings=(_exc(e),), as_of=ctx.as_of or "")
            res.signals[cand.ticker] = sig
        if prog:
            prog.kill("quality")                 # done: silence this owner for good

    def run(self, ctx: Context, cands: list[Candidate]) -> LayerResult:
        import quality
        res = self._partial or self._begin(*_engine_version("quality", quality))
        res.warnings = tuple(dict.fromkeys((*res.warnings, *self._refs_warnings)))[:12]
        if not res.signals or all(s.status == "ERROR" for s in res.signals.values()):
            res.status = "ERROR"
        elif any(s.status != "OK" for s in res.signals.values()) or res.warnings:
            res.status = "DEGRADED"
        fixtures = ctx.flags.get("source") == "fixtures"
        if fixtures:
            res.cache = "n/a"
        elif self._stamp is not None and _touched(self._stamp, self._cache_dir):
            res.cache = "cold"
        elif res.signals:
            res.cache = "warm"
        res.ctx_out = {"scored": sum(1 for s in res.signals.values() if s.status == "OK"),
                       "total": len(res.signals)}
        return res


# ── § 3.5 · EarningsLayer (L3, earnings_engine) ──────────────────────────
def _num(x: Any) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def _accuracy_verdict(acc: Any) -> str:
    """Mirror of the engine's own walk-forward verdict (report() is never
    called; verbatim-in-spirit)."""
    if acc is None or len(acc) == 0:
        return "NOT ENOUGH DATA (no walk-forward history to test)"
    n_tests = int(_num(acc.get("n_tests")) or 0)
    n_hi = int(_num(acc.get("n_score>=50")) or 0)
    if n_tests < 60 or n_hi < 30:
        return f"NOT ENOUGH DATA to judge (only {n_hi} high-rated tests, want 30+). Add more tickers."
    lift = _num(acc.get("lift_vs_base"))
    corr = _num(acc.get("rank_corr_score_vs_next_surprise"))
    lo = _num(acc.get("auc_lo"))
    if lift == lift and lift >= 1.5 and corr == corr and corr >= 0.10 and lo == lo and lo > 0.5:
        return f"SIGNAL: high-rated names hit big beats {lift:.2f}x more often than base"
    return "WEAK / NO SIGNAL in this sample (AUC interval touches 0.50 or lift is small)"


def _dstr(x: Any) -> str:
    return str(getattr(x, "date", x) or "")


def _earnings_signal(t: str, row: Any, plan_row: dict | None, err: str | None,
                     as_of: str | None) -> LayerSignal:
    facts: dict[str, Any] = {"plan": None, "now": False}
    base = dict(source="yahoo", as_of=as_of or "", layer="earnings", ticker=t)
    if row is None:
        return LayerSignal(**base, status="MISSING", grade="-",
                           warnings=(_redact(str(err or "no earnings history (<4 quarters or provider failed)"))[:160],))
    last_s = _dstr(row.get("last_date"))
    if as_of and last_s and last_s > as_of:
        return LayerSignal(**base, status="MISSING",
                           warnings=(f"future-dated output rejected (no-lookahead): last_date {last_s} > as_of {as_of}",))
    score = float(row.get("score"))
    pn = row.get("p_next_big")
    conf = row.get("confidence")
    facts.update({
        "n_quarters": int(_num(row.get("n_quarters")) or 0), "last_date": last_s,
        "last4_big": int(_num(row.get("last4_big")) or 0),
        "streak_big": int(_num(row.get("streak_big")) or 0),
        "qtrs_since_big": _num(row.get("qtrs_since_big")),
        "last_big_date": _dstr(row.get("last_big_date")),
        "last_big_pct": _num(row.get("last_big_pct")),
        "latest_surprise_pct": _num(row.get("latest_surprise_pct")),
        "beat_rate": _num(row.get("beat_rate")),
        "p_next_big": (pn if (pn is not None and pn == pn) else None),
        "confidence": (float(conf) if conf is not None else 1.0),
    })
    if plan_row:
        facts["plan"] = plan_row.get("status")
        facts["now"] = plan_row.get("status") == "LONG"
        for k in ("price", "target", "stop_px", "days_since"):
            facts[k] = _num(plan_row.get(k)) if plan_row.get(k) is not None else None
        facts["exit_by"] = _dstr(plan_row.get("exit_by"))
        facts["last_report"] = _dstr(plan_row.get("last_report"))
    warns = (_redact(str(err))[:160],) if err else ()
    return LayerSignal(**base, status="OK", score=round(score, 1),
                       grade=str(row.get("rating") or "-"),   # engine's own rating
                       confidence=float(_num(row.get("confidence")) or 1.0),
                       facts=facts, warnings=warns)


def _backtest_summary(a: Any) -> dict | None:
    try:
        bt = getattr(a, "backtest", None)
        if bt is None or len(bt) == 0:
            return None
        key = [i for i in bt.index if str(i).startswith("score>=")]
        if not key:
            return None
        r = bt.loc[key[0]]
        return {"n_trades": int(len(getattr(a, "trades", []) or [])),
                "rule_n": int(_num(r.get("n")) or 0),
                "vs_spy_pct": round(_num(r.get("vs_SPY%")), 1),
                "ci_lo_pct": round(_num(r.get("ci_lo%")), 1),
                "ci_hi_pct": round(_num(r.get("ci_hi%")), 1)}
    except Exception:
        return None


class EarningsLayer(LayerBase):
    """L3 timing on the funnel shortlist. trade=True (full backtest) only
    with --earnings-backtest; eng.plan is called separately (one small price
    download) and ONLY when as_of is None (no lookahead: the engine's plan
    uses today's clock)."""
    name = "earnings"
    order = 3
    stage = "score"

    def __init__(self) -> None:
        super().__init__()
        self._eng = None
        self._mod: types.ModuleType | None = None
        self._stamp: tuple[bool, float] | None = None
        self._cache_dir = ""

    def _engine(self, ctx: Context):
        if self._eng is None:
            import earnings_engine
            self._mod = earnings_engine
            workers = int(ctx.flags.get("workers") or CONFIG["DEFAULT_WORKERS"])
            if workers > CONFIG["DEFAULT_WORKERS"]:
                _ctx_note(ctx, f"workers {workers} > {CONFIG['DEFAULT_WORKERS']} may hit "
                               "Yahoo rate limits (quality/meds share the endpoint)")
            self._cache_dir = ctx.flags.get("earnings_cache_dir") or ""
            self._stamp = _dir_stamp(self._cache_dir) if self._cache_dir else None
            eng = earnings_engine.EarningsEngine(
                quarters=CONFIG["EARNINGS_QUARTERS"], workers=workers,
                cache_dir=self._cache_dir or None)
            if ctx.flags.get("offline"):
                eng._fetch = _offline_raiser      # instance attrs only; cache names unchanged
                eng._px_fetch = _offline_raiser
            self._eng = eng
        return self._eng

    def prefetch(self, ctx: Context) -> None:
        """--earnings-prefetch all (off by default): warm histories for the
        whole watchlist at t=0, only when it is <= PREFETCH_ALL_MAX names."""
        if ctx.flags.get("earnings_prefetch") != "all":
            return
        if len(ctx.tickers) > CONFIG["PREFETCH_ALL_MAX"]:
            _ctx_note(ctx, f"--earnings-prefetch all ignored ({len(ctx.tickers)} > "
                           f"{CONFIG['PREFETCH_ALL_MAX']} names)")
            return
        eng = self._engine(ctx)

        def _warm(t: str) -> None:
            try:
                eng.history(t)
            except Exception:
                pass                        # run() retries and records the real error
        from concurrent.futures import ThreadPoolExecutor as _TP
        with _TP(4) as ex:
            list(ex.map(_warm, [c.ticker for c in ctx.tickers]))

    def _plan(self, eng, scores, ctx: Context):
        if ctx.as_of is not None:
            return None                      # no lookahead: plan needs today's clock
        try:
            return eng.plan(scores, min_score=CONFIG["EARNINGS_PLAN_MIN"],
                            hold_days=CONFIG["EARNINGS_HOLD_DAYS"],
                            take_profit=CONFIG["EARNINGS_TP"],
                            max_age_days=CONFIG["EARNINGS_MAX_AGE"])
        except Exception as e:
            _ctx_note(ctx, f"earnings plan unavailable (prices): {_exc(e)}")
            return None

    def run(self, ctx: Context, cands: list[Candidate]) -> LayerResult:
        eng = self._engine(ctx)
        ver, tested, differs = _engine_version("earnings", self._mod or types.ModuleType("earnings_engine"))
        res = self._begin(ver, tested)
        if self._mod is not None and not hasattr(self._mod, "__version__") \
                and not hasattr(self._mod, "_version_noted"):
            self._mod._version_noted = True
            res.warnings = (*res.warnings, "earnings engine exposes no __version__; "
                            f"reporting docstring v{ver} (drift undetectable)")
        if differs:
            res.warnings = (*res.warnings, f"earnings v{ver} != tested v{tested}")
        prog = ctx.flags.get("progress")
        tickers = [c.ticker for c in cands]
        if not tickers:
            res.warnings = (*res.warnings, "empty shortlist: nothing passed the quality gate")
            res.ctx_out = {"verdict": "not run (empty shortlist)", "weak": False,
                           "missing": [], "scored": 0, "backtest": None}
            res.status = "DEGRADED"
            return res
        if prog and prog.alive("earnings"):
            prog.set(f"earnings: {len(tickers)} names (history+plan)")
        try:
            backtest = bool(ctx.flags.get("earnings_backtest"))
            a = eng.analyze(tickers, as_of=ctx.as_of, accuracy=True, trade=backtest)
            plan = a.plan if (backtest and ctx.as_of is None) else self._plan(eng, a.scores, ctx)
        except Exception as e:
            res.status = "ERROR"
            res.warnings = (*res.warnings, _exc(e))
            _ctx_note(ctx, f"earnings layer: {_exc(e)}")
            if prog:
                prog.kill("earnings")
            return res
        plan_map = dict(plan.to_dict("index")) if (plan is not None and len(plan)) else {}
        verdict = _accuracy_verdict(getattr(a, "accuracy", None))
        weak = verdict.startswith(("WEAK", "NOT ENOUGH"))
        for t in tickers:
            row = a.scores.loc[t] if t in a.scores.index else None
            res.signals[t] = _earnings_signal(t, row, plan_map.get(t), eng.errors.get(t), ctx.as_of)
        missing = [t for t, s in res.signals.items() if s.status != "OK"]
        if not res.signals or all(s.status != "OK" for s in res.signals.values()):
            res.status = "ERROR"
        elif missing or weak or eng.errors:
            res.status = "DEGRADED"
        if ctx.flags.get("offline"):
            res.cache = "n/a"
        elif self._stamp is not None and _touched(self._stamp, self._cache_dir):
            res.cache = "cold"
        elif res.signals:
            res.cache = "warm"
        res.ctx_out = {"verdict": verdict, "weak": weak, "missing": missing,
                       "scored": len(res.signals) - len(missing),
                       "backtest": _backtest_summary(a) if backtest else None}
        if prog:
            prog.kill("earnings")
        return res


# ── § 3.6 · registry (L4 'ml' / L5 'risk' get appended here later) ────────
LAYER_REGISTRY: dict[str, type[LayerBase]] = {
    "macro": MacroLayer, "quality": QualityLayer, "earnings": EarningsLayer,
}
LAYERS: list[LayerBase] = [LAYER_REGISTRY[n]() for n in ("macro", "quality", "earnings")]


def build_layers(only: set[str] | None, skip: set[str] | None,
                 stubbed: bool = False) -> list[LayerBase]:
    """Ordered instances for one run. A --layers registry flag (reserved)
    will make extra layers appear in the header and --json automatically."""
    order = ("macro", "quality", "earnings")
    names = [n for n in order
             if (not only or n in only) and (not skip or n not in skip)]
    maker: dict[str, type[LayerBase]]
    if stubbed:                       # SELFTEST stubs (defined in § 8)
        maker = {"macro": StubMacroLayer, "quality": StubQualityLayer,
                 "earnings": StubEarningsLayer}
    else:
        maker = LAYER_REGISTRY
    return [maker[n]() for n in names]


# ════════════════════════════════════════════════════════════════════════
#  § 4 · FUSION — gates -> conviction -> action -> reasons (priors, §4 spec)
# ════════════════════════════════════════════════════════════════════════
def macro_tilt(state: MacroState | None, sector: str) -> float | None:
    """+1/+0.5 when a mapped ETF is long (weak mappings halved); -0.5 when
    defensive AND cyclical AND not long-aligned; 0 otherwise; None =
    macro-silent (no ETF vocabulary for the sector, or the layer is down) —
    healthcare/financials/reits/specialty are always silent (trap 3)."""
    if state is None or state.status == "ERROR" or not sector:
        return None
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
    mapped = ", ".join(
        f"{etf}({'strong' if s >= 1.0 else 'weak'})"
        for etf, pairs in CONFIG["ETF_TO_SECTORS"].items()
        for sec, s in pairs if sec == sector and etf in set(state.longs or ()))
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


def _base_conviction(q: float, e: float | None, weak: bool) -> float:
    """§4.3 base before the macro multiplier."""
    if e is None:
        return q * CONFIG["E_MISSING_HAIRCUT"]
    if not weak:
        return CONFIG["W_Q"] * q + CONFIG["W_E"] * e
    we = CONFIG["W_E"] * CONFIG["EARNINGS_WEAK_SCALE"]
    return (CONFIG["W_Q"] * q + we * e) / (CONFIG["W_Q"] + we)


def _reasons(d: Decision, cand: Candidate, q: float | None, e: float | None,
             q_sig: LayerSignal | None, e_sig: LayerSignal | None,
             state: MacroState | None, mv: dict, weak: bool, mode: str,
             capped: bool, trig_block: bool) -> None:
    pool = (q_sig.facts.get("sector") if q_sig else "") or "-"
    if q is not None:
        rank = q_sig.facts.get("rank") if q_sig else None
        rank_s = f"rank {rank}/{q_sig.facts.get('pool_size', '-')}" if isinstance(rank, int) else f"rank -/{pool}"
        d.reasons.append(f"Q {q:.0f} ({d.layers['quality'].grade}) {rank_s} {pool}")
    t = mv["tilt"]
    if state is None or state.status == "ERROR":
        d.reasons.append("macro n/a (layer down)")
    elif t is None:
        d.reasons.append(f"macro --: no ETF mapping for {cand.macro_sector}")
    else:
        why = (f"{mv['mapped'][:40]} long in {state.scenario_key}" if t > 0 and mv["mapped"]
               else (f"defensive, {cand.macro_sector} cyclical" if t < 0 else "not long-aligned"))
        if mv["damp"] < 1.0 and t:
            why += " (damped x0.5)"
        d.reasons.append(f"macro {t:+.1f}: {why}")
    if e is not None:
        seg = f"E {e:.0f} ({d.layers['earnings'].grade})"
        if e_sig is not None and e_sig.facts.get("plan") == "LONG":
            seg += f" NOW (report {e_sig.facts.get('days_since', '?')}d)"
        if weak:
            seg += " (weak x0.5)"
        d.reasons.append(seg)
    else:
        why = "E layer off" if e_sig is None else f"E {e_sig.status}"
        d.reasons.append(f"{why} -> Q x{CONFIG['E_MISSING_HAIRCUT']:.2f}")
    if capped:
        d.reasons.append(f"cap: defensive regime, tilt {t:+.1f}")
    if trig_block:
        plan_s = (e_sig.facts.get("plan") if e_sig else None) or "-"
        d.reasons.append(f"trigger: plan {plan_s} -> WATCH")


def fuse_candidate(cand: Candidate, q_sig: LayerSignal | None,
                   e_sig: LayerSignal | None, state: MacroState | None,
                   mode: str, weak: bool) -> Decision:
    """One Decision for one candidate (§4.1-§4.4, in order)."""
    q = q_sig.score if (q_sig is not None and q_sig.status == "OK"
                        and q_sig.score is not None) else None
    e = e_sig.score if (e_sig is not None and e_sig.status == "OK"
                        and e_sig.score is not None) else None
    if q_sig is not None:
        cand.sector = q_sig.facts.get("sector") or cand.sector
        cand.macro_sector = q_sig.facts.get("macro_sector") or cand.sector
    mv = macro_view(state, cand.macro_sector or cand.sector)
    d = Decision(ticker=cand.ticker, sector=cand.sector or "-")
    d.layers["macro"] = _macro_signal(cand.ticker, state, mv)
    d.layers["quality"] = q_sig or LayerSignal(cand.ticker, "quality", status="MISSING")
    d.layers["earnings"] = e_sig or LayerSignal(cand.ticker, "earnings", status="MISSING")
    veto = sorted(set((q_sig.flags if q_sig else ())) & CONFIG["VETO_FLAGS"])
    if q is not None:                       # conviction computed even when gated
        d.conviction = round(max(0.0, min(100.0, _base_conviction(q, e, weak) * mv["mult"])), 1)
        d.grade = _native_grade("MASTER_GRADES", d.conviction)
    # hard quality gate (macro never vetoes)
    if q is None:
        d.action = "AVOID"
        why = (q_sig.facts.get("engine_status") if q_sig else None) or "LAYER OFF"
        d.reasons.insert(0, f"no quality score: {why}")
    elif veto:
        d.action = "AVOID"
        d.reasons.insert(0, f"veto: {', '.join(veto)}")
    elif q < CONFIG["MIN_QUALITY"]:
        d.action = "AVOID"
        d.reasons.insert(0, f"Q {q:.0f} ({d.layers['quality'].grade}) < {CONFIG['MIN_QUALITY']:.0f} gate")
    else:
        capped = mv["tilt"] is not None and mv["tilt"] < 0
        now = bool(e_sig is not None and e_sig.facts.get("plan") == "LONG")
        trig_block = (mode == "trigger") and not now
        if d.conviction >= CONFIG["ACTION_LONG_AT"] and not capped and not trig_block:
            d.action = "LONG"
        elif (d.conviction >= CONFIG["ACTION_WATCH_AT"]
                or (d.conviction >= CONFIG["ACTION_LONG_AT"] and (capped or trig_block))):
            d.action = "WATCH"
        else:
            d.action = "AVOID"
        _reasons(d, cand, q, e, q_sig, e_sig, state, mv, weak, mode, capped, trig_block)
    d.reasons = d.reasons[:CONFIG["MAX_REASONS"]]
    return d


def fuse(ctx: Context, results: dict[str, LayerResult], mode: str = "boost") -> list[Decision]:
    """All decisions, sorted by conviction desc then ticker."""
    state = ctx.regime
    q_res, e_res = results.get("quality"), results.get("earnings")
    weak = bool(e_res is not None and e_res.ctx_out.get("weak"))
    out = []
    for cand in ctx.tickers:
        q_sig = (q_res.signals.get(cand.ticker) if q_res else None)
        e_sig = (e_res.signals.get(cand.ticker) if e_res else None)
        if q_sig is None and q_res is not None:
            q_sig = LayerSignal(cand.ticker, "quality", status="MISSING",
                                facts={"engine_status": "NO_SIGNAL"})
        out.append(fuse_candidate(cand, q_sig, e_sig, state, mode, weak))
    out.sort(key=lambda d: (-d.conviction, d.ticker))
    return out


def funnel_shortlist(ctx: Context, results: dict[str, LayerResult], k: int) -> list[Candidate]:
    """Top-K survivors of L1+L2 for the earnings funnel, ranked by
    pre-earnings conviction (E assumed missing at funnel time — the
    documented prior; --earnings-prefetch all exists for <=60-name lists)."""
    q_res, state = results.get("quality"), ctx.regime
    if q_res is None:
        return []
    ranked: list[tuple[float, str, Candidate]] = []
    for cand in ctx.tickers:
        q_sig = q_res.signals.get(cand.ticker)
        if q_sig is None or q_sig.status != "OK" or q_sig.score is None:
            continue
        if q_sig.score < CONFIG["MIN_QUALITY"] or set(q_sig.flags) & CONFIG["VETO_FLAGS"]:
            continue
        cand.sector = q_sig.facts.get("sector") or cand.sector
        cand.macro_sector = q_sig.facts.get("macro_sector") or cand.sector
        mv = macro_view(state, cand.macro_sector)
        ranked.append((q_sig.score * CONFIG["E_MISSING_HAIRCUT"] * mv["mult"], cand.ticker, cand))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    return [c for _, _, c in ranked[:max(0, int(k))]]

# ════════════════════════════════════════════════════════════════════════
#  § 5 · ORCHESTRATOR — context, parallel prefetch, funnel, fuse
# ════════════════════════════════════════════════════════════════════════
class MasterError(Exception):
    """One-line user error carrying its exit code (2 NO-GO / 64 bad usage)."""

    def __init__(self, msg: str, code: int = 2) -> None:
        super().__init__(msg)
        self.code = code


_PHASE_NAME = "startup"


class _phase:
    """Context manager naming the current phase (printed on Ctrl-C, exit 130)."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __enter__(self) -> "_phase":
        global _PHASE_NAME
        _PHASE_NAME = self.name
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


def phase_name() -> str:
    return _PHASE_NAME


# ── § 5.1 · context build (candidates + flags; raises MasterError on bad input)
def _parse_layers(ns: argparse.Namespace) -> tuple[set[str] | None, set[str] | None]:
    only = {s.strip() for s in (ns.only or "").split(",") if s.strip()} or None
    skip = {s.strip() for s in (ns.skip or "").split(",") if s.strip()} or None
    known = set(LAYER_REGISTRY)          # 'ml'/'risk' reserved: not selectable yet
    bad = (only or set()) | (skip or set())
    bad -= known
    if bad:
        raise MasterError(f"unknown layer(s): {', '.join(sorted(bad))} "
                           f"(known: {', '.join(sorted(known))})", 64)
    if only and skip and (only & skip):
        raise MasterError(f"--only and --skip overlap on {', '.join(sorted(only & skip))}", 64)
    return only, skip


def _watchlist_rows(path: str) -> list[tuple[str, str | None]]:
    """One (ticker, sector|None) per line: 'TICKER' or 'TICKER,sector'."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise MasterError(f"watchlist {path}: {e}", 64) from e
    out: list[tuple[str, str | None]] = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        parts = [p.strip() for p in re.split(r"[,\t]", ln, maxsplit=1)]
        if parts[0].lower() in ("ticker", "symbol"):
            continue                                   # header line
        out.append((parts[0], parts[1] if len(parts) > 1 and parts[1] else None))
    return out


def _build_context(ns: argparse.Namespace) -> Context:
    """Candidates + flags. Sleeve ETFs never go to L2/L3 (macro card only)."""
    cands: list[Candidate] = []
    by_t: dict[str, Candidate] = {}

    def _add(raw: str, sector: str | None, bucket: str | None) -> None:
        t = _norm_ticker(raw)
        if t is None:
            raise MasterError(f"{raw!r} does not look like a ticker (e.g. AAPL, BRK-B)", 64)
        if t in by_t:
            if sector:
                by_t[t].sector_arg = sector
            if bucket:
                by_t[t].bucket = bucket
            return
        c = Candidate(ticker=t, sector_arg=sector, bucket=bucket)
        by_t[t] = c
        cands.append(c)

    for t in (ns.tickers or []):
        _add(t, None, None)
    for spec in (ns.tickers_csv or []):
        for part in spec.split(","):
            if part.strip():
                _add(part, None, None)
    for t, sector in _watchlist_rows(ns.watchlist) if ns.watchlist else ():
        if sector and sector.lower() not in CONFIG["QUALITY_SECTORS"]:
            raise MasterError(f"watchlist sector {sector!r} for {t} is not one of "
                               f"{', '.join(sorted(CONFIG['QUALITY_SECTORS']))}", 64)
        _add(t, sector.lower() if sector else None, None)
    for spec in (ns.sector or []):
        t, _, val = spec.partition("=")
        if not val or val.lower() not in CONFIG["QUALITY_SECTORS"]:
            raise MasterError(f"--sector {spec!r}: expected TICKER=<group> with group in "
                               f"{', '.join(sorted(CONFIG['QUALITY_SECTORS']))}", 64)
        _add(t, val.lower(), None)
    for spec in (ns.bucket or []):
        t, _, val = spec.partition("=")
        if val not in ("staples", "discretionary"):
            raise MasterError(f"--bucket {spec!r}: expected TICKER=staples|discretionary", 64)
        _add(t, None, val)
    if not cands:
        for t in CONFIG["DEFAULT_WATCHLIST"]:
            _add(t, None, None)
    sleeve = [c.ticker for c in cands if c.ticker in CONFIG["SLEEVE_ETFS"]]
    cands = [c for c in cands if c.ticker not in CONFIG["SLEEVE_ETFS"]]
    flags: dict[str, Any] = {
        "source": ns.source, "offline": ns.offline, "workers": ns.workers,
        "peers": ns.peers, "earnings_prefetch": ns.earnings_prefetch,
        "earnings_backtest": ns.earnings_backtest, "verbose": ns.verbose,
    }
    if ns.cache_dir:
        base = str(Path(ns.cache_dir))
        os.environ["QE_DATA_DIR"] = os.path.join(base, "quality")        # BEFORE import quality
        os.environ["QE_CACHE_DIR"] = os.path.join(base, "quality", "cache")
        flags["earnings_cache_dir"] = os.path.join(base, "earnings")
    ctx = Context(as_of=ns.as_of, tickers=cands, flags=flags)
    if not cands:
        raise MasterError("no equity tickers left (only non-equity sleeve ETFs: "
                           + ", ".join(sleeve) + " — macro card only)", 64)
    return ctx


# ── § 5.2 · guarded phase calls (per-layer wall-clock budget) ────────────
def _deadline_call(deadline: float, fn: Callable[..., Any], *args: Any) -> Any:
    """Run fn on one throwaway thread with the remaining budget; raise
    TimeoutError when it expires (the stuck thread keeps filling the partial)."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError()
    ex = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mx-run")
    try:
        return ex.submit(fn, *args).result(timeout=remaining)
    finally:
        ex.shutdown(wait=False, cancel_futures=True)


def _prefetch_one(layer: LayerBase, ctx: Context) -> LayerResult | None:
    try:
        layer.prefetch(ctx)
        return None
    except Exception as e:                 # adapter boundary; run continues
        return layer._salvage(f"prefetch: {_exc(e)}")


def _timeout_hint(layer: LayerBase, note: Callable[[str], None]) -> None:
    """Actionable next step when a timed-out layer produced nothing at all
    (v1.1.0: the all-AVOID 'no quality score' table was honest but useless)."""
    if layer.name == "quality" and not (layer._partial and layer._partial.signals):
        note("quality timed out before the first score — the background pass keeps "
             "filling data/cache; rerun the same command to resume from cache, "
             "or use --mode quick / --warm now")


# ── § 5.2.5 · [plan] banner — printed BEFORE any layer runs (v1.1.0) ──────
def _plan_banner(ctx: Context, layers: list[LayerBase], ns: argparse.Namespace,
                 stubbed: bool) -> None:
    """The anti-'stuck' banner on stderr: what this run will do (mode, ticker
    count, EXACT quality comparison pool, L3 funnel, per-layer budget), what
    state the caches are in, and the honest ETA with the faster alternative
    when the pass would be cold. Estimates come from COLD_S_PER_NAME /
    WARM_ETA_RANGE_S and are advisory only — never a decision input."""
    if stubbed or getattr(ns, "quiet", False):
        return
    mode = getattr(ns, "mode", "standard")
    warm = bool(getattr(ns, "warm", False))
    parts = [(f"warm-up run (macro+quality only, budget {ns.timeout:g}s)"
              if warm else f"mode {mode}"),
             f"{len(ctx.tickers)} tickers"]
    ql = next((l for l in layers if l.name == "quality"), None)
    pool: int | None = None
    if ql is not None and hasattr(ql, "peek_refs"):
        refs = ql.peek_refs(ctx)                 # built once; prefetch reuses
        pool = len(refs) if refs else 0
    if pool:
        parts.append(f"quality pool {pool} names"
                     + (" (watchlist ranks — rough)" if ns.peers == "watchlist" else ""))
    if any(l.name == "earnings" for l in layers):
        parts.append(f"L3 top-{ns.earnings_top}")
    if not warm:
        parts.append(f"budget {ns.timeout:g}s/layer")
    # -- cache ages (informational only) ---------------------------------- #
    qmod = sys.modules.get("quality")
    qdir = str(getattr(qmod, "CACHE_DIR", "")
               or os.path.join(os.environ.get("QE_DATA_DIR", "data"), "cache"))
    mdir = str(Path(__file__).resolve().parent / "meds_cache")
    edir = str(ctx.flags.get("earnings_cache_dir")
               or Path.home() / ".earnings_engine_cache")
    ages = {n: _cache_age_h(p) for n, p in
            (("quality", qdir), ("macro", mdir), ("earnings", edir))}
    cells = [(f"{n} COLD" if a is None else f"{n} {a:.1f}h") for n, a in ages.items()]
    hint = ""
    if pool and ages["quality"] is None:
        lo, hi = CONFIG["COLD_S_PER_NAME"]
        hint = (f" — cold quality pass ≈{pool * lo / 60:.0f}-{pool * hi / 60:.0f} min"
                " · faster now: --mode quick · fill caches first: --warm")
    elif pool and ages["quality"] is not None \
            and ages["quality"] > CONFIG["PRICE_TTL_H"]:
        hint = (f" — quality prices older than {CONFIG['PRICE_TTL_H']:.0f}h"
                " will re-fetch (slower pass)")
    elif pool and not warm:
        lo, hi = CONFIG["WARM_ETA_RANGE_S"]
        hint = f" — caches warm, expect ≈{lo / 60:.0f}-{hi / 60:.0f} min"
    sys.stderr.write("[plan] " + " · ".join(parts) + "\n"
                     "[plan] caches: " + " · ".join(cells) + hint + "\n")
    sys.stderr.flush()


# ── § 5.3 · the pipeline ─────────────────────────────────────────────────
def run_pipeline(ns: argparse.Namespace) -> RunOutput:
    """1 macro call -> N quality scores (shared universe) -> top-K earnings
    -> fuse -> one ranked table. A layer failure never kills the run."""
    t_all = time.monotonic()
    _apply_mode(ns)                        # mode/warm presets for unset flags
    with _phase("setup"):
        ctx = _build_context(ns)
        only, skip = _parse_layers(ns)
        if ns.earnings_mode == "off":
            if only == {"earnings"}:
                raise MasterError("--only earnings with --earnings-mode off selects nothing", 64)
            skip = (skip or set()) | {"earnings"}
        stubbed = os.environ.get("MASTER_STUBS", "") not in ("", "0", "false")
        prog = _Progress(ns.quiet)
        notes: list[str] = []
        _seen: set[str] = set()

        def _note(msg: str) -> None:      # one stderr line per distinct failure
            if msg in _seen:
                return
            _seen.add(msg)
            notes.append(msg)
            sys.stderr.write(msg[:300] + "\n")

        ctx.flags["progress"] = prog
        ctx.flags["note"] = _note
        if ns.verbose:
            _note(f"layers: {' '.join(l.name for l in build_layers(only, skip, stubbed))}"
                  f" · as_of={ctx.as_of or 'live'} · tickers={len(ctx.tickers)}")
        layers = build_layers(only, skip, stubbed)
        if not layers:
            raise MasterError("no layers selected", 64)
        _plan_banner(ctx, layers, ns, stubbed)   # before ANY layer runs
    results: dict[str, LayerResult] = {}
    starts = {l.name: time.monotonic() for l in layers}
    budgets = {l.name: starts[l.name] + float(ns.timeout) for l in layers}
    with _phase("prefetch"):
        ex = ThreadPoolExecutor(max_workers=3, thread_name_prefix="mx")
        try:
            futs = {l.name: ex.submit(_prefetch_one, l, ctx) for l in layers}
            for layer in layers:
                try:
                    bad = futs[layer.name].result(
                        timeout=max(0.05, budgets[layer.name] - time.monotonic()))
                    if bad is not None:
                        results[layer.name] = bad
                        _note(f"{layer.name} prefetch failed: {bad.warnings[-1] if bad.warnings else '?'}")
                except TimeoutError:
                    prog.kill(layer.name)          # silence the stuck thread's line
                    results[layer.name] = layer._salvage(
                        f"{layer.name}: timeout after {ns.timeout}s (partial kept)")
                    _note(f"{layer.name} prefetch timed out after {ns.timeout}s — partial kept")
                    _timeout_hint(layer, _note)
                except Exception as e:
                    results[layer.name] = layer._salvage(f"{layer.name}: {_exc(e)}")
                    _note(f"{layer.name} prefetch failed: {_exc(e)}")
        finally:
            ex.shutdown(wait=False, cancel_futures=True)
    with _phase("layers"):
        for layer in layers:
            if layer.name in results or layer.name == "earnings":
                continue                     # errored in prefetch / runs after funnel
            try:
                results[layer.name] = _deadline_call(
                    budgets[layer.name], layer.run, ctx, ctx.tickers)
            except TimeoutError:
                prog.kill(layer.name)
                results[layer.name] = layer._salvage(
                    f"{layer.name}: timeout after {ns.timeout}s (partial kept)")
                _note(f"{layer.name} timed out after {ns.timeout}s — partial kept")
                _timeout_hint(layer, _note)
            except Exception as e:
                results[layer.name] = layer._salvage(f"{layer.name} run: {_exc(e)}")
                _note(f"{layer.name} run failed: {_exc(e)}")
        macro_res = results.get("macro")
        if macro_res is not None and macro_res.ctx_out.get("macro") is not None:
            ctx.regime = macro_res.ctx_out["macro"]
            ctx.risk_budget = float(macro_res.ctx_out.get("risk_budget", 1.0))
    with _phase("funnel"):
        shortlist = (funnel_shortlist(ctx, results, int(ns.earnings_top))
                     if "quality" in results else list(ctx.tickers))
        earn = next((l for l in layers if l.name == "earnings"), None)
        if earn is not None and "earnings" not in results:
            with _phase("earnings"):
                starts["earnings"] = time.monotonic()      # its clock starts at its run
                budgets["earnings"] = starts["earnings"] + float(ns.timeout)
                try:
                    results["earnings"] = _deadline_call(
                        budgets["earnings"], earn.run, ctx, shortlist)
                except TimeoutError:
                    prog.kill("earnings")
                    results["earnings"] = earn._salvage(
                        f"earnings: timeout after {ns.timeout}s (partial kept)")
                    _note(f"earnings timed out after {ns.timeout}s — partial kept")
                except Exception as e:
                    results["earnings"] = earn._salvage(f"earnings: {_exc(e)}")
                    _note(f"earnings failed: {_exc(e)}")
    with _phase("fusion"):
        decisions = (fuse(ctx, results, ns.earnings_mode)
                     if "quality" in results else [])
    for name, res in results.items():
        res.elapsed_s = round(time.monotonic() - starts.get(name, res.elapsed_s), 2)
    warnings = _aggregate_warnings(ctx, results, ns)
    exit_code, exit_reason = _resolve_exit(results, decisions)
    prog.stop()                            # final: no stuck thread paints after us
    timings = {"total": round(time.monotonic() - t_all, 1)}
    timings.update({n: r.elapsed_s for n, r in results.items()})
    return RunOutput(ctx=ctx, results=results, decisions=decisions, warnings=warnings,
                     timings=timings, exit_code=exit_code, exit_reason=exit_reason,
                     stubbed=stubbed)


def _aggregate_warnings(ctx: Context, results: dict[str, LayerResult],
                        ns: argparse.Namespace) -> list[str]:
    """Every honesty gate, loudly: credit OFF, DEGRADED, stale, no history."""
    w: list[str] = []
    state = ctx.regime
    if state is not None and state.credit == "OFF":
        w.append(f"credit OFF — not trade-grade (macro damped; excluded: "
                 f"{', '.join(state.excluded) or 'CREDIT_CRUNCH, EARLY_CYCLE_RE_ACCELERATION'})")
    if state is not None and state.status == "DEGRADED":
        w.append(f"macro DEGRADED ({'; '.join(state.warnings[:2]) or 'engine-reported'})")
    if "macro" in results and (state is None or state.status == "ERROR"):
        w.append("MACRO UNAVAILABLE — no regime context (tilt n/a, risk budget capped at 1.0)")
    q_res, e_res = results.get("quality"), results.get("earnings")
    if q_res is not None:
        if getattr(ns, "peers", None) == "watchlist":
            w.append(f"quality ranks are relative to the {len(ctx.tickers)}-name "
                     "watchlist only (--peers watchlist / --mode quick) — rough "
                     "percentiles, not sector pools")
        for t, sig in sorted(q_res.signals.items()):
            for flag in ("SPLIT_BASIS_UNVERIFIED", "STALE_PRICE"):
                if flag in sig.flags:
                    w.append(f"{flag} on {t}")
    if e_res is not None:
        if e_res.ctx_out.get("missing"):
            w.append(f"{len(e_res.ctx_out['missing'])} ticker(s) no earnings history")
        if e_res.ctx_out.get("verdict"):
            w.append(f"earnings accuracy: {e_res.ctx_out['verdict']}")
        bt = e_res.ctx_out.get("backtest")
        if bt:
            w.append(f"earnings backtest: {bt['n_trades']} trades, rule vs SPY "
                     f"{bt['vs_spy_pct']:+.1f}% (95% CI {bt['ci_lo_pct']:+.1f}..{bt['ci_hi_pct']:+.1f})")
    for res in results.values():
        for wn in res.warnings:
            if wn not in w and "version" not in wn:
                w.append(wn)
    if ns.earnings_mode == "trigger" and ns.as_of:
        w.append("trigger mode with --as-of: plan unavailable -> LONG impossible (WATCH at most)")
    out: list[str] = []
    for item in w:
        if item not in out:
            out.append(item)
    return out


def _resolve_exit(results: dict[str, LayerResult], decisions: list[Decision]) -> tuple[int, str]:
    """0 ok (DEGRADED included) / 2 no result / NO-GO — one line, no traceback.
    v1.1.0: the reason names the ERROR layer with the lowest order (the real
    blocker) and never quotes cosmetic version-drift notes — v1.0.0 blamed
    'earnings ... no __version__' when the actual cause was a macro/quality
    timeout."""
    if not results:
        return 2, "no result: no layer ran"

    def _useful(res: LayerResult) -> bool:
        if res.signals:
            return any(s.status != "ERROR" for s in res.signals.values())
        # no signals: only a non-ERROR macro state (or its exports) is a result
        return res.name == "macro" and res.status != "ERROR" and bool(res.ctx_out)

    if not any(_useful(r) for r in results.values()) \
            and not any(d.conviction > 0 for d in decisions):
        ordered = sorted(results.values(),
                         key=lambda r: (r.status != "ERROR", r.order))
        first = next((f"{r.name}: {wn.removeprefix(r.name + ': ')}"
                      for r in ordered for wn in r.warnings
                      if "version" not in wn), "all layers failed")
        return 2, f"no result / NO-GO: {first[:200]}"
    return 0, ""


# ════════════════════════════════════════════════════════════════════════
#  § 6 · RENDER — pure functions, no pandas; colour/ASCII/width honoured
# ════════════════════════════════════════════════════════════════════════
_COLORS = {"head": "36", "ok": "32", "warn": "33", "err": "31", "dim": "90", "bold": "1"}
_ASCII_MAP = {"█": "#", "░": "-", "╭": "+", "╮": "+", "╰": "+", "╯": "+", "─": "-",
              "│": "|", "✓": "v", "●": "*", "▲": "!", "✗": "x", "·": ".", "–": "-",
              "−": "-", "—": "-", "×": "x", "…": ".", "→": ">"}
_STRIP_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    return _STRIP_ANSI.sub("", text)


class Style:
    """Colour + ASCII swap + width. Colour-stripped output equals plain."""

    def __init__(self, color: bool, ascii_only: bool, width: int) -> None:
        self.color, self.ascii_only, self.width = color, ascii_only, width

    def mark(self, text: str, kind: str) -> str:
        code = _COLORS.get(kind)
        if not self.color or not code:
            return text
        return f"\033[{code}m{text}\033[0m"

    def swap(self, text: str) -> str:
        if not self.ascii_only:
            return text
        return "".join(_ASCII_MAP.get(ch, ch) for ch in text)


def make_style(ns: argparse.Namespace | None = None,
               color: bool | None = None, ascii_only: bool | None = None,
               width: int | None = None) -> Style:
    """Auto colour on a real TTY; honour NO_COLOR, TERM=dumb, --no-color."""
    if color is None:
        color = (sys.stdout.isatty() and not os.environ.get("NO_COLOR")
                 and os.environ.get("TERM") != "dumb")
        if ns is not None and ns.no_color:
            color = False
    ascii_only = bool(ns.ascii) if (ascii_only is None and ns is not None) else bool(ascii_only)
    if width is None:
        width = int(ns.width) if (ns is not None and ns.width) else 0
        if not width:
            try:
                width = shutil.get_terminal_size((96, 24)).columns
            except Exception:
                width = 96
        width = max(CONFIG["MIN_TERM_WIDTH"], min(width, CONFIG["MAX_TERM_WIDTH"]))
    width = max(40, min(width, CONFIG["MAX_TERM_WIDTH"]))
    return Style(color=color, ascii_only=ascii_only, width=width)


def _bar(frac: float, cols: int | None = None) -> str:
    frac = max(0.0, min(1.0, float(frac)))
    cols = cols or CONFIG["BAR_COLS"]
    n = int(round(frac * cols))
    return "█" * n + "░" * (cols - n)


def _fit(text: str, width: int) -> str:
    """Truncate with an ellipsis, width-safe."""
    return text if len(text) <= width else text[:max(1, width - 1)].rstrip() + "…"


def _wrap(text: str, width: int, indent: str = "   ") -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        if cur and len(cur) + 1 + len(w_) > width - len(indent):
            lines.append(cur)
            cur = w_
        else:
            cur = f"{cur} {w_}".strip()
    if cur:
        lines.append(cur)
    return [lines[0]] + [indent + ln for ln in lines[1:]] if lines else [""]


def _header(st: Style, out: RunOutput) -> str:
    names = sorted(out.results, key=lambda n: out.results[n].order)
    chain = "→".join(names) or "no layers"
    as_of = out.ctx.as_of or f"{date.today().isoformat()} (live)"
    inner = f"MASTER ENGINE v{__version__} · as of {as_of} · {chain}"
    w = st.width
    top, bot = "╭" + "─" * (w - 2) + "╮", "╰" + "─" * (w - 2) + "╯"
    mid = "│" + f" {inner} "[:w - 2].ljust(w - 2) + "│"
    return "\n".join([st.swap(top), st.mark(st.swap(mid), "head"), st.swap(bot)])


_LAYER_MODULE = {"macro": "meds", "quality": "quality", "earnings": "earnings"}
_STATUS_GLYPH = {"OK": ("●", "ok"), "DEGRADED": ("▲", "warn"), "ERROR": ("✗", "err")}


def _layers_block(st: Style, out: RunOutput) -> list[str]:
    lines = []
    for name in sorted(out.results, key=lambda n: out.results[n].order):
        res = out.results[name]
        glyph, kind = _STATUS_GLYPH.get(res.status, ("✗", "err"))
        mod = _LAYER_MODULE.get(name, name)
        ver = f"{mod} v{res.engine_version}"
        if res.engine_version != res.version_tested:
            ver += " ≠tested"
        elapsed = f"{res.elapsed_s:.1f}s" if res.elapsed_s < 100 else f"{res.elapsed_s:.0f}s"
        extra = ""
        if name == "quality" and res.ctx_out.get("total"):
            scored, total = res.ctx_out["scored"], res.ctx_out["total"]
            extra = f"{scored}/{total} scored"
            if st.width >= 96:
                extra += f"  {_bar(scored / max(total, 1), 12)} {scored}/{total}"
        elif name == "earnings":
            missing = len(res.ctx_out.get("missing") or [])
            extra = f"{missing} no data" if missing else "OK"
            if res.ctx_out.get("weak"):
                extra += " · weak"
        lead = "✓" if res.status != "ERROR" else "✗"
        name_col = st.mark(f"L{res.order} {name}".ljust(13), "bold")
        stat_col = st.mark(f"{glyph} {res.status}".ljust(12), kind)
        line = (f" {st.mark(lead, 'ok' if res.status != 'ERROR' else 'err')} {name_col}"
                f"{ver:<18}{elapsed:>6}  {res.cache:<5}{stat_col}{extra}")
        lines.append(st.swap(_fit(line, st.width)))
    if "earnings" not in out.results and out.ctx.flags.get("earnings_mode") == "off":
        lines.append(st.swap(f" · L3 earnings  off (--earnings-mode off)"))
    return lines


def _tilt_line(st: Style, state: "MacroState") -> list[str]:
    parts = []
    for sec in CONFIG["SECTOR_ORDER"]:
        t = macro_tilt(state, sec)
        abbr = CONFIG["SECTOR_ABBR"].get(sec, sec[:6])
        val = "–" if t is None else ("0" if not t else f"{t:+.1f}")
        parts.append(f"{abbr} {val}")
    txt = "   sector tilt  " + "  ·  ".join(parts)
    if state.degraded_for_damp:
        txt += f"  ·  macro {'DEGRADED' if state.status == 'DEGRADED' else 'credit OFF'}: tilt damped ×{CONFIG['MACRO_DEGRADED_DAMP']:.1f}"
    return [st.swap(x) for x in _wrap(txt, st.width, "     ")]


def _macro_card(st: Style, out: RunOutput) -> list[str]:
    state = out.ctx.regime
    if state is None or state.status == "ERROR":
        why = ""
        res = out.results.get("macro")
        if res is not None and res.warnings:
            why = res.warnings[0][:120]
        line = f" ! MACRO UNAVAILABLE — no regime context (tilt –, risk budget capped 1.0){' · ' + why if why else ''}"
        return [st.mark(st.swap(line), "err")]
    head = f" L1 MACRO ── {state.scenario_name or state.scenario_key} · {state.cycle_phase}"
    sub = (f"   conf {_bar(state.confidence)} {state.confidence:.2f} · "
           f"lev {state.conviction_leverage:.2f}x · risk budget {out.ctx.risk_budget:.2f}")
    credit = state.credit
    credit_txt = (f"credit {credit} ▲ not trade-grade" if credit == "OFF" else f"credit {credit}")
    info = (f"   eff {state.effective_as_of or '–'} · data {state.data_tier or '–'} · "
            f"PIT {state.pit_mode or '–'} · {credit_txt} · next month {state.trade_month or '–'}")
    longs = " ".join(state.longs) or "–"
    shorts = " ".join(state.shorts) or "–"
    sleeve = " ".join(state.sleeve) or "–"
    basket = f"   LONG  {longs:<14} SHORT  {shorts:<10} sleeve: {sleeve}"
    lines = [st.swap(_fit(head, st.width)), st.swap(_fit(sub, st.width))]
    lines += [st.swap(x) for x in _wrap(info, st.width, "     ")]
    lines.append(st.swap(_fit(basket, st.width)))
    if state.credit == "OFF" and state.excluded:
        lines.append(st.swap(f"   excluded (credit OFF): {', '.join(state.excluded)}"))
    if state.warnings:
        lines += [st.swap(x) for x in
                  _wrap("   macro warnings: " + " · ".join(state.warnings[:4]), st.width, "     ")]
    lines += _tilt_line(st, state)
    return lines


_Q_SHORT = {"INSUFFICIENT_DATA": "INSUF", "STALE_DATA": "STALE", "SECTOR_DATA_MISSING": "NOSEC",
            "NO_DATA": "NODATA", "DELISTED": "DELIST", "RENAMED": "RENAME", "ERROR": "ERR"}


def _q_cell(sig: LayerSignal | None) -> str:
    if sig is None:
        return "–"
    if sig.status == "OK" and sig.score is not None:
        return f"{sig.score:.0f} {sig.grade}"
    word = str(sig.facts.get("engine_status") or sig.status)
    return _Q_SHORT.get(word, word[:6])


def _e_cell(sig: LayerSignal | None) -> str:
    if sig is None:
        return "off"
    if sig.status != "OK" or sig.score is None:
        return "–"
    cell = f"{sig.score:.0f} {sig.grade}"
    if sig.facts.get("now"):
        cell += "·NOW"
    return cell


def _flags_cell(d: Decision) -> str:
    q = d.layers.get("quality")
    if d.action == "AVOID" and d.reasons:
        return d.reasons[0]
    flags = [f for f in (q.flags if q else ()) if f not in CONFIG["VETO_FLAGS"]]
    return ", ".join(flags) if flags else "–"


def _decisions_table(st: Style, out: RunOutput, ns: argparse.Namespace) -> list[str]:
    rows = [d for d in out.decisions if d.conviction >= float(ns.min_conviction)]
    rows = rows[:int(ns.top)]
    hidden = len(out.decisions) - len(rows)
    head = (f" {'#':>2}  {'TICKER':<7}{'SECTOR':<7}{'ACTION':<7}{'CONV':<16}"
            f"{'Q':<7}{'E':<10}{'MACRO':<6}FLAGS")
    flags_w = max(6, st.width - 65)
    lines = [st.mark(st.swap(head), "bold")]
    for i, d in enumerate(rows, 1):
        m = d.layers.get("macro")
        t = m.facts.get("tilt") if m else None
        mac = "–" if t is None else ("0" if not t else f"{t:+.1f}")
        act = st.mark(f"{d.action:<7}", {"LONG": "ok", "WATCH": "warn", "AVOID": "err"}[d.action])
        conv = f"{_bar(d.conviction / 100)} {d.conviction:.0f} {d.grade}"
        abbr = CONFIG["SECTOR_ABBR"].get(d.sector, d.sector[:6])
        fcell = _flags_cell(d)
        if len(fcell) > flags_w:
            fcell = fcell[:flags_w - 1] + "…"
        line = (f" {i:>2}  {st.mark(f'{d.ticker:<7}', 'bold')}{abbr:<7}{act}{conv:<16}"
                f"{_q_cell(d.layers.get('quality')):<7}{_e_cell(d.layers.get('earnings')):<10}"
                f"{mac:<6}{fcell}")
        lines.append(st.swap(line))
    counts = {a: sum(1 for d in out.decisions if d.action == a)
              for a in ("LONG", "WATCH", "AVOID")}
    tail = (f" {counts['LONG']} LONG · {counts['WATCH']} WATCH · {counts['AVOID']} AVOID")
    if hidden:
        tail += f" · {hidden} hidden (--top {ns.top} / min-conviction {ns.min_conviction:g})"
    lines.append(st.mark(st.swap(tail), "dim"))
    return lines


def _earnings_scorecard(st: Style, out: RunOutput, ns: argparse.Namespace) -> list[str]:
    res = out.results.get("earnings")
    if res is None or not res.signals:
        return []
    rows = sorted(res.signals.items(), key=lambda kv: -(kv[1].score or -1))
    rows = [(t, s) for t, s in rows if (s.score or 0) >= float(ns.min_conviction)][:int(ns.top)]
    lines = [st.mark(st.swap(f" {'#':>2}  {'TICKER':<8}{'E':<11}{'STATUS':<9}"
                             f"{'PLAN':<7}{'P_NEXT':<7}LAST BIG"), "bold")]
    for i, (t, s) in enumerate(rows, 1):
        e = f"{s.score:.0f} {s.grade}" + ("·NOW" if s.facts.get("now") else "")
        plan = s.facts.get("plan") or "–"
        p_next = ("–" if s.facts.get("p_next_big") != s.facts.get("p_next_big")
                  else f"{(s.facts.get('p_next_big') or 0) * 100:.0f}%")
        lines.append(st.swap(f" {i:>2}  {st.mark(f'{t:<8}', 'bold')}{e:<11}{s.status:<9}"
                             f"{plan:<7}{p_next:<7}{s.facts.get('last_big_date') or '–'}"))
    return lines


def _footer(st: Style, out: RunOutput) -> list[str]:
    lines = []
    if out.warnings:
        lines += [st.swap(x) for x in
                  _wrap(" warnings: " + " · ".join(out.warnings), st.width, "   ")]
    per = " · ".join(f"{n} {out.timings[n]:.1f}s" for n in
                     sorted(out.results, key=lambda n: out.results[n].order) if n in out.timings)
    disc = (f" research screener, not investment advice · survivorship-biased universe · "
            f"timings {out.timings.get('total', 0):.1f}s" + (f" ({per})" if per else ""))
    lines += [st.mark(st.swap(x), "dim") for x in _wrap(disc, st.width, "   ")]
    return lines


def render_report(out: RunOutput, ns: argparse.Namespace) -> str:
    """Header + layer statuses + macro card + ranked table + footer."""
    st = make_style(ns)
    blocks = [_header(st, out), ""]
    blocks += _layers_block(st, out) + [""]
    if out.ctx.regime is not None or "macro" in out.results:
        blocks += _macro_card(st, out) + [""]
    if out.decisions:
        blocks += _decisions_table(st, out, ns) + [""]
    elif "earnings" in out.results and "quality" not in out.results:
        blocks += _earnings_scorecard(st, out, ns) + [""]
    blocks += _footer(st, out)
    return "\n".join(blocks)


# ── § 6.5 · --explain: per-layer breakdown + fusion arithmetic + provenance
def _pillars_line(st: Style, sig: LayerSignal) -> list[str]:
    pillars = sig.facts.get("pillars") or {}
    names = [k for k in ("profitability", "growth", "financial_strength",
                         "earnings_quality", "valuation", "shareholder_yield") if k in pillars]
    out = []
    for i in range(0, len(names), 2):
        seg = []
        for k in names[i:i + 2]:
            v = pillars.get(k)
            seg.append(f"{k:<19}{_bar((v or 0) / 100, 8)} {v:.0f}" if isinstance(v, (int, float))
                       else f"{k:<19}{'–':>11}")
        out.append(st.swap("            " + "  ".join(seg)))
    return out or [st.swap("            pillars n/a")]


def _explain_block(st: Style, out: RunOutput, ns: argparse.Namespace, ticker: str) -> str:
    d = next((x for x in out.decisions if x.ticker == ticker), None)
    if d is None:
        sig = None
        for res in out.results.values():
            if ticker in res.signals:
                sig = res.signals[ticker]
        if sig is None:
            raise MasterError(f"--explain {ticker}: not in this run "
                               f"(tickers: {', '.join(c.ticker for c in out.ctx.tickers)})", 64)
    state = out.ctx.regime
    q = (d.layers.get("quality") if d else _res_signal(out, "quality", ticker))
    e = (d.layers.get("earnings") if d else _res_signal(out, "earnings", ticker))
    m = (d.layers.get("macro") if d else _res_signal(out, "macro", ticker))
    title = f"── {ticker} · {d.sector if d else '?'} · {d.action} {d.conviction:.0f} {d.grade}" if d else f"── {ticker}"
    lines = [st.mark(st.swap(title), "bold")]
    # L1
    if state is not None and state.status != "ERROR":
        lines.append(st.swap(f" L1 macro    {state.scenario_key} · {state.scenario_name} · "
                             f"conf {state.confidence:.2f} · lev {state.conviction_leverage:.2f}x "
                             f"(risk budget {out.ctx.risk_budget:.2f})"))
        lines.append(st.swap(f"             longs {' '.join(state.longs) or '–'} · shorts "
                             f"{' '.join(state.shorts) or '–'} · sleeve {' '.join(state.sleeve) or '–'}"))
        sec = (q.facts.get("macro_sector") if q else "") or (d.sector if d else "")
        mv = macro_view(state, sec)
        lines.append(st.swap(f"             {sec}: {mv['mapped'] or 'no ETF mapping'} → tilt "
                             f"{('–' if mv['tilt'] is None else format(mv['tilt'], '+.1f'))}, "
                             f"damp ×{mv['damp']:.1f} → conviction ×{mv['mult']:.3f}"))
    elif "macro" in out.results:
        lines.append(st.mark(st.swap(" L1 macro    MACRO UNAVAILABLE — no regime context"), "err"))
    # L2
    if q is not None:
        cov = q.facts.get("coverage")
        cov_s = "–" if cov is None else f"{cov:.0%}"
        head = (f" L2 quality  {_q_cell(q)} · rank {q.facts.get('rank') or '–'}/"
                f"{q.facts.get('pool_size') or '–'} {q.facts.get('sector') or '–'} · "
                f"coverage {cov_s} · "
                f"{q.facts.get('data_source') or '–'} · {q.status}")
        lines.append(st.swap(head))
        lines += _pillars_line(st, q)
        metrics = q.facts.get("metrics_top") or {}
        if metrics:
            lines.append(st.swap("             metrics  " + " · ".join(
                f"{k} {v:g}" for k, v in metrics.items())))
        if q.flags:
            lines.append(st.swap(f"             flags    {', '.join(q.flags)} "
                                 f"({'veto' if set(q.flags) & CONFIG['VETO_FLAGS'] else 'warning'})"))
    # L3
    if e is not None and out.ctx.flags.get("earnings_mode") != "off":
        if e.status == "OK":
            f = e.facts
            lines.append(st.swap(f" L3 earnings {e.score:.0f} {e.grade} · last4 {f.get('last4_big')}/4 big · "
                                 f"streak {f.get('streak_big')} · last big {f.get('last_big_date') or '–'} "
                                 f"{(f.get('last_big_pct') or 0):+.0f}% · p_next_big "
                                 f"{_pct(f.get('p_next_big'))}"))
            plan = f.get("plan")
            if plan:
                lines.append(st.swap(f"             plan {plan} @ {f.get('price') or 0:.2f} → target "
                                     f"{f.get('target') or 0:.2f} · stop {f.get('stop_px') or 0:.2f} · "
                                     f"exit by {f.get('exit_by') or '–'} · report {f.get('days_since') or '?'}d ago"))
            else:
                lines.append(st.swap("             plan n/a (as-of mode or no fresh price)"))
        else:
            lines.append(st.swap(f" L3 earnings {e.status} · {(e.warnings[0] if e.warnings else '')[:80]}"))
    # fusion arithmetic
    if d is not None:
        e_res = out.results.get("earnings")
        weak = bool(e_res is not None and e_res.ctx_out.get("weak"))
        qv = q.score if (q and q.status == "OK") else None
        ev = e.score if (e and e.status == "OK") else None
        m_sig = d.layers.get("macro")
        mult = m_sig.facts.get("mult", 1.0) if m_sig else 1.0
        if qv is not None:
            if ev is None:
                base_s = f"base = {qv:.0f} × {CONFIG['E_MISSING_HAIRCUT']:.2f} (E missing haircut)"
            elif weak:
                base_s = (f"base = ({CONFIG['W_Q']:.2f}×{qv:.0f} + {CONFIG['W_E']:.2f}×0.5×{ev:.0f})"
                          f" / {CONFIG['W_Q'] + CONFIG['W_E'] * 0.5:.3f} (E weak ×0.5)")
            else:
                base_s = f"base = {CONFIG['W_Q']:.2f}×{qv:.0f} + {CONFIG['W_E']:.2f}×{ev:.0f}"
            base = _base_conviction(qv, ev, weak)
            lines.append(st.swap(f" fusion      {base_s} = {base:.1f}"))
            lines.append(st.swap(f"             × macro {mult:.3f} → conviction {d.conviction:.1f} "
                                 f"→ {d.grade} → {d.action}"))
        if d.reasons:
            lines.append(st.swap("             reasons  " + " | ".join(d.reasons)))
    # provenance
    prov = []
    if state is not None:
        prov.append(f"macro: {state.data_tier or '–'}/{state.pit_mode or '–'} ({state.status})")
    if q is not None:
        prov.append(f"quality: {q.facts.get('data_source') or '–'} ({q.status}; engine {q.facts.get('engine_status')})")
    e_res = out.results.get("earnings")
    if e_res is not None:
        prov.append(f"earnings: yahoo ({e_res.status}; {e_res.ctx_out.get('verdict', '')[:60]})")
    if prov:
        lines.append(" provenance  " + " · ".join(prov))
    return "\n".join(st.swap(_fit(x, st.width)) for x in lines)


def _res_signal(out: RunOutput, layer: str, ticker: str) -> LayerSignal | None:
    res = out.results.get(layer)
    if res is None:
        return None
    if layer == "macro":
        return res.signals.get(ticker)    # per-ticker macro signals exist only via fusion
    return res.signals.get(ticker)


def _pct(x: Any) -> str:
    return "–" if x is None or x != x else f"{x * 100:.0f}%"


# ── § 6.9 · stable --json schema ─────────────────────────────────────────
def json_payload(out: RunOutput, ns: argparse.Namespace) -> dict[str, Any]:
    """One parseable object on stdout; keys are stable across releases."""
    state = out.ctx.regime
    layers = []
    for name in sorted(out.results, key=lambda n: out.results[n].order):
        res = out.results[name]
        entry: dict[str, Any] = {
            "name": name, "stage": res.stage, "order": res.order, "status": res.status,
            "engine_version": res.engine_version, "version_tested": res.version_tested,
            "elapsed_s": res.elapsed_s, "cache": res.cache,
            "warnings": list(res.warnings)[:8]}
        if name == "macro" and state is not None:
            entry["regime"] = {
                "scenario_key": state.scenario_key, "name": state.scenario_name,
                "class": state.regime_class, "cycle_phase": state.cycle_phase,
                "confidence": round(state.confidence, 4),
                "conviction_leverage": round(state.conviction_leverage, 3),
                "credit": state.credit, "quality": state.quality_tier,
                "data_tier": state.data_tier, "pit_mode": state.pit_mode,
                "effective_as_of": state.effective_as_of, "trade_month": state.trade_month,
                "longs": list(state.longs), "shorts": list(state.shorts),
                "sleeve": list(state.sleeve), "excluded": list(state.excluded)}
        if name == "earnings":
            entry["verdict"] = res.ctx_out.get("verdict")
            entry["weak"] = bool(res.ctx_out.get("weak"))
            entry["backtest"] = res.ctx_out.get("backtest")
        layers.append(entry)
    decisions = []
    for d in out.decisions:
        q, e, m = d.layers.get("quality"), d.layers.get("earnings"), d.layers.get("macro")
        decisions.append({
            "ticker": d.ticker, "sector": d.sector, "action": d.action,
            "conviction": d.conviction, "grade": d.grade, "weight": d.weight,
            "macro": {"tilt": (m.facts.get("tilt") if m else None),
                      "damp": (m.facts.get("damp") if m else 1.0),
                      "mult": (m.facts.get("mult") if m else 1.0),
                      "mapped": (m.facts.get("mapped") if m else "")},
            "quality": {"score": (q.score if q else None), "grade": (q.grade if q else "-"),
                        "status": (q.status if q else "MISSING"),
                        "engine_status": (q.facts.get("engine_status") if q else None),
                        "rank": (q.facts.get("rank") if q else None),
                        "pool": (q.facts.get("sector") if q else None),
                        "coverage": (q.facts.get("coverage") if q else None),
                        "flags": list(q.flags) if q else []},
            "earnings": {"score": (e.score if e else None), "grade": (e.grade if e else "-"),
                         "status": (e.status if e else "MISSING"),
                         "plan": (e.facts.get("plan") if e else None),
                         "now": bool(e.facts.get("now")) if e else False,
                         "p_next_big": (e.facts.get("p_next_big") if e else None)},
            "reasons": list(d.reasons)})
    return {
        "schema": 1, "master": __version__, "mode": str(getattr(ns, "mode", "")),
        "as_of": out.ctx.as_of, "live_date": (None if out.ctx.as_of else date.today().isoformat()),
        "macro_effective": (state.effective_as_of if state else None),
        "risk_budget": round(float(out.ctx.risk_budget), 3),
        "stubbed": out.stubbed,
        "disclaimer": "research screener, not investment advice; never a buy/sell "
                      "instruction or an alpha claim",
        "layers": layers, "decisions": decisions,
        "warnings": list(out.warnings),
        "timings": {k: round(v, 2) for k, v in out.timings.items()}}

# ════════════════════════════════════════════════════════════════════════
#  § 7 · CLI — argparse (flags only + tickers), exit codes, --check, --selftest
# ════════════════════════════════════════════════════════════════════════
class MasterParser(argparse.ArgumentParser):
    """argparse, but bad usage exits 64 (never 2)."""

    def error(self, message: str) -> None:                       # noqa: D102
        raise MasterError(f"{self.prog}: {message}", 64)


def build_parser() -> MasterParser:
    p = MasterParser(prog="master.py", description=__doc__.splitlines()[0])
    p.add_argument("tickers", nargs="*", metavar="TICKER")
    p.add_argument("--tickers", dest="tickers_csv", action="append", default=[],
                   metavar="A,B,C", help="comma list, repeatable")
    p.add_argument("--watchlist", metavar="FILE", help="one per line or CSV: ticker[,sector]")
    p.add_argument("--mode", choices=tuple(CONFIG["MODES"]),
                   default=CONFIG["MODE_DEFAULT"],
                   help="run preset: quick=watchlist-only quality ranks, ~minutes "
                        "even cold · standard (default)=sector-pool ranks, "
                        "minutes warm · deep=long budget + L3 top-40 + prefetch. "
                        "Sets --timeout/--peers/--earnings-top/--earnings-prefetch "
                        "unless passed explicitly")
    p.add_argument("--warm", action="store_true",
                   help="cache-fill run: macro+quality only, long budget "
                        "(WARM_TIMEOUT_S); fills the disk caches so the next "
                        "standard run is fast. Combine with --mode quick to "
                        "warm only the watchlist names")
    p.add_argument("--as-of", metavar="YYYY-MM-DD", help="point-in-time run, no lookahead")
    p.add_argument("--top", type=int, default=CONFIG["DEFAULT_TOP"], metavar="N",
                   help=f"table rows shown (default {CONFIG['DEFAULT_TOP']})")
    p.add_argument("--min-conviction", type=float, default=CONFIG["DEFAULT_MIN_CONV"],
                   metavar="X", help="hide rows below this conviction (table/csv)")
    p.add_argument("--only", default="", metavar="L1,L2", help="macro|quality|earnings (comma list)")
    p.add_argument("--skip", default="", metavar="L1,L2", help="macro|quality|earnings (comma list)")
    p.add_argument("--earnings-mode", choices=("off", "boost", "trigger"), default="boost",
                   help="off=skip L3 · boost (default)=score modifier + NOW chip · "
                        "trigger=plan LONG required for LONG")
    p.add_argument("--earnings-top", type=int, default=None, metavar="K",
                   help="earnings runs only on the top-K L1+L2 survivors "
                        "(mode default: quick 10 / standard 25 / deep 40)")
    p.add_argument("--earnings-backtest", action="store_true",
                   help="opt-in full 90-day price backtest per ticker (slow)")
    p.add_argument("--earnings-prefetch", choices=("none", "all"), default=None,
                   help="all: warm earnings histories at t=0 (<=60 names; deep mode default)")
    p.add_argument("--peers", choices=("builtin", "watchlist"), default=None,
                   help="quality comparison pool: builtin=sector peers (standard/deep) · "
                        "watchlist=the requested names only (quick; rough percentiles)")
    p.add_argument("--sector", action="append", default=[], metavar="T=GROUP",
                   help="pin a ticker's quality sector, e.g. --sector PLTR=tech")
    p.add_argument("--bucket", action="append", default=[], metavar="T=staples|discretionary",
                   help="split quality's merged consumer group for this ticker")
    p.add_argument("--source", choices=("auto", "fixtures", "sec", "yfinance"), default="auto",
                   help="passed through to quality")
    p.add_argument("--offline", action="store_true",
                   help="macro snapshot + engine caches only; no network from master")
    p.add_argument("--cache-dir", metavar="DIR",
                   help="redirect quality+earnings caches (QE_DATA_DIR/QE_CACHE_DIR set "
                        "before import; meds' location is fixed)")
    p.add_argument("--workers", type=int, default=CONFIG["DEFAULT_WORKERS"], metavar="N",
                   help=f"earnings pool (default {CONFIG['DEFAULT_WORKERS']}; keep <=4)")
    p.add_argument("--timeout", type=float, default=None, metavar="SEC",
                   help="per-layer wall-clock budget (mode default: quick 300 / "
                        "standard 900 / deep+warm 3600)")
    p.add_argument("--explain", metavar="TICKER", help="full per-layer breakdown for one ticker")
    p.add_argument("--json", action="store_true", help="one parseable JSON object on stdout")
    p.add_argument("--csv", metavar="FILE", help="opt-in CSV write (default run writes nothing)")
    p.add_argument("--no-color", action="store_true")
    p.add_argument("--ascii", action="store_true", help="plain ASCII (# - | v * !) output")
    p.add_argument("--width", type=int, help="terminal width 40..110")
    p.add_argument("--quiet", action="store_true", help="no [plan] banner, no live progress bar")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--check", action="store_true", help="health probe: versions, env names, caches, tiny requests")
    p.add_argument("--selftest", action="store_true", help="stubbed unittest, no network (LIVE SKIP for live checks)")
    p.add_argument("--version", action="store_true")
    return p


def _apply_mode(ns: argparse.Namespace) -> argparse.Namespace:
    """v1.1.0: fill the mode-driven defaults ONCE, right after parsing
    (idempotent — explicit flags always win, so tests/direct run_pipeline
    callers can call it again safely). --warm selects macro+quality and the
    long budget; a --skip that removes one of them is honoured."""
    if getattr(ns, "mode", None) is None:
        ns.mode = CONFIG["MODE_DEFAULT"]
    preset = CONFIG["MODES"].get(ns.mode) or CONFIG["MODES"][CONFIG["MODE_DEFAULT"]]
    warm = bool(getattr(ns, "warm", False))
    if warm and not getattr(ns, "only", ""):
        skip = {s.strip() for s in (getattr(ns, "skip", "") or "").split(",") if s.strip()}
        ns.only = ",".join(n for n in ("macro", "quality") if n not in skip)
    if getattr(ns, "timeout", None) is None:
        ns.timeout = CONFIG["WARM_TIMEOUT_S"] if warm else preset["timeout"]
    if getattr(ns, "peers", None) is None:
        ns.peers = preset["peers"]
    if getattr(ns, "earnings_top", None) is None:
        ns.earnings_top = preset["earnings_top"]
    if getattr(ns, "earnings_prefetch", None) is None:
        ns.earnings_prefetch = preset["earnings_prefetch"]
    return ns


def _validate_ns(ns: argparse.Namespace) -> None:
    """Fail fast on bad values, BEFORE any network call or engine import.
    Mode-driven defaults may still be unset here (None) — _apply_mode fills
    them; the range checks only run on explicitly passed values."""
    if ns.as_of:
        try:
            d = date.fromisoformat(ns.as_of)
        except ValueError:
            raise MasterError(f"--as-of {ns.as_of!r}: expected YYYY-MM-DD", 64) from None
        if d > date.today():
            raise MasterError(f"--as-of {ns.as_of} is in the future "
                              "(quality rejects future dates; no lookahead)", 64)
    if ns.json and ns.explain:
        raise MasterError("--explain is a terminal view; incompatible with --json", 64)
    if ns.top < 1 or ns.min_conviction < 0 or ns.min_conviction > 100:
        raise MasterError("--top must be >=1 and --min-conviction in 0..100", 64)
    if ((ns.earnings_top is not None and ns.earnings_top < 0)
            or (ns.workers is not None and ns.workers < 1)
            or (ns.timeout is not None and ns.timeout < 1)):
        raise MasterError("--earnings-top/--workers/--timeout must be positive", 64)
    if ns.width is not None and not 40 <= ns.width <= 110:
        raise MasterError(f"--width {ns.width}: out of range 40..110", 64)


def _write_csv(path: str, out: RunOutput, ns: argparse.Namespace) -> str:
    """Opt-in write; applies the same --top/--min-conviction filters as the table."""
    import csv
    p = Path(path)
    if str(p.parent):
        p.parent.mkdir(parents=True, exist_ok=True)
    rows = [d for d in out.decisions if d.conviction >= float(ns.min_conviction)][:int(ns.top)]
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["rank", "ticker", "sector", "action", "conviction", "grade",
                    "macro_tilt", "now", "q_score", "q_grade", "q_status", "e_score",
                    "e_grade", "e_status", "plan", "p_next_big", "flags", "reasons", "weight"])
        for i, d in enumerate(rows, 1):
            q, e, m = d.layers.get("quality"), d.layers.get("earnings"), d.layers.get("macro")
            w.writerow([i, d.ticker, d.sector, d.action, d.conviction, d.grade,
                        (m.facts.get("tilt") if m else None),
                        bool(e.facts.get("now")) if e else False,
                        (q.score if q else None), (q.grade if q else "-"),
                        (q.status if q else "MISSING"),
                        (e.score if e else None), (e.grade if e else "-"),
                        (e.status if e else "MISSING"),
                        (e.facts.get("plan") if e else None),
                        (e.facts.get("p_next_big") if e else None),
                        ";".join(q.flags) if q else "", " | ".join(d.reasons), d.weight])
    return str(p)


def _probe(url: str, ua: str | None = None) -> str:
    """One tiny read-only request per source; secrets redacted."""
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua or "master.py/1.0"})
        with urllib.request.urlopen(req, timeout=CONFIG["PROBE_TIMEOUT_S"]) as r:
            r.read(2048)
            code = getattr(r, "status", 200) or 200
        return f"OK ({code}; {(time.monotonic() - t0) * 1000:.0f} ms)"
    except Exception as e:
        return f"FAIL: {_exc(e)[:100]}"


def run_check(ns: argparse.Namespace) -> int:
    """Health probe: engine versions, env KEY NAMES (never values), cache
    dirs, one tiny request per source (skipped with --offline)."""
    st = make_style(ns)
    print(st.mark(f"master v{__version__} --check", "head"))
    imported = 0
    for name, mod_name in (("meds", "meds"), ("quality", "quality"),
                            ("earnings", "earnings_engine")):
        try:
            mod = importlib.import_module(mod_name)
        except Exception as e:
            print(f"  {name:<9} IMPORT FAILED — {_exc(e)}")
            continue
        imported += 1
        ver, tested, differs = _engine_version(name, mod)
        note = "tested" if not differs else f"DIFFERS from tested {tested}"
        extra = "" if name != "earnings" or hasattr(mod, "__version__") else " (no __version__ attr; drift undetectable)"
        print(f"  {name:<9} v{ver:<8} {note}{extra}")
    print("  env (names only, never values): " + " · ".join(
        f"{v}={'set' if os.environ.get(v) else 'absent'}"
        for v in ("FREDAPI", "FRED_API_KEY", "SEC_USER_AGENT", "FINNHUB_API_KEY")))
    dirs: list[tuple[str, str]] = []
    try:
        import meds as _m
        dirs.append(("meds_cache", str(Path(_m.__file__).parent / "meds_cache")))
    except Exception:
        pass
    try:
        import quality as _q
        dirs.append(("quality cache", str(getattr(_q, "CACHE_DIR", "data/cache"))))
    except Exception:
        pass
    dirs.append(("earnings cache", os.path.join(str(ns.cache_dir), "earnings") if ns.cache_dir
                 else str(Path.home() / ".earnings_engine_cache")))
    for label, p in dirs:
        exists, newest = _dir_stamp(p)
        age = "new" if not newest else f"{(time.time() - newest) / 3600:.1f}h old"
        print(f"  {label:<14} {p} — {'present' if exists else 'absent'} ({age})")
    try:
        import quality as _q
        refs, _rep = _q.get_universe()
        active = sum(1 for r in refs if getattr(r, "status", "") == "active")
        print(f"  quality universe: {len(refs)} entries ({active} active) — a "
              "watchlist spanning all sectors scores all of them (standard mode)")
    except Exception:
        pass
    if ns.offline:
        print("  probes skipped (--offline)")
        return 0 if imported else 2
    for label, url, ua in (
            ("FRED public CSV", "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF", None),
            ("SEC EDGAR", "https://www.sec.gov/",
             os.environ.get("SEC_USER_AGENT") or "master.py health probe (set SEC_USER_AGENT)"),
            ("Yahoo chart", "https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=1d&interval=1d",
             "Mozilla/5.0 master.py health probe")):
        print(f"  {label:<14} {_probe(url, ua)}")
    return 0 if imported else 2


def run_selftest() -> int:
    """stdlib unittest over this module; live checks print LIVE SKIP."""
    import unittest
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if res.wasSuccessful() else 1


def _cli_run(ns: argparse.Namespace) -> int:
    out = run_pipeline(ns)
    if ns.json:
        sys.stdout.write(json.dumps(json_payload(out, ns), indent=2, default=str) + "\n")
    else:
        sys.stdout.write(render_report(out, ns) + "\n")
        if ns.explain:
            t = _norm_ticker(ns.explain) or ns.explain
            sys.stdout.write(_explain_block(make_style(ns), out, ns, t) + "\n")
    if ns.csv:
        sys.stderr.write(f"csv -> {_write_csv(ns.csv, out, ns)}\n")
    if getattr(ns, "warm", False):
        qdir = str(getattr(sys.modules.get("quality"), "CACHE_DIR", "")
                   or os.path.join(os.environ.get("QE_DATA_DIR", "data"), "cache"))
        age = _cache_age_h(qdir)
        state = "filled (last write just now)" if age is not None and age < 0.2 \
                else (f"last write {age:.1f}h ago" if age is not None else "still COLD")
        sys.stderr.write("warm-up done — quality cache " + state
                         + "; next: python master.py (warm run ≈ minutes;"
                           " add --mode quick for the fast pass)\n")
    if out.exit_code == 2:
        sys.stderr.write(out.exit_reason + "\n")
    return out.exit_code


def main(argv: list[str] | None = None) -> int:
    """Exit codes: 0 ok (DEGRADED included) · 1 unexpected · 2 no result/NO-GO ·
    64 bad usage (before any network call) · 130 Ctrl-C (names the phase)."""
    ns: argparse.Namespace | None = None
    try:
        ns = _apply_mode(build_parser().parse_args(argv))
        _validate_ns(ns)
        if ns.selftest:
            return run_selftest()
        if ns.version:
            print(f"master v{__version__} · tested engines: "
                  + ", ".join(f"{k} {v}" for k, v in CONFIG["TESTED_VERSIONS"].items()))
            return 0
        if ns.check:
            return run_check(ns)
        return _cli_run(ns)
    except KeyboardInterrupt:
        sys.stderr.write(f"\n^C interrupted during: {phase_name()} — exit 130\n")
        return 130
    except MasterError as e:
        sys.stderr.write(f"master: {e}\n")
        return e.code
    except Exception as e:
        if ns is not None and getattr(ns, "verbose", False):
            import traceback
            traceback.print_exc()
        sys.stderr.write(f"master: unexpected {type(e).__name__}: {_exc(e)}\n")
        return 1


# ════════════════════════════════════════════════════════════════════════
#  § 8 · SELFTEST — stub adapters + fake engine modules; NO network; live
#         checks print LIVE SKIP and never fake data
# ════════════════════════════════════════════════════════════════════════
import tempfile
import unittest

FAKE_GROUPS: dict[str, list[str]] = {
    "tech": ["MU", "NVDA", "AVGO", "INTC", "TXN", "QCOM", "AMAT", "LRCX", "ADI", "KLAC"],
    "consumer": ["COST", "HD", "TSLA", "KO", "PG", "WMT", "MCD", "NKE", "TJX", "LOW"],
    "financials": ["JPM", "BAC", "WFC"], "healthcare": ["UNH", "LLY", "JNJ"],
    "energy": ["XOM", "CVX", "COP"], "industrials": ["CAT", "HON", "UNP"],
    "utilities": ["NEE", "DUK", "SO"], "materials": ["LIN", "SHW", "APD"],
    "reits": ["PLD", "AMT", "SPG"], "communication": ["VZ", "TMUS", "META"],
    "specialty": ["HRB", "MAN", "LDOS"],
}
SECTOR_MAP = {"AAPL": "tech", "AMD": "tech", "META": "communication", "TSLA": "consumer",
              "AMZN": "consumer", "BRK-B": "financials", "V": "financials",
              "MA": "financials", "GOOGL": "tech", "MSFT": "tech", "NVDA": "tech"}

STUB_Q_TABLE: dict[str, tuple] = {   # ticker -> (score|None, engine_status, flags, sector)
    "MU": (72, "OK", (), "tech"), "NVDA": (80, "OK", ("HIGH_ACCRUALS",), "tech"),
    "AAPL": (88, "OK", (), "tech"), "AMD": (58, "OK", (), "tech"),
    "META": (84, "OK", (), "communication"), "COST": (86, "OK", (), "consumer"),
    "JPM": (76, "OK", (), "financials"), "UNH": (77, "OK", (), "healthcare"),
    "XOM": (74, "OK", (), "energy"), "CAT": (69, "OK", (), "industrials"),
    "NEE": (71, "OK", (), "utilities"), "LIN": (79, "OK", (), "materials"),
    "PLD": (73, "OK", (), "reits"), "VZ": (70, "OK", (), "communication"),
    "TSLA": (62, "OK", (), "consumer"), "HRB": (64, "OK", (), "specialty"),
    "XYZ": (52, "OK", ("SPLIT_BASIS_UNVERIFIED",), "tech"),
    "VETO1": (66, "OK", ("NEGATIVE_EQUITY",), "tech"),
    "STALE1": (None, "STALE_DATA", (), "tech"), "NODATA1": (None, "NO_DATA", (), "tech"),
}
STUB_E_TABLE: dict[str, tuple | None] = {  # ticker -> (score, rating, plan, days) | None
    "MU": (81, "A", "LONG", 4), "NVDA": (44, "C", "SKIP", 40), "AAPL": None,
    "AMD": (58, "B", "WATCH", 23), "META": (66, "B", "LONG", 9),
    "COST": (71, "A", "WATCH", 30), "JPM": (55, "B", "SKIP", 44),
}

_MACRO_NOW = {"scenario_key": "SOFT_LANDING_PIVOT", "name": "Soft Landing / Policy Pivot",
              "confidence": 0.82, "dominance": 0.35, "cycle_phase": "Mid Cycle",
              "conviction_leverage": 1.35, "as_of": "2026-10-31", "data_tier": "public",
              "pit_mode": "approximate_pit_lag", "next_trade_month": "2026-12",
              "credit_signal": "ON", "regime_class": "risk_on", "status": "OK",
              "credit": "ON", "quality": "MED", "month": "2026-12", "version": "14.7.0",
              "warnings": [], "errors": [],
              "basket": {"longs": ["S&P 500 (SPY)", "Nasdaq 100 (QQQ)", "Consumer Disc. (XLY)"],
                         "shorts": []},
              "runner_up": "LATE_CYCLE_OVERHEATING", "excluded_scenarios": []}
_MACRO_RR = {"scenario_key": "INFLATION_SHOCK", "name": "Inflation Shock",
             "confidence": 0.74, "dominance": 0.28, "cycle_phase": "Late Cycle",
             "conviction_leverage": 1.1, "as_of": "2026-05-31", "data_tier": "public",
             "pit_mode": "approximate_pit_lag", "next_trade_month": "2026-07",
             "credit_signal": "ON", "warnings": [], "errors": [],
             "basket": {"longs": ["Energy (XLE)", "Commodities (DBC)", "T-Bills (BIL)"],
                        "shorts": ["Long Treasuries (TLT)"]}}


def _sector_of(t: str) -> str:
    if t in SECTOR_MAP:
        return SECTOR_MAP[t]
    for g, names in FAKE_GROUPS.items():
        if t in names:
            return g
    return "tech"


def _stub_q_row(t: str) -> tuple:
    r = STUB_Q_TABLE.get(t)
    if r is not None:
        return r
    return (25 + (sum(map(ord, t)) * 7) % 61, "OK", (), _sector_of(t))


def _stub_q_raw(t: str) -> dict:
    score, word, flags, sector = _stub_q_row(t)
    return {"ticker": t, "as_of": "2026-11-08", "sector": sector, "score": score,
            "pillars": {"profitability": 71, "growth": 66, "financial_strength": 74,
                        "earnings_quality": 69, "valuation": 58, "shareholder_yield": 61},
            "coverage": 0.78, "flags": list(flags), "rank_in_sector": 3, "status": word,
            "data_source": "sec+chart", "model": "default",
            "metrics": {"roic": 14.2, "gross_profitability": 0.31, "operating_margin": 18.4,
                        "fcf_margin": 19.1, "net_debt_ebitda": 0.4, "altman_z": 4.1,
                        "ebitda_yield": 6.2, "fcf_yield": 4.1, "accruals_ratio": -0.02,
                        "shareholder_yield": 2.3},
            "notes": [], "error": None}


def _stub_e_row(t: str) -> tuple | None:
    r = STUB_E_TABLE.get(t)
    if r is None and t in STUB_E_TABLE:
        return None
    if r is None:
        r = (40 + (sum(map(ord, t)) * 5) % 45, "B", "SKIP", 60)
    return r


def _stub_last(as_of: str | None) -> "date":
    return date(2026, 5, 20) if as_of else date(2026, 10, 28)


# ── § 8.2 · fake engine modules (real adapters run against these) ────────
def _fake_meds(log: dict, raise_in: tuple = ()) -> types.ModuleType:
    mod = types.ModuleType("meds")
    mod.__version__ = "14.7.0"
    mod.FORCE_SNAPSHOT = False

    def now(cfg=None):
        log.setdefault("now", []).append(cfg)
        if "now" in raise_in:
            raise RuntimeError("meds now boom")
        return dict(_MACRO_NOW)

    def regime_now(as_of=None, live=True, data=None, cfg=None):
        log.setdefault("regime_now", []).append(as_of)
        if "regime_now" in raise_in:
            raise RuntimeError("meds regime boom")
        return dict(_MACRO_RR)

    mod.now, mod.regime_now = now, regime_now
    return mod


def _fake_quality(log: dict, raise_tickers: tuple = ()) -> types.ModuleType:
    mod = types.ModuleType("quality")
    mod.ENGINE_VERSION = "3.4.1"

    class _Ref:
        def __init__(self, ticker, sector, status="active", note="", evidence=""):
            self.ticker, self.sector = ticker, sector
            self.status, self.note, self.evidence = status, note, evidence

    mod.TickerRef = _Ref
    mod.GROUPS = FAKE_GROUPS

    def normalize_ticker(text):
        cand = (text or "").strip().upper().replace(".", "-")
        return cand if re.fullmatch(r"[A-Z0-9][A-Z0-9-]{0,11}", cand) else None

    def build_inline_universe(ticker, sector_arg=None, peers_arg=None, full=False):
        t = normalize_ticker(ticker)
        if t is None:
            return (None, None, None, [], "bad ticker")
        sector = sector_arg or _sector_of(t)
        if peers_arg:
            peers = [p for p in peers_arg.split(",") if p and p != t]
        else:
            peers = [p for p in FAKE_GROUPS.get(sector, []) if p != t]
        refs = [_Ref(t, sector)] + [_Ref(p, sector) for p in peers]
        return refs, sector, f"{len(peers)} peers", [], None

    def get_quality_score(ticker, as_of=None, *, source="auto", universe_file=None,
                          universe_refs=None, progress=None):
        t = normalize_ticker(ticker)
        log.setdefault("quality", []).append(
            {"ticker": t, "as_of": as_of, "source": source, "refs": universe_refs})
        if t in raise_tickers:
            raise RuntimeError(f"quality boom {t}")
        raw = _stub_q_raw(t)
        raw["as_of"] = as_of or "2026-11-08"
        return raw

    mod.normalize_ticker = normalize_ticker
    mod.build_inline_universe = build_inline_universe
    mod.get_quality_score = get_quality_score
    mod.CACHE_DIR = os.environ.get("QE_CACHE_DIR") or "data/cache"
    return mod


def _fake_earnings(log: dict, future: bool = False, raise_in: bool = False) -> types.ModuleType:
    import pandas as pd
    mod = types.ModuleType("earnings_engine")           # like the real one: no __version__

    class _Eng:
        def __init__(self, quarters=40, workers=4, cache_dir=None, **kw):
            self.errors: dict = {}
            self.quarters, self.workers, self.cache_dir = quarters, workers, cache_dir
            self._fetch = self._px_fetch = None

        def analyze(self, tickers, as_of=None, accuracy=True, trade=False, **kw):
            log.setdefault("analyze", []).append(
                {"tickers": list(tickers), "as_of": as_of, "trade": trade})
            if raise_in:
                raise RuntimeError("earnings analyze boom")
            last = _stub_last(as_of) if not future else date(2026, 10, 28)
            rows = {}
            for t in tickers:
                r = _stub_e_row(t)
                if r is None:
                    self.errors[t] = "fewer than 4 usable quarters"
                    continue
                score, rating, _plan, days = r
                rows[t] = {"score": float(score), "rating": rating, "last_date": last,
                           "n_quarters": 40, "last4_big": 3, "streak_big": 2,
                           "qtrs_since_big": 1.0, "last_big_date": last, "last_big_pct": 24.0,
                           "latest_surprise_pct": 18.0, "beat_rate": 0.9, "p_next_big": 0.62,
                           "confidence": 1.0}
            scores = (pd.DataFrame.from_dict(rows, orient="index")
                      .sort_values("score", ascending=False)) if rows else pd.DataFrame()
            acc = pd.Series({"n_tests": 240, "n_tickers": 12, "base_big_beat_rate": 0.25,
                             "big_rate_when_score>=50": 0.45, "n_score>=50": 40,
                             "lift_vs_base": 1.8, "rank_corr_score_vs_next_surprise": 0.3,
                             "auc": 0.61, "auc_lo": 0.58, "auc_hi": 0.65, "auc_naive": 0.57})
            return types.SimpleNamespace(scores=scores, accuracy=acc, plan=pd.DataFrame(),
                                         backtest=pd.DataFrame(), trades=[])

        def plan(self, scores, min_score=50.0, hold_days=90, take_profit=0.15,
                 stop=None, max_age_days=10, **kw):
            log.setdefault("plan", []).append(list(scores.index))
            rows = {}
            for t in scores.index:
                r = _stub_e_row(t) or (50, "B", "SKIP", 60)
                score, rating, plan_s, days = r
                price = 100.0 + (sum(map(ord, t)) % 90)
                rows[t] = {"status": plan_s, "score": float(score), "rating": rating,
                           "last_report": date(2026, 10, 28), "days_since": days,
                           "price": price, "target": round(price * 1.15, 2),
                           "stop_px": round(price * 0.90, 2), "exit_by": date(2027, 2, 5)}
            return pd.DataFrame.from_dict(rows, orient="index")

    mod.EarningsEngine = _Eng
    return mod


_MISSING = object()


class _Mods:
    """Install fake engine modules into sys.modules for one test (restored after)."""

    def __init__(self, meds=None, quality=None, earnings=None):
        self.want = {"meds": meds, "quality": quality, "earnings_engine": earnings}
        self.saved: dict[str, object] = {}

    def __enter__(self) -> "_Mods":
        for name, mod in self.want.items():
            self.saved[name] = sys.modules.get(name, _MISSING)
            if mod is not None:
                sys.modules[name] = mod
        return self

    def __exit__(self, *exc) -> bool:
        for name in self.want:
            prev = self.saved.get(name, _MISSING)
            if prev is _MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = prev
        return False


def _ns(argv: list[str], **over) -> argparse.Namespace:
    ns = _apply_mode(build_parser().parse_args(argv))
    _validate_ns(ns)
    for k, v in over.items():
        setattr(ns, k, v)
    return ns


def _run(argv: list[str], mods: dict[str, types.ModuleType] | None = None, stubs: bool = False,
         **over) -> RunOutput:
    """run_pipeline with fake engine modules (keyword: meds/quality/earnings)
    and/or MASTER_STUBS, in-process."""
    old = os.environ.get("MASTER_STUBS")
    os.environ["MASTER_STUBS"] = "1" if stubs else "0"
    try:
        with _Mods(**(mods or {})):
            return run_pipeline(_ns(argv, **over))
    finally:
        if old is None:
            os.environ.pop("MASTER_STUBS", None)
        else:
            os.environ["MASTER_STUBS"] = old


# ── § 8.3 · stub layers (MASTER_STUBS=1: deterministic, no engine, no network)
class StubMacroLayer(LayerBase):
    name = "macro"
    order = 1
    stage = "gate"

    def run(self, ctx: Context, cands: list[Candidate]) -> LayerResult:
        res = self._begin("14.7.0", "14.7.0")
        st = MacroState(status="OK", scenario_key="SOFT_LANDING_PIVOT",
                        scenario_name="Soft Landing / Policy Pivot", regime_class="risk_on",
                        cycle_phase="Mid Cycle", confidence=0.82, dominance=0.35,
                        conviction_leverage=1.35, credit="OFF", quality_tier="MED",
                        data_tier="public", pit_mode="approximate_pit_lag",
                        effective_as_of=(month_end_floor(ctx.as_of) if ctx.as_of else "2026-10-31"),
                        trade_month="2026-12", longs=("SPY", "QQQ", "XLY"), shorts=(), sleeve=(),
                        excluded=("CREDIT_CRUNCH", "EARLY_CYCLE_RE_ACCELERATION"),
                        source="stub", engine_version="14.7.0")
        res.status, res.cache = "OK", "warm"
        res.ctx_out = {"macro": st, "risk_budget": _risk_budget(st)}
        return res


class StubQualityLayer(LayerBase):
    name = "quality"
    order = 2
    stage = "score"

    def run(self, ctx: Context, cands: list[Candidate]) -> LayerResult:
        res = self._begin("3.4.1", "3.4.1")
        for cand in ctx.tickers:
            raw = _stub_q_raw(cand.ticker)
            raw["_pool_size"] = 41 if raw["sector"] == "tech" else 30
            res.signals[cand.ticker] = _quality_signal(cand, raw)
        res.cache = "warm"
        res.ctx_out = {"scored": sum(1 for s in res.signals.values() if s.status == "OK"),
                       "total": len(res.signals)}
        res.status = "DEGRADED" if any(s.status != "OK" for s in res.signals.values()) else "OK"
        return res


class StubEarningsLayer(LayerBase):
    name = "earnings"
    order = 3
    stage = "score"

    def run(self, ctx: Context, cands: list[Candidate]) -> LayerResult:
        res = self._begin("3", "3")
        last = _stub_last(ctx.as_of)
        for cand in cands:
            r = _stub_e_row(cand.ticker)
            if r is None:
                res.signals[cand.ticker] = LayerSignal(
                    cand.ticker, "earnings", status="MISSING", facts={"plan": None, "now": False},
                    warnings=("no earnings history (<4 quarters or provider failed)",),
                    source="stub", as_of=ctx.as_of or "")
                continue
            score, rating, plan_s, days = r
            price = 100.0 + (sum(map(ord, cand.ticker)) % 90)
            row = {"score": float(score), "rating": rating, "last_date": last,
                   "n_quarters": 40, "last4_big": 3, "streak_big": 2, "qtrs_since_big": 1.0,
                   "last_big_date": last, "last_big_pct": 24.0, "latest_surprise_pct": 18.0,
                   "beat_rate": 0.9, "p_next_big": 0.62, "confidence": 1.0}
            plan_row = None if ctx.as_of else {
                "status": plan_s, "price": price, "target": round(price * 1.15, 2),
                "stop_px": round(price * 0.9, 2), "days_since": days,
                "exit_by": date(2027, 2, 5), "last_report": last}
            res.signals[cand.ticker] = _earnings_signal(cand.ticker, row, plan_row, None, ctx.as_of)
        res.cache = "warm"
        missing = [t for t, s in res.signals.items() if s.status != "OK"]
        res.status = "DEGRADED" if missing else "OK"
        res.ctx_out = {"verdict": "SIGNAL: high-rated names hit big beats 1.80x more often than base",
                       "weak": False, "missing": missing,
                       "scored": len(res.signals) - len(missing), "backtest": None}
        return res


# ── § 8.4 · fusion unit tests (pure functions, hand-built signals) ───────
def _mstate(key="SOFT_LANDING_PIVOT", cls="risk_on", longs=("SPY", "QQQ", "XLY"),
            credit="ON", status="OK", lev=1.35) -> MacroState:
    return MacroState(status=status, scenario_key=key, scenario_name=key.replace("_", " ").title(),
                      regime_class=cls, cycle_phase="Mid Cycle", confidence=0.82,
                      conviction_leverage=lev, credit=credit, quality_tier="MED",
                      data_tier="public", effective_as_of="2026-10-31", trade_month="2026-12",
                      longs=tuple(longs), source="test", engine_version="14.7.0")


def _sig(layer: str, score=None, status="OK", flags=(), facts=None) -> LayerSignal:
    base_f = {"engine_status": status, "sector": "tech", "macro_sector": "tech",
              "rank": 3, "pool_size": 41, "coverage": 0.78, "pillars": {},
              "data_source": "sec+chart", "metrics_top": {}, "notes": []}
    if facts:
        base_f.update(facts)
    return LayerSignal("T", layer, score=score,
                       status=("OK" if (status == "OK" and score is not None) else
                               ("ERROR" if status == "ERROR" else "MISSING")),
                       grade=(_native_grade("QUALITY_NATIVE_GRADES", score) if layer == "quality"
                              and score is not None else
                              (_native_grade("EARNINGS_NATIVE_GRADES", score) if layer == "earnings"
                               and score is not None else "-")),
                       flags=tuple(flags), facts=base_f, warnings=tuple(flags), as_of="2026-11-08")


class TestFusionGates(unittest.TestCase):
    """Gate table: each veto/threshold boundary (§9 selftest list)."""

    def _d(self, q, flags=(), status="OK", e=None, mode="boost"):
        cand = Candidate("T")
        q_sig = (None if q is None and status == "ABSENT"
                 else _sig("quality", q, status=status, flags=flags))
        e_sig = _sig("earnings", e) if e is not None else None
        return fuse_candidate(cand, q_sig, e_sig, _mstate(), mode, False)

    def test_below_gate(self):
        for q in (39.9, 20):
            d = self._d(q, e=60)
            self.assertEqual(d.action, "AVOID")
            self.assertIn("gate", d.reasons[0])

    def test_at_gate_boundary(self):
        d = self._d(40, e=60)
        self.assertNotEqual(d.action, "AVOID")       # 40.0 passes (>=)
        self.assertTrue(all("gate" not in r and "veto" not in r for r in d.reasons))

    def test_vetoes(self):
        for flag in ("NEGATIVE_EQUITY", "ALTMAN_DISTRESS"):
            d = self._d(88, flags=(flag,), e=81)
            self.assertEqual(d.action, "AVOID")
            self.assertIn(flag, d.reasons[0])

    def test_no_score_never_imputed(self):
        for word in ("STALE_DATA", "NO_DATA", "INSUFFICIENT_DATA"):
            d = self._d(None, status=word, e=81)
            self.assertEqual(d.action, "AVOID")
            self.assertIn(f"no quality score: {word}", d.reasons[0])
            self.assertIsNone(d.layers["quality"].score)

    def test_other_flags_are_warnings_only(self):
        d = self._d(88, flags=("HIGH_ACCRUALS", "SPLIT_BASIS_UNVERIFIED"), e=81)
        self.assertNotEqual(d.action, "AVOID")
        self.assertIn("HIGH_ACCRUALS", d.layers["quality"].warnings)


class TestMonotonicity(unittest.TestCase):
    """Improving Q or E never lowers conviction; improving tilt never lowers it."""

    def test_q_monotone(self):
        convs = [fuse_candidate(Candidate("T"), _sig("quality", q), _sig("earnings", 60),
                                _mstate(), "boost", False).conviction
                 for q in range(40, 95, 10)]
        self.assertEqual(convs, sorted(convs))
        self.assertTrue(all(a <= b for a, b in zip(convs, convs[1:])))

    def test_e_monotone(self):
        for weak in (False, True):
            convs = [fuse_candidate(Candidate("T"), _sig("quality", 70), _sig("earnings", e),
                                    _mstate(), "boost", weak).conviction
                     for e in range(0, 95, 10)]
            self.assertEqual(convs, sorted(convs), f"weak={weak}")

    def test_tilt_monotone(self):
        states = [_mstate("HARD_LANDING", "defensive", longs=()),
                  _mstate("NEUTRAL_WAIT_AND_SEE", "neutral", longs=()),
                  _mstate(longs=("SPY",)),
                  _mstate(longs=("QQQ",))]
        convs = [fuse_candidate(Candidate("T"), _sig("quality", 70), _sig("earnings", 60),
                                s, "boost", False).conviction for s in states]
        self.assertEqual(convs, sorted(convs))


class TestTiltMapping(unittest.TestCase):
    """Tilt mapping incl. macro-silent None (healthcare/fin/reits/spec)."""

    def test_soft_landing(self):
        s = _mstate(longs=("SPY", "QQQ", "XLY"))
        tilts = {sec: macro_tilt(s, sec) for sec in CONFIG["SECTOR_ORDER"]}
        self.assertEqual(tilts["tech"], 1.0)
        self.assertEqual(tilts["communication"], 1.0)
        self.assertEqual(tilts["consumer"], 1.0)
        self.assertEqual(tilts["industrials"], 0.5)   # weak SPY
        self.assertEqual(tilts["energy"], 0.5)
        self.assertEqual(tilts["utilities"], 0.5)
        self.assertEqual(tilts["materials"], 0.5)
        for sec in ("healthcare", "financials", "reits", "specialty"):
            self.assertIsNone(tilts[sec], sec)        # macro-silent, never 0

    def test_inflation_shock(self):
        s = _mstate("INFLATION_SHOCK", "risk_on", longs=("XLE", "DBC", "BIL"))
        self.assertEqual(macro_tilt(s, "energy"), 1.0)
        self.assertEqual(macro_tilt(s, "materials"), 0.5)
        self.assertEqual(macro_tilt(s, "tech"), 0.0)  # mapped, not long, not defensive

    def test_defensive_caps(self):
        s = _mstate("HARD_LANDING", "defensive", longs=("XLU", "XLP"))
        self.assertEqual(macro_tilt(s, "utilities"), 1.0)
        self.assertEqual(macro_tilt(s, "consumer"), 1.0)
        for sec in ("tech", "industrials", "materials", "communication"):
            self.assertEqual(macro_tilt(s, sec), -0.5, sec)
        self.assertEqual(macro_tilt(s, "energy"), 0.0)     # cyclical list excludes energy
        self.assertIsNone(macro_tilt(s, "financials"))     # silent even in defensive

    def test_sleeve_split(self):
        st = _parse_macro(dict(_MACRO_RR), "regime_now", "14.7.0")
        self.assertEqual(st.longs, ("XLE", "DBC"))         # BIL is the sleeve
        self.assertEqual(st.sleeve, ("BIL",))
        self.assertEqual(st.shorts, ("TLT",))
        st2 = _parse_macro(dict(_MACRO_NOW), "now", "14.7.0")
        self.assertEqual(st2.longs, ("SPY", "QQQ", "XLY"))


class TestDegradedDamp(unittest.TestCase):
    """DEGRADED / credit OFF halves the tilt EFFECT, not the shown tilt."""

    def test_damp(self):
        ok = _mstate()
        deg = _mstate(status="DEGRADED")
        off = _mstate(credit="OFF")
        mk = lambda s: fuse_candidate(Candidate("T"), _sig("quality", 70),
                                      _sig("earnings", 60), s, "boost", False)
        base = CONFIG["W_Q"] * 70 + CONFIG["W_E"] * 60   # 66.5
        c_ok, c_deg, c_off = mk(ok).conviction, mk(deg).conviction, mk(off).conviction
        self.assertAlmostEqual(c_ok, round(base * 1.10, 1), places=2)
        self.assertAlmostEqual(c_deg, round(base * 1.05, 1), places=2)
        self.assertEqual(c_deg, c_off)
        self.assertLess(c_deg, c_ok)
        for s in (ok, deg, off):
            self.assertEqual(macro_view(s, "tech")["tilt"], 1.0)   # shown tilt unchanged
        self.assertNotIn("damped", mk(ok).reasons[1])
        for s in (deg, off):
            self.assertIn("damped", mk(s).reasons[1])


class TestFailureIsolation(unittest.TestCase):
    """An adapter that raises never kills the run; a ticker failure never
    kills its layer (§9)."""

    DEMO = ["MU", "NVDA", "--timeout", "30"]

    def test_meds_error_rest_runs(self):
        log: dict = {}
        mods = {"meds": _fake_meds(log, raise_in=("now",)),
                "quality": _fake_quality(log), "earnings": _fake_earnings(log)}
        out = _run(self.DEMO, mods=mods)
        self.assertEqual(out.results["macro"].status, "ERROR")
        self.assertTrue(out.decisions)
        self.assertEqual(out.exit_code, 0)                 # quality produced results
        self.assertTrue(any("MACRO UNAVAILABLE" in w for w in out.warnings))
        for d in out.decisions:
            self.assertIsNone(d.layers["macro"].facts.get("tilt"))

    def test_one_ticker_quality_error(self):
        log: dict = {}
        mods = {"meds": _fake_meds(log), "quality": _fake_quality(log, raise_tickers=("MU",)),
                "earnings": _fake_earnings(log)}
        out = _run(self.DEMO, mods=mods)
        self.assertEqual(out.results["quality"].signals["MU"].status, "ERROR")
        self.assertEqual(out.results["quality"].signals["NVDA"].status, "OK")
        self.assertEqual(out.results["quality"].status, "DEGRADED")
        self.assertEqual(out.exit_code, 0)

    def test_all_fail_exit2(self):
        log: dict = {}
        mods = {"meds": _fake_meds(log, raise_in=("now",)),
                "quality": _fake_quality(log, raise_tickers=("MU", "NVDA")),
                "earnings": _fake_earnings(log, raise_in=True)}
        out = _run(self.DEMO, mods=mods)
        self.assertEqual(out.exit_code, 2)
        self.assertTrue(out.exit_reason.startswith("no result"))


class TestAsOfPropagation(unittest.TestCase):
    """--as-of reaches all three adapters (§9)."""

    def test_propagation_and_floor(self):
        log: dict = {}
        mods = {"meds": _fake_meds(log), "quality": _fake_quality(log),
                "earnings": _fake_earnings(log)}
        out = _run(["MU", "NVDA", "--as-of", "2026-06-30", "--timeout", "30"], mods=mods)
        self.assertEqual(log["regime_now"], ["2026-06-30"])
        self.assertNotIn("now", log)                       # live now() never called
        for call in log["quality"]:
            self.assertEqual(call["as_of"], "2026-06-30")
        self.assertEqual(log["analyze"][0]["as_of"], "2026-06-30")
        self.assertEqual(out.ctx.regime.effective_as_of, "2026-05-31")   # engine's floor
        st = out.ctx.regime
        self.assertEqual(st.scenario_key, "INFLATION_SHOCK")
        self.assertEqual(macro_tilt(st, "tech"), 0.0)      # risk_on, not long -> 0
        for d in out.decisions:
            e = d.layers.get("earnings")
            if e is not None:
                self.assertFalse(e.facts.get("now"))       # NOW impossible under as_of


class TestNoLookahead(unittest.TestCase):
    """Future as-of rejected; future-dated engine output rejected; flooring."""

    def test_floor(self):
        self.assertEqual(month_end_floor("2026-11-07"), "2026-10-31")
        self.assertEqual(month_end_floor("2026-10-31"), "2026-10-31")
        self.assertEqual(month_end_floor("2026-01-01"), "2025-12-31")
        self.assertEqual(month_end_floor("2020-03-15"), "2020-02-29")

    def test_future_as_of_rejected(self):
        for bad in ("2999-01-01", "not-a-date", "2026-13-40"):
            with self.assertRaises(MasterError) as cm:
                _validate_ns(_ns(["MU"], as_of=bad))
            self.assertEqual(cm.exception.code, 64)

    def test_future_dated_earnings_rejected(self):
        log: dict = {}
        mods = {"meds": _fake_meds(log), "quality": _fake_quality(log),
                "earnings": _fake_earnings(log, future=True)}
        out = _run(["MU", "--as-of", "2026-06-30", "--timeout", "30"], mods=mods)
        sig = out.results["earnings"].signals["MU"]
        self.assertEqual(sig.status, "MISSING")
        self.assertIn("future-dated", sig.warnings[0])
        self.assertNotIn("plan", log)                      # plan never called under as_of


class TestFunnel(unittest.TestCase):
    """Earnings receives only the top-K survivors of L1+L2 (§9)."""

    def test_topk(self):
        log: dict = {}
        mods = {"quality": _fake_quality(log), "earnings": _fake_earnings(log)}
        argv = ["MU", "NVDA", "AAPL", "AMD", "META", "VETO1", "STALE1",
                "--only", "quality,earnings", "--earnings-top", "3", "--timeout", "30"]
        out = _run(argv, mods=mods)
        self.assertEqual(log["analyze"][0]["tickers"], ["AAPL", "META", "NVDA"])
        got = set(out.results["earnings"].signals)
        self.assertEqual(got, {"AAPL", "META", "NVDA"})    # VETO1/STALE1 never reach L3
        self.assertNotIn("VETO1", got)
        self.assertNotIn("STALE1", got)


class TestRefsIdentity(unittest.TestCase):
    """The identical universe_refs object goes to every quality call (§9)."""

    def test_same_object(self):
        log: dict = {}
        out = _run(["MU", "NVDA", "AAPL", "--only", "quality", "--timeout", "30"],
                   mods={"quality": _fake_quality(log)})
        calls = log["quality"]
        self.assertEqual(len(calls), 3)
        first = calls[0]["refs"]
        for c in calls[1:]:
            self.assertIs(c["refs"], first)
        self.assertIsNotNone(first)
        tickers = {r.ticker for r in first}
        self.assertTrue({"MU", "NVDA", "AAPL"} <= tickers)
        self.assertIn("AVGO", tickers)                     # sector peers included (builtin)

    def test_watchlist_peers_targets_only(self):
        log: dict = {}
        _run(["MU", "NVDA", "--only", "quality", "--peers", "watchlist", "--timeout", "30"],
             mods={"quality": _fake_quality(log)})
        tickers = {r.ticker for r in log["quality"][0]["refs"]}
        self.assertEqual(tickers, {"MU", "NVDA"})

    def test_bucket_split(self):
        log: dict = {}
        _run(["COST", "HD", "--only", "quality", "--bucket", "COST=staples", "--timeout", "30"],
             mods={"quality": _fake_quality(log)})
        refs = log["quality"][0]["refs"]
        sectors = {r.ticker: r.sector for r in refs}
        self.assertEqual(sectors["COST"], "staples")       # the pinned name
        self.assertEqual(sectors["KO"], "staples")         # curated staples half
        self.assertEqual(sectors["WMT"], "staples")
        self.assertEqual(sectors["HD"], "discretionary")   # curated discretionary half
        self.assertEqual(sectors["TSLA"], "discretionary")


class TestImportPurity(unittest.TestCase):
    """import master has no side effects; --only quality imports nothing else."""

    HERE = str(Path(__file__).resolve().parent)

    def test_import_no_side_effects(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            code = ("import os, sys, master; "
                    "assert os.listdir('.') == [], os.listdir('.'); "
                    "sys.stdout.write('EMPTY-OK')")
            env = dict(os.environ, PYTHONPATH=self.HERE, NO_COLOR="1")
            r = subprocess.run([sys.executable, "-c", code], cwd=tmp, env=env,
                               capture_output=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr.decode()[-400:])
            self.assertIn("EMPTY-OK", r.stdout.decode())
            self.assertEqual(r.stdout.decode().strip(), "EMPTY-OK")   # no prints on import

    def test_env_unchanged(self):
        import subprocess
        code = ("import os; before = dict(os.environ); import master; "
                "assert dict(os.environ) == before; print('ENV-OK')")
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, PYTHONPATH=self.HERE)
            r = subprocess.run([sys.executable, "-c", code], cwd=tmp, env=env,
                               capture_output=True, timeout=60)
            self.assertIn("ENV-OK", r.stdout.decode(), r.stderr.decode()[-400:])

    def test_only_quality_imports_nothing_else(self):
        sys.modules.pop("meds", None)
        sys.modules.pop("earnings_engine", None)
        log: dict = {}
        try:
            out = _run(["MU", "--only", "quality", "--timeout", "30"],
                       mods={"quality": _fake_quality(log)})
            self.assertEqual(set(out.results), {"quality"})
            self.assertEqual(out.exit_code, 0)
            self.assertNotIn("meds", sys.modules)
            self.assertNotIn("earnings_engine", sys.modules)
        finally:
            sys.modules.pop("meds", None)
            sys.modules.pop("earnings_engine", None)


class TestCli(unittest.TestCase):
    """Exit codes: 64 bad usage (before any network), 0 help/version/json."""

    HERE = str(Path(__file__).resolve().parent)

    def _run_cli(self, argv, env_extra=None, timeout=90):
        import subprocess
        env = dict(os.environ, PYTHONPATH=self.HERE, NO_COLOR="1")
        env.update(env_extra or {})
        return subprocess.run([sys.executable, "master.py", *argv], cwd=self.HERE, env=env,
                               capture_output=True, timeout=timeout)

    def test_help_version(self):
        self.assertEqual(self._run_cli(["--help"]).returncode, 0)
        self.assertEqual(self._run_cli(["--version"]).returncode, 0)

    def test_bad_flag_is_64(self):
        r = self._run_cli(["MU", "--bogus"])
        self.assertEqual(r.returncode, 64)
        self.assertIn("master:", r.stderr.decode())

    def test_bad_as_of_is_64(self):
        for bad in ("2999-01-01", "nope"):
            self.assertEqual(self._run_cli(["MU", "--as-of", bad]).returncode, 64, bad)

    def test_json_exit0_and_parses(self):
        r = self._run_cli(["MU", "NVDA", "--json"], env_extra={"MASTER_STUBS": "1"})
        self.assertEqual(r.returncode, 0, r.stderr.decode()[-400:])
        doc = json.loads(r.stdout.decode())
        self.assertEqual(doc["schema"], 1)
        self.assertTrue(doc["decisions"])
        self.assertIn("research screener", doc["disclaimer"])   # never advice, in json too


class TestRunModes(unittest.TestCase):
    """v1.1.0: --mode presets, explicit-flag precedence, --warm selection,
    and the [plan] banner (the anti-'stuck' fix)."""

    def test_mode_presets(self):
        for mode, want in (("quick", (300.0, "watchlist", 10, "none")),
                           ("standard", (900.0, "builtin", 25, "none")),
                           ("deep", (3600.0, "builtin", 40, "all"))):
            ns = _ns(["--mode", mode])
            self.assertEqual((ns.timeout, ns.peers, ns.earnings_top,
                              ns.earnings_prefetch), want, mode)

    def test_standard_mirrors_v100_defaults(self):
        ns = _ns([])
        self.assertEqual(ns.timeout, CONFIG["LAYER_TIMEOUT_S"])
        self.assertEqual(ns.peers, "builtin")
        self.assertEqual(ns.earnings_top, CONFIG["EARNINGS_TOP_K"])
        self.assertEqual(ns.mode, CONFIG["MODE_DEFAULT"])

    def test_explicit_flag_beats_mode(self):
        ns = _ns(["--mode", "quick", "--timeout", "60", "--peers", "builtin",
                  "--earnings-top", "3"])
        self.assertEqual(ns.timeout, 60.0)
        self.assertEqual(ns.peers, "builtin")
        self.assertEqual(ns.earnings_top, 3)

    def test_bad_mode_is_64(self):
        with self.assertRaises(MasterError) as cm:
            _ns(["--mode", "turbo"])
        self.assertEqual(cm.exception.code, 64)

    def test_warm_selects_macro_quality(self):
        log: dict = {}
        out = _run(["--warm", "--timeout", "30"], mods={
            "meds": _fake_meds(log), "quality": _fake_quality(log),
            "earnings": _fake_earnings(log)})
        self.assertEqual(set(out.results), {"macro", "quality"})
        self.assertNotIn("analyze", log)              # earnings never ran
        self.assertTrue(out.decisions)                 # E-off preview still fuses

    def test_warm_respects_skip(self):
        log: dict = {}
        out = _run(["--warm", "--skip", "macro", "--timeout", "30"],
                   mods={"quality": _fake_quality(log)})
        self.assertEqual(set(out.results), {"quality"})

    def test_plan_banner_prints_pool_and_caches(self):
        import contextlib
        import io
        log: dict = {}
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            _run(["MU", "NVDA", "--only", "macro,quality", "--timeout", "30"],
                 mods={"meds": _fake_meds(log), "quality": _fake_quality(log)})
        text = buf.getvalue()
        self.assertIn("[plan]", text)
        self.assertIn("quality pool", text)           # exact pool size shown
        self.assertIn("caches:", text)
        self.assertIn("budget 30s/layer", text)

    def test_plan_banner_silent_when_quiet(self):
        import contextlib
        import io
        log: dict = {}
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            _run(["MU", "--only", "quality", "--timeout", "30", "--quiet"],
                 mods={"quality": _fake_quality(log)})
        self.assertNotIn("[plan]", buf.getvalue())

    def test_watchlist_peers_warning_present(self):
        log: dict = {}
        out = _run(["MU", "NVDA", "--mode", "quick", "--timeout", "30"],
                   mods={"meds": _fake_meds(log), "quality": _fake_quality(log),
                         "earnings": _fake_earnings(log)})
        self.assertTrue(any("watchlist only" in w for w in out.warnings))


class TestProgressSilencing(unittest.TestCase):
    """v1.1.0: kill(owner)/stop() — a timed-out layer's stuck thread must not
    keep painting the stderr line (the stray 'quality: 643/643' after the
    table) and nothing writes after stop()."""

    def test_kill_and_stop(self):
        import contextlib
        import io
        p = _Progress(quiet=True)
        self.assertTrue(p.off)                  # non-TTY stderr in tests
        p.off = False                           # simulate a TTY
        cb = lambda txt: p.set(txt) if p.alive("quality") else None
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            cb("quality: 1/643 MU")
            p.kill("quality")
            self.assertFalse(p.alive("quality"))
            self.assertTrue(p.alive("earnings"))
            cb("quality: 643/643 REXR")         # dead owner -> never written
            p.stop()
            p.set("earnings: never")            # stopped -> never written
        text = buf.getvalue()
        self.assertIn("quality: 1/643 MU", text)
        self.assertNotIn("643/643", text)
        self.assertNotIn("never", text)


class TestExitReason(unittest.TestCase):
    """v1.1.0: the NO-GO reason names the ERROR layer's real cause (timeout),
    never the cosmetic earnings version note (v1.0.0 bug)."""

    def _res(self, name, order, status, warnings=()):
        r = LayerResult(name=name, order=order, status=status)
        r.warnings = tuple(warnings)
        return r

    def test_no_go_reason_names_real_blocker(self):
        res = {
            "macro": self._res("macro", 1, "ERROR",
                                ("macro: timeout after 900s (partial kept)",)),
            "quality": self._res("quality", 2, "ERROR",
                                 ("quality: timeout after 900s (partial kept)",)),
            "earnings": self._res(
                "earnings", 3, "DEGRADED",
                ("earnings engine exposes no __version__; reporting docstring "
                 "v3 (drift undetectable)",)),
        }
        code, reason = _resolve_exit(res, [])
        self.assertEqual(code, 2)
        self.assertEqual(reason,
                         "no result / NO-GO: macro: timeout after 900s (partial kept)")
        self.assertNotIn("__version__", reason)

    def test_useful_macro_still_exits_zero(self):
        m = self._res("macro", 1, "OK")
        m.ctx_out = {"macro": MacroState()}
        code, _ = _resolve_exit({"macro": m}, [])
        self.assertEqual(code, 0)


class TestRender(unittest.TestCase):
    """Width/ASCII/NO_COLOR equality (§9)."""

    def _out(self) -> RunOutput:
        return _run(["MU", "NVDA", "AAPL", "AMD", "META", "VETO1", "STALE1", "XYZ"],
                    stubs=True, timeout=30, top=25)

    def test_width_bounds(self):
        out = self._out()
        for w in (72, 96, 110):
            text = render_report(out, _ns([], width=w, top=25, min_conviction=0.0))
            for ln in strip_ansi(text).splitlines():
                self.assertLessEqual(len(ln), w, (w, ln))

    def test_ascii_is_ascii(self):
        out = self._out()
        text = render_report(out, _ns([], ascii=True, top=25))
        for ch in text:
            self.assertLess(ord(ch), 128, repr(ch))
        self.assertIn("#", text)                          # bar swapped to #

    def test_color_stripped_equals_plain(self):
        out = self._out()
        plain = render_report(out, _ns([], no_color=True, top=25))
        old = sys.stdout.isatty
        sys.stdout.isatty = lambda: True                  # noqa: SLF001 (test-only)
        os.environ.pop("NO_COLOR", None)
        try:
            colored = render_report(out, _ns([], no_color=False, top=25))
        finally:
            sys.stdout.isatty = old
        self.assertEqual(strip_ansi(colored), plain)

    def test_bar(self):
        self.assertEqual(_bar(0.5), "█████░░░░░")
        self.assertEqual(len(_bar(0.78)), CONFIG["BAR_COLS"])


class TestJsonSchema(unittest.TestCase):
    """Stable --json schema (§9)."""

    def test_keys(self):
        out = _run(["MU", "NVDA"], stubs=True, timeout=30)
        payload = json_payload(out, _ns([], top=25))
        self.assertEqual(set(payload), {"schema", "master", "mode", "as_of", "live_date",
                                        "macro_effective", "risk_budget", "stubbed",
                                        "disclaimer", "layers", "decisions", "warnings",
                                        "timings"})
        base = {"name", "stage", "order", "status", "engine_version", "version_tested",
                "elapsed_s", "cache", "warnings"}
        by_name = {e["name"]: e for e in payload["layers"]}
        self.assertEqual(set(by_name["macro"]) - base, {"regime"})
        self.assertEqual(set(by_name["earnings"]) - base, {"verdict", "weak", "backtest"})
        self.assertEqual(set(by_name["quality"]), base)
        d0 = payload["decisions"][0]
        self.assertEqual(set(d0), {"ticker", "sector", "action", "conviction", "grade",
                                    "weight", "macro", "quality", "earnings", "reasons"})
        self.assertIsNone(d0["weight"])                  # reserved for the L5 sizer
        json.dumps(payload, default=str)                  # serialisable

    def test_mu_long_math(self):
        out = _run(["MU"], stubs=True, timeout=30)
        d_mu = next(d for d in out.decisions if d.ticker == "MU")
        # base = .65*72 + .35*81 = 75.15; credit OFF -> damp .5 -> mult 1.05 -> 78.9
        self.assertEqual(d_mu.conviction, 78.9)
        self.assertEqual(d_mu.action, "LONG")
        self.assertEqual(d_mu.grade, "A")


class TestEndToEnd(unittest.TestCase):
    """Stubbed end-to-end run: pipeline -> fusion -> render -> explain (§10)."""

    def test_full_run(self):
        out = _run(["MU", "NVDA", "AAPL", "AMD", "META", "VETO1", "STALE1", "XYZ",
                    "NEE", "PLD", "JPM", "COST"], stubs=True, timeout=30, top=25)
        self.assertEqual(out.exit_code, 0)
        self.assertTrue(out.decisions)
        for d in out.decisions:
            self.assertIn(d.action, ("LONG", "WATCH", "AVOID"))
            self.assertLessEqual(len(d.reasons), CONFIG["MAX_REASONS"])
            self.assertIsNone(d.weight)
        by_t = {d.ticker: d for d in out.decisions}
        self.assertEqual(by_t["VETO1"].action, "AVOID")
        self.assertIn("NEGATIVE_EQUITY", by_t["VETO1"].reasons[0])
        self.assertEqual(by_t["STALE1"].action, "AVOID")
        self.assertIn("STALE_DATA", by_t["STALE1"].reasons[0])
        self.assertIn("SPLIT_BASIS_UNVERIFIED on XYZ", " · ".join(out.warnings))
        self.assertIn("credit OFF", " · ".join(out.warnings))
        text = render_report(out, _ns([], top=25))
        for needle in ("MASTER ENGINE", "L1 MACRO", "sector tilt", "MU",
                       "research screener, not investment advice"):
            self.assertIn(needle, text)
        expl = _explain_block(make_style(_ns([])), out, _ns([], top=25), "MU")
        for needle in ("L1 macro", "L2 quality", "L3 earnings", "fusion", "provenance",
                       "× macro 1.050"):
            self.assertIn(needle, expl)


class TestConfigSanity(unittest.TestCase):
    """Weights sum to 1, thresholds ordered, vocabularies consistent (§9)."""

    def test_weights(self):
        self.assertAlmostEqual(CONFIG["W_Q"] + CONFIG["W_E"], 1.0, places=9)

    def test_bands_ordered(self):
        for key in ("MASTER_GRADES", "QUALITY_NATIVE_GRADES", "EARNINGS_NATIVE_GRADES"):
            cuts = [c for c, _ in CONFIG[key]]
            self.assertEqual(cuts, sorted(cuts, reverse=True), key)
            self.assertTrue(all(0 <= c <= 100 for c in cuts))
        self.assertGreater(CONFIG["ACTION_LONG_AT"], CONFIG["ACTION_WATCH_AT"])
        self.assertGreaterEqual(CONFIG["ACTION_WATCH_AT"], 0)

    def test_vocab(self):
        self.assertTrue(CONFIG["VETO_FLAGS"])
        self.assertTrue(CONFIG["VETO_FLAGS"] <= {"NEGATIVE_EQUITY", "ALTMAN_DISTRESS",
                                                 "PIOTROSKI_LOW", "HIGH_ACCRUALS"})
        sectors = set(CONFIG["QUALITY_SECTORS"])
        for etf, pairs in CONFIG["ETF_TO_SECTORS"].items():
            for sec, _s in pairs:
                self.assertIn(sec, sectors, (etf, sec))
        self.assertTrue(CONFIG["CYCLICAL_SECTORS"] <= sectors)
        self.assertEqual(len(CONFIG["SECTOR_ORDER"]), len(sectors))
        self.assertEqual(set(CONFIG["SECTOR_ORDER"]), sectors)
        self.assertEqual(set(CONFIG["TESTED_VERSIONS"]), {"meds", "quality", "earnings"})
        self.assertEqual(set(LAYER_REGISTRY), {"macro", "quality", "earnings"})


class RealEngineContract(unittest.TestCase):
    """LIVE contract checks against the real engine files; LIVE SKIP when an
    engine is not importable here (never fake data)."""

    @classmethod
    def setUpClass(cls):
        try:
            import meds  # noqa: F401
            import quality  # noqa: F401
            import earnings_engine  # noqa: F401
        except Exception as e:                            # pragma: no cover
            raise unittest.SkipTest(f"LIVE SKIP: engine import failed ({e})")

    def test_versions_match_tested(self):
        import meds
        import quality
        self.assertEqual(meds.__version__, CONFIG["TESTED_VERSIONS"]["meds"])
        self.assertEqual(quality.ENGINE_VERSION, CONFIG["TESTED_VERSIONS"]["quality"])

    def test_normalize_parity(self):
        import quality
        for t in ("BRK.B", "brk-b", "AAPL", "aapl.x"):
            self.assertEqual(quality.normalize_ticker(t), _norm_ticker(t), t)
        self.assertEqual(_norm_ticker("BRK.B"), "BRK-B")

    def test_month_floor_parity(self):
        import meds
        for d in ("2026-11-07", "2026-10-31", "2020-03-15", "2026-01-01"):
            self.assertEqual(str(meds._decision_month_end(d).date()), month_end_floor(d), d)

    def test_build_inline_shape(self):
        import quality
        refs, sector, scope, warns, err = quality.build_inline_universe("MU")
        self.assertIsNone(err)
        self.assertEqual(sector, "tech")
        self.assertTrue(refs and refs[0].ticker == "MU")
        self.assertIsInstance(warns, list)


if __name__ == "__main__":                                # pragma: no cover
    sys.exit(main())
