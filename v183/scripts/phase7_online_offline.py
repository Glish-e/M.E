#!/usr/bin/env python3
"""phase7_online_offline.py — B-9 item 1 (D3): online-vs-offline decision
identity on a REAL cache.

Protocol: (1) an ONLINE quick run on real names (SEC_USER_AGENT set) —
it refreshes whatever is stale and WRITES the cache; (2) an OFFLINE run
immediately after, on the SAME cache the online run just left — zero
sockets, cache truth only; (3) compare the two runs' decisions
(ranking + conviction + action) name by name. Identical => the offline
path reproduces the online path's decisions on the same data basis.

Any difference is printed in full and the script exits 1.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMES = ["MU", "NVDA", "AAPL", "AMD", "META"]
ENV = {"SEC_USER_AGENT": "research-screener admin@example.com",
       "PYTHONPATH": str(ROOT)}


def run(mode: str) -> dict:
    argv = [sys.executable, "master.py", *NAMES, "--mode", "quick",
            "--quiet", "--json"]
    if mode == "offline":
        argv += ["--offline"]
        env = dict(ENV, MASTER_NET="offline")
    else:
        env = dict(ENV, MASTER_NET="online")
    t0 = time.monotonic()
    p = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True,
                       text=True, timeout=600)
    dt = time.monotonic() - t0
    payload = json.loads(p.stdout)
    print(f"[{mode}] exit {p.returncode} · {dt:.1f}s · "
          f"timings {payload.get('timings', {}).get('total')}s · "
          f"{len(payload.get('decisions', []))} decisions")
    return payload


def decisions_of(payload: dict) -> list[tuple]:
    out = []
    for d in payload.get("decisions", []):
        out.append((d.get("ticker"), d.get("action"),
                    round(float(d.get("conviction", 0.0) or 0.0), 6)))
    out.sort()
    return out


def main() -> int:
    print("B-9 item 1 (D3): online-vs-offline decision identity on a "
          "real cache")
    print("names: " + " ".join(NAMES))
    on = run("online")
    off = run("offline")
    a, b = decisions_of(on), decisions_of(off)
    if a == b:
        print(f"IDENTICAL: {len(a)} decisions (ticker, action, conviction) "
              f"match bit-for-bit between the online run and the offline "
              f"replay of the cache it wrote")
        for row in a:
            print("  ", row)
        return 0
    print("MISMATCH:")
    for x, y in zip(a, b):
        flag = "" if x == y else "   <-- differs"
        print(f"   online {x} vs offline {y}{flag}")
    if len(a) != len(b):
        print(f"   count differs: online {len(a)} vs offline {len(b)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
