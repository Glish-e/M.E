#!/usr/bin/env python3
"""DECISION PATH (audit scope), AST-based, read-only.

PHASE 2 PORT (v1.7.0-dev): ported by function name from v1.4.1's
scripts/decision_path.py; every seed below was verified present on this
base before the port (the v1.5.0 final phase kept the entry-point names).

Starting from the decision entry points (fuse_candidate, size_portfolio,
the layer adapters incl. freshness/veto, the ML overlay and the output
writers), compute the transitive closure of every function, method and
constant that can change an action, a conviction, a weight, a status, a
data-freshness label or a dataset row. That closure is the audit scope.

Usage:  python3 scripts/decision_path.py
Exit 0 = closure computed; exit 2 = file/parse failure.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# master.py seeds: entry points named by the phase-8 spec + the orchestrator
# that feeds them and the writers that publish their output.
ENTRY_FUNCS = [
    "run_pipeline", "_run_pipeline_inner", "_build_context", "_parse_layers",
    "fuse", "fuse_candidate", "funnel_shortlist", "_apply_overlays",
    "size_portfolio", "risk_ctx_out", "json_payload", "_write_csv",
    "_resolve_exit", "_aggregate_warnings", "_validate_ns", "_apply_mode",
]
# Layer classes: run() + prefetch() + their private helpers (adapters).
ENTRY_CLASSES = ["MacroLayer", "QualityLayer", "EarningsLayer", "MLLayer",
                 "RiskLayer", "LayerBase"]
# ml_dataset functions master calls at inference time (the ONE feature source)
ML_DATASET_SEEDS = ["record_from_parts", "date_features", "macro_features",
                    "macro_feature_names"]
# ml_train decision-relevant parts (label/split/embargo/calibration/pin):
# matched by name over the module's top-level functions.
ML_TRAIN_PAT = ("split", "embargo", "purge", "calib", "pin", "label",
                "train", "valid", "activate", "save", "walk", "fold",
                "feature", "brier", "rank_ic", "verdict", "load", "manifest")

ENGINE_MODULES = {"meds": "meds.py", "quality": "quality.py",
                  "earnings_engine": "earnings_engine.py"}


class ModuleMap:
    def __init__(self, path: Path) -> None:
        self.path = path
        src = path.read_text(encoding="utf-8")
        self.tree = ast.parse(src, filename=str(path))
        self.lines = src.count("\n") + 1
        self.funcs: dict[str, ast.AST] = {}      # qualname -> node
        self.classes: dict[str, ast.ClassDef] = {}
        self.consts: dict[str, ast.AST] = {}     # module-level NAME -> node
        self.cfg_keys: set[str] = set()          # _cfg("KEY", ...) names
        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.funcs[node.name] = node
            elif isinstance(node, ast.ClassDef):
                self.classes[node.name] = node
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        self.funcs[f"{node.name}.{sub.name}"] = sub
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        self.consts[t.id] = node
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                self.consts[node.target.id] = node
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                f = node.value.func
                if isinstance(f, ast.Name) and f.id == "_cfg" and node.value.args:
                    a = node.value.args[0]
                    if isinstance(a, ast.Constant):
                        self.cfg_keys.add(str(a.value))


def class_of(qual: str) -> str:
    return qual.split(".", 1)[0] if "." in qual else ""


def analyse(mod: ModuleMap, seeds: list[str], label: str,
            externals: dict[str, set[str]] | None = None) -> dict:
    """Transitive closure from seeds within ONE module. externals (optional)
    collects module.attr calls leaving this module (keyed by module name)."""
    seen: set[str] = set()
    frontier = [s for s in seeds if s in mod.funcs]
    missing = [s for s in seeds if s not in mod.funcs]
    cfg_used: set[str] = set()
    consts_used: set[str] = set()
    while frontier:
        cur = frontier.pop()
        if cur in seen:
            continue
        seen.add(cur)
        node = mod.funcs[cur]
        cls = class_of(cur)
        for n in ast.walk(node):
            if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) \
                    and n.value.id == "CONFIG":
                s = n.slice
                if isinstance(s, ast.Constant):
                    cfg_used.add(str(s.value))
            if isinstance(n, ast.Call):
                f = n.func
                if isinstance(f, ast.Name):
                    if f.id in mod.funcs:
                        frontier.append(f.id)
                    if f.id == "_native_grade" and n.args and isinstance(n.args[0], ast.Constant):
                        cfg_used.add(str(n.args[0].value))   # indirect key
                elif isinstance(f, ast.Attribute):
                    base = f.value
                    if isinstance(base, ast.Name):
                        if base.id == "self" and cls and f"{cls}.{f.attr}" in mod.funcs:
                            frontier.append(f"{cls}.{f.attr}")
                        elif base.id in mod.classes and f"{base.id}.{f.attr}" in mod.funcs:
                            frontier.append(f"{base.id}.{f.attr}")
                        elif externals is not None and base.id not in (
                                "self", "CONFIG", "os", "sys", "time", "json",
                                "re", "argparse", "statistics", "types", "Path",
                                "date", "timedelta", "datetime"):
                            externals.setdefault(base.id, set()).add(f.attr)
                    elif isinstance(base, ast.Call):     # e.g. quality.TickerRef(...)()
                        pass
            if isinstance(n, ast.Name) and n.id in mod.consts:
                consts_used.add(n.id)
    fn_lines = 0
    for q in seen:
        nd = mod.funcs[q]
        fn_lines += (getattr(nd, "end_lineno", getattr(nd, "lineno", 0))
                     - getattr(nd, "lineno", 0) + 1)
    return {"label": label, "funcs": seen, "n_funcs": len(seen),
            "fn_lines": fn_lines, "pct": 100.0 * fn_lines / mod.lines,
            "cfg_used": cfg_used, "consts_used": consts_used,
            "missing_seeds": missing, "module_lines": mod.lines}


def main() -> int:
    master = ModuleMap(ROOT / "master.py")
    externals: dict[str, set[str]] = {}

    seeds = list(ENTRY_FUNCS)
    for cls in ENTRY_CLASSES:
        seeds += [q for q in master.funcs if q.startswith(cls + ".")]
    m = analyse(master, seeds, "master.py", externals)

    # engine closures: entry points = functions master actually calls on them
    eng_info: dict[str, dict] = {}
    for mod_name, fname in ENGINE_MODULES.items():
        em = ModuleMap(ROOT / fname)
        calls = set(externals.get(mod_name, ()))
        eseed: list[str] = []
        for c in sorted(calls):
            if c in em.funcs:
                eseed.append(c)
            elif c in em.classes:                      # constructor + methods master uses
                eseed.append(f"{c}.__init__")
                for known in ("analyze", "signals", "history", "prices"):
                    if f"{c}.{known}" in em.funcs:
                        eseed.append(f"{c}.{known}")
        eng_info[mod_name] = analyse(em, eseed, fname)

    # ml_dataset: inference-time feature source
    ml_d = ModuleMap(ROOT / "ml_dataset.py")
    d = analyse(ml_d, ML_DATASET_SEEDS, "ml_dataset.py")

    # ml_train: decision-relevant by name pattern (artifacts feed MLLayer)
    ml_t = ModuleMap(ROOT / "ml_train.py")
    t_seeds = [q for q in ml_t.funcs if "." not in q
               and any(p in q.lower() for p in ML_TRAIN_PAT)]
    t = analyse(ml_t, t_seeds, "ml_train.py")

    # ---- report -----------------------------------------------------------
    out: list[str] = []
    A = out.append
    A("DECISION PATH — audit scope (AST closure, read-only; v1.4.1 port)")
    A("=" * 72)
    A(f"base: master.py v{ast.literal_eval(next(n.value for n in master.tree.body if isinstance(n, ast.Assign) and any(getattr(t, 'id', '') == '__version__' for t in n.targets)))}")
    A("")
    A("[1] CLOSURE SIZE")
    A(f"  master.py      : {m['n_funcs']:4d} functions/methods, {m['fn_lines']:5d} lines "
      f"({m['pct']:.0f}% of {m['module_lines']})")
    for k in ("meds", "quality", "earnings_engine"):
        e = eng_info[k]
        A(f"  {k + '.py':15s}: {e['n_funcs']:4d} functions/methods, {e['fn_lines']:5d} lines "
          f"({e['pct']:.0f}% of {e['module_lines']})  entries: {len(e['funcs']) and ''}"
          f"from {len(externals.get(k, ()))} adapter call(s)")
    A(f"  ml_dataset.py  : {d['n_funcs']:4d} functions/methods, {d['fn_lines']:5d} lines "
      f"({d['pct']:.0f}% of {d['module_lines']})")
    A(f"  ml_train.py    : {t['n_funcs']:4d} functions/methods, {t['fn_lines']:5d} lines "
      f"({t['pct']:.0f}% of {t['module_lines']})  [label/split/embargo/calib/pin]")
    tot = m['n_funcs'] + sum(e['n_funcs'] for e in eng_info.values()) + d['n_funcs'] + t['n_funcs']
    totl = m['fn_lines'] + sum(e['fn_lines'] for e in eng_info.values()) + d['fn_lines'] + t['fn_lines']
    A(f"  TOTAL          : {tot} functions, {totl} lines audited of "
      f"{sum(x.lines for x in [master, ml_d, ml_t] + [ModuleMap(ROOT / f) for f in ENGINE_MODULES.values()])} lines (7 files)")
    if m["missing_seeds"]:
        A(f"  NOTE seeds not found in master.py: {', '.join(m['missing_seeds'])}")
    A("")
    A("[2] EXTERNAL ENGINE CALLS FROM master.py CLOSURE")
    for mod in sorted(externals):
        if mod in ENGINE_MODULES or mod in ("ml_dataset", "test_master", "np", "pd"):
            A(f"  {mod}: {', '.join(sorted(externals[mod]))}")
    A("")
    A("[3] CONFIG KEYS READ INSIDE THE master.py CLOSURE "
      f"({len(m['cfg_used'])} of {len(master.cfg_keys)})")
    A("  " + ", ".join(sorted(m['cfg_used'])))
    unused = master.cfg_keys - m["cfg_used"]
    if unused:
        A(f"  CONFIG keys NOT in the closure: {', '.join(sorted(unused))}")
    A("")
    A("[4] MODULE CONSTANTS REFERENCED BY THE CLOSURE")
    A("  " + ", ".join(sorted(m["consts_used"])))
    A("")
    for blk, info in (("master.py", m), ("meds.py", eng_info["meds"]),
                      ("quality.py", eng_info["quality"]),
                      ("earnings_engine.py", eng_info["earnings_engine"]),
                      ("ml_dataset.py", d), ("ml_train.py", t)):
        A(f"[5.{list([m, eng_info['meds'], eng_info['quality'], eng_info['earnings_engine'], d, t]).index(info) + 1}] {blk} CLOSURE FUNCTIONS")
        for q in sorted(info["funcs"]):
            A(f"    {q}")
        A("")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
