#!/usr/bin/env python3
"""Invariant and fuzz tests over the decision core (read-only run: reports
violations, changes nothing).

PHASE 2 PORT (v1.7.0-dev): ported by function name from v1.4.1's
scripts/fuzz_decisions.py (seed 88117 kept for comparability with the
v1.4.1 hunt evidence). The v1.5.0 tree ships none of the hunt scripts;
every imported symbol was re-verified present on this base before the
port. I3 carries the v1.4.1 HARDENED contract (the "fuzz I3 update":
blocked => AVOID + below-WATCH; only the sanctioned WATCH-1 re-assert cap
may change a blocked row's conviction) — see evidence/fixture_changes.md.

Seeded, 24,000+ cases with edge values (NaN, inf, 0, negatives, huge,
empty, missing layers). Invariants:
  I1 conviction in [0,100]
  I2 weights >= 0 and sum <= budget
  I3 vetoed / gate-failed never LONG
  I4 MONOTONICITY: raising Q (others fixed) never lowers the raw fused
     conviction; same for E
  I5 missing earnings data never RAISES conviction vs a present E (the
     missing-data penalty must not become a subsidy) — reported, judged
  I5b PHASE 4 (P-1): under ruleset v2 the conservative fill can NEVER let
     a missing-E name outrank an observed-E name (fuzzed over q, e, weak)
  I6 same input twice -> same output (determinism)
  I7 shuffling ticker order -> same per-ticker decisions
  I8 0-1 unit-scale scores never silently accepted as 0-100 (a 0.85 must
     never act like 85)
  I9 no exception escapes

Usage: python3 scripts/fuzz_decisions.py
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import master                                                        # noqa: E402
from master import (Candidate, Decision, LayerResult, LayerSignal,    # noqa: E402
                    MacroState, fuse_candidate, size_portfolio,
                    _apply_overlays, _ml_adjustment, _ml_scaled,
                    _base_conviction, _map_plan_row)
from datetime import date

N_FUSE = 12000
N_SIZER = 4000
N_OVERLAY = 2000
N_ML = 2000
N_PLAN = 2000
N_MONO = 2400
SEED = 88117

SCORE_POOL = [None, float("nan"), float("inf"), float("-inf"), -5.0, 0.0,
              0.7, 0.85, 1.0, 20.0, 39.9, 40.0, 44.9, 45.0, 55.0, 59.9,
              60.0, 60.1, 72.0, 85.0, 99.9, 100.0, 100.5, 1e6, -0.0]
STATUS_POOL = ["OK", "ERROR", "MISSING", "MISSING_DATA", "DEGRADED", ""]
FLAG_POOL = [(), ("NEGATIVE_EQUITY",), ("ALTMAN_DISTRESS",),
             ("NEGATIVE_EQUITY", "ALTMAN_DISTRESS"), ("WEIRD_FLAG",),
             ("negative_equity",)]                      # case variant
MODE_POOL = ["boost", "trigger", "weird"]
SECTORS = ["tech", "consumer", "staples", "discretionary", "financials",
           "healthcare", "reits", "utilities", "energy", "materials",
           "industrials", "communication", "specialty", "", None]


def rand_macro(rng):
    if rng.random() < 0.08:
        return None
    key = rng.choice(["HARD_LANDING", "SOFT_LANDING_PIVOT", "NEUTRAL_WAIT_AND_SEE",
                      "CREDIT_CRUNCH", "GOLDILOCKS", "", "WEIRD"])
    longs = rng.choice([(), ("SPY",), ("QQQ", "XLY"), ("TLT", "BIL"),
                        ("XLE", "XLI", "XLV", "XLF"), ("XLP",), ("XLY",),
                        ("SGOV", "BIL")])
    return MacroState(
        status=rng.choice(["OK", "OK", "OK", "DEGRADED", "ERROR"]),
        scenario_key=key, regime_class=rng.choice(["risk_on", "defensive", "neutral", ""]),
        conviction_leverage=rng.choice([0.0, 0.5, 1.0, 1.35, 2.0, 10.0]),
        confidence=rng.choice([0.0, 0.5, 0.9]), credit=rng.choice(["ON", "OFF"]),
        data_tier=rng.choice(["api", "public", "cache", "snapshot", ""]),
        longs=longs, source="fuzz")


def rand_sig(rng, layer):
    score = rng.choice(SCORE_POOL)
    status = rng.choice(STATUS_POOL)
    if score is not None and not (isinstance(score, float) and math.isfinite(score)):
        status = "OK"                      # smuggle NaN/inf with OK status
    facts = {"sector": rng.choice(SECTORS[:12]), "macro_sector": rng.choice(SECTORS[:12]),
             "rank": rng.choice([1, 5, None, "3"]), "pool_size": rng.choice([40, 0, None]),
             "plan": rng.choice([None, "LONG", "open", "ENTER", "closed"]),
             "engine_status": rng.choice(STATUS_POOL)}
    return LayerSignal("T", layer, score=score, status=status,
                       flags=rng.choice(FLAG_POOL), facts=facts)


def main() -> int:
    rng = random.Random(SEED)
    viol: dict[str, list[str]] = {}
    counts: dict[str, int] = {}

    def bump(k):
        counts[k] = counts.get(k, 0) + 1

    def v(k, msg):
        viol.setdefault(k, []).append(msg)

    # ── fuse_candidate fuzz ───────────────────────────────────────────────
    long_blocked = 0
    for i in range(N_FUSE):
        q = rand_sig(rng, "quality")
        e = rand_sig(rng, "earnings")
        st = rand_macro(rng)
        cand = Candidate(ticker=f"T{i%7}", sector=rng.choice(SECTORS[:12]))
        mode = rng.choice(MODE_POOL)
        weak = rng.random() < 0.3
        try:
            d = fuse_candidate(cand, q, e, st, mode, weak)
        except Exception as exc:
            v("I9-exception-fuse", f"case {i}: {type(exc).__name__}: {exc} "
              f"q={q.score!r}/{q.status} e={e.score!r}/{e.status}")
            continue
        bump("fuse")
        if not (0.0 <= d.conviction <= 100.0):
            v("I1-conviction-range", f"case {i}: conviction={d.conviction!r} "
              f"q={q.score!r}/{q.status} e={e.score!r}/{e.status} weak={weak}")
        if d.blocked and d.action != "AVOID":
            v("I3-blocked-not-avoid", f"case {i}: blocked={d.blocked!r} "
              f"action={d.action}")
        if d.blocked in ("veto", "gate") and d.action == "LONG":
            long_blocked += 1
            v("I3-veto-long", f"case {i}: blocked={d.blocked} action=LONG")
        # I8: unit-scale check — a valid 0..1 score must never make LONG
        if q.status == "OK" and isinstance(q.score, (int, float)) \
                and math.isfinite(q.score) and 0 < q.score < 1.5 \
                and d.action == "LONG":
            v("I8-unit-scale", f"case {i}: q={q.score} -> action={d.action} "
              f"conv={d.conviction}")
        if d.action not in ("LONG", "WATCH", "AVOID"):
            v("I0-unknown-action", f"case {i}: action={d.action!r}")
        if not isinstance(d.reasons, list) or len(d.reasons) > master.CONFIG["MAX_REASONS"]:
            v("I0-reasons", f"case {i}: {len(d.reasons)} reasons")

    # ── size_portfolio fuzz ───────────────────────────────────────────────
    for i in range(N_SIZER):
        n = rng.randint(0, 8)
        names = [f"L{j}" for j in range(n)]
        if n and rng.random() < 0.05:
            names.append(names[0])                      # duplicate ticker
        vols = {}
        for t in set(names):
            vols[t] = rng.choice([None, 0.0, -0.3, float("nan"), float("inf"),
                                  1e-9, 0.15, 0.35, 0.8, 3.0, 250.0])
        rho = rng.choice([None, -1.0, 0.0, 0.35, 0.999, 1.0, 1.5, float("nan")])
        budget = rng.choice([0.0, -1.0, 0.2, 0.24, 0.25, 1.0, 1.35, 2.0, 1e6,
                             float("nan")])
        secs = {t: rng.choice(SECTORS) for t in set(names)}
        try:
            r = size_portfolio(names, vols, rho, secs, budget)
        except Exception as exc:
            v("I9-exception-sizer", f"case {i}: {type(exc).__name__}: {exc} "
              f"budget={budget!r} rho={rho!r}")
            continue
        bump("sizer")
        ws = r["weights"]
        for t, w in ws.items():
            if not (isinstance(w, float) and w >= 0.0 and math.isfinite(w)):
                v("I2-weight-invalid", f"case {i}: w[{t}]={w!r} budget={budget!r} "
                  f"rho={rho!r} vols={vols!r}")
                break
        s = sum(ws.values())
        if math.isfinite(budget) and budget >= 0 and (not math.isfinite(s) or s > budget + 1e-9):
            v("I2-sum-over-budget", f"case {i}: sum={s!r} budget={budget!r}")
        if budget < master.CONFIG["RISK_MIN_BUDGET"] and ws and budget >= 0 \
                and math.isfinite(budget):
            v("I2-lowbudget-weights", f"case {i}: budget={budget} but weights={ws}")
        if not math.isfinite(budget) and ws:
            v("I2-nan-budget-weights", f"case {i}: budget={budget!r} -> weights {ws!r}")

    # ── _apply_overlays fuzz ──────────────────────────────────────────────
    for i in range(N_OVERLAY):
        decs = []
        for j in range(rng.randint(1, 5)):
            d = Decision(ticker=f"O{j}", sector="tech")
            d.conviction = rng.choice([0.0, 30.0, 44.9, 45.0, 58.0, 60.0, 95.0, 100.0])
            d.action = rng.choice(["LONG", "WATCH", "AVOID"])
            d.blocked = rng.choice(["", "veto", "gate", "no quality score"])
            d.grade = "C"
            if rng.random() < 0.5:
                d.layers["macro"] = LayerSignal(
                    f"O{j}", "macro", facts={"tilt": rng.choice([None, 0.0, -0.5, 1.0])})
            decs.append(d)
        res = LayerResult(name="ml", order=4, stage="overlay", status="OK")
        for d in decs:
            if rng.random() < 0.85:
                adj = rng.choice([None, 0.0, 5.0, -5.0, 10.0, -10.0, 100.0,
                                  -100.0, float("nan"), float("inf")])
                res.signals[d.ticker] = LayerSignal(d.ticker, "ml", status="OK",
                                                    facts={"conviction_adj": adj,
                                                           "p_note": "x"})
        was_blocked = [(d.ticker, d.blocked) for d in decs if d.blocked]
        was_conv = {d.ticker: d.conviction for d in decs}
        try:
            _apply_overlays(decs, {"ml": res}, rng.choice(["boost", "trigger"]))
        except Exception as exc:
            v("I9-exception-overlay", f"case {i}: {type(exc).__name__}: {exc}")
            continue
        bump("overlay")
        for d in decs:
            if not (0.0 <= d.conviction <= 100.0):
                v("I1-overlay-range", f"case {i}: {d.ticker} conv={d.conviction!r}")
            # v1.4.1 (B5): a blocked row must END as AVOID with conviction
            # capped below WATCH (the same treatment fuse gives veto/gate
            # rows). Hand-built inconsistent states (blocked but LONG /
            # WATCH, or uncapped) are CORRECTED here, not preserved — the
            # pre-B5 invariant "blocked rows pass through untouched" would
            # flag the fix itself, so the invariant is now the hardened
            # contract: AVOID + below-WATCH, and never adjusted further by
            # the adjustment arithmetic itself (no SHADOW path may touch a
            # blocked row's conviction).
            if d.blocked and d.action != "AVOID":
                v("I3-overlay-blocked", f"case {i}: {d.ticker} blocked={d.blocked!r} "
                  f"action={d.action}")
            if d.blocked and d.conviction >= master.CONFIG["ACTION_WATCH_AT"]:
                v("I3-overlay-blocked-uncapped", f"case {i}: {d.ticker} blocked "
                  f"conv {d.conviction} >= WATCH "
                  f"{master.CONFIG['ACTION_WATCH_AT']}")
            if d.blocked and d.conviction != was_conv.get(d.ticker) \
                    and d.conviction != round(
                        master.CONFIG["ACTION_WATCH_AT"] - 1.0, 1):
                # only the sanctioned B5 re-assert cap may change a blocked
                # row's conviction, and only to exactly WATCH-1; any other
                # change means the adjustment arithmetic touched it
                v("I3-overlay-adjusted-blocked", f"case {i}: {d.ticker} blocked "
                  f"conv {was_conv.get(d.ticker)} -> {d.conviction}")

    # ── _ml_adjustment / _ml_scaled fuzz ──────────────────────────────────
    for i in range(N_ML):
        parts = []
        for _ in range(rng.randint(0, 4)):
            parts.append((rng.choice([0.0, 0.65, 0.35, -1.0, float("nan"), 5.0]),
                          rng.choice([None, 0.0, 0.5, 1.0, float("nan"), -2.0]),
                          rng.choice([None, 0.0, 0.5, 1.0, float("nan"), 1e-9]),
                          rng.random() < 0.7))
        try:
            a = _ml_adjustment(parts)
        except Exception as exc:
            v("I9-exception-ml", f"case {i}: {type(exc).__name__}: {exc} parts={parts!r}")
            continue
        bump("ml")
        if a is not None and not (isinstance(a, float) and math.isfinite(a)
                                  and abs(a) <= master.CONFIG["OVERLAY_MAX_ADJ"] + 1e-9):
            v("I1-ml-bound", f"case {i}: adj={a!r} parts={parts!r}")
        try:
            s = _ml_scaled(rng.choice([0.0, 0.5, 1.0, float("nan"), -1.0, 2.0]),
                           rng.choice([0.0, 0.5, 1.0, float("nan"), 1e-12]))
            if s is not None and not (-1.0 - 1e-9 <= s <= 1.0 + 1e-9):
                v("I1-ml-scaled-range", f"case {i}: s={s!r}")
        except Exception as exc:
            v("I9-exception-mlscaled", f"case {i}: {type(exc).__name__}: {exc}")

    # ── _map_plan_row fuzz (NOW-chip freshness rule) ─────────────────────
    for i in range(N_PLAN):
        row = {"action": rng.choice(["LONG", "LONG (enter)", "ENTER", "closed",
                                     "skip", "error: bad", "", "LONGER"]),
               "event_date": rng.choice([None, "", "2026-11-01", "2026-13-99",
                                         "2027-01-01", "2020-01-01", 12345,
                                         "not-a-date"]),
               "entry_px": rng.choice([None, 100.0, float("nan")]),
               "target_px": None, "planned_exit": rng.choice([None, "2027-02-05"])}
        try:
            r = _map_plan_row(row, date(2026, 11, 13))
        except Exception as exc:
            v("I9-exception-plan", f"case {i}: {type(exc).__name__}: {exc} row={row!r}")
            continue
        bump("plan")
        if r["status"] == "LONG" and isinstance(row.get("event_date"), str):
            try:
                ev = date.fromisoformat(row["event_date"])
                if ev > date(2026, 11, 13):
                    v("I5-future-report-NOW", f"case {i}: future event "
                      f"{row['event_date']} got NOW status LONG")
            except ValueError:
                pass

    # ── I4 monotonicity (structured, not random) ──────────────────────────
    st_ok = MacroState(status="OK", scenario_key="SOFT_LANDING_PIVOT",
                       regime_class="risk_on", conviction_leverage=1.35,
                       credit="ON", data_tier="public", longs=("SPY", "QQQ", "XLY"),
                       source="mono")
    bad = 0
    for i in range(N_MONO):
        q0 = rng.uniform(40.0, 100.0)
        e0 = rng.choice([None, rng.uniform(0.0, 100.0)])
        weak = rng.random() < 0.3
        q1 = min(100.0, q0 + rng.uniform(0.0, 25.0))
        e1 = e0
        c0 = _base_conviction(q0, e0, weak)
        c1 = _base_conviction(q1, e1, weak)
        if c1 < c0 - 1e-9:
            bad += 1
            v("I4-Q-monotonic", f"iter {i}: q {q0}->{q1} raw {c0}->{c1} "
              f"e={e0} weak={weak}")
        if e0 is not None:
            e2 = min(100.0, e0 + rng.uniform(0.0, 25.0))
            c_base = _base_conviction(q0, e0, weak)
            c2 = _base_conviction(q0, e2, weak)
            if c2 < c_base - 1e-9 and e2 >= e0:
                v("I4-E-monotonic", f"iter {i}: e {e0}->{e2} raw {c_base}->{c2} q={q0}")
    # I5: missing-E vs bad-E subsidy probe (structural)
    subsidy = 0
    for q in (50.0, 60.0, 70.0, 80.0, 90.0):
        for e_bad in (5.0, 15.0, 25.0, 35.0):
            c_missing = _base_conviction(q, None, False)
            c_bad = _base_conviction(q, e_bad, False)
            if c_missing > c_bad:
                subsidy += 1
    # I5b (phase 4, P-1): ruleset v2 invariant — the fixed conservative
    # fill means base(missing E) <= base(observed E) for EVERY observed
    # E >= 0, weak or not. Fuzzed across the full q/e space; any violation
    # is a crash of the v2 contract, not a judgement call.
    v2_checked = 0
    v2_bad = 0
    master.CONFIG["RULESET"] = "v2"
    master.CONFIG["E_MISSING_V2"] = 0.0
    try:
        for _ in range(N_MONO):
            q0 = rng.uniform(40.0, 100.0)
            e0 = rng.uniform(0.0, 100.0)
            for weak in (False, True):
                v2_checked += 1
                miss = _base_conviction(q0, None, weak)
                obs = _base_conviction(q0, e0, weak)
                if miss > obs + 1e-9:
                    v2_bad += 1
                    v("I5b-v2-missing-outranks",
                      f"q={q0:.3f} e={e0:.3f} weak={weak}: missing {miss:.4f} "
                      f"> observed {obs:.4f}")
    finally:
        master.CONFIG["RULESET"] = "legacy"
    # I6 determinism + I7 order independence
    cases = []
    for i in range(60):
        cases.append((Candidate(ticker=f"D{i}", sector="tech"),
                      rand_sig(rng, "quality"), rand_sig(rng, "earnings")))
    run1 = [fuse_candidate(c, q, e, st_ok, "boost", False) for c, q, e in cases]
    run2 = [fuse_candidate(c, q, e, st_ok, "boost", False) for c, q, e in cases]
    for (c, q, e), d1, d2 in zip(cases, run1, run2):
        if (d1.action, d1.conviction) != (d2.action, d2.conviction):
            v("I6-determinism", f"{c.ticker}: {d1.action}/{d1.conviction} vs "
              f"{d2.action}/{d2.conviction}")
    shuffled = list(cases)
    rng.shuffle(shuffled)
    run3 = {c.ticker: fuse_candidate(c, q, e, st_ok, "boost", False)
            for c, q, e in shuffled}
    for (c, q, e), d1 in zip(cases, run1):
        d3 = run3[c.ticker]
        if (d1.action, d1.conviction) != (d3.action, d3.conviction):
            v("I7-order-independence", f"{c.ticker}: {d1.action}/{d1.conviction} "
              f"vs {d3.action}/{d3.conviction}")
    # sizer order independence
    names = [f"S{j}" for j in range(8)]
    vols = {t: 0.2 + 0.07 * j for j, t in enumerate(names)}
    secs = {t: ["tech", "healthcare"][j % 2] for j, t in enumerate(names)}
    r1 = size_portfolio(names, vols, 0.4, secs, 1.35)
    r2 = size_portfolio(list(reversed(names)), {k: vols[k] for k in reversed(names)},
                        0.4, {k: secs[k] for k in reversed(secs)}, 1.35)
    if {k: round(v, 9) for k, v in r1["weights"].items()} != \
            {k: round(v, 9) for k, v in r2["weights"].items()}:
        v("I7-sizer-order", f"{r1['weights']} vs {r2['weights']}")

    # ── report ────────────────────────────────────────────────────────────
    print("FUZZ DECISIONS — invariant fuzz (seed %d)" % SEED)
    print("=" * 76)
    total = sum(counts.values())
    print(f"cases executed: {total}  (fuse={counts.get('fuse',0)}, "
          f"sizer={counts.get('sizer',0)}, overlay={counts.get('overlay',0)}, "
          f"ml={counts.get('ml',0)}, plan={counts.get('plan',0)}, "
          f"mono={N_MONO}, det/order=120)")
    print(f"invariant suites with violations: "
          f"{sum(1 for k in viol if not k.startswith('NOTE'))}")
    print()
    if not viol:
        print("ALL INVARIANTS PASS — no violations.")
    for k in sorted(viol):
        lst = viol[k]
        print(f"-- {k}: {len(lst)} violation(s), first 5:")
        for m in lst[:5]:
            print(f"     {m}")
    print()
    print(f"NOTE I5 structural probe: missing-E beats bad-E in {subsidy}/20 "
          f"(q, e_bad) combos — the E_MISSING_HAIRCUT 0.90 subsidy for missing "
          f"data vs bad data (judged a rules finding, not a crash).")
    print(f"NOTE I5b v2 invariant (phase 4): {v2_checked} (q, e, weak) cases "
          f"fuzzed under ruleset v2 — missing-E outranks observed-E in "
          f"{v2_bad} (must be 0; the E_MISSING_V2=0.0 fill guarantees it).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
