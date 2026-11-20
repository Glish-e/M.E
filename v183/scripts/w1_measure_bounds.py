#!/usr/bin/env python3
"""W1 measurement probe: loopback numbers for the net bounds doc.

Measures (loopback only, 127.0.0.1):
  1. connect-refused latency (the outage case, per attempt)
  2. preflight wall for 6 refused hosts (v1.8.1 semantics, no total budget)
  3. brownout per-call latency + breaker trip time (accept+hang, cap 30)
  4. intermittent fast-fail: consecutive rule never trips; rate rule needed
Prints the raw numbers evidence/net_bounds.md cites.
"""
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from test_master import _fault_srv  # noqa: E402
from me import netguard as ng  # noqa: E402


def dead_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


print("== 1. connect-refused latency (10 attempts) ==")
port = dead_port()
t0 = time.monotonic()
for _ in range(10):
    try:
        socket.create_connection(("127.0.0.1", port), timeout=2.0)
    except Exception:
        pass
refused10 = time.monotonic() - t0
print(f"10 refused connects: {refused10*1000:.1f} ms total")

print("== 2. preflight, 6 refused hosts, retries=2 (v1.8.1 semantics) ==")
ports = [dead_port() for _ in range(6)]
g = ng.NetGuard(breaker_k=5, breaker_cooldown_s=30.0, negcache_path=None)
t0 = time.monotonic()
res = ng.preflight([("127.0.0.1", p) for p in ports], budget_s=2.0, retries=2)
wall = time.monotonic() - t0
print(f"6 hosts x (1+2) attempts: {wall:.2f} s; all dead: "
      f"{all(not r['ok'] for r in res.values())}")

print("== 3. brownout (accept+hang, call cap 30 s): trip time ==")
srv = _fault_srv({"*": ["hang"]}, hang_s=45.0)
try:
    g = ng.NetGuard(breaker_k=5, breaker_cooldown_s=30.0, call_cap_s=30.0,
                    retry_budget_s=45.0, max_attempts=3,
                    backoff=(0.5, 1.5), negcache_path=None)
    import urllib.request as _u
    wrapped = g.wrap_urlopen(_u.urlopen)
    url = f"http://127.0.0.1:{srv.port}/x"
    t0 = time.monotonic()
    walls = []
    for call in range(4):
        tc = time.monotonic()
        try:
            wrapped(_u.Request(url), timeout=45.0)
        except Exception as e:
            pass
        walls.append(time.monotonic() - tc)
        st = g.breaker.state("127.0.0.1")
        print(f"  call {call+1}: {walls[-1]:.1f} s -> breaker {st}")
        if st == "open":
            print(f"  TRIPPED after {time.monotonic()-t0:.1f} s "
                  f"({sum(walls):.1f} s in calls)")
            break
finally:
    srv.stop()

print("== 4. intermittent fast 500s: consecutive rule never trips ==")
srv = _fault_srv({"*": [500, 200]})   # alternating fail/ok
try:
    g = ng.NetGuard(breaker_k=5, breaker_cooldown_s=30.0, call_cap_s=30.0,
                    retry_budget_s=45.0, max_attempts=1,
                    backoff=(0.05,), negcache_path=None)
    import urllib.request as _u
    wrapped = g.wrap_urlopen(_u.urlopen)
    url = f"http://127.0.0.1:{srv.port}/x"
    ok = fail = 0
    for i in range(30):
        try:
            wrapped(_u.Request(url), timeout=5.0)
            ok += 1
        except Exception:
            fail += 1
    print(f"30 alternating calls: {ok} ok / {fail} failed -> "
          f"breaker {g.breaker.state('127.0.0.1')} (consecutive rule: "
          f"{'TRIPPED' if g.breaker.state('127.0.0.1') == 'open' else 'never trips'})")
finally:
    srv.stop()
