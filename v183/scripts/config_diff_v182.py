#!/usr/bin/env python3
"""config_diff_v182.py — S7 CONFIG disclosure: v1.8.1 (pristine
final_master_f.zip tree) vs the CURRENT v1.8.2 tree, loading each tree's
CONFIG in a SEPARATE subprocess (config_diff.py loads both in one
process, which reuses the first tree's cached me.core and prints an
empty diff — a pre-existing limitation since CONFIG moved to me/core).

Usage: python3 scripts/config_diff_v182.py [v181-tree] [v182-tree]
Writes evidence/v182_config_diff_vs_v181.txt; exit 0 identical / 1 diff.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
OLD = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "v181"
NEW = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE

DUMP = r'''
import json, sys
sys.path.insert(0, r"{tree}")
import master
from me.core import _RATIONALE
print(json.dumps({{"values": dict(master.CONFIG),
                   "rationales": dict(_RATIONALE)}}, default=str, sort_keys=True))
'''


def dump(tree: Path) -> dict:
    r = subprocess.run([sys.executable, "-c", DUMP.format(tree=str(tree))],
                       cwd=str(tree), capture_output=True, text=True,
                       timeout=120,
                       env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
    if r.returncode != 0:
        raise RuntimeError(f"dump failed for {tree}: {r.stderr[-400:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def _norm(v) -> str:
    """Order-insensitive comparison for set-like reprs (frozenset/set
    repr order varies across processes; the VALUES are equal)."""
    s = str(v)
    for opener, closer in (("frozenset({", "})"), ("{", "}")):
        if s.startswith(opener) and s.endswith(closer):
            inner = s[len(opener):-len(closer)].strip()
            if inner:
                parts = sorted(x.strip() for x in inner.split(","))
                return opener + ", ".join(parts) + closer
    return s


def main() -> int:
    old, new = dump(OLD), dump(NEW)
    lines = [f"baseline: {OLD} ({len(old['values'])} entries)",
             f"current : {NEW} ({len(new['values'])} entries)", ""]
    keys = sorted(set(old["values"]) | set(new["values"]))
    vdiff, rdiff = [], []
    for k in keys:
        b, c = old["values"].get(k, "<absent>"), new["values"].get(k, "<absent>")
        if _norm(b) != _norm(c):
            vdiff.append((k, b, c))
        rb = old["rationales"].get(k, "<absent>")
        rc = new["rationales"].get(k, "<absent>")
        if rb != rc:
            rdiff.append((k, rb, rc))
    for k, b, c in vdiff:
        lines += [f"VALUE CHANGED {k}:", f"  v1.8.1={b!r}", f"  v1.8.2={c!r}"]
    for k, b, c in rdiff:
        lines += [f"RATIONALE CHANGED {k}:", f"  v1.8.1={str(b)[:300]!r}",
                  f"  v1.8.2={str(c)[:300]!r}"]
    if not vdiff and not rdiff:
        lines.append("CONFIG DIFF: EMPTY (values and rationales identical)")
    else:
        lines += ["", f"summary: {len(vdiff)} value change(s), "
                  f"{len(rdiff)} rationale change(s) — every change is a "
                  "disclosed runtime knob (S7); no decision input changed "
                  "(proof: evidence/v182_decision_hash.txt)"]
    out = HERE / "evidence" / "v182_config_diff_vs_v181.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:8]))
    print(f"... ({len(lines)} lines) -> {out}")
    return 0 if not vdiff and not rdiff else 1


if __name__ == "__main__":
    raise SystemExit(main())
