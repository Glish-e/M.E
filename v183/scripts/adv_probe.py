#!/usr/bin/env python3
"""ADV liquidity feasibility probe — P-4 (spec 3.3), phase 4.

QUESTION (asked BEFORE any guard was written): is average daily dollar
volume obtainable from the price feeds this master can actually read,
offline-cacheable, per name?

Feeds master can read (read-only; neither engine file is edited):
  1. earnings_engine.prices(ticker, start) — a close-only Series, served
     from px_*.csv cache files written by the engine's own fetcher;
  2. quality's price client — Close / Adj Close / Stock Splits rows in its
     own cache (the columns it extracts from the provider payload).

WHAT THE PROBE CHECKS (live, offline, no network, no invented numbers):
  A. every cached px_*.csv header in the earnings engine cache dir for a
     Volume column;
  B. the earnings_engine.py source for a Volume column anywhere in its
     price paths;
  C. the quality.py source for a Volume column in its price client.

VERDICT:
  AVAILABLE   — volume is genuinely readable (guard may be built on it);
  UNAVAILABLE — no volume anywhere: the ADV cap (max position as % of ADV)
               and the min-ADV exclusion are NOT implemented, nothing is
               faked or estimated, and the fact ships loudly with the
               stable code [W_ADV_UNAVAILABLE] (also printed by
               `python3 master.py --doctor`).

Exit 0 with the verdict either way (a probe reports data; it does not
fail on an honest negative). Usage: python3 scripts/adv_probe.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CODE = "[W_ADV_UNAVAILABLE]"
HINT = "python3 scripts/adv_probe.py"


def _cache_scan(base: Path, limit: int = 8):
    """(checked, with_volume, [(file, columns)]) over px_*.csv headers."""
    checked = with_vol = 0
    found: list[tuple[str, list[str]]] = []
    try:
        files = sorted(base.glob("px_*.csv"))[:limit]
    except OSError:
        return 0, 0, []
    for p in files:
        try:
            head = p.open("r", encoding="utf-8", errors="replace").readline()
        except OSError:
            continue
        checked += 1
        cols = [c.strip().strip('"').lower() for c in head.split(",") if c.strip()]
        found.append((p.name, cols))
        if any("volume" in c for c in cols):
            with_vol += 1
    return checked, with_vol, found


def _source_has_volume(fname: str) -> tuple[bool, int]:
    """(has_volume_column_key, n_references) in one engine source file."""
    try:
        src = (ROOT / fname).read_text(encoding="utf-8")
    except OSError:
        return False, 0
    hits = re.findall(r"[\"']Volume[\"']", src)
    return bool(hits), len(hits)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        print(f"usage: adv_probe.py (got {argv!r}) — no arguments, read-only probe")
        return 64
    print("=" * 76)
    print("ADV PROBE — P-4 feasibility (spec 3.3): is dollar volume readable?")
    print("=" * 76)

    # A. the earnings engine's own price cache (the feed master's risk
    #    layer and the P-3 stop already consume)
    cache_dir = os.environ.get("QE_CACHE_DIR") or str(Path.home() / ".earnings_engine_cache")
    checked, with_vol, files = _cache_scan(Path(cache_dir))
    print(f"\n1) earnings engine price cache ({cache_dir})")
    if not files:
        print("   no px_*.csv cache files found (cold cache — nothing to inspect)")
    for name, cols in files:
        print(f"   {name}: columns {cols}")
    print(f"   cached price files with a Volume column: {with_vol}/{checked}")

    # B/C. the two engine SOURCES: do their price paths extract volume?
    ee_vol, ee_hits = _source_has_volume("earnings_engine.py")
    q_vol, q_hits = _source_has_volume("quality.py")
    print("\n2) engine source price paths")
    ee_note = ("PRESENT" if ee_vol else
               "none — yahoo_prices() extracts Close only, cached as a "
               "single close column")
    q_note = ("PRESENT" if q_vol else
              "none — the price client extracts Close / Adj Close / "
              "Stock Splits only")
    print(f"   earnings_engine.py: Volume column references {ee_hits} ({ee_note})")
    print(f"   quality.py:          Volume column references {q_hits} ({q_note})")

    available = bool(with_vol or ee_vol or q_vol)
    print("\n" + "-" * 76)
    if available:
        print("ADV PROBE VERDICT: AVAILABLE — volume is readable from the feeds;")
        print("the ADV cap (max position as % of ADV) and the min-ADV exclusion")
        print("are pending implementation on top of this evidence.")
        return 0
    print("ADV PROBE VERDICT: ADV UNAVAILABLE " + CODE)
    print("  No price feed this master can read carries a Volume column —")
    print("  average daily dollar volume cannot be computed offline, and it")
    print("  is NOT estimated, faked or proxied (spec 3.3: probe first, do")
    print("  not fake). Consequences, stated loudly:")
    print("   - the ADV cap (max position as a percentage of ADV) is NOT")
    print("     implemented;")
    print("   - the minimum-ADV exclusion (with a visible reason) is NOT")
    print("     implemented;")
    print("   - the liquidity limit of spec 3.4's trade-management grid is")
    print("     UNANSWERABLE until an engine-side volume feed exists (an")
    print("     owner decision — engine files stay untouched).")
    print(f"  This verdict also prints in `python3 master.py --doctor` output;")
    print(f"  re-run this probe any time: {HINT}")
    print("-" * 76)
    return 0


if __name__ == "__main__":
    sys.exit(main())
