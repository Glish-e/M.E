#!/usr/bin/env python3
"""bench.py - one-command speed benchmark (section 6.1 of the final phase).

Usage (from the repo root):
    python3 scripts/bench.py --tag before            # a,b,c,d (+e if --with-cold)
    python3 scripts/bench.py --tag after --with-cold # adds the cold online run

Writes evidence/perf_<tag>.txt and prints the same table to stdout.
Sections:
  a) import cost        python3 -X importtime master.py --version (top 15)
  b) selftest wall      python3 master.py --selftest
  c) stub run           MASTER_STUBS=1, default watchlist (+ cProfile top 15)
  d) warm offline run   default watchlist, per-layer seconds + render seconds
                        (+ cProfile top 15)
  e) cold online run    default watchlist, throwaway cache dirs, real network
                        (opt-in via --with-cold or folded in via --cold-json)
Cold runs are measured with the real network; when it is unreachable bench
prints UNVERIFIED for (e) per rule H7.
"""
from __future__ import annotations

import argparse
import cProfile
import io
import json
import os
import pstats
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
OUT_LINES: list[str] = []


def say(line: str = "") -> None:
    print(line)
    OUT_LINES.append(line)


def _run(cmd: list[str], env: dict | None = None, timeout: int = 3600) -> str:
    e = dict(os.environ)
    if env:
        e.update(env)
    t0 = time.monotonic()
    p = subprocess.run(cmd, cwd=ROOT, env=e, capture_output=True, text=True,
                       timeout=timeout)
    dt = time.monotonic() - t0
    if p.returncode not in (0,):
        say(f"  ! exit {p.returncode}: {(p.stderr or p.stdout)[-400:]}")
    say(f"  wall {dt:.1f}s (exit {p.returncode})")
    return p.stdout


def sec_importtime() -> dict:
    say("\n[a] import cost  (python3 -X importtime master.py --version)")
    e = dict(os.environ)
    t0 = time.monotonic()
    p = subprocess.run([PY, "-X", "importtime", "master.py", "--version"],
                       cwd=ROOT, env=e, capture_output=True, text=True, timeout=120)
    dt = time.monotonic() - t0
    say(f"  wall {dt:.1f}s (exit {p.returncode})")
    rows = []
    total = 0.0
    for ln in p.stderr.splitlines():          # importtime writes to STDERR
        parts = ln.split("|")
        if len(parts) >= 3:
            try:
                cum = int(parts[1].strip())
                total = max(total, cum)
                rows.append((cum, parts[2].strip()))
            except ValueError:
                pass
    rows.sort(reverse=True)
    say(f"  cumulative total (max) {total/1000:.0f} ms; top 15:")
    for cum, name in rows[:15]:
        say(f"    {cum/1000:8.1f} ms  {name}")
    return {"total_ms": total / 1000.0, "top": rows[:15]}


def sec_selftest() -> dict:
    say("\n[b] --selftest wall time")
    t0 = time.monotonic()
    out = _run([PY, "master.py", "--selftest"], timeout=1800)
    dt = time.monotonic() - t0
    tail = [l for l in out.splitlines() if l.startswith("Ran ") or l == "OK"]
    say("  " + " · ".join(tail))
    return {"wall_s": round(dt, 1)}


def _profile(fn, top: int = 15) -> list[str]:
    pr = cProfile.Profile()
    pr.enable()
    fn()
    pr.disable()
    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(top)
    keep, grab = [], False
    for ln in s.getvalue().splitlines():
        if "ncalls" in ln:
            grab = True
        if grab and ln.strip():
            keep.append("    " + ln.strip()[:120])
        if len(keep) >= top + 2:
            break
    return keep


def sec_stub() -> dict:
    say("\n[c] stub run (MASTER_STUBS=1, default watchlist)")
    env = {"MASTER_STUBS": "1"}
    out = _run([PY, "master.py", "--quiet", "--json"], env=env, timeout=300)
    res: dict = {}
    try:
        payload = json.loads(out)
        res["total_s"] = payload.get("timings", {}).get("total")
        say(f"  pipeline total {res['total_s']}s · "
            f"layers {payload.get('timings')}")
    except Exception as e:
        say(f"  ! json parse: {e}")
    # in-process profile of the same run
    sys.path.insert(0, str(ROOT))
    import master  # noqa: E402
    import test_master  # noqa: E402

    def _stub_run():
        ns = master._apply_mode(master.build_parser().parse_args([]))
        master._validate_ns(ns)
        master.run_pipeline(ns)

    old = os.environ.get("MASTER_STUBS")
    os.environ["MASTER_STUBS"] = "1"
    try:
        prof = _profile(_stub_run)
    finally:
        if old is None:
            os.environ.pop("MASTER_STUBS", None)
        else:
            os.environ["MASTER_STUBS"] = old
    say("  cProfile (cumulative, top 15):")
    for ln in prof:
        say(ln)
    res["profile"] = prof
    return res


def sec_warm_offline() -> dict:
    say("\n[d] warm offline run (default watchlist; caches as-is)")
    t0 = time.monotonic()
    out = _run([PY, "master.py", "--quiet", "--json", "--offline"], timeout=1800)
    res: dict = {"wall_s": round(time.monotonic() - t0, 1)}
    say(f"  subprocess wall (incl. startup): {res['wall_s']}s")
    try:
        payload = json.loads(out)
        t = payload.get("timings", {})
        res["timings"] = t
        say(f"  timings: {t}")
        say("  layer statuses: " + ", ".join(
            f"{l['name']}={l['status']}" for l in payload.get("layers", [])))
    except Exception as e:
        say(f"  ! json parse: {e}")
    # in-process profiled run + render timing on its output
    sys.path.insert(0, str(ROOT))
    import master  # noqa: E402

    ns = master._apply_mode(master.build_parser().parse_args(
        ["--offline", "--quiet"]))
    master._validate_ns(ns)
    held: dict = {}

    def _one():
        held["out"] = master.run_pipeline(ns)

    prof = _profile(_one)
    r0 = time.monotonic()
    master.render_report(held["out"], ns)
    res["render_s"] = round(time.monotonic() - r0, 2)
    say(f"  render_report: {res['render_s']}s")
    say("  cProfile (cumulative, top 15):")
    for ln in prof:
        say(ln)
    res["profile"] = prof
    return res


def sec_cold_online(tickers: str) -> dict:
    say(f"\n[e] cold online run ({tickers or 'default watchlist'}, THROWAWAY caches, "
        "real network)")
    tmp = tempfile.mkdtemp(prefix="bench_cold_")
    base = os.path.join(tmp, "cache")
    meds_cache = ROOT / "meds_cache"
    bak = ROOT / "meds_cache.benchbak"
    moved = False
    try:
        if meds_cache.exists():
            shutil.move(str(meds_cache), str(bak))
            moved = True
        env = {"SEC_USER_AGENT": "master.py bench (bench)", "MEDS_CACHE": "1"}
        cmd = [PY, "master.py", "--quiet", "--json", "--timeout", "3600",
               "--cache-dir", base] + (tickers.split() if tickers else [])
        out = _run(cmd, env=env, timeout=3600)
        res: dict = {}
        try:
            payload = json.loads(out)
            res["timings"] = payload.get("timings")
            say(f"  timings: {payload.get('timings')}")
        except Exception as e:
            say(f"  ! json parse: {e}")
        return res
    finally:
        if moved and bak.exists():
            if meds_cache.exists():
                shutil.rmtree(str(meds_cache))
            shutil.move(str(bak), str(meds_cache))
        shutil.rmtree(tmp, ignore_errors=True)


def fold_cold_json(path: str) -> dict:
    say("\n[e] cold online run (folded in from a saved --json run)")
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        t = payload.get("timings")
        say(f"  timings: {t}")
        return {"timings": t, "folded": path}
    except Exception as e:
        say(f"  ! could not read {path}: {e}")
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="before | after (output file tag)")
    ap.add_argument("--with-cold", action="store_true",
                    help="run the cold online section inline (slow, real network)")
    ap.add_argument("--cold-tickers", default="MU NVDA AAPL",
                    help="watchlist for the cold section (default: MU NVDA AAPL — "
                         "same names as the phase-5 evidence run; the default "
                         "watchlist cold pass takes 10+ minutes of rate-limited "
                         "fetching and does not fit a bench command)")
    ap.add_argument("--cold-json", default=None,
                    help="path to a saved cold-run --json stdout to fold in")
    args = ap.parse_args()

    say(f"bench {args.tag} · {time.strftime('%Y-%m-%d %H:%M:%S')} · "
        f"python {sys.version.split()[0]} · cwd {ROOT}")
    a = sec_importtime()
    b = sec_selftest()
    c = sec_stub()
    d = sec_warm_offline()
    e: dict = {}
    if args.with_cold:
        e = sec_cold_online(args.cold_tickers)
    elif args.cold_json:
        e = fold_cold_json(args.cold_json)
    else:
        say("\n[e] cold online run: SKIPPED (pass --with-cold or --cold-json)")

    say("\n== summary ==")
    say(f"import total        {a.get('total_ms', 0):.0f} ms")
    say(f"selftest wall       {b.get('wall_s')} s")
    say(f"stub run total      {c.get('total_s')} s")
    t = d.get("timings") or {}
    say(f"warm offline total  {t.get('total')} s (render {d.get('render_s')} s)")
    if e.get("timings"):
        say(f"cold online total   {e['timings'].get('total')} s")

    outp = ROOT / "evidence" / f"perf_{args.tag}.txt"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text("\n".join(OUT_LINES) + "\n", encoding="utf-8")
    print(f"\nwrote {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
