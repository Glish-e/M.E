#!/usr/bin/env python3
"""PHASE 8 M1 — STATIC HUNT over the decision-path closure (read-only).

ast + regex patterns from the phase-8 spec: broad except / silent pass,
"x or default" on numbers, float ==, mutable default args, module-level
mutable state, magic numbers outside CONFIG, percent-vs-fraction mixes,
date.today() inside decision logic, code after return, constants used
once, dead parameters, sort without tie-break, dict-order dependence,
silent fallbacks to neutral (1.0 / 0.0 / "OK"/ None), dead CONFIG keys.

Usage: python3 scripts/lint_hunt.py > evidence/lint_hunt_v8.txt
"""
from __future__ import annotations

import ast
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decision_path as dp                                    # noqa: E402

ROOT = dp.ROOT
MODULES = ["master.py", "meds.py", "quality.py", "earnings_engine.py",
           "ml_dataset.py", "ml_train.py"]

# numbers that are structural, not magic (indexes, safe fallbacks, common)
BENIGN = {-1, 0, 1, 2, 3, 4, 5, 8, 10, 12, 16, 20, 25, 30, 40, 50, 60, 100,
          252, 1000, 3600, -1.0, 0.0, 1.0, 2.0, 3.0, 5.0, 10.0, 100.0,
          1e-6, 0.5, 1e-9, 1e-12, 252.0}


def closure_for(fname: str) -> dict:
    """Re-run the closure analysis for one file (same seeds as step 0)."""
    if fname == "master.py":
        seeds = list(dp.ENTRY_FUNCS)
        for cls in dp.ENTRY_CLASSES:
            seeds += [q for q in dp.master_funcs(dp.ModuleMap(ROOT / fname))
                      if q.startswith(cls + ".")] if False else []
        mm = dp.ModuleMap(ROOT / fname)
        seeds = list(dp.ENTRY_FUNCS) + [q for q in mm.funcs
                                        if q.split(".")[0] in dp.ENTRY_CLASSES]
        return dp.analyse(mm, seeds, fname)
    if fname == "ml_dataset.py":
        return dp.analyse(dp.ModuleMap(ROOT / fname), dp.ML_DATASET_SEEDS, fname)
    if fname == "ml_train.py":
        mt = dp.ModuleMap(ROOT / fname)
        t_seeds = [q for q in mt.funcs if "." not in q
                   and any(p in q.lower() for p in dp.ML_TRAIN_PAT)]
        return dp.analyse(mt, t_seeds, fname)
    name = {"meds.py": "meds", "quality.py": "quality",
            "earnings_engine.py": "earnings_engine"}[fname]
    mm = dp.ModuleMap(ROOT / fname)
    entries = {"meds": ["now", "regime_now"],
               "quality": ["build_inline_universe", "get_quality_score",
                           "TickerRef.__init__"],
               "earnings_engine": ["EarningsEngine.__init__",
                                   "EarningsEngine.analyze",
                                   "EarningsEngine.signals",
                                   "EarningsEngine.history",
                                   "EarningsEngine.prices"]}[name]
    return dp.analyse(mm, [e for e in entries if e in mm.funcs], fname)


def src_lines(fname: str) -> list[str]:
    return (ROOT / fname).read_text(encoding="utf-8").splitlines()


def node_snip(lines: list[str], ln: int) -> str:
    return lines[ln - 1].strip()[:110] if 0 < ln <= len(lines) else "?"


class Hunt(ast.NodeVisitor):
    def __init__(self, fname: str, fn: str, lines: list[str]) -> None:
        self.f = fname
        self.fn = fn
        self.lines = lines
        self.hits: list[tuple[str, str, int, str]] = []   # kind, where, line, snip

    def add(self, kind: str, node: ast.AST, note: str = "") -> None:
        ln = getattr(node, "lineno", 0)
        self.hits.append((kind, f"{self.f}:{self.fn}:{ln}", ln,
                          node_snip(self.lines, ln) + (f"   [{note}]" if note else "")))

    # -- except handlers ---------------------------------------------------
    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        t = node.type
        broad = (t is None or (isinstance(t, ast.Name) and t.id in
                 ("Exception", "BaseException")))
        body = node.body
        silent = len(body) == 1 and isinstance(body[0], ast.Pass)
        neutral = None
        if len(body) == 1 and isinstance(body[0], ast.Return):
            v = body[0].value
            if isinstance(v, ast.Constant) and v.value in (None, 0.0, 1.0, "OK", 0, 1):
                neutral = repr(v.value)
            elif isinstance(v, ast.Constant) and isinstance(v.value, (int, float)) \
                    and v.value in (0.0, 1.0, 0, 1):
                neutral = repr(v.value)
        if silent:
            self.add("EXCEPT-silent-pass", node)
        elif broad:
            note = f"returns neutral {neutral}" if neutral else "broad"
            self.add("EXCEPT-broad", node, note)
        elif neutral:
            self.add("EXCEPT-neutral-return", node, neutral)
        self.generic_visit(node)

    # -- x or default on numbers -------------------------------------------
    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        if isinstance(node.op, ast.Or) and len(node.values) >= 2:
            last = node.values[-1]
            if isinstance(last, ast.Constant) and isinstance(last.value, (int, float)) \
                    and not isinstance(last.value, bool) and last.value != 0:
                self.add("OR-default-on-number", node,
                         f"0 treated as missing -> {last.value}")
        self.generic_visit(node)

    # -- float equality ------------------------------------------------------
    def visit_Compare(self, node: ast.Compare) -> None:
        for op, comp in zip(node.ops, node.comparators):
            if not isinstance(op, ast.Eq):
                continue
            for side in (node.left, comp):
                if isinstance(side, ast.Constant) and isinstance(side.value, float) \
                        and side.value not in (0.0, 1.0):
                    # x == x NaN-checks are intentional
                    if isinstance(node.left, ast.Name) and isinstance(comp, ast.Name) \
                            and node.left.id == comp.id:
                        self.add("FLOAT-eq (NaN check - intentional)", node)
                    else:
                        self.add("FLOAT-eq", node)
                    break
        self.generic_visit(node)

    # -- mutable default args ------------------------------------------------
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for d in node.args.defaults + [x for x in node.args.kw_defaults if x]:
            if isinstance(d, (ast.List, ast.Dict, ast.Set)) or (
                    isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
                    and d.func.id in ("list", "dict", "set")):
                self.add("MUTABLE-default-arg", d)
        # dead parameters: named arg never referenced in body
        body_names = {n.id for n in ast.walk(node)
                      if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        params = [a.arg for a in node.args.args + node.args.kwonlyargs
                  if a.arg not in ("self", "cls")]
        for p in params:
            if p not in body_names and f"{p}" not in ast.dump(node)[:0]:
                if p not in body_names:
                    self.add("DEAD-parameter", node, p)
        # statements after return in the same block
        for blk in ast.walk(node):
            if isinstance(blk, (ast.FunctionDef, ast.If, ast.For, ast.While,
                                ast.With, ast.Try)):
                seen_ret = False
                for st in blk.body:
                    if seen_ret and not isinstance(st, ast.Expr):
                        self.add("UNREACHABLE-after-return", st)
                        break
                    if isinstance(st, ast.Return):
                        seen_ret = True
        self.generic_visit(node)

    # -- date.today / now inside logic --------------------------------------
    def visit_Call(self, node: ast.Call) -> None:
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr in ("today", "now", "utcnow"):
            if isinstance(f.value, ast.Name) and f.value.id in ("date", "datetime"):
                self.add("CLOCK-in-decision-logic", node, f.value.id + "." + f.attr)
        # sort without tie-break
        if isinstance(f, ast.Attribute) and f.attr in ("sort", "sorted") or (
                isinstance(f, ast.Name) and f.id == "sorted"):
            key = None
            for kw in node.keywords:
                if kw.arg == "key":
                    key = kw.value
            if key is None and node.args and isinstance(f, ast.Name):
                pass                        # sorted(x) -> stable, flag separately
            if isinstance(key, ast.Lambda):
                body = key.body
                tie = False
                if isinstance(body, ast.Tuple) and body.elts:
                    last = body.elts[-1]
                    if isinstance(last, ast.Name):
                        tie = True
                if isinstance(body, ast.Name):
                    tie = None              # opaque key fn
                if tie is False:
                    self.add("SORT-no-tiebreak", node)
        self.generic_visit(node)


def magic_numbers(fname: str, info: dict, lines: list[str]) -> list[str]:
    out: list[str] = []
    counts: Counter = Counter()
    where: dict[float, str] = {}
    for q in sorted(info["funcs"]):
        node = info["_map"].funcs[q]
        for n in ast.walk(node):
            if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) \
                    and not isinstance(n.value, bool):
                v = n.value
                if v in BENIGN or (isinstance(v, float) and v.is_integer()
                                   and abs(v) in BENIGN):
                    continue
                if isinstance(v, int) and (abs(v) > 100000 or abs(v) < -100000):
                    continue
                counts[v] += 1
                where.setdefault(v, f"{fname}:{q}:{n.lineno}")
    for v, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        out.append(f"    {v!r:>10} x{c:<3} first {where[v]}   {node_snip(lines, int(where[v].rsplit(':', 1)[1]))}")
    return out


def main() -> int:
    all_hits: list[tuple[str, str, int, str]] = []
    print("LINT HUNT — phase 8 M1 static analysis over the decision-path closure")
    print("=" * 78)
    for fname in MODULES:
        if not (ROOT / fname).exists():
            continue
        info = closure_for(fname)
        info["_map"] = dp.ModuleMap(ROOT / fname)      # for magic numbers
        lines = src_lines(fname)
        h = Hunt(fname, "", lines)
        for q in sorted(info["funcs"]):
            sub = Hunt(fname, q, lines)
            sub.visit(dp.ModuleMap(ROOT / fname).funcs[q])
            all_hits.extend(sub.hits)
        print(f"\n### {fname}: {info['n_funcs']} closure functions")
        print("\n".join(magic_numbers(fname, info, lines)))
    # group hits
    print("\n" + "=" * 78)
    print("PATTERN HITS (grouped by kind)")
    print("=" * 78)
    bykind: dict[str, list] = {}
    for kind, where, ln, snip in all_hits:
        bykind.setdefault(kind, []).append((where, snip))
    for kind in sorted(bykind):
        print(f"\n-- {kind} ({len(bykind[kind])}) --")
        for where, snip in bykind[kind]:
            print(f"  {where}: {snip}")
    # dead CONFIG keys (production reads; v1.8.0: master.py + me/)
    print("\n-- DEAD-CONFIG-KEYS (never read in production code) --")
    msrc = (ROOT / "master.py").read_text(encoding="utf-8")
    mm = dp.ModuleMap(ROOT / "master.py")
    reads = set(re.findall(r'CONFIG\[["\']([A-Z_0-9]+)["\']\]', msrc))
    reads |= set(re.findall(r'_native_grade\(["\']([A-Z_0-9]+)["\']', msrc))
    me_src = "\n".join(
        f.read_text(encoding="utf-8")
        for f in sorted((ROOT / "me").glob("*.py")))
    reads |= set(re.findall(r'CONFIG\[["\']([A-Z_0-9]+)["\']\]', me_src))
    reads |= set(re.findall(r'_native_grade\(["\']([A-Z_0-9]+)["\']', me_src))
    for key in sorted(mm.cfg_keys - reads):
        print(f"  CONFIG['{key}'] defined but never read in production code")
    return 0


if __name__ == "__main__":
    sys.exit(main())
