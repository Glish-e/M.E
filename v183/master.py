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

EXIT CODES (phase-5 contract — old->new mapping in CHANGELOG.md and --doctor)
  0 clean · 1 degraded (result produced + warnings, incl. ml head
  UNAVAILABLE) · 2 usage/config (was 64) · 3 network required but
  unreachable · 4 no result / NO-GO (was 2) · 65 replay mismatch ·
  70 unexpected internal error (was 1; traceback only with --debug) ·
  130 Ctrl-C (names the phase).

NOTES
  --offline forces the macro snapshot (meds.FORCE_SNAPSHOT) and disables
  network in the earnings adapter (cache-miss becomes an honest error);
  quality serves from its caches when warm. stdout = results only;
  progress/warnings go to stderr. The default run writes NOTHING to disk
  (only --csv, and the engines' own caches, ever write).

SELFTEST
  `--selftest` runs the stdlib unittest suite which since phase 3 lives in
  test_master.py (all tests + fake engines moved out of master.py); it
  imports that file, so the two entry points run the SAME suite. Live
  checks print LIVE SKIP and never fake data. Env MASTER_STUBS=1 runs the
  stub layers from test_master.py (loud 64 if that file is absent — handy
  for hacking on the render/CLI without engines or network).
LAYER REGISTRY (phase 3)
  LAYER_REGISTRY is the single source of run order: build_layers, the
  pipeline, fusion, the renderer and --json all iterate it, so a
  REGISTERED layer always runs or fails loudly — never a silent skip.
  The overlay (L4-style, stage="overlay") and sizer (L5-style,
  stage="sizer") stages are wired end to end: overlays receive the
  Decision list and may add a bounded conviction_adj; sizers fill
  Decision.weight and add portfolio footer lines. No layer occupies
  them yet; test_master.py proves the plumbing with dummy layers.

CHANGELOG v1.3.1 (phase-4 L3 adapter repaired to the real engine)
  earnings_engine.py v3 arrived (uploaded this phase); phases 1-3 wrote
  the L3 adapter blind while it was absent, and v3 has NO plan() / NO
  Analysis.plan: the live what-to-hold API is signals(), the accuracy
  summary has lift/corr/oos_brier_skill (no AUC) and BacktestResult is
  an object with a summary Series. Repaired adapter-side only (H1):
  _plan_map() fetches signals() and maps rows onto the plan vocabulary
  (LONG / open / ENTER / closed / skip) with the documented NOW-chip
  freshness rule (EARNINGS_MAX_AGE) applied adapter-side because v3 has
  no max-age parameter; --earnings-backtest no longer ERRORs (it used
  to hit the missing a.plan attribute) and reports the v3 edge/naive-t
  summary; the accuracy verdict mirrors v3's own ladder (a missing auc
  previously degenerated every verdict to WEAK, halving E's fusion
  weight dataset-wide); --explain omits the stop price v3 never sends.
  No CONFIG value changed; TESTED_VERSIONS stays earnings v3 (now real).
CHANGELOG v1.3.0 (phase-3 interface + real layer registry)
  LAYER_REGISTRY is the single source of run order: build_layers, the
  pipeline, fusion, the renderer and --json all iterate the registry, so a
  registered layer always runs or fails loudly (A15) — overlay (L4-style)
  and sizer (L5-style) stages are wired end to end, overlays nudge
  conviction by at most OVERLAY_MAX_ADJ (the one new CONFIG entry) and
  never touch veto/gate AVOIDs; no-args runs in a TTY open a wizard whose
  every choice is also a flag (--sectors, --cap, --discover, --only,
  --mode) and which builds the exact same Namespace the flags build
  (the confirm line prints the command); --cap honestly refuses (64)
  while no engine exposes market caps at universe scope, and --discover
  sizes the table without ever truncating a percentile pool (fewer
  qualifiers than asked is a loud warning); the report gained a manifest
  header (mode/offline/stubs/as-of/engine versions incl. MISSING), a
  sector table (tilt, scored count, median quality), a reasons column,
  tiered widths 40/70/110 (colour still equals plain at every width),
  and ONE footer: conviction is a score, not a probability; the ~1,700
  test/fake lines moved from master.py into test_master.py (--selftest
  imports it; MASTER_STUBS=1 runs its stub layers, loud 64 if absent).
CHANGELOG v1.2.0 (phase-2 reliability + financial logic)
  _deadline_call renamed _soft_deadline_call (documented: the worker thread
  is never killed; hard kill would need a subprocess) and results are
  SNAPSHOT at the fusion boundary so a late worker can never mutate a fused
  decision; one offline guard per layer (quality source=auto included, via
  the engine's default_transport seam) and the JSON manifest says offline;
  every env/module mutation (QE_DATA_DIR/QE_CACHE_DIR, meds.FORCE_SNAPSHOT,
  quality paths/transport) is registered and restored — two runs in one
  process leak no state, and a second --cache-dir run actually redirects;
  earnings prefetch honours --workers; earnings cache status read from the
  real (default) directory; --check separates importable/configured/
  cache-ready/provider-ready and exits 2 when a required engine is missing;
  --warm --skip macro,quality is an explicit usage error; an empty or stale
  macro snapshot is DEGRADED (MACRO_SNAPSHOT_MAX_AGE_H, 48h, disclosed)
  instead of OK; staples/discretionary keep separate macro identities
  (XLP/XLY) while unbucketed consumer is unchanged; earnings per-signal
  status vocabulary OK/DISABLED/NOT_SELECTED/MISSING_DATA/ERROR replaces
  "E layer off"; p_next_big labelled as a beat chance (not a return) and
  conviction defined in the table, --explain and JSON (never a probability;
  missing E can still reach LONG).
CHANGELOG v1.1.1 (phase-1 correctness)
  _finite() hardening at every trust boundary (engine dicts, CLI flags,
  fusion): NaN/inf/out-of-range scores become ERROR/MISSING with no score
  and can never reach LONG (a NaN quality score used to print conviction 100
  grade A LONG); "x or default" patterns fixed so a real 0 (confidence,
  conviction leverage) is honoured; per-ticker isolation in the earnings
  loop; the earnings scorecard shows NO DATA / dash instead of crashing on
  missing scores and never prints 0% for a missing probability; strict JSON
  (allow_nan=False) and CSV formula-cell escaping; ranking is now action ->
  conviction desc -> ticker with vetoed/gate-failed convictions capped below
  WATCH with the cap in the reason; quality scoring zero names exits 2;
  _fit measures visible width after strip_ansi (colour output == plain);
  MASTER_STUBS=1 prints a loud STUBBED banner; --earnings-top 0 is an
  explicit, documented L3 idle.
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

# ── § 0 · imports (the me/* modules carry their own; this block serves
#    master.py's own code — v1.8.0 split) ─────────────────────────────────
import argparse
import copy
import importlib
import json
import math
import os
import re
import shutil
import sys
import time
import types
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Protocol

__all__ = ["LAYERS", "LAYER_REGISTRY", "Context", "Candidate", "LayerSignal",
           "LayerResult", "Decision", "MacroState", "fuse", "run_pipeline",
           "build_layers", "run_wizard", "main", "MLLayer", "RiskLayer",
           "size_portfolio", "risk_ctx_out"]
# ── § 3.2 · Layer protocol + base class ──────────────────────────────────
class Layer(Protocol):
    name: str            # "macro" | "quality" | "earnings" | later "ml"/"risk"
    order: int
    stage: str           # "gate" | "score" | "overlay" | "sizer"
    funnel_input: bool   # True: runs on the L1+L2 shortlist (earnings-style)
    def prefetch(self, ctx: Context) -> None: ...
    def run(self, ctx: Context, cands: list[Candidate]) -> LayerResult: ...
    # phase 3: overlay/sizer layers are called with the Decision LIST (they
    # get the last word on conviction / own the weights) — duck-typed.


class LayerBase:
    """Partial-result salvage: run() stashes its LayerResult early and mutates
    it as tickers complete, so a per-layer timeout keeps partial results."""
    name: str = "?"
    order: int = 0
    stage: str = "score"
    funnel_input: bool = False   # True: runs on the L1+L2 shortlist, not all candidates

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
    conf = _finite(raw.get("confidence"), 0.0, 1.0)          # zero is not missing
    dom = _finite(raw.get("dominance"), 0.0, 1.0)
    lev = _finite(raw.get("conviction_leverage"), 0.0, 10.0)  # meds ~1.35; 10 = sanity cap
    st.confidence = 0.0 if conf is None else conf
    st.dominance = 0.0 if dom is None else dom
    st.conviction_leverage = 1.0 if lev is None else lev
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
    if not raw.get("error") and not (st.scenario_key or st.scenario_name):
        # P2-8: an EMPTY snapshot (no scenario, no error) is not a regime —
        # report DEGRADED with a loud warning instead of a silent OK.
        st.status = "DEGRADED"
        st.warnings = tuple(dict.fromkeys(
            (*st.warnings, "empty macro snapshot (no scenario) — rejected")))[:12]
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
    """The macro-derived budget cap; CONSUMED by the risk sizer (RiskLayer
    passes it as size_portfolio's budget — weights are absolute exposures
    summing to <= this; me/risk.py). Not 'future' since v1.8.x."""
    if state.status == "ERROR":
        return 1.0
    lev = _finite(state.conviction_leverage, 0.0, 10.0)      # 0.0 lev honored (not 1.0)
    lev = 1.0 if lev is None else lev
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
        restores = ctx.flags.get("restores")
        if ctx.flags.get("offline"):
            # P2-3: swapped for this run only, restored by run_pipeline's
            # finally (meds resets it itself on its normal path; master must
            # not rely on that for every error path).
            # Final phase (§2.4): point meds at the best OFFLINE snapshot —
            # the master-materialised one from an earlier online run when
            # present, else meds' own repo snapshot. READ-ONLY: offline
            # never writes (§2.6).
            snap = _prepare_meds_snapshot(meds)
            if snap:
                g = _EnvRestore("MACRO_ENGINE_SNAPSHOT", snap)
                if restores is not None:
                    restores.append(g)
                else:
                    os.environ["MACRO_ENGINE_SNAPSHOT"] = snap
            guard = _AttrRestore(meds, "FORCE_SNAPSHOT", True)
            if restores is not None:
                restores.append(guard)
            # §2.4/H6: meds calls yfinance DIRECTLY for price inputs (no
            # transport seam, H1 forbids an engine edit). In offline mode
            # the package must look ABSENT so meds takes its own documented
            # no-yfinance path (verified: snapshot FRED data still serves
            # the regime, 0.2 s, zero sockets).
            blk = _SysModuleBlock("yfinance", "offline: meds price inputs")
            if restores is not None:
                restores.append(blk)
            else:
                blk.undo()                    # standalone caller: no scope
        else:
            # §3.5 online: let meds' verified cache FILL (engine-gated env
            # var; the offline tier of a future offline run is born here).
            g = _EnvRestore("MEDS_CACHE", "1")
            if restores is not None:
                restores.append(g)
            else:
                os.environ["MEDS_CACHE"] = "1"
        try:
            self._raw = (meds.now() if ctx.as_of is None
                         else meds.regime_now(as_of=ctx.as_of))
            self._source = "now" if ctx.as_of is None else "regime_now"
        except Exception as e:                        # adapter boundary
            self._raw = {"error": _exc(e)}
            # v1.8.1 (N9): a TRANSIENT macro failure gets ONE deferred
            # attempt after the cooldown (the guard records it in FETCH
            # HEALTH either way); PERMANENT/CONFIG classes stay the honest
            # error dict.
            ng = ctx.flags.get("netguard")
            if ng is not None:
                from me.netguard import classify_exc
                if classify_exc(e) == "TRANSIENT":
                    ng.note_pending(
                        "api.stlouisfed.org", "macro", "macro",
                        fn=(meds.now if ctx.as_of is None
                            else meds.regime_now),
                        kwargs=({} if ctx.as_of is None
                                else {"as_of": ctx.as_of}),
                        on_ok=lambda raw: setattr(self, "_raw", raw))
                    ng.deferred_pass(
                        cooldown_s=float(CONFIG["NET_DEFER_COOLDOWN_S"]),
                        deadline=ctx.flags.get("run_deadline"))

    def run(self, ctx: Context, cands: list[Candidate]) -> LayerResult:
        ver, tested, differs = _engine_version("meds", self._mod or types.ModuleType("meds"))
        res = self._begin(ver, tested)
        state = _parse_macro(self._raw or {}, self._source, ver)
        # P2-8: a STALE snapshot is DEGRADED, not OK (offline / snapshot tier
        # only — the live tiers refresh by construction). Threshold is a
        # disclosed CONFIG entry (meds TTL 24 h -> 48 h = two missed cycles).
        if state.status != "ERROR" and (ctx.flags.get("offline")
                                        or state.data_tier == "snapshot"):
            base = getattr(self._mod, "__file__", None) or __file__
            age = _cache_age_h(str(Path(str(base)).resolve().parent / "meds_cache"))
            if age is not None and age > CONFIG["MACRO_SNAPSHOT_MAX_AGE_H"]:
                note = (f"macro snapshot stale: {age:.0f}h old > "
                        f"{CONFIG['MACRO_SNAPSHOT_MAX_AGE_H']:.0f}h threshold "
                        "— regime may be outdated")
                state.status = "DEGRADED"
                state.warnings = tuple(dict.fromkeys((*state.warnings, note)))[:12]
                res.warnings = (*res.warnings, note)
        res.status = state.status
        res.warnings = tuple(dict.fromkeys((*res.warnings, *state.warnings)))[:12]
        res.cache = {"api": "cold", "public": "cold", "cache": "warm",
                     "snapshot": "warm"}.get(state.data_tier, "n/a")
        res.ctx_out = {"macro": state, "risk_budget": _risk_budget(state)}
        if differs:
            res.warnings = (*res.warnings, f"meds v{ver} != tested v{tested}")
        return res


# ── § 3.4 · QualityLayer (L2, quality) ───────────────────────────────────
def _quality_signal(cand: Candidate, r: dict) -> LayerSignal:
    """quality result dict -> LayerSignal (score only when the engine said OK
    AND the score is a finite number in 0..100; a present-but-invalid score
    is an ERROR with no score — it can never reach LONG)."""
    word = str(r.get("status") or "ERROR")
    raw_score = r.get("score")
    score = _finite(raw_score, 0.0, 100.0)
    ok = word == "OK" and score is not None
    invalid = word == "OK" and raw_score is not None and score is None
    if ok:
        status = "OK"
    elif word == "ERROR" or invalid:
        status = "ERROR"
    else:
        status = "MISSING"
    pool = str(r.get("sector") or "")
    flags = tuple(str(f) for f in (r.get("flags") or ()))
    metrics = r.get("metrics") or {}
    notes = [str(n) for n in (r.get("notes") or [])[:4]]
    facts: dict[str, Any] = {
        "engine_status": word, "sector": pool,
        # P2-9: staples/discretionary keep their own macro identity (XLP/XLY
        # map separately); an unbucketed consumer name still reads "consumer".
        "macro_sector": pool,
        "rank": r.get("rank_in_sector"), "coverage": r.get("coverage"),
        "pillars": dict(r.get("pillars") or {}),
        "data_source": str(r.get("data_source") or ""), "model": str(r.get("model") or ""),
        "metrics_top": {k: round(float(metrics[k]), 2) for k in CONFIG["EXPLAIN_METRICS"]
                        if isinstance(metrics.get(k), (int, float))},
        "notes": notes,
        "pool_size": r.get("_pool_size"),
    }
    bad_note = (f"invalid quality score ({raw_score!r}: not finite / not in 0..100)"
                if invalid else "")
    return LayerSignal(
        ticker=cand.ticker, layer="quality",
        score=(round(score, 1) if ok else None),
        grade=(_native_grade("QUALITY_NATIVE_GRADES", score) if ok else "-"),
        status=status,
        flags=flags, facts=facts,
        warnings=(*((bad_note,) if bad_note else ()), *flags, *notes[:2]),
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
        restores = ctx.flags.get("restores")
        # P2-2 (A4): offline guard for quality source=auto — one seam covers
        # the whole engine (SEC client + both price clients default to
        # quality.default_transport); honest NETWORK_ERROR, caches still
        # served, restored after the run.
        if ctx.flags.get("offline") and getattr(quality, "default_transport", None) \
                is not _offline_transport:
            guard = _AttrRestore(quality, "default_transport", _offline_transport)
            if restores is not None:
                restores.append(guard)
        # Final phase (§2.4): yfinance bypasses default_transport entirely
        # (its own sockets) — with the package installed an offline run
        # would still touch the network for prices. Swap the engine's own
        # availability seam so quality picks its chart client, which DOES
        # honour the blocked transport. Restored after the run.
        if ctx.flags.get("offline"):
            yfc = getattr(quality, "YfinancePriceClient", None)
            if yfc is not None:
                guard = _AttrRestore(
                    yfc, "available",
                    staticmethod(lambda: (False, _offline_yfinance_reason())))
                if restores is not None:
                    restores.append(guard)
        elif ctx.flags.get("net") == "online":
            # §3.3 + v1.8.1 (N3-N5): the net guard's transport wrapper (ledger
            # + breaker + classification + retry budget) when a guard is
            # installed, else the plain retry wrapper; the engine seam is
            # restored after the run either way.
            base_t = getattr(quality, "default_transport", None)
            ng = ctx.flags.get("netguard")
            wrapped = (ng.wrap_transport(base_t) if (ng is not None and base_t
                                                    is not None)
                       else (_retrying_quality_transport(base_t)
                             if base_t is not None else None))
            if wrapped is not None and not getattr(base_t, "_master_retry", False):
                guard = _AttrRestore(quality, "default_transport", wrapped)
                if restores is not None:
                    restores.append(guard)
            # v1.8.2 (W2): yfinance bypasses default_transport entirely
            # (its own sockets — yf.Ticker().history / .info). When the
            # package is installed an online run would otherwise skip the
            # breaker, the call cap and the ledger. Swap the engine's own
            # seams — YfinancePriceClient._download (the class attribute;
            # YahooChartPriceClient's override is untouched, it goes through
            # default_transport) and _detect_sector_yfinance — with the same
            # guard policy. RUNTIME class/module attribute swaps, restored
            # after the run (restores list); NEVER an engine file edit.
            if ng is not None:
                yfc = getattr(quality, "YfinancePriceClient", None)
                if yfc is not None and not getattr(
                        yfc._download, "_master_yf_guard", False):
                    restores.append(_AttrRestore(
                        yfc, "_download",
                        ng.wrap_yfinance_download(yfc._download)))
                det = getattr(quality, "_detect_sector_yfinance", None)
                if det is not None and not getattr(
                        det, "_master_yf_guard", False):
                    restores.append(_AttrRestore(
                        quality, "_detect_sector_yfinance",
                        ng.wrap_yfinance_sector(det)))
        # P2-3: --cache-dir must hold for THIS run even when quality was
        # already imported with other dirs (env is read at import time);
        # redirected via the engine's own patchable module globals, restored
        # after the run.
        self._redirect_quality_paths(quality, restores)
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
        # v1.8.1 (N5/N6/N9): per-name classification + negative cache +
        # coverage + deferred retry. guard is None offline/stub (the loop
        # is then exactly the v1.8.0 loop).
        ng = ctx.flags.get("netguard")
        from me.netguard import classify_exc
        skipped: list[tuple[str, str, str]] = []
        pend: list[tuple[str, Callable]] = []
        for cand in ctx.tickers:
            t = cand.ticker
            if ng is not None:
                neg = ng.negcache.hit("quality", t)
                if neg is not None:
                    ng.ledger.skip(str(neg.get("host", "n/a")), "quality", t,
                                   why=str(neg.get("why", "negative cache")),
                                   fix=str(neg.get("fix", "")))
                    skipped.append((t, str(neg.get("why", "negative cache")),
                                   str(neg.get("fix", ""))))
                    _ctx_note(ctx, f"quality {t}: skipped (negative cache: "
                                   f"{neg.get('why', '')}) — not fetched this "
                                   "run")
                    res.signals[t] = LayerSignal(
                        t, "quality", status="ERROR",
                        warnings=(f"[W_ITEM_SKIPPED] quality {t}: "
                                   f"{neg.get('why', '')} (negative cache, "
                                   "TTL "
                                   f"{float(CONFIG['NET_NEG_CACHE_TTL_S']):.0f}s)",),
                        as_of=ctx.as_of or "")
                    continue
            try:
                r = quality.get_quality_score(
                    t, as_of=ctx.as_of, source=ctx.flags.get("source", "auto"),
                    universe_refs=self._refs,
                    progress=(lambda p, n, tt: prog.set(
                        f"quality: {p}/{n} {tt} · {time.monotonic() - t0:.0f}s"
                        + (f" · net {ng.live()}" if ng is not None else ""))
                        if prog.alive("quality") else None) if prog else None)
                r["_pool_size"] = pool_sizes.get(str(r.get("sector") or ""), 0)
                sig = _quality_signal(cand, r)
            except Exception as e:                 # ticker failure never kills the layer
                _ctx_note(ctx, f"quality {t}: {_exc(e)}")
                cls = classify_exc(e)
                if ng is not None and cls == "PERMANENT":
                    why = f"{cls}: {e}"[:120]
                    fix = ("add the ticker to data/universe_overrides.csv "
                           "if it is delisted (scripts/universe_override.py "
                           "add TICKER sector delisted), or wait the TTL")
                    ng.negcache.put("quality", t, host="quality-engine",
                                    why=why,
                                    ttl_s=float(CONFIG["NET_NEG_CACHE_TTL_S"]),
                                    fix=fix)
                    ng.ledger.skip("quality-engine", "quality", t, why=why,
                                   fix=fix)
                    skipped.append((t, why, fix))
                    sig = LayerSignal(
                        t, "quality", status="ERROR",
                        warnings=(f"[W_ITEM_SKIPPED] quality {t}: {why} — "
                                   "no retry (permanent)",),
                        as_of=ctx.as_of or "")
                else:
                    sig = LayerSignal(t, "quality", status="ERROR",
                                      warnings=(_exc(e),), as_of=ctx.as_of or "")
                    if ng is not None and cls == "TRANSIENT":
                        pend.append((t, quality.get_quality_score))
            res.signals[t] = sig
        # v1.8.1 (N9): the deferred pass — ONE more attempt for the
        # transient-failed names after a cooldown, unless the budget or a
        # still-open host breaker says no. A recovered name is re-scored
        # through the SAME engine call (caches updated by the engine).
        if ng is not None and pend:
            for t, fn in pend:
                ng.note_pending(
                    "quality-engine", "quality", t, fn=fn, args=(t,),
                    kwargs={"as_of": ctx.as_of,
                            "source": ctx.flags.get("source", "auto"),
                            "universe_refs": self._refs},
                    on_ok=self._deferred_rescore(res, ctx=ctx,
                                                  pool_sizes=pool_sizes,
                                                  ticker=t))
            ng.deferred_pass(
                cooldown_s=float(CONFIG["NET_DEFER_COOLDOWN_S"]),
                deadline=ctx.flags.get("run_deadline"))
            for t, fn in pend:
                if t in ng.recovered_items("quality"):
                    _ctx_note(ctx, f"quality {t}: recovered by the deferred "
                                   "retry pass")
        self._skipped = skipped
        if prog:
            prog.kill("quality")                 # done: silence this owner for good

    def _deferred_rescore(self, res: LayerResult, ctx: Context,
                          pool_sizes: dict, ticker: str) -> Callable:
        """on_ok closure for the deferred pass: refresh ONE name's signal
        from the engine dict the retry returned (same mapper as the main
        loop; a crash here never breaks the pass)."""
        def _rescore(raw: dict) -> None:
            try:
                raw["_pool_size"] = pool_sizes.get(str(raw.get("sector") or ""), 0)
                cand = next((c for c in ctx.tickers if c.ticker == ticker), None)
                if cand is None:
                    return
                res.signals[ticker] = _quality_signal(cand, raw)
            except Exception:
                pass
        return _rescore

    @staticmethod
    def _redirect_quality_paths(quality: types.ModuleType,
                                restores: list | None) -> None:
        """Point quality's import-time path globals at THIS run's --cache-dir
        (mirrors the engine's own env derivation); no-op when they already
        match. P2-3: without this, run 2 in-process silently reused run 1's
        cache dirs."""
        want_data = os.environ.get("QE_DATA_DIR") or "data"
        want_cache = os.environ.get("QE_CACHE_DIR") or (want_data + "/cache")
        want_snap = os.environ.get("QE_SNAPSHOT_DIR") or (want_data + "/snapshots")
        want_scan = os.environ.get("QE_SCAN_STATE") or (want_data + "/scan_state.json")
        for attr, want in (("DATA_DIR", want_data), ("CACHE_DIR", want_cache),
                           ("SNAPSHOT_DIR", want_snap), ("SCAN_STATE_PATH", want_scan)):
            if str(getattr(quality, attr, "")) != want:
                guard = _AttrRestore(quality, attr, want)
                if restores is not None:
                    restores.append(guard)

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
        # v1.8.1 (N6): the layer reports its coverage and lists skipped
        # items (item, why, fix) — a failed item is skipped, never fatal.
        res.ctx_out["coverage"] = (f"{res.ctx_out['scored']}/"
                                   f"{res.ctx_out['total']}")
        res.ctx_out["skipped"] = list(getattr(self, "_skipped", []) or [])
        return res


# ── § 3.5 · EarningsLayer (L3, earnings_engine) ──────────────────────────
def _num(x: Any) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def _accuracy_verdict(acc: Any) -> str:
    """Mirror of the engine's own walk-forward verdict ladder
    (earnings_engine v3 _accuracy_lines; report() is never called).
    Phase 4: v3's validate() summary has lift/corr/oos_brier_skill and NO
    auc — the old auc_lo guard degenerated every verdict to WEAK. The v3
    ladder: NOT ENOUGH (n<60 or n_hi<30) -> SIGNAL (lift>=1.5 & corr>=0.10)
    unless the out-of-sample Brier skill is <= 0 (MIXED) -> else WEAK."""
    if acc is None or len(acc) == 0:
        return "NOT ENOUGH DATA (no walk-forward history to test)"
    n_tests = int(_num(acc.get("n_tests")) or 0)
    n_hi = int(_num(acc.get("n_score>=50")) or 0)
    if n_tests < 60 or n_hi < 30:
        return f"NOT ENOUGH DATA to judge (only {n_hi} high-rated tests, want 30+). Add more tickers."
    lift = _num(acc.get("lift_vs_base"))
    corr = _num(acc.get("rank_corr_score_vs_next_surprise"))
    skill = _num(acc.get("oos_brier_skill"))
    if lift == lift and lift >= 1.5 and corr == corr and corr >= 0.10:
        if skill == skill and skill <= 0:
            return f"MIXED: in-sample lift {lift:.2f}x but NO out-of-sample skill. Don't trust yet."
        return f"SIGNAL: high-rated names hit big beats {lift:.2f}x more often than base"
    return "WEAK / NO SIGNAL in this sample (lift is small or rank corr < 0.10)"


def _dstr(x: Any) -> str:
    """Any date-ish value -> 'YYYY-MM-DD' ('' for None). P4-D1: the REAL
    earnings engine returns pd.Timestamp, whose .date is a METHOD (not a
    property like datetime.date's absent attr) — stringifying the bound
    method produced '<bound method ...>' which the future-dated guard then
    compared against as_of, rejecting EVERY real-engine row. Call the
    method when callable; truncate '2025-06-25 00:00:00' to its date."""
    if x is None:
        return ""
    d = getattr(x, "date", None)
    if callable(d):
        x = d()
    return str(x or "")[:10]


def _earnings_signal(t: str, row: Any, plan_row: dict | None, err: str | None,
                     as_of: str | None) -> LayerSignal:
    facts: dict[str, Any] = {"plan": None, "now": False}
    base = dict(source="yahoo", as_of=as_of or "", layer="earnings", ticker=t)
    if row is None:
        return LayerSignal(**base, status="MISSING_DATA", grade="-",
                           warnings=(_redact(str(err or "no earnings history (<4 quarters or provider failed)"))[:160],))
    last_s = _dstr(row.get("last_date"))
    if as_of and last_s and last_s > as_of:
        return LayerSignal(**base, status="MISSING_DATA",
                           warnings=(f"future-dated output rejected (no-lookahead): last_date {last_s} > as_of {as_of}",))
    score = _finite(row.get("score"), 0.0, 100.0)
    if score is None:                      # invalid input: ERROR, no score (never LONG)
        return LayerSignal(**base, status="ERROR", grade="-",
                           warnings=(_redact(f"invalid earnings score ({row.get('score')!r}: "
                                             "not finite / not in 0..100)")[:160],))
    conf = _finite(row.get("confidence"), 0.0, 1.0)        # 0.0 is real, not missing
    pn = _finite(row.get("p_next_big"), 0.0, 1.0)
    facts.update({
        "n_quarters": _fin_int(row.get("n_quarters"), 0, 400),
        "last_date": last_s,
        "last4_big": _fin_int(row.get("last4_big"), 0, 4),
        "streak_big": _fin_int(row.get("streak_big"), 0, 400),
        "qtrs_since_big": (_finite(row.get("qtrs_since_big"), -1.0, 400.0) or 0.0),
        "last_big_date": _dstr(row.get("last_big_date")),
        "last_big_pct": (_finite(row.get("last_big_pct"), -100.0, 1000.0) or 0.0),
        "latest_surprise_pct": (_finite(row.get("latest_surprise_pct"), -100.0, 1000.0) or 0.0),
        "beat_rate": (_finite(row.get("beat_rate"), 0.0, 1.0) or 0.0),
        "p_next_big": pn,
        "confidence": (conf if conf is not None else 1.0),
    })
    if plan_row:
        facts["plan"] = plan_row.get("status")
        facts["now"] = plan_row.get("status") == "LONG"
        for k in ("price", "target", "stop_px", "days_since"):
            facts[k] = _num(plan_row.get(k)) if plan_row.get(k) is not None else None
        facts["exit_by"] = _dstr(plan_row.get("exit_by"))
        facts["last_report"] = _dstr(plan_row.get("last_report"))
    warns = (_redact(str(err))[:160],) if err else ()
    if plan_row and plan_row.get("future_report"):
        # B4 (v1.4.1 port): future-dated report — loud data-quality warning,
        # never NOW. The W_FUTURE_REPORT code is carried for the phase-5
        # ERRORS & WARNINGS block.
        warns = warns + (str(plan_row["future_report"]),)
    if plan_row and plan_row.get("stop_warn"):
        # P-3 (phase 4): no vol -> no stop — the loud warning rides the
        # signal (visible on the L3 line, --explain and the scorecard).
        warns = warns + (str(plan_row["stop_warn"]),)
    return LayerSignal(**base, status="OK", score=round(score, 1),
                       grade=str(row.get("rating") or "-"),   # engine's own rating
                       confidence=(conf if conf is not None else 1.0),
                       facts=facts, warnings=warns)


def _backtest_summary(a: Any) -> dict | None:
    """earnings_engine v3 BacktestResult -> the warning/JSON summary. v3's
    summary is a Series (picked_n, picked_mean_excess, edge, edge_t,
    edge_basis, n_open); the naive t overstates significance (earnings
    seasons cluster) — the engine says so and so does the warning line."""
    try:
        bt = getattr(a, "backtest", None)
        summ = getattr(bt, "summary", None)
        trades = getattr(bt, "trades", None)
        if bt is None or summ is None or len(summ) == 0:
            return None
        n_trades = len(trades) if trades is not None and len(trades) else 0
        if not n_trades:
            return None
        return {"n_trades": int(n_trades),
                "picked_n": int(_num(summ.get("picked_n")) or 0),
                "edge_pct": round(_num(summ.get("edge")) * 100, 1),
                "edge_t": round(_num(summ.get("edge_t")), 2),
                "basis": str(summ.get("edge_basis") or "")}
    except Exception:
        return None


def _stop_price(entry_px: float | None, vol: float | None,
                hold_days: int | None = None) -> float | None:
    """P-3 (spec 3.4, phase 4): live-plan stop = entry x (1 - k x annualised
    vol scaled to the holding window), k = EARNINGS_STOP_K, window =
    EARNINGS_HOLD_DAYS calendar days (the engine's own hold unit), vol = the
    sizer's trailing annualised vol estimate. None when k is off, no entry,
    or the vol is unusable — the CALLER must then ship the loud
    W_NO_VOL_NO_STOP warning, never a silent None."""
    k = float(CONFIG["EARNINGS_STOP_K"])
    if not k:
        return None
    try:
        entry = float(entry_px)
        fv = float(vol)
    except (TypeError, ValueError):
        return None
    if entry <= 0.0 or not math.isfinite(entry) or not math.isfinite(fv) or fv <= 0.0:
        return None
    hold = int(hold_days if hold_days is not None else CONFIG["EARNINGS_HOLD_DAYS"])
    stop = entry * (1.0 - k * fv * math.sqrt(hold / 365.0))
    return round(max(0.0, min(entry, stop)), 4)


def _map_plan_row(r: dict, today: "date", vol: float | None = None) -> dict:
    """One earnings_engine v3 signals() row -> the plan-row vocabulary the
    rest of master already speaks (_earnings_signal / --explain / trigger
    mode). The NOW chip keeps its documented freshness rule
    (EARNINGS_MAX_AGE, RUNBOOK): v3's signals() has no max-age parameter,
    so the adapter applies it HERE — an engine-LONG position whose report
    is older than EARNINGS_MAX_AGE days is 'open' (held), never NOW.
    v1.4.1 (B4), ported in phase 2: the freshness window is bounded on
    BOTH sides — 0 <= days <= EARNINGS_MAX_AGE. A future-dated event_date
    (negative days) is a data-quality error, never a NOW chip: status
    'open' plus a loud future_report warning that _earnings_signal
    re-raises (W_FUTURE_REPORT codes the warning for the phase-5 ERRORS &
    WARNINGS block)."""
    action = str(r.get("action") or "")
    event = _dstr(r.get("event_date"))
    days: int | None = None
    if event:
        try:
            days = (today - date.fromisoformat(event)).days
        except ValueError:
            days = None
    if action.startswith("LONG"):
        status = ("LONG" if days is not None
                  and 0 <= days <= int(CONFIG["EARNINGS_MAX_AGE"])
                  else "open")
    elif action.startswith("ENTER"):
        status = "ENTER"
    elif action.startswith("closed"):
        status = "closed"
    elif action.startswith("skip"):
        status = "skip"
    else:
        status = action.split(":", 1)[0][:12] or "n/a"   # error rows stay honest
    out = {"status": status, "price": r.get("entry_px"), "target": r.get("target_px"),
           "stop_px": None, "days_since": days,
           "exit_by": _dstr(r.get("planned_exit")), "last_report": event}
    # P-3 (phase 4): vol-based stop. A LIVE row (an entry price) with no
    # usable vol ships the LOUD W_NO_VOL_NO_STOP warning (code + fix
    # command) — never a silent None. Rows without an entry (skip/closed/
    # ENTER-pending) have nothing to stop, so no warning.
    entry = out["price"]
    out["stop_px"] = _stop_price(entry, vol)
    if out["stop_px"] is None and entry is not None \
            and float(CONFIG["EARNINGS_STOP_K"]) > 0.0:
        out["stop_warn"] = (
            "no vol -> no stop [W_NO_VOL_NO_STOP]: no usable price history "
            "for a volatility estimate on this name; fix: run once online "
            "(e.g. python3 master.py <TICKER> --mode online) to cache the "
            "price history the stop (and the sizer) need")
    if days is not None and days < 0:
        out["future_report"] = (f"future-dated report {event} is {-days} day(s) "
                                f"AFTER today {today.isoformat()} — treated as "
                                "open (never NOW); check the feed's clock "
                                "[W_FUTURE_REPORT]")
    return out


class EarningsLayer(LayerBase):
    """L3 timing on the funnel shortlist. trade=True (full backtest) only
    with --earnings-backtest. Phase 4: the real earnings_engine v3 has no
    plan() — the live what-to-hold table is signals() (one small price
    download), called ONLY when as_of is None (no lookahead: it uses
    today's clock) and mapped adapter-side by _map_plan_row."""
    name = "earnings"
    order = 3
    stage = "score"
    funnel_input = True          # phase 3: the funnel layer (top-K L1+L2 survivors)

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
            eng = earnings_engine.EarningsEngine(
                quarters=CONFIG["EARNINGS_QUARTERS"], workers=workers,
                cache_dir=(ctx.flags.get("earnings_cache_dir") or None),
                # Final phase (§2.4): offline serves ANY cached file however
                # old (last cached truth — the age is labelled by the layer
                # provenance, never silently fresh); online keeps the
                # engine's own 12 h TTL (the incremental refresh).
                cache_ttl_hours=(1e9 if ctx.flags.get("offline") else 12.0))
            if ctx.flags.get("offline"):
                # instance attrs only; cache file names unchanged. NOTE the
                # real engine's price fetcher is _pfetch (v3); _px_fetch is
                # kept for the documented test-fake contract — BOTH are
                # guarded so the socket-free guarantee cannot hinge on a
                # name (a latent phase-5 gap, found by the final red run).
                eng._fetch = _offline_raiser
                eng._pfetch = _offline_raiser
                eng._px_fetch = _offline_raiser
            else:
                # §3.3 + v1.8.1 (N3-N5/N9): per-request retries on the
                # provider callables — with a net guard installed this is
                # guard.wrap_fetch (ledger + breaker + classification +
                # retry budget + the deferred-retry pending list; the
                # item is the ticker, the host hint is the engine's own
                # provider name), else the plain retry wrapper. 4xx other
                # than 429 never retried; the engine's own cache/diag
                # paths take over after the final failure.
                ng = ctx.flags.get("netguard")
                _host = (str(getattr(eng, "_pname", "") or "earnings")
                         or "earnings")
                if ng is not None:
                    eng._fetch = ng.wrap_fetch(eng._fetch, "earnings history",
                                               host_hint=_host)
                    if callable(getattr(eng, "_pfetch", None)):
                        eng._pfetch = ng.wrap_fetch(eng._pfetch,
                                                    "earnings prices",
                                                    host_hint=_host)
                    if callable(getattr(eng, "_px_fetch", None)):
                        eng._px_fetch = ng.wrap_fetch(eng._px_fetch,
                                                      "earnings prices",
                                                      host_hint=_host)
                else:
                    eng._fetch = _retrying_fetch(eng._fetch, "earnings history")
                    if callable(getattr(eng, "_pfetch", None)):
                        eng._pfetch = _retrying_fetch(eng._pfetch, "earnings prices")
                    if callable(getattr(eng, "_px_fetch", None)):
                        eng._px_fetch = _retrying_fetch(eng._px_fetch, "earnings prices")
            self._eng = eng
            # P2-5: cache status reads the REAL directory: the explicit
            # --cache-dir when given, else the engine's own dir when it
            # exposes one, else the documented default. (Previously the stamp
            # was None without --cache-dir and a cold default-dir fetch
            # reported "warm".) The real engine's attr name is UNVERIFIED —
            # the getattr falls back to the documented default.
            self._cache_dir = (ctx.flags.get("earnings_cache_dir")
                               or str(getattr(eng, "cache_dir", "") or "")
                               or str(Path.home() / ".earnings_engine_cache"))
            self._stamp = _dir_stamp(self._cache_dir)
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
        with _TP(max(1, int(ctx.flags.get("workers") or CONFIG["DEFAULT_WORKERS"]))) as ex:
            list(ex.map(_warm, [c.ticker for c in ctx.tickers]))   # P2-4: --workers honoured

    def _plan_map(self, eng, scores, ctx: Context, sig_frame=None) -> dict:
        """{ticker: plan-row dict} from the engine's signals() frame — the
        backtest pass reuses a.signals, the default run fetches signals()
        once (v3 API; the old eng.plan() no longer exists). Empty map under
        --as-of (no lookahead) or when prices are unavailable (honest note).
        Phase 4 (P-3): each row with an entry price also gets its vol-based
        stop — the vol comes from the engine's OWN price cache via
        _ann_vol (the same trailing-126-td estimate the risk sizer uses;
        offline serves the cache, a cold cache leaves vol None and _map_plan_row
        ships the loud W_NO_VOL_NO_STOP warning, never a silent None)."""
        if ctx.as_of is not None:
            return {}                          # no lookahead: signals use today's clock
        frame = sig_frame if (sig_frame is not None and len(sig_frame)) else None
        if frame is None:
            try:
                frame = eng.signals(list(scores.index),
                                    hold_days=CONFIG["EARNINGS_HOLD_DAYS"],
                                    take_profit=CONFIG["EARNINGS_TP"],
                                    min_score=CONFIG["EARNINGS_PLAN_MIN"])
            except Exception as e:
                _ctx_note(ctx, f"earnings plan unavailable (prices): {_exc(e)}")
                return {}
        try:
            if frame is None or not len(frame):
                return {}
            rows = frame.to_dict("index")
        except Exception as e:
            _ctx_note(ctx, f"earnings plan unreadable: {_exc(e)}")
            return {}
        today = date.today()
        # phase 4 (P-3): one vol per planned name (cached prices; failures
        # leave None -> the row's own loud warning). Bounded to the names
        # that actually have a plan row, in the frame's order.
        vols: dict[str, float | None] = {}
        if float(CONFIG["EARNINGS_STOP_K"]) > 0.0:
            anchor = today
            start = (anchor - timedelta(days=380)).isoformat()   # 126 td + buffer
            for t in rows:
                tt = str(t)
                if tt in vols:
                    continue
                vols[tt] = None
                try:
                    s = eng.prices(tt, start)
                    if s is not None and len(s):
                        vols[tt] = _ann_vol(s)
                except Exception:
                    continue                     # vol stays None -> W_NO_VOL_NO_STOP
        return {str(t): _map_plan_row(r, today, vols.get(str(t)))
                for t, r in rows.items()}

    def run(self, ctx: Context, cands: list[Candidate]) -> LayerResult:
        eng = self._engine(ctx)
        ver, tested, differs = _engine_version("earnings", self._mod or types.ModuleType("earnings_engine"))
        res = self._begin(ver, tested)
        if self._mod is not None and not hasattr(self._mod, "__version__") \
                and not ctx.flags.get("earnings_version_noted"):
            # P2-3: per-run flag, NOT a module attribute (two runs in one
            # process must not leak state — the note belongs to every run).
            ctx.flags["earnings_version_noted"] = True
            res.warnings = (*res.warnings, "earnings engine exposes no __version__; "
                            f"reporting docstring v{ver} (drift undetectable)")
        if differs:
            res.warnings = (*res.warnings, f"earnings v{ver} != tested v{tested}")
        prog = ctx.flags.get("progress")
        tickers = [c.ticker for c in cands]
        if not tickers:
            top = ctx.flags.get("earnings_top")
            if top == 0:
                note = ("L3 funnel top-0: no names sent to earnings (--earnings-top 0) "
                        "— deliberate idle, not a failure")
                status = "OK"
            else:
                note = "empty shortlist: nothing passed the quality gate"
                status = "DEGRADED"
            res.warnings = (*res.warnings, note)
            res.ctx_out = {"verdict": ("not run (top-0 requested)" if top == 0
                                        else "not run (empty shortlist)"),
                           "weak": False,
                           "missing": [], "scored": 0, "backtest": None}
            res.status = status
            return res
        if prog and prog.alive("earnings"):
            prog.set(f"earnings: {len(tickers)} names (history+plan)")
        try:
            backtest = bool(ctx.flags.get("earnings_backtest"))
            # phase 4 (B-7c): ONE CONFIG source of truth — the SAME three
            # trade parameters flow to analyze() (the trade backtest AND its
            # embedded signals) as to the standalone signals() call below,
            # so the live plan and the backtest can never disagree. The
            # engine's own defaults (90 / 0.20 / 50) are never reached.
            a = eng.analyze(tickers, as_of=ctx.as_of, accuracy=True, trade=backtest,
                            hold_days=int(CONFIG["EARNINGS_HOLD_DAYS"]),
                            take_profit=CONFIG["EARNINGS_TP"],
                            min_score=float(CONFIG["EARNINGS_PLAN_MIN"]))
            sig_frame = (getattr(a, "signals", None)
                         if (backtest and ctx.as_of is None) else None)
            plan_map = self._plan_map(eng, a.scores, ctx, sig_frame)
        except Exception as e:
            res.status = "ERROR"
            res.warnings = (*res.warnings, _exc(e))
            _ctx_note(ctx, f"earnings layer: {_exc(e)}")
            if prog:
                prog.kill("earnings")
            return res
        verdict = _accuracy_verdict(getattr(a, "accuracy", None))
        weak = verdict.startswith(("WEAK", "NOT ENOUGH"))
        for t in tickers:                     # P1-3: one bad ticker never kills the layer
            try:
                row = a.scores.loc[t] if t in a.scores.index else None
                res.signals[t] = _earnings_signal(t, row, plan_map.get(t),
                                                  eng.errors.get(t), ctx.as_of)
            except Exception as e:             # record its error, continue
                res.signals[t] = LayerSignal(
                    t, "earnings", status="ERROR",
                    warnings=(_exc(e),), as_of=ctx.as_of or "")
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
        # v1.8.1 (N6): the layer reports coverage and lists skipped items
        # (item, why, fix) from the engine's own per-name errors.
        res.ctx_out["coverage"] = (f"{res.ctx_out['scored']}/"
                                   f"{len(res.signals) or len(tickers)}")
        res.ctx_out["skipped"] = [
            (str(t), f"engine error: {str(eng.errors.get(t, ''))[:80]}",
             "check the ticker (dead/delisted names: "
             "data/universe_overrides.csv) or rerun when the provider is back")
            for t in missing[:8]]
        # v1.8.1 (N9): the deferred retry pass for transient-failed fetch
        # items recorded by guard.wrap_fetch — ONE more attempt after the
        # cooldown; recovered tickers are re-analyzed through the engine's
        # PUBLIC analyze() (subset call, same CONFIG parameters) so the
        # layer result reflects the recovered caches.
        ng = ctx.flags.get("netguard")
        if ng is not None and ng.pending("earnings"):
            ng.deferred_pass(
                cooldown_s=float(CONFIG["NET_DEFER_COOLDOWN_S"]),
                deadline=ctx.flags.get("run_deadline"))
            recovered = [t for t in ng.recovered_items("earnings")
                         if t in res.signals]
            if recovered:
                try:
                    a2 = eng.analyze(recovered, as_of=ctx.as_of, accuracy=False,
                                     trade=False,
                                     hold_days=int(CONFIG["EARNINGS_HOLD_DAYS"]),
                                     take_profit=CONFIG["EARNINGS_TP"],
                                     min_score=float(CONFIG["EARNINGS_PLAN_MIN"]))
                    for t in recovered:
                        try:
                            row = a2.scores.loc[t] if t in a2.scores.index else None
                            if row is not None and getattr(a2, "errors", None):
                                a2.errors.pop(t, None)
                            res.signals[t] = _earnings_signal(
                                t, row, self._plan_map(
                                    eng, a2.scores, ctx, sig_frame=None).get(t),
                                (getattr(a2, "errors", {}) or {}).get(t),
                                ctx.as_of)
                        except Exception:
                            pass                     # keep the main-pass signal
                    missing = [t for t, s in res.signals.items()
                               if s.status != "OK"]
                    res.ctx_out["missing"] = missing
                    res.ctx_out["scored"] = (len(res.signals) - len(missing))
                    res.ctx_out["coverage"] = (f"{res.ctx_out['scored']}/"
                                               f"{len(res.signals)}")
                    res.ctx_out["recovered_by_deferred"] = recovered
                    _ctx_note(ctx, f"earnings: deferred retry recovered "
                                   f"{len(recovered)} name(s) — "
                                   f"{', '.join(recovered[:6])}")
                except Exception as e:
                    _ctx_note(ctx, f"earnings deferred re-analyze failed: "
                                   f"{_exc(e)}")
        if prog:
            prog.kill("earnings")
        return res


# ── § 3.6 · MLLayer (L4 overlay) + RiskLayer (L5 sizer) + registry ────────

def _sha256_file(path: Path) -> str:
    """M5 (v1.4.1 port, phase 3): sha256 of one artifact file — the
    integrity pin the ACTIVE-state report check compares against."""
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _ml_load_head(models_dir: Path, head: str) -> tuple[dict | None, str]:
    """Load one head model (pure numpy, allow_pickle=False). Returns
    (bundle, note); bundle is None with the reason in the note for every
    UNTRAINED / refused case — a bad model never crashes the run."""
    path = models_dir / f"head_{head}.npz"
    if not path.exists():
        return None, f"head {head}: no model file — UNTRAINED"
    try:
        import numpy as np                                    # inference only
        z = np.load(path, allow_pickle=False)
        b = {k: z[k] for k in z.files}
        feats = [str(x) for x in np.asarray(b.get("feature_names", ())).tolist()]
    except Exception as e:
        return None, f"head {head}: unreadable npz ({_exc(e)}) — UNTRAINED"
    bad = sorted(set(feats) & set(CONFIG["ML_FORBIDDEN_FEATURES"]))
    if bad:
        return None, (f"head {head} REFUSED: feature(s) {', '.join(bad)} come "
                      "from the label window (future-dated) — leakage guard")
    # B8 (v1.4.1 port, phase 3): validate the numbers that feed conviction
    # arithmetic BEFORE any state handling — a corrupt base_rate/calib
    # must be refused loudly, never allowed to push NaN into
    # conviction_adj downstream.
    try:
        base_rate = float(b.get("base_rate", 0.5))
    except Exception:
        base_rate = float("nan")
    if not (math.isfinite(base_rate) and 0.0 < base_rate < 1.0):
        return None, (f"head {head} REFUSED: base_rate {b.get('base_rate')!r} "
                      "is not a finite number in (0,1) — UNTRAINED")
    if str(b.get("model_type", "")) == "logistic_np":
        for k, dflt in (("calib_a", 1.0), ("calib_b", 0.0)):
            try:
                v = float(b.get(k, dflt))
            except Exception:
                v = float("nan")
            if not math.isfinite(v):
                return None, (f"head {head} REFUSED: {k} {b.get(k)!r} is not "
                              "a finite number — UNTRAINED")
    if str(b.get("model_type", "")) == "gbm_joblib":
        side = path.with_suffix(".joblib")
        if not side.exists():
            return None, (f"head {head}: GBM model needs the sidecar "
                          f"{side.name} — UNTRAINED here")
        # final phase (§7.1): NEVER unpickle an unhashed file. The integrity
        # gates run BEFORE any dependency import and BEFORE any unpickle, so
        # a tampered/stale sidecar is refused identically with or without
        # sklearn/joblib installed on this machine.
        import hashlib
        pin = str(b.get("sidecar_sha256", "") or "")
        if not pin:
            return None, (f"head {head}: GBM npz carries no sidecar_sha256 pin "
                          "— unpickling an unhashed file is refused (retrain "
                          "with the current ml_train.py)")
        side_bytes = side.read_bytes()
        actual = hashlib.sha256(side_bytes).hexdigest()
        if actual != pin:
            return None, (f"head {head}: sidecar sha256 mismatch "
                          f"(file {actual[:12]} != pin {pin[:12]}) — UNTRAINED "
                          "(tampered or stale sidecar)")
        # §3.1 (B-1): optional deps — missing means the ENVIRONMENT cannot
        # run this head: UNAVAILABLE with the reason, never a crash.
        try:
            import joblib                      # optional deps: UNAVAILABLE,
            import sklearn                     # never a crash
        except Exception as e:
            return None, (f"head {head}: UNAVAILABLE — joblib/sklearn not "
                          f"importable here ({_exc(e)}); retrain with "
                          "python3 ml_train.py on this machine")
        # §3.1 (B-1) version-aware loading: the npz pins the sklearn/numpy/
        # joblib/python versions the artifact was TRAINED with. Any mismatch
        # means the pickle may be unreadable on this interpreter (sklearn
        # 1.9.1 loading a 1.5.2 pickle: \"No module named '_loss'\") — the
        # head is marked UNAVAILABLE with the reason and SKIPPED; the run
        # continues degraded (exit 1). Pins absent from legacy artifacts are
        # not compared (the sha256 pin above still guards integrity).
        got = {"sklearn": str(getattr(sklearn, "__version__", "") or ""),
               "numpy": str(np.__version__),
               "joblib": str(getattr(joblib, "__version__", "") or ""),
               "python": sys.version.split()[0]}
        for label, key in (("sklearn", "sklearn_version"),
                           ("numpy", "numpy_version"),
                           ("joblib", "joblib_version"),
                           ("python", "python_version")):
            want = str(b.get(key, "") or "")
            if want and want != got[label]:
                return None, (f"head {head}: UNAVAILABLE — {label} "
                              f"{got[label]} != trained-on {want}; pin the "
                              "training environment or retrain here "
                              "(python3 ml_train.py). The head is skipped, "
                              "the run continues degraded")
        note_ver = ""
        want_m = str(b.get("master_version", "") or "")
        if want_m and want_m != __version__:
            note_ver = f" [trained on master v{want_m}]"
        b["_joblib"] = str(side)
        b["_sidecar_bytes"] = side_bytes   # the sha256-VERIFIED bytes: the
        # only bytes _ml_predict will ever unpickle (no TOCTOU re-read)
        b["_pin_note"] = note_ver
    elif str(b.get("model_type", "")) != "logistic_np":
        return None, (f"head {head}: model_type {str(b.get('model_type', ''))!r} "
                      "not loadable — UNTRAINED")
    state = str(b.get("state", "SHADOW"))
    if state == "ACTIVE":
        # M5 (v1.4.1 port, phase 3): an ACTIVE head needs a passing report
        # that is HASH-BOUND to this exact model file and its training
        # dataset — a verdict alone is not evidence; any mismatch or a
        # missing pin downgrades the head to SHADOW, decisions unchanged.
        rep_path = models_dir / f"validation_{head}.json"
        why = ""
        try:
            v = json.loads(rep_path.read_text(encoding="utf-8"))
            if str(v.get("verdict", "")) != "beats":
                why = (f"verdict {str(v.get('verdict', ''))!r} != beats")
            elif str(v.get("dataset_sha256", "")) != str(
                    b.get("dataset_sha256", "")) or not str(
                    v.get("dataset_sha256", "")):
                why = ("the report's dataset_sha256 does not match the "
                       "model's training dataset pin")
            elif str(v.get("model_sha256", "")) != _sha256_file(path):
                why = ("the report's model_sha256 does not match this "
                       "model file")
        except Exception as e:
            why = f"report unreadable ({_exc(e)})"
        if why:
            b["state"] = "SHADOW"
            b["feature_names"] = feats
            return b, (f"head {head}: ACTIVE refused — {why}; downgraded "
                       "to SHADOW, decisions unchanged")
    b["state"] = state
    b["feature_names"] = feats
    return b, f"head {head}: {state} (n_train {int(b.get('n_train', 0))})"


def _ml_predict(bundle: dict, rows: dict[str, Any]) -> dict[str, float | None]:
    """Pure-numpy calibrated probabilities for every row dict (logistic);
    a GBM bundle goes through its joblib sidecar (sklearn present). Missing
    feature KEYS and NaN values impute to the training medians for the
    logistic path — the same policy the trainer exported. B8 (v1.4.1
    port, phase 3): a non-finite probability is returned as None so the
    head's contribution DROPS (with a note in MLLayer) instead of
    poisoning the blend."""
    import math
    import numpy as np
    names = list(rows)
    if not names:
        return {}
    feats = bundle["feature_names"]
    X = np.array([[float(rows[t].get(f, float("nan"))) for f in feats]
                  for t in names], dtype=np.float64)
    if bundle.get("model_type") == "gbm_joblib":
        import io as _io
        import joblib
        # §3.1/§7.1 (B-1): unpickle ONLY the sha256-verified bytes captured
        # by _ml_load_head — the file on disk is never re-read, so a swap
        # between load and predict cannot smuggle bytes past the hash gate.
        data = bundle.get("_sidecar_bytes")
        if data is None:
            raise RuntimeError(
                "gbm bundle carries no verified sidecar bytes — load it "
                "through _ml_load_head (hash gate) before predicting")
        m = joblib.load(_io.BytesIO(data))
        P = m.predict_proba(X)[:, 1]
        return {t: (float(min(1.0, max(0.0, p))) if math.isfinite(p) else None)
                for t, p in zip(names, P)}
    med = np.asarray(bundle["impute_medians"], dtype=np.float64)
    mu = np.asarray(bundle["scaler_mean"], dtype=np.float64)
    sd = np.asarray(bundle["scaler_scale"], dtype=np.float64)
    sd = np.where(sd > 0, sd, 1.0)
    X = np.where(np.isnan(X), med, X)
    Z = (X - mu) / sd
    Z = Z @ np.asarray(bundle["coef"], dtype=np.float64) + float(bundle["intercept"])
    Z = float(bundle["calib_a"]) * Z + float(bundle["calib_b"])
    with np.errstate(over="ignore"):
        P = 1.0 / (1.0 + np.exp(-Z))
    return {t: (float(min(1.0, max(0.0, p))) if math.isfinite(p) else None)
            for t, p in zip(names, P)}


def _ml_scaled(p: float, base: float) -> float:
    """(p - base) / max(base, 1-base) in ~[-1, 1]: p at the base rate maps
    to 0, p=1 to +1, p=0 to -1. Monotone in p, no new tunables."""
    base = min(max(float(base), 1e-6), 1.0 - 1e-6)
    return (float(p) - base) / max(base, 1.0 - base)


def _ml_adjustment(parts: list[tuple[float, float, float | None, bool]]) -> float | None:
    """Bounded conviction_adj from (weight, p, base, include) contributions.
    The weights are the H2-frozen fusion priors (W_Q, W_E, MACRO_TILT_GAIN)
    — the overlay reuses the core's own opinion instead of inventing new
    ones. Excluded heads drop out of numerator AND denominator. B8
    (v1.4.1 port, phase 3): a non-finite p or base is unusable data — it
    drops the same way (belt under the load validation and the predict
    guard)."""
    import math
    num = den = 0.0
    for w, p, base, include in parts:
        if not include or p is None or base is None:
            continue
        if not (math.isfinite(float(p)) and math.isfinite(float(base))):
            continue
        num += w * _ml_scaled(p, base)
        den += w
    if den <= 0.0:
        return None
    bound = min(float(CONFIG["ML_ADJ_MAX"]), float(CONFIG["OVERLAY_MAX_ADJ"]))
    return float(max(-bound, min(bound, bound * num / den)))


class MLLayer(LayerBase):
    """L4 overlay: calibrated per-head probabilities (q / e / macro) from
    ml_train.py model files. UNTRAINED (no models, refused features, deps)
    runs loud and supplies nothing; SHADOW logs the probability WITH its
    sample size and changes no decision; ACTIVE (model state + a passing
    validation report) sets a bounded conviction_adj. Inference is pure
    numpy on the SAME features ml_dataset extracts — no sklearn, no
    network, offline-safe by construction."""
    name, order, stage = "ml", 4, "overlay"

    def __init__(self, models_dir: str | None = None) -> None:
        super().__init__()
        self._dir = models_dir

    def run(self, ctx: Context, decisions: list[Decision]) -> LayerResult:
        res = self._begin("1.0.0", "1.0.0")     # model-file schema version
        mdir = Path(self._dir or ctx.flags.get("ml_models_dir")
                    or CONFIG["ML_MODELS_DIR"])
        loaded: dict[str, dict] = {}
        heads: dict[str, dict] = {}
        notes: list[str] = []
        unavailable: list[str] = []
        for head in ("q", "e", "macro"):
            b, note = _ml_load_head(mdir, head)
            state = "UNTRAINED" if b is None else str(b["state"])
            if b is None and "UNAVAILABLE" in note:
                state = "UNAVAILABLE"          # §3.1 (B-1): env/version block
                unavailable.append(f"{head}: {note.split('— ', 1)[-1].strip()}")
            heads[head] = {"state": state, "note": note}
            if b is not None:
                loaded[head] = b
                heads[head].update({
                    "n_train": int(b.get("n_train", 0)),
                    "base_rate": float(b.get("base_rate", 0.5)),
                    "model_type": str(b.get("model_type", "")),
                    "train_from": str(b.get("train_from", "")),
                    "train_to": str(b.get("train_to", "")),
                    "trained_at": str(b.get("trained_at", ""))})   # provenance date
            if "REFUSED" in note or "refused" in note or "UNAVAILABLE" in note:
                notes.append(note)     # leakage / downgrade / env block: loud
        if unavailable:
            res.status = "DEGRADED"
            res.ctx_out = {"state": "DEGRADED", "heads": heads,
                           "unavailable": tuple(unavailable)}
            res.warnings = tuple(dict.fromkeys(notes))[:12]
            if not loaded:
                return res
        elif not loaded:
            res.status = "DEGRADED"
            w = notes + [f"ml: UNTRAINED — no models in {mdir} "
                         "(train: python3 ml_train.py)"]
            res.warnings = tuple(dict.fromkeys(w))[:12]
            res.ctx_out = {"state": "UNTRAINED", "heads": heads}
            return res
        missing = [h for h in ("q", "e", "macro") if h not in loaded]
        if missing:
            res.status = "DEGRADED"
            res.warnings = tuple(dict.fromkeys((*notes,
                f"ml: head(s) {', '.join(missing)} UNTRAINED — overlay runs "
                "on the loaded heads only",)))
        try:
            import ml_dataset                     # the ONE feature source
        except Exception as e:
            res.status = "DEGRADED"
            res.warnings = tuple(dict.fromkeys(
                (*res.warnings, f"ml: UNTRAINED — ml_dataset.py not importable "
                                f"({_exc(e)})")))[:12]
            res.ctx_out = {"state": "UNTRAINED", "heads": heads}
            return res
        as_of = ctx.as_of or date.today().isoformat()
        try:
            rec = ml_dataset.record_from_parts(as_of, ctx.regime, decisions)
            feats = ml_dataset.date_features(rec)
        except Exception as e:
            res.status = "ERROR"
            res.warnings = (f"ml: feature extraction failed: {_exc(e)}",)
            res.ctx_out = {"state": "UNTRAINED", "heads": heads}
            return res
        p_q = _ml_predict(loaded["q"], feats) if "q" in loaded else {}
        p_e = _ml_predict(loaded["e"], feats) if "e" in loaded else {}
        p_m: dict[str, float | None] = {}
        if "macro" in loaded:
            try:
                mrows = ml_dataset.macro_features(rec)
                mnames = list(ml_dataset.macro_feature_names())
                per_etf = {etf: dict(zip(mnames, row)) for etf, row in mrows.items()}
                p_m = _ml_predict(loaded["macro"], per_etf)
            except Exception as e:
                res.warnings = (*res.warnings, f"ml: macro head inference: {_exc(e)}")
        # B8 (v1.4.1 port, phase 3): a non-finite probability is unusable
        # data — the head's contribution DROPS with a loud note, it never
        # reaches the blend
        dropped = {h: sum(1 for v in pm.values() if v is None)
                   for h, pm in (("q", p_q), ("e", p_e), ("macro", p_m))}
        if any(dropped.values()):
            res.warnings = (*res.warnings,
                "ml: non-finite probability dropped — head(s) "
                + ", ".join(f"{h} ({n} row(s))" for h, n in dropped.items() if n)
                + " contribute nothing this run")
        base_q = float(loaded["q"].get("base_rate", 0.5)) if "q" in loaded else None
        base_e = float(loaded["e"].get("base_rate", 0.5)) if "e" in loaded else None
        base_m = float(loaded["macro"].get("base_rate", 0.5)) if "macro" in loaded else None
        sec_to_etfs: dict[str, list[str]] = {}
        for etf, pairs in CONFIG["ETF_TO_SECTORS"].items():
            for sec, _s in pairs:
                sec_to_etfs.setdefault(sec, []).append(etf)
        act = {h: loaded[h]["state"] == "ACTIVE" for h in loaded}
        any_active = any(act.values())
        for d in decisions:
            t = d.ticker
            f: dict[str, Any] = {
                "state": "ACTIVE" if any_active else "SHADOW",
                "p_q": p_q.get(t), "p_e": p_e.get(t),
                "n_q": (int(loaded["q"].get("n_train", 0)) if "q" in loaded else None),
                "n_e": (int(loaded["e"].get("n_train", 0)) if "e" in loaded else None),
                "p_m": None, "s_m": None}
            s_m = None
            qsig = d.layers.get("quality")
            m_sec = ((qsig.facts.get("macro_sector") if qsig is not None else "")
                     or d.sector or "")
            if p_m and base_m is not None:
                etfs = [e for e in sec_to_etfs.get(m_sec, ()) if e in p_m]
                good = [e for e in etfs if p_m[e] is not None]
                if good:
                    s_m = sum(_ml_scaled(p_m[e], base_m) for e in good) / len(good)
                    f["p_m"] = sum(p_m[e] for e in good) / len(good)
                    f["s_m"] = s_m
            would = _ml_adjustment([
                (CONFIG["W_Q"], f["p_q"], base_q, True),
                (CONFIG["W_E"], f["p_e"], base_e, True),
                (CONFIG["MACRO_TILT_GAIN"], f["p_m"], base_m, True)])
            applied = _ml_adjustment([
                (CONFIG["W_Q"], f["p_q"], base_q, act.get("q", False)),
                (CONFIG["W_E"], f["p_e"], base_e, act.get("e", False)),
                (CONFIG["MACRO_TILT_GAIN"], f["p_m"], base_m, act.get("macro", False))])
            f["adj"] = applied if (applied is not None and any_active) else would
            segs = []
            if f["p_q"] is not None:
                segs.append(f"p_q {f['p_q']:.2f} (n={f['n_q']})")
            elif "q" in loaded:
                segs.append("p_q dropped (non-finite)")
            if f["p_e"] is not None:
                segs.append(f"p_e {f['p_e']:.2f} (n={f['n_e']})")
            elif "e" in loaded:
                segs.append("p_e dropped (non-finite)")
            adj_s = "no adj (no head scored this name)" if f["adj"] is None \
                else f"{'adj' if (any_active and applied is not None) else 'would adj'} {f['adj']:+.1f}"
            if any_active and applied is not None:
                f["conviction_adj"] = applied
                f["p_note"] = " · ".join(segs + [adj_s, "ACTIVE, bounded"])
            else:
                f["p_note"] = " · ".join(segs + [adj_s, "SHADOW, logged not applied"])
            res.signals[t] = LayerSignal(t, "ml", score=None, grade=str(f["state"]),
                                         status="OK", facts=f, source="ml_train",
                                         as_of=as_of)
        if res.status != "DEGRADED":
            res.status = "OK"
        res.ctx_out = {"state": ("ACTIVE" if any_active else "SHADOW"),
                       "heads": heads,
                       "macro": {e: (p if p is None else round(p, 3))
                                 for e, p in sorted(p_m.items())}}
        if unavailable:      # §3.1 (B-1): carry the env-block reasons through
            res.ctx_out["unavailable"] = tuple(unavailable)
            res.ctx_out["state"] = "DEGRADED"
        return res


class RiskLayer(LayerBase):
    """L5 sizer: fills Decision.weight from volatility-based sizing with
    concentration caps, a correlation-aware gross cap and a drawdown
    portfolio veto. Prices come from the earnings engine's own adapter
    (the one blessed price source, disk-cached; offline guard identical to
    EarningsLayer's). Weights are assigned ATOMICALLY: a timeout or error
    leaves every weight untouched (None), never a half-sized book."""
    name, order, stage = "risk", 5, "sizer"

    def __init__(self) -> None:
        super().__init__()
        self._eng = None

    def _engine(self, ctx: Context):
        if self._eng is None:
            import earnings_engine
            eng = earnings_engine.EarningsEngine(
                workers=int(ctx.flags.get("workers") or CONFIG["DEFAULT_WORKERS"]),
                cache_dir=(ctx.flags.get("earnings_cache_dir") or None),
                cache_ttl_hours=(1e9 if ctx.flags.get("offline") else 12.0))
            if ctx.flags.get("offline"):
                eng._fetch = _offline_raiser       # same guards as EarningsLayer
                eng._pfetch = _offline_raiser
                eng._px_fetch = _offline_raiser
            else:
                if callable(getattr(eng, "_pfetch", None)):
                    eng._pfetch = _retrying_fetch(eng._pfetch, "risk prices")
                if callable(getattr(eng, "_px_fetch", None)):
                    eng._px_fetch = _retrying_fetch(eng._px_fetch, "risk prices")
            self._eng = eng
        return self._eng

    def _price_data(self, ctx: Context, longs: list[str]):
        """{ticker: close Series} for the LONG names (bounded by
        RISK_MAX_PRICE_NAMES); ({}, note) when unavailable — never raises."""
        if ctx.flags.get("offline"):
            return {}, "offline: prices not fetched — equal-weight fallback"
        try:
            eng = self._engine(ctx)
        except Exception as e:
            return {}, f"price engine unavailable ({_exc(e)}) — equal-weight fallback"
        anchor = (date.fromisoformat(ctx.as_of) if ctx.as_of else date.today())
        start = (anchor - timedelta(days=380)).isoformat()   # 126 td + buffer
        series: dict[str, Any] = {}
        for t in longs[:int(CONFIG["RISK_MAX_PRICE_NAMES"])]:
            try:
                s = eng.prices(t, start)
                if s is not None and len(s):
                    series[t] = s
            except Exception:
                continue
        note = "" if series else "no price history (fetch failed) — equal-weight fallback"
        return series, note

    def run(self, ctx: Context, decisions: list[Decision]) -> LayerResult:
        res = self._begin(__version__, __version__)
        prog = ctx.flags.get("progress")
        longs = [d.ticker for d in decisions if d.action == "LONG"]
        if prog and prog.alive("risk") and longs:
            prog.set(f"risk: sizing {len(longs)} LONG names")
        if longs:
            series, note = self._price_data(ctx, longs)
        else:
            series, note = {}, ""      # nothing to fetch; size_portfolio says all-cash
        vols = {t: _ann_vol(s, ctx.as_of) for t, s in series.items()}
        vols = {t: v for t, v in vols.items() if v is not None}
        rho = _rho_bar(series, ctx.as_of)
        # phase 4 (P-2): the OPT-IN sizing mode from the run flags
        # (--sizing vol_target; CONFIG RISK_SIZING_MODE default legacy).
        mode = str(ctx.flags.get("sizing") or CONFIG["RISK_SIZING_MODE"])
        sized = size_portfolio(
            longs, vols, rho, {d.ticker: d.sector for d in decisions},
            float(ctx.risk_budget), mode=mode)
        if note:
            sized["notes"].insert(0, note)
        # ATOMIC assignment: every weight lands at once, after all caps
        adv_checked = bool(sized.get("adv_checked", False))   # F9 (v1.8.3)
        by_t = {d.ticker: d for d in decisions}
        for t, w in sized["weights"].items():
            by_t[t].weight = round(float(w), 4)
            by_t[t].adv_checked = adv_checked    # F9: additive Decision field
        for d in decisions:                       # non-LONG rows: explicit 0
            if d.ticker not in sized["weights"]:
                d.weight = 0.0
        if sized.get("fallback"):
            res.status = "DEGRADED"
            res.warnings = ("risk sizer: " + note,) if note else ()
        res.ctx_out = risk_ctx_out(sized)
        if prog:
            prog.kill("risk")
        return res


LAYER_REGISTRY: dict[str, type[LayerBase]] = {
    "macro": MacroLayer, "quality": QualityLayer, "earnings": EarningsLayer,
    "ml": MLLayer, "risk": RiskLayer,
}
LAYERS: list[LayerBase] = [LAYER_REGISTRY[n]() for n in LAYER_REGISTRY]


def build_layers(only: set[str] | None, skip: set[str] | None,
                 registry: "dict[str, type[LayerBase]] | None" = None) -> list[LayerBase]:
    """Ordered instances for one run, straight from the REGISTRY in
    insertion order (phase 3 / A15): a registered + selected layer is
    ALWAYS constructed and run — it runs or fails loudly, never a silent
    skip. `registry` lets callers (tests, MASTER_STUBS) substitute their
    own layer classes; the default is this module's LAYER_REGISTRY."""
    reg = LAYER_REGISTRY if registry is None else registry
    return [reg[n]() for n in reg
            if (not only or n in only) and (not skip or n not in skip)]


def _stubbed_registry() -> "dict[str, type[LayerBase]]":
    """MASTER_STUBS=1: the stub layers live in test_master.py since phase 3
    (all fakes moved out of master.py — H3). Loud 64 when it is absent —
    never silently run real layers under a STUBBED banner."""
    try:
        import test_master
    except Exception as e:
        raise MasterError("MASTER_STUBS=1: the stub layers live in test_master.py "
                          f"since phase 3 — put it next to master.py ({_exc(e)})", 2) from e
    return dict(getattr(test_master, "STUB_LAYERS"))


# ════════════════════════════════════════════════════════════════════════
#  § 4 · FUSION — gates -> conviction -> action -> reasons (priors, §4 spec)
# ════════════════════════════════════════════════════════════════════════
# P2-9: meds' basket reports XLP (Consumer Staples) and XLY (Consumer
# Discretionary) SEPARATELY, so quality's --bucket pools stay apart in the
# macro vocabulary too. Derived from ETF_TO_SECTORS (both map consumer at
# strength 1.0) — CONFIG itself is untouched (phase-2 gate). An unbucketed
# consumer name keeps the merged XLP+XLY view; in a defensive regime it is
# NOT tilt-punished (consumer is NOT in CYCLICAL_SECTORS — verified
# v1.8.3, F4: unbucketed consumer gets tilt 0.0). Only the BUCKET branch
# (sector == 'discretionary' via _BUCKET_ETF, macro_tilt) applies the
# defensive -0.5; bucketed staples never get it. Limit: quality
# percentiles are still computed inside the pinned --bucket pool (that is
# the point of --bucket); SPY's weak mapping covers the merged group only.
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
            # phase-4 hunt fix: interpolated — the old hard-coded x0.5
            # could lie the moment MACRO_DEGRADED_DAMP changed
            why += f" (damped x{CONFIG['MACRO_DEGRADED_DAMP']:g})"
        d.reasons.append(f"macro {t:+.1f}: {why}")
    if e is not None:
        seg = f"E {e:.0f} ({d.layers['earnings'].grade})"
        if e_sig is not None and e_sig.facts.get("plan") == "LONG":
            seg += f" NOW (report {e_sig.facts.get('days_since', '?')}d)"
        if weak:
            # phase-4 hunt fix: the label INTERPOLATES the CONFIG value —
            # a hard-coded x0.5 could lie the moment the key changed
            seg += f" (weak x{CONFIG['EARNINGS_WEAK_SCALE']:g})"
        d.reasons.append(seg)
    else:
        word = e_sig.status if e_sig is not None else "MISSING"
        why = {"DISABLED": "E layer off (--earnings-mode off)",
               "NOT_SELECTED": "E not selected (top-K funnel)",
               "MISSING_DATA": "E no data (<4 quarters or provider failed)",
               "ERROR": "E error"}.get(word, f"E {word}")   # P2-10 vocabulary
        if _ruleset() == "v2":
            # P-1 (phase 4): v2 says WHAT the fill was, not just 'missing'
            d.reasons.append(
                f"{why} -> conservative fill "
                f"E={float(CONFIG['E_MISSING_V2']):.1f} (ruleset v2, "
                f"W_Q {float(CONFIG['W_Q']):.2f} effective)")
        else:
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
    # P1-1: defence in depth — even a hand-built/foreign signal cannot smuggle
    # NaN/inf/out-of-range into fusion (NaN compares False and made LONG).
    q = (_finite(q_sig.score, 0.0, 100.0)
         if (q_sig is not None and q_sig.status == "OK" and q_sig.score is not None)
         else None)
    e = (_finite(e_sig.score, 0.0, 100.0)
         if (e_sig is not None and e_sig.status == "OK" and e_sig.score is not None)
         else None)
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
        raw = max(0.0, min(100.0, _base_conviction(q, e, weak) * mv["mult"]))
        d.conviction_raw = raw              # phase 4 (P-6): the unrounded door value
        d.conviction = round(raw, 1)         # display stays rounded, both rulesets
        d.grade = _native_grade("MASTER_GRADES", d.conviction)
    # hard quality gate (macro never vetoes)
    if q is None:
        d.action = "AVOID"
        d.blocked = "no quality score"
        why = (q_sig.facts.get("engine_status") if q_sig else None) or "LAYER OFF"
        # final phase (§2.3): a stale/unscorable name never appears as a
        # bare 'F 0' — the one-line reason names the CAUSE (engine flags +
        # first warning), and the existing ranking rules (action, then
        # conviction, then ticker) already place it below every LONG/WATCH.
        if q_sig is not None:
            stale = sorted(f for f in q_sig.flags if "STALE" in str(f).upper())
            first_w = next((w for w in q_sig.warnings if w), "")
            if stale or str(why).upper().startswith("STALE"):
                cause = (f"quality data STALE: {', '.join(stale) or why}"
                         + (f" — {first_w[:90]}" if first_w else ""))
            else:
                cause = (f"no quality score ({why}"
                         + (f": {first_w[:90]}" if first_w else "") + ")")
        else:
            cause = f"no quality score: {why}"
        d.reasons.insert(0, cause)
    elif veto:
        d.action = "AVOID"
        d.blocked = "veto"
        d.reasons.insert(0, _cap_avoid_conviction(d, f"veto: {', '.join(veto)}"))
    elif q < CONFIG["MIN_QUALITY"]:
        d.action = "AVOID"
        d.blocked = "gate"
        d.reasons.insert(0, _cap_avoid_conviction(
            d, f"Q {q:.0f} ({d.layers['quality'].grade}) < {CONFIG['MIN_QUALITY']:.0f} gate"))
    else:
        capped = mv["tilt"] is not None and mv["tilt"] < 0
        now = bool(e_sig is not None and e_sig.facts.get("plan") == "LONG")
        trig_block = (mode == "trigger") and not now
        door = _door_value(d)               # phase 4 (P-6): raw under v2
        if door >= CONFIG["ACTION_LONG_AT"] and not capped and not trig_block:
            d.action = "LONG"
        elif (door >= CONFIG["ACTION_WATCH_AT"]
                or (door >= CONFIG["ACTION_LONG_AT"] and (capped or trig_block))):
            d.action = "WATCH"
        else:
            d.action = "AVOID"
        _reasons(d, cand, q, e, q_sig, e_sig, state, mv, weak, mode, capped, trig_block)
    d.reasons = d.reasons[:CONFIG["MAX_REASONS"]]
    return d


_ACTION_RANK = {"LONG": 0, "WATCH": 1, "AVOID": 2}


def _rank_key(d: Decision) -> tuple[int, float, str]:
    """P1-6: table order is action (LONG, WATCH, AVOID), then conviction
    descending, then ticker — a vetoed 72 could previously outrank a LONG."""
    return (_ACTION_RANK.get(d.action, 3), -d.conviction, d.ticker)


def _cap_avoid_conviction(d: Decision, why: str) -> str:
    """P1-6 (A3): an AVOID row (veto / gate fail) never displays a conviction
    in WATCH/LONG territory; the reason keeps the uncapped value. Cap is
    WATCH-1 so even the 0-decimal table render stays visibly below the door.
    Phase 4: the RAW door value is capped too, so a v2 unrounded re-gate can
    never push a blocked row back over a door it must stay below."""
    cap = round(CONFIG["ACTION_WATCH_AT"] - 1.0, 1)   # 44.0
    if d.conviction > cap:
        raw = d.conviction
        d.conviction = cap
        if d.conviction_raw is not None and d.conviction_raw > cap:
            d.conviction_raw = float(cap)
        d.grade = _native_grade("MASTER_GRADES", d.conviction)
        return f"{why} (conviction capped {raw:.1f}->{cap:.1f})"
    return why


def fuse(ctx: Context, results: dict[str, LayerResult], mode: str = "boost") -> list[Decision]:
    """All decisions, sorted by action, then conviction desc, then ticker."""
    state = ctx.regime
    q_res, e_res = results.get("quality"), results.get("earnings")
    weak = bool(e_res is not None and e_res.ctx_out.get("weak"))
    out = []
    for cand in ctx.tickers:
        q_sig = (q_res.signals.get(cand.ticker) if q_res else None)
        # P2-10: an absent earnings signal is EXPLICIT about why: the layer
        # did not run (DISABLED) vs the ticker was not in the top-K funnel
        # (NOT_SELECTED) — no more ambiguous "E layer off".
        if e_res is None:
            e_sig = LayerSignal(cand.ticker, "earnings", status="DISABLED")
        else:
            e_sig = (e_res.signals.get(cand.ticker)
                     or LayerSignal(cand.ticker, "earnings", status="NOT_SELECTED"))
        if q_sig is None and q_res is not None:
            q_sig = LayerSignal(cand.ticker, "quality", status="MISSING",
                                facts={"engine_status": "NO_SIGNAL"})
        out.append(fuse_candidate(cand, q_sig, e_sig, state, mode, weak))
    out.sort(key=_rank_key)
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
        # phase 4 (P-1): ONE missing-E prior — _base_conviction(q, None) is
        # q*E_MISSING_HAIRCUT under legacy (identical to the shipped rule)
        # and the conservative-fill blend under ruleset v2, so the funnel and
        # the fusion can never disagree about what "E assumed missing" means.
        ranked.append((_base_conviction(q_sig.score, None, False) * mv["mult"],
                       cand.ticker, cand))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    return [c for _, _, c in ranked[:max(0, int(k))]]


def _apply_overlays(decisions: list[Decision],
                    results: dict[str, LayerResult], mode: str) -> None:
    """Phase 3: registered overlay layers (stage='overlay', L4-style) get the
    last word on conviction — bounded by CONFIG['OVERLAY_MAX_ADJ'], never on
    veto/gate AVOIDs (those stay capped below WATCH, P1-6), the clamp
    disclosed in the reasons line. Action re-gates with the SAME H2
    thresholds, honouring the macro cap and the trigger rule.
    v1.4.1 (B5), ported in phase 2: the pass FIRST re-asserts EVERY blocked
    row (AVOID + below-WATCH cap) once per decision, BEFORE any overlay
    signal is consulted — a hand-built/foreign blocked-but-LONG/WATCH state
    cannot survive even when no overlay produced a signal for the name
    (v1.4.1's first version covered only rows WITH a signal; the fuzz
    invariant caught it). Idempotent by construction."""
    overlays = [r for r in sorted(results.values(), key=lambda r: r.order)
                if r.stage == "overlay"]
    bound = float(CONFIG["OVERLAY_MAX_ADJ"])
    for d in decisions:
        if d.blocked and (d.action != "AVOID"
                          or d.conviction >= CONFIG["ACTION_WATCH_AT"]):
            # B5 (defence in depth): a blocked row that arrives in a
            # hand-built/foreign state (blocked but still LONG/WATCH, or
            # uncapped) is re-asserted HERE — once per decision, before any
            # overlay signal is consulted — so the guarantee 'blocked =>
            # AVOID with conviction below WATCH' holds for ALL rows. The
            # W_BLOCKED_REASSERT code marks the correction for the phase-5
            # ERRORS & WARNINGS block.
            d.action = "AVOID"
            d.reasons.append(_cap_avoid_conviction(
                d, f"overlay pass: blocked row re-asserted AVOID "
                   f"({d.blocked}) [W_BLOCKED_REASSERT]"))
    for d in decisions:
        for res in overlays:
            sig = res.signals.get(d.ticker)
            if sig is None:
                continue
            d.layers[res.name] = sig
            adj = sig.facts.get("conviction_adj")
            if adj is None:
                # phase 5: a SHADOW overlay (an ML head with no passing
                # validation report) has a view but changes NO decision —
                # it is logged here and that is all.
                pn = sig.facts.get("p_note")
                if pn:
                    d.reasons.append(f"overlay {res.name}: {pn}")
                continue
            adj = float(adj)
            if d.blocked:
                d.reasons.append(f"overlay {res.name}: skipped ({d.blocked} "
                                  "AVOID — never adjusted)")
                continue
            use = max(-bound, min(bound, adj))
            clamped = "" if use == adj else f" clamped {adj:+.0f}->{use:+.0f}"
            # phase 4 (P-6): under ruleset v2 the overlay arithmetic and
            # the re-gate run on the UNROUNDED conviction (the overlay
            # nudges the raw value; the display stays rounded). Legacy keeps the
            # legacy arithmetic byte-for-byte when the ruleset is legacy.
            if _ruleset() == "v2" and d.conviction_raw is not None:
                d.conviction_raw = min(100.0, max(0.0, d.conviction_raw + use))
                d.conviction = round(d.conviction_raw, 1)
                door = d.conviction_raw
            else:
                d.conviction = round(min(100.0, max(0.0, d.conviction + use)), 1)
                door = d.conviction
            d.grade = _native_grade("MASTER_GRADES", d.conviction)
            m_sig = d.layers.get("macro")
            tilt = (m_sig.facts.get("tilt") if m_sig else None)
            capped = tilt is not None and tilt < 0
            e_sig = d.layers.get("earnings")
            trig_block = (mode == "trigger"
                           and not (e_sig is not None and e_sig.facts.get("plan") == "LONG"))
            if door >= CONFIG["ACTION_LONG_AT"] and not capped and not trig_block:
                d.action = "LONG"
            elif (door >= CONFIG["ACTION_WATCH_AT"]
                  or (door >= CONFIG["ACTION_LONG_AT"] and (capped or trig_block))):
                d.action = "WATCH"
            else:
                d.action = "AVOID"
            d.reasons.append(f"overlay {res.name}: {use:+.0f} (bounded "
                             f"±{bound:g}{clamped})")

# ════════════════════════════════════════════════════════════════════════
#  § 5 · ORCHESTRATOR — context, parallel prefetch, funnel, fuse
# ════════════════════════════════════════════════════════════════════════
# ── § 5.1 · context build (candidates + flags; raises MasterError on bad input)
def _parse_layers(ns: argparse.Namespace) -> tuple[set[str] | None, set[str] | None]:
    only = {s.strip() for s in (ns.only or "").split(",") if s.strip()} or None
    skip = {s.strip() for s in (ns.skip or "").split(",") if s.strip()} or None
    known = set(LAYER_REGISTRY)          # 'ml'/'risk' reserved: not selectable yet
    bad = (only or set()) | (skip or set())
    bad -= known
    if bad:
        raise MasterError(f"unknown layer(s): {', '.join(sorted(bad))} "
                           f"(known: {', '.join(sorted(known))})", 2)
    if only and skip and (only & skip):
        raise MasterError(f"--only and --skip overlap on {', '.join(sorted(only & skip))}", 2)
    return only, skip


def _watchlist_rows(path: str) -> list[tuple[str, str | None]]:
    """One (ticker, sector|None) per line: 'TICKER' or 'TICKER,sector'."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise MasterError(f"watchlist {path}: {e}", 2) from e
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


_CAP_BANDS: dict[str, tuple[float, "float | None"]] = {
    # phase 3: conventional round breakpoints — a vocabulary, not a tuned
    # value (the CONFIG gate stays untouched). Half-open [lo, hi) in USD.
    "mega": (200e9, None), "large": (10e9, 200e9), "mid": (2e9, 10e9),
    "small": (0.0, 2e9),
}


def _universe_probe() -> dict[str, Any]:
    """ONE probe behind the wizard, --sectors and --cap (phase 3). Reads the
    quality engine's own state (H3: invents nothing). ok=False carries the
    reason; refs is None when the engine exposes no per-name refs."""
    try:
        import quality  # noqa: PLC0415 (lazy by design — H1/H8)
    except Exception as e:
        return {"ok": False, "groups": {}, "refs": None,
                "reason": f"quality import failed: {_exc(e)}"}
    refs: list | None = None
    gu = getattr(quality, "get_universe", None)
    if callable(gu):
        try:
            out = gu()
            refs = out[0] if isinstance(out, tuple) else out
        except Exception as e:
            return {"ok": False, "groups": {}, "refs": None,
                    "reason": f"get_universe failed: {_exc(e)}"}
    groups: dict[str, int] = {}
    if refs is not None:
        for r in refs:
            if getattr(r, "status", "active") == "active":
                g = getattr(r, "sector", "") or ""
                groups[g] = groups.get(g, 0) + 1
    else:
        gmap = getattr(quality, "GROUPS", None)
        if isinstance(gmap, dict):
            groups = {k: len(v) for k, v in gmap.items()
                      if isinstance(v, (list, tuple))}
    if not groups:
        return {"ok": False, "groups": {}, "refs": refs,
                "reason": "quality universe exposes no sector groups"}
    return {"ok": True, "groups": groups, "refs": refs, "reason": ""}


def _sector_scope(spec: str) -> tuple[set[str], list, str]:
    """'all' or comma groups -> (wanted, active refs, error)."""
    p = _universe_probe()
    if not p["ok"]:
        return set(), [], p["reason"]
    known = set(p["groups"])
    want = (None if spec.strip().lower() in ("", "all")
            else {s.strip().lower() for s in spec.split(",") if s.strip()})
    if want is None:
        want = set(known)
    bad = want - known
    if bad:
        return set(), [], (f"unknown group(s) {', '.join(sorted(bad))} "
                            f"(known: {', '.join(sorted(known))})")
    refs = p["refs"]
    if not refs:
        return set(), [], "universe gives no per-name refs (get_universe absent)"
    sel = [r for r in refs
           if getattr(r, "status", "active") == "active"
           and (getattr(r, "sector", "") or "").lower() in want]
    return want, sel, ""


def _mcap_map() -> tuple[bool, dict[str, float], str]:
    """(available, {ticker: usd market cap}, reason) from the universe refs."""
    p = _universe_probe()
    if not p["ok"]:
        return False, {}, p["reason"]
    out: dict[str, float] = {}
    for r in (p["refs"] or []):
        mc = getattr(r, "market_cap", None)
        if isinstance(mc, (int, float)) and float(mc) > 0:
            t = getattr(r, "ticker", "")
            if t:
                out[t] = float(mc)
    if not out:
        return False, {}, ("no market-cap data at universe scope — quality "
                           "computes price x shares per name at scoring time; "
                           "universe refs carry no caps")
    return True, out, ""


def _build_context(ns: argparse.Namespace, restores: list | None = None) -> Context:
    """Candidates + flags. Sleeve ETFs never go to L2/L3 (macro card only).
    restores (P2-3): every env/module mutation this run makes is registered
    here or in a layer adapter and undone by run_pipeline's finally."""
    cands: list[Candidate] = []
    by_t: dict[str, Candidate] = {}

    def _add(raw: str, sector: str | None, bucket: str | None) -> None:
        t = _norm_ticker(raw)
        if t is None:
            raise MasterError(f"{raw!r} does not look like a ticker (e.g. AAPL, BRK-B)", 2)
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
                               f"{', '.join(sorted(CONFIG['QUALITY_SECTORS']))}", 2)
        _add(t, sector.lower() if sector else None, None)
    for spec in (ns.sector or []):
        t, _, val = spec.partition("=")
        if not val or val.lower() not in CONFIG["QUALITY_SECTORS"]:
            raise MasterError(f"--sector {spec!r}: expected TICKER=<group> with group in "
                               f"{', '.join(sorted(CONFIG['QUALITY_SECTORS']))}", 2)
        _add(t, val.lower(), None)
    for spec in (ns.bucket or []):
        t, _, val = spec.partition("=")
        if val not in ("staples", "discretionary"):
            raise MasterError(f"--bucket {spec!r}: expected TICKER=staples|discretionary", 2)
        _add(t, None, val)
    # phase 3: --sectors scopes the run to the quality universe's active
    # names in those groups (one probe, H3: reads engine state, invents
    # nothing; a probe failure is a LOUD 64, never a silent empty run).
    if getattr(ns, "sectors", None):
        _groups, sel, err = _sector_scope(ns.sectors)
        if err:
            raise MasterError(f"--sectors {ns.sectors!r}: {err}", 2)
        added = 0
        for r in sel:
            t = _norm_ticker(getattr(r, "ticker", "") or "")
            if t is None or t in by_t:
                continue
            _add(t, (getattr(r, "sector", "") or "").lower() or None, None)
            added += 1
        if not added:
            raise MasterError("--sectors selected 0 active names — nothing to score", 2)
    if not cands:
        for t in CONFIG["DEFAULT_WATCHLIST"]:
            _add(t, None, None)
    sleeve = [c.ticker for c in cands if c.ticker in CONFIG["SLEEVE_ETFS"]]
    cands = [c for c in cands if c.ticker not in CONFIG["SLEEVE_ETFS"]]
    flags: dict[str, Any] = {
        "source": ns.source, "offline": ns.offline, "workers": ns.workers,
        "peers": ns.peers, "earnings_prefetch": ns.earnings_prefetch,
        "earnings_backtest": ns.earnings_backtest, "verbose": ns.verbose,
        "earnings_top": getattr(ns, "earnings_top", None),
        "ml_models_dir": getattr(ns, "ml_models_dir", None),
        "restores": restores if restores is not None else [],
        "ruleset": str(getattr(ns, "ruleset", None) or CONFIG["RULESET"]),
        "sizing": str(getattr(ns, "sizing", None) or CONFIG["RISK_SIZING_MODE"]),
    }
    # phase 3: --cap band filter — only when the universe refs actually
    # carry market caps (honest 64 otherwise); excluded-for-no-data names
    # are disclosed in the warnings, never silently scored.
    if getattr(ns, "cap", None) and ns.cap != "any":
        band = _CAP_BANDS[ns.cap]
        ok, by_mcap, reason = _mcap_map()
        if not ok:
            raise MasterError(f"--cap {ns.cap}: market-cap filter unavailable — "
                              f"{reason}", 2)
        kept: list[Candidate] = []
        excl: list[str] = []
        for c in cands:
            mc = by_mcap.get(c.ticker)
            if mc is None:
                excl.append(c.ticker)
                continue
            lo, hi = band
            if mc >= lo and (hi is None or mc < hi):
                kept.append(c)
        cands = kept
        if excl:
            flags["cap_excluded"] = excl
            flags["cap_band"] = ns.cap
        if not cands:
            raise MasterError(f"--cap {ns.cap}: every candidate fell outside the "
                              "band — nothing to score", 2)
    if ns.cache_dir:
        base = str(Path(ns.cache_dir))
        # P2-3: set BEFORE import quality (engine reads env at import time)
        # and RESTORED after the run — two runs in one process leak nothing.
        for k, v in (("QE_DATA_DIR", os.path.join(base, "quality")),
                     ("QE_CACHE_DIR", os.path.join(base, "quality", "cache"))):
            g = _EnvRestore(k, v)
            if restores is not None:
                restores.append(g)
            else:                       # standalone call: still set (undo list absent)
                os.environ[k] = v
        flags["earnings_cache_dir"] = os.path.join(base, "earnings")
    ctx = Context(as_of=ns.as_of, tickers=cands, flags=flags)
    if not cands:
        raise MasterError("no equity tickers left (only non-equity sleeve ETFs: "
                           + ", ".join(sleeve) + " — macro card only)", 2)
    return ctx


# ── § 5.2 · guarded phase calls (per-layer wall-clock budget) ────────────
def _soft_deadline_call(deadline: float, fn: Callable[..., Any], *args: Any,
                        layer: str | None = None) -> Any:
    """SOFT deadline only (P2-1): run fn on one throwaway thread and raise
    TimeoutError when the budget expires — the worker thread itself is NEVER
    killed and NEVER interrupted mid-write (a hard kill would need a
    subprocess boundary; the engines are never touched). A late worker keeps
    filling engine caches in the background; master just stops WAITING for
    it, and run_pipeline snapshots the results at the fusion boundary so a
    late write can never mutate what fusion/render already read.
    v1.8.1: `layer=` tags the worker thread's fetches for the net guard's
    FETCH HEALTH (per-layer attribution, N4)."""
    if layer:
        from me.netguard import layer_scope
        inner = fn

        def _scoped(*a: Any, **k: Any) -> Any:
            with layer_scope(layer):
                return inner(*a, **k)
        fn = _scoped
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError()
    ex = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mx-run")
    try:
        return ex.submit(fn, *args).result(timeout=remaining)
    finally:
        ex.shutdown(wait=False, cancel_futures=True)


def _snapshot_results(results: dict[str, LayerResult]) -> dict[str, LayerResult]:
    """P2-1: freeze the layer results at the fusion boundary. A timed-out
    layer's stuck thread keeps mutating its ORIGINAL LayerResult (that is by
    design — cache filling); fusion, warnings, exit logic, render and JSON
    all read THIS snapshot, so nothing a late worker writes afterwards can
    change an already-fused decision."""
    out: dict[str, LayerResult] = {}
    for name, res in results.items():
        cp = LayerResult(name=res.name, status=res.status, stage=res.stage,
                         order=res.order, elapsed_s=res.elapsed_s, cache=res.cache,
                         signals={t: copy.copy(s) for t, s in res.signals.items()},
                         ctx_out=dict(res.ctx_out), warnings=tuple(res.warnings),
                         engine_version=res.engine_version,
                         version_tested=res.version_tested)
        out[name] = cp
    return out


def _prefetch_one(layer: LayerBase, ctx: Context) -> LayerResult | None:
    from me.netguard import layer_scope
    try:
        with layer_scope(layer.name):          # N4: per-layer fetch attribution
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
def _assert_cache_writable(ctx: Context, restores: list | None,
                           note: Callable[[str], None]) -> None:
    """§2.5 (degradation matrix, last row): an ONLINE run writes caches, so
    the cache roots must be writable. Missing dirs are created (the engines
    do that themselves; this pre-creates + checks). A read-only root is a
    CLEAR error with the fix and exit 2 — never a traceback deep inside an
    engine, and never a silent no-cache run. Offline runs only read and
    skip this check entirely (§2.6)."""
    dirs = _layer_cache_dirs(ctx)
    checked: dict[str, str] = {}
    qmod = sys.modules.get("quality")
    if qmod is not None:
        checked["quality data"] = str(getattr(qmod, "DATA_DIR", "data") or "data")
        checked["quality cache"] = dirs.get("quality", "data/cache")
    checked["earnings cache"] = dirs.get("earnings", "")
    checked["meds cache"] = dirs.get("meds_cache", "")
    bad: list[str] = []
    for label, path in checked.items():
        if not path:
            continue
        p = Path(path)
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".master_write_probe"
            probe.write_text("", encoding="utf-8")
            probe.unlink()
        except OSError as e:
            bad.append(f"{label}: {path} not writable ({_exc(e)[:80]})")
    if bad:
        raise MasterError(
            "cache dir(s) not writable for an online run: " + "; ".join(bad)
            + " — fix: chmod/chown the dir, or pass --cache-dir to a writable "
              "location, or run --mode offline (reads only)", 2)
    note("cache dirs writable (online run will refresh stale items only)")


def _plan_banner(ctx: Context, layers: list[LayerBase], ns: argparse.Namespace,
                 stubbed: bool, net: str = "") -> None:
    """The anti-'stuck' banner on stderr: what this run will do (mode, ticker
    count, EXACT quality comparison pool, L3 funnel, per-layer budget), what
    state the caches are in, and the honest ETA with the faster alternative
    when the pass would be cold. Estimates come from COLD_S_PER_NAME /
    WARM_ETA_RANGE_S and are advisory only — never a decision input."""
    if stubbed or getattr(ns, "quiet", False):
        return
    mode = getattr(ns, "depth", None) or getattr(ns, "mode", "standard")
    warm = bool(getattr(ns, "warm", False))
    parts = [(f"warm-up run (macro+quality only, budget {ns.timeout:g}s)"
              if warm else f"mode {mode}"),
             (f"net {net}" if net else ""),
             f"{len(ctx.tickers)} tickers"]
    parts = [p for p in parts if p]
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
    if net == "online":
        # §3.1: the incremental-refresh plan — only stale/missing items hit
        # the network; fresh items are served from cache.
        sys.stderr.write("[plan] " + _refresh_plan_line(ctx, layers, ns) + "\n")
    sys.stderr.flush()


# ── § 5.2.6 · net-mode resolution + provenance (final phase) ──────────────
_NET_PROBE_MEMO: tuple[bool, str] | None = None


def _resolve_net_mode(ns: argparse.Namespace, stubbed: bool) -> tuple[str, str]:
    """Resolve the data mode for THIS run: ('online'|'offline', probe note).
    §4: auto probes once (2 s budget, DNS+TCP, no payload) — memoised per
    process so a many-run process pays once. Explicit online is VERIFIED
    (probe) and exits 3 'network required' when unreachable — never a
    silent fallback. MASTER_NET (online|offline|auto) overrides the probe:
    the hermeticity valve for test harnesses and CI (documented, never
    needed on a real terminal). Never called at import time; skipped
    entirely for offline."""
    global _NET_PROBE_MEMO
    want = str(getattr(ns, "net", "auto") or "auto")
    env = os.environ.get("MASTER_NET", "").strip().lower()
    if env in ("online", "offline"):
        # the documented CI/hermeticity valve: TRUST it, never probe
        return env, f"MASTER_NET={env} (override)"
    if env == "auto":
        want = "auto"
    if want == "offline":
        return "offline", ""                    # no probe for offline (spec)
    if stubbed:
        return "offline", ""                    # stubs never need the network
    if _NET_PROBE_MEMO is None:
        _NET_PROBE_MEMO = _net_probe()
    ok, note = _NET_PROBE_MEMO
    if want == "online" and not ok:
        raise MasterError(
            "network required (--mode online) but the probe failed — "
            f"{note}; use --mode offline for last-cached-truth or --mode "
            "auto to pick automatically", 3)
    return ("online" if ok else "offline"), note


def _age_days_from(as_of: str | None) -> int | None:
    """Calendar days from a YYYY-MM-DD stamp to today (None when unknown)."""
    if not as_of:
        return None
    try:
        return (date.today() - date.fromisoformat(str(as_of)[:10])).days
    except ValueError:
        return None


def _newest_file_date(path: str) -> str:
    """Date (YYYY-MM-DD) of the newest file under a dir ('' when absent)."""
    exists, newest = _dir_stamp(path)
    if not exists or newest <= 0:
        return ""
    return date.fromtimestamp(newest).isoformat()


def _earnings_px_date(cache_dir: str) -> str:
    """Newest px_*.csv fetch stamp under the earnings cache ('' absent)."""
    p = Path(cache_dir)
    if not p.is_dir():
        return ""
    best = 0.0
    for f in p.glob("px_*.csv"):
        try:
            best = max(best, f.stat().st_mtime)
        except OSError:
            pass
    return date.fromtimestamp(best).isoformat() if best else ""


def layer_provenance(name: str, results: dict[str, LayerResult],
                     ctx: Context, cache_dirs: dict[str, str] | None = None) -> LayerProvenance:
    """§2.1/§2.2: per-layer provenance — source, data_as_of, age_days and a
    freshness status from the CONFIG thresholds. Dates come from the
    engines' own outputs where they expose them (meds effective_as_of,
    earnings last_date) and from cache-file mtimes otherwise (quality and
    price fetch stamps); `basis` says which. STALE keeps data and score and
    carries the age + reason — it never silently becomes OK.
    v1.8.2 (W3): STALE separates 'older than cadence' (the data simply
    has no newer period than its publication cadence allows) from
    'refresh failed' (THIS online run's fetch attempts failed — net-guard
    ledger evidence). Within cadence + no failed refresh is NOT STALE
    (the renderer shows 'refresh-due'); a failed refresh is STALE even
    within cadence."""
    dirs = cache_dirs or {}
    res = results.get(name)
    p = LayerProvenance(layer=name)
    # v1.8.2 (W3): did THIS run's refresh attempts for the layer fail?
    # (online runs only — offline/stub runs attempt no refresh; the
    # per-layer failed count comes from the net guard's ledger, N4)
    guard = ctx.flags.get("netguard")
    if guard is not None:
        try:
            lay_h = (guard.health().get("layers") or {}).get(name) or {}
            p.refresh_failed = bool(lay_h.get("failed"))
        except Exception:
            p.refresh_failed = False
    disp_stale = int(CONFIG["STALE_STATUS_DAYS"])
    if res is None:
        p.status = "DISABLED"
        p.reason = "layer did not run (--only/--skip/--earnings-mode off)"
        return p
    if ctx.flags.get("stubs"):
        p.source, p.status = "stub", "OK"
        p.basis = "stub layers: no engine data"
        return p
    if name == "macro":
        st = res.ctx_out.get("macro")
        tier = (getattr(st, "data_tier", "") or "").lower()
        p.source = "cache" if tier in ("cache", "snapshot") else "network"
        as_of = str(getattr(st, "effective_as_of", "") or "")
        if not as_of:                       # engine gave no date: cache stamp
            as_of = _newest_file_date(dirs.get("meds_cache", ""))
            p.basis = "meds meds_cache newest file mtime (engine gave no effective_as_of)"
        else:
            p.basis = "meds effective_as_of (engine output)"
        p.data_as_of, p.age_days = as_of, _age_days_from(as_of)
        if res.status == "ERROR" or st is None or not as_of:
            p.status = "MISSING_DATA" if res.status != "ERROR" else "ERROR"
            p.reason = "no macro data this run (offline with no snapshot, or engine error)"
        elif p.age_days is not None and p.age_days > int(CONFIG["FRESHNESS_MACRO_MAX_AGE_D"]):
            p.status = "STALE"
            # v1.8.1 (F4): 'older than cadence' — the monthly series simply
            # has no newer month; NOT a refresh failure (that is the
            # fetch-stamp wording the quality/earnings rows carry).
            p.reason = _stale_reason("macro", p.age_days)
        elif p.refresh_failed and p.age_days is not None \
                and p.age_days > disp_stale:
            # v1.8.2 (W3): a REAL failed refresh — the run was online, the
            # fetch attempts failed, and the served cache is past the
            # display threshold. STALE even within the monthly cadence.
            p.status = "STALE"
            p.reason = (f"refresh failed: this online run's macro fetch "
                        f"attempts failed (net-guard ledger) — the monthly "
                        f"data as-of {as_of} is {p.age_days}d old (within "
                        f"its {int(CONFIG['FRESHNESS_MACRO_MAX_AGE_D'])}d "
                        "cadence) but could not be refreshed")
        else:
            p.status = "OK"
        return p

    if name == "quality":
        qdir = dirs.get("quality", "")
        p.source = "cache" if res.cache == "warm" else "mixed"
        as_of = _newest_file_date(qdir)
        p.basis = ("quality cache newest file mtime (a FETCH stamp, not the "
                   "filing date; filings are quarterly — per-name staleness "
                   "is the engine's own STALE_DATA flags)")
        p.data_as_of, p.age_days = as_of, _age_days_from(as_of)
        if res.status == "ERROR" or not as_of:
            p.status = "MISSING_DATA" if res.status != "ERROR" else "ERROR"
            p.reason = "no quality cache for this run (cold + offline, or engine error)"
        elif p.age_days is not None and p.age_days > int(CONFIG["FRESHNESS_QUALITY_MAX_AGE_D"]):
            p.status = "STALE"
            # v1.8.1 (F4): fetch-stamp age = the refresh failed/overdue case
            # (distinct from macro's 'older than cadence' data-age case).
            p.reason = _stale_reason("quality", p.age_days)
        elif p.refresh_failed and p.age_days is not None \
                and p.age_days > disp_stale:
            # v1.8.2 (W3): quarterly filings within cadence, but this
            # online run could not refresh them — a real failed refresh.
            p.status = "STALE"
            p.reason = (f"refresh failed: this online run's quality fetch "
                        f"attempts failed (net-guard ledger) — the cache "
                        f"fetch stamp is {p.age_days}d old (within the "
                        f"{int(CONFIG['FRESHNESS_QUALITY_MAX_AGE_D'])}d "
                        "quarterly cadence) but could not be refreshed")
        else:
            p.status = "OK"
        return p

    if name == "earnings":
        edir = dirs.get("earnings", "")
        as_of = _earnings_px_date(edir)
        p.source = "cache" if res.cache == "warm" else "mixed"
        p.basis = ("earnings px_*.csv newest mtime (a price FETCH stamp; the "
                   "daily series runs through the fetch date)")
        p.data_as_of, p.age_days = as_of, _age_days_from(as_of)
        if not as_of:
            p.status = "MISSING_DATA" if res.status != "ERROR" else "ERROR"
            p.reason = "no earnings price cache this run"
        elif p.age_days is not None and p.age_days > int(CONFIG["FRESHNESS_EARNINGS_PRICE_MAX_AGE_D"]):
            p.status = "STALE"
            p.reason = _stale_reason("earnings", p.age_days)
        else:
            p.status = "OK"
        # §2.2 per-name: an earnings date has passed since the cache was
        # written -> the newest history row is a quarter + lag old.
        for t, sig in res.signals.items():
            last = str(sig.facts.get("last_date") or "")[:10]
            gap = _age_days_from(last) if last else None
            if sig.status == "OK" and gap is not None \
                    and gap > int(CONFIG["FRESHNESS_EARNINGS_EVENT_MAX_D"]):
                res.warnings = tuple(dict.fromkeys((*res.warnings,
                    f"{t}: no earnings report since {last} ({gap}d) — a report "
                    f"date has likely passed since the cache was written")))[:12]
        return p

    if name == "ml":
        p.source = "cache"
        p.basis = "ml_data model files (trained_at stamp)"
        trained = ""
        heads = res.ctx_out.get("heads") or {}
        for h in heads.values():
            trained = max(trained, str(h.get("trained_at") or ""))
        p.data_as_of, p.age_days = trained, _age_days_from(trained)
        p.status = "OK" if res.status != "ERROR" else "ERROR"
        return p

    if name == "risk":
        p.source = "cache" if res.cache == "warm" else ("none" if res.cache == "n/a" else "mixed")
        as_of = _earnings_px_date(dirs.get("earnings", ""))
        p.basis = "sizer price cache px_*.csv newest mtime (equal-weight fallback = none)"
        p.data_as_of, p.age_days = as_of, _age_days_from(as_of)
        p.status = "OK" if res.status != "ERROR" else "ERROR"
        return p

    p.status = "OK" if res.status != "ERROR" else "ERROR"
    return p


def _layer_cache_dirs(ctx: Context) -> dict[str, str]:
    """The cache dirs provenance reads for THIS run (real dirs, best effort)."""
    dirs: dict[str, str] = {"meds_cache": str(Path(__file__).resolve().parent / "meds_cache")}
    qmod = sys.modules.get("quality")
    dirs["quality"] = str(getattr(qmod, "CACHE_DIR", "")
                          or os.path.join(os.environ.get("QE_DATA_DIR", "data"), "cache"))
    dirs["earnings"] = str(ctx.flags.get("earnings_cache_dir")
                           or Path.home() / ".earnings_engine_cache")
    return dirs


def _refresh_plan_line(ctx: Context, layers: list[LayerBase],
                       ns: argparse.Namespace) -> str:
    """§3.1: the one-line incremental-refresh plan (advisory, printed in the
    [plan] banner): what is FRESH (served from cache) vs STALE/MISSING
    (the only items that will hit the network in online mode).
    v1.8.1 (F4/F5): freshness is estimated with the REAL engine TTLs, not
    just file presence — '90/90 cached' can never precede a cold pass, and
    a monthly macro series 18 days old is refresh-DUE, not 'stale' (the
    data cadence is 45 d; meds' own cache TTL is 24 h)."""
    dirs = _layer_cache_dirs(ctx)
    qdir, edir = dirs["quality"], dirs["earnings"]
    meds_age = _cache_age_h(dirs["meds_cache"])
    # F4: the macro DATA age is proxied by the fetch-stamp age (the cache
    # file was written when the engine last fetched) — calendar-date math
    # against date.today() would flip under the suite's PINNED clocks (the
    # env matrix), so the monotonic-stamp age keeps the banner hermetic.
    meds_data_age_d = (int(meds_age // 24) if meds_age is not None else None)
    ql = next((l for l in layers if l.name == "quality"), None)
    pool = 0
    if ql is not None and hasattr(ql, "peek_refs"):
        refs = ql.peek_refs(ctx)
        pool = len(refs) if refs else 0
    # F5: count the quality pool's SEC files that are still WITHIN the
    # engine's own 7-day cache TTL (quality.py CACHE_TTL_SECONDS sec),
    # not merely present.
    q_fresh = _dir_files_fresher(qdir, "sec", ttl_d=7.0) if pool else 0
    qcached = _dir_file_count(qdir, "sec") if pool else 0
    etickers = [c.ticker for c in ctx.tickers]
    # F5: earnings price histories within the engine's own 12 h TTL
    # (earnings_engine cache_ttl_hours=12 online).
    e_fresh = sum(1 for t in etickers
                  if any(_file_fresher(f, ttl_h=12.0)
                         for f in Path(edir).glob(f"*_{t}_*.csv")))
    ecached = sum(1 for t in etickers
                  if Path(edir, f"yahoo_{t}_*.csv").exists()
                  or any(Path(edir).glob(f"*_{t}_*.csv")))
    return _refresh_plan_line_ages(
        meds_age_h=meds_age, meds_data_age_d=meds_data_age_d,
        q_fresh=min(q_fresh, pool), q_pool=pool,
        q_due=min(max(qcached - q_fresh, 0), pool),
        e_fresh=e_fresh, e_total=len(etickers))


def _file_fresher(f: Path, ttl_h: float) -> bool:
    """A cache file still within an engine TTL (age <= ttl)."""
    try:
        return (time.time() - f.stat().st_mtime) <= ttl_h * 3600.0
    except OSError:
        return False


def _dir_files_fresher(base: str, sub: str, ttl_d: float) -> int:
    p = Path(base) / sub
    cut = time.time() - ttl_d * 86400.0
    try:
        return sum(1 for f in p.iterdir() if f.stat().st_mtime >= cut)
    except OSError:
        return 0


def _refresh_plan_line_ages(*, meds_age_h: float | None,
                            meds_data_age_d: int | None,
                            q_fresh: int, q_pool: int, q_due: int,
                            e_fresh: int, e_total: int) -> str:
    """F4/F5: the pure plan-banner text from measured ages. Macro: 'fresh'
    (cache < 24 h), 'refresh-due' (cache older than the 24 h TTL but the
    monthly data cadence of 45 d has NOT passed — not stale, just a
    refresh owed), 'stale-data' (the data as-of itself is older than the
    45 d monthly cadence) or 'cold'."""
    cad = int(CONFIG["FRESHNESS_MACRO_MAX_AGE_D"])
    if meds_age_h is None:
        macro = "macro cold"
    elif meds_data_age_d is not None and meds_data_age_d > cad:
        macro = (f"macro stale-data ({meds_data_age_d}d as-of > {cad}d "
                 "monthly cadence — older than cadence)")
    elif meds_age_h < 24.0:
        macro = f"macro fresh ({meds_age_h:.1f}h since fetch)"
    else:
        macro = (f"macro refresh-due ({meds_age_h / 24.0:.0f}d since fetch · "
                 f"TTL 24h · monthly cadence {cad}d — not stale)")
    q_part = (f"quality {q_fresh}/{q_pool} fresh by TTL (7d)"
              + (f" · {q_due} due refresh" if q_due else ""))
    e_part = f"earnings {e_fresh}/{e_total} fresh by TTL (12h)"
    return f"refresh plan: {macro} · {q_part} · {e_part}"


def _stale_reason(layer: str, data_age_d: int | None,
                  ttl_h: float | None = None) -> str:
    """F4: two DISTINCT staleness reasons — 'older than cadence' (the data
    itself has no newer month than its cadence allows) vs 'refresh failed
    or overdue' (the FETCH stamp aged past the layer's refresh window)."""
    a = int(data_age_d or 0)
    if layer == "macro":
        cad = int(CONFIG["FRESHNESS_MACRO_MAX_AGE_D"])
        return (f"macro data as-of is {a}d old > {cad}d (older than "
                "cadence — monthly; no newer month published)")
    if layer == "quality":
        lim = int(CONFIG["FRESHNESS_QUALITY_MAX_AGE_D"])
        return (f"quality cache fetched {a}d ago > {lim}d (refresh failed "
                "or overdue — the fetch stamp aged past the refresh "
                "window; per-name staleness is the engine's own "
                "STALE_DATA flags)")
    lim = int(CONFIG["FRESHNESS_EARNINGS_PRICE_MAX_AGE_D"])
    return (f"price history fetched {a}d ago > {lim}d (refresh failed or "
            "overdue — the fetch stamp aged past the refresh window)")


def _dir_file_count(base: str, sub: str) -> int:
    p = Path(base) / sub
    try:
        return sum(1 for _ in p.iterdir())
    except OSError:
        return 0


# ── § 5.3 · the pipeline ─────────────────────────────────────────────────
def run_pipeline(ns: argparse.Namespace) -> RunOutput:
    """1 macro call -> N quality scores (shared universe) -> top-K earnings
    -> fuse -> one ranked table. A layer failure never kills the run.
    P2-1/P2-3: results are SNAPSHOTTED at the fusion boundary and every
    env/module mutation is registered in `restores` and undone on exit.
    v1.8.1: the net guard (N1-N9) lives exactly this run's lifetime —
    installed for online runs, uninstalled + ledger dumped + negcache
    saved in the finally (an engine-visible urllib/requests patch is
    NEVER left behind)."""
    t_all = time.monotonic()
    _apply_mode(ns)                        # mode/warm presets for unset flags
    restores: list[Any] = []
    net_state: dict[str, Any] = {}
    try:
        return _run_pipeline_inner(ns, restores, t_all, net_state)
    finally:
        guard = net_state.get("guard")
        if guard is not None:
            try:
                guard.uninstall()
            except Exception:
                pass
            try:
                guard.negcache.save()
            except Exception:
                pass
            try:                        # N9: --retry-failed reads this dump
                guard.ledger.dump(str(CONFIG["FETCH_LEDGER_PATH"]))
            except Exception:
                pass
        _restore_all(restores)


def _run_budget_s(ns: argparse.Namespace) -> float:
    """v1.8.2 (W1): the OVERALL run budget for this run — derived from
    the depth preset (RUN_BUDGET_BY_DEPTH, disclosed CONFIG key);
    MASTER_RUN_BUDGET_S env always wins (the CI/test valve); RUN_BUDGET_S
    is the fallback for unknown depths (the v1.8.1 flat value).
    Budget/display only — never a fusion input."""
    by_depth = CONFIG["RUN_BUDGET_BY_DEPTH"]
    depth = str(getattr(ns, "depth", "") or "")
    default = float(by_depth.get(depth, CONFIG["RUN_BUDGET_S"]))
    try:
        return float(os.environ.get("MASTER_RUN_BUDGET_S", "") or default)
    except ValueError:
        return default


def _run_pipeline_inner(ns: argparse.Namespace, restores: list,
                        t_all: float,
                        net_state: dict | None = None) -> RunOutput:
    net_state = net_state if net_state is not None else {}
    with _phase("setup"):
        ctx = _build_context(ns, restores)
        only, skip = _parse_layers(ns)
        if ns.earnings_mode == "off":
            if only == {"earnings"}:
                raise MasterError("--only earnings with --earnings-mode off selects nothing", 2)
            skip = (skip or set()) | {"earnings"}
        stubbed = os.environ.get("MASTER_STUBS", "") not in ("", "0", "false")
        # final phase (§4): resolve the net mode ONCE per run (auto probes
        # with a 2 s budget; explicit online is verified; offline skips the
        # probe). MASTER_NET is the documented CI/hermeticity override.
        net, probe_note = _resolve_net_mode(ns, stubbed)
        ctx.flags["net"] = net
        # v1.8.1 (N1) / v1.8.2 (W1): the OVERALL run budget — DERIVED FROM
        # THE DEPTH PRESET now (RUN_BUDGET_BY_DEPTH; MASTER_RUN_BUDGET_S
        # env still wins). After it the run renders what it has and the
        # process exits within seconds even if a worker is stuck.
        run_budget_s = _run_budget_s(ns)
        run_deadline = t_all + run_budget_s
        ctx.flags["run_deadline"] = run_deadline
        ctx.flags["run_budget_s"] = run_budget_s
        # v1.8.1 (N6): auto mode with a dead network falls back to
        # offline-from-cache with a CLEAR banner (explicit --mode online
        # keeps its exit-3 contract in _resolve_net_mode, above).
        if net == "offline" and not stubbed \
                and str(getattr(ns, "net", "auto") or "auto") == "auto" \
                and os.environ.get("MASTER_NET", "") not in ("online",
                                                                 "offline"):
            banner = ("auto mode: network probe failed — falling back to "
                      "offline-from-cache (live data unavailable; cache "
                      "ages are labelled per layer; --mode online keeps "
                      "its exit-3 contract)")
            ctx.flags["net_fallback_banner"] = banner
        # the offline FLAG keeps its data-truth meaning for real runs; a
        # stub run is STUBBED (its own loud banner), never quietly
        # relabelled 'offline' — stubs carry no data mode (§4).
        ctx.flags["offline"] = bool(ctx.flags.get("offline")
                                    or (net == "offline" and not stubbed))
        ctx.flags["stubs"] = stubbed
        registry = _stubbed_registry() if stubbed else None
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
        # v1.8.1 (N6): emit the auto-mode fallback banner now that _note
        # exists (set above at net-resolution time).
        if ctx.flags.get("net_fallback_banner"):
            _note(str(ctx.flags["net_fallback_banner"]))
        # phase 4 (P-1): fuse/funnel/_reasons read CONFIG["RULESET"] — the
        # CLI override is written ONCE here (P2-3 discipline: restored by
        # run_pipeline's finally, so a v2 run never leaks into the next).
        rs = str(getattr(ns, "ruleset", None) or CONFIG["RULESET"])
        if rs != CONFIG["RULESET"]:
            restores.append(_CfgKeyRestore("RULESET", rs))
        if ns.verbose:
            _note(f"layers: {' '.join(l.name for l in build_layers(only, skip, registry))}"
                  f" · as_of={ctx.as_of or 'live'} · tickers={len(ctx.tickers)}"
                  f" · net {net}{(' (' + probe_note + ')') if probe_note else ''}")
        layers = build_layers(only, skip, registry)
        if not layers:
            raise MasterError("no layers selected", 2)
        # final phase (§2.5): a run that will WRITE caches needs writable
        # cache dirs — a read-only cache is a CLEAR error up front (exit 2,
        # never a traceback). Offline runs only READ (§2.6) and skip this.
        if net == "online" and not stubbed:
            _assert_cache_writable(ctx, restores, _note)
        # v1.8.1 (N1-N9): create + install the net guard for THIS online
        # run (offline/stub runs never patch anything — the suite pins
        # MASTER_NET_PREFLIGHT_HOSTS="" for hermeticity, and the owner's
        # real run preflights the six engine hosts).
        guard = None
        if net == "online" and not stubbed:
            from me.netguard import NetGuard
            # read EVERY net CONFIG key at its production call site (the
            # rules register's LIVE criterion): breaker/budget/cap/negcache
            # values flow from CONFIG into the guard here.
            guard = NetGuard(
                breaker_k=int(CONFIG["NET_BREAKER_K"]),
                breaker_cooldown_s=float(CONFIG["NET_BREAKER_COOLDOWN_S"]),
                call_cap_s=float(CONFIG["NET_CALL_CAP_S"]),
                retry_budget_s=float(CONFIG["NET_RETRY_BUDGET_S"]),
                max_attempts=int(CONFIG["RETRY_MAX_ATTEMPTS"]),
                backoff=tuple(CONFIG["RETRY_BACKOFF_S"]),
                negcache_path=str(CONFIG["NET_NEG_CACHE_PATH"]),
                negcache_ttl_s=float(CONFIG["NET_NEG_CACHE_TTL_S"]),
                defer_cooldown_s=float(CONFIG["NET_DEFER_COOLDOWN_S"]),
                window_n=int(CONFIG["NET_BREAKER_WINDOW_N"]),
                rate=float(CONFIG["NET_BREAKER_RATE"]),
                timeout_weight=float(CONFIG["NET_BREAKER_TIMEOUT_WEIGHT"]),
                brownout_s=(float(CONFIG["NET_BROWNOUT_S"])
                            if float(CONFIG["NET_BROWNOUT_S"]) > 0 else None))
            guard.set_run_deadline(run_deadline)
            guard.install()
            net_state["guard"] = guard
            ctx.flags["netguard"] = guard
            if os.environ.get("MASTER_NET_PREFLIGHT", "") != "0" \
                    and os.environ.get("MASTER_NET", "") \
                    not in ("online", "offline"):
                # MASTER_NET is the hermeticity valve (TRUST it, never
                # probe): in-process test harnesses pin it online/offline,
                # and a pinned run must never TCP the real hosts. A real
                # terminal run (env unset) preflights all six.
                _hosts_env = os.environ.get("MASTER_NET_PREFLIGHT_HOSTS")
                if _hosts_env is None:
                    _hosts = list(CONFIG["NET_PREFLIGHT_HOSTS"] or ())
                else:
                    # a SET env var (even empty) overrides the CONFIG list:
                    # "" = no preflight (the hermeticity valve), a comma
                    # list of host:port entries pins the loopback targets.
                    _hosts = [tuple(x.split(":")[:1] + [int(x.split(":")[1])])
                              for x in _hosts_env.split(",") if x and ":" in x]
                if _hosts:
                    res = guard.preflight(
                        _hosts,
                        budget_s=float(CONFIG["NET_PREFLIGHT_S"]),
                        retries=int(CONFIG["NET_PREFLIGHT_RETRIES"]),
                        total_budget_s=(
                            float(CONFIG["NET_PREFLIGHT_TOTAL_S"])
                            if float(CONFIG["NET_PREFLIGHT_TOTAL_S"]) > 0
                            else None))
                    dead = [k for k, r in res.items() if not r["ok"]]
                    live = [k for k, r in res.items() if r["ok"]]
                    if live:
                        _note("preflight: " + " · ".join(
                            f"{k} ok ({res[k]['note']})" for k in live))
                    if dead:
                        _note("preflight: DEAD HOSTS known within seconds — "
                              "breaker open, calls fail fast: " + " · ".join(
                                  f"{k} ({res[k]['note']}; "
                                  f"{res[k]['attempts']} attempts)"
                                  for k in dead))
        # final phase (§3.1/§3.5): cache state BEFORE the run (for the
        # refresh plan + the after-run refresh report)
        cache_dirs = _layer_cache_dirs(ctx)
        before = {k: _dir_stamp(v) for k, v in cache_dirs.items()}
        _plan_banner(ctx, layers, ns, stubbed, net)   # before ANY layer runs
    results: dict[str, LayerResult] = {}
    starts = {l.name: time.monotonic() for l in layers}
    done: dict[str, float] = {}          # final phase: per-layer COMPLETION stamps
    # v1.8.1 (N1): layer budgets are clamped to the OVERALL run budget —
    # after it the run renders what it has (the timeout message then says
    # run budget, not the layer timeout).
    budgets = {l.name: min(starts[l.name] + float(ns.timeout), run_deadline)
               for l in layers}
    with _phase("prefetch"):
        ex = ThreadPoolExecutor(max_workers=3, thread_name_prefix="mx")
        try:
            futs = {l.name: ex.submit(_prefetch_one, l, ctx) for l in layers}
            for layer in layers:
                try:
                    bad = futs[layer.name].result(
                        timeout=max(0.05, budgets[layer.name] - time.monotonic()))
                    done[layer.name] = time.monotonic()
                    if bad is not None:
                        results[layer.name] = bad
                        _note(f"{layer.name} prefetch failed: {bad.warnings[-1] if bad.warnings else '?'}")
                except TimeoutError:
                    done[layer.name] = time.monotonic()
                    prog.kill(layer.name)          # silence the stuck thread's line
                    _budget = (time.monotonic() >= run_deadline)
                    results[layer.name] = layer._salvage(
                        (f"{layer.name}: run budget exhausted after "
                         f"{run_budget_s:.0f}s (RUN_BUDGET_S) — partial kept"
                         if _budget else
                         f"{layer.name}: timeout after {ns.timeout}s (partial kept)"))
                    _note((f"{layer.name} prefetch hit the RUN BUDGET "
                           f"({run_budget_s:.0f}s) — partial kept; "
                           "the background worker keeps filling cache"
                           if _budget else
                           f"{layer.name} prefetch timed out after "
                           f"{ns.timeout}s — partial kept"))
                    _timeout_hint(layer, _note)
                except Exception as e:
                    results[layer.name] = layer._salvage(f"{layer.name}: {_exc(e)}")
                    _note(f"{layer.name} prefetch failed: {_exc(e)}")
        finally:
            ex.shutdown(wait=False, cancel_futures=True)
    with _phase("layers"):
        for layer in layers:
            if (layer.name in results or getattr(layer, "funnel_input", False)
                    or layer.stage in ("overlay", "sizer")):
                continue     # prefetch-errored / funnel layer / post-fusion stages
            if time.monotonic() >= run_deadline:   # v1.8.1 (N1): render what we have
                results[layer.name] = layer._salvage(
                    f"{layer.name}: run budget exhausted after "
                    f"{run_budget_s:.0f}s (RUN_BUDGET_S) — skipped, "
                    "run rendered what it has")
                _note(f"{layer.name} skipped: RUN BUDGET "
                      f"({run_budget_s:.0f}s) exhausted before its run")
                continue
            try:
                results[layer.name] = _soft_deadline_call(
                    budgets[layer.name], layer.run, ctx, ctx.tickers,
                    layer=layer.name)
                done[layer.name] = time.monotonic()
            except TimeoutError:
                done[layer.name] = time.monotonic()
                prog.kill(layer.name)
                _budget = (time.monotonic() >= run_deadline)
                results[layer.name] = layer._salvage(
                    (f"{layer.name}: run budget exhausted after "
                     f"{run_budget_s:.0f}s (RUN_BUDGET_S) — partial kept"
                     if _budget else
                     f"{layer.name}: timeout after {ns.timeout}s (partial kept)"))
                _note((f"{layer.name} hit the RUN BUDGET ({run_budget_s:.0f}s) "
                       "— partial kept; the background worker keeps "
                       "filling cache"
                       if _budget else
                       f"{layer.name} timed out after {ns.timeout}s — partial kept"))
                _timeout_hint(layer, _note)
            except Exception as e:
                done[layer.name] = time.monotonic()
                results[layer.name] = layer._salvage(f"{layer.name} run: {_exc(e)}")
                _note(f"{layer.name} run failed: {_exc(e)}")
        macro_res = results.get("macro")
        if macro_res is not None and macro_res.ctx_out.get("macro") is not None:
            ctx.regime = macro_res.ctx_out["macro"]
            ctx.risk_budget = float(macro_res.ctx_out.get("risk_budget", 1.0))
    with _phase("funnel"):
        shortlist = (funnel_shortlist(ctx, results, int(ns.earnings_top))
                     if "quality" in results else list(ctx.tickers))
        for layer in [l for l in layers if getattr(l, "funnel_input", False)]:
            if layer.name in results:            # already errored in prefetch
                continue
            with _phase("funnel"):
                starts[layer.name] = time.monotonic()   # its clock starts at its run
                budgets[layer.name] = min(starts[layer.name] + float(ns.timeout),
                                         run_deadline)
                try:
                    results[layer.name] = _soft_deadline_call(
                        budgets[layer.name], layer.run, ctx, shortlist,
                        layer=layer.name)
                    done[layer.name] = time.monotonic()
                except TimeoutError:
                    done[layer.name] = time.monotonic()
                    prog.kill(layer.name)
                    _b = (time.monotonic() >= run_deadline)
                    results[layer.name] = layer._salvage(
                        (f"{layer.name}: run budget exhausted after "
                         f"{run_budget_s:.0f}s (RUN_BUDGET_S) — partial kept"
                         if _b else
                         f"{layer.name}: timeout after {ns.timeout}s (partial kept)"))
                    _note((f"{layer.name} hit the RUN BUDGET "
                           f"({run_budget_s:.0f}s) — partial kept"
                           if _b else
                           f"{layer.name} timed out after {ns.timeout}s — "
                           "partial kept"))
                except Exception as e:
                    done[layer.name] = time.monotonic()
                    results[layer.name] = layer._salvage(f"{layer.name}: {_exc(e)}")
                    _note(f"{layer.name} failed: {_exc(e)}")
    with _phase("fusion"):
        # P2-1: freeze before fusion — a late (timed-out) worker keeps
        # mutating the ORIGINAL LayerResult; everything downstream reads
        # this snapshot instead.
        snap = _snapshot_results(results)
        decisions = (fuse(ctx, snap, ns.earnings_mode)
                     if "quality" in snap else [])
    # phase 3: overlay stage (L4-style) — registered layers run AFTER fusion,
    # receive the Decision list, and may nudge conviction (bounded).
    for layer in [l for l in layers if l.stage == "overlay" and l.name not in snap]:
        with _phase("overlay"):
            starts[layer.name] = time.monotonic()
            budgets[layer.name] = min(starts[layer.name] + float(ns.timeout),
                                     run_deadline)
            try:
                snap[layer.name] = _soft_deadline_call(
                    budgets[layer.name], layer.run, ctx, decisions,
                    layer=layer.name)
                done[layer.name] = time.monotonic()
            except TimeoutError:
                done[layer.name] = time.monotonic()
                prog.kill(layer.name)
                _b = (time.monotonic() >= run_deadline)
                snap[layer.name] = layer._salvage(
                    (f"{layer.name}: run budget exhausted after "
                     f"{run_budget_s:.0f}s (RUN_BUDGET_S) — partial kept"
                     if _b else
                     f"{layer.name}: timeout after {ns.timeout}s (partial kept)"))
                _note((f"{layer.name} hit the RUN BUDGET ({run_budget_s:.0f}s) "
                       "— partial kept"
                       if _b else
                       f"{layer.name} timed out after {ns.timeout}s — "
                       "partial kept"))
            except Exception as e:
                done[layer.name] = time.monotonic()
                snap[layer.name] = layer._salvage(f"{layer.name}: {_exc(e)}")
                _note(f"{layer.name} failed: {_exc(e)}")
    if decisions and any(l.stage == "overlay" for l in layers):
        _apply_overlays(decisions, snap, ns.earnings_mode)
        decisions.sort(key=_rank_key)
    # phase 3: sizer stage (L5-style) — reads the Decision list, owns weights.
    for layer in [l for l in layers if l.stage == "sizer" and l.name not in snap]:
        with _phase("sizer"):
            starts[layer.name] = time.monotonic()
            budgets[layer.name] = min(starts[layer.name] + float(ns.timeout),
                                     run_deadline)
            try:
                snap[layer.name] = _soft_deadline_call(
                    budgets[layer.name], layer.run, ctx, decisions,
                    layer=layer.name)
                done[layer.name] = time.monotonic()
            except TimeoutError:
                done[layer.name] = time.monotonic()
                prog.kill(layer.name)
                _b = (time.monotonic() >= run_deadline)
                snap[layer.name] = layer._salvage(
                    (f"{layer.name}: run budget exhausted after "
                     f"{run_budget_s:.0f}s (RUN_BUDGET_S) — partial kept"
                     if _b else
                     f"{layer.name}: timeout after {ns.timeout}s (partial kept)"))
                _note((f"{layer.name} hit the RUN BUDGET ({run_budget_s:.0f}s) "
                       "— partial kept"
                       if _b else
                       f"{layer.name} timed out after {ns.timeout}s — "
                       "partial kept"))
            except Exception as e:
                done[layer.name] = time.monotonic()
                snap[layer.name] = layer._salvage(f"{layer.name}: {_exc(e)}")
                _note(f"{layer.name} failed: {_exc(e)}")
    # final phase (§6.2 fix): per-layer elapsed = its OWN completion stamp
    # minus its start — a fast macro that finished while quality was still
    # fetching no longer inherits the whole run's wall clock.
    for name, res in snap.items():
        res.elapsed_s = round(done.get(name, time.monotonic()) - starts.get(name, t_all), 2)
    # final phase (§2.1): provenance per layer, from the SNAPSHOT (a late
    # worker writing after fusion cannot change what is reported).
    prov = {name: layer_provenance(name, snap, ctx, cache_dirs) for name in snap}
    # final phase (§3.5): online cache maintenance + refresh report —
    # the visible proof the online run ADDED freshness (§3).
    refresh: dict[str, Any] = {}
    if net == "online" and not stubbed:
        m = sys.modules.get("meds")
        if m is not None and "macro" in snap:
            n_files, mnote = _materialise_meds_snapshot(m)
            if n_files:
                _note(f"meds snapshot: {mnote}")
        for key, path in cache_dirs.items():
            b_exists, b_newest = before.get(key, (False, 0.0))
            a_exists, a_newest = _dir_stamp(path)
            b_age = (f"{(time.time() - b_newest) / 86400:.0f}d" if (b_exists and b_newest > 0) else "cold")
            a_age = (f"{(time.time() - a_newest) / 86400:.0f}d" if (a_exists and a_newest > 0) else "cold")
            refresh[key] = {"age_before": b_age, "age_after": a_age,
                            "refreshed": bool(a_newest > (b_newest + 1e-6))}
    refresh["per_layer_s"] = {n: r.elapsed_s for n, r in snap.items()}
    warnings = _aggregate_warnings(ctx, snap, ns, decisions)
    # §2.2: STALE provenance is a warning too — loud, never silent.
    for name, p in prov.items():
        if p.status == "STALE":
            warnings.append(f"{name} data STALE: {p.reason}")
    # v1.8.1 (N1): the run-budget exhaustion note is a warning too.
    if any("run budget" in str(x).lower() for x in notes):
        warnings.append(f"run budget exhausted ({run_budget_s:.0f}s "
                        "RUN_BUDGET_S) — the run rendered what it had")
    # v1.8.1 (N4): the FETCH HEALTH payload — EVERY run carries it (empty
    # totals + note when no fetches happened: offline cached-truth or stubs).
    if guard is not None:
        fetch_health = guard.health()
    else:
        from me.netguard import Ledger
        note = ("stub layers — no fetches (MASTER_STUBS)" if stubbed
                else "offline: cached truth, zero attempts" if net == "offline"
                else "no fetches this run")
        fetch_health = Ledger.empty_health(note)
    exit_code, exit_reason = _resolve_exit(snap, decisions, warnings,
                                            policy=_exit_policy(ns))
    prog.stop()                            # final: no stuck thread paints after us
    timings = {"total": round(time.monotonic() - t_all, 1)}
    timings.update({n: r.elapsed_s for n, r in snap.items()})
    return RunOutput(ctx=ctx, results=snap, decisions=decisions, warnings=warnings,
                     timings=timings, exit_code=exit_code, exit_reason=exit_reason,
                     stubbed=stubbed, provenance=prov, net_mode=net,
                     net_probe=probe_note, refresh=refresh,
                     fetch_health=fetch_health)


def _aggregate_warnings(ctx: Context, results: dict[str, LayerResult],
                        ns: argparse.Namespace,
                        decisions: list[Decision] | None = None) -> list[str]:
    """Every honesty gate, loudly: credit OFF, DEGRADED, stale, no history,
    phase-3 disclosure gates (--cap exclusions, --discover shortfalls)."""
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
            w.append(f"earnings backtest: {bt['n_trades']} trades · picked {bt['picked_n']} · "
                     f"edge {bt['edge_pct']:+.1f}% ({bt['basis']}, naive t={bt['edge_t']:.2f}; "
                     "clustered events overstate t)")
    for res in results.values():
        for wn in res.warnings:
            if wn not in w and "version" not in wn:
                w.append(wn)
        # v1.8.1 (N6): skipped items are LISTED (item, why, fix) — one
        # aggregate warning per layer, the FETCH HEALTH block has the rows.
        skipd = res.ctx_out.get("skipped") or []
        if skipd:
            w.append(f"[W_ITEM_SKIPPED] {res.name}: skipped {len(skipd)} "
                     f"item(s): " + "; ".join(
                         f"{s[0]} ({s[1]} — fix: {s[2]})" for s in skipd[:4])
                     + (" …" if len(skipd) > 4 else ""))
    # v1.8.1 (N6): the auto-mode dead-network fallback banner.
    if ctx.flags.get("net_fallback_banner"):
        w.append(str(ctx.flags["net_fallback_banner"]))
    if ns.earnings_mode == "trigger" and ns.as_of:
        w.append("trigger mode with --as-of: plan unavailable -> LONG impossible (WATCH at most)")
    # phase 3: loud disclosure gates ----------------------------------------
    cap_excl = ctx.flags.get("cap_excluded") or []
    if cap_excl:
        w.append(f"--cap {ctx.flags.get('cap_band', '?')}: excluded "
                 f"{', '.join(cap_excl)} (no market-cap data — kept out, "
                 "never silently scored)")
    want = getattr(ns, "discover", None)
    if want and decisions is not None and len(decisions) < int(want):
        w.append(f"--discover {int(want)}: only {len(decisions)} names qualified "
                 "— pools never truncated, nothing hidden; widen the universe "
                 "(--sectors) or lower the bar (--min-conviction)")
    # F5 (v1.8.3): ONE loud, specific disclosure when unbucketed consumer
    # names are scored under a consumer-basket long (the merged XLP+XLY
    # view: a long in EITHER basket lifts every consumer name ~+10%
    # conviction). Scores are unchanged; this is a warning, never a veto.
    if decisions is not None and state is not None \
            and any(d.sector == "consumer" for d in decisions) \
            and ({"XLP", "XLY"} & set(state.longs or ())):
        w.append("consumer names scored on the merged XLP+XLY view — a long "
                 "in EITHER basket lifts every unbucketed consumer name "
                 "~+10% conviction (--bucket staples,discretionary splits "
                 "the pools) [W_CONSUMER_MERGED]")
    out: list[str] = []
    for item in w:
        if item not in out:
            out.append(item)
    return out


def _resolve_exit(results: dict[str, LayerResult], decisions: list[Decision],
                   warnings: list[str] | None = None,
                   policy: str = "default") -> tuple[int, str]:
    """The NEW exit-code contract (phase 5, C-5 — deliberate change, mapped
    in CHANGELOG/--help/--doctor): 0 clean · 1 degraded (result produced +
    warnings, incl. ml head UNAVAILABLE) · 4 no result / NO-GO (was 2).
    The reason names the ERROR layer with the lowest order (the real
    blocker) and never quotes cosmetic version-drift notes.
    v1.8.1 (F7): `policy` is the OPT-IN exit policy — 'default' is the
    documented contract above (unchanged); 'strict' (CLI --strict) turns
    a degraded/warning run into exit 2 so CI fails fast; 'lenient'
    (--lenient) keeps a produced result at exit 0 (warnings still listed;
    NO-GO exit 4 and usage errors are NEVER forgiven)."""
    if not results:
        return 4, "no result: no layer ran"

    q_res = results.get("quality")
    if q_res is not None and q_res.signals \
            and not any(s.status == "OK" for s in q_res.signals.values()):
        # P1-7 (A6): quality ran and scored NOTHING — an all-AVOID table built
        # on zero scores is not a result, whatever macro says.
        bad = next((s for s in q_res.signals.values() if s.status != "OK"), None)
        why = (bad.warnings[0] if bad is not None and bad.warnings else "no OK signals")
        return 4, f"no result / NO-GO: quality scored 0/{len(q_res.signals)} names — {why[:160]}"

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
        return 4, f"no result / NO-GO: {first[:200]}"
    # §3.1 (B-1): an ml head that exists but cannot run in THIS environment
    # (sklearn/numpy/joblib/python mismatch) is a degraded run that still
    # produced a result — exit 1 with the reason, never a silent 0.
    ml_res = results.get("ml")
    if ml_res is not None and ml_res.ctx_out.get("unavailable"):
        why = "; ".join(str(x) for x in ml_res.ctx_out["unavailable"])[:180]
        return 1, (f"ml head(s) UNAVAILABLE (environment/version mismatch, "
                   f"run continued): {why}")
    # phase 5 (C-5): a run that produced a result WITH degraded layers or
    # warnings is exit 1 (owner's contract), never a silent 0.
    degraded = sorted((r.name for r in results.values()
                       if r.status in ("DEGRADED", "ERROR")))
    if degraded:
        code, why = 1, (f"degraded (result produced): {', '.join(degraded)} "
                        f"— details in the ERRORS & WARNINGS block")
    elif warnings:
        code, why = 1, (f"degraded (result produced): {len(warnings)} warning(s) "
                        f"— {str(warnings[0])[:120]}")
    else:
        code, why = 0, ""
    if policy == "strict" and code == 1:
        return 2, ("strict (--strict): " + why[:160]
                   + " — rerun without --strict for the default exit-1 "
                   "degraded contract")
    if policy == "lenient" and code == 1:
        return 0, ("lenient (--lenient): degraded run kept at exit 0 — "
                   + why[:160])
    return code, why


def _exit_policy(ns: argparse.Namespace) -> str:
    """F7: the --strict/--lenient exit policy from the CLI flags (default
    = the current contract; both flags together is a usage error)."""
    strict = bool(getattr(ns, "strict", False))
    lenient = bool(getattr(ns, "lenient", False))
    if strict and lenient:
        raise MasterError("--strict and --lenient are mutually exclusive "
                           "(pick one exit policy; default = neither)", 2)
    return "strict" if strict else ("lenient" if lenient else "default")


def _write_csv(path: str, out: RunOutput, ns: argparse.Namespace) -> str:
    """Opt-in write; applies the same --top/--min-conviction filters as the table."""
    import csv
    p = Path(path)
    if str(p.parent):
        p.parent.mkdir(parents=True, exist_ok=True)
    rows = [d for d in out.decisions if d.conviction >= float(ns.min_conviction)][:int(ns.top)]
    # B8: atomic write — a crash mid-write leaves the PREVIOUS csv intact
    # and removes the temp file; never a truncated book on disk.
    tmp = p.with_name(p.name + ".tmp")
    try:
        with tmp.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow([_csv_safe(c) for c in
                        ["rank", "ticker", "sector", "action", "conviction", "grade",
                         "macro_tilt", "now", "q_score", "q_grade", "q_status", "e_score",
                         "e_grade", "e_status", "plan", "p_next_big", "flags", "reasons", "weight"]])
            for i, d in enumerate(rows, 1):
                q, e, m = d.layers.get("quality"), d.layers.get("earnings"), d.layers.get("macro")
                w.writerow([_csv_safe(c) for c in [
                    i, d.ticker, d.sector, d.action, d.conviction, d.grade,
                    (m.facts.get("tilt") if m else None),
                    bool(e.facts.get("now")) if e else False,
                    (q.score if q else None), (q.grade if q else "-"),
                    (q.status if q else "MISSING"),
                    (e.score if e else None), (e.grade if e else "-"),
                    (e.status if e else "MISSING"),
                    (e.facts.get("plan") if e else None),
                    (e.facts.get("p_next_big") if e else None),
                    ";".join(q.flags) if q else "", " | ".join(d.reasons), d.weight]])
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)
    finally:
        if tmp.exists():
            tmp.unlink()
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
    """Health probe in four separated sections (P2-6):
    [importable]    every required engine imports + version vs tested
    [configured]    env KEY NAMES (never values)
    [cache-ready]   the real cache dirs, present + age
    [provider-ready] one tiny request per source (skipped with --offline)
    Exit 2 when a REQUIRED engine is missing (all three belong to the default
    pipeline; --only partial runs remain possible — that is printed too)."""
    st = make_style(ns)
    print(st.mark(f"master v{__version__} --check", "head"))
    missing: list[str] = []
    print("[importable]")
    for name, mod_name in (("meds", "meds"), ("quality", "quality"),
                            ("earnings", "earnings_engine")):
        try:
            mod = importlib.import_module(mod_name)
        except Exception as e:
            print(f"  {name:<9} IMPORT FAILED — {_exc(e)}")
            missing.append(name)
            continue
        ver, tested, differs = _engine_version(name, mod)
        note = "tested" if not differs else f"DIFFERS from tested {tested}"
        extra = "" if name != "earnings" or hasattr(mod, "__version__") else " (no __version__ attr; drift undetectable)"
        print(f"  {name:<9} v{ver:<8} {note}{extra}")
    if missing:
        print(f"  required engine(s) missing: {', '.join(missing)} — the default "
              "pipeline needs all three; --only runs without them stay possible")
    print("[configured]")
    print("  env (names only, never values): " + " · ".join(
        f"{v}={'set' if os.environ.get(v) else 'absent'}"
        for v in ("FREDAPI", "FRED_API_KEY", "SEC_USER_AGENT", "FINNHUB_API_KEY")))
    print("[cache-ready]")
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
    print("[provider-ready]")
    if ns.offline:
        print("  probes skipped (--offline)")
        return 1 if missing else 0
    for label, url, ua in (
            ("FRED public CSV", "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF", None),
            ("SEC EDGAR", "https://www.sec.gov/",
             os.environ.get("SEC_USER_AGENT") or "master.py health probe (set SEC_USER_AGENT)"),
            ("Yahoo chart", "https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=1d&interval=1d",
             "Mozilla/5.0 master.py health probe")):
        print(f"  {label:<14} {_probe(url, ua)}")
    return 1 if missing else 0


def run_selftest() -> int:
    """The suite lives in test_master.py since phase 3 (all tests + fakes
    moved out of master.py). This stays the `python master.py --selftest`
    entry point: it imports that file and runs the SAME unittest suite;
    live checks print LIVE SKIP."""
    try:
        import test_master
    except Exception as e:
        raise MasterError("--selftest needs test_master.py next to master.py "
                          f"({_exc(e)})", 2) from e
    import unittest
    suite = unittest.TestLoader().loadTestsFromModule(test_master)
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if res.wasSuccessful() else 1


# ── § 7b · freeze / replay / doctor (final phase §5, §8) ─────────────────
def _frozen_ranking(out: RunOutput) -> list[dict[str, Any]]:
    return [{"ticker": d.ticker, "action": d.action,
             "conviction": round(float(d.conviction), 1), "grade": d.grade,
             "weight": (None if d.weight is None else round(float(d.weight), 4))}
            for d in out.decisions]


def _freeze_copy_tree(src: Path, dst: Path, cap_left: int
                      ) -> tuple[int, int, bool]:
    """Copy files (newest first) under src into dst until cap_left bytes.
    P7-H1: files skipped for budget are REPORTED (starved=True) — a silent
    skip made a budget-starved freeze masquerade as complete and replay
    fail on the cache miss."""
    n = b = 0
    starved = False
    files = []
    if src.is_dir():
        files = sorted((f for f in src.rglob("*") if f.is_file()),
                       key=lambda f: f.stat().st_mtime, reverse=True)
    for f in files:
        try:
            size = f.stat().st_size
        except OSError:
            continue
        if size > cap_left:
            starved = True
            continue
        target = dst / f.relative_to(src)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
        except OSError:
            continue
        n += 1
        b += size
        cap_left -= size
    return n, b, starved


def run_freeze(dir_path: str, out: RunOutput, ns: argparse.Namespace) -> str:
    """§5: after a run, write DIR/manifest.json (args, master+engine
    versions, ENGINES hashes, layer provenance, ranking with conviction)
    and copy the cache files this run's tickers/dates used (size-capped by
    FREEZE_MAX_BYTES, printed). Exact for quick/watchlist-peer runs; a
    standard-mode quality pool exceeds the cap, so the manifest records
    what was copied and replay then verifies what it can — loudly."""
    d = Path(dir_path)
    d.mkdir(parents=True, exist_ok=True)
    engines = _engines_sha256()
    args = {k: v for k, v in vars(ns).items() if k in (
        "tickers", "tickers_csv", "watchlist", "mode", "depth", "net",
        "net_flag", "as_of",
        "peers", "earnings_top", "earnings_mode", "earnings_prefetch", "top",
        "source", "workers", "timeout", "sector", "bucket", "sectors", "cap",
        "discover", "ml_models_dir", "min_conviction")}
    risk_res = out.results.get("risk")
    man: dict[str, Any] = {
        "schema": 1, "frozen_at": date.today().isoformat(),
        "master_version": __version__, "args": args,
        "stubbed": out.stubbed, "net_mode": out.net_mode,
        "engines_sha256": engines,
        "engine_versions": {n: (out.results.get(n).engine_version
                                if out.results.get(n) else None)
                            for n in ("macro", "quality", "earnings")},
        "provenance": {k: p.as_dict() for k, p in (out.provenance or {}).items()},
        "risk_budget": round(float(out.ctx.risk_budget), 3),
        "risk": (risk_res.ctx_out.get("summary") if risk_res is not None
                 else None),
        "ranking": _frozen_ranking(out),
        "warnings": list(out.warnings)[:12],
    }
    # B2 (v1.4.1 port, phase 2): the freeze manifest carries the risk
    # summary — rho_fallback / rho_used / warn_codes included — so OFFLINE
    # REPLAY of a frozen run reproduces the guard-off disclosure instead
    # of silently dropping it (the port_map conflict note for the new
    # v1.5.0 surfaces). Atomic write (B8): a crash leaves the previous
    # manifest intact.
    _atomic_write_text(d / "manifest.json",
                       json.dumps(man, indent=2, default=str))
    # -- cache copies (capped) ------------------------------------------- #
    cap = int(CONFIG["FREEZE_MAX_BYTES"])
    copied_n = copied_b = 0
    parts: list[str] = []
    qdir = Path(str(_layer_cache_dirs(out.ctx).get("quality", "data/cache")))
    edir = Path(str(_layer_cache_dirs(out.ctx).get("earnings", "")))
    tickers = {c.ticker for c in out.ctx.tickers}
    # earnings + meds first (small, exact); then quality for the run's
    # names; then the rest of the pool while the cap allows.
    n, b = 0, 0
    if edir.is_dir():
        want = [f for f in edir.glob("*.csv")
                if any(f"_{t}_" in f.name for t in tickers)]
        tgt = d / "cache" / "earnings"
        for f in want:
            try:
                tgt.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, tgt / f.name)
                n += 1
                b += f.stat().st_size
            except OSError:
                pass
    copied_n, copied_b = n, b
    parts.append(f"earnings {n} files")
    meds_src = Path(__file__).resolve().parent / "meds_cache" / "cache.json.gz"
    if meds_src.is_file():
        try:
            (d / "meds_cache").mkdir(parents=True, exist_ok=True)
            shutil.copy2(meds_src, d / "meds_cache" / "cache.json.gz")
            parts.append("meds cache 1 file")
            copied_n += 1
            copied_b += meds_src.stat().st_size
        except OSError:
            pass
    snap_starved = False
    snap = _meds_snapshot_root()
    if (snap / "fred").is_dir():
        n2, b2, snap_starved = _freeze_copy_tree(snap, d / "meds_snapshot",
                                                 cap)
        copied_n += n2
        copied_b += b2
        parts.append(f"meds snapshot {n2} files")
    left = max(0, cap - copied_b)
    # quality: run's tickers first (by name match), then the pool. Copied
    # into <d>/cache/quality/cache/<ns>/ so --cache-dir <d>/cache on replay
    # resolves exactly the way the frozen run's dirs did (quality's cache
    # files are engine-internal HASH names — a per-ticker copy is not
    # possible adapter-side, so freeze the run's whole cache dir: exact when
    # the run used a dedicated --cache-dir, size-capped otherwise).
    if qdir.is_dir():
        own = d / "cache" / "quality" / "cache"
        n3 = b3 = 0
        starved = False
        for sub in ("cik_map", "sec", "sec_submissions", "prices_v2"):
            sdir = qdir / sub
            if not sdir.is_dir():
                continue
            files = sorted(sdir.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
            own_files = [f for f in files
                         if any(t.lower() in f.name.lower() for t in tickers)]
            for f in own_files + [x for x in files if x not in own_files]:
                # P7-H1: b3 already grows with every copy — the old code
                # ALSO decremented `left` per file, double-counting the
                # budget (an effective cap of cap/2) and then silently
                # skipping every remaining namespace while copied_b < cap
                # kept the freeze note free of the cap warning.
                if b3 + f.stat().st_size > left:
                    starved = True
                    continue
                target = own / sub / f.name
                if target.resolve() == f.resolve():
                    n3 += 1            # dedicated --cache-dir inside the
                    b3 += f.stat().st_size   # freeze dir: already in place
                    continue
                try:
                    (own / sub).mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, target)
                    n3 += 1
                    b3 += f.stat().st_size
                except OSError:
                    continue
        copied_n += n3
        copied_b += b3
        parts.append(f"quality {n3} files")
    capped = copied_b > cap or starved or snap_starved
    note = (f" — cap {cap // (1024 * 1024)} MB hit; for an EXACT freeze rerun "
            "with a dedicated cache: --freeze DIR --cache-dir DIR/warm (the "
            "run then fills exactly what it needs and the freeze copies it "
            "whole)") if capped else ""
    mb = copied_b / (1024 * 1024)
    return (f"wrote {d}/manifest.json ({len(man['ranking'])} names) · "
            f"copied {copied_n} files {mb:.1f} MB ({', '.join(parts)}){note}")


def _replay_argv(man: dict[str, Any], d: Path) -> list[str]:
    """Rebuild the run's argv from the freeze manifest, forced offline."""
    a = man.get("args") or {}
    argv: list[str] = []
    argv += [str(t) for t in (a.get("tickers") or [])]
    for spec in (a.get("tickers_csv") or []):
        argv += ["--tickers", str(spec)]
    if a.get("watchlist"):
        argv += ["--watchlist", str(a["watchlist"])]
    if a.get("as_of"):
        argv += ["--as-of", str(a["as_of"])]
    if a.get("peers"):
        argv += ["--peers", str(a["peers"])]
    if a.get("earnings_top") is not None:
        argv += ["--earnings-top", str(a["earnings_top"])]
    if a.get("earnings_mode"):
        argv += ["--earnings-mode", str(a["earnings_mode"])]
    if a.get("source") and a["source"] != "auto":
        argv += ["--source", str(a["source"])]
    if a.get("workers"):
        argv += ["--workers", str(a["workers"])]
    if a.get("sector"):
        for s in a["sector"]:
            argv += ["--sector", str(s)]
    if a.get("bucket"):
        for s in a["bucket"]:
            argv += ["--bucket", str(s)]
    if a.get("sectors"):
        argv += ["--sectors", str(a["sectors"])]
    if a.get("cap") and a["cap"] != "any":
        argv += ["--cap", str(a["cap"])]
    if a.get("ml_models_dir"):
        argv += ["--ml-models", str(a["ml_models_dir"])]
    argv += ["--mode", "offline", "--cache-dir", str(d / "cache"),
             "--timeout", "900", "--json", "--quiet"]
    return argv


def run_replay(dir_path: str, ns: argparse.Namespace) -> int:
    """§5: rerun FULLY OFFLINE from a freeze dir (env pointed at the copied
    caches; MASTER_NET=offline so no probe) and FAIL LOUDLY (exit 65) when
    the ranking or any conviction differs from the frozen manifest. A
    tampered cache file shows up as a ranking difference or a clean engine
    error — either way replay refuses to say 'identical'."""
    d = Path(dir_path)
    man_path = d / "manifest.json"
    if not man_path.is_file():
        raise MasterError(f"--replay {dir_path}: no manifest.json (freeze first "
                          "with --freeze)", 2)
    try:
        man = json.loads(man_path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise MasterError(f"--replay {dir_path}: manifest.json unreadable "
                          f"({_exc(e)}) — tampered?", 2) from None
    argv = _replay_argv(man, d)
    env = dict(os.environ)
    env.pop("QE_DATA_DIR", None)
    env.pop("QE_CACHE_DIR", None)
    env["MASTER_NET"] = "offline"
    env["MEDS_CACHE"] = "0"
    if man.get("stubbed"):
        env["MASTER_STUBS"] = "1"
    else:
        env.pop("MASTER_STUBS", None)
    if (d / "meds_snapshot" / "fred").is_dir():
        env["MACRO_ENGINE_SNAPSHOT"] = str(d / "meds_snapshot")
    import subprocess
    t0 = time.monotonic()
    p = subprocess.run([sys.executable, str(Path(__file__).resolve().name)] + argv,
                       cwd=str(Path(__file__).resolve().parent), env=env,
                       capture_output=True, text=True, timeout=3600)
    dt = time.monotonic() - t0
    # phase 5 (C-5): exit 1 (degraded run with warnings) still produced a
    # result — the ranking/conviction comparison below is the replay gate;
    # only a run WITHOUT a result (4+) is a replay failure.
    if p.returncode not in (0, 1):
        sys.stderr.write(f"replay run FAILED (exit {p.returncode}):\n"
                         + (p.stderr or p.stdout)[-600:] + "\n")
        return 65
    try:
        payload = json.loads(p.stdout)
    except ValueError:
        sys.stderr.write("replay run produced no JSON — cannot verify\n")
        return 65
    got = [{"ticker": x["ticker"], "action": x["action"],
            "conviction": round(float(x["conviction"]), 1), "grade": x["grade"]}
           for x in payload.get("decisions", [])]
    want = [{"ticker": x["ticker"], "action": x["action"],
             "conviction": round(float(x["conviction"]), 1), "grade": x["grade"]}
            for x in (man.get("ranking") or [])]
    if got != want:
        sys.stderr.write("REPLAY MISMATCH — the offline rerun from this freeze "
                         "dir differs from the frozen manifest:\n")
        for i in range(max(len(got), len(want))):
            g = got[i] if i < len(got) else None
            w = want[i] if i < len(want) else None
            if g != w:
                sys.stderr.write(f"  rank {i + 1}: frozen {w} vs replay {g}\n")
        sys.stderr.write("tampered cache, changed code, or a partial (capped) "
                         "freeze — freeze again with --mode quick for an exact copy\n")
        return 65
    sys.stderr.write(f"replay OK: {len(got)} names identical to the frozen "
                     f"manifest ({dt:.1f}s, fully offline)\n")
    return 0


def _adv_status() -> tuple[bool, str]:
    """P-4 (spec 3.3, phase 4) feasibility probe, LIVE and offline: is
    average daily dollar volume obtainable from the price feeds master can
    actually read? Checks (a) the earnings engine's cached px_*.csv columns,
    (b) both engine SOURCES for a Volume column anywhere in their price
    paths. Never invents an ADV number; the verdict + the stable
    W_ADV_UNAVAILABLE code is what the doctor prints and what
    scripts/adv_probe.py reports in full."""
    here = Path(__file__).resolve().parent
    csv_hits = 0
    csv_seen = 0
    base = Path.home() / ".earnings_engine_cache"
    try:
        for p in sorted(base.glob("px_*.csv"))[:8]:
            try:
                head = p.open("r", encoding="utf-8", errors="replace").readline()
            except OSError:
                continue
            csv_seen += 1
            cols = {c.strip().strip('"').lower() for c in head.split(",")}
            if any("volume" in c for c in cols):
                csv_hits += 1
    except OSError:
        pass
    src_vol = False
    for fname in ("earnings_engine.py", "quality.py"):
        try:
            src = (here / fname).read_text(encoding="utf-8")
        except OSError:
            continue
        if re.search(r"[\"']Volume[\"']", src):
            src_vol = True            # a future engine that extracts volume
    if csv_hits or src_vol:
        return True, (f"volume present ({csv_hits}/{csv_seen} cached price files"
                      f"{', engine source' if src_vol else ''})")
    return False, ("no volume column in any price feed ("
                   + (f"{csv_seen} cached price file(s) checked: close only; "
                      if csv_seen else "")
                   + "earnings engine prices() = close Series; quality price "
                     "client = Close/Adj Close/Stock Splits)")


def run_doctor(ns: argparse.Namespace) -> int:
    """§8: ONE screen — engines + ENGINES.sha256 match, library versions,
    cache dirs/sizes/data age per layer, network probe, ML head states,
    free disk, the phase-5 COLOUR DIAGNOSTIC (isatty/TERM/COLORTERM/NO_COLOR/
    FORCE_COLOR/CLICOLOR_FORCE/platform/depth/decision+reason) and the
    EXIT-CODE table, plus the single most useful NEXT action. Exit 0 when
    the required engines import and their hashes match, else 1 (degraded
    health — the phase-5 doctor contract)."""
    print(f"master v{__version__} doctor")
    # phase 5 (C-1): the colour diagnostic — you cannot see the owner's
    # terminal, so --doctor must tell you what colour would do and why.
    env = os.environ
    try:
        tty_out = bool(sys.stdout.isatty())
        tty_err = bool(sys.stderr.isatty())
    except Exception:
        tty_out = tty_err = False
    on, reason = _colour_choice(env, tty_out,
                                str(getattr(ns, "color", "auto") or "auto"))
    vt_ok, vt_note = _windows_vt_enable()
    depth = _colour_depth(env)
    print("colour    "
          f"stdout isatty={int(tty_out)} stderr isatty={int(tty_err)} · "
          f"TERM={env.get('TERM', '')} · COLORTERM={env.get('COLORTERM', '')} · "
          f"NO_COLOR={env.get('NO_COLOR', '')} · "
          f"FORCE_COLOR={env.get('FORCE_COLOR', '')} · "
          f"CLICOLOR_FORCE={env.get('CLICOLOR_FORCE', '')} · "
          f"platform={sys.platform} · depth={depth}")
    print(f"          decision: {'ON' if on else 'OFF'} — {reason}"
          + (f" · windows VT: {vt_note}" if vt_ok is not None else ""))
    print("exit      0 clean · 1 degraded (warnings/ml UNAVAILABLE) · "
          "2 usage/config · 3 network · 4 no result/NO-GO · "
          "65 replay mismatch · 70 unexpected · 130 interrupted")
    bad = False
    # engines + hashes
    here = Path(__file__).resolve().parent
    recorded: dict[str, str] = {}
    sha_file = here / "ENGINES.sha256"
    if sha_file.is_file():
        for line in sha_file.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2:
                key = parts[1].removesuffix(".py")
                key = "earnings" if key == "earnings_engine" else key
                recorded[key] = parts[0]
    cells = []
    hashes_note = "(hashes match)"
    for name, mod_name, fn in (("meds", "meds", "meds.py"),
                               ("quality", "quality", "quality.py"),
                               ("earnings", "earnings_engine", "earnings_engine.py")):
        try:
            mod = importlib.import_module(mod_name)
            ver, _t, _d = _engine_version(name, mod)
        except Exception:
            cells.append(f"{name} MISSING")
            bad = True
            continue
        actual = _engines_sha256().get(name, "")
        want = recorded.get(name, "")
        if not want:
            hashes_note = "(ENGINES.sha256 absent — hash check skipped)"
            cells.append(f"{name} ok v{ver}")
        elif actual != want:
            cells.append(f"{name} HASH-MISMATCH")
            bad = True
        else:
            cells.append(f"{name} ok v{ver}")
    print("engines   " + "  ".join(cells) + f"  {hashes_note}")
    # libraries
    libs = [f"python {sys.version.split()[0]}"]
    for lib in ("numpy", "sklearn", "joblib"):
        try:
            m = importlib.import_module(lib)
            libs.append(f"{lib} {getattr(m, '__version__', '?')}")
        except Exception:
            libs.append(f"{lib} absent")
    print("libs      " + " · ".join(libs))
    # caches: age + freshness verdict per layer
    try:
        qdir = str(getattr(importlib.import_module("quality"), "CACHE_DIR", "data/cache"))
    except Exception:
        qdir = "data/cache"
    cdir = {"macro": str(here / "meds_cache"), "quality": qdir,
            "earnings": str(Path.home() / ".earnings_engine_cache")}
    cells = []
    next_hint = ""
    for layer, path in cdir.items():
        as_of = _newest_file_date(path)
        age = _age_days_from(as_of)
        lim = {"macro": CONFIG["FRESHNESS_MACRO_MAX_AGE_D"],
               "quality": CONFIG["FRESHNESS_QUALITY_MAX_AGE_D"],
               "earnings": CONFIG["FRESHNESS_EARNINGS_PRICE_MAX_AGE_D"]}[layer]
        if as_of and age is not None and age > int(lim):
            cells.append(f"{layer} {age}d STALE")
            if not next_hint:
                next_hint = f"python3 master.py --warm --mode online ({layer} cache is {age} days old)"
        elif as_of:
            cells.append(f"{layer} {age}d OK")
        else:
            cells.append(f"{layer} cold")
            if not next_hint:
                next_hint = "python3 master.py --warm (first cache fill)"
    print("cache     " + " | ".join(cells))
    # network
    if ns.offline or os.environ.get("MASTER_NET") == "offline":
        print("network   skipped (--mode offline)")
    else:
        ok, note = _net_probe()
        print(f"network   {'reachable' if ok else 'DOWN'} ({note.replace('probe ok ', '').replace('probe failed: ', '')})")
        if not ok and not next_hint:
            next_hint = "python3 master.py --mode offline (network down; cached truth, ages shown)"
    # phase 4 (P-4): the ADV liquidity feasibility verdict — LOUD and
    # never faked. UNAVAILABLE means no ADV cap and no min-ADV exclusion
    # exist (and none are invented); the full probe is scripts/adv_probe.py.
    adv_ok, adv_note = _adv_status()
    if adv_ok:
        print(f"adv       AVAILABLE ({adv_note}) — guard pending the phase decision")
    else:
        print(f"adv       UNAVAILABLE — {adv_note} [W_ADV_UNAVAILABLE]; "
              "no ADV cap / min-ADV exclusion is implemented (nothing faked); "
              "full probe: python3 scripts/adv_probe.py")
    if not next_hint:
        next_hint = ("python3 master.py --mode quick (caches fresh, network up — "
                     "the fast pass)")
    # ML heads (B-1: through the REAL loader — a version/env-blocked head
    # shows as UNAVAILABLE with its reason, not a fake SHADOW)
    try:
        models_dir = Path(getattr(ns, "ml_models_dir", None) or CONFIG["ML_MODELS_DIR"])
        heads = []
        for head in ("q", "e", "macro"):
            npz = models_dir / f"head_{head}.npz"
            if not npz.is_file():
                heads.append(f"{head} no file")
                continue
            b, note = _ml_load_head(models_dir, head)
            if b is not None:
                heads.append(f"{head} {b['state']}")
                continue
            state = "UNAVAILABLE" if "UNAVAILABLE" in note else "UNTRAINED"
            why = note.split("— ", 1)[-1].split(";")[0].strip()[:46]
            heads.append(f"{head} {state} ({why})")
        print("ml        " + " · ".join(heads)
              + "  (SHADOW heads change no decision; UNAVAILABLE = version/"
                "environment mismatch — retrain with ml_train.py)")
    except Exception as e:
        print(f"ml        state unreadable ({_exc(e)[:60]})")
    # disk
    try:
        usage = shutil.disk_usage(str(here))
        print(f"disk      {usage.free / (1024 ** 3):.1f} GB free of "
              f"{usage.total / (1024 ** 3):.0f} GB")
    except OSError:
        print("disk      ?")
    print(f"NEXT: {next_hint}")
    return 1 if bad else 0


def _cli_run(ns: argparse.Namespace) -> int:
    # final phase (§5): --replay is a DIFFERENT command shape (offline rerun
    # from a freeze dir + verify); it never runs a normal pipeline.
    if getattr(ns, "replay", None):
        return run_replay(str(ns.replay), ns)
    out = run_pipeline(ns)
    if ns.json:
        if out.stubbed:                      # P1-9 (A2): loud even in --json mode
            sys.stderr.write("*** STUBBED RUN — stub layers, NOT real engine data ***\n")
        sys.stdout.write(json.dumps(json_payload(out, ns), indent=2,
                                    default=str, allow_nan=False) + "\n")   # P1-5
    else:
        sys.stdout.write(render_report(out, ns) + "\n")
        if ns.explain:
            t = _norm_ticker(ns.explain) or ns.explain
            sys.stdout.write(_explain_block(make_style(ns), out, ns, t) + "\n")
    if ns.csv:
        sys.stderr.write(f"csv -> {_write_csv(ns.csv, out, ns)}\n")
    # v1.8.0 (W3): Markdown / HTML exports (additive flags; the report,
    # JSON and CSV surfaces are untouched). Atomic writes, same filters.
    md_path = getattr(ns, "md", None)
    html_path = getattr(ns, "html", None)
    if md_path:
        _atomic_write_text(str(md_path), render_markdown(out, ns))
        sys.stderr.write(f"md -> {md_path}\n")
    if html_path:
        _atomic_write_text(str(html_path), render_html(out, ns))
        sys.stderr.write(f"html -> {html_path}\n")
    # phase 5 (C-5): ERRORS also go to STDERR — one line per error entry,
    # both in report mode and --json mode (the block itself stays stdout).
    try:
        _st_err = Style(color=False, ascii_only=bool(getattr(ns, "ascii", False)),
                        width=make_style(ns).width)
        errs = [d for d in _build_diags(out) if d["severity"] == "error"]
        for d in errs:
            sys.stderr.write(_diag_line(_st_err, d) + "\n")
    except Exception:
        pass
    # final phase (§3.5): the after-run refresh report — online's visible
    # proof (items refreshed per layer, seconds, data age before/after).
    if out.net_mode == "online" and out.refresh and not ns.quiet:
        bits = []
        for key in ("meds_cache", "quality", "earnings"):
            r = out.refresh.get(key)
            if isinstance(r, dict) and r.get("refreshed"):
                bits.append(f"{key} {r.get('age_before')} -> {r.get('age_after')}")
        per = out.refresh.get("per_layer_s") or {}
        line = "refresh: " + (" · ".join(bits) if bits else "nothing stale (all caches fresh)")
        line += f" · per-layer {', '.join(f'{k} {v:.1f}s' for k, v in per.items())}"
        sys.stderr.write("[refresh] " + line + "\n")
    if getattr(ns, "freeze", None):
        note = run_freeze(str(ns.freeze), out, ns)
        sys.stderr.write("[freeze] " + note + "\n")
    if getattr(ns, "warm", False):
        qdir = str(getattr(sys.modules.get("quality"), "CACHE_DIR", "")
                   or os.path.join(os.environ.get("QE_DATA_DIR", "data"), "cache"))
        age = _cache_age_h(qdir)
        state = "filled (last write just now)" if age is not None and age < 0.2 \
                else (f"last write {age:.1f}h ago" if age is not None else "still COLD")
        sys.stderr.write("warm-up done — quality cache " + state
                         + "; next: python master.py (warm run ≈ minutes;"
                           " add --mode quick for the fast pass)\n")
    if out.exit_code:
        sys.stderr.write(f"master: exit {out.exit_code} — {out.exit_reason}\n")
    return out.exit_code


class _WizardEOF(Exception):
    """stdin closed mid-wizard (tests / Ctrl-D)."""


_WIZ_SCOPE = {"t": "tickers", "tickers": "tickers", "i": "tickers",
              "s": "sectors", "sectors": "sectors",
              "m": "market", "market": "market"}
_WIZ_CAP = {"a": "any", "any": "any", "mega": "mega", "large": "large",
            "l": "large", "mid": "mid", "mi": "mid", "small": "small",
            "s": "small"}
_WIZ_DEPTH = {"q": "quick", "quick": "quick", "s": "standard",
              "standard": "standard", "d": "deep", "deep": "deep"}


def _wants_wizard(argv: list[str], stdin: Any, stdout: Any) -> bool:
    """Phase 3: the wizard appears only for a NO-ARGUMENT run in a real TTY;
    pipes, scripts and CI keep today's default run."""
    if argv:
        return False
    try:
        return bool(stdin.isatty() and stdout.isatty())
    except Exception:
        return False


def _wiz_tickers(a: str):
    parts = [p for p in re.split(r"[,\s]+", a) if p]
    if not parts:
        return False, "give at least one ticker (e.g. MU, NVDA)"
    bad = [p for p in parts if _norm_ticker(p) is None]
    if bad:
        return False, f"not tickers: {', '.join(bad)}"
    return True, [_norm_ticker(p) for p in parts]


def _wiz_int_1_500(a: str):
    try:
        v = int(a)
    except ValueError:
        return False, "a whole number 1..500"
    return (1 <= v <= 500), (v if 1 <= v <= 500 else "1..500")


def _wiz_yn(a: str):
    x = a.strip().lower()
    if x in ("y", "yes"):
        return True, "y"
    if x in ("n", "no"):
        return True, "n"
    return False, "y or n"


def _wiz_cap(a: str):
    x = a.strip().lower()
    return (x in _WIZ_CAP), (_WIZ_CAP.get(x, "a/mega/l/mid/s"))


def _wiz_depth(a: str):
    x = a.strip().lower()
    return (x in _WIZ_DEPTH), (_WIZ_DEPTH.get(x, "q/s/d"))


class _Ask:
    """One wizard question: prompt on stdout, answer from stdin; invalid
    answers are retried up to the per-question retry budget
    (CONFIG WIZARD_RETRIES, v1.8.1 F2: default 6) before the honest exit 2
    (argparse USAGE errors are a DIFFERENT path — never this one). Empty
    answer takes the default when one exists."""

    def __init__(self, stdin: Any, stdout: Any) -> None:
        self.stdin, self.stdout = stdin, stdout

    def __call__(self, prompt: str, validate: Callable, default: Any = None) -> Any:
        for _ in range(max(1, int(CONFIG["WIZARD_RETRIES"]))):
            self.stdout.write(prompt)
            self.stdout.flush()
            line = self.stdin.readline()
            if line == "":
                raise _WizardEOF()
            ans = line.strip()
            if not ans and default is not None:
                return default
            ok, val = validate(ans)
            if ok:
                return val
            self.stdout.write(f"  ! {val} — try again\n")
        raise MasterError(f"wizard: too many invalid answers for "
                           f"{prompt.strip()[:48]!r}", 2)


def run_wizard(stdin: Any = None, stdout: Any = None) -> tuple[list[str], bool]:
    """Phase-3 startup wizard: scope > sectors (multi) > market-cap band
    (only if data exists, else one honest 'unavailable' line) > discover N >
    layers > depth > confirm. EVERY choice is also a flag; the confirm line
    prints the exact command, and Y parses it through the SAME build_parser —
    the wizard and the flags can never drift apart. Returns (argv, aborted);
    aborted means nothing ran (exit 0, the rerun command is printed)."""
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    ask = _Ask(stdin, stdout)
    argv: list[str] = []
    try:
        # 1 scope ---------------------------------------------------------
        scope = ask("Scope? (t)ickers / (s)ectors / (m)arket: ",
                    lambda a: (a.strip().lower() in _WIZ_SCOPE,
                               _WIZ_SCOPE.get(a.strip().lower(), "answer t, s or m")))
        probe = {"ok": False, "groups": {}, "refs": None, "reason": ""}
        if scope in ("sectors", "market"):
            probe = _universe_probe()
            if not probe["ok"]:
                stdout.write(f"  ! {scope} scope unavailable — {probe['reason']}; "
                             "falling back to your own tickers\n")
                scope = "tickers"
        if scope == "tickers":
            argv += ask("Tickers (comma/space list, e.g. MU, NVDA): ", _wiz_tickers)
        elif scope == "sectors":
            listed = "  ".join(f"{g}({n})" for g, n in
                              sorted(probe["groups"].items(), key=lambda kv: -kv[1])[:12])
            known = list(probe["groups"])
            # v1.8.1 (F2): the n-th LISTED group order (by count, desc) —
            # what the prompt shows — is what a bare number selects.
            listed_order = [g for g, _n in sorted(probe["groups"].items(),
                                                 key=lambda kv: -kv[1])]

            def _wiz_sectors(a: str):
                if a.strip().lower() == "all":
                    return True, ["all"]
                # F2: space OR comma separators (never both required).
                parts = [p.strip().lower() for p in re.split(r"[,\s]+", a)
                          if p.strip()]
                picked: list[str] = []
                for p in parts:
                    if p in known:
                        picked.append(p)
                        continue
                    # F2: a bare number = the n-th listed group.
                    if p.isdigit():
                        n = int(p)
                        if 1 <= n <= len(listed_order):
                            picked.append(listed_order[n - 1])
                            continue
                        return False, (f"{n} is not a listed group number "
                                      f"(1..{len(listed_order)})")
                    # F2: a UNIQUE prefix of one group.
                    pref = [g for g in known if g.startswith(p)]
                    if len(pref) == 1 and len(p) >= 2:
                        picked.append(pref[0])
                        continue
                    if len(pref) > 1:
                        return False, (f"ambiguous prefix {p!r} — "
                                       f"matches {', '.join(sorted(pref))}")
                    # F2: difflib close match — suggest, but never guess.
                    import difflib
                    close = difflib.get_close_matches(p, known, n=1, cutoff=0.75)
                    if close:
                        return False, (f"unknown group {p!r} — did you mean: "
                                       f"{close[0]}?")
                    return False, (f"unknown group {p!r} "
                                   f"(known: {', '.join(sorted(known))})")
                if not picked:
                    return False, "answer group names, prefixes, numbers or 'all'"
                return True, picked

            argv += ["--sectors", ",".join(ask(
                f"Sectors (multi, or 'all') — {listed}: ", _wiz_sectors))]
            stdout.write("  scoring the active names in those groups — "
                         "the [plan] banner sizes the pool first\n")
        else:
            total = sum(probe["groups"].values())
            argv += ["--sectors", "all"]
            stdout.write(f"  market = all sectors: {total} active names — "
                         "standard mode scores them ALL (the [plan] banner "
                         "sizes it first)\n")
        # 2 market-cap band (only if the data exists) -----------------------
        ok, _by_mcap, reason = _mcap_map()
        if ok:
            band = ask("Market-cap band? (a)ny/mega/(l)arge/mid/(s)mall [any]: ",
                       _wiz_cap, default="any")
            if band != "any":
                argv += ["--cap", band]
        else:
            stdout.write(f"  market-cap filter: unavailable — {reason}\n")
        # 3 how many names to discover ------------------------------------
        n = ask("How many names to discover (table rows)? [20]: ",
                _wiz_int_1_500, default=CONFIG["DEFAULT_TOP"])
        argv += ["--discover", str(n)]
        # 4 layers --------------------------------------------------------
        known_layers = list(LAYER_REGISTRY)
        lay_lbl = ", ".join(f"L{i + 1} {n}" for i, n in enumerate(known_layers))

        def _wiz_layers(a: str):
            if a.strip().lower() == "all":
                return True, "all"
            parts = [p.strip().lower() for p in a.split(",") if p.strip()]
            bad = [p for p in parts if p not in known_layers]
            if bad:
                return False, (f"unknown layer(s) {', '.join(bad)} "
                               f"(known: {', '.join(known_layers)})")
            return True, [x for x in known_layers if x in set(parts)]

        lay = ask(f"Layers ({lay_lbl}; subset or blank = all): ",
                  _wiz_layers, default="all")
        if lay != "all":
            argv += ["--only", ",".join(lay)]
        # 5 depth ----------------------------------------------------------
        depth = ask("Depth? (q)uick/(s)tandard/(d)eep [standard]: ",
                    _wiz_depth, default="standard")
        argv += ["--mode", depth]
        # 6 confirm --------------------------------------------------------
        cmd = "python master.py " + " ".join(argv)
        stdout.write(f"\n  command: {cmd}\n")
        if ask("Run? [Y/n]: ", _wiz_yn, default="y") != "y":
            stdout.write(f"  aborted — nothing ran. rerun with: {cmd}\n")
            return [], True
        return argv, False
    except _WizardEOF:
        stdout.write("wizard: end of input — nothing ran. Non-interactive "
                     "runs keep the default: python master.py\n")
        return [], True


def main(argv: list[str] | None = None) -> int:
    """Exit codes — the phase-5 contract (old->new mapping in CHANGELOG and
    the --doctor exit table): 0 clean · 1 degraded (result produced +
    warnings, incl. ml head UNAVAILABLE) · 2 usage/config (was 64; includes
    the unwritable-cache error) · 3 network required but unreachable
    (--mode online) · 4 no result / NO-GO (was 2) · 65 replay mismatch ·
    70 unexpected internal error (was 1; traceback only with --debug) ·
    130 Ctrl-C (names the phase)."""
    ns: argparse.Namespace | None = None
    try:
        argv = list(sys.argv[1:] if argv is None else argv)
        if _wants_wizard(argv, sys.stdin, sys.stdout):
            wargv, aborted = run_wizard(sys.stdin, sys.stdout)
            if aborted:
                return 0
            argv = wargv
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
        if getattr(ns, "doctor", False):
            return run_doctor(ns)
        if getattr(ns, "backtest", False):
            return run_backtest(ns)
        if getattr(ns, "retry_failed", False):
            return _retry_failed_main(ns)
        return _cli_run(ns)
    except KeyboardInterrupt:
        from me.core import _resume_hint
        sys.stderr.write(f"\n^C interrupted during: {phase_name()} — exit 130\n"
                         + _resume_hint(phase_name()) + "\n")
        return 130
    except MasterError as e:
        sys.stderr.write(f"master: {e}\n")
        return e.code
    except Exception as e:
        # phase 5 (C-5): traceback ONLY with --debug (or legacy --verbose);
        # one line otherwise, exit 70.
        if ns is not None and (getattr(ns, "debug", False)
                               or getattr(ns, "verbose", False)):
            import traceback
            traceback.print_exc()
        sys.stderr.write(f"master: unexpected {type(e).__name__}: {_exc(e)} — "
                         "exit 70 (rerun with --debug for the traceback)\n")
        return 70


def _exit_sweep(code: int, grace_s: float = 1.0) -> int:
    """v1.8.1 (N1): the process must EXIT within a few seconds after the
    budget even if non-daemon worker threads are stuck (ThreadPoolExecutor
    threads are non-daemon and threading._shutdown JOINs them). After a
    short grace period: flush the streams, say WHICH threads are being
    left to the OS, and os._exit with the run's own exit code. Guards were
    already uninstalled, caches saved and the report rendered — the stuck
    workers are only cache-filling late (the snapshot discipline, P2-1)."""
    import threading
    deadline = time.monotonic() + max(0.0, grace_s)
    while time.monotonic() < deadline:
        stuck = [t for t in threading.enumerate()
                 if t is not threading.current_thread()
                 and t is not threading.main_thread() and not t.daemon]
        if not stuck:
            return code
        time.sleep(0.1)
    stuck = [t for t in threading.enumerate()
             if t is not threading.current_thread()
             and t is not threading.main_thread() and not t.daemon]
    if stuck:
        names = ", ".join(sorted({t.name for t in stuck}))[:120]
        sys.stderr.write(f"master: {len(stuck)} stuck worker thread(s) "
                         f"[{names}] after the run budget — exiting now "
                         "(they only fill caches late; nothing rendered "
                         "waits on them)\n")
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        os._exit(int(code))
    return code


def _retry_failed_main(ns: argparse.Namespace) -> int:
    """v1.8.1 (N9): the --retry-failed command — reads the LAST run's
    fetch ledger (CONFIG FETCH_LEDGER_PATH), re-fetches ONLY the failed
    TRANSIENT items (never permanent ones), updates the engine caches and
    prints the pass's FETCH HEALTH. Exit 0 all recovered · 1 some still
    failed · 2 no ledger / usage."""
    path = str(getattr(ns, "retry_failed_path", "") or ""
               or CONFIG["FETCH_LEDGER_PATH"])
    try:
        rep = retry_failed(path)
    except MasterError as e:
        sys.stderr.write(f"master: {e}\n")
        return e.code
    lines = ["FETCH HEALTH (retry-failed pass · last ledger "
             f"{Path(path).name})"]
    lines += rep.get("lines") or []
    sys.stdout.write("\n".join(lines) + "\n")
    if rep.get("permanent_skipped"):
        sys.stderr.write(
            f"master: {len(rep['permanent_skipped'])} permanent failure(s) "
            "never retried: "
            + ", ".join(rep["permanent_skipped"][:8]) + "\n")
    return 0 if rep.get("attempted") == rep.get("recovered") else 1


def retry_failed(ledger_path: str,
                 quality_mod: types.ModuleType | None = None,
                 earnings_mod: types.ModuleType | None = None,
                 meds_mod: types.ModuleType | None = None) -> dict:
    """v1.8.1 (N9): re-fetch ONLY the last run's failed TRANSIENT items.
    Reads the jsonl ledger every online run dumps (FETCH_LEDGER_PATH),
    groups the FINAL failures by (layer, item), skips PERMANENT ones
    forever, and re-calls the same engine surfaces the run used:
    quality.get_quality_score(item), EarningsEngine().history(item) /
    .prices(item, start) and meds.now(). Caches are updated by the
    engines themselves; healthy items are never touched."""
    p = Path(ledger_path)
    if not p.is_file():
        raise MasterError(f"no fetch ledger at {ledger_path} — run once "
                          "(online) first; every online run dumps it there",
                          2)
    rows: list[dict] = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    except ValueError as e:
        raise MasterError(f"unreadable fetch ledger {ledger_path} "
                          f"({ _exc(e) }) — delete it; the next online run "
                          "rewrites it", 2) from e
    finals: dict[str, dict] = {}
    for r in rows:
        if r.get("kind") == "skip":
            continue
        cid = str(r.get("call_id") or "")
        if not cid:
            continue
        prev = finals.get(cid)
        if prev is None or int(r.get("attempt", 1)) >= int(
                prev.get("attempt", 1)):
            finals[cid] = r
    want: dict[tuple[str, str], dict] = {}
    permanent: list[str] = []
    for r in finals.values():
        if r.get("ok"):
            continue                       # healthy items are NEVER rerun
        layer, item = str(r.get("layer") or ""), str(r.get("item") or "")
        if not item:
            continue
        if r.get("err_class") != "TRANSIENT":
            if item not in permanent:
                permanent.append(item)    # 404/bad key: never retried
            continue
        want[(layer, item)] = r
    from me.netguard import Ledger
    lg = Ledger()
    recovered = 0
    for (layer, item), r in sorted(want.items()):
        fn, args, kwargs, host = None, (), {}, str(r.get("host") or "")
        try:
            if layer == "quality":
                qm = quality_mod or importlib.import_module("quality")
                refs = None
                gu = getattr(qm, "get_universe", None)
                if callable(gu):
                    try:
                        refs = gu()[0]
                    except Exception:
                        refs = None
                fn, args, kwargs = (qm.get_quality_score, (item,),
                                    {"universe_refs": refs})
            elif layer == "earnings":
                em = earnings_mod or importlib.import_module("earnings_engine")
                eng = em.EarningsEngine(
                    quarters=int(CONFIG["EARNINGS_QUARTERS"]),
                    workers=int(CONFIG["DEFAULT_WORKERS"]),
                    cache_dir=None,
                    cache_ttl_hours=0.0)     # force the refresh
                fn, args, kwargs = (eng.history, (item,), {})
            elif layer == "macro":
                mm = meds_mod or importlib.import_module("meds")
                fn, args, kwargs = (mm.now, (), {})
            else:
                continue
        except Exception as e:
            lg.record(host, layer, item, ok=False, err_class="TRANSIENT",
                      err=f"retry-failed setup: {_exc(e)}", call="retry-failed")
            continue
        t0 = time.monotonic()
        try:
            fn(*args, **kwargs)
            recovered += 1
            lg.record(host, layer, item, ok=True,
                      latency_s=time.monotonic() - t0, call="retry-failed")
        except Exception as e:
            from me.netguard import classify_exc
            lg.record(host, layer, item, ok=False,
                      err_class=classify_exc(e),
                      err=f"{type(e).__name__}: {e}"[:160],
                      latency_s=time.monotonic() - t0, call="retry-failed")
    lg.set_recovered(recovered, len(want))
    lines = ["retry-failed: " + (f"{recovered} of {len(want)} transient "
             "item(s) recovered · caches updated; healthy items were "
             "NOT rerun"
             if want else "no transient-failed items in the last ledger "
             "(nothing to do; permanent failures are never retried)")]
    lines += lg.health_lines()
    return {"attempted": len(want), "recovered": recovered,
            "permanent_skipped": permanent, "lines": lines,
            "ledger": lg.health()}




# ════════════════════════════════════════════════════════════════════════
#  v1.8.0 · MODULE SPLIT RE-EXPORTS — the single definitions now
#  live in me/*; master.py re-exports them so `master.X` (tests,
#  scripts, freeze manifests) resolves to the SAME objects.
from me.core import (  # noqa: F401
    CONFIG,
    _canonical_json,
    Candidate,
    Context,
    Decision,
    LayerProvenance,
    LayerResult,
    LayerSignal,
    MacroState,
    RunOutput,
    _AttrRestore,
    _BUCKET_ETF,
    _CSV_DANGER,
    _CfgKeyRestore,
    _EnvRestore,
    _MISSING_SENTINEL,
    _Progress,
    _RATIONALE,
    _REDACT_RE,
    _SECRET_VARS,
    _SysModuleBlock,
    _TICKER_RE,
    __version__,
    _atomic_write_bytes,
    _atomic_write_text,
    _base_conviction,
    _cache_age_h,
    _cfg,
    _csv_safe,
    _ctx_note,
    _dir_stamp,
    _door_value,
    _engine_version,
    _engines_sha256,
    _exc,
    _fin_int,
    _finite,
    _macro_signal,
    _materialise_meds_snapshot,
    _meds_snapshot_root,
    _missing_fill,
    _native_grade,
    _net_probe,
    _norm_ticker,
    _offline_raiser,
    _offline_transport,
    _offline_yfinance_reason,
    _prepare_meds_snapshot,
    _redact,
    _restore_all,
    _retry_sleep,
    _retrying_fetch,
    _retrying_quality_transport,
    _ruleset,
    _touched,
    config_rationales,
    macro_tilt,
    macro_view,
    month_end_floor
)
from me.errors import (  # noqa: F401
    MasterError,
    _PHASE_NAME,
    _code_registry,
    _phase,
    phase_name
)
from me.risk import (  # noqa: F401
    _ann_vol,
    _rho_bar,
    risk_ctx_out,
    size_portfolio
)
from me.render import (  # noqa: F401
    _export_rows,
    _fmt_num,
    _shorten_word,
    _summary_card,
    render_html,
    render_markdown,
    Style,
    _ASCII_MAP,
    _CAPABLE_MARKERS,
    _COLORS,
    _E_CELL_WORD,
    _LAYER_MODULE,
    _Q_SHORT,
    _STATUS_GLYPH,
    _STRIP_ANSI,
    _bar,
    _build_diags,
    _classify_warning,
    _colour_choice,
    _colour_depth,
    _data_sources_line,
    _decisions_table,
    _diag,
    _diag_line,
    _disp_width,
    _e_cell,
    _earnings_scorecard,
    _engines_sha_recorded,
    _errors_block,
    _explain_block,
    _fit,
    _flags_cell,
    _footer,
    _header,
    _json_num,
    _layers_block,
    _legend_line,
    _macro_card,
    _ml_line,
    _pack_units,
    _pad,
    _pct,
    _pillars_line,
    _prov_status,
    _q_cell,
    _res_signal,
    _sector_table,
    _tilt_line,
    _verdict_line,
    _verdict_reason,
    _windows_vt_enable,
    _wrap,
    json_payload,
    make_style,
    render_report,
    strip_ansi
)
from me.cli import (  # noqa: F401
    MasterParser,
    _apply_mode,
    _layer_registry,
    _validate_ns,
    build_parser
)
from me.backtest import (  # noqa: F401
    _BT_BOOT_N,
    _BT_BOOT_SEED,
    _BT_COSTS_BPS,
    _BT_DATES_REQUIRED,
    _BT_LOCKBOX_N,
    _BT_WINDOW_TD,
    _bt_boot_ci,
    _bt_config_hash,
    _bt_eval_date,
    _bt_fm,
    _bt_harvest_live,
    _bt_quintile_spread,
    _bt_rankdata,
    _bt_rerun_ns,
    _bt_rng,
    _bt_series_metrics,
    _bt_spearman,
    _bt_verdict,
    _master_run_pipeline,
    run_backtest
)


if __name__ == "__main__":                                # pragma: no cover
    # v1.8.0: script-mode aliasing — `python3 master.py` registers THIS
    # running module as 'master' so the late-bound `import master`
    # inside me/* sees the live module instead of double-executing the
    # file (identical objects, one CONFIG, one set of module globals).
    if "master" not in sys.modules:
        sys.modules["master"] = sys.modules[__name__]
    # v1.8.1 (N1): the exit sweep is the SCRIPT-exit path ONLY — a
    # library call (tests, master.main([...]) in-process) returns
    # normally; the process-level promise holds where a process exists.
    sys.exit(_exit_sweep(main()))

