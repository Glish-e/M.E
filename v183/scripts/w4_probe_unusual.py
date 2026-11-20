#!/usr/bin/env python3
"""Probe: enumerate every W_UNUSUAL produced by stub / offline / outage runs."""
import io
import os
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["MASTER_STUBS"] = "0"
os.environ["MASTER_NET_PREFLIGHT_HOSTS"] = ""

import test_master as tm  # noqa: E402  (helpers: _run, _fake_*)

from me.render import _build_diags, _classify_warning  # noqa: E402


def unusual(out):
    return [d for d in _build_diags(out) if d["code"] == "W_UNUSUAL"]


print("== stub run (MASTER_STUBS=1) ==")
with redirect_stderr(io.StringIO()):
    out = tm._run(["MU", "NVDA", "AAPL", "AMD", "META", "COST"], stubs=True, timeout=30)
for d in unusual(out):
    print("  W_UNUSUAL:", d.get("layer"), "|", d.get("what"))
for w in out.warnings:
    print(f"  raw warning [{_classify_warning('pipeline', w)}]: {w[:90]}")
for name, res in out.results.items():
    for w in res.warnings:
        print(f"  layer {name} [{_classify_warning(name, w)}]: {w[:90]}")

print("== offline run (fake engines) ==")
log = {}
with redirect_stderr(io.StringIO()):
    out = tm._run(["MU", "NVDA", "--timeout", "30"], mods={
        "meds": tm._fake_meds(log), "quality": tm._fake_quality(log),
        "earnings": tm._fake_earnings(log)}, net="offline")
for d in unusual(out):
    print("  W_UNUSUAL:", d.get("layer"), "|", d.get("what"))
for w in out.warnings:
    print(f"  raw warning [{_classify_warning('pipeline', w)}]: {w[:90]}")
for name, res in out.results.items():
    for w in res.warnings:
        print(f"  layer {name} [{_classify_warning(name, w)}]: {w[:90]}")

print("== outage run (online pin, dead loopback preflight -> breaker) ==")
srv = tm._fault_srv({"*": [500]}, hang_s=0.2)
try:
    old = tm.CONFIG["NET_PREFLIGHT_HOSTS"]
    tm.CONFIG["NET_PREFLIGHT_HOSTS"] = []
    log = {}
    with redirect_stderr(io.StringIO()):
        out = tm._run(["MU", "NVDA", "--timeout", "20"], mods={
            "meds": tm._fake_meds(log), "quality": tm._fake_quality(log),
            "earnings": tm._fake_earnings(log)}, net="online")
    tm.CONFIG["NET_PREFLIGHT_HOSTS"] = old
    for d in unusual(out):
        print("  W_UNUSUAL:", d.get("layer"), "|", d.get("what"))
    for w in out.warnings:
        print(f"  raw warning [{_classify_warning('pipeline', w)}]: {w[:90]}")
    for name, res in out.results.items():
        for w in res.warnings:
            print(f"  layer {name} [{_classify_warning(name, w)}]: {w[:90]}")
finally:
    srv.stop()

print("== known engine warning texts (from facts d) ==")
for layer, txt in [
    ("quality", "empty shortlist: nothing passed the quality gate"),
    ("macro", "scenario RISK_ON score renormalized: retained weight 60% of its terms (<70%)"),
    ("macro", "macro DEGRADED (engine-reported)"),
    ("macro", "credit OFF — not trade-grade (macro damped; excluded: CREDIT_CRUNCH)"),
    ("earnings", "earnings accuracy: SIGNAL: high-rated names hit big beats 1.80x more often than base"),
    ("pipeline", "MACRO UNAVAILABLE — no regime context (tilt n/a, risk budget capped at 1.0)"),
]:
    print(f"  [{_classify_warning(layer, txt)}] {txt[:70]}")
