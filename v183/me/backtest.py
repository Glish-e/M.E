"""me/backtest.py — the §5.8 integration backtest (v1.8.0 split from
master.py): consumes the recorded per-date run_pipeline harvests (or
re-runs them through the same pipeline), evaluates the ACTUAL fused
convictions against the dataset's 63-td label windows, and prints the
preregistered gates with costs (10 bps/side baseline, 5/10/25/50
sensitivity)."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

from me.cli import _apply_mode, _validate_ns, build_parser
from me.core import (CONFIG, RunOutput, _atomic_write_text, _exc,
                     month_end_floor)
from me.errors import MasterError, _code_registry

_SYNTHETIC_ALLOWED: list = []      # v1.8.0 W6: unit-test bypass marker (MASTER_ALLOW_SYNTHETIC)



# ── § 5.8 · --backtest: the integration backtest (final phase §5) ──────────
# B-7f/C-4 conventions live HERE (preregistration §6): costs 10 bps/side
# baseline with 5/10/25/50 sensitivity, entries at the next trading
# window open, cash earns ZERO, no leverage. THE DECISIONS ARE THE ACTUAL
# M.E. CODE'S: either the recorded per-date harvests of real run_pipeline
# runs (ml_data/cache/dates/*.json — the same records the dataset build
# wrote), or, with --backtest-rerun, DIRECT run_pipeline calls through the
# same Namespace shape the dataset builder uses. There is NO second
# decision path: this section only CONSUMES decisions + CONFIG (EARNINGS_TP
# is read from CONFIG at run time and echoed — single source of truth).
# Hermetic: no sockets are opened on the cached path; the report JSON is
# written allow_nan=False (C-6: null, never NaN).

_BT_COSTS_BPS = (5.0, 10.0, 25.0, 50.0)   # prereg §6: 10 baseline + sensitivity
_BT_LOCKBOX_N = 6                         # prereg §3: last 6 month-ends
_BT_DATES_REQUIRED = 36                   # prereg §7 gate (1)
_BT_BOOT_SEED = 11                        # fixed: bootstrap CIs are reproducible
_BT_BOOT_N = 2000
_BT_WINDOW_TD = 63.0                      # the pilot label horizon (63 trading days)


def _bt_rerun_ns(as_of: str, sectors: str) -> argparse.Namespace:
    """--backtest-rerun: the SAME Namespace shape the dataset builder uses
    (ml_dataset.build_ns): standard mode, as-of pinned, funnel opened to
    every gated name, no table filter — so a fresh backtest decision comes
    from the very same run_pipeline the live plan calls."""
    argv = ["--sectors", sectors, "--as-of", as_of,
            "--mode", "standard", "--timeout", "3600"]
    ns2 = _apply_mode(build_parser().parse_args(argv))
    ns2.earnings_top = 10 ** 9
    ns2.quiet = True
    ns2.min_conviction = 0.0
    _validate_ns(ns2)
    return ns2


def _bt_harvest_live(out: RunOutput) -> dict:
    """RunOutput -> the SAME per-date record shape ml_data/cache/dates/
    *.json stores (names -> sector/action/conviction/q/e), built directly
    from the Decision + LayerSignal objects the pipeline just produced —
    no JSON round-trip, no second extractor."""
    names: dict[str, dict] = {}
    for dec in out.decisions:
        q = dec.layers.get("quality")
        e = dec.layers.get("earnings")
        names[dec.ticker] = {
            "sector": dec.sector, "action": dec.action,
            "conviction": dec.conviction,
            "q": {"score": (q.score if q is not None and q.status == "OK"
                            and q.score is not None else None)},
            "e": {"score": (e.score if e is not None and e.status == "OK"
                            and e.score is not None else None)},
        }
    return {"as_of": out.ctx.as_of, "names": names}


def _bt_rankdata(xs: list[float]) -> list[float]:
    """Ranks 1..n with average ties (pure stdlib — no numpy/scipy import
    at module scope)."""
    order = sorted(range(len(xs)), key=lambda i: (xs[i], i))
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _bt_spearman(xs: list[float], ys: list[float]) -> float | None:
    """Spearman rank correlation (the prereg's monthly cross-sectional
    rank IC). None when fewer than 3 pairs or a degenerate side."""
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    rx, ry = _bt_rankdata(xs), _bt_rankdata(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx)
                    * sum((b - my) ** 2 for b in ry))
    return num / den if den > 0 else None


def _bt_boot_ci(vals: list[float], seed: int = _BT_BOOT_SEED,
                n: int = _BT_BOOT_N) -> tuple[float | None, float | None]:
    """Pairs bootstrap over dates: the 95% CI for the mean of per-date
    values (overlap in the underlying labels is disclosed separately —
    this CI resamples dates, it does not de-correlate overlapping windows).
    F12 (v1.8.3): empty input is a LEGAL state (a rerun whose re-decisions
    produced no scoreable date). (nan, nan) previously reached the
    allow_nan=False dumps and killed the run with exit 70 ("Out of range
    float values are not JSON compliant"). None renders 'n/a (no scored
    dates)' and serialises as null — C-6's contract."""
    if not vals:
        return None, None
    rng = _bt_rng(seed)
    m = len(vals)
    means = []
    for _ in range(n):
        sample = [vals[rng() % m] for _ in range(m)]
        means.append(sum(sample) / len(sample))
    means.sort()
    lo = means[int(0.025 * len(means))]
    hi = means[min(len(means) - 1, int(0.975 * len(means)))]
    return lo, hi


def _bt_rng(seed: int):
    """A tiny xorshift PRNG with a fixed seed — stdlib-only, reproducible
    (identical across Python versions and platforms, unlike hash())."""
    state = (seed * 2654435761 + 12345) & 0xFFFFFFFF

    def _next() -> int:
        nonlocal state
        state ^= (state << 13) & 0xFFFFFFFF
        state ^= state >> 17
        state ^= (state << 5) & 0xFFFFFFFF
        return state

    return _next


def _bt_quintile_spread(conv: list[float], ret: list[float]
                         ) -> tuple[float | None, float | None]:
    """Top-minus-bottom conviction-quintile mean return spread; None when
    fewer than 5 names (quintiles undefined)."""
    if len(conv) < 5:
        return None, None
    order = sorted(range(len(conv)), key=lambda i: conv[i])
    q = len(order) // 5
    top = [ret[i] for i in order[-q:]]
    bot = [ret[i] for i in order[:q]]
    return (sum(top) / len(top) - sum(bot) / len(bot)), q


def _bt_fm(x: float | None, spec: str = ".3f") -> str:
    """Report formatting: finite floats get the spec, None/nan -> 'n/a'."""
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "n/a"
    return format(x, spec)


def _bt_ratio(x: float | None, why_none: str = "", low_power: str = "") -> str:
    """F7 (v1.8.3): one ratio cell — the number, or the honest null reason
    ('n/a (n_neg<3)' for degenerate Sortino/PF), plus the caller's
    independent-window suffix ('(low power, n=4)') so no ratio is ever
    quoted without its power disclosure."""
    s = _bt_fm(x)
    if x is None and why_none:
        s = f"n/a ({why_none})"
    return s + low_power


def _json_scrub(obj):
    """F12 (v1.8.3): NaN/inf -> None everywhere (C-6: null, never NaN),
    recursive — the last line of defence before every allow_nan=False
    dump (a metric computed on a degenerate/empty sample must never kill
    the report with exit 70)."""
    if isinstance(obj, dict):
        return {k: _json_scrub(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_scrub(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def _bt_series_metrics(rets: list[float]) -> dict[str, Any]:
    """The per-window series metrics on overlapping 63-td windows —
    overlap is NOT de-correlated; the effective independent window count
    is stated next to every metric by the caller.
    F7 (v1.8.3): Sortino is a DOWNSIDE-deviation ratio and profit factor
    a gross-up of losses — with fewer than 3 losing windows both
    degenerate (the shipped 12-date pilot: ONE -0.1% window produced
    Sortino 791.285, PF 1371.55). They report None (rendered
    'n/a (n_neg<3)') instead of an absurd number; the losing-window
    count rides along as the additive n_neg key so the caller prints it
    beside every ratio."""
    n = len(rets)
    mean = sum(rets) / n if n else float("nan")
    var = (sum((r - mean) ** 2 for r in rets) / (n - 1)) if n > 1 else 0.0
    sd = math.sqrt(var) if var > 0 else 0.0
    per_year = 252.0 / _BT_WINDOW_TD          # ~4 windows/year
    sharpe = (mean / sd * math.sqrt(per_year)) if sd > 0 else None
    negs = [r for r in rets if r < 0]
    downs = negs or [0.0]
    dd = math.sqrt(sum(d * d for d in downs) / n) if n else 0.0
    sortino = ((mean / dd * math.sqrt(per_year))
               if dd > 0 and len(negs) >= 3 else None)   # F7 guard
    cum, peak, mdd = 1.0, 1.0, 0.0
    peak_at, trough_i = 0, 0
    for i, r in enumerate(rets):
        cum *= (1.0 + r)
        if cum > peak:
            peak = cum
        dd_now = 1.0 - cum / peak
        if dd_now > mdd:
            mdd, peak_at, trough_i = dd_now, (i - 1 if i else 0), i
    pos = [r for r in rets if r > 0]
    pf = ((sum(pos) / abs(sum(negs)))
          if negs and sum(negs) != 0 and len(negs) >= 3 else None)  # F7
    return {"n_windows": n, "mean": mean, "sd": sd, "sharpe": sharpe,
            "sortino": sortino, "max_dd": mdd, "mdd_peak_i": peak_at,
            "mdd_trough_i": trough_i, "win_rate": (len(pos) / n if n else None),
            "profit_factor": pf, "ann_mean": mean * per_year,
            "n_neg": len(negs)}          # F7: printed beside every ratio


def _bt_verdict(gates: dict[str, Any]) -> str:
    """The prereg §7 wording, as ONE pure function: the verdict's FIRST
    line is exactly 'no edge demonstrated' unless EVERY gate passed."""
    if all(g.get("pass") for g in gates.values()):
        return "edge demonstrated (every preregistered gate passed)"
    return "no edge demonstrated"


def _bt_eval_date(record: dict) -> dict[str, Any]:
    """One date: consume the recorded decisions + the dataset labels."""
    names: dict[str, dict] = record.get("names") or {}
    labels: dict[str, float] = record["_labels"]
    conv = [(t, float(rec.get("conviction") or 0.0)) for t, rec in names.items()
            if t in labels]
    pairs_x = [c for _t, c in conv]
    pairs_y = [labels[t] for t, _c in conv]
    ic = _bt_spearman(pairs_x, pairs_y)
    longs = [t for t, rec in names.items()
             if rec.get("action") == "LONG" and t in labels]
    gross = (sum(labels[t] for t in longs) / len(longs)) if longs else None
    ew = (sum(pairs_y) / len(pairs_y)) if pairs_y else None
    spread, q_size = _bt_quintile_spread(pairs_x, pairs_y)
    med = sorted(pairs_y)[len(pairs_y) // 2] if pairs_y else None
    hit = (sum(1 for t in longs if labels[t] > med) / len(longs)) \
        if (longs and med is not None) else None
    # ablation rankings over the SAME recorded data (no re-decisions)
    def _rank_ic(key: str) -> float | None:
        vals = []
        for t, rec in names.items():
            if t not in labels:
                continue
            s = ((rec.get("q") or {}).get("score")
                 if key == "q" else (rec.get("e") or {}).get("score"))
            if isinstance(s, (int, float)) and s == s:
                vals.append((float(s), labels[t]))
        return _bt_spearman([v for v, _ in vals], [r for _, r in vals]) \
            if len(vals) >= 3 else None
    return {"n_elig": len(conv), "n_long": len(longs), "ic": ic,
            "long_gross": gross, "ew_gross": ew, "q_spread": spread,
            "q_size": q_size, "hit_vs_median": hit,
            "ic_q_only": _rank_ic("q"), "ic_e_only": _rank_ic("e"),
            "longs": sorted(longs),
            "regime": ((record.get("macro") or {}).get("regime_class") or "-")}


def run_backtest(ns: argparse.Namespace) -> int:
    """§5 integration backtest: evaluates the ACTUAL M.E. decisions at each
    recorded month-end against the dataset's forward labels, applies the
    preregistered execution conventions (next-open windows, 10 bps/side,
    cash zero, no leverage), and grades the prereg §7 gates. Honest by
    construction: missing benchmarks print 'SPY: NOT AVAILABLE'; any gate
    failure makes the verdict's first line 'no edge demonstrated'."""
    t0 = time.monotonic()
    here = Path(__file__).resolve().parent.parent  # project root (me/)
    ds_path = Path(str(getattr(ns, "backtest_dataset", "") or "")
                   or here / "ml_data" / "dataset_v1.npz")
    if not ds_path.exists():
        raise MasterError(
            f"--backtest: dataset {ds_path} not found — build one with "
            "python3 ml_dataset.py --dates 36 --sectors all", 2)
    try:
        import numpy as _np                              # dataset only
        z = _np.load(str(ds_path), allow_pickle=True)
    except Exception as e:
        raise MasterError(f"--backtest: dataset unreadable ({_exc(e)}) — "
                          "exit 4", 4)
    manifest: dict[str, Any] = {}
    mpath = ds_path.parent / "manifest.json"
    if mpath.exists():
        try:
            manifest = json.loads(mpath.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}
    # v1.8.0 (W6, R7): REFUSE a dataset whose manifest is SYNTHETIC or
    # lacks API provenance — the backtest's numbers feed prereg gates;
    # synthetic fixtures never produce verdicts.
    _prov = manifest.get("data_provenance") or {}
    _syn_ok = str(os.environ.get("MASTER_ALLOW_SYNTHETIC", "")).strip().lower() \
        in ("1", "true")
    if _syn_ok and manifest:
        # unit-test path (R7): synthetic fixtures are legal ONLY in
        # tests — the report says so, loudly, every time.
        manifest.setdefault("data_provenance",
                            {"class": "SYNTHETIC",
                             "note": "MASTER_ALLOW_SYNTHETIC=1 "
                                     "(unit-test fixtures only)"})
        _prov = manifest["data_provenance"]
    if not _syn_ok and not _prov.get("class"):
        raise MasterError(
            f"--backtest: REFUSED — dataset manifest lacks "
            "data_provenance (no API provenance) — rebuild with "
            "python3 ml_dataset.py (real engine fetches; the owner "
            "network run)", 2)
    if str(_prov.get("class", "")).upper() != "REAL-API":
        if _syn_ok:
            _SYNTHETIC_ALLOWED.append(_prov.get("class"))
        else:
            raise MasterError(
                f"--backtest: REFUSED — dataset data_provenance is "
                f"{_prov.get('class')!r} (synthetic fixtures are unit-test "
                "only; a verdict needs real API data — R7)", 2)
    rerun = bool(getattr(ns, "backtest_rerun", False))
    # v1.8.0 (W2): hoist the three npz members ONCE — NpzFile.__getitem__
    # re-reads (and re-decompresses) the member on EVERY subscript, so the
    # per-row `z["..."][i]` pattern re-parsed each member ~1,080 times
    # (cProfile: 3,170 __getitem__ calls, ~0.5 s on the shipped fixture).
    as_of_arr = z["as_of"]
    ret_arr = z["ret_63"]
    tick_arr = z["tickers"]
    dates = sorted({str(x) for x in as_of_arr})
    # v1.8.0 (W4): --bt-start/--bt-end evaluate a SUB-WINDOW of the
    # dataset, descriptive only (R19). Month-ends, start <= end, and the
    # window must contain >=1 dataset date — otherwise the owner builds
    # the longer history with ml_dataset.py (network, their machine).
    w_start = str(getattr(ns, "bt_start", "") or "")
    w_end = str(getattr(ns, "bt_end", "") or "")
    for _tag, _val in (("start", w_start), ("end", w_end)):
        if not _val:
            continue
        try:
            _ok = len(_val) == 10 and _val == month_end_floor(_val)
        except Exception:
            _ok = False
        if not _ok:
            raise MasterError(f"--bt-{_tag}: {_val!r} is not a month-end "
                              "(YYYY-MM-DD, last calendar day of the "
                              "month)", 2)
    if w_start and w_end and w_start > w_end:
        raise MasterError(f"--bt-start {w_start} is before --bt-end "
                          f"{w_end} — swap them", 2)
    _w_dates = [d for d in dates
                if (not w_start or d >= w_start)
                and (not w_end or d <= w_end)]
    if (w_start or w_end) and not _w_dates:
        raise MasterError(
            f"--bt-start/--bt-end: no dataset dates inside "
            f"{w_start or '...'}..{w_end or '...'} (this dataset spans "
            f"{dates[0]}..{dates[-1]}) — dates outside the dataset need "
            "python3 ml_dataset.py --start YYYY-MM-DD --end YYYY-MM-DD "
            "--freq monthly run by the OWNER (network; resumable; see "
            "OWNER_RUN.md)", 2)
    labels: dict[str, dict[str, float]] = {}
    for i in range(len(as_of_arr)):
        r = ret_arr[i]
        if r == r:                                       # NaN never a label
            labels.setdefault(str(as_of_arr[i]), {})[str(tick_arr[i])] = \
                float(r)
    n_lab = sum(len(v) for v in labels.values())
    if not n_lab:
        raise MasterError("--backtest: dataset carries zero usable "
                          "forward labels — exit 4 (NO-GO)", 4)

    records: dict[str, dict] = {}
    skipped: list[tuple[str, str]] = []
    sectors = str((manifest.get("build") or {}).get("sectors") or "tech")
    for d in dates:
        cpath = ds_path.parent / "cache" / "dates" / f"{d}.json"
        if cpath.exists() and not rerun:
            records[d] = json.loads(cpath.read_text(encoding="utf-8"))
            records[d]["_prov"] = "REAL-DERIVED (cached)"
        elif rerun:
            out = _master_run_pipeline(_bt_rerun_ns(d, sectors))
            if not out.decisions:
                skipped.append((d, f"rerun produced no decisions "
                                  f"(exit {out.exit_code})"))
                continue
            rec = _bt_harvest_live(out)
            rec["macro"] = {"regime_class":
                           (out.ctx.regime.regime_class
                            if out.ctx.regime is not None else "-")}
            records[d] = rec
            records[d]["_prov"] = "live rerun"
            _atomic_write_text(cpath, json.dumps(rec, default=str))
        else:
            skipped.append((d, f"no decision record cache/dates/{d}.json "
                              "(--backtest-rerun rebuilds via run_pipeline)"))
    if not records:
        raise MasterError(f"--backtest: no decision records for any of the "
                          f"{len(dates)} dates ({skipped[0][1]}) — exit 4", 4)

    ev = {}
    for d, rec in records.items():
        rec["_labels"] = labels.get(d, {})
        ev[d] = _bt_eval_date(rec)

    # F6 (v1.8.3): the opt-in macro ablation reads ONLY the already-loaded
    # recorded rows (action, conviction, macro_tilt) — no re-decisions, no
    # network, no engine calls, nothing written. It prints its own report
    # and returns before the preregistered evaluation.
    ablate = str(getattr(ns, "bt_ablate", "") or "")
    if ablate:
        return _bt_ablate_report(records, labels, ablate)

    # ── execution: equal-weight LONG book, next-open windows, costs ──────
    prev: set[str] = set()
    rows, gross_series, turn_series = [], [], []
    for d in sorted(ev):
        e = ev[d]
        new = set(e["longs"])
        w_new = (1.0 / len(new)) if new else 0.0
        w_old = (1.0 / len(prev)) if prev else 0.0
        buys = sum(w_new for _ in (new - prev)) if new else 0.0
        sells = sum(w_old for _ in (prev - new)) if prev else 1.0 if not new and prev else 0.0
        traded = buys + sells                        # notional fraction traded
        g = e["long_gross"] if e["long_gross"] is not None else 0.0
        gross_series.append(g)                       # cash dates earn zero
        turn_series.append(traded)
        rows.append({"date": d, "n_elig": e["n_elig"], "n_long": e["n_long"],
                     "ic": e["ic"], "long_gross": e["long_gross"],
                     "ew_gross": e["ew_gross"], "traded_frac": traded,
                     "regime": e["regime"]})
        prev = new
    ew_series = [r["ew_gross"] if r["ew_gross"] is not None else 0.0
                 for r in rows]
    cost_series = {c: [g - t * c / 10000.0 for g, t in
                       zip(gross_series, turn_series)]
                   for c in _BT_COSTS_BPS}
    ics = [e["ic"] for e in ev.values() if e["ic"] is not None]
    ic_lo, ic_hi = _bt_boot_ci(ics)
    ew_metrics = _bt_series_metrics(ew_series)
    net_metrics = {c: _bt_series_metrics(s) for c, s in cost_series.items()}
    spread_vals = [e["q_spread"] for e in ev.values()
                   if e["q_spread"] is not None]
    hits = [e["hit_vs_median"] for e in ev.values()
            if e["hit_vs_median"] is not None]
    runs: list[int] = []
    streak: dict[str, int] = {}
    for d in sorted(ev):
        cur = set(ev[d]["longs"])
        for t in list(streak):
            if t not in cur:
                runs.append(streak.pop(t))
        for t in cur:
            streak[t] = streak.get(t, 0) + 1
    runs.extend(streak.values())
    avg_hold = (sum(runs) / len(runs)) if runs else None
    cash_dates = sum(1 for r in rows if r["n_long"] == 0)

    # ── groups + lockbox (prereg §3: last 6 month-ends, evaluated once) ──
    by_year: dict[str, list[int]] = {}
    by_regime: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        by_year.setdefault(r["date"][:4], []).append(i)
        by_regime.setdefault(r["regime"], []).append(i)
    lock_idx = list(range(max(0, len(rows) - _BT_LOCKBOX_N), len(rows)))
    lock_ics = [rows[i]["ic"] for i in lock_idx if rows[i]["ic"] is not None]
    lock_net = [cost_series[10.0][i] for i in lock_idx]
    full_sign = (net_metrics[10.0]["mean"] >= 0)
    lock_sign = (sum(lock_net) / len(lock_net) if lock_net else float("nan")) >= 0
    n_indep = max(1, round(len(rows) * 21.0 / _BT_WINDOW_TD))
    # F7 (v1.8.3): the low-power suffix every ratio carries while the
    # independent-window count sits below 8 (the prereg's ~4 on the
    # 12-date pilot) — defined once, used by the gates AND the metrics.
    _lp = (f" (low power, n={n_indep})" if n_indep < 8 else "")

    # v1.8.0 (W5) + v1.8.1 (F1): SPY series via an owner-supplied file,
    # loaded BEFORE the gates so gate 3's SPY half can be computed from it.
    # The label windows are 63 trading days ~= 3 calendar months, so the
    # aligned SPY window return is close[t+3m]/close[t]-1 on month-ends. A
    # file whose source says SYNTHETIC is labelled and stays descriptive
    # (never a verdict, never gate evidence — R7); a REAL owner series
    # also answers prereg gate 3's SPY half (AMENDMENT 2, 2026-11-19).
    spy_path = str(getattr(ns, "bt_spy", "") or "")
    spy_note, spy_mean, spy_n, spy_excess, spy_synthetic = None, None, 0, None, False
    _spy_gate: dict | None = None
    if spy_path:
        try:
            _sj = json.loads(Path(spy_path).read_text(encoding="utf-8"))
            _sc = {str(k): float(v) for k, v in
                   (_sj.get("monthly_close") or {}).items()}
            _src = str(_sj.get("source") or "")
            spy_synthetic = "SYNTHETIC" in _src.upper()
            _keys = sorted(_sc)
            _kidx = {k: i for i, k in enumerate(_keys)}
            _rets = []
            for r in rows:
                i = _kidx.get(r["date"])
                if i is None or i + 3 >= len(_keys):
                    continue
                _rets.append(_sc[_keys[i + 3]] / _sc[_keys[i]] - 1.0)
            if _rets:
                spy_mean = sum(_rets) / len(_rets)
                spy_n = len(_rets)
                _lmean = net_metrics.get(10.0, {}).get("mean")
                spy_excess = ((_lmean - spy_mean)
                              if _lmean is not None else None)
            # F1: gate 3's SPY half — Sharpe/MDD of the SPY monthly
            # returns restricted to the dataset's rebalance dates.
            _spy_gate = _spy_gate_metrics(_sc, [r["date"] for r in rows])
            _spy_gate["synthetic"] = spy_synthetic
            spy_note = f"owner series {Path(spy_path).name} "
            if spy_synthetic:
                spy_note += ("(SYNTHETIC — alignment math only, never a "
                             "verdict, never gate evidence)")
            else:
                spy_note += ("(REAL owner series; gate 3's SPY half "
                             "answerable per AMENDMENT 2)")
        except MasterError:
            raise
        except Exception as e:
            raise MasterError(f"--bt-spy: unreadable file {spy_path} "
                              f"({_exc(e)}) — scripts/owner_fetch_spy.py "
                              "writes the expected "
                              '{"source", "monthly_close"} shape', 2)
    # ── gates (prereg §7; Q5 = YES only if ALL hold) ─────────────────────
    ic_lb = ic_lo if ics else float("nan")
    sharpe10 = net_metrics[10.0]["sharpe"]
    ew_sharpe = ew_metrics["sharpe"]
    mdd10 = net_metrics[10.0]["max_dd"]
    ew_mdd = ew_metrics["max_dd"]
    beats_ew = ((sharpe10 is not None and ew_sharpe is not None
                 and sharpe10 > ew_sharpe
                 and mdd10 is not None and ew_mdd is not None
                 and mdd10 <= ew_mdd))
    pos_groups = 0
    for idx in list(by_year.values()) + list(by_regime.values()):
        m = sum(cost_series[10.0][i] for i in idx) / len(idx)
        if (m - sum(ew_series[i] for i in idx) / len(idx)) > 0:
            pos_groups += 1
    # v1.8.1 (F1, prereg AMENDMENT 2, evidence/preregistration.md
    # 2026-11-19 — written BEFORE this code ran): the SPY half of gate 3 is
    # computed from a REAL --bt-spy series (net Sharpe @10bps vs SPY Sharpe
    # over the SAME month-end dates; net MDD <= SPY MDD + 1e-9); a
    # SYNTHETIC-labelled file and files overlapping <12 dataset dates keep
    # the UNANSWERABLE label, and no series keeps today's exact text.
    _spy_half = _gate3_spy_half(
        spy_sharpe=_spy_gate.get("sharpe") if _spy_gate else None,
        spy_mdd=_spy_gate.get("mdd") if _spy_gate else None,
        overlap=_spy_gate.get("overlap", 0) if _spy_gate else 0,
        synthetic=bool(_spy_gate.get("synthetic", False)) if _spy_gate else False,
        net_sharpe=sharpe10, net_mdd=mdd10)
    gates = {
        "1_rebalances_ge_36": {
            "pass": len(rows) >= _BT_DATES_REQUIRED,
            "detail": f"{len(rows)}/{_BT_DATES_REQUIRED} month-end rebalances"},
        "2_ic_lower_bound_positive": {
            "pass": bool(ics) and ic_lb > 0,
            "detail": (f"mean rank IC {sum(ics)/len(ics):+.4f} · "
                       f"95% CI [{ic_lo:+.4f}, {ic_hi:+.4f}] · "
                       f"positive {sum(1 for x in ics if x > 0)}/{len(ics)}"
                       if ics else "no computable IC")},
        "3_beats_ew_and_spy": {
            "pass": bool(beats_ew) and bool(_spy_half["pass"]),
            "detail": (f"vs EW: Sharpe "
                       f"{_bt_fm(sharpe10)} vs {_bt_fm(ew_sharpe)}, MDD {mdd10:.3f} vs "
                       f"{ew_mdd:.3f} — "
                       + ("beats EW; " if beats_ew else "does not beat EW; ")
                       + _spy_half["detail"])},
        "4_excess_3_groups": {
            "pass": pos_groups >= 3,
            "detail": f"positive net excess vs EW in {pos_groups} "
                      f"distinct year/regime groups "
                      f"({len(by_year)} years, {len(by_regime)} regimes)"},
        "5_survives_25bps": {
            "pass": bool(net_metrics[25.0]["mean"] > 0),
            "detail": (f"net mean @25bps {net_metrics[25.0]['mean']:+.4f} "
                       f"· Sharpe {_bt_ratio(net_metrics[25.0]['sharpe'], low_power=_lp)}")},
        "6_lockbox_consistent": {
            "pass": bool(lock_sign == full_sign),
            "detail": (f"last {len(lock_idx)} dates: net sign "
                       f"{'+' if lock_sign else '-'} vs full "
                       f"{'+' if full_sign else '-'} · IC "
                       f"{sum(lock_ics)/len(lock_ics):+.4f}" if lock_ics
                       else "lockbox empty")},
    }
    verdict = _bt_verdict(gates)

    # ── the report ───────────────────────────────────────────────────────
    m_hash = _bt_config_hash(CONFIG)
    b_hash = str(manifest.get("config_hash_master") or "unknown")
    tp = CONFIG["EARNINGS_TP"]
    lines = []
    lines.append("M.E. integration backtest — preregistration-locked "
                 "evaluation (final phase §5)")
    lines.append("=" * 72)
    lines.append(f"verdict    {verdict}")
    q5 = "YES" if verdict.startswith("edge") else "PARTLY"
    lines.append(f"           Q5 = {q5} — real out-of-sample decisions and "
                 "labels, but the prereg full universe was never built "
                 "(B-9 carried; owner command below) and SPY is unavailable")
    if _SYNTHETIC_ALLOWED:
        lines.append("*** SYNTHETIC DATASET ALLOWED (MASTER_ALLOW_SYNTHETIC"
                     " — unit-test fixture path; NEVER real evidence, never "
                     "a verdict) ***")
    lines.append("evidence   FIXTURE-CLASS: the shipped 12-date tech-pool "
                 "pilot (90 names, 1080 rows) — the prereg's smoke "
                 "fixture, never the full-universe verdict set")
    lines.append(f"dates      {len(rows)} month-ends {rows[0]['date']}.."
                 f"{rows[-1]['date']} · 63-td overlapping label windows · "
                 f"~{n_indep} independent label windows (stated per prereg "
                 "§6: every metric above carries this n)")
    provs = sorted({r["_prov"] for r in records.values()})
    if rerun:
        lines.append("decisions  live rerun via DIRECT run_pipeline calls "
                     "(the same function the live plan runs)")
    else:
        lines.append("decisions  " + " + ".join(provs)
                     + " — the recorded harvests of REAL run_pipeline runs")
    lines.append(f"config     build-time CONFIG hash {b_hash} · "
                 f"current {m_hash} — the additions are exactly the "
                 "disclosed evidence/rules_changes.md items (phase-8 "
                 "diff discipline); no recorded decision was re-derived · "
                 "hash recipe v1.8.0 (D-18-002): sets canonicalised — "
                 "pre-v1.8.0 build hashes are not comparable")
    lines.append(f"           EARNINGS_TP {tp:g} (CONFIG, single source — "
                 "engine + backtest read the same key) · RULESET "
                 f"{CONFIG['RULESET']} · costs 10 bps/side baseline "
                 "(5/10/25/50 sensitivity) · next-open windows · cash "
                 "earns zero · no leverage")
    lines.append("ML         M.E. with ML: not run — no validated head "
                 "(every shipped head is SHADOW, uncalibrated/insufficient)")
    lines.append("           M.E. without ML == the recorded strategy — "
                 "identical while all heads are SHADOW, stated as such")
    if not spy_path:
        # F1: with no --bt-spy file the UNANSWERABLE label stays EXACTLY
        # this (the shipped evidence re-check must reproduce it byte for
        # byte); with a file the SPY block below prints the real numbers.
        lines.append("SPY        SPY: NOT AVAILABLE — no benchmark series in "
                     "the pilot (gate 3's SPY half unanswerable; never faked)")
    lines.append("")
    lines.append("per-date (gross 63-td window returns; entry at the "
                 "next window open — the label window starts the trading "
                 "day after as-of):")
    lines.append("date        elig long      ic     long_gross  ew_gross"
                 "  traded  regime")
    for r in rows:
        lines.append(f"{r['date']}  {r['n_elig']:4d} {r['n_long']:4d}  "
                     f"{('%+.4f' % r['ic']) if r['ic'] is not None else '     n/a'}"
                     f"  {('%+.4f' % r['long_gross']) if r['long_gross'] is not None else '     n/a'}"
                     f"   {('%+.4f' % r['ew_gross']) if r['ew_gross'] is not None else '     n/a'}"
                     f"  {r['traded_frac']:.3f}  {r['regime']}")
    lines.append("")
    m10 = net_metrics[10.0]
    lines.append("metrics (net of the 10 bps baseline, gross beside; "
                 "overlapping windows, ~%d independent):" % n_indep)
    lines.append(f"  rank IC         mean {sum(ics)/len(ics):+.4f} · "
                 f"95% CI [{ic_lo:+.4f}, {ic_hi:+.4f}] · "
                 f"{sum(1 for x in ics if x > 0)}/{len(ics)} months positive"
                 if ics else "  rank IC         n/a (no scored dates)")
    lines.append(f"  LONG basket     gross mean {sum(gross_series)/len(gross_series):+.4f}/window · "
                 f"net mean {m10['mean']:+.4f} · "
                 f"Sharpe {_bt_ratio(m10['sharpe'], low_power=_lp)} · "
                 f"Sortino {_bt_ratio(m10['sortino'], 'n_neg<3', _lp)} · "
                 f"n_neg {m10['n_neg']}")
    lines.append(f"  EW universe     mean {ew_metrics['mean']:+.4f} · "
                 f"Sharpe {_bt_ratio(ew_sharpe, low_power=_lp)} · MDD {ew_metrics['max_dd']:.3f} "
                 f"(LONG: {m10['max_dd']:.3f})")
    lines.append(f"  max drawdown    {m10['max_dd']:.3f} (window "
                 f"{m10['mdd_peak_i'] + 1} -> {m10['mdd_trough_i'] + 1}) · "
                 f"win rate {m10['win_rate']:.3f} · profit factor "
                 f"{_bt_ratio(m10['profit_factor'], 'n_neg<3', _lp)}")
    # v1.8.0 (W4): the descriptive sub-window block (R19) — printed
    # BESIDE the full-span numbers above; never a verdict, never a gate.
    w_net_mean = None
    if w_start or w_end:
        _wi = [i for i, r in enumerate(rows)
               if (not w_start or r["date"] >= w_start)
               and (not w_end or r["date"] <= w_end)]
        _wg = [gross_series[i] for i in _wi]
        _wt = [turn_series[i] for i in _wi]
        _wn = [g - t * 10.0 / 10000.0 for g, t in zip(_wg, _wt)]
        _wm = _bt_series_metrics(_wn) if _wn else {}
        w_net_mean = _wm.get("mean")
        lines.append(f"  window {w_start or dates[0]}..{w_end or dates[-1]} "
                     "(descriptive sub-window, R19 — never a verdict; ~"
                     f"{max(1, round(len(_wi) * 21.0 / _BT_WINDOW_TD))} "
                     "independent):")
        lines.append(f"    dates {len(_wi)} · gross mean "
                     f"{(sum(_wg) / len(_wg)) if _wg else 0.0:+.4f}/window · "
                     f"net mean "
                     f"{(w_net_mean if w_net_mean is not None else 0.0):+.4f}"
                     f" · Sharpe {_bt_fm(_wm.get('sharpe'))} · win rate "
                     f"{_wm.get('win_rate', 0.0):.3f}")
        lines.append("    (sub-windows are regime slices — reported as "
                     "description only, never as evidence of skill)")
    # v1.8.0 (W5): opt-in drawdown circuit-breaker what-if (--bt-breaker):
    # walk the 10-bps net equity curve; when the drawdown from the
    # running peak crosses RISK_DD_BREAKER_DD the book goes to cash for
    # RISK_DD_BREAKER_COOLDOWN_W windows, then re-enters. Descriptive
    # what-if ONLY — the preregistered default backtest is unchanged.
    breaker_on = bool(getattr(ns, "bt_breaker", False))
    b_fired, b_net_mean, b_windows = 0, None, []
    if breaker_on:
        _n10 = cost_series[10.0]
        _eq, _peak = 1.0, 1.0
        _cool = 0
        _cool_w = int(CONFIG["RISK_DD_BREAKER_COOLDOWN_W"])
        _thr = float(CONFIG["RISK_DD_BREAKER_DD"])
        _kept = []
        for d, v in zip([r["date"] for r in rows], _n10):
            _eq *= (1.0 + v)
            _peak = max(_peak, _eq)
            if _cool > 0:
                _cool -= 1
                _kept.append((d, 0.0))
                continue
            if (_peak - _eq) / _peak > _thr:
                b_fired += 1
                _cool = _cool_w
                _kept.append((d, 0.0))
                b_windows.append(d)
                continue
            _kept.append((d, v))
        _bk = [v for _d, v in _kept]
        b_net_mean = (sum(_bk) / len(_bk)) if _bk else None
    # v1.8.0 (W5): stress report on windows PRESENT in this dataset —
    # the defensive stretch, the worst rolling 3-window net stretch and
    # the worst single window (all descriptive, R19).
    _n10r = cost_series[10.0]
    _def_ranges, _cur = [], None
    for r in rows:
        if r["regime"] == "defensive" or r["n_long"] == 0:
            _cur = (r["date"], r["date"]) if _cur is None else (
                _cur[0], r["date"])
        else:
            if _cur is not None:
                _def_ranges.append(_cur)
            _cur = None
    if _cur is not None:
        _def_ranges.append(_cur)
    _w3 = min(((i, sum(_n10r[i:i + 3]) / len(_n10r[i:i + 3]))
               for i in range(max(1, len(_n10r) - 2))), default=None,
              key=lambda x: x[1])
    _w1 = min(((i, v) for i, v in enumerate(_n10r)), default=None,
              key=lambda x: x[1])
    lines.append("stress windows present in this dataset (descriptive, "
                 "R19 — what the data contains, never a claim about "
                 "regimes it does not):")
    if _def_ranges:
        lines.append("  defensive/cash stretch  "
                     + " · ".join(f"{a}..{b}" for a, b in _def_ranges))
    else:
        lines.append("  defensive/cash stretch  none present")
    if _w3:
        lines.append(f"  worst rolling 3-window net {_w3[1]:+.4f} "
                     f"({rows[_w3[0]]['date']}.."
                     f"{rows[min(_w3[0] + 2, len(rows) - 1)]['date']}) · "
                     f"worst single window {_w1[1]:+.4f} "
                     f"({rows[_w1[0]]['date']})")
    if spy_path:
        _lab = "SPY        "
        if spy_mean is not None:
            lines.append(
                f"{_lab} {spy_note} · mean {spy_mean:+.4f}/window over "
                f"{spy_n} aligned 3-month windows · "
                + (f"LONG-minus-SPY excess "
                   f"{(spy_excess if spy_excess is not None else 0.0):+.4f}"
                   "/window (descriptive)"
                   if spy_excess is not None else "excess n/a"))
        else:
            lines.append(f"{_lab} {spy_note} · no aligned windows "
                         "(the series must span the as-of month-ends + 3)")
    if breaker_on:
        lines.append(
            f"circuit breaker (--bt-breaker what-if; "
            f"RISK_DD_BREAKER_DD {_thr:.0%} · cooldown "
            f"{_cool_w} windows) — breaker "
            + (f"fired on {b_fired} window(s): {', '.join(b_windows)}; "
               f"what-if net mean {b_net_mean:+.4f}/window vs baseline "
               f"{net_metrics.get(10.0, {}).get('mean'):+.4f}"
               if b_fired else
               "never fired on this curve (threshold not crossed — "
               "the control is live and bound-checked, it simply did "
               "not bind on this data)"))
    if spread_vals:
        lines.append(f"  top-bottom Q    mean spread {sum(spread_vals)/len(spread_vals):+.4f}"
                     f"/window (quintile size {ev[rows[0]['date']]['q_size']})")
    if hits:
        lines.append(f"  hit vs median   {sum(hits)/len(hits):.3f} "
                     "(LONG names beating the universe median)")
    lines.append(f"  turnover        mean traded notional "
                 f"{sum(turn_series)/len(turn_series):.3f}/window · "
                 f"avg holding {_bt_fm(avg_hold)} consecutive month-ends · "
                 f"cash dates {cash_dates}/{len(rows)} (avg cash "
                 f"{100.0 * cash_dates / len(rows):.0f}%)")
    lines.append("  sector exposure 100% tech every date (the pilot's "
                 "universe — the prereg's cross-sector breadth was never built)")
    lines.append("costs sensitivity (bps -> net mean/window, Sharpe):")
    for c in _BT_COSTS_BPS:
        mc = net_metrics[c]
        star = " (baseline)" if c == 10.0 else ""
        lines.append(f"  {c:5.0f} bps{star:12s} -> {mc['mean']:+.4f} · "
                     f"Sharpe {_bt_ratio(mc['sharpe'], low_power=_lp)}")
    lines.append("groups (net@10bps vs EW excess):")
    for y, idx in sorted(by_year.items()):
        m = sum(cost_series[10.0][i] for i in idx) / len(idx)
        ex = m - sum(ew_series[i] for i in idx) / len(idx)
        lines.append(f"  {y}: {len(idx)} dates · net {m:+.4f} · excess {ex:+.4f}")
    for rg, idx in sorted(by_regime.items()):
        m = sum(cost_series[10.0][i] for i in idx) / len(idx)
        ex = m - sum(ew_series[i] for i in idx) / len(idx)
        lines.append(f"  regime {rg}: {len(idx)} dates · net {m:+.4f} · "
                     f"excess {ex:+.4f}")
    if lock_ics:
        _uninf = (" — uninformative (6 dates, one sign)"
                  if len(lock_idx) == _BT_LOCKBOX_N else "")
        lines.append(f"lockbox (last {len(lock_idx)} month-ends, evaluated "
                     f"once, no tuning follows): net sign "
                     f"{'+' if lock_sign else '-'} (full period "
                     f"{'+' if full_sign else '-'}) · mean IC "
                     f"{sum(lock_ics)/len(lock_ics):+.4f} — "
                     + ("consistent" if lock_sign == full_sign
                        else "INCONSISTENT") + _uninf)
    lines.append("ablations (same recorded data, re-ranked — no "
                 "re-decisions):")
    iq = [e["ic_q_only"] for e in ev.values() if e["ic_q_only"] is not None]
    ie = [e["ic_e_only"] for e in ev.values() if e["ic_e_only"] is not None]
    lines.append(f"  quality-only IC  {sum(iq)/len(iq):+.4f}" if iq
                 else "  quality-only IC  n/a")
    lines.append(f"  earnings-only IC {sum(ie)/len(ie):+.4f}" if ie
                 else "  earnings-only IC n/a")
    lines.append("  v2 missing-E vs legacy  NOT RUN — re-deciding dates "
                 "needs the engine caches (gone; REAL-DERIVED records "
                 "only) — owner: python3 master.py --backtest --backtest-rerun "
                 "--ruleset v2")
    lines.append("  vol_target sizing        NOT RUN — the pilot's "
                 "records carry no sizer weights — owner: "
                 "python3 master.py --backtest --backtest-rerun --sizing vol_target")
    lines.append("  rounded vs unrounded door NOT RUN — records store the "
                 "rounded display conviction only — owner: "
                 "python3 master.py --backtest --backtest-rerun --ruleset v2")
    lines.append("gates (prereg §7 — Q5 = YES only if ALL pass):")
    for k in sorted(gates):
        g = gates[k]
        st = "PASS" if g["pass"] else "FAIL"
        lines.append(f"  {k:28s} {st}  {g['detail']}")
    lines.append(f"variants tried in this run: 1 (the preregistered "
                 "rule-based M.E.; ablations above are disclosures, not "
                 "tuned variants) · seeds fixed "
                 f"(bootstrap {_BT_BOOT_SEED}/{_BT_BOOT_N})")
    if skipped:
        lines.append(f"skipped dates: {', '.join(d for d, _r in skipped)} "
                     f"— W_BT_DATE_SKIPPED ({len(skipped)}/{len(dates)})")
    for _d, why in skipped[:3]:
        lines.append(f"  why: {why}")
    report = "\n".join(lines)

    out_json = {"verdict": verdict, "q5": q5, "dates": rows,
                "metrics": {"net": {str(c): net_metrics[c]
                                    for c in _BT_COSTS_BPS},
                            "ew": ew_metrics, "ic_mean":
                            (sum(ics) / len(ics)) if ics else None,
                            "ic_ci": [ic_lo, ic_hi],
                            "avg_holding_dates": avg_hold,
                            "cash_dates": cash_dates},
                "gates": gates, "config": {"earnings_tp": tp,
                                           "ruleset": CONFIG["RULESET"],
                                           "build_hash": b_hash,
                                           "current_hash": m_hash},
                "provenance": provs, "skipped": skipped,
                "dataset": str(ds_path),
                "prereg": "evidence/preregistration.md"}
    jpath = Path(str(getattr(ns, "backtest_out", "") or "")
                 or here / "evidence" / "phase6_backtest.json")
    _atomic_write_text(jpath, json.dumps(_json_scrub(out_json), indent=1,
                                         default=str, allow_nan=False))
    rpath = Path(str(jpath)[:-5] + "_report.md") \
        if str(jpath).endswith(".json") else jpath.with_suffix(".report.md")
    _atomic_write_text(rpath, report + f"\nwritten {jpath.name} + "
                        f"{rpath.name} in {time.monotonic() - t0:.1f}s\n")
    sys.stdout.write(report + "\n")
    # v1.8.0 (W4): the runlog — EVERY backtest run appends one JSON line
    # (span, window, full-span and window means, hashes); append-only.
    import datetime as _dt
    _m10 = net_metrics.get(10.0) or {}
    _rlog = {"ts": _dt.datetime.now(_dt.timezone.utc).isoformat(
                 timespec="seconds"),
             "dates": [r["date"] for r in rows],
             "window": ({"start": w_start, "end": w_end}
                        if (w_start or w_end) else None),
             "full_net_mean": _m10.get("mean"),
             "full_gross_mean": (sum(gross_series) / len(gross_series))
                                if gross_series else None,
             "window_net_mean": w_net_mean,
             "breaker": bool(getattr(ns, "bt_breaker", False)),
             "breaker_fired": b_fired,
             "spy": (str(getattr(ns, "bt_spy", "") or "") or None),
             "spy_synthetic": spy_synthetic if spy_path else None,
             "config_hash": m_hash,
             "dataset": str(ds_path)}
    _rpath = here / "evidence" / "backtest_runlog.jsonl"
    _atomic_write_text(_rpath,
                       (_rpath.read_text(encoding="utf-8")
                        if _rpath.exists() else "")
                       + json.dumps(_json_scrub(_rlog), default=str,
                                    allow_nan=False) + "\n")
    sys.stdout.write(f"backtest: report {rpath} · json {jpath} · "
                      f"{time.monotonic() - t0:.1f}s\n")
    warn = []
    if skipped:
        warn.append("W_BT_DATE_SKIPPED")
    if len(records) < _BT_DATES_REQUIRED or "tech" in sectors:
        warn.append("W_BT_FIXTURE_ONLY")
    for w in warn:
        entry = _code_registry().get(w) or {}
        sys.stderr.write(f"backtest: {w} — {entry.get('what', '')} "
                         f"fix: {entry.get('fix', '')}\n")
    return 0


def _bt_ablate_report(records: dict, labels: dict, mode: str) -> int:
    """F6 (v1.8.3): the opt-in --bt-ablate what-if over RECORDED rows only
    (ml_data/cache/dates/*.json already loaded by run_backtest; no
    re-decisions, no network, no engine calls, nothing written).

    Modes:
      macro_cap  — a defensive-regime demotion (tilt<0, conviction >=
                   ACTION_LONG_AT, recorded action WATCH) is counted as
                   LONG: the cap, not the tilt multiplier, kept it out of
                   the book (master.py fuse_candidate).
      macro_mult — conviction is rescaled by 1/(1 + MACRO_TILT_GAIN*tilt)
                   (undoing the tilt's conviction multiplier) and the
                   action re-derived from the ACTION_LONG_AT door.
      macro_all  — both.

    Damp is NOT stored in the records; every shipped record carries
    layers.macro == 'OK' (degraded_for_damp False -> damp 1.0), so the
    report PRINTS that assumption beside every number. Observation count
    n and the episode disclosure are mandatory; nothing here is validated
    evidence — the shipped pilot contains ONE defensive episode."""
    long_at = float(CONFIG["ACTION_LONG_AT"])
    gain = float(CONFIG["MACRO_TILT_GAIN"])
    n_cap = n_mult = 0
    cap_dates: list[str] = []
    lines: list[str] = []
    lines.append(f"M.E. backtest ablation (--bt-ablate {mode}) — a WHAT-IF "
                 "over the RECORDED decisions, never a verdict")
    lines.append("=" * 72)
    lines.append("assumption: damp = 1.0 (every shipped record carries "
                 "layers.macro == 'OK' -> degraded_for_damp False); the "
                 "records do not store damp")
    lines.append("assumption: gross windows, no costs (the recorded rows "
                 "carry no sizer weights; costs are a rerun question)")
    lines.append("")
    lines.append("date        regime     n  long as-rec -> ablated   "
                 "excess vs EW (as-rec / ablated)   flipped rows")
    tot = {"n": 0, "asrec": [], "ablate": []}
    for d in sorted(records):
        rec = records[d]
        lab = labels.get(d, {})
        regime = str((rec.get("macro") or {}).get("regime_class") or "-")
        rows = []
        day_cap = 0
        for t, r in sorted((rec.get("names") or {}).items()):
            if t not in lab:
                continue
            act = str(r.get("action") or "")
            conv = float(r.get("conviction") or 0.0)
            tilt = r.get("macro_tilt")
            tilt = float(tilt) if isinstance(tilt, (int, float)) else None
            a_act, a_conv = act, conv
            if mode in ("macro_cap", "macro_all") and tilt is not None \
                    and tilt < 0 and conv >= long_at and act == "WATCH":
                a_act = "LONG"            # the cap was the only demotion
                n_cap += 1
                day_cap += 1
            if mode in ("macro_mult", "macro_all") and tilt:
                a_conv = conv / (1.0 + gain * tilt)   # undo the tilt mult
                if a_act in ("LONG", "WATCH"):        # re-derive the action
                    a_act = "LONG" if a_conv >= long_at else a_act
                n_mult += 1
            rows.append((t, act, conv, a_act, a_conv, lab[t]))
        if day_cap:
            cap_dates.append(d)
        ew = (sum(x[5] for x in rows) / len(rows)) if rows else None
        asrec = (sum(x[5] for x in rows if x[1] == "LONG")
                 / max(1, sum(1 for x in rows if x[1] == "LONG"))) \
            if any(x[1] == "LONG" for x in rows) else None
        abl = (sum(x[5] for x in rows if x[3] == "LONG")
               / max(1, sum(1 for x in rows if x[3] == "LONG"))) \
            if any(x[3] == "LONG" for x in rows) else None
        if rows and ew is not None:
            tot["n"] += len(rows)
            tot["asrec"].append((asrec - ew) if asrec is not None else 0.0)
            tot["ablate"].append((abl - ew) if abl is not None else 0.0)
        ex_a = f"{(asrec - ew):+.4f}" if (asrec is not None
                                          and ew is not None) else "n/a"
        ex_b = f"{(abl - ew):+.4f}" if (abl is not None
                                        and ew is not None) else "n/a"
        lines.append(f"{d}  {regime:<9s} {len(rows):3d}  "
                     f"{sum(1 for x in rows if x[1] == 'LONG'):4d} -> "
                     f"{sum(1 for x in rows if x[3] == 'LONG'):4d}      "
                     f"{ex_a:>8s} / {ex_b:>8s}          {day_cap}")
    agg_a = (sum(tot["asrec"]) / len(tot["asrec"])) if tot["asrec"] else None
    agg_b = (sum(tot["ablate"]) / len(tot["ablate"])) if tot["ablate"] else None
    lines.append("")
    lines.append(f"aggregate excess vs EW (mean per date): as-recorded "
                 f"{(f'{agg_a:+.4f}' if agg_a is not None else 'n/a')} · "
                 f"ablated {(f'{agg_b:+.4f}' if agg_b is not None else 'n/a')} "
                 f"· delta "
                 f"{(f'{(agg_b - agg_a):+.4f}' if (agg_a is not None and agg_b is not None) else 'n/a')}")
    months = sorted({d[:7] for d in cap_dates})
    span = (f"{cap_dates[0]}..{cap_dates[-1]}" if cap_dates else "none")
    lines.append(f"macro_cap flipped {n_cap} WATCH row(s) to LONG; "
                 f"macro_mult rescaled {n_mult} tilted row(s)")
    lines.append(f"episode disclosure: {len(months)} month(s) with demoted "
                 f"rows ({', '.join(months) or 'none'}; span {span}) — "
                 "NOT validated evidence: the shipped pilot holds ONE "
                 "defensive episode (2025-10-31..2026-01-31), 12 "
                 "month-end dates, tech-only universe")
    lines.append("nothing here changes a gate, a verdict or a recorded "
                 "decision; the preregistered backtest is `python3 "
                 "master.py --backtest` without --bt-ablate")
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


def _spy_gate_metrics(closes: dict, dates: list) -> dict:
    """F1 (AMENDMENT 2): SPY monthly Sharpe/MDD over the dataset's
    rebalance dates. Returns {"n": aligned monthly returns, "overlap":
    dataset dates present in the file, "sharpe": monthly mean/std*sqrt(12)
    (None when degenerate), "mdd": compounded max drawdown, "answerable":
    overlap >= 12}. Pure function — the unit tests exercise it with
    SYNTHETIC-labelled series (math wiring only, never real evidence)."""
    have = [d for d in dates if str(d) in closes]
    rets = []
    for a, b in zip(have, have[1:]):
        ca, cb = closes[str(a)], closes[str(b)]
        if ca and cb:
            rets.append(cb / ca - 1.0)
    overlap = len(have)
    if overlap < 12 or len(rets) < 11:
        return {"n": len(rets), "overlap": overlap, "sharpe": None,
                "mdd": None, "answerable": False}
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    sharpe = (mean / (var ** 0.5) * (12.0 ** 0.5)) if var > 0 else None
    eq, peak, mdd = 1.0, 1.0, 0.0
    for r in rets:
        eq *= (1.0 + r)
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak if peak > 0 else 0.0)
    return {"n": len(rets), "overlap": overlap, "sharpe": sharpe,
            "mdd": mdd, "answerable": True}


def _gate3_spy_half(*, spy_sharpe, spy_mdd, overlap, synthetic,
                    net_sharpe, net_mdd) -> dict:
    """F1 (AMENDMENT 2): the SPY half of gate 3 as {"pass", "detail"}.
    No series / SYNTHETIC series / <12 overlap -> UNANSWERABLE (pass
    False, the exact legacy label); a REAL series -> pass iff
    net Sharpe @10bps > SPY Sharpe over the same dates AND net MDD <=
    SPY MDD + 1e-9 (the 1-ulp tolerance the DD veto uses)."""
    if synthetic:
        return {"pass": False,
                "detail": ("SPY: NOT AVAILABLE (gate unanswerable — Q5 "
                           "capped; SYNTHETIC series are never gate "
                           "evidence)" )}
    if spy_sharpe is None or spy_mdd is None or overlap < 12:
        return {"pass": False,
                "detail": (f"SPY: NOT AVAILABLE (gate unanswerable — Q5 "
                           f"capped; only {int(overlap)} of the dataset's "
                           "dates in the file)" )}
    ok = bool(net_sharpe is not None and net_mdd is not None
              and net_sharpe > spy_sharpe
              and net_mdd <= spy_mdd + 1e-9)
    return {"pass": ok,
            "detail": (f"SPY: Sharpe {net_sharpe:.3f} vs {spy_sharpe:.3f} · "
                       f"MDD {net_mdd:.3f} vs {spy_mdd:.3f} over "
                       f"{int(overlap)} month-end dates"
                       + (" — beats SPY" if ok else " — does not beat SPY"))}


def _bt_config_hash(cfg: dict) -> str:
    """CONFIG identity hash, same recipe as ml_dataset's manifest field.

    v1.8.0 (D-18-002): renders through me.core._canonical_json (sets ->
    sorted lists). The pre-v1.8.0 recipe str()'ed frozensets, so the hash
    changed with PYTHONHASHSEED in every process; hashes from pre-v1.8.0
    builds are NOT comparable to this one."""
    import hashlib
    from me.core import _canonical_json
    return hashlib.sha256(_canonical_json(cfg).encode()).hexdigest()[:16]


def _master_run_pipeline(ns: "argparse.Namespace"):
    """Late-bound run_pipeline (master.py defines it AFTER this module is
    imported by it): resolving at call time keeps me/backtest acyclic and
    honours test monkeypatches on master.run_pipeline."""
    import master
    return master.run_pipeline(ns)

