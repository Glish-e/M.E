#!/usr/bin/env python3
"""W1 split planner: AST analysis of master.py top-level defs/classes.

Buckets the top-level definitions into the planned v1.8.0 modules
(me/core.py, me/errors.py, me/render.py, me/cli.py, me/backtest.py,
me/risk.py, master.py-remainder) by line range, then reports, for each
bucket, which GLOBAL names it references that are defined in a
DIFFERENT bucket. Read-only: prints the dependency matrix; exit 0.

Run: python3 scripts/w18_split_plan.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "master.py"

# Planned buckets: (module_name, start_line, end_line_exclusive).
# Boundaries chosen on section-comment borders from the structure map.
BUCKETS = [
    ("me/core.py",    174,  216),   # imports + version + __all__ (master re-exports)
    ("me/core.py",    217,  1161),  # CONFIG + dataclasses + shared helpers
    ("master.py",     1162, 2407),  # layers L1-L3 + ml helpers
    ("me/risk.py",    2408, 2776),  # size_portfolio + risk_ctx_out cluster
    ("master.py",     2777, 2911),  # RiskLayer + build_layers + stub registry
    ("me/core.py",    2911, 3020),  # _BUCKET_ETF + macro glue + ruleset/base conviction (pure)
    ("master.py",     3020, 3305),  # fuse cluster
    ("me/errors.py",  3305, 3335),  # MasterError + phase registry
    ("master.py",     3336, 4303),  # context/pipeline/provenance
    ("me/render.py",  4304, 5518),  # ANSI consts + strip_ansi ... json_payload
    ("me/cli.py",    5519, 5808),  # MasterParser/build_parser/_apply_mode/_validate_ns
    ("me/core.py",    5808, 5857),  # _CSV_DANGER/_csv_safe/atomic writes
    ("master.py",     5857, 5996),  # csv writer/probe/check/selftest
    ("me/core.py",    5997, 6013),  # _engines_sha256
    ("master.py",     6013, 6290),  # freeze/replay
    ("me/backtest.py", 6291, 6879),  # _BT_* + _bt_* + run_backtest
    ("me/errors.py",  6880, 6889),  # _code_registry
    ("master.py",     6889, 7382),  # doctor/_cli_run/wizard/main
]


def load():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    defs = []  # (name, lineno, end_lineno, kind)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs.append((node.name, node.lineno, node.end_lineno or node.lineno,
                         "class" if isinstance(node, ast.ClassDef) else "def"))
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    defs.append((t.id, node.lineno, node.end_lineno or node.lineno,
                                 "assign"))
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                defs.append((node.target.id, node.lineno,
                             node.end_lineno or node.lineno, "assign"))
    return tree, defs


def bucket_of(line: int) -> str:
    for name, a, b in BUCKETS:
        if a <= line < b:
            return name
    return "?"


def main() -> int:
    tree, defs = load()
    own = {}  # module -> set of top-level names defined there
    for name, ln, _end, _k in defs:
        own.setdefault(bucket_of(ln), set()).add(name)

    # name -> defining module (first definition wins; no dupes expected)
    where = {}
    for name, ln, _end, _k in defs:
        where.setdefault(name, bucket_of(ln))

    # collect Name loads per top-level def, via per-node walk
    edges = {}  # (from_mod, to_mod) -> set(names)
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef, ast.Assign)):
            continue
        src_mod = bucket_of(node.lineno)
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                tgt = where.get(sub.id)
                if tgt and tgt != src_mod and sub.id not in ("sys", "os", "json",
                                                             "time", "math", "re",
                                                             "argparse", "types",
                                                             "pathlib", "datetime"):
                    edges.setdefault((src_mod, tgt), set()).add(sub.id)

    mods = sorted({m for m, _a, _b in BUCKETS})
    print("cross-module global references (from -> to: names):")
    for a in mods:
        outs = {b: names for (x, b), names in edges.items() if x == a}
        if not outs:
            continue
        print(f"\n[{a}] uses:")
        for b in sorted(outs):
            names = sorted(outs[b])
            print(f"   -> {b} ({len(names)}): {', '.join(names[:24])}"
                  + (" ..." if len(names) > 24 else ""))

    # module sizes by line span
    print("\nplanned sizes (lines, approx):")
    agg = {}
    for name, a, b in BUCKETS:
        agg[name] = agg.get(name, 0) + (b - a)
    for m in sorted(agg):
        print(f"   {m:16s} {agg[m]:6d}")
    total = sum(agg.values())
    print(f"   {'TOTAL':16s} {total:6d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
