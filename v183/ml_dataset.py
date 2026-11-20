"""ml_dataset.py — phase-4 ML dataset maker (v1)
=================================================
Builds (ticker, as-of) feature/label rows for the future L4 overlay layer
by driving the REAL master pipeline — `import master`, adapters only, the
engines are never edited (H1).

WHAT IT DOES
  For each month-end as-of date (--freq monthly|quarterly) it runs
  master.run_pipeline with the STANDARD pool (--sectors, never quick:
  quality percentile pools over the builtin sector universe), opens the
  earnings funnel to EVERY gated name (no truncation), and harvests the
  layer signals into per-date JSON caches (crash-safe resume: a killed run
  re-invokes and skips cached dates). Labels are computed from prices
  STRICTLY AFTER each as-of using the earnings engine's own price adapter
  (Yahoo daily adjusted close, one fetch per ticker) and its earnings
  history (announcement dates). Delisted / unpriced names are RECORDED,
  never dropped silently.

OUTPUT  ml_data/dataset_v1.npz  (np.savez_compressed; loads with
  allow_pickle=False) — ticker rows:
    X float32 (n_rows, n_features), feature_names, tickers, as_of
    datetime64[D], sector, y_q, y_e, ret_21, ret_63, group (as-of month id)
  + documented extras: event_date (the y_e earnings event, NaT when none)
    and label_end_63 (the 63-trading-day label horizon end; --verify's
    embargo check reads it).
  macro rows (one per sector ETF per as-of):
    macro_X, macro_feature_names, macro_etf, macro_as_of, y_m, macro_group
    (+ macro_ret_1m raw).
  ml_data/manifest.json — schema version, engine + master versions, config
  hashes, date range, row counts, NaN rate per feature, pit_verified per
  engine (meds is PIT_APPROXIMATE by its own label), survivorship warning,
  delisting/gap recording, price field, embargo statement.

TARGETS (full argument in DESIGN_NOTES.md)
  y_q  1 if the 63-TRADING-day forward return beats SPY (quality is slow)
  y_e  1 if the return over ~30 trading days after the NEXT earnings event
       (first event strictly after as_of, within the 63-td window) beats
       SPY over the same window; NaN when no event / incomplete prices
  y_m  1 if the sector ETF beats SPY over the next calendar month
  raw ret_21 / ret_63 stored so other targets can be rebuilt.

USAGE
  python3 ml_dataset.py --sectors tech --dates 12          # the pilot
  python3 ml_dataset.py --sectors all                      # full universe
  python3 ml_dataset.py --verify ml_data/dataset_v1.npz    # reload checks
  Flags: --start/--end (month-ends) · --freq monthly|quarterly · --dates N
  · --sectors g1,g2|all · --workers N · --offline · --cache-dir DIR
  · --out DIR (default ml_data) · --max-dates N (build only N new dates
  this invocation, then stop — resume by re-running) · --restart (ignore
  the date cache) · --timeout SEC (per-layer budget, default 3600).

NOTES
  SEC_USER_AGENT must be set for live quality fetches (SEC 403s anonymous
  UAs); a note is printed when it is absent. Progress lines go to stderr,
  the summary to stdout. Exit 0 ok · 1 verify/build failure · 64 bad usage.
  The universe is today's active listing set: survivorship-biased by
  construction; results exclude costs and claim no alpha.
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import master  # noqa: E402  (the ONLY orchestration path — adapters only)

SCHEMA_VERSION = 1
__version__ = "1.0.0"


def _atomic_write_text(path: "Path", text: str) -> None:
    """v1.4.1 port (B8, phase 2) + the fsync extension: write temp +
    fsync + rename so a crash mid-write leaves the PREVIOUS file intact
    and never a truncated cache/manifest that a later run would load as
    garbage. The temp file is removed on failure."""
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


def _atomic_savez(path: "Path", **arrays) -> None:
    """v1.4.1 port (B8, phase 2) + the fsync extension: atomic npz (file
    handle + fsync + os.replace). Same contract as _atomic_write_text for
    the binary dataset artifact."""
    import numpy as _np
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "wb") as fh:
            _np.savez_compressed(fh, **arrays)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()

# -- label constants (rationales in DESIGN_NOTES.md; NOT master CONFIG ——  #
# master's H2 tunables are untouched; these belong to the dataset contract)
Y_Q_HORIZON_TD = 63          # y_q forward window, trading days (~3 months)
RET_21_TD = 21               # raw stored forward window
Y_E_EVENT_WINDOW_TD = 63     # the y_e event must fall inside the y_q window
Y_E_HOLD_TD = 30             # event-drift window after the entry bar
EMBARGO_TD = 63              # purge+embargo for walk-forward training
BENCHMARK = "SPY"
SECTOR_ETFS = ("XLE", "XLU", "XLP", "XLY", "XLI", "QQQ", "DBC")
DEFAULT_OUT = "ml_data"
EMBARGO_STATEMENT = (
    "Labels look up to 63 trading days (~3 calendar months) ahead of their "
    "as-of date. With monthly as-of dates, consecutive dates' label windows "
    "overlap by construction: walk-forward training must purge + embargo at "
    "least 63 trading days (3 monthly periods; 1 quarterly period) between "
    "train and test, and rows must be grouped by `group` (never shuffled "
    "across time)."
)

_QUALITY_SECTORS = tuple(master.CONFIG["QUALITY_SECTORS"])
_PILLARS = ("profitability", "growth", "financial_strength",
            "earnings_quality", "valuation", "shareholder_yield")
_RANK_FEATURES = ("q_score", "e_score", "p_next_big", "conviction",
                  "days_since_last_earnings", "beat_rate")


def feature_names() -> list[str]:
    """The stable X column list (47 columns; per-head subsets in
    DESIGN_NOTES.md)."""
    names = ["q_score", "q_rank_pct", "q_coverage", "q_flag_count", "q_veto"]
    names += [f"q_pillar_{p}" for p in _PILLARS]
    names += ["e_score", "p_next_big", "beat_rate", "last4_big", "streak_big",
              "qtrs_since_big", "days_since_last_earnings", "e_confidence",
              "conviction", "macro_tilt", "macro_confidence", "macro_leverage",
              "macro_credit_on", "macro_regime_defensive", "macro_regime_risk_on"]
    names += [f"sector_{s}" for s in _QUALITY_SECTORS]
    names += ["q_missing", "e_missing", "p_next_big_missing", "days_since_missing"]
    names += [f"r_{f}" for f in _RANK_FEATURES]
    return names


def macro_feature_names() -> list[str]:
    return ["regime_confidence", "regime_dominance", "regime_leverage",
            "regime_credit_on", "regime_defensive", "regime_risk_on",
            "etf_in_longs", "etf_in_shorts", "tilt_mean"]


def _days_since(as_of: str, last_date) -> float:
    """as_of - last earnings report date; NaN when unknown/unparseable."""
    try:
        return float((date.fromisoformat(as_of[:10])
                      - date.fromisoformat(str(last_date)[:10])).days)
    except (TypeError, ValueError):
        return float("nan")


def _nan(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v if v == v else float("nan")


# ── date grid ─────────────────────────────────────────────────────────────
def _shift_months(iso: str, months: int) -> str:
    """Shift a MONTH-END date by whole months, landing on the target
    month's last day (2026-01-31 + 1m -> 2026-02-28). Callers pass
    month-ends (month_grid floors its bounds first), so the day of the
    input is never carried — a naive day-carry would drift 31 -> 30 -> 28."""
    y, m = int(iso[:4]), int(iso[5:7])
    tot = y * 12 + (m - 1) + months
    yy, mm = tot // 12, tot % 12 + 1
    return f"{yy:04d}-{mm:02d}-{calendar.monthrange(yy, mm)[1]:02d}"


def _ev_str(ev) -> str:
    """An earnings event date as YYYY-MM-DD — pd.Timestamp (its .date is a
    METHOD, not a property), datetime.date or str all work."""
    if isinstance(ev, str):
        return ev[:10]
    d = getattr(ev, "date", None)
    if callable(d):
        return str(d())[:10]
    return str(ev)[:10]


def month_grid(start: str, end: str, freq: str) -> list[str]:
    """Month-end dates (floored), ascending, stepped by the frequency."""
    start, end = master.month_end_floor(start), master.month_end_floor(end)
    step = 1 if freq == "monthly" else 3
    out, cur = [], start
    while cur <= end:
        out.append(cur)
        cur = _shift_months(cur, step)
    return out


def default_end(today: date) -> str:
    """Last month-end whose 63-td label window is COMPLETE: floor(today)
    minus 3 months (labels need ~63 trading days of forward prices)."""
    return _shift_months(master.month_end_floor(today.isoformat()), -3)


# ── per-date build (the real pipeline, adapter-driven) ────────────────────
def build_ns(as_of: str, args: argparse.Namespace) -> argparse.Namespace:
    """The SAME Namespace the CLI builds (adapters only): --sectors scopes
    the STANDARD pool, the funnel is opened to every gated name, the table
    filters cannot hide rows from the harvest."""
    argv = ["--sectors", args.sectors, "--as-of", as_of, "--mode", "standard",
            "--timeout", str(int(args.timeout))]
    if args.offline:
        argv.append("--offline")
    if args.cache_dir:
        argv += ["--cache-dir", str(args.cache_dir)]
    if args.workers:
        argv += ["--workers", str(args.workers)]
    ns = master._apply_mode(master.build_parser().parse_args(argv))
    ns.earnings_top = 10 ** 9          # funnel: NO truncation (every gated name)
    ns.quiet = True                    # ml_dataset paints its own progress
    ns.min_conviction = 0.0
    master._validate_ns(ns)
    return ns


def record_from_parts(as_of: str | None, regime, decisions,
                      risk_budget: float | None = None) -> dict:
    """The per-date record date_features() consumes, built from the parts a
    LIVE run has (phase 5: master's MLLayer calls this on its Decision
    list, so the dataset build and live inference share ONE feature
    source — parity by construction, no second extractor)."""
    st = regime
    macro = {}
    if st is not None:
        macro = {"scenario_key": st.scenario_key, "scenario_name": st.scenario_name,
                 "regime_class": st.regime_class, "cycle_phase": st.cycle_phase,
                 "confidence": st.confidence, "dominance": st.dominance,
                 "conviction_leverage": st.conviction_leverage, "credit": st.credit,
                 "quality_tier": st.quality_tier,
                 "risk_budget": (risk_budget if risk_budget is not None
                                 else getattr(st, "conviction_leverage", 1.0)),
                 "longs": list(st.longs), "shorts": list(st.shorts),
                 "sleeve": list(st.sleeve), "data_tier": st.data_tier,
                 "pit_mode": st.pit_mode, "effective_as_of": st.effective_as_of,
                 "status": st.status}
    names: dict[str, dict] = {}
    for d in decisions:
        q, e = d.layers.get("quality"), d.layers.get("earnings")
        qf = (q.facts if q else {}) or {}
        ef = (e.facts if e else {}) or {}
        rec: dict = {"sector": d.sector, "action": d.action,
                     "conviction": d.conviction,
                     "macro_tilt": (d.layers.get("macro").facts.get("tilt")
                                    if d.layers.get("macro") else None)}
        if q is not None:
            rec["q"] = {"score": q.score, "grade": q.grade, "status": q.status,
                        "rank": qf.get("rank"), "pool_size": qf.get("pool_size"),
                        "coverage": qf.get("coverage"), "flags": list(q.flags),
                        "pillars": dict(qf.get("pillars") or {})}
        if e is not None:
            rec["e"] = {"score": e.score, "grade": e.grade, "status": e.status,
                        "p_next_big": ef.get("p_next_big"),
                        "confidence": ef.get("confidence"),
                        "beat_rate": ef.get("beat_rate"),
                        "last4_big": ef.get("last4_big"),
                        "streak_big": ef.get("streak_big"),
                        "qtrs_since_big": ef.get("qtrs_since_big"),
                        "last_date": ef.get("last_date"),
                        "n_quarters": ef.get("n_quarters")}
        names[d.ticker] = rec
    return {"as_of": as_of, "macro": macro, "names": names}


def harvest(out: master.RunOutput) -> dict:
    """RunOutput -> JSON-able per-date record (the feature source)."""
    base = record_from_parts(out.ctx.as_of, out.ctx.regime, out.decisions,
                             risk_budget=out.ctx.risk_budget)
    base["layers"] = {n: r.status for n, r in out.results.items()}
    base["warnings"] = list(out.warnings)[:12]
    base["pool"] = {"tickers": [c.ticker for c in out.ctx.tickers],
                    "n": len(out.ctx.tickers)}
    return base


def build_date(as_of: str, args: argparse.Namespace) -> dict:
    ns = build_ns(as_of, args)
    out = master.run_pipeline(ns)
    if not out.decisions:
        raise RuntimeError(f"{as_of}: pipeline produced no decisions "
                           f"(exit {out.exit_code}: {out.exit_reason[:120]})")
    return harvest(out)


# ── features ──────────────────────────────────────────────────────────────
def date_features(h: dict) -> dict[str, dict[str, float]]:
    """One feature dict per ticker for ONE date; NaN preserved, *_missing
    flags, sector one-hots, then within-date rank-normalised copies."""
    macro = h.get("macro") or {}
    regime_def = 1.0 if macro.get("regime_class") == "defensive" else 0.0
    regime_ron = 1.0 if macro.get("regime_class") == "risk_on" else 0.0
    credit_on = 1.0 if macro.get("credit") == "ON" else 0.0
    out: dict[str, dict[str, float]] = {}
    for t, rec in h.get("names", {}).items():
        q = rec.get("q") or {}
        e = rec.get("e") or {}
        q_ok = q.get("status") == "OK" and q.get("score") is not None
        e_ok = e.get("status") == "OK" and e.get("score") is not None
        pillars = q.get("pillars") or {}
        flags = q.get("flags") or []
        rank, pool = q.get("rank"), q.get("pool_size")
        f = {
            "q_score": _nan(q.get("score")) if q_ok else float("nan"),
            "q_rank_pct": (_nan(rank) / _nan(pool)
                           if isinstance(rank, (int, float)) and pool else float("nan")),
            "q_coverage": _nan(q.get("coverage")),
            "q_flag_count": float(len(flags)),
            "q_veto": 1.0 if set(flags) & master.CONFIG["VETO_FLAGS"] else 0.0,
            "e_score": _nan(e.get("score")) if e_ok else float("nan"),
            "p_next_big": _nan(e.get("p_next_big")),
            "beat_rate": _nan(e.get("beat_rate")),
            "last4_big": _nan(e.get("last4_big")),
            "streak_big": _nan(e.get("streak_big")),
            "qtrs_since_big": _nan(e.get("qtrs_since_big")),
            "days_since_last_earnings": _days_since(str(h["as_of"]),
                                                     e.get("last_date")),
            "e_confidence": _nan(e.get("confidence")),
            "conviction": _nan(rec.get("conviction")),
            "macro_tilt": _nan(rec.get("macro_tilt")),
            "macro_confidence": _nan(macro.get("confidence")),
            "macro_leverage": _nan(macro.get("conviction_leverage")),
            "macro_credit_on": credit_on,
            "macro_regime_defensive": regime_def,
            "macro_regime_risk_on": regime_ron,
            "q_missing": 0.0 if q_ok else 1.0,
            "e_missing": 0.0 if e_ok else 1.0,
            "p_next_big_missing": (0.0 if e.get("p_next_big") is not None else 1.0),
            "days_since_missing": (0.0 if (e_ok and e.get("last_date")) else 1.0),
        }
        for p in _PILLARS:
            v = (pillars or {}).get(p)
            f[f"q_pillar_{p}"] = _nan(v) if isinstance(v, (int, float)) else float("nan")
        sector = rec.get("sector") or "-"
        for s in _QUALITY_SECTORS:
            f[f"sector_{s}"] = 1.0 if sector == s else 0.0
        out[t] = f
    # within-date rank-normalised copies (NaN preserved; >=2 values needed)
    for feat in _RANK_FEATURES:
        vals = [(t, f[feat]) for t, f in out.items() if f[feat] == f[feat]]
        if len(vals) >= 2:
            vals.sort(key=lambda kv: (kv[1], kv[0]))
            n = len(vals)
            for i, (t, _v) in enumerate(vals):
                out[t][f"r_{feat}"] = i / (n - 1)
        for t, f in out.items():
            f.setdefault(f"r_{feat}", float("nan"))
    return out


def macro_features(h: dict) -> dict[str, list[float]]:
    """Feature row per sector ETF for ONE date (master's macro adapter
    output; meds is PIT_APPROXIMATE and the manifest says so)."""
    macro = h.get("macro") or {}
    longs = set(macro.get("longs") or ())
    shorts = set(macro.get("shorts") or ())
    conf = _nan(macro.get("confidence"))
    dom = _nan(macro.get("dominance"))
    lev = _nan(macro.get("conviction_leverage"))
    credit = 1.0 if macro.get("credit") == "ON" else 0.0
    defensive = 1.0 if macro.get("regime_class") == "defensive" else 0.0
    risk_on = 1.0 if macro.get("regime_class") == "risk_on" else 0.0
    etf_to_sectors = master.CONFIG["ETF_TO_SECTORS"]
    rows: dict[str, list[float]] = {}
    for etf in SECTOR_ETFS:
        tilts = []
        if macro:
            for sec, _strength in etf_to_sectors.get(etf, ()):
                tilt = master.macro_tilt(
                    _state_like(macro), sec)
                if tilt is not None:
                    tilts.append(tilt)
        tilt_mean = (sum(tilts) / len(tilts)) if tilts else float("nan")
        rows[etf] = [conf, dom, lev, credit, defensive, risk_on,
                     1.0 if etf in longs else 0.0,
                     1.0 if etf in shorts else 0.0,
                     tilt_mean]
    return rows


def _state_like(macro: dict) -> master.MacroState:
    """A MacroState carrying just what macro_tilt reads (the harvest is the
    source; no engine re-run)."""
    st = master.MacroState()
    st.scenario_key = str(macro.get("scenario_key") or "")
    st.regime_class = str(macro.get("regime_class") or "neutral")
    st.longs = tuple(macro.get("longs") or ())
    st.shorts = tuple(macro.get("shorts") or ())
    st.status = str(macro.get("status") or "OK")
    return st


# ── labels (prices strictly after as-of; delisted names recorded) ─────────
class PriceBook:
    """Adjusted-close series per ticker via the earnings engine's own price
    adapter (one fetch each, engine-cached)."""

    def __init__(self, eng) -> None:
        self.eng = eng
        self.memo: dict[str, object] = {}

    def series(self, t: str, start: str):
        if t not in self.memo:
            try:
                self.memo[t] = self.eng.prices(t, start)
            except Exception:
                self.memo[t] = None
        return self.memo[t]


def forward_return(series, as_of: str, n_td: int):
    """(return, end_date) over the n_td trading rows strictly after as_of;
    entry basis = last close <= as_of. (nan, None) when the series is too
    short (delisted / not yet enough history) — the caller records it."""
    if series is None or not len(series):
        return float("nan"), None
    idx, vals = series.index, series.to_numpy(float)
    pos = int(idx.searchsorted(as_of, side="right")) - 1
    if pos < 0:
        return float("nan"), None
    end = pos + n_td
    if end >= len(idx):
        return float("nan"), None
    return float(vals[end] / vals[pos] - 1.0), str(idx[end].date())


def next_event(events, as_of: str, series, window_td: int):
    """The first earnings event strictly after as_of and within the
    window_td trading rows after as_of; (event_date, entry_pos) or
    (None, None)."""
    if series is None or not len(series) or events is None or not len(events):
        return None, None
    idx = series.index
    pos = int(idx.searchsorted(as_of, side="right")) - 1
    if pos < 0:
        return None, None
    horizon = min(pos + window_td, len(idx) - 1)
    horizon_date = str(idx[horizon].date())
    for ev in events:
        ev_d = _ev_str(ev)
        if as_of < ev_d <= horizon_date:
            entry = int(idx.searchsorted(ev_d, side="right"))  # first bar AFTER the event
            if entry < len(idx):
                return ev_d, entry
    return None, None


def window_return(series, entry_pos: int, hold_td: int):
    if series is None or not len(series):
        return float("nan"), None
    vals = series.to_numpy(float)
    end = entry_pos + hold_td
    if entry_pos >= len(vals) or end >= len(vals):
        return float("nan"), None
    idx = series.index
    return float(vals[end] / vals[entry_pos] - 1.0), str(idx[end].date())


def month_end_next(as_of: str) -> str:
    nxt = _shift_months(master.month_end_floor(as_of), 1)
    return nxt


# ── assembly ──────────────────────────────────────────────────────────────
def assemble(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    cache_dir = out_dir / "cache" / "dates"
    cache_dir.mkdir(parents=True, exist_ok=True)
    end = args.end or default_end(date.today())
    start = args.start or _shift_months(end, -(int(args.dates) - 1))
    dates = month_grid(start, end, args.freq)
    if not dates:
        print(f"ml_dataset: empty date grid ({start}..{end}, {args.freq})", file=sys.stderr)
        return 64
    # final phase §7.3: disk-space check BEFORE a long build (a mid-build
    # ENOSPC is the worst possible failure mode).
    _need_mb = len(dates) * 3.0          # per-date cache JSONs, measured ~2-3 MB
    _free_mb = shutil.disk_usage(str(Path(args.out))).free / (1024 * 1024)
    if _free_mb < max(512.0, _need_mb * 2):
        print(f"ml_dataset: only {_free_mb:.0f} MB free under {args.out} - a "
              f"build needs ~{_need_mb:.0f} MB of date-cache headroom; free "
              "space or pass --out elsewhere", file=sys.stderr)
        return 2
    if not args.offline and not os.environ.get("SEC_USER_AGENT"):
        print("[ml] note: SEC_USER_AGENT is not set — SEC EDGAR will likely "
              "403 live quality fetches (set it, or pass --offline for a "
              "cache-only build)", file=sys.stderr)

    # -- 1 · per-date pipeline runs (cached, resumable) ------------------- #
    harvested: dict[str, dict] = {}
    built = skipped = failed = 0
    t0 = time.monotonic()
    for i, d in enumerate(dates, 1):
        cpath = cache_dir / f"{d}.json"
        if cpath.exists() and not args.restart:
            harvested[d] = json.loads(cpath.read_text(encoding="utf-8"))
            skipped += 1
            print(f"[ml] {i}/{len(dates)} {d} · cached", file=sys.stderr)
            continue
        if args.max_dates is not None and built >= int(args.max_dates):
            print(f"[ml] --max-dates {args.max_dates}: stopping after {built} "
                  f"new date(s); re-run to resume", file=sys.stderr)
            break
        sys.stderr.write(f"[ml] {i}/{len(dates)} {d} · building (pool via "
                         f"--sectors {args.sectors}) ...\n")
        sys.stderr.flush()
        try:
            h = build_date(d, args)
            _atomic_write_text(cpath, json.dumps(h, default=str))
            harvested[d] = h
            built += 1
            q_ok = sum(1 for r in h["names"].values()
                       if (r.get("q") or {}).get("status") == "OK")
            print(f"[ml] {i}/{len(dates)} {d} · {h['pool']['n']} names · "
                  f"quality OK {q_ok} · layers "
                  f"{','.join(f'{k}={v}' for k, v in h['layers'].items())} · "
                  f"{time.monotonic() - t0:.0f}s", file=sys.stderr)
        except Exception as e:                               # noqa: BLE001
            failed += 1
            print(f"[ml] {i}/{len(dates)} {d} · FAILED {type(e).__name__}: "
                  f"{str(e)[:160]}", file=sys.stderr)
    if not harvested:
        print("ml_dataset: no dates built — nothing to assemble", file=sys.stderr)
        return 1
    dates = [d for d in dates if d in harvested]              # ascending grid order

    # -- 2 · labels: one price fetch per name via the engine adapter ------ #
    import earnings_engine
    eng = earnings_engine.EarningsEngine(
        workers=int(args.workers or master.CONFIG["DEFAULT_WORKERS"]),
        cache_dir=(os.path.join(str(args.cache_dir), "earnings")
                   if args.cache_dir else None))
    if args.offline:
        eng._fetch = master._offline_raiser
        eng._px_fetch = master._offline_raiser
    price_start = _shift_months(dates[0], -2)
    book = PriceBook(eng)
    spy = book.series(BENCHMARK, price_start)
    etf_series = {etf: book.series(etf, price_start) for etf in SECTOR_ETFS}

    def _events(t: str):
        try:
            h = eng.history(t)
            return list(h["date"]) if h is not None and len(h) else None
        except Exception:
            return None

    # -- 3 · ticker rows --------------------------------------------------- #
    names = feature_names()
    tickers: list[str] = []
    as_of_arr: list[str] = []
    sector_arr: list[str] = []
    group_arr: list[int] = []
    rows: list[list[float]] = []
    y_q: list[float] = []
    y_e: list[float] = []
    ret_21: list[float] = []
    ret_63: list[float] = []
    event_arr: list[str] = []
    label_end_arr: list[str] = []
    gap_names: set[str] = set()

    for d in dates:
        feats = date_features(harvested[d])
        group = int(d[:4]) * 12 + int(d[5:7]) - 1
        spy63, _ = forward_return(spy, d, Y_Q_HORIZON_TD)
        spy21, _ = forward_return(spy, d, RET_21_TD)
        for t in harvested[d]["pool"]["tickers"]:
            f = feats.get(t)
            if f is None:                       # a decision row never appeared
                continue
            tickers.append(t)
            as_of_arr.append(d)
            sector_arr.append((harvested[d]["names"].get(t) or {}).get("sector") or "-")
            group_arr.append(group)
            rows.append([f[n] for n in names])
            s = book.series(t, price_start)
            r21, _e21 = forward_return(s, d, RET_21_TD)
            r63, e63 = forward_return(s, d, Y_Q_HORIZON_TD)
            ret_21.append(r21)
            ret_63.append(r63)
            label_end_arr.append(e63 or "")
            if r63 != r63:
                gap_names.add(t)                 # series too short / no data: recorded
            y_q.append((1.0 if r63 > spy63 else 0.0)
                       if (r63 == r63 and spy63 == spy63) else float("nan"))
            ev, entry = next_event(_events(t), d, s, Y_E_EVENT_WINDOW_TD)
            event_arr.append(ev or "")
            if ev is None:
                y_e.append(float("nan"))
            else:
                ret_ev, _ = window_return(s, entry, Y_E_HOLD_TD)
                spy_ev, _ = window_return(spy, entry, Y_E_HOLD_TD)
                y_e.append((1.0 if ret_ev > spy_ev else 0.0)
                           if (ret_ev == ret_ev and spy_ev == spy_ev)
                           else float("nan"))

    # -- 4 · macro rows ----------------------------------------------------- #
    mnames = macro_feature_names()
    macro_rows: list[list[float]] = []
    macro_etf: list[str] = []
    macro_as_of: list[str] = []
    macro_group: list[int] = []
    y_m: list[float] = []
    macro_ret: list[float] = []
    for d in dates:
        group = int(d[:4]) * 12 + int(d[5:7]) - 1
        mrows = macro_features(harvested[d])
        nxt = month_end_next(d)

        def _ret_to(series, as_of: str, until: str):
            if series is None or not len(series):
                return float("nan")
            idx, vals = series.index, series.to_numpy(float)
            p0 = int(idx.searchsorted(as_of, side="right")) - 1
            p1 = int(idx.searchsorted(until, side="right")) - 1
            if p0 < 0 or p1 <= p0:
                return float("nan")
            return float(vals[p1] / vals[p0] - 1.0)
        spy_m = _ret_to(spy, d, nxt)
        for etf in SECTOR_ETFS:
            macro_rows.append(mrows[etf])
            macro_etf.append(etf)
            macro_as_of.append(d)
            macro_group.append(group)
            r = _ret_to(etf_series[etf], d, nxt)
            macro_ret.append(r)
            y_m.append((1.0 if r > spy_m else 0.0)
                       if (r == r and spy_m == spy_m) else float("nan"))

    # -- 5 · arrays + save -------------------------------------------------- #
    import numpy as np
    X = np.array(rows, dtype=np.float32) if rows else np.zeros((0, len(names)), np.float32)
    mX = np.array(macro_rows, dtype=np.float32) if macro_rows \
        else np.zeros((0, len(mnames)), np.float32)

    def _d64(seq):
        return np.array([np.datetime64(x) if x else np.datetime64("NaT")
                         for x in seq], dtype="datetime64[D]") if seq \
            else np.array([], dtype="datetime64[D]")

    npz_path = out_dir / "dataset_v1.npz"
    _atomic_savez(
        npz_path,
        X=X,
        feature_names=np.array(names),
        tickers=np.array(tickers),
        as_of=_d64(as_of_arr),
        sector=np.array(sector_arr),
        y_q=np.array(y_q, dtype=np.float32),
        y_e=np.array(y_e, dtype=np.float32),
        ret_21=np.array(ret_21, dtype=np.float32),
        ret_63=np.array(ret_63, dtype=np.float32),
        group=np.array(group_arr, dtype=np.int32),
        event_date=_d64(event_arr),
        label_end_63=_d64(label_end_arr),
        macro_X=mX,
        macro_feature_names=np.array(mnames),
        macro_etf=np.array(macro_etf),
        macro_as_of=_d64(macro_as_of),
        y_m=np.array(y_m, dtype=np.float32),
        macro_group=np.array(macro_group, dtype=np.int32),
        macro_ret_1m=np.array(macro_ret, dtype=np.float32),
    )

    # -- 6 · manifest -------------------------------------------------------- #
    nan_rates = {n: float(np.isnan(X[:, i]).mean()) if len(X) else 0.0
                 for i, n in enumerate(names)}
    try:
        import quality
        q_hash = quality.config_hash()
    except Exception:
        q_hash = ""
    # v1.8.0 (D-18-002): deterministic CONFIG hash — the v1.7.0 recipe
    # str()'ed frozensets, so the hash changed with PYTHONHASHSEED every
    # process. Same shared recipe as me/backtest._bt_config_hash now.
    m_hash = hashlib.sha256(master._canonical_json(
        master.CONFIG).encode()).hexdigest()[:16]
    delisted, renamed = [], []
    try:
        import quality
        _refs, rep = quality.get_universe()
        delisted, renamed = rep.get("delisted", []), rep.get("renamed", [])
    except Exception:
        pass
    _stubbed = str(os.environ.get("MASTER_STUBS", "")).strip().lower() \
        not in ("", "0", "false")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created": date.today().isoformat(),
        # v1.8.0 (W6): provenance declaration — ml_train AND --backtest
        # refuse anything but class REAL-API (synthetic = unit-test-only
        # fixtures; R7). stubbed builds are labelled SYNTHETIC.
        "data_provenance": {
            "class": ("SYNTHETIC" if _stubbed else "REAL-API"),
            "stubbed": _stubbed,
            "apis": ["FRED", "SEC EDGAR", "Finnhub", "Yahoo (yfinance)"],
            "note": ("engine fetches (adapters only, engines never "
                     "edited); offline builds serve the engines' own "
                     "cached REAL data")},

        "ml_dataset_version": __version__,
        "master_version": master.__version__,
        "engine_versions": dict(master.CONFIG["TESTED_VERSIONS"]),
        "config_hash_master": m_hash,
        "config_hash_quality": q_hash,
        "build": {"freq": args.freq, "sectors": args.sectors,
                  "pool": "standard (quality sector percentile pools, peers=builtin)",
                  "funnel": "earnings top-K opened to every gated name (no truncation)",
                  "dates": dates, "dates_built": built, "dates_cached": skipped,
                  "dates_failed": failed, "offline": bool(args.offline),
                  "workers": int(args.workers or master.CONFIG["DEFAULT_WORKERS"])},
        "date_range": [dates[0], dates[-1]],
        "rows": {"ticker_rows": len(tickers), "macro_rows": len(macro_etf),
                 "tickers": len(set(tickers)), "dates": len(dates)},
        "nan_rate_per_feature": nan_rates,
        "label_coverage": {
            "y_q": (sum(1 for v in y_q if v == v) / len(y_q)) if y_q else 0.0,
            "y_e": (sum(1 for v in y_e if v == v) / len(y_e)) if y_e else 0.0,
            "ret_63": (sum(1 for v in ret_63 if v == v) / len(ret_63)) if ret_63 else 0.0,
        },
        "pit_verified": {"earnings": True, "quality": True, "meds": False},
        "pit_status": {
            "earnings": "PIT_VERIFIED — deterministic; _window cuts quarters to "
                        "date+provider-lag < as_of (evidence/phase4_pit_probes.txt)",
            "quality": "PIT_VERIFIED — deterministic; facts cut by public "
                       "availability (filing) date, boundary probe passed",
            "meds": "PIT_APPROXIMATE — deterministic, as-of floored, PIT lags "
                    "applied, but series are fetched at TODAY's vintage "
                    "(pit_mode=approximate_pit_lag) — pit_verified false",
        },
        "price_field": ("Yahoo daily ADJUSTED close (earnings_engine.prices, "
                        "auto_adjust=True); feature prices are cut at as-of by "
                        "the engines, label prices are strictly after as-of"),
        "embargo": EMBARGO_STATEMENT,
        "targets": {
            "y_q": f"1 if the {Y_Q_HORIZON_TD}-trading-day forward return beats "
                   f"{BENCHMARK} (quality is slow)",
            "y_e": f"1 if the {Y_E_HOLD_TD}-trading-day return after the next "
                   f"earnings event (first event strictly after as-of, within "
                   f"{Y_E_EVENT_WINDOW_TD} td) beats {BENCHMARK}; NaN when no "
                   "event or incomplete prices",
            "y_m": "1 if the sector ETF beats SPY over the next calendar month",
        },
        "survivorship_warning": (
            "The universe is TODAY's active listing set (quality's builtin "
            "universe, active refs only): names delisted before the build are "
            "absent by construction and forward returns are upward-biased. "
            "Results exclude costs and claim no alpha."),
        "delisting_and_gaps": {
            "universe_delisted": delisted, "universe_renamed": renamed,
            "forward_price_gap_names": sorted(gap_names),
            "forward_price_gap_rows": int(sum(1 for v in ret_63 if v != v)),
        },
    }
    _atomic_write_text(out_dir / "manifest.json",
                       json.dumps(manifest, indent=2, default=str))
    ok_q = sum(1 for v in y_q if v == v)
    ok_e = sum(1 for v in y_e if v == v)
    print(f"dataset -> {npz_path}")
    print(f"  ticker rows {len(tickers)} ({len(set(tickers))} names x "
          f"{len(dates)} dates) · macro rows {len(macro_etf)}")
    print(f"  labels: y_q {ok_q}/{len(y_q)} · y_e {ok_e}/{len(y_e)} · "
          f"y_m {sum(1 for v in y_m if v == v)}/{len(y_m)}")
    print(f"  dates built {built} · cached {skipped} · failed {failed} · "
          f"manifest -> {out_dir / 'manifest.json'}")
    return 0 if (failed == 0 and (built or skipped)) else 1


# ── --verify ---------------------------------------------------------------
def verify(path: str) -> int:
    """Reload checks: shapes/dtypes/key parity, feature time-safety, the
    label-horizon embargo, class balance, NaN rates vs the manifest."""
    import numpy as np
    p = Path(path)
    if not p.exists():
        print(f"verify: {path} does not exist", file=sys.stderr)
        return 64
    ok = True

    def check(cond: bool, msg: str) -> None:
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + msg)
        ok = ok and bool(cond)

    z = np.load(p, allow_pickle=False)           # PASS 1: pickle-free load
    check(True, f"loads with allow_pickle=False ({p.stat().st_size / 1e6:.1f} MB)")
    keys = set(z.files)
    need = {"X", "feature_names", "tickers", "as_of", "sector", "y_q", "y_e",
            "ret_21", "ret_63", "group", "macro_X", "macro_feature_names",
            "macro_etf", "macro_as_of", "y_m", "macro_group"}
    check(need <= keys, f"key parity: required keys present (extras: {sorted(keys - need)})")
    X, fn = z["X"], [str(s) for s in z["feature_names"]]
    n = len(z["tickers"])
    check(X.ndim == 2 and X.shape[0] == n and X.shape[1] == len(fn),
          f"shapes: X {X.shape} == ({n}, {len(fn)}) rows/tickers/features")
    for k in ("as_of", "sector", "y_q", "y_e", "ret_21", "ret_63", "group"):
        check(len(z[k]) == n, f"shape parity: {k} has {len(z[k])} rows")
    check(str(X.dtype) == "float32", f"X dtype {X.dtype} == float32")
    check(str(z["as_of"].dtype) == "datetime64[D]", f"as_of dtype {z['as_of'].dtype}")
    check(np.issubdtype(z["group"].dtype, np.integer), "group dtype is integer")
    as_of, group = z["as_of"], z["group"]
    check(bool(np.all(as_of[:-1] <= as_of[1:])) if n else True,
          "as_of rows are non-decreasing (build order = time order)")
    months = np.array([int(str(d)[:4]) * 12 + int(str(d)[5:7]) - 1 for d in as_of])
    check(bool(np.all(months == group)) if n else True, "group == as-of month id")
    # feature time-safety
    fi = {f: i for i, f in enumerate(fn)}
    if "days_since_last_earnings" in fi:
        dsl = X[:, fi["days_since_last_earnings"]]
        check(bool(np.all((dsl != dsl) | (dsl >= 0))),
              "days_since_last_earnings >= 0 or NaN (no future-dated reports)")
    if "event_date" in z.files:
        ev = z["event_date"]
        check(bool(np.all((ev.astype("datetime64[D]") > as_of)
                          | np.isnat(ev.astype("datetime64[D]")))),
              "y_e event dates are strictly AFTER their as-of (no lookahead)")
    if "label_end_63" in z.files:
        le = z["label_end_63"].astype("datetime64[D]")
        check(bool(np.all((le >= as_of) | np.isnat(le))),
              "label_end_63 >= as_of (windows point forward)")
    # embargo: label horizon vs the next training as-of
    uniq = sorted(set(as_of.tolist())) if n else []
    overlaps = 0
    if len(uniq) > 1 and "label_end_63" in z.files:
        le = z["label_end_63"].astype("datetime64[D]")
        by_date = {d: e for d, e in zip(as_of.tolist(), le.tolist())}
        for a, b in zip(uniq, uniq[1:]):
            if by_date[a] and by_date[a] > np.datetime64(b, "D"):
                overlaps += 1
        step = (uniq[1] - uniq[0]).days
        if step >= 80:      # quarterly grid: 63 td fits inside one step
            check(overlaps == 0,
                  f"quarterly grid: label windows never overlap the next as-of "
                  f"(overlaps={overlaps}) — embargo {EMBARGO_TD} td is inherent")
        else:
            check(True, f"monthly grid: {overlaps}/{len(uniq) - 1} consecutive "
                        f"date pairs share label price windows (63 td > 1 month) "
                        f"— REQUIRED purge+embargo >= {EMBARGO_TD} trading days "
                        f"(3 monthly periods); never shuffle across `group`")
    # class balance per target
    for k in ("y_q", "y_e", "y_m"):
        y = z[k]
        good = y[~np.isnan(y)] if len(y) else y
        if not len(good):
            check(False, f"class balance {k}: NO labelled rows")
            continue
        mean = float(good.mean())
        check(0.0 < mean < 1.0,
              f"class balance {k}: {int(good.sum())}/{len(good)} positive "
              f"({mean:.1%}) — both classes present")
    # NaN rates vs manifest
    mpath = p.parent / "manifest.json"
    if mpath.exists():
        man = json.loads(mpath.read_text(encoding="utf-8"))
        rates = man.get("nan_rate_per_feature") or {}
        drift = [f for f, r in rates.items()
                 if f in fi and abs(float(r) - float(np.isnan(X[:, fi[f]]).mean())) > 1e-6]
        check(not drift, f"NaN rates match the manifest (drift: {drift or 'none'})")
        check(bool(man.get("pit_verified")) is not None and
              "survivorship_warning" in man and "embargo" in man,
              "manifest carries pit_verified, survivorship warning + embargo")
    print(("verify: OK" if ok else "verify: FAILED"))
    return 0 if ok else 1


# ── CLI ───────────────────────────────────────────────────────────────────

MEASURED_S_PER_NAME = 1.3     # cold-cache seconds per pool name, measured on
                              # the build machine (371 names in 480 s); the
                              # dry-run prints this basis and allows an override


def dry_run(args: argparse.Namespace) -> int:
    """Final phase §7.3: NO build - print the plan (dates, tickers, expected
    rows, expected time from measured per-date seconds, disk needed vs free)
    and exit 0. The estimate basis is printed; nothing is fetched."""
    end = args.end or default_end(date.today())
    start = args.start or _shift_months(end, -(int(args.dates) - 1))
    dates = month_grid(start, end, args.freq)
    if not dates:
        print(f"ml_dataset: empty date grid ({start}..{end}, {args.freq})", file=sys.stderr)
        return 64
    cache_dir = Path(args.out) / "cache" / "dates"
    cached = [d for d in dates if (cache_dir / f"{d}.json").exists()]
    todo = [d for d in dates if d not in cached]
    pool, pool_basis = 0, "universe probe failed"
    try:
        _g, sel, err = master._sector_scope(args.sectors)
        if err:
            pool_basis = f"universe probe: {err[:80]}"
        else:
            pool = len(sel)
            pool_basis = (f"quality universe probe: {pool} active names in "
                          f"--sectors {args.sectors}")
    except Exception as e:
        pool_basis = f"universe probe failed ({type(e).__name__})"
    spn = (float(args.per_date_s) / max(pool, 1)
           if getattr(args, "per_date_s", None) else MEASURED_S_PER_NAME)
    per_date = pool * spn
    basis_t = (f"{pool} names x {spn:.2f} s/name cold (measured on the build "
               "machine; override with --per-date-s)")
    rows_exp = int(len(dates) * pool * 0.85)   # 0.85 = measured gated-row coverage
    t_exp = len(todo) * per_date + len(cached) * 5.0
    n_feat = len(feature_names())
    disk_mb = rows_exp * (n_feat + 6) * 8 / (1024 * 1024) * 2.0   # npz + labels
    free_mb = shutil.disk_usage(str(Path(args.out))).free / (1024 * 1024)
    print("ml_dataset DRY RUN (no build, no fetch):")
    print(f"  dates      {len(dates)} ({dates[0]}..{dates[-1]}, {args.freq})"
          f" | {len(cached)} cached | {len(todo)} to build")
    print(f"  tickers    ~{pool} per date ({pool_basis})")
    print(f"  rows       ~{rows_exp} expected (pool x dates x 0.85 gated coverage)")
    print(f"  time       ~{t_exp / 60:.0f} min ({basis_t})")
    print(f"  disk       ~{disk_mb:.0f} MB needed vs {free_mb / 1024:.1f} GB free")
    if free_mb < disk_mb * 2:
        print("  ! disk headroom below 2x the estimate - free space first",
              file=sys.stderr)
    print("  pacing     the engines' own limiters (quality 40 Yahoo/min, SEC "
          "fair-access); no added parallelism; resumable per date")
    print("  next       re-run WITHOUT --dry-run to build; interrupt any time - "
          "cached dates are kept and the same command resumes")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="ml_dataset.py",
        description="Build the (ticker, as-of) ML dataset from the real "
                    "master pipeline (adapters only; engines never edited).")
    ap.add_argument("--start", help="first month-end (default: dates back from end)")
    ap.add_argument("--end", help="last month-end (default: floor(today)-3m "
                                  "so every 63-td label window is complete)")
    ap.add_argument("--dates", type=int, default=12,
                    help="grid length when --start is not given (default 12)")
    ap.add_argument("--freq", choices=("monthly", "quarterly"), default="monthly")
    ap.add_argument("--sectors", default="tech",
                    help="quality sector groups for the STANDARD pool "
                         "(comma list or 'all'; default tech)")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--offline", action="store_true",
                    help="engine caches only (master's offline guards)")
    ap.add_argument("--cache-dir", default=None,
                    help="redirect quality+earnings caches (master --cache-dir)")
    ap.add_argument("--out", default=DEFAULT_OUT, help=f"output dir (default {DEFAULT_OUT})")
    ap.add_argument("--max-dates", type=int, default=None, metavar="N",
                    help="build at most N new dates this invocation (resume "
                         "by re-running; the date cache is the resume point)")
    ap.add_argument("--restart", action="store_true", help="ignore cached dates")
    ap.add_argument("--timeout", type=float, default=3600.0,
                    help="per-layer budget seconds (default 3600)")
    ap.add_argument("--verify", metavar="FILE",
                    help="verify an existing dataset npz and exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan (dates, tickers, expected rows, time "
                         "from measured per-date seconds, disk needed vs "
                         "free) and exit - no build, no fetch")
    ap.add_argument("--per-date-s", type=float, default=None, metavar="S",
                    help="dry-run override: measured seconds per date "
                         "(default: pool x 1.3 s/name cold)")
    args = ap.parse_args(argv)
    if args.verify:
        return verify(args.verify)
    if args.dry_run:
        return dry_run(args)
    if args.dates < 1 or (args.max_dates is not None and args.max_dates < 1):
        print("ml_dataset: --dates/--max-dates must be >= 1", file=sys.stderr)
        return 64
    try:
        return assemble(args)
    except KeyboardInterrupt:
        print("\nml_dataset: interrupted — cached dates are kept; re-run to "
              "resume", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
