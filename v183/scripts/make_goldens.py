#!/usr/bin/env python3
"""make_goldens.py — regenerate the 12 report goldens (phase 5, C-4).

WHAT THE GOLDENS ARE
  Byte-exact fixtures of the REAL CLI report, 3 modes x 4 widths
  (colour / plain / ascii at 40 / 70 / 110 / 160), captured from a REAL
  MASTER_STUBS=1 + MASTER_NET=offline run of master.main() with a FROZEN
  CLOCK (2026-11-13) — deterministic stub data, no network, no engines,
  no sklearn (stub layers import none of them).

WHAT IS MASKED (disclosed, and ONLY these two volatile classes)
  1. ISO dates -> "FROZEN-DATE": the C-4 mandate is that NO golden
     contains a date, so the harness masks every date token after the
     capture. The frozen clock makes all BEHAVIOUR date-deterministic;
     the rendered as-of itself is masked to keep the files dateless.
  2. Wall-clock durations ("0.4s", "12.5s") -> "Xs": timings are not
     renderable deterministically; masking them is disclosed here and in
     evidence/phase5_gate.txt. Nothing else is touched.

INVARIANTS (tested in TestGoldensC4)
  * byte-exact: re-capturing now reproduces the file bit-for-bit;
  * strip_ansi(colour golden) == plain golden;
  * no golden contains a date (checker with a failing negative control);
  * goldens say SYNTHETIC (stub runs never look like real data);
  * locale/terminal-independent (LC_ALL/TERM/COLUMNS do not change bytes);
  * sklearn-independent (a blocking sklearn shim does not change bytes);
  * regeneration ONLY via the explicit --regen flag (refuses otherwise).

Usage:
  python3 scripts/make_goldens.py            -> refuses, exit 2
  python3 scripts/make_goldens.py --regen    -> regenerates + verifies
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDENS = ROOT / "goldens"
MODES = ("colour", "plain", "ascii")
WIDTHS = (40, 70, 110, 160)
AS_OF = "2026-11-13"                      # the frozen clock
_TICKERS = ["MU", "NVDA", "AAPL"]         # small, fixed universe

_DATE_RE = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")
_DUR_RE = re.compile(r"\b\d+(?:\.\d+)?s\b")

_BOOTSTRAP = r'''
import contextlib
import io
import sys
from datetime import date
sys.path.insert(0, {root!r})
import test_master as tm

argv = {argv!r}
buf = io.StringIO()
with tm._pin_today(date({y}, {m}, {d})):
    with contextlib.redirect_stdout(buf):
        try:
            tm.master.main(argv)
        except SystemExit as e:
            if e.code not in (0, 1):
                raise
text = buf.getvalue()
sys.stdout.write(text)
'''


def golden_date_violations(text: str) -> list:
    """Every date token found in a golden (or any text) — the checker the
    C-4 test uses; MUST flag an injected date (negative control)."""
    return _DATE_RE.findall(text)


def _mask(text: str) -> str:
    text = _DATE_RE.sub("FROZEN-DATE", text)
    text = _DUR_RE.sub("Xs", text)
    return text


def capture(mode: str, width: int, **env_over) -> str:
    """One real CLI stub run (frozen clock, offline, stubs), masked."""
    argv = ["--as-of", AS_OF, "--width", str(width),
            "--top", "10", "--min-conviction", "0"]
    if mode == "colour":
        argv += ["--color", "always"]
    elif mode == "plain":
        argv += ["--plain"]
    elif mode == "ascii":
        argv += ["--ascii", "--no-color"]
    else:
        raise ValueError(f"mode {mode!r} not in (colour, plain, ascii)")
    argv += _TICKERS

    env = dict(os.environ)
    env.update(MASTER_STUBS="1", MASTER_NET="offline", LC_ALL="C",
               TERM="xterm")
    for k in ("NO_COLOR", "FORCE_COLOR", "CLICOLOR_FORCE", "WT_SESSION",
              "TERM_PROGRAM", "ConEmuANSI", "COLUMNS", "FREDAPI",
              "FRED_API_KEY"):
        env.pop(k, None)
    env.update({k: str(v) for k, v in env_over.items()})

    code = _BOOTSTRAP.format(root=str(ROOT), argv=argv, y=2026, m=11, d=13)
    p = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), env=env,
                       capture_output=True, text=True, timeout=180)
    if p.returncode not in (0, 1):
        raise RuntimeError(f"golden capture failed (exit {p.returncode}): "
                           f"{(p.stderr or p.stdout)[-400:]}")
    return _mask(p.stdout)


def verify() -> list:
    """Post-regeneration checks; returns a list of violations (empty=ok)."""
    bad = []
    strip = _STRIP = None
    for w in WIDTHS:
        c = (GOLDENS / f"golden_colour_{w}.txt").read_text(encoding="utf-8")
        p = (GOLDENS / f"golden_plain_{w}.txt").read_text(encoding="utf-8")
        _STRIP_RE = re.compile(r"\x1b\[[0-9;]*m")
        if _STRIP_RE.sub("", c) != p:
            bad.append(f"strip_ansi(colour_{w}) != plain_{w}")
    for f in sorted(GOLDENS.glob("golden_*.txt")):
        text = f.read_text(encoding="utf-8")
        if golden_date_violations(text):
            bad.append(f"{f.name}: date leaked")
        if "SYNTHETIC" not in text:
            bad.append(f"{f.name}: no SYNTHETIC marker")
    return bad


def main(argv: list) -> int:
    if "--regen" not in argv:
        sys.stderr.write(
            "refusing: goldens regenerate ONLY via --regen (C-4 discipline; "
            "the files are fixtures, not scratch output)\n")
        return 2
    GOLDENS.mkdir(exist_ok=True)
    for mode in MODES:
        for w in WIDTHS:
            text = capture(mode, w)
            (GOLDENS / f"golden_{mode}_{w}.txt").write_text(
                text, encoding="utf-8")
            print(f"wrote golden_{mode}_{w}.txt ({len(text)} bytes)")
    bad = verify()
    if bad:
        sys.stderr.write("VERIFY FAILED:\n  " + "\n  ".join(bad) + "\n")
        return 1
    print("verified: no dates, SYNTHETIC present, strip_ansi(colour)==plain")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
