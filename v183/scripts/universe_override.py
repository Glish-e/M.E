#!/usr/bin/env python3
"""universe_override.py — the owner command for dead tickers
(v1.8.1 F8; v1.8.2 W6 adds the sector-mismatch warning).

Adds/updates rows in data/universe_overrides.csv (the format quality.py's
load_overrides reads at quality.py:1695-1764 expects: columns
ticker,sector,status,note; status one of active|delisted|renamed; the file
is ALSO read through the QE_UNIVERSE_OVERRIDES env var). A delisted row
takes the name out of the ACTIVE universe refs the next run — no engine
file is touched (R1), and master's negative cache (N5) stops refetching a
404-ing ticker in the meantime.

v1.8.2 (W6): `add` WARNS when the given sector differs from the engine's
own group for that ticker (quality's GROUPS map — a wrong sector would
silently move the name into a different comparison pool while it is
active, and the mismatch is almost always a mistake). The check fails
soft (one note, no warning, exit still 0) when quality cannot be
imported. The shipped CSV is HEADER-ONLY (an example row would surface
as an unknown_override_ticker in every engine universe report).

Run it (owner or agent — no network needed):
  python3 scripts/universe_override.py add CFLT tech delisted "owner-verified dead 2026-11"
  python3 scripts/universe_override.py add PSTG tech delisted "owner-verified dead 2026-11"
  python3 scripts/universe_override.py list
  python3 scripts/universe_override.py remove CFLT

Exit 0 ok · 2 usage · 3 status word unknown.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "data" / "universe_overrides.csv"
KNOWN_STATUSES = ("active", "delisted", "renamed")
USAGE = __doc__.split("Run it")[0] + (
    "usage: universe_override.py add TICKER SECTOR STATUS [NOTE] "
    "[--file CSV] · list [--file CSV] · remove TICKER [--file CSV]")


def _engine_group(ticker: str) -> str | None:
    """quality's own group for the ticker, or None when the engine (or its
    GROUPS map) is unavailable — the mismatch check FAILS SOFT either way.
    Returns "" (known-but-unmapped: a name outside the builtin universe)
    vs None (check unavailable)."""
    try:
        sys.path.insert(0, str(ROOT))
        import quality  # noqa: PLC0415 - the fail-soft import
    except Exception:
        return None
    groups = getattr(quality, "GROUPS", None)
    if not isinstance(groups, dict):
        return None
    for group, names in groups.items():
        if ticker in names:
            return str(group)
    return ""


def _sector_mismatch_note(ticker: str, sector: str) -> str:
    """The W6 warning line, or '' when nothing to say (fail soft)."""
    if not sector:
        return ""
    engine_group = _engine_group(ticker)
    if engine_group is None:
        return ("note: quality unavailable — the sector/engine-group check "
                "was SKIPPED (fail-soft); verify the group with: python3 -c "
                f"'import quality; print([g for g,m in quality.GROUPS.items() "
                f"if {ticker!r} in m])'")
    if engine_group == "":
        return (f"note: {ticker} is not in quality's builtin universe — the "
                "sector is recorded as given (no engine group to compare)")
    if sector != engine_group:
        return (f"WARNING: sector mismatch — you gave sector '{sector}' but "
                f"quality groups {ticker} under '{engine_group}'; a wrong "
                "sector silently moves the name between comparison pools "
                "while it is active. Row written as given; to use the "
                f"engine's group instead: add {ticker} {engine_group}")
    return ""


def _read(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not path.is_file():
        return out
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            t = (row.get("ticker") or "").strip().upper()
            if t:
                out[t] = {k: (row.get(k) or "").strip()
                          for k in ("sector", "status", "note")}
    return out


def _write(path: Path, data: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(("ticker", "sector", "status", "note"))
        for t in sorted(data):
            r = data[t]
            w.writerow((t, r.get("sector", ""), r.get("status", ""),
                        r.get("note", "")))
    tmp.replace(path)          # atomic: never a truncated CSV on a crash


def main(argv: list[str]) -> int:
    args = [a for a in argv if a != "--file"]
    path = DEFAULT_CSV
    if "--file" in argv:
        path = Path(argv[argv.index("--file") + 1])
    if not args or args[0] not in ("add", "list", "remove"):
        sys.stderr.write(USAGE + "\n")
        return 2
    cmd = args[0]
    if cmd == "list":
        data = _read(path)
        if not data:
            print(f"{path}: no override rows yet (header only or absent)")
            return 0
        print(f"{path}: {len(data)} override row(s)")
        for t in sorted(data):
            r = data[t]
            print(f"  {t:<6} sector={r.get('sector') or '-':<14} "
                  f"status={r.get('status') or '-':<10} note={r.get('note', '')}")
        return 0
    if cmd == "add":
        if len(args) < 4:
            sys.stderr.write("add needs TICKER SECTOR STATUS [NOTE]\n"
                             + USAGE + "\n")
            return 2
        ticker, sector, status = args[1].upper(), args[2].lower(), args[3].lower()
        note = " ".join(args[4:])
        if status not in KNOWN_STATUSES:
            sys.stderr.write(f"status must be one of {KNOWN_STATUSES} "
                             f"(got {status!r})\n")
            return 3
        # v1.8.2 (W6): warn on a sector that differs from the engine's own
        # group for the ticker (fail soft when quality is unavailable)
        mismatch = _sector_mismatch_note(ticker, sector)
        if mismatch:
            sys.stderr.write(mismatch + "\n")
        data = _read(path)
        data[ticker] = {"sector": sector, "status": status, "note": note}
        _write(path, data)
        print(f"override added: {ticker} sector={sector or '-'} "
              f"status={status} note={note or '-'} -> {path}")
        print("the next run's universe drops it from the ACTIVE refs when "
              "status=delisted/renamed; master's negative cache (N5) also "
              "stops refetching a 404-ing ticker for the TTL")
        return 0
    if cmd == "remove":
        if len(args) < 2:
            sys.stderr.write("remove needs TICKER\n" + USAGE + "\n")
            return 2
        ticker = args[1].upper()
        data = _read(path)
        if ticker not in data:
            sys.stderr.write(f"{ticker} has no override row in {path}\n")
            return 2
        data.pop(ticker)
        _write(path, data)
        print(f"override removed: {ticker} -> {path}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
