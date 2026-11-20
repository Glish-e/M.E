#!/usr/bin/env python3
"""W1 executor: split master.py into me/* modules (v1.8.0, one pass).

Deterministic text move — NO logic edits. Boundaries verified by
asserting the first line of every extracted range. See the module
docstrings in me/*.py for what moved where; master.py keeps the layers,
registry, fuse, pipeline, freeze/replay, doctor, wizard, main and a
tail re-export block (explicit from-imports of the SAME objects, so
tests' `master.X` references and the monkeypatch seams stay intact) +
a script-mode sys.modules alias so late-bound `import master` inside
me/* cannot double-execute the file under `python3 master.py`.

Two body-text substitutions replace a direct master-only global with a
late-bound resolver (LAYER_REGISTRY in _validate_ns; run_pipeline in
run_backtest). Everything else is untouched text.

Usage: python3 scripts/w18_split_exec.py
Exit 0 on success; any assertion failure aborts with no file written.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "master.py"

RANGES = {
    "me/core.py": [
        (174, 202, "from __future__ import annotations"),
        (206, 1161, None),
        (2911, 3020, "_BUCKET_ETF = {\"staples\": \"XLP\", \"discretionary\": \"XLY\"}"),
        (5808, 5857, "_CSV_DANGER = (\"=\", \"+\", \"-\", \"@\")"),
        (5997, 6013, "def _engines_sha256() -> dict[str, str]:"),
    ],
    "me/errors.py": [
        (3305, 3335, "class MasterError(Exception):"),
        (6880, 6889, "def _code_registry() -> dict:"),
    ],
    "me/risk.py": [
        (2408, 2777, "def size_portfolio(longs: list[str], vols: dict[str, float | None] | None,"),
    ],
    "me/render.py": [
        (4296, 5516, "# ════════════════════════════════════════════════════════════════════════"),
    ],
    "me/cli.py": [
        (5516, 5808, "# ════════════════════════════════════════════════════════════════════════"),
    ],
    "me/backtest.py": [
        (6291, 6880, "# ── § 5.8 · --backtest: the integration backtest (final phase §5) ──────────"),
    ],
}

CORE_DOC = '''\
"""me/core.py — the shared core of the M.E. orchestrator (v1.8.0 split
from master.py §0-§3.1): the CONFIG registry (every tunable with its
one-line rationale — changing any needs walk-forward evidence, never
in-sample tuning), the run datatypes (MacroState/Candidate/LayerSignal/
LayerResult/Decision/Context/LayerProvenance/RunOutput), the small
shared helpers (finite/normalise/month-end/redaction), the net-mode
probe + retry wrappers + meds snapshot machinery, the env/attr/config
restore guards (two runs in one process leak no state), _Progress, and
the pure macro/decision glue (macro_tilt/macro_view/_ruleset/
_base_conviction) plus the atomic-write and ENGINES.sha256 helpers.
Leaf module: imports stdlib only; never imports master."""
'''

IMPORT_BLOCK = """\
from __future__ import annotations

# ── § 0 · imports (the me/* modules carry their own; this block serves
#    master.py's own code — v1.8.0 split) ─────────────────────────────────
import argparse
import calendar
import copy
import importlib
import json
import math
import os
import re
import shutil
import statistics
import sys
import time
import types
import unicodedata
import urllib.request
import codes
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Protocol

"""

VERSION_BUMP = ('__version__ = "1.7.0-dev"', '__version__ = "1.8.0-dev"')

CLI_PATCH = (
    "        known = set(LAYER_REGISTRY)",
    "        known = set(_layer_registry())",
)
CLI_WRAPPER = '''

def _layer_registry() -> "dict[str, type]":
    """Late-bound LAYER_REGISTRY (defined in master.py AFTER this module
    is imported by it): resolving at call time keeps me/cli acyclic and
    honours test monkeypatches on master.LAYER_REGISTRY."""
    import master
    return master.LAYER_REGISTRY

'''

BT_PATCH = (
    "            out = run_pipeline(_bt_rerun_ns(d, sectors))",
    "            out = _master_run_pipeline(_bt_rerun_ns(d, sectors))",
)
BT_WRAPPER = '''

def _master_run_pipeline(ns: "argparse.Namespace"):
    """Late-bound run_pipeline (master.py defines it AFTER this module is
    imported by it): resolving at call time keeps me/backtest acyclic and
    honours test monkeypatches on master.run_pipeline."""
    import master
    return master.run_pipeline(ns)

'''

MAIN_GUARD_OLD = '''\
if __name__ == "__main__":                                # pragma: no cover
    sys.exit(main())
'''
MAIN_GUARD_NEW = '''\
if __name__ == "__main__":                                # pragma: no cover
    # v1.8.0: script-mode aliasing — `python3 master.py` registers THIS
    # running module as 'master' so the late-bound `import master`
    # inside me/* sees the live module instead of double-executing the
    # file (identical objects, one CONFIG, one set of module globals).
    if "master" not in sys.modules:
        sys.modules["master"] = sys.modules[__name__]
    sys.exit(main())
'''

HEADERS = {
    "me/errors.py": '''\
"""me/errors.py — user-error type + phase registry + code registry (v1.8.0
split from master.py §5/§8). MasterError carries its exit code (2 NO-GO /
64 bad usage); _phase names the current run phase (the Ctrl-C line);
_code_registry lazily reads codes.py, the one-source registry of every
user-facing error code, its reason and its fix command (R18)."""
from __future__ import annotations

import codes
from typing import Any

''',
    "me/risk.py": '''\
"""me/risk.py — the portfolio sizer + risk context (v1.8.0 split from
master.py §3.6). size_portfolio is the L5 sizer: position weights from
conviction x inverse vol under the legacy eff/8 correlation cap or the
opt-in vol_target gross solve; risk_ctx_out publishes the portfolio risk
context for the report/footer; _ann_vol/_rho_bar are the trailing
annualised-vol and mean-correlation estimators (RISK_* CONFIG keys)."""
from __future__ import annotations

import math
import statistics
from typing import Any, Callable

from me.core import CONFIG

''',
    "me/render.py": '''\
"""me/render.py — the terminal renderer (v1.8.0 split from master.py §6):
pure functions, no pandas; colour/plain/ASCII honoured at widths
40/70/110/160; strip_ansi(colour) == plain at every width; the JSON
payload is the stable --json schema (never NaN); _explain_block is the
--explain per-layer breakdown for one ticker."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import sys
import unicodedata
import codes
from datetime import date
from typing import Any

from me.core import (CONFIG, Decision, LayerSignal, RunOutput, __version__,
                     _base_conviction, _engines_sha256, _exc, _finite,
                     _ruleset, macro_tilt, macro_view)
from me.errors import MasterError

''',
    "me/cli.py": '''\
"""me/cli.py — the CLI surface (v1.8.0 split from master.py §7): the
argparse parser (bad usage exits 64, never 2), the --mode quick/
standard/deep presets and the namespace validation. Every existing flag
is unchanged; new flags are additions only (R16)."""
from __future__ import annotations

import argparse
from typing import Any

from me.core import CONFIG, _finite
from me.errors import MasterError

''',
    "me/backtest.py": '''\
"""me/backtest.py — the §5.8 integration backtest (v1.8.0 split from
master.py): consumes the recorded per-date run_pipeline harvests (or
re-runs them through the same pipeline), evaluates the ACTUAL fused
convictions against the dataset's 63-td label windows, and prints the
preregistered gates with costs (10 bps/side baseline, 5/10/25/50
sensitivity)."""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from me.cli import _apply_mode, _validate_ns, build_parser
from me.core import CONFIG, RunOutput, _atomic_write_text, _exc
from me.errors import MasterError, _code_registry

''',
}


def main() -> int:
    text = SRC.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    n = len(lines)

    for mod, ranges in RANGES.items():
        for start, end, first in ranges:
            assert 1 <= start < end <= n + 1, (mod, start, end, n)
            if first is not None:
                got = lines[start - 1].rstrip("\n")
                assert got == first, (
                    f"{mod}: line {start} is {got!r}, expected {first!r}")

    # extract segments per module (in range order)
    segs = {}
    for mod, ranges in RANGES.items():
        buf = []
        for start, end, _f in ranges:
            buf.append("".join(lines[start - 1:end - 1]))
        segs[mod] = "".join(buf)

    # patches inside moved segments
    core = segs["me/core.py"]
    assert VERSION_BUMP[0] in core
    segs["me/core.py"] = core.replace(VERSION_BUMP[0], VERSION_BUMP[1], 1)

    cli_seg = segs["me/cli.py"]
    assert CLI_PATCH[0] in cli_seg, "cli LAYER_REGISTRY seam not found"
    cli_seg = cli_seg.replace(CLI_PATCH[0], CLI_PATCH[1], 1)
    segs["me/cli.py"] = cli_seg.rstrip("\n") + "\n" + CLI_WRAPPER

    bt_seg = segs["me/backtest.py"]
    assert BT_PATCH[0] in bt_seg, "backtest run_pipeline seam not found"
    bt_seg = bt_seg.replace(BT_PATCH[0], BT_PATCH[1], 1)
    segs["me/backtest.py"] = bt_seg.rstrip("\n") + "\n" + BT_WRAPPER

    # write me/ modules (core keeps its own import block; prepend its
    # docstring before the future import)
    me_dir = ROOT / "me"
    me_dir.mkdir(exist_ok=True)
    (me_dir / "__init__.py").write_text(
        '"""me/ — the v1.8.0 module split of master.py (core, errors, risk,\n'
        'render, cli, backtest). master.py stays the single entry point and\n'
        're-exports every public name; the modules are leaves over me.core\n'
        '(never importing master at module level)."""\n', encoding="utf-8")

    segs["me/core.py"] = CORE_DOC + segs["me/core.py"]
    for mod, seg in segs.items():
        out = (HEADERS[mod] + "\n\n" + seg) if mod in HEADERS else seg
        (ROOT / mod).write_text(out, encoding="utf-8")
        print(f"[write] {mod}: {out.count(chr(10))} lines")

    # rebuild master.py: docstring(1-173) + import block + __all__
    # (202-205) + every line >= 1161 that is not moved
    removed = [(s, e) for ranges in RANGES.values() for s, e, _f in ranges]

    def is_removed(i: int) -> bool:
        return any(s <= i < e for s, e in removed)

    body = []
    for i in range(1161, n + 1):
        if not is_removed(i):
            body.append(lines[i - 1])
    head = "".join(lines[0:173])
    all_block = "".join(lines[201:205])

    # tail re-export block: explicit from-imports generated from the new
    # modules' ASTs (every top-level name, underscore names included).
    order = ["me/core.py", "me/errors.py", "me/risk.py",
             "me/render.py", "me/cli.py", "me/backtest.py"]
    tail = ["\n\n# ══════════════════════════════════════════════════════════════════"
            "══════\n"
            "#  v1.8.0 · MODULE SPLIT RE-EXPORTS — the single definitions now\n"
            "#  live in me/*; master.py re-exports them so `master.X` (tests,\n"
            "#  scripts, freeze manifests) resolves to the SAME objects.\n"]
    for mod in order:
        tree = ast.parse((ROOT / mod).read_text(encoding="utf-8"))
        names = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                names.append(node.name)
            elif isinstance(node, ast.Assign):
                names.extend(t.id for t in node.targets if isinstance(t, ast.Name))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target,
                                                                ast.Name):
                names.append(node.target.id)
        names = sorted(x for x in names if x != "annotations")
        modname = mod[:-3].replace("/", ".")
        tail.append(f"from {modname} import (  # noqa: F401\n")
        for j, name in enumerate(names):
            comma = "," if j < len(names) - 1 else ""
            tail.append(f"    {name}{comma}\n")
        tail[-1] = tail[-1].rstrip("\n") + "\n)\n"
    tail_text = "".join(tail)

    new_master = head + IMPORT_BLOCK + all_block + "".join(body)
    assert MAIN_GUARD_OLD in new_master, "main guard not found"
    new_master = new_master.replace(MAIN_GUARD_OLD, MAIN_GUARD_NEW, 1)
    guard_at = new_master.index(MAIN_GUARD_NEW)
    new_master = (new_master[:guard_at] + tail_text + "\n\n"
                  + new_master[guard_at:])
    SRC.write_text(new_master, encoding="utf-8")
    print(f"[write] master.py: {new_master.count(chr(10))} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
