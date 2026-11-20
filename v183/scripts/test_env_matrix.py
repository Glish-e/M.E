#!/usr/bin/env python3
"""B-2 gate (v1.7.0-dev): the whole suite green across dates / env vars /
blocked deps — the hermeticity proof the v1.5.0 handoff claimed and the
reviewer disproved (1 failure on sklearn 1.9.1, 7 under MASTER_NET=offline).

Cells:
  1  baseline              (MASTER_NET unset, MASTER_STUBS unset, real clock)
  2  MASTER_NET=offline
  3  MASTER_STUBS=1
  4  sklearn+joblib import blocked (sys.modules pinned to None)
  5-8 four pinned dates    (Monday, year end, Sunday, leap day)
  9  MASTER_NET=offline + MASTER_STUBS=1 (the section-7 gate)

v1.4.1's harness DEFINED a FakeDate but never installed it (dead code —
its "date independence" evidence was invalid). This port pins the clock
for real: master/ml_dataset/ml_train get a date subclass whose today()
returns the pin. The global datetime module is NEVER patched — that
breaks pandas' Timestamp.date() (the Phase-0 harness bug, defect C-2).

Usage: python3 scripts/test_env_matrix.py [substring-filter]
Output: one line per cell + up to 3 failure details; exit 1 if any cell
failed. Write it to evidence: the paste for the phase gate.
"""
from __future__ import annotations

import datetime as _dt
import io
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DATES = [("2027-03-01 (Monday)", "2027-03-01"),
         ("2026-12-31 (year end)", "2026-12-31"),
         ("2025-02-01 (Sunday)", "2025-02-01"),
         ("2028-02-29 (leap)", "2028-02-29")]   # v1.4.1 pinned "2026-02-29",
# which is not a real date (2026 is not a leap year) — that cell never ran;
# the REAL leap day 2028-02-29 is used here.

_PURGE = ("master", "test_master", "ml_dataset", "ml_train")


def _make_pin_date(pin: _dt.date):
    class PinnedDate(_dt.date):
        @classmethod
        def today(cls):
            return pin
    PinnedDate.__doc__ = _dt.date.__doc__
    return PinnedDate


def run_suite(label: str, pin: _dt.date | None = None,
              block: tuple[str, ...] = ()) -> tuple[int, int, int, list[str]]:
    """Fresh-import the suite, pin the clock on the modules under test,
    optionally block sklearn/joblib, run everything, report."""
    for mod in tuple(sys.modules):
        if mod in _PURGE or mod.startswith(("master_", "test_")):
            del sys.modules[mod]
    saved: dict[str, object] = {}
    import importlib.util
    for name in block:
        saved[name] = sys.modules.pop(name, None)
        # C-6 (phase-3 finding): purge every cached SUBMODULE too — in a
        # sequential run the earlier cells leave sklearn.impute/... fully
        # imported, and `from sklearn.X import Y` reads those entries
        # without ever consulting sys.modules['sklearn'], so the blocked
        # cell was not fully hermetic (surfaced by phase 3's per-fold
        # selection test, which fit a real pipeline through _pipe).
        for sub in [m for m in tuple(sys.modules) if m.startswith(name + ".")]:
            saved[sub] = sys.modules.pop(sub)
        if importlib.util.find_spec(name) is not None:
            sys.modules[name] = None          # block the import
    patched: dict[str, object] = {}
    try:
        import master
        import ml_dataset                   # noqa: F401
        import ml_train                     # noqa: F401
        if pin is not None:
            pinned = _make_pin_date(pin)
            # v1.8.0 (W7): the module split moved date.today() callers
            # into me/* (cli validation, render header, backtest) — the
            # pin must cover every module that reads the clock at runtime,
            # else the pinned cells validate against the REAL today.
            for mod_name in ("master", "ml_dataset", "ml_train",
                             "me.core", "me.errors", "me.risk",
                             "me.render", "me.cli", "me.backtest"):
                mod = sys.modules[mod_name]
                if hasattr(mod, "date"):
                    patched[mod_name] = getattr(mod, "date")
                    setattr(mod, "date", pinned)
                # v1.8.0: some me/* modules legitimately import no date
                # (the W1 lint trim removed unused imports) — skipped.
        import test_master
        suite = unittest.defaultTestLoader.loadTestsFromModule(test_master)
        res = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        fails = [f"{t}: {tb.strip().splitlines()[-1][:110]}"
                 for t, tb in (res.failures + res.errors)[:8]]
        n = res.testsRun
        print(f"{label:<42s} ran={n:<4d} failures={len(res.failures)} "
              f"errors={len(res.errors)} skipped={len(res.skipped)}")
        for line in fails:
            print(f"    FAIL {line}")
        return len(res.failures), len(res.errors), len(res.skipped), \
            [f"{t}" for t, _ in (res.failures + res.errors)]
    finally:
        for mod_name, real in patched.items():
            if mod_name in sys.modules:
                setattr(sys.modules[mod_name], "date", real)
        for name, m in saved.items():
            if m is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = m


def main() -> int:
    flt = sys.argv[1] if len(sys.argv) > 1 else ""
    print("TEST ENV MATRIX — v1.8.0-dev (B-2 gate, pins widened to me/*): dates pinned "
          "ON THE MODULES (C-2 fixed), deps blocked, env pinned")
    print("=" * 76)
    print(f"interpreter: python {sys.version.split()[0]} · "
          f"numpy {__import__('numpy').__version__}")
    for lib in ("sklearn", "joblib"):
        try:
            print(f"            {lib} {__import__(lib).__version__}")
        except Exception:
            print(f"            {lib} ABSENT")
    print("=" * 76)
    bad = 0
    cells: list[tuple[str, dict]] = [
        ("baseline (no ambient pins)", {}),
        ("env MASTER_NET=offline", {"MASTER_NET": "offline"}),
        ("env MASTER_STUBS=1", {"MASTER_STUBS": "1"}),
        ("env MASTER_NET=offline MASTER_STUBS=1",
         {"MASTER_NET": "offline", "MASTER_STUBS": "1"}),
    ]
    for label, env in cells:
        if flt and flt not in label:
            continue
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            f, e, _s, _t = run_suite(label)
            bad += f + e
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    if not flt or flt in "sklearn+joblib import blocked":
        f, e, _s, _t = run_suite("sklearn+joblib import blocked",
                                 block=("sklearn", "joblib"))
        bad += f + e
    for label, ds in DATES:
        if flt and flt not in label and flt not in "date pinned":
            continue
        y, m, d = (int(x) for x in ds.split("-"))
        try:
            pin = _dt.date(y, m, d)
        except ValueError:
            print(f"{label:<42s} invalid date — NOT RUN")
            continue
        f, e, _s, _t = run_suite(f"date pinned {label}", pin=pin)
        bad += f + e
    print("=" * 76)
    print("MATRIX VERDICT: " + ("ALL CELLS GREEN" if bad == 0
                                else f"{bad} FAILURE(ES) — NOT HERMETIC"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
