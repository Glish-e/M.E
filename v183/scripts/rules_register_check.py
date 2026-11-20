#!/usr/bin/env python3
"""rules_register_check.py - B6 gate: every CONFIG key is either READ in
production master.py or EXPLICITLY DISCLOSED as not-read in its rationale.

PHASE 2 PORT (v1.7.0-dev): ported by function name from v1.4.1's
scripts/rules_register_check.py (classify/main). Why this gate exists
(hunt F-008 / v1.4.1 B6): four CONFIG keys (EARNINGS_TOP_K,
LAYER_TIMEOUT_S, EARNINGS_NATIVE_GRADES, CONF_DIGITS) were defined but
never read in production code while MODES["standard"] hard-coded the same
numbers — tests asserted the values against numbers that merely
coincided (900==900, 25==25). A rules register that silently contains
dead keys is a register that lies. The v1.5.0 tree re-introduced the
exact same defect (MODES hard-codes 900.0/25; port_map.md B6, fact-check
F-line: wip:334). The census counts differ on this base (CONFIG grew);
the PASS condition is unchanged: every key LIVE or DISCLOSED.

PASS criteria, per key:
  1. LIVE  - referenced in production master.py as CONFIG["KEY"], or passed
     as a bands key to _native_grade("KEY", ...); OR
  2. DISCLOSED - its rationale contains a disclosure marker
     ("NOT currently read" / "never re-scores" / "documented vocabulary"),
     i.e. the register says out loud that production does not read it.

Exit 0 = PASS (printed), exit 1 = FAIL with the offending keys.

Negative control (the gate must catch a planted dead key, not just pass):
  python3 scripts/rules_register_check.py --master /tmp/corrupt_master.py
where /tmp/corrupt_master.py is a copy of master.py with
_cfg("ZZ_PLANTED_DEAD_KEY", 1, "planted for the negative control.")
appended — the run must FAIL and name the planted key.

Usage: python3 scripts/rules_register_check.py [--master PATH]
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DISCLOSURE_MARKERS = ("NOT currently read", "never re-scores",
                      "documented vocabulary")


def _dead_cyclical_members(core_mod) -> set:
    """F4 (v1.8.3): CYCLICAL_SECTORS members with no ETF vocabulary entry
    — a member appears in no ETF_TO_SECTORS pair and is no _BUCKET_ETF
    key, so macro_tilt returns None for it BEFORE the cyclical test and
    its -0.5 tilt is unreachable. _BUCKET_ETF is a MODULE attribute of
    me.core (not a CONFIG key)."""
    mapped = {sec for pairs in core_mod.CONFIG["ETF_TO_SECTORS"].values()
              for sec, _s in pairs}
    mapped |= set(getattr(core_mod, "_BUCKET_ETF", {}) or {})
    return set(core_mod.CONFIG.get("CYCLICAL_SECTORS", ())) - mapped


def classify(key: str, src: str, rationale: str) -> tuple[str, str]:
    """(verdict, evidence) for one CONFIG key."""
    live = (f'CONFIG["{key}"]' in src) or (f"CONFIG['{key}']" in src) \
        or (f'_native_grade("{key}"' in src) or (f"_native_grade('{key}'" in src)
    if live:
        return "LIVE", "read in production code (master.py + me/)"
    if any(m in rationale for m in DISCLOSURE_MARKERS):
        return "DISCLOSED", "rationale states production does not read it"
    return "DEAD", "no production reference and no disclosure in rationale"


def _load_master(path: Path | None):
    """The module + its own source text + a cleanup callable (or None).
    Default: the real tree's master; --master PATH: load exactly that file
    (negative control / other trees) WITHOUT disturbing sys.modules
    ['master'] (the copy registers under its own name for the
    dataclasses machinery, and is removed after)."""
    if path is None:
        sys.path.insert(0, str(ROOT))
        import master
        return master, (ROOT / "master.py").read_text(encoding="utf-8"), None
    name = "master_register_under_test"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod               # dataclasses resolves cls.__module__
    # phase 8: a --master copy from OUTSIDE the repo (the negative
    # control's /tmp/corrupt_master.py) must still import master's
    # siblings (codes.py) — the REPO ROOT goes on sys.path for the
    # exec and is removed after, never leaked.
    added = str(Path(__file__).resolve().parent.parent)
    sys.path.insert(0, added)
    # v1.8.0 (W1): master.py imports CONFIG from the me.core SINGLETON;
    # a --master copy's appended _cfg(...) lines mutate that shared dict.
    # Snapshot now; _cleanup() restores it AFTER classification.
    import me.core as _core
    _cfg_before = dict(_core.CONFIG)
    _rat_before = dict(_core._RATIONALE)
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(name, None)       # never leak the copy
        if added in sys.path:
            sys.path.remove(added)

    def _cleanup() -> None:
        """v1.8.0 (W1): master.py imports CONFIG from the me.core
        SINGLETON, so exec'ing a --master copy (whose appended _cfg(...)
        lines mutate that shared dict) would leak keys into the real
        registry for the rest of the process. main() classifies the
        copy's state FIRST, then restores the snapshot."""
        _core.CONFIG.clear()
        _core.CONFIG.update(_cfg_before)
        _core._RATIONALE.clear()
        _core._RATIONALE.update(_rat_before)
    return mod, path.read_text(encoding="utf-8"), _cleanup


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    master_path: Path | None = None
    if "--master" in argv:
        i = argv.index("--master")
        master_path = Path(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if argv:
        print(f"usage: rules_register_check.py [--master PATH] (got {argv!r})")
        return 64
    mod, src, cleanup = _load_master(master_path)
    # v1.8.0 (W1): production code is master.py + the me/ modules it
    # re-exports; the register greps the CONCATENATED production source.
    me_src = "\n".join(
        f.read_text(encoding="utf-8")
        for f in sorted((ROOT / "me").glob("*.py")))
    src = src + "\n" + me_src
    try:
        return _classify_all(mod, src)
    finally:
        if cleanup is not None:
            cleanup()


def _classify_all(mod, src: str) -> int:
    """Print the per-key register and return the exit code (shared with
    main; the caller restores the CONFIG snapshot via cleanup())."""
    rationales = mod.config_rationales()
    counts: dict[str, int] = {"LIVE": 0, "DISCLOSED": 0, "DEAD": 0}
    dead: list[str] = []
    for key in sorted(mod.CONFIG):
        verdict, why = classify(key, src, rationales.get(key, ""))
        counts[verdict] += 1
        if verdict == "DEAD":
            dead.append(key)
        print(f"  {verdict:<9s} {key:<28s} {why}")
    print(f"RULES REGISTER: {counts['LIVE']} live / {counts['DISCLOSED']} "
          f"disclosed-not-read / {counts['DEAD']} dead "
          f"(total {len(mod.CONFIG)})")
    # F4 (v1.8.3): VALUE-level reachability for the sector-vocabulary
    # sets — a key can be LIVE (read in production) while some of its
    # VALUES are unreachable (CYCLICAL_SECTORS' financials/specialty have
    # no ETF mapping, so their -0.5 tilt can never fire). The register
    # only stays honest when the rationale carries the REACHABILITY
    # disclosure naming the inert members; otherwise the gate FAILS.
    reach_fail = False
    try:
        import me.core as _core
        _dead_cyc = _dead_cyclical_members(_core)
    except Exception:
        _dead_cyc = set()
    if _dead_cyc:
        if "REACHABILITY" in rationales.get("CYCLICAL_SECTORS", ""):
            print(f"  REACH    CYCLICAL_SECTORS           "
                  f"inert member(s) disclosed: {sorted(_dead_cyc)} "
                  "(no ETF_TO_SECTORS entry; -0.5 unreachable by design "
                  "— see the rationale)")
        else:
            print(f"FAIL: CYCLICAL_SECTORS: inert member(s) "
                  f"{sorted(_dead_cyc)} with no reachability disclosure "
                  "in the rationale")
            reach_fail = True
    if dead:
        print("FAIL: dead CONFIG keys (no production read, no disclosure): "
              + ", ".join(dead))
        return 1
    if reach_fail:
        return 1
    print("RULES REGISTER CHECK: PASS "
          "(every key is live or disclosed as not-read)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
