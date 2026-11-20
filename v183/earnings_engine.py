"""
earnings_engine.py  (v3)
========================
Rates tickers by how often they deliver BIG earnings beats (EPS surprise >= 17% by default),
tests whether that rating would have made money (long ~90 days after earnings, exit early
on a profit target), and tells you what to hold right now. Free data (Yahoo / Finnhub).
Importing prints nothing; every function RETURNS objects, printing is opt-in via .show().

QUICK START
    from earnings_engine import analyze, report, EarningsEngine

    a = analyze(["MU", "NVDA", "AAPL", "MSFT", "AMD"])   # returns an Analysis, prints nothing
    a.show()                                              # prints the compact report
    a.scores        # DataFrame: score, rating, p_next_big, big beats, ...
    a.accuracy      # Series: walk-forward accuracy (incl. out-of-sample)
    a.trades        # DataFrame: every simulated trade
    a.trade_summary # Series: picked vs not-picked, edge, t-stat
    a.signals       # DataFrame: what to be long RIGHT NOW (entry, planned exit, target price)
    a.save("out/")  # writes CSVs

    report([...])   # = analyze(...).show(), returns the Analysis

AS A LAYER
    eng = EarningsEngine(quarters=40)
    eng.signal(tickers)            # 0..1 per ticker
    eng.multiplier(tickers)        # 1.0..1.5 sizing multiplier
    eng.apply(weights_series)      # tilt portfolio weights
    eng.filter(tickers, 40)        # keep names with a real big-beat record
    eng.signals(tickers)           # live long/skip table
    eng.backtest(tickers, hold_days=90, take_profit=0.20)   # BacktestResult

SCORE (0-100)  strong_rate 35% | last4 20% | streak 15% | magnitude 15% | freshness 15%
    Only quarters with surprise >= threshold earn credit. Fewer than 8 quarters shrinks it.
    rating: A>=70 B>=50 C>=30 D>=10 F.
    The score is ABSOLUTE: the same ticker gets the same score whichever peers you pass, and it is
    exactly what the accuracy test, p_next_big and the trade test measure. How a ticker ranks
    against the others in your call is shown separately as vs_peers (0-100, needs 5+ tickers).

TRADE RULE (all parameters adjustable)
    Signal : rating computed from quarters public at the report date (no lookahead), score >= min_score
    Entry  : close of the first trading day after the report (entry_lag=1) - tradable either
             for before-open or after-close reporters
    Exit   : +take_profit (default +20%) if hit, else after hold_days (default 90 calendar days)
    Result : return, return vs SPY over the same window, picked vs not-picked "edge"

Providers: earnings "yahoo" (no key) | "finnhub" (FINNHUB_API_KEY) | callable(ticker, limit)
           prices   "yahoo" | callable(ticker, start, end) -> Series(close, DatetimeIndex)
"""
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore", message=".*numexpr.*")      # harmless pandas optional-dep nags
warnings.filterwarnings("ignore", message=".*bottleneck.*")

import argparse
import logging
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional, Union

import numpy as np
import pandas as pd

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

__all__ = ["EarningsEngine", "EarningsLayer", "Analysis", "BacktestResult",
           "analyze", "report", "backtest", "rate", "rate_many", "DEFAULT_WEIGHTS"]

DEFAULT_WEIGHTS = {"strong_rate": 0.35, "last4": 0.20, "streak": 0.15,
                   "magnitude": 0.15, "freshness": 0.15}
_COLS = ["date", "est", "actual"]


def _norm(tickers: Iterable[str]) -> list:
    return list(dict.fromkeys(str(t).upper().strip() for t in tickers if t and str(t).strip()))


# --------------------------------------------------------------------------- #
# Data providers
# --------------------------------------------------------------------------- #
def yahoo_provider(ticker: str, limit: int = 16, **_) -> pd.DataFrame:
    import yfinance as yf

    df = yf.Ticker(ticker).get_earnings_dates(limit=max(limit + 4, 12))
    if df is None or df.empty:
        return pd.DataFrame(columns=_COLS)
    df = df.copy()
    df.index.name = "date"
    df = df.reset_index().rename(columns={"EPS Estimate": "est", "Reported EPS": "actual"})
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    return df[_COLS]


def finnhub_provider(ticker: str, limit: int = 16, api_key: Optional[str] = None, **_) -> pd.DataFrame:
    import requests

    key = api_key or os.getenv("FINNHUB_API_KEY")
    if not key:
        raise RuntimeError("Finnhub needs api_key= or FINNHUB_API_KEY env var")
    r = requests.get("https://finnhub.io/api/v1/stock/earnings",
                     params={"symbol": ticker, "limit": limit, "token": key}, timeout=10)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        return pd.DataFrame(columns=_COLS)
    df = pd.DataFrame(rows).rename(columns={"period": "date", "estimate": "est"})
    df["date"] = pd.to_datetime(df["date"])        # quarter-end, not announcement date
    return df[_COLS]


def yahoo_prices(ticker: str, start, end, **_) -> pd.Series:
    import yfinance as yf

    px = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)["Close"]
    if px.empty:
        return pd.Series(dtype=float)
    idx = pd.DatetimeIndex(px.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    px = pd.Series(px.to_numpy(float), index=idx.normalize(), name="close")
    return px[~px.index.duplicated()].sort_index()


# name -> (fn, days between the listed date and when the result was actually public)
_PROVIDERS = {"yahoo": (yahoo_provider, 0), "finnhub": (finnhub_provider, 45)}


# --------------------------------------------------------------------------- #
# Scoring math
# --------------------------------------------------------------------------- #
def _surprise_pct(est: np.ndarray, act: np.ndarray) -> np.ndarray:
    # floor the denominator so near-zero estimates don't create absurd surprises
    return np.clip((act - est) / np.maximum(np.abs(est), 0.10) * 100, -100, 100)


def _clean(h: pd.DataFrame) -> pd.DataFrame:
    h = h.dropna(subset=["est", "actual"]).sort_values("date").drop_duplicates("date")
    return h.reset_index(drop=True)


def _metrics_arr(dates: np.ndarray, est: np.ndarray, act: np.ndarray, thr: float,
                 half_life: float, min_q: int) -> Optional[dict]:
    """Core metrics from CLEAN, date-sorted arrays (fast path used inside loops)."""
    dates, est, act = dates[-40:], est[-40:], act[-40:]
    n = len(est)
    if n < min_q:
        return None
    s = _surprise_pct(est, act)
    big = s >= thr
    w = 0.5 ** (np.arange(n)[::-1] / half_life)       # 0 = latest quarter
    w /= w.sum()

    streak = 0
    for b in big[::-1]:
        if not b:
            break
        streak += 1
    idx = np.flatnonzero(big)
    since = float(n - 1 - idx[-1]) if len(idx) else np.nan
    avg_big = float((w[big] * s[big]).sum() / w[big].sum()) if big.any() else np.nan

    comp = {
        "strong_rate": float((w * big).sum()) * 100,
        "last4": float(big[-4:].mean()) * 100,
        "streak": min(streak, 4) / 4 * 100,
        "magnitude": 50 + 50 * np.tanh((avg_big - thr) / 25) if big.any() else 0.0,
        "freshness": 100 * max(0.0, 1 - since / 8) if len(idx) else 0.0,
    }
    m = {
        "n_quarters": n,
        "last_date": pd.Timestamp(dates[-1]),
        "n_big": int(big.sum()),
        "big_rate": float((w * big).sum()),
        "last4_big": int(big[-4:].sum()),
        "streak_big": streak,
        "qtrs_since_big": since,
        "avg_big_pct": avg_big,
        "avg_surprise_pct": float((w * s).sum()),
        "latest_surprise_pct": float(s[-1]),
        "last_big_date": pd.Timestamp(dates[idx[-1]]) if len(idx) else pd.NaT,
        "last_big_pct": float(s[idx[-1]]) if len(idx) else np.nan,
        "beat_rate": float((w * (s > 0)).sum()),
        "miss_rate": float((w * (s < 0)).sum()),
    }
    m.update({f"c_{k}": v for k, v in comp.items()})
    return m


def _metrics(h: pd.DataFrame, thr: float, half_life: float, min_q: int) -> Optional[dict]:
    h = _clean(h)
    return _metrics_arr(h["date"].to_numpy(), h["est"].to_numpy(float), h["actual"].to_numpy(float),
                        thr, half_life, min_q)


def _abs_score(m: dict, weights: dict, miss_penalty: float) -> float:
    keys = [k for k in weights if f"c_{k}" in m and weights[k] > 0]
    wsum = sum(weights[k] for k in keys)
    raw = sum(weights[k] * m[f"c_{k}"] for k in keys) / wsum
    raw -= miss_penalty * m["miss_rate"] * 100
    return float(np.clip(raw, 0, 100) * min(1.0, m["n_quarters"] / 8))


def _pct_rank(col: pd.Series) -> pd.Series:
    n = col.notna().sum()
    if n < 2 or col.nunique() <= 1:
        return col                                    # nothing to rank -> keep absolute value
    return (col.rank(method="min") - 1) / (n - 1) * 100   # ties share the LOWER rank


def _rating(score: float) -> str:
    if score is None or np.isnan(score):
        return "-"
    return "A" if score >= 70 else "B" if score >= 50 else "C" if score >= 30 else "D" if score >= 10 else "F"


_BUCKETS = [(0, 20, "0-20"), (20, 50, "20-50"), (50, 70, "50-70"), (70, 101, "70+")]


def _calibrate(det: pd.DataFrame, scores: pd.Series, k: float = 20.0):
    """score -> P(next quarter is a big beat), from walk-forward results. Each bucket's hit
    rate is shrunk toward the base rate (k pseudo-observations) and kept non-decreasing."""
    base = det["next_big"].mean()
    rows = []
    for lo, hi, name in _BUCKETS:
        sub = det[(det["score_before"] >= lo) & (det["score_before"] < hi)]
        n, hits = len(sub), int(sub["next_big"].sum())
        rows.append((name, n, hits / n if n else np.nan, (hits + k * base) / (n + k)))
    table = pd.DataFrame(rows, columns=["bucket", "n", "actual", "p"])
    table["p"] = np.maximum.accumulate(table["p"].to_numpy())

    def look(x):
        for (lo, hi, _), p in zip(_BUCKETS, table["p"]):
            if lo <= x < hi:
                return p
        return np.nan
    return scores.map(look), table


def _accuracy_lines(m: pd.Series, thr: float, table: Optional[pd.DataFrame] = None) -> list:
    if m.empty:
        return ["not enough history to test"]
    pct = lambda x: "n/a" if pd.isna(x) else f"{x * 100:.0f}%"
    n_hi = int(m["n_score>=50"])
    lines = [f"tests: {int(m['n_tests'])} quarters, {int(m['n_tickers'])} tickers"
             f" | base rate of a >={thr:g}% beat: {pct(m['base_big_beat_rate'])}"]
    if table is not None:
        lines.append("score bucket -> how often the NEXT quarter was a big beat:")
        for _, r in table.iterrows():
            lines.append(f"  {r['bucket']:>6}: {pct(r['actual']):>4} actual (n={int(r['n']):>3})"
                         f"  ->  p_next_big used: {pct(r['p'])}")
    lift, corr = m["lift_vs_base"], m["rank_corr_score_vs_next_surprise"]
    lines.append(f"lift (score>=50 vs base): {'n/a' if pd.isna(lift) else format(lift, '.2f') + 'x'}"
                 f"  |  rank corr, score vs next surprise: {corr:.2f}")
    skill = m.get("oos_brier_skill", np.nan)
    if pd.notna(skill):
        lines.append(f"OUT-OF-SAMPLE (calibrated on earlier 60% of dates, tested on later 40%, "
                     f"n={int(m['oos_n_tests'])}):")
        lines.append(f"  rated>=50 -> {pct(m['oos_big_rate_hi'])} big beats (n={int(m['oos_n_hi'])})"
                     f" vs base {pct(m['oos_base'])} | Brier skill {skill:+.3f} (>0 beats guessing base rate)")
    if m["n_tests"] < 60 or n_hi < 30:
        verdict = f"NOT ENOUGH DATA to judge (only {n_hi} high-rated tests, want 30+). Add more tickers."
    elif pd.notna(lift) and lift >= 1.5 and corr >= 0.10:
        if pd.notna(skill) and skill <= 0:
            verdict = f"MIXED: in-sample lift {lift:.2f}x but NO out-of-sample skill. Don't trust yet."
        else:
            verdict = f"SIGNAL: high-rated names hit big beats {lift:.2f}x more often than base."
    else:
        verdict = "WEAK / NO SIGNAL in this sample."
    return lines + [f"verdict: {verdict}",
                    "caveat: today's tickers (survivorship) + overlapping quarters flatter this."]


# --------------------------------------------------------------------------- #
# Trade simulation
# --------------------------------------------------------------------------- #
def _simulate(dates: np.ndarray, vals: np.ndarray, d, hold_days: int, tp: Optional[float],
              sl: Optional[float], entry_lag: int) -> Optional[dict]:
    """Long after an earnings date. Returns None if the entry day isn't in the data yet."""
    d64 = np.datetime64(pd.Timestamp(d).to_datetime64(), "ns")
    ei = int(np.searchsorted(dates, d64, side="right")) + entry_lag - 1   # first trading day AFTER d
    if ei >= len(vals):
        return None
    entry_date, entry = pd.Timestamp(dates[ei]), float(vals[ei])
    horizon = entry_date + pd.Timedelta(days=hold_days)
    h64 = np.datetime64(horizon.to_datetime64(), "ns")
    last_i = int(np.searchsorted(dates, h64, side="right")) - 1
    complete = bool(dates[-1] >= h64)
    path = vals[ei + 1: last_i + 1] / entry - 1

    exit_i, reason = last_i, "time"
    cand = []
    if tp is not None and len(path):
        w = np.flatnonzero(path >= tp)
        if len(w):
            cand.append((int(w[0]), "target"))
    if sl is not None and len(path):
        w = np.flatnonzero(path <= -sl)
        if len(w):
            cand.append((int(w[0]), "stop"))
    if cand:
        k, reason = min(cand)
        exit_i = ei + 1 + k
    status = "closed" if (reason != "time" or complete) else "open"
    exit_date, exit_px = pd.Timestamp(dates[exit_i]), float(vals[exit_i])
    return {"entry_date": entry_date, "entry_px": entry, "exit_date": exit_date, "exit_px": exit_px,
            "ret": exit_px / entry - 1, "hold_days": (exit_date - entry_date).days,
            "reason": reason if status == "closed" else "open", "status": status,
            "planned_exit": horizon}


def _asof_val(dates: np.ndarray, vals: np.ndarray, d) -> float:
    i = int(np.searchsorted(dates, np.datetime64(pd.Timestamp(d).to_datetime64(), "ns"), side="right")) - 1
    return float(vals[i]) if i >= 0 else np.nan


def _trade_stats(df: pd.DataFrame) -> dict:
    n = len(df)
    if n == 0:
        return dict(n=0, win_rate=np.nan, mean_ret=np.nan, median_ret=np.nan, mean_excess=np.nan,
                    avg_hold=np.nan, tp_rate=np.nan)
    ex = df["excess"].dropna()
    return dict(n=n, win_rate=float((df["ret"] > 0).mean()), mean_ret=float(df["ret"].mean()),
                median_ret=float(df["ret"].median()),
                mean_excess=float(ex.mean()) if len(ex) else np.nan,
                avg_hold=float(df["hold_days"].mean()), tp_rate=float((df["reason"] == "target").mean()))


def _welch(a: np.ndarray, b: np.ndarray):
    if len(a) < 2 or len(b) < 2:
        return np.nan, np.nan
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    diff = float(a.mean() - b.mean())
    return diff, (diff / se if se > 0 else np.nan)


# --------------------------------------------------------------------------- #
# Result objects
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Terminal rendering (aligned tables; colour only on a real terminal, honours NO_COLOR)
# --------------------------------------------------------------------------- #
_ANSI = {"green": "\033[32m", "yellow": "\033[33m", "red": "\033[31m", "dim": "\033[2m",
         "bold": "\033[1m"}


def _use_color(color: Optional[bool]) -> bool:
    if color is None:
        return bool(sys.stdout.isatty()) and not os.environ.get("NO_COLOR")
    return bool(color)


def _paint(text: str, style: Optional[str], on: bool) -> str:
    return f"{_ANSI[style]}{text}\033[0m" if (on and style) else text


def _rating_style(r) -> Optional[str]:
    return {"A": "green", "B": "green", "C": "yellow"}.get(r, "red" if r in ("D", "F") else None)


def _verdict_style(line: str) -> Optional[str]:
    u = line.upper()
    if "VERDICT:" not in u:
        return None
    if "NO EDGE" in u or "WEAK / NO" in u:
        return "red"
    if "NOT ENOUGH" in u or "MIXED" in u or "WEAK:" in u:
        return "yellow"
    if "SIGNAL:" in u or "EDGE IN-SAMPLE" in u:
        return "green"
    return None


def _render(df: pd.DataFrame, cols: list, fmt: Optional[dict] = None, style: Optional[dict] = None,
            on: bool = False, left: tuple = ("action",), indent: str = "  ", name: str = "ticker") -> str:
    """Aligned text table. fmt[col](value)->text, style[col](value)->colour name."""
    fmt, style = fmt or {}, style or {}
    heads = [name] + list(cols)
    cells, raw = [], []
    for idx, r in df.iterrows():
        row = [str(idx)]
        for c in cols:
            v = r[c] if c in r.index else np.nan
            try:
                row.append(fmt[c](v) if c in fmt else ("-" if pd.isna(v) else str(v)))
            except Exception:
                row.append(str(v))
        cells.append(row)
        raw.append(r)
    widths = [max([len(h)] + [len(c[j]) for c in cells]) for j, h in enumerate(heads)]
    pad = lambda j, t: t.ljust(widths[j]) if (j == 0 or heads[j] in left) else t.rjust(widths[j])
    out = [indent + "  ".join(_paint(pad(j, h), "bold", on) for j, h in enumerate(heads))]
    for row, r in zip(cells, raw):
        parts = [_paint(pad(0, row[0]), "bold", on)]
        for j, c in enumerate(cols, start=1):
            st = None
            if c in style:
                try:
                    st = style[c](r[c] if c in r.index else np.nan)
                except Exception:
                    st = None
            parts.append(_paint(pad(j, row[j]), st, on))
        out.append(indent + "  ".join(parts))
    return "\n".join(out)


_d10 = lambda v: "-" if pd.isna(v) else pd.Timestamp(v).strftime("%Y-%m-%d")
_p1 = lambda v: "-" if pd.isna(v) else f"{v:+.1f}%"            # value already in percent units
_f1 = lambda v: "-" if pd.isna(v) else f"{v:.1f}"
_f0 = lambda v: "-" if pd.isna(v) else f"{v:.0f}"


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    summary: pd.Series
    by_rating: pd.DataFrame
    params: dict
    errors: dict = field(default_factory=dict)

    def lines(self) -> list:
        p, s = self.params, self.summary
        f = lambda x, d=1: "n/a" if pd.isna(x) else f"{x * 100:+.{d}f}%"
        w = lambda x: "n/a" if pd.isna(x) else f"{x * 100:.0f}%"
        tp = "none" if p["take_profit"] is None else f"+{p['take_profit'] * 100:g}%"
        out = [f"long after earnings | max {p['hold_days']}d | take-profit {tp} | entry = close of day "
               f"{p['entry_lag']} after report | vs {p['benchmark'] or 'no benchmark'}"]
        if s.empty or s["picked_n"] + s["rest_n"] == 0:
            return out + ["no closed trades (missing price data or too little history)"]
        for tag, lab in (("picked", f"picked (score>={p['min_score']:g})"), ("rest", "not picked")):
            out.append(f"  {lab:<20} n={int(s[tag + '_n']):>4} | win {w(s[tag + '_win_rate'])} | avg {f(s[tag + '_mean_ret'])}"
                       f" | vs bench {f(s[tag + '_mean_excess'])} | avg hold {s[tag + '_avg_hold']:.0f}d"
                       f" | hit target {w(s[tag + '_tp_rate'])}")
        out.append(f"  edge (picked - not picked, {s['edge_basis']}): {f(s['edge'])}  (naive t={s['edge_t']:.2f})")
        if len(self.by_rating):
            out.append("  by rating at entry: " + " | ".join(
                f"{r}: n={int(row['n'])} avg {f(row['mean_ret'], 1)}" for r, row in self.by_rating.iterrows()))
        if s["n_open"]:
            out.append(f"  ({int(s['n_open'])} trades still open - excluded from stats)")
        n, t, e = s["picked_n"], s["edge_t"], s["edge"]
        if n < 30:
            v = f"NOT ENOUGH TRADES (picked n={int(n)}, want 30+). Add tickers / more history."
        elif pd.notna(e) and e > 0 and pd.notna(t) and t >= 2:
            v = "EDGE in-sample: picked beat not-picked. Naive t overstates it (earnings seasons cluster)."
        elif pd.notna(e) and e > 0:
            v = "WEAK: positive edge but not statistically distinguishable from noise."
        else:
            v = "NO EDGE: picked trades did not beat the rest."
        return out + [f"  verdict: {v}"]

    def show(self) -> None:
        print("\n".join(self.lines()))


@dataclass
class Analysis:
    scores: pd.DataFrame
    accuracy: pd.Series
    calibration: Optional[pd.DataFrame]
    tests: pd.DataFrame
    backtest: Optional[BacktestResult]
    signals: Optional[pd.DataFrame]
    errors: dict
    params: dict

    @property
    def trades(self) -> pd.DataFrame:
        return self.backtest.trades if self.backtest else pd.DataFrame()

    @property
    def trade_summary(self) -> pd.Series:
        return self.backtest.summary if self.backtest else pd.Series(dtype=float)

    def show(self, detail: bool = False, history: bool = False, eng: "EarningsEngine" = None,
             color: Optional[bool] = None) -> "Analysis":
        """Print the compact report. color=None -> colour only on a real terminal."""
        on, pr = _use_color(color), self.params
        B = lambda t: _paint(t, "bold", on)
        line = "=" * 78

        def para(lines):
            for ln in lines:
                print(_paint(ln, _verdict_style(ln), on))

        print(line)
        print(B(f"EARNINGS ENGINE | {pr['n_tickers']} tickers | big beat = EPS surprise >= {pr['threshold']:g}%"))
        print(line)
        if self.scores.empty:
            print("No tickers could be scored.")
        else:
            qmin = int(self.scores["n_quarters"].min())
            if qmin < 0.7 * pr["quarters"]:
                print(f"note: some tickers have short history (min {qmin} of {pr['quarters']} quarters requested)")
            card = EarningsEngine.scorecard(self.scores, detail=detail)
            cols = [c for c in card.columns]
            fmt = {"score": _f1, "vs_peers": _f0, "last_big_pct": _p1, "latest_qtr_pct": _p1,
                   "avg_surprise_pct": _p1}
            style = {"rating": _rating_style, "score": lambda v: _rating_style(_rating(v))}
            print("\n" + B("SCORECARD"))
            print(_render(card, cols, fmt, style, on))
            print(_paint("  score 0-100 (absolute) | rating A>=70 B>=50 C>=30 D>=10 F | vs_peers = rank in this list"
                         "\n  p_next_big = est. chance the next quarter is a big beat | big_beats = quarters >= "
                         "threshold", "dim", on))
            if history and eng is not None:
                for t in self.scores.index:
                    print("\n" + B(f"-- {t} history --"))
                    print(eng.history_table(t).to_string(index=False))
            if not self.accuracy.empty:
                print("\n" + B("ACCURACY") + "  (walk-forward: rate each past quarter using only earlier data)")
                para("  " + ln for ln in _accuracy_lines(self.accuracy, pr["threshold"], self.calibration))
            if self.backtest is not None:
                print("\n" + B("TRADE TEST"))
                para(("  " + ln if not ln.startswith("  ") else ln) for ln in self.backtest.lines())
            if self.signals is not None and len(self.signals):
                sg = self.signals
                act = sg["action"].fillna("") if "action" in sg else pd.Series("", index=sg.index)
                live = sg[act.str.startswith(("LONG", "ENTER"))]
                tp = pr.get("take_profit")
                print("\n" + B("LIVE SIGNALS") + f"  (latest report per ticker | score>={pr['min_score']:g} | "
                      f"hold up to {pr.get('hold_days', 90)}d" + (f" | +{tp * 100:g}% target)" if tp else ")"))
                if len(live):
                    scols = ["action", "score", "rating", "event_date", "entry_date", "planned_exit",
                             "ret_so_far", "target_px"]
                    sfmt = {"score": _f1, "event_date": _d10, "entry_date": _d10, "planned_exit": _d10,
                            "ret_so_far": lambda v: "-" if pd.isna(v) else f"{v * 100:+.1f}%",
                            "target_px": lambda v: "-" if pd.isna(v) else f"{v:.2f}"}
                    sstyle = {"action": lambda v: "green" if str(v).startswith("LONG") else "yellow",
                              "rating": _rating_style,
                              "ret_so_far": lambda v: None if pd.isna(v) else ("green" if v > 0 else "red")}
                    print(_render(live.reindex(columns=scols), scols, sfmt, sstyle, on))
                else:
                    print("  none open: every latest report is already past the hold window / closed,"
                          " or scored below the minimum.")
                n_skip, n_closed = int(act.str.startswith("skip").sum()), int(act.str.startswith("closed").sum())
                print(_paint(f"  {len(sg)} checked | {len(live)} long/enter | {n_skip} below min score | "
                             f"{n_closed} closed", "dim", on))
        if self.errors:
            print("\n" + _paint("COULD NOT SCORE: " + "; ".join(f"{t} ({e[:60]})" for t, e in self.errors.items()),
                               "red", on))
        print(line)
        print(_paint(f"done in {pr.get('elapsed', 0):.1f}s", "dim", on))
        return self

    def save(self, folder: str) -> str:
        p = Path(folder)
        p.mkdir(parents=True, exist_ok=True)
        self.scores.to_csv(p / "scores.csv")
        if not self.tests.empty:
            self.tests.to_csv(p / "accuracy_tests.csv", index=False)
        if self.backtest is not None:
            self.backtest.trades.to_csv(p / "trades.csv", index=False)
        if self.signals is not None:
            self.signals.to_csv(p / "signals.csv")
        return str(p)


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class EarningsEngine:
    def __init__(
        self,
        provider: Union[str, Callable] = "yahoo",
        threshold: float = 17.0,          # EPS surprise % that counts as a BIG beat
        quarters: int = 40,               # history depth (40 ~ 10 years)
        weights: Optional[dict] = None,
        half_life: float = 6.0,           # recency weighting, in quarters
        alpha: float = 0.0,               # 0 = score is ABSOLUTE (matches accuracy/trades); >0 blends peer rank
        miss_penalty: float = 0.0,        # 0 = ignore misses (only big beats matter)
        min_quarters: int = 4,
        min_universe: int = 5,
        workers: int = 8,
        cache: bool = True,
        cache_ttl_hours: float = 12.0,
        cache_dir: Optional[str] = None,
        api_key: Optional[str] = None,
        prices: Union[str, Callable] = "yahoo",
    ):
        if callable(provider):
            self._fetch, self._lag, self._pname = provider, 0, getattr(provider, "__name__", "custom")
        elif provider in _PROVIDERS:
            (self._fetch, self._lag), self._pname = _PROVIDERS[provider], provider
        else:
            raise ValueError(f"provider must be one of {list(_PROVIDERS)} or a callable")
        if callable(prices):
            self._pfetch, self._prname = prices, getattr(prices, "__name__", "custom")
        elif prices == "yahoo":
            self._pfetch, self._prname = yahoo_prices, "yahoo"
        else:
            raise ValueError("prices must be 'yahoo' or a callable(ticker, start, end)")
        self.threshold, self.quarters, self.half_life = threshold, quarters, half_life
        self.alpha, self.miss_penalty = alpha, miss_penalty
        self.min_quarters, self.min_universe, self.workers = min_quarters, min_universe, workers
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}
        self.api_key = api_key
        self.cache, self.ttl = cache, cache_ttl_hours * 3600
        self.cache_dir = Path(cache_dir or Path.home() / ".earnings_engine_cache")
        self.errors: dict = {}
        self.tracebacks: dict = {}
        self._mem: dict = {}
        self._px: dict = {}
        self._fail: dict = {}                         # ("h"|"p", ticker) -> exception (no repeat retries)
        if cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ---- data ------------------------------------------------------------- #
    def history(self, ticker: str) -> pd.DataFrame:
        """Raw earnings history [date, est, actual] for one ticker (memory + disk cached)."""
        t = ticker.upper().strip()
        if t in self._mem:
            return self._mem[t]
        if ("h", t) in self._fail:
            raise self._fail[("h", t)]
        path = self.cache_dir / f"{self._pname}_{t}_{self.quarters}.csv"
        if self.cache and path.exists() and time.time() - path.stat().st_mtime < self.ttl:
            try:
                df = pd.read_csv(path, parse_dates=["date"])
                self._mem[t] = df
                return df
            except Exception:
                path.unlink(missing_ok=True)          # bad cache file -> refetch

        df = None
        for attempt in range(2):
            try:
                try:
                    df = self._fetch(t, limit=self.quarters, api_key=self.api_key)
                except TypeError:                     # custom callable without api_key
                    df = self._fetch(t, self.quarters)
                break
            except Exception as e:
                if attempt == 1:
                    self._fail[("h", t)] = e
                    raise
                time.sleep(0.5)
        df = df[_COLS].copy()
        df["date"] = pd.to_datetime(df["date"])
        df = _clean(df).tail(self.quarters).reset_index(drop=True)
        if self.cache:
            try:
                df.to_csv(path, index=False)          # CSV: safe across pandas/numpy versions
            except Exception:
                pass
        self._mem[t] = df
        return df

    def prices(self, ticker: str, start) -> pd.Series:
        """Daily closes from ~`start` to today (memory + disk cached, one fetch per ticker)."""
        t = ticker.upper().strip()
        start = pd.Timestamp(start).to_period("M").to_timestamp()
        s = self._px.get(t)
        if s is not None and len(s) and s.index[0] <= start + pd.Timedelta(days=10):
            return s
        if ("p", t) in self._fail:
            raise self._fail[("p", t)]
        path = self.cache_dir / f"px_{self._prname}_{t}_{start:%Y%m}.csv"
        if self.cache and path.exists() and time.time() - path.stat().st_mtime < self.ttl:
            try:
                s = pd.read_csv(path, index_col=0, parse_dates=True)["close"]
                self._px[t] = s
                return s
            except Exception:
                path.unlink(missing_ok=True)
        end = pd.Timestamp.now().normalize() + pd.Timedelta(days=2)
        for attempt in range(2):
            try:
                s = self._pfetch(t, start, end)
                break
            except Exception as e:
                if attempt == 1:
                    self._fail[("p", t)] = e
                    raise
                time.sleep(0.5)
        s = pd.Series(np.asarray(s, dtype=float), index=pd.DatetimeIndex(s.index).normalize(), name="close")
        s = s[~s.index.duplicated()].sort_index().dropna()
        if self.cache and len(s):
            try:
                s.to_csv(path, header=["close"])
            except Exception:
                pass
        self._px[t] = s
        return s

    def _window(self, h: pd.DataFrame, as_of) -> pd.DataFrame:
        """Only quarters that were already public strictly before `as_of`."""
        if as_of is None:
            return h
        avail = pd.to_datetime(h["date"]) + pd.Timedelta(days=self._lag)
        return h[avail < pd.Timestamp(as_of)]

    # ---- scoring ---------------------------------------------------------- #
    def _one(self, ticker: str, as_of) -> Optional[dict]:
        h = self._window(self.history(ticker), as_of)
        return _metrics(h, self.threshold, self.half_life, self.min_quarters)

    def score(self, tickers: Iterable[str], as_of=None) -> pd.DataFrame:
        """Rate tickers. Relative rank is against the tickers passed in this call."""
        tickers = _norm(tickers)
        raw, self.errors, self.tracebacks = {}, {}, {}
        with ThreadPoolExecutor(self.workers) as ex:
            futs = {ex.submit(self._one, t, as_of): t for t in tickers}
            for f in as_completed(futs):
                t = futs[f]
                try:
                    m = f.result()
                except Exception as e:
                    self.errors[t] = f"{type(e).__name__}: {str(e)[:150]}"
                    self.tracebacks[t] = "".join(traceback.format_exception(e))
                    continue
                if m is None:
                    self.errors[t] = f"fewer than {self.min_quarters} usable quarters"
                else:
                    raw[t] = m

        if not raw:
            out = pd.DataFrame(columns=["score", "rating", "signal"])
            out.attrs["errors"] = self.errors
            return out

        df = pd.DataFrame.from_dict({t: raw[t] for t in tickers if t in raw}, orient="index")   # input order
        comp = df[[c for c in df.columns if c.startswith("c_")]].rename(columns=lambda c: c[2:])
        abs_score = pd.Series({t: _abs_score(raw[t], self.weights, self.miss_penalty) for t in df.index})
        conf = (df["n_quarters"] / 8).clip(upper=1.0)

        if len(df) >= self.min_universe:                      # peer rank is always shown as vs_peers
            rel = comp.apply(_pct_rank)
            w = pd.Series({k: v for k, v in self.weights.items() if k in rel.columns and v > 0})
            rel_score = (rel[w.index] * w).sum(axis=1) / w.sum() * conf
        else:
            rel_score = pd.Series(np.nan, index=df.index)
        final = (1 - self.alpha) * abs_score + self.alpha * rel_score if (
            self.alpha > 0 and rel_score.notna().all()) else abs_score
        final = final.clip(0, 100)

        out = df.drop(columns=[c for c in df.columns if c.startswith("c_") or c == "miss_rate"])
        out.insert(0, "score", final.round(1))
        out.insert(1, "rating", final.map(_rating))
        out.insert(2, "signal", (final / 100).round(3))            # 0..1, handy as a layer input
        out["abs_score"] = abs_score.round(1)
        out["rel_score"] = rel_score.round(1)
        out["confidence"] = conf.round(2)
        out = out.sort_values("score", ascending=False, kind="stable")   # deterministic order on ties
        out.attrs["errors"] = self.errors
        return out

    def rate(self, ticker: str, peers: Iterable[str] = (), as_of=None) -> pd.Series:
        """Rate one ticker (pass peers=[...] to rank it against them)."""
        df = self.score([ticker, *peers], as_of=as_of)
        t = ticker.upper().strip()
        if t not in df.index:
            raise ValueError(f"{t}: {self.errors.get(t, 'no result')}")
        return df.loc[t]

    def history_table(self, ticker: str, as_of=None) -> pd.DataFrame:
        """Every quarter: estimate, actual, surprise %, BIG BEAT/BEAT/INLINE/MISS, plus the
        rating this ticker had right after that quarter (point-in-time, no lookahead)."""
        h = _clean(self._window(self.history(ticker), as_of))
        s = _surprise_pct(h["est"].to_numpy(float), h["actual"].to_numpy(float))
        result = np.select([s >= self.threshold, s > 0, s < 0], ["BIG BEAT", "BEAT", "MISS"], "INLINE")
        d, e, a = h["date"].to_numpy(), h["est"].to_numpy(float), h["actual"].to_numpy(float)
        scores = []
        for i in range(len(h)):
            m = _metrics_arr(d[: i + 1], e[: i + 1], a[: i + 1], self.threshold, self.half_life, self.min_quarters)
            scores.append(_abs_score(m, self.weights, self.miss_penalty) if m else np.nan)
        return pd.DataFrame({
            "date": pd.to_datetime(h["date"]).dt.date.to_numpy(),
            "est": h["est"].to_numpy(float),
            "actual": h["actual"].to_numpy(float),
            "surprise_pct": s.round(2),
            "result": result,
            "score": np.round(scores, 1),
            "rating": [_rating(x) for x in scores],
        })

    # ---- accuracy (does the rating predict the next big beat?) ------------ #
    def validate(self, tickers: Iterable[str], min_hist: int = 4, as_of=None):
        """Walk-forward, no lookahead: rate each past quarter using only earlier quarters, then
        check whether the NEXT quarter was a big beat. Also reports an out-of-sample check
        (calibrate on the earlier 60% of dates, test on the later 40%).
        Returns (summary Series, per-quarter detail DataFrame)."""
        rows = []
        for t in _norm(tickers):
            try:
                h = _clean(self._window(self.history(t), as_of))
            except Exception:
                continue
            if len(h) < min_hist + 2:
                continue
            d, e, a = h["date"].to_numpy(), h["est"].to_numpy(float), h["actual"].to_numpy(float)
            s = _surprise_pct(e, a)
            for i in range(min_hist, len(h)):
                m = _metrics_arr(d[:i], e[:i], a[:i], self.threshold, self.half_life, min_hist)
                if m is not None:
                    rows.append((t, pd.Timestamp(d[i]), _abs_score(m, self.weights, self.miss_penalty), s[i]))
        det = pd.DataFrame(rows, columns=["ticker", "date", "score_before", "next_surprise_pct"])
        if det.empty:
            return pd.Series(dtype=float), det
        det["next_big"] = det["next_surprise_pct"] >= self.threshold
        hi, lo = det[det["score_before"] >= 50], det[det["score_before"] < 20]
        base = det["next_big"].mean()
        hi_rate = hi["next_big"].mean() if len(hi) else np.nan

        oos = {"oos_n_tests": np.nan, "oos_base": np.nan, "oos_big_rate_hi": np.nan,
               "oos_n_hi": np.nan, "oos_brier_skill": np.nan}
        ds = det.sort_values("date")
        cut = ds["date"].iloc[int(len(ds) * 0.6)]
        tr, te = det[det["date"] < cut], det[det["date"] >= cut]
        if len(tr) >= 40 and len(te) >= 40:
            p_te, _ = _calibrate(tr, te["score_before"])
            y = te["next_big"].astype(float)
            b_model = float(((p_te - y) ** 2).mean())
            b_base = float(((tr["next_big"].mean() - y) ** 2).mean())
            te_hi = te[te["score_before"] >= 50]
            oos = {"oos_n_tests": len(te), "oos_base": float(y.mean()),
                   "oos_big_rate_hi": float(te_hi["next_big"].mean()) if len(te_hi) else np.nan,
                   "oos_n_hi": len(te_hi),
                   "oos_brier_skill": 1 - b_model / b_base if b_base > 0 else np.nan}

        summary = pd.Series({
            "n_tests": len(det),
            "n_tickers": det["ticker"].nunique(),
            "base_big_beat_rate": base,
            "big_rate_when_score>=50": hi_rate,
            "n_score>=50": len(hi),
            "big_rate_when_score<20": lo["next_big"].mean() if len(lo) else np.nan,
            "n_score<20": len(lo),
            "lift_vs_base": hi_rate / base if base and not np.isnan(hi_rate) else np.nan,
            "rank_corr_score_vs_next_surprise":
                det["score_before"].rank().corr(det["next_surprise_pct"].rank()),
            **oos,
        })
        return summary, det

    # ---- trading: backtest + live signals --------------------------------- #
    def backtest(self, tickers: Iterable[str], hold_days: int = 90, take_profit: Optional[float] = 0.20,
                 stop_loss: Optional[float] = None, min_score: float = 50.0, entry_lag: int = 1,
                 benchmark: Optional[str] = "SPY") -> BacktestResult:
        """Simulate going long after EVERY earnings event in the history. The score at each event
        uses only quarters public by then. `picked` = score >= min_score; the rest is the baseline."""
        params = dict(hold_days=hold_days, take_profit=take_profit, stop_loss=stop_loss,
                      min_score=min_score, entry_lag=entry_lag, benchmark=benchmark)
        errors, ev = {}, []
        for t in _norm(tickers):
            try:
                h = _clean(self.history(t))
            except Exception as e:
                errors[t] = f"earnings: {type(e).__name__}"
                continue
            d, e, a = h["date"].to_numpy(), h["est"].to_numpy(float), h["actual"].to_numpy(float)
            s = _surprise_pct(e, a)
            for i in range(self.min_quarters - 1, len(h)):
                m = _metrics_arr(d[: i + 1], e[: i + 1], a[: i + 1], self.threshold, self.half_life, self.min_quarters)
                if m is not None:
                    sc = _abs_score(m, self.weights, self.miss_penalty)
                    ev.append((t, pd.Timestamp(d[i]), sc, _rating(sc), float(s[i])))
        ev = pd.DataFrame(ev, columns=["ticker", "event_date", "score", "rating", "surprise_pct"])
        empty = BacktestResult(pd.DataFrame(), pd.Series(dtype=float), pd.DataFrame(), params, errors)
        if ev.empty:
            return empty

        starts = ev.groupby("ticker")["event_date"].min()
        names = list(starts.index) + ([benchmark] if benchmark else [])
        px: dict = {}
        with ThreadPoolExecutor(self.workers) as ex:
            futs = {ex.submit(self.prices, t, starts.get(t, starts.min())): t for t in names}
            for f in as_completed(futs):
                t = futs[f]
                try:
                    s = f.result()
                    if len(s):
                        px[t] = (s.index.values.astype("datetime64[ns]"), s.to_numpy(float))
                    else:
                        errors[t] = "no price data"
                except Exception as e:
                    errors[t] = f"prices: {type(e).__name__}: {str(e)[:80]}"
        bench = px.get(benchmark) if benchmark else None

        rows = []
        for r in ev.itertuples(index=False):
            if r.ticker not in px:
                continue
            sim = _simulate(*px[r.ticker], r.event_date, hold_days, take_profit, stop_loss, entry_lag)
            if sim is None:
                continue
            b_ret = np.nan
            if bench is not None:
                b0, b1 = _asof_val(*bench, sim["entry_date"]), _asof_val(*bench, sim["exit_date"])
                b_ret = b1 / b0 - 1 if b0 and not np.isnan(b0) and not np.isnan(b1) else np.nan
            rows.append({"ticker": r.ticker, "event_date": r.event_date, "score": round(r.score, 1),
                         "rating": r.rating, "surprise_pct": round(r.surprise_pct, 2), **sim,
                         "bench_ret": b_ret, "excess": sim["ret"] - b_ret, "picked": r.score >= min_score})
        if not rows:
            return BacktestResult(pd.DataFrame(), pd.Series(dtype=float), pd.DataFrame(), params, errors)
        trades = pd.DataFrame(rows).drop(columns=["planned_exit"])
        closed = trades[trades["status"] == "closed"]
        pk, rest = closed[closed["picked"]], closed[~closed["picked"]]
        sp, sr = _trade_stats(pk), _trade_stats(rest)
        col = "excess" if (pk["excess"].notna().sum() >= 10 and rest["excess"].notna().sum() >= 10) else "ret"
        edge, t_stat = _welch(pk[col].dropna().to_numpy(float), rest[col].dropna().to_numpy(float))
        summary = pd.Series({**{f"picked_{k}": v for k, v in sp.items()},
                             **{f"rest_{k}": v for k, v in sr.items()},
                             "edge": edge, "edge_t": t_stat,
                             "edge_basis": "excess vs bench" if col == "excess" else "raw return",
                             "n_open": int((trades["status"] == "open").sum())})
        by = {}
        for r_ in ["A", "B", "C", "D", "F"]:
            sub = closed[closed["rating"] == r_]
            if len(sub):
                st = _trade_stats(sub)
                by[r_] = {k: st[k] for k in ("n", "win_rate", "mean_ret", "mean_excess", "avg_hold")}
        return BacktestResult(trades, summary, pd.DataFrame.from_dict(by, orient="index"), params, errors)

    def signals(self, tickers: Iterable[str], hold_days: int = 90, take_profit: Optional[float] = 0.20,
                stop_loss: Optional[float] = None, min_score: float = 50.0, entry_lag: int = 1) -> pd.DataFrame:
        """What to hold right now: for each ticker's LATEST earnings event, apply the same rule as
        the backtest and report the live status (ENTER / LONG / closed / skip)."""
        rows = []
        for t in _norm(tickers):
            try:
                h = _clean(self.history(t))
                m = _metrics(h, self.threshold, self.half_life, self.min_quarters)
                if m is None:
                    continue
                sc = _abs_score(m, self.weights, self.miss_penalty)
                d = h["date"].iloc[-1]
                row = {"ticker": t, "score": round(sc, 1), "rating": _rating(sc), "event_date": d,
                       "surprise_pct": round(float(m["latest_surprise_pct"]), 2)}
                s = self.prices(t, d)
                sim = _simulate(s.index.values.astype("datetime64[ns]"), s.to_numpy(float), d,
                                hold_days, take_profit, stop_loss, entry_lag) if len(s) else None
                picked = sc >= min_score
                if sim is None:
                    row.update(status="pending", action="ENTER (next session close)" if picked else "skip (score < min)")
                else:
                    stt = sim["status"]
                    act = ("skip (score < min)" if not picked else
                           f"LONG (day {(s.index[-1] - sim['entry_date']).days} of {hold_days})" if stt == "open" else
                           f"closed ({sim['reason']})")
                    row.update(status=stt, action=act, entry_date=sim["entry_date"], entry_px=sim["entry_px"],
                               planned_exit=sim["planned_exit"], ret_so_far=sim["ret"],
                               target_px=sim["entry_px"] * (1 + take_profit) if take_profit else np.nan)
                rows.append(row)
            except Exception as e:
                rows.append({"ticker": t, "status": "error", "action": f"error: {type(e).__name__}"})
        out = pd.DataFrame(rows)
        if out.empty:
            return out
        for c in ("entry_date", "planned_exit", "entry_px", "ret_so_far", "target_px"):
            if c not in out:
                out[c] = np.nan
        order = {"open": 0, "pending": 1, "closed": 2}
        out["_o"] = out["status"].map(order).fillna(3)
        return (out.sort_values(["_o", "score"], ascending=[True, False], kind="stable")
                .drop(columns="_o").set_index("ticker"))

    # ---- one call that returns everything -------------------------------- #
    def analyze(self, tickers: Iterable[str], as_of=None, accuracy: bool = True, trade: bool = True,
                hold_days: int = 90, take_profit: Optional[float] = 0.20, stop_loss: Optional[float] = None,
                min_score: float = 50.0, entry_lag: int = 1, benchmark: Optional[str] = "SPY") -> Analysis:
        """Score + accuracy + trade test + live signals. Returns an Analysis; prints nothing."""
        t_start = time.time()
        tickers = _norm(tickers)
        scores = self.score(tickers, as_of=as_of)
        errors = dict(self.errors)
        summ, det, table = pd.Series(dtype=float), pd.DataFrame(), None
        if accuracy and not scores.empty:
            summ, det = self.validate(scores.index, as_of=as_of)
            if not det.empty:
                probs, table = _calibrate(det, scores["abs_score"])
                scores["p_next_big"] = probs.round(3)
        bt = sig = None
        if trade and as_of is None and not scores.empty:
            try:
                bt = self.backtest(scores.index, hold_days, take_profit, stop_loss, min_score, entry_lag, benchmark)
                errors.update({f"{k}(prices)": v for k, v in bt.errors.items()})
                sig = self.signals(scores.index, hold_days, take_profit, stop_loss, min_score, entry_lag)
            except Exception as e:
                errors["trade"] = f"{type(e).__name__}: {str(e)[:100]}"
        params = dict(n_tickers=len(tickers), threshold=self.threshold, quarters=self.quarters,
                      min_score=min_score, hold_days=hold_days, take_profit=take_profit,
                      elapsed=time.time() - t_start)
        return Analysis(scores, summ, table, det, bt, sig, errors, params)

    def report(self, tickers: Iterable[str], history: bool = False, detail: bool = False, **kw) -> Analysis:
        """analyze() + print. Returns the Analysis so you can keep using the numbers."""
        a = self.analyze(tickers, **kw)
        return a.show(detail=detail, history=history, eng=self)

    # ---- layer helpers ---------------------------------------------------- #
    def signal(self, tickers: Iterable[str], as_of=None, scores: Optional[pd.DataFrame] = None) -> pd.Series:
        """0..1 per ticker (score/100). Unscorable tickers get 0."""
        tickers = _norm(tickers)
        df = scores if scores is not None else self.score(tickers, as_of=as_of)
        return (df["score"] / 100).reindex(tickers).fillna(0.0).rename("earnings_signal")

    def multiplier(self, tickers: Iterable[str], lo: float = 1.0, hi: float = 1.5,
                   as_of=None, scores: Optional[pd.DataFrame] = None) -> pd.Series:
        """score 0..100 -> [lo, hi]. Default 1.0..1.5 = no penalty, boost for big-beat names."""
        sig = self.signal(tickers, as_of=as_of, scores=scores)
        return (lo + (hi - lo) * sig).rename("earnings_mult")

    def apply(self, weights: pd.Series, lo: float = 1.0, hi: float = 1.5,
              renormalize: bool = True, as_of=None) -> pd.Series:
        """Tilt an existing {ticker: weight} Series. renormalize=True keeps total exposure."""
        w = weights.copy()
        w.index = [str(i).upper().strip() for i in w.index]
        out = w * self.multiplier(w.index, lo, hi, as_of=as_of)
        if renormalize and out.sum() != 0:
            out = out * (w.sum() / out.sum())
        return out

    def filter(self, tickers: Iterable[str], min_score: float = 40.0, as_of=None) -> list:
        df = self.score(tickers, as_of=as_of)
        return df.index[df["score"] >= min_score].tolist()

    @staticmethod
    def scorecard(df: pd.DataFrame, detail: bool = False) -> pd.DataFrame:
        """Compact one-row-per-ticker summary. detail=True adds the raw surprise columns."""
        if df.empty:
            return df
        out = pd.DataFrame(index=df.index)
        out["score"] = df["score"]
        out["rating"] = df["rating"]
        if "rel_score" in df and df["rel_score"].notna().any():
            out["vs_peers"] = df["rel_score"]
        if "p_next_big" in df:
            out["p_next_big"] = df["p_next_big"].map(lambda x: "-" if pd.isna(x) else f"{x * 100:.0f}%")
        out["big_beats"] = df["n_big"].astype(int).astype(str) + "/" + df["n_quarters"].astype(int).astype(str)
        out["last4"] = df["last4_big"].astype(int).astype(str) + "/4"
        out["streak"] = df["streak_big"]
        out["last_big_beat"] = pd.to_datetime(df["last_big_date"]).dt.strftime("%Y-%m-%d").fillna("-")
        if detail:
            out["last_big_pct"] = df["last_big_pct"]
            out["latest_qtr_pct"] = df["latest_surprise_pct"]
            out["avg_surprise_pct"] = df["avg_surprise_pct"]
        return out

    @staticmethod
    def export(df: pd.DataFrame, path: str) -> str:
        """Write .csv / .json / .parquet based on the extension."""
        ext = Path(path).suffix.lower()
        if ext == ".json":
            df.to_json(path, orient="index", indent=2, date_format="iso")
        elif ext == ".parquet":
            df.to_parquet(path)
        else:
            df.to_csv(path)
        return path


EarningsLayer = EarningsEngine      # alias


# --------------------------------------------------------------------------- #
# Module-level shortcuts
# --------------------------------------------------------------------------- #
_ENGINE_KW = {"provider", "threshold", "quarters", "weights", "half_life", "alpha", "miss_penalty",
              "min_quarters", "min_universe", "workers", "cache", "cache_ttl_hours", "cache_dir",
              "api_key", "prices"}


def _split(kw: dict):
    return ({k: v for k, v in kw.items() if k in _ENGINE_KW}, {k: v for k, v in kw.items() if k not in _ENGINE_KW})


def analyze(tickers: Iterable[str], **kw) -> Analysis:
    """analyze(['MU','NVDA',...]) -> Analysis (no printing). Engine kwargs (threshold=, quarters=,
    provider=, prices=...) and trade kwargs (hold_days=, take_profit=, min_score=...) both accepted."""
    ekw, akw = _split(kw)
    return EarningsEngine(**ekw).analyze(tickers, **akw)


def report(tickers: Iterable[str], history: bool = False, detail: bool = False, **kw) -> Analysis:
    """Prints the compact report and RETURNS the Analysis."""
    ekw, akw = _split(kw)
    return EarningsEngine(**ekw).report(tickers, history=history, detail=detail, **akw)


def backtest(tickers: Iterable[str], **kw) -> BacktestResult:
    ekw, bkw = _split(kw)
    return EarningsEngine(**ekw).backtest(tickers, **bkw)


def rate(ticker: str, **kw) -> pd.Series:
    as_of, peers = kw.pop("as_of", None), kw.pop("peers", ())
    return EarningsEngine(**kw).rate(ticker, peers=peers, as_of=as_of)


def rate_many(tickers: Iterable[str], **kw) -> pd.DataFrame:
    as_of = kw.pop("as_of", None)
    return EarningsEngine(**kw).score(tickers, as_of=as_of)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _main():
    ap = argparse.ArgumentParser(description="Big-earnings-beat rater + 90-day long test")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--thr", type=float, default=17.0, help="EPS surprise %% that counts as a big beat")
    ap.add_argument("--quarters", type=int, default=40, help="history depth (default 40 = ~10 years)")
    ap.add_argument("--provider", default="yahoo", choices=list(_PROVIDERS))
    ap.add_argument("--hold", type=int, default=90, help="max holding days")
    ap.add_argument("--tp", type=float, default=0.20, help="take-profit as a fraction (0.20 = +20%%); 0 = off")
    ap.add_argument("--sl", type=float, default=0.0, help="stop-loss fraction; 0 = off")
    ap.add_argument("--min-score", type=float, default=50.0, help="score needed to go long")
    ap.add_argument("--bench", default="SPY", help="benchmark ticker ('' = none)")
    ap.add_argument("--no-trade", action="store_true", help="skip the trade test + live signals")
    ap.add_argument("--no-accuracy", action="store_true")
    ap.add_argument("--history", action="store_true", help="print every quarter with its rating")
    ap.add_argument("--detail", action="store_true", help="raw surprise columns in the scorecard")
    ap.add_argument("--debug", action="store_true", help="full tracebacks on errors")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--save", help="folder to write scores/trades/signals CSVs")
    a = ap.parse_args()

    eng = EarningsEngine(a.provider, threshold=a.thr, quarters=a.quarters, cache=not a.no_cache)
    res = eng.report(a.tickers, history=a.history, detail=a.detail, accuracy=not a.no_accuracy,
                     trade=not a.no_trade, hold_days=a.hold, take_profit=a.tp or None,
                     stop_loss=a.sl or None, min_score=a.min_score, benchmark=a.bench or None)
    if a.debug:
        for t, tb in eng.tracebacks.items():
            print(f"\n--- {t} ---\n{tb}")
    if a.save:
        print("saved ->", res.save(a.save))


if __name__ == "__main__":
    _main()
