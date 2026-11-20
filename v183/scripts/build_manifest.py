#!/usr/bin/env python3
"""Build MANIFEST.txt (sha256 of every shipped file, MANIFEST itself
excluded) and verify it by recomputation.

PHASE 2 PORT (v1.7.0-dev): ported from v1.4.1's delivery gate; run at each
phase's packaging step (the WIP manifest covers the current tree; the
RELEASE manifest is rebuilt at phase 9 per spec Section 9).

F8 (v1.8.3): the version stamp comes from me/core.py __version__ — the
SINGLE source of truth (requirements*.txt carried a stale 'v1.7.0-dev'
for two releases; a copy-pasted constant here would drift the same way)."""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {"__pycache__", "tool-results", ".git", "meds_cache"}
EXCLUDE_FILES = {"MANIFEST.txt"}
EXCLUDE_SUFFIX = (".pyc", ".tmp")
# phase 7: runtime caches are NOT release files — a warmed quality cache
# (data/cache/**, ~300+ provider payloads) is machine state, never a
# shipped artifact (the v1.5.0 zip shipped the empty dir roots only).
EXCLUDE_PREFIX = ("data/cache/",)


def files():
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if rel.parts[0] in EXCLUDE_DIRS or p.name in EXCLUDE_FILES \
                or p.suffix in EXCLUDE_SUFFIX or any(
                    part in EXCLUDE_DIRS for part in rel.parts) \
                or rel.as_posix().startswith(EXCLUDE_PREFIX):
            continue
        yield p, rel


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    # F8 (v1.8.3): stamp from me/core.py __version__ (single source of
    # truth) instead of a hard-coded 'v1.7.0-dev' that silently went stale.
    ver = re.search(r'^__version__ = "(.+)"',
                    (ROOT / "me" / "core.py").read_text(encoding="utf-8"),
                    re.M).group(1)
    entries = [(sha(p), rel.as_posix()) for p, rel in files()]
    head = (f"# MANIFEST - sha256 of every file in the v{ver} WIP tree "
            f"(MANIFEST.txt itself excluded)\n"
            f"# base: master.py v{ver} (v1.8.2 + the stage-2 fixes F1-F12 "
            f"per download/stage1_out; engines untouched)\n"
            f"# files: {len(entries)}\n")
    body = "".join(f"{h}  {name}\n" for h, name in entries)
    (ROOT / "MANIFEST.txt").write_text(head + body, encoding="utf-8")
    # verify by recomputation
    bad = []
    for line in (ROOT / "MANIFEST.txt").read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        h, _, name = line.partition("  ")
        f = ROOT / name
        if not f.exists() or sha(f) != h:
            bad.append(name)
    print(f"MANIFEST: {len(entries)} files written; "
          f"reverification: {'ALL MATCH' if not bad else 'MISMATCH ' + str(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
