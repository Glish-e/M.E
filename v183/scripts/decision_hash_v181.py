#!/usr/bin/env python3
"""decision_hash_v181.py — the R15 invariance gate for v1.8.1.

"The network layer on and healthy must not change decisions": runs the
SAME deterministic fake-engine scenario in the PRISTINE v1.8.0 tree
(extracted from final_master_e.zip) and in THIS v1.8.1 tree, with the
net guard installed and a HEALTHY loopback HTTP server behind every
quality fetch (127.0.0.1 only — never the real network, R11), then
compares the sha256 of the decision ranking (ticker, action,
conviction, weight).

Usage: python3 scripts/decision_hash_v181.py
Exit 0 = hashes identical; writes evidence/v181_decision_hash.txt.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent.parent
EZIP = Path("/home/z/my-project/download/final_master_e.zip")

DRIVER = r'''
import hashlib, json, sys, types, urllib.request
sys.path.insert(0, r"{tree}")
import test_master as tm
import master

PORT = int(sys.argv[1])
log = {{}}
qm = tm._fake_quality(log)

def get_quality_score(ticker, as_of=None, *, source="auto",
                      universe_file=None, universe_refs=None,
                      progress=None):
    # the fetch goes THROUGH the process-level transports: v1.8.1's net
    # guard (ledger + breaker + retries) is on the path; v1.8.0 sends it
    # directly. A HEALTHY loopback server answers 200 for every item.
    urllib.request.urlopen(f"http://127.0.0.1:{{PORT}}/q/{{ticker}}",
                           timeout=5).read()
    raw = tm._stub_q_raw(ticker)
    raw["as_of"] = as_of or "2026-11-19"
    return raw

qm.get_quality_score = get_quality_score
mods = dict(meds=tm._fake_meds(log), quality=qm,
            earnings=tm._fake_earnings(log))
with tm._Mods(**mods):
    out = tm._run(["MU", "NVDA", "AMD", "META", "COST"],
                  mods=None, net="online")
rows = [(d.ticker, d.action, round(d.conviction, 6),
         round(d.weight, 6)) for d in out.decisions]
h = hashlib.sha256(repr(rows).encode()).hexdigest()
fh = getattr(out, "fetch_health", None) or {{}}
print(json.dumps({{"hash": h, "n": len(rows),
                   "fetch_total": (fh.get("total") if fh else None)}}))
'''


def _server() -> ThreadingHTTPServer:
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _run_tree(tree: Path, port: int) -> dict:
    driver = DRIVER.format(tree=str(tree))
    r = subprocess.run(
        [sys.executable, "-c", driver, str(port)],
        cwd=str(tree), capture_output=True, text=True, timeout=180,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(tree),
             "HOME": str(tree), "LC_ALL": "C",
             "MASTER_NET_PREFLIGHT_HOSTS": ""})
    if r.returncode != 0:
        raise RuntimeError(f"driver failed in {tree}: {r.stderr[-500:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def main() -> int:
    srv = _server()
    port = srv.server_address[1]
    tmp = Path(tempfile.mkdtemp(prefix="v180_ref_"))
    try:
        subprocess.run(["unzip", "-qo", str(EZIP), "-d", str(tmp)],
                       check=True, timeout=120)
        old = _run_tree(tmp, port)
        new = _run_tree(HERE, port)
        lines = [
            "# v1.8.1 decision-hash invariance gate (R15-style proof)",
            "",
            "Scenario: identical fake engines; every quality fetch goes",
            "through the process-level transports to a HEALTHY loopback",
            "HTTP server (127.0.0.1:200; never the real network). The",
            "v1.8.1 run has the net guard INSTALLED and ACTIVE (urlopen",
            "guard, ledger, breaker, retry clock); the v1.8.0 run (pristine",
            "final_master_e.zip extraction) has no guard.",
            "",
            f"v1.8.0 (final_master_e.zip): hash {old['hash']} · "
            f"{old['n']} decisions",
            f"v1.8.1 (this tree)        : hash {new['hash']} · "
            f"{new['n']} decisions · fetch_total {new['fetch_total']}",
            "",
            ("UNCHANGED — the network layer on and healthy changes no "
             "decision." if old["hash"] == new["hash"]
             else "CHANGED — VIOLATION."),
        ]
        out = HERE / "evidence" / "v181_decision_hash.txt"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        return 0 if old["hash"] == new["hash"] else 1
    finally:
        srv.shutdown()
        srv.server_close()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
