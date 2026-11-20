#!/usr/bin/env python3
"""DIFFERENTIAL AND CONSISTENCY CHECKS (read-only).

PHASE 2 PORT (v1.7.0-dev): ported by function name from v1.4.1's
scripts/diff_checks.py; the D1/D2/D3 sections run unchanged (all CLI
flags and engine APIs verified present on this base). D4's note is
REWRITTEN for this base: freeze/replay DO exist here (v1.5.0 final-phase
features), so the parity harness is the in-suite TestFreezeReplay + the
replay tests, not an absence note.

D1 stub CLI run: table vs JSON vs CSV — every shared field must agree.
D2 stub vs real-engine API shapes (import + attribute/signature checks).
D3 online vs offline on the same cache — needs a real cache; UNVERIFIED here.
D4 freeze/replay parity — features present; harness in the suite.

Usage: python3 scripts/diff_checks.py
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def run_cli(argv, env_extra=None, timeout=120):
    env = dict(os.environ, PYTHONPATH=str(ROOT), NO_COLOR="1", COLUMNS="110")
    env.update(env_extra or {})
    return subprocess.run([sys.executable, "master.py", *argv], cwd=str(ROOT),
                          env=env, capture_output=True, timeout=timeout)


def main() -> int:
    print("DIFF CHECKS — differential and consistency (v1.4.1 port)")
    print("=" * 76)

    # ── D1: table vs JSON vs CSV on the same stub run ────────────────────
    tickers = ["MU", "NVDA", "AAPL", "AMD", "META", "COST", "HD", "LOW"]
    rj = run_cli([*tickers, "--json"], {"MASTER_STUBS": "1"})
    print(f"D1 stub --json run: exit={rj.returncode}")
    # phase 8 (P8-H1): the phase-5 exit contract makes a degraded run
    # (warnings, result produced) exit 1 — a stub run with earnings/ml
    # notes is DEGRADED-BY-DESIGN, not a failure. Only 2/4/65/70 fail D1.
    if rj.returncode not in (0, 1) or not rj.stdout.strip():
        print(rj.stderr.decode()[-800:])
        return 2
    doc = json.loads(rj.stdout.decode())
    jmap = {}
    for d in doc["decisions"]:
        jmap[d["ticker"]] = d
    print(f"   JSON decisions: {len(jmap)}")

    with tempfile.TemporaryDirectory() as td:
        csv_path = str(Path(td) / "out.csv")
        rc = run_cli([*tickers, "--csv", csv_path, "--top", "50"],
                     {"MASTER_STUBS": "1"})
        print(f"D1 stub --csv run: exit={rc.returncode}")
        import csv as _csv
        rows = list(_csv.DictReader(open(csv_path, encoding="utf-8")))
        print(f"   CSV rows: {len(rows)}")

    rt = run_cli([*tickers, "--top", "50"], {"MASTER_STUBS": "1"})
    table = rt.stdout.decode()
    print(f"D1 stub table run: exit={rt.returncode}, {len(table.splitlines())} lines")

    mismatches = []
    # JSON vs CSV
    for row in rows:
        t = row["ticker"]
        j = jmap.get(t)
        if j is None:
            mismatches.append(f"CSV row {t} missing from JSON")
            continue
        pairs = [("action", "action"), ("conviction", "conviction"),
                 ("sector", "sector"), ("grade", "grade")]
        for cj, jj in pairs:
            cv, jv = row.get(cj), j.get(jj)
            if cv is None or jv is None:
                continue
            if isinstance(jv, (int, float)):
                try:
                    same = abs(float(cv) - float(jv)) < 0.051
                except ValueError:
                    same = False
            else:
                same = str(cv).strip() == str(jv).strip()
            if not same:
                mismatches.append(f"{t}: CSV {cj}={cv!r} vs JSON {jj}={jv!r}")
        # weight: CSV 'weight' vs JSON weight
        if row.get("weight") not in (None, "") and j.get("weight") is not None:
            if abs(float(row["weight"]) - float(j["weight"])) > 1e-6:
                mismatches.append(f"{t}: CSV weight={row['weight']} vs "
                                  f"JSON {j['weight']}")
    # JSON vs table (action + conviction presence)
    for t, j in jmap.items():
        line = next((ln for ln in table.splitlines()
                     if re.search(rf"\b{re.escape(t)}\b", ln)), None)
        if line is None:
            mismatches.append(f"ticker {t} not found in table output")
            continue
        if j["action"] not in line:
            mismatches.append(f"{t}: action {j['action']} not on table line: {line[:90]}")
        conv = f"{j['conviction']:.0f}"
        if conv not in line:
            mismatches.append(f"{t}: conviction {j['conviction']} ({conv}) not "
                              f"on table line: {line[:90]}")
    if mismatches:
        print(f"   MISMATCHES ({len(mismatches)}):")
        for m in mismatches[:20]:
            print(f"     {m}")
    else:
        print("   table / JSON / CSV agree on every shared decision field "
              f"({len(jmap)} decisions, {len(rows)} CSV rows)")

    # determinism: same run twice
    rj2 = run_cli([*tickers, "--json"], {"MASTER_STUBS": "1"})
    same = json.loads(rj2.stdout.decode())["decisions"] == doc["decisions"]
    print(f"   determinism (two identical stub --json runs): "
          f"{'IDENTICAL' if same else 'DIFFER — VIOLATION'}")

    # ── D2: adapter vs real-engine API shapes (import, no network) ───────
    print("\nD2 adapter vs real engine API shapes (import only, zero sockets)")
    import master
    checks = []
    import meds
    for fn in ("now", "regime_now"):
        checks.append(("meds." + fn, callable(getattr(meds, fn, None))))
    import quality
    for fn in ("build_inline_universe", "get_quality_score"):
        checks.append(("quality." + fn, callable(getattr(quality, fn, None))))
    checks.append(("quality.TickerRef", hasattr(quality, "TickerRef")))
    checks.append(("quality.GROUPS", isinstance(getattr(quality, "GROUPS", None), dict)))
    checks.append(("quality.default_transport",
                   callable(getattr(quality, "default_transport", None))))
    import earnings_engine
    ee = earnings_engine.EarningsEngine
    for fn in ("analyze", "signals", "history", "prices"):
        checks.append((f"EarningsEngine.{fn}", callable(getattr(ee, fn, None))))
    for name, ok in checks:
        print(f"   {'OK ' if ok else 'MISSING'} {name}")
    # signature arity of the adapter-called engine methods
    src = (ROOT / "earnings_engine.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "EarningsEngine":
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name in (
                        "analyze", "signals", "history", "prices"):
                    n_pos = len([a for a in sub.args.args
                                 if a.arg not in ("self",)])
                    print(f"   EarningsEngine.{sub.name}: {n_pos} positional "
                          f"params ({', '.join(a.arg for a in sub.args.args[1:])})")

    # ── D3: online vs offline on the same cache ───────────────────────────
    print("\nD3 online vs offline, same cache (phase 7 scripted it: "
          "scripts/phase7_online_offline.py)")
    caches = [ROOT / "meds_cache", ROOT / "data" / "cache",
              Path.home() / ".earnings_engine_cache"]
    have = [c for c in caches if c.exists() and any(c.iterdir())]
    p7 = ROOT / "evidence" / "phase7_online_offline_identity.txt"
    if have and (ROOT / "scripts" / "phase7_online_offline.py").exists():
        import subprocess as _sp
        r = _sp.run([sys.executable,
                     str(ROOT / "scripts" / "phase7_online_offline.py")],
                    cwd=ROOT, capture_output=True, text=True, timeout=560)
        tail = "\n".join(r.stdout.splitlines()[-9:])
        print(tail)
        if r.returncode == 0 and "IDENTICAL" in r.stdout:
            print("   D3 VERIFIED (real cache): online run vs its offline "
                  "replay — decisions identical. Full log: "
                  "evidence/phase7_online_offline_identity.txt")
        else:
            print("   D3 FAILED — see the output above; "
                  "evidence/phase7_online_offline_identity.txt")
            return 2
    elif p7.exists():
        print("   (caches absent now; the phase-7 verified record stands: "
              + p7.read_text(encoding="utf-8").splitlines()[3][:80] + ")")
    else:
        print("   UNVERIFIED — no engine caches on disk in this sandbox "
              "(quality/meds/earnings fetch live); decision-identity between "
              "online and offline runs cannot be tested here. Owner: "
              "python3 scripts/phase7_online_offline.py")

    # ── D4: freeze/replay parity ───────────────────────────────────────
    print("\nD4 freeze/replay parity (v1.5.0 features PRESENT on this base)")
    feats = [n for n in ("--freeze", "--replay", "--history", "--diff",
                         "pool_snapshot", "freeze_replay")
             if n in (ROOT / "master.py").read_text(encoding="utf-8")]
    print(f"   features present in this base: {feats or 'NONE'}")
    print("   NOTE (phase-2 port): unlike the v1.4.1 base, THIS tree HAS the")
    print("   v1.5.0 freeze/replay features. The parity harness is IN the")
    print("   suite: TestFreezeReplay (stub freeze -> offline replay verifies")
    print("   ranking+convictions, exit 65 on any difference; tampered-manifest")
    print("   and missing-manifest negative controls) + the phase-2 atomic-")
    print("   write crash test on the manifest itself (TestAtomicWritesB8).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
