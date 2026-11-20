#!/usr/bin/env python3
"""release_gate.py — the phase-9 release gate (phase 7, B-9 item 4).

The mechanism the phase-7 task book demands: HANDOFF.txt's
"ZIP SHA256: PLACEHOLDER" line is replaced at phase 9 with the real
wording (the sha256 itself can NEVER live inside the zip — a zip cannot
contain its own hash — so the release wording states where the value is
printed). Until that replacement happens this gate FAILS on the
placeholder string, which is exactly the designed behaviour: a leftover
placeholder must never ship.

Checks (each printed PASS/FAIL, exit 1 on any FAIL):
  1. HANDOFF.txt is at most 3,500 ASCII characters (spec Section 11).
  2. HANDOFF.txt contains no "PLACEHOLDER" string.
  3. HANDOFF.txt's "ZIP SHA256:" line carries the release wording (the
     value is printed in the delivery message, not embedded).
  4. ml_train version agreement: ml_train.__version__ == every shipped
     head_*.npz sidecar pin == the CHANGELOG top claim == the HANDOFF
     top claim (the phase-1 test's contract, enforced at packaging).
  5. RUNBOOK.md is at most 120 lines (phase 9 D).
  6. MANIFEST.txt lists every file in the tree with a matching sha256
     and excludes itself (build_manifest.py's contract).
  7. No file named final_master_d.zip inside the tree (the release zip
     is built from a clean copy, never nested).

Usage: python3 scripts/release_gate.py [--root DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_VRE = re.compile(r"(\d+\.\d+\.\d+(?:-[A-Za-z0-9.]+)?)")
HANDOFF_MAX_CHARS = 3500
RUNBOOK_MAX_LINES = 120


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def handoff_checks(root: Path) -> bool:
    p = root / "HANDOFF.txt"
    if not p.exists():
        return check("HANDOFF.txt exists", False)
    text = p.read_text(encoding="utf-8")
    ok = True
    n = len(text.encode("ascii", errors="ignore"))
    ok &= check(f"HANDOFF <= {HANDOFF_MAX_CHARS} ASCII chars",
                len(text) <= HANDOFF_MAX_CHARS and n == len(text),
                f"{len(text)} chars ({n} ASCII)")
    ok &= check('HANDOFF has no "PLACEHOLDER"', "PLACEHOLDER" not in text)
    zip_line = next((l for l in text.splitlines()
                     if l.startswith("ZIP SHA256:")), "")
    ok &= check("HANDOFF ZIP SHA256 line carries the release wording",
                bool(zip_line) and "printed in the delivery" in zip_line,
                zip_line[:70])
    return ok


def version_checks(root: Path) -> bool:
    sys.path.insert(0, str(root))
    try:
        import ml_train
        code = str(ml_train.__version__)
    except Exception as e:
        return check("ml_train imports", False, str(e)[:60])
    finally:
        sys.path.remove(str(root))
    ok = check(f"ml_train version readable", True, f"v{code}")
    import numpy as np
    models = sorted((root / "ml_data" / "models").glob("head_*.npz"))
    if not models:
        return ok & check("shipped heads exist", False)
    for p in models:
        z = np.load(p, allow_pickle=False)
        ok &= check(f"sidecar {p.name} pins ml_train {code}",
                    str(z["ml_train_version"]) == code,
                    str(z["ml_train_version"]))
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    lines = changelog.splitlines()
    i0 = next(i for i, ln in enumerate(lines) if ln.startswith("## "))
    i1 = next((i for i in range(i0 + 1, len(lines)) if lines[i].startswith("## ")),
              len(lines))
    top = "\n".join(lines[i0:i1])
    claim = None
    for line in top.splitlines():
        if "ml_train" in line:
            toks = _VRE.findall(line)
            if toks:
                claim = toks[-1]
    ok &= check("CHANGELOG top ml_train claim agrees", claim == code,
                str(claim))
    hand = "\n".join((root / "HANDOFF.txt").read_text(encoding="utf-8")
                     .splitlines()[:40])
    claim = None
    for line in hand.splitlines():
        if "ml_train" in line:
            toks = _VRE.findall(line)
            if toks:
                claim = toks[-1]
    ok &= check("HANDOFF top ml_train claim agrees", claim == code,
                str(claim))
    return ok


def runbook_check(root: Path) -> bool:
    p = root / "RUNBOOK.md"
    if not p.exists():
        return check("RUNBOOK.md exists", False)
    n = len(p.read_text(encoding="utf-8").splitlines())
    return check(f"RUNBOOK <= {RUNBOOK_MAX_LINES} lines",
                 n <= RUNBOOK_MAX_LINES, f"{n} lines")


def manifest_check(root: Path) -> bool:
    p = root / "MANIFEST.txt"
    if not p.exists():
        return check("MANIFEST.txt exists", False)
    man: dict[str, str] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        h, _, name = line.partition("  ")
        if name.strip():
            man[name.strip()] = h.strip()
    bad = []
    for name, h in man.items():
        f = root / name
        if not f.exists() or hashlib.sha256(f.read_bytes()).hexdigest() != h:
            bad.append(name)
    # runtime caches are machine state, not release files (the same
    # roots build_manifest.py excludes: data/cache/**, meds_cache/**)
    RUNTIME_ROOTS = ("data/cache/", "meds_cache/")
    extra = [str(f.relative_to(root)) for f in root.rglob("*")
             if f.is_file() and str(f.relative_to(root)) not in man
             and "__pycache__" not in str(f)
             and f.name != "MANIFEST.txt"
             and "final_master_d.zip" not in str(f)
             and not str(f.relative_to(root)).startswith(RUNTIME_ROOTS)]
    ok = check("MANIFEST hashes all match", not bad, ", ".join(bad[:3]))
    ok &= check("MANIFEST lists every file (excl. itself)",
                not extra, ", ".join(extra[:3]))
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args()
    root = Path(args.root)
    print(f"release gate — {root}")
    ok = True
    ok &= handoff_checks(root)
    ok &= version_checks(root)
    ok &= runbook_check(root)
    ok &= manifest_check(root)
    ok &= check("no final_master_d.zip nested in the tree",
                not (root / "final_master_d.zip").exists())
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
