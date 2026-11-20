#!/usr/bin/env python3
"""capture_sim_fetch_health.py — the docs/CLI.md FETCH HEALTH sample.

Runs ONE in-process master pipeline against LOOPBACK-ONLY fault servers
(127.0.0.1; never the real network — the agent may not touch it, R11),
with the net guard fully active (preflight to the loopback host, mixed
200/404/500/429 items, a transient item the deferred pass recovers), and
prints the report's FETCH HEALTH block + the ERRORS & WARNINGS lines
that the N-codes produce.

The capture is labelled SIMULATED wherever it lands: it is a fault
simulation on a fake engine, never real provider data.

Usage: python3 scripts/capture_sim_fetch_health.py   (prints the block)
"""
from __future__ import annotations

import io
import os
import sys
import threading
import time
import types
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import master  # noqa: E402
from master import build_parser  # noqa: E402

# -- loopback-only fault topology (N8 a..f in miniature) --------------------
#  /pre          -> 200            (preflight TCP target, always up)
#  /q/MU         -> 200            (a good item)
#  /q/ZZ         -> 404            (permanent: no retry, negative cache)
#  /q/QQ         -> 500 500 200    (transient x2 then recovers on the
#                                   deferred retry pass -> recovered 1 of 1)
#  /q/429        -> 429 Retry-After: 1 then 200 (Retry-After honoured)
PLAN = {"/pre": [200], "/q/MU": [200], "/q/ZZ": [404],
        "/q/QQ": [500, 500, 500, 200], "/q/429": [429, 200]}
SEQ: dict = {}
HITS: list = []


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        HITS.append(self.path)
        seq = PLAN.get(self.path) or PLAN["/pre"]
        i = SEQ.get(self.path, 0)
        SEQ[self.path] = i + 1
        status = seq[min(i, len(seq) - 1)]
        self.send_response(status)
        if status == 429:
            self.send_header("Retry-After", "1")
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
PORT = srv.server_address[1]
BASE = f"http://127.0.0.1:{PORT}"


def main() -> int:
    # fake engine modules (test-style): quality fetches through the
    # PROCESS-LEVEL urlopen guard (ledger/breaker/classification all live)
    qmod = types.ModuleType("quality")
    qmod.ENGINE_VERSION = "3.4.1"
    qmod.CACHE_DIR = str(Path(ROOT) / "data" / "cache")

    class _Ref:
        def __init__(self, t, s):
            self.ticker, self.sector, self.status = t, s, "active"

    def get_universe(overrides_path=None):
        refs = [_Ref("MU", "tech"), _Ref("ZZ", "tech"),
                _Ref("QQ", "tech"), _Ref("429", "tech")]
        return refs, "fake universe"

    def get_quality_score(ticker, as_of=None, *, source="auto",
                          universe_file=None, universe_refs=None,
                          progress=None):
        urllib.request.urlopen(f"{BASE}/q/{ticker}", timeout=5).read()
        return {"status": "OK", "score": 70.0, "sector": "tech",
                "grade": "B", "flags": (), "as_of": as_of or "2026-11-19"}

    qmod.get_universe = get_universe
    qmod.get_quality_score = get_quality_score
    qmod.default_transport = lambda *a, **k: (None, None, None, "fake")

    def build_inline_universe(ticker, sector_arg=None, peers_arg=None,
                              full=False):
        refs, *_ = get_universe()
        return refs, "tech", "3 peers", [], None
    qmod.build_inline_universe = build_inline_universe

    mmod = types.ModuleType("meds")
    mmod.__version__ = "14.7.0"

    def now(cfg=None):
        return {"status": "OK", "scenario_key": "SOFT_LANDING_PIVOT",
                "scenario_name": "Soft Landing / Policy Pivot",
                "regime_class": "risk_on", "cycle_phase": "Mid Cycle",
                "confidence": 0.8, "dominance": 0.3,
                "conviction_leverage": 1.0, "credit": "ON",
                "quality_tier": "MED", "data_tier": "api",
                "pit_mode": "approximate_pit_lag",
                "effective_as_of": "2026-11-18", "trade_month": "2026-12",
                "longs": ("SPY",), "shorts": (), "sleeve": (),
                "excluded": (), "source": "api", "engine_version": "14.7.0"}
    mmod.now = now

    emod = types.ModuleType("earnings_engine")
    import pandas as pd  # noqa: F401  (the fake analyse needs a frame)

    class _Eng:
        def __init__(self, quarters=40, workers=4, cache_dir=None, **kw):
            self.errors: dict = {}
            self._fetch = None          # master checks callable() first
            self._pfetch = None
            self._px_fetch = None

        def prices(self, t, start):
            import pandas as pd2
            urllib.request.urlopen(f"{BASE}/q/MU", timeout=5).read()
            idx = pd2.bdate_range(end="2026-11-18", periods=200)
            return pd2.Series(100.0, index=idx.normalize(), name="close")

        def analyze(self, tickers, as_of=None, accuracy=True, trade=False,
                    hold_days=90, take_profit=None, stop_loss=None,
                    min_score=50.0, entry_lag=1, benchmark="SPY"):
            rows = {}
            for t in tickers:
                try:
                    urllib.request.urlopen(f"{BASE}/q/{t}",
                                           timeout=5).read()
                    rows[t] = {"score": 60.0, "rating": "B",
                               "last_date": "2026-11-12",
                               "n_quarters": 40, "last4_big": 3,
                               "streak_big": 2, "qtrs_since_big": 1.0,
                               "last_big_date": "2026-11-12",
                               "last_big_pct": 24.0,
                               "latest_surprise_pct": 18.0,
                               "beat_rate": 0.9, "p_next_big": 0.62,
                               "confidence": 1.0}
                except Exception as e:
                    self.errors[t] = f"{type(e).__name__}: {e}"
            import pandas as pd2
            scores = (pd2.DataFrame.from_dict(rows, orient="index")
                      if rows else pd2.DataFrame())
            acc = pd2.Series({"n_tests": 240, "n_tickers": 12,
                              "base_big_beat_rate": 0.25,
                              "big_rate_when_score>=50": 0.45,
                              "n_score>=50": 40,
                              "big_rate_when_score<20": 0.1,
                              "n_score<20": 30, "lift_vs_base": 1.8,
                              "rank_corr_score_vs_next_surprise": 0.3,
                              "oos_n_tests": 96, "oos_base": 0.24,
                              "oos_big_rate_hi": 0.4, "oos_n_hi": 16,
                              "oos_brier_skill": 0.05})
            return types.SimpleNamespace(scores=scores, accuracy=acc,
                                         calibration=None,
                                         tests=pd2.DataFrame(),
                                         backtest=None, signals=None,
                                         errors=dict(self.errors), params={})
    emod.EarningsEngine = _Eng

    # env: auto net resolved online by the MEMO (no real probe), preflight
    # pinned to the LOOPBACK host only (hermeticity valves).
    os.environ.pop("MASTER_NET", None)
    os.environ["MASTER_NET_PREFLIGHT_HOSTS"] = f"127.0.0.1:{PORT}"
    os.environ["MASTER_STUBS"] = "0"
    os.environ["MASTER_RUN_BUDGET_S"] = "12"
    os.environ["MASTER_NET_DEFER_COOLDOWN_S"] = "0.2"
    os.environ["NET_NEG_CACHE_TTL_S"] = "21600"
    saved = master._NET_PROBE_MEMO
    master._NET_PROBE_MEMO = (True, "probe ok 1 ms")
    saved_neg = master.CONFIG["NET_NEG_CACHE_PATH"]
    import tempfile
    tmp = tempfile.mkdtemp(prefix="negcap_")
    master.CONFIG["NET_NEG_CACHE_PATH"] = str(Path(tmp) / "neg.json")
    for mod in ("meds", "quality", "earnings_engine"):
        sys.modules[mod] = {"meds": mmod, "quality": qmod,
                            "earnings_engine": emod}[mod]
    out_err = io.StringIO()
    try:
        argv = ["MU", "ZZ", "QQ", "429", "--mode", "quick",
                "--earnings-top", "4", "--timeout", "20", "--quiet"]
        ns = master._apply_mode(build_parser().parse_args(argv))
        master._validate_ns(ns)
        import contextlib
        with contextlib.redirect_stderr(out_err):
            out = master.run_pipeline(ns)
        text = master.render_report(out, ns)
        lines = text.splitlines()
        keep = []
        grab = False
        for ln in lines:
            if "FETCH HEALTH" in ln:
                grab = True
            if grab:
                keep.append(ln)
        print("=== FETCH HEALTH (captured from the LOOPBACK fault "
              "simulation — SIMULATED, never real provider data) ===")
        for ln in keep:
            print(ln)
        for ln in out_err.getvalue().splitlines():
            if "preflight:" in ln or "recovered" in ln or "skipped (" in ln:
                print("[stderr] " + ln[:150])
        return 0
    finally:
        master._NET_PROBE_MEMO = saved
        master.CONFIG["NET_NEG_CACHE_PATH"] = saved_neg
        os.environ.pop("MASTER_NET_PREFLIGHT_HOSTS", None)
        os.environ.pop("MASTER_RUN_BUDGET_S", None)
        os.environ.pop("MASTER_NET_DEFER_COOLDOWN_S", None)
        for m in ("meds", "quality", "earnings_engine"):
            sys.modules.pop(m, None)
        srv.shutdown()
        srv.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
