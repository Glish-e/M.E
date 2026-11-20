#!/usr/bin/env python3
"""owner_fetch_spy.py — W5 (v1.8.0): fetch the SPY monthly series the
backtest's --bt-spy flag consumes.

OWNER-RUN ONLY (R11/R12): this script talks to Yahoo's public chart
endpoint — the agent never runs it; run it on the machine with network
and copy the file back into owner_results/ (AWAITING OWNER DATA until
then; nothing is faked in its absence — the backtest keeps printing
'SPY: NOT AVAILABLE').

What it writes: owner_results/spy_monthly.json
  {"source": "Yahoo chart API (v8) monthly candles, fetched <ts> by
             owner_fetch_spy.py — REAL data",
   "monthly_close": {"YYYY-MM-DD": <float adj close at month-end>, ...}}
The backtest aligns 63-trading-day label windows as 3-month SPY returns
on the SAME month-end as-of dates (close[t+3m]/close[t]-1).

Usage:  python3 scripts/owner_fetch_spy.py [--years N] [--out PATH]
Exit 0 on success; 2 on any fetch/parse failure (nothing is written on
failure — the file is atomic-or-absent, never partial).
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = ("https://query1.finance.yahoo.com/v8/finance/chart/SPY"
       "?range={years}y&interval=1mo")
UA = "Mozilla/5.0 (research screener; owner_fetch_spy.py; contact: owner)"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    years = 10
    out = ROOT / "owner_results" / "spy_monthly.json"
    if "--years" in argv:
        years = int(argv[argv.index("--years") + 1])
        del argv[argv.index("--years"): argv.index("--years") + 2]
    if "--out" in argv:
        out = Path(argv[argv.index("--out") + 1])
        del argv[argv.index("--out"): argv.index("--out") + 2]
    if argv:
        print(f"usage: owner_fetch_spy.py [--years N] [--out PATH] "
              f"(got {argv!r})")
        return 64
    url = URL.format(years=years)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"owner_fetch_spy: fetch failed ({e}) — rerun when the "
              "network is up; the backtest stays honest with "
              "'SPY: NOT AVAILABLE' meanwhile")
        return 2
    try:
        res = payload["chart"]["result"][0]
        ts = res["timestamp"]
        closes = res["indicators"]["quote"][0]["close"]
        adj = (res.get("indicators", {}).get("adjclose")
               or [{}])[0].get("adjclose") or closes
    except Exception as e:
        print(f"owner_fetch_spy: unexpected payload shape ({e}) — "
              "Yahoo changed the schema; inspect "
              "https://query1.finance.yahoo.com/v8/finance/chart/SPY")
        return 2
    monthly: dict[str, float] = {}
    for t, c in zip(ts, adj):
        if c is None:
            continue
        d = datetime.fromtimestamp(t, tz=timezone.utc)
        key = f"{d.year:04d}-{d.month:02d}-{d.day:02d}"
        monthly[key] = round(float(c), 6)
    if len(monthly) < 15:
        print(f"owner_fetch_spy: only {len(monthly)} rows parsed — "
              "refusing to write a too-short series")
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({
        "source": ("Yahoo chart API (v8) monthly candles, fetched "
                   f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} "
                   "by owner_fetch_spy.py — REAL data"),
        "monthly_close": dict(sorted(monthly.items()))}, indent=1),
        encoding="utf-8")
    tmp.replace(out)
    print(f"owner_fetch_spy: wrote {out} ({len(monthly)} month-ends) — "
          "use: python3 master.py --backtest --bt-spy "
          f"{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
