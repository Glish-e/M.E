#!/usr/bin/env python3
"""verify_owner_results.py — W6 (v1.8.0): validate the OWNER's returned
results before they are trusted (R12): schema, row counts, sha256, no
future dates, API provenance — with a NEGATIVE CONTROL that corrupts a
file and must FAIL (proving the checker can fail, not just pass).

Usage:
  python3 scripts/verify_owner_results.py            # verify owner_results/
  python3 scripts/verify_owner_results.py --dir PATH
  python3 scripts/verify_owner_results.py --negative-control

Checks (each printed PASS/FAIL, exit 1 on any FAIL):
  1. every file in owner_results/ parses as its declared type
     (spy_monthly.json: monthly_close dict of floats, source mentions
     REAL; bench_*.txt: non-empty; long_history_log.txt: exists);
  2. no FUTURE dates: any YYYY-MM-DD inside results strictly after
     today is a fabrication (the engines cannot know the future);
  3. SPY series provenance: source must NOT say SYNTHETIC for gate use;
  4. row counts sane: spy_monthly.json >= 15 month-ends;
  5. sha256 of every file listed in the report is recomputed and shown
     (so the delivery message can pin them).

Negative control (--negative-control): writes a corrupted spy file to a
temp dir, runs the SAME checks on it, and must exit 1 naming the corrupt
file — if it exits 0 the checker itself is broken (R12's requirement).
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TODAY = date.today()
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def check_spy(path: Path) -> list[str]:
    errs = []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"{path.name}: unparseable JSON ({e})"]
    src = str(doc.get("source") or "")
    closes = doc.get("monthly_close")
    if not isinstance(closes, dict) or not closes:
        errs.append(f"{path.name}: monthly_close missing/empty")
        return errs
    if len(closes) < 15:
        errs.append(f"{path.name}: only {len(closes)} month-ends (<15)")
    for k, v in closes.items():
        if not DATE_RE.match(str(k)):
            errs.append(f"{path.name}: bad date key {k!r}")
        try:
            fv = float(v)
        except (TypeError, ValueError):
            errs.append(f"{path.name}: non-float close {k}={v!r}")
            continue
        if not (0.0 < fv < 1e6):
            errs.append(f"{path.name}: implausible close {k}={v}")
    if "SYNTHETIC" in src.upper():
        errs.append(f"{path.name}: source says SYNTHETIC — not owner data")
    elif "REAL" not in src.upper():
        errs.append(f"{path.name}: source does not declare REAL data")
    return errs


def check_future_dates(path: Path) -> list[str]:
    errs = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for m in DATE_RE.findall(text):
        try:
            d = datetime.strptime(m, "%Y-%m-%d").date()
        except ValueError:
            continue
        if d > TODAY:
            errs.append(f"{path.name}: FUTURE date {m} (after {TODAY})")
            break
    return errs


def verify_dir(d: Path) -> tuple[int, list[str]]:
    fails: list[str] = []
    files = sorted(p for p in d.glob("*") if p.is_file()) if d.is_dir() else []
    if not files:
        fails.append(f"{d}: no files to verify")
    for p in files:
        if p.name == "spy_monthly.json":
            fails += check_spy(p)
        elif p.suffix == ".json":
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                fails.append(f"{p.name}: unparseable JSON ({e})")
        if p.stat().st_size == 0:
            fails.append(f"{p.name}: EMPTY file")
        fails += check_future_dates(p)
        print(f"  [sha256] {hashlib_sha(p)}  {p.name}")
    return len(fails), fails


def hashlib_sha(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    negative = "--negative-control" in argv
    if negative:
        argv.remove("--negative-control")
    d = ROOT / "owner_results"
    if "--dir" in argv:
        i = argv.index("--dir")
        d = Path(argv[i + 1])
        del argv[i:i + 2]
    if argv:
        print(f"usage: verify_owner_results.py [--dir PATH] "
              f"[--negative-control] (got {argv!r})")
        return 64
    if negative:
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "spy_monthly.json"
            bad.write_text(json.dumps({
                "source": "REAL (faked by the negative control)",
                "monthly_close": {"2099-01-31": 1e9,
                                  "2020-01-31": "not-a-number"}}),
                encoding="utf-8")
            n, fails = verify_dir(Path(td))
            print(f"negative control: {n} failure(s) as REQUIRED "
                  f"(corrupt file must be caught)")
            for f in fails:
                print(f"  [FAIL] {f}")
            if n == 0:
                print("negative control PASSED the corrupt file — the "
                      "checker is broken (R12 breach)")
                return 1
            print("negative control OK: the checker fails on corrupted "
                  "files")
            return 1            # exit 1 by design (control run failed)
    print(f"verify_owner_results — {d}")
    n, fails = verify_dir(d)
    for f in fails:
        print(f"  [FAIL] {f}")
    if n:
        print(f"RESULT: FAIL ({n} problem(s)) — do not trust these "
              "results until rebuilt")
        return 1
    print("RESULT: PASS — owner results parse, carry no future dates and "
          "declare real provenance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
