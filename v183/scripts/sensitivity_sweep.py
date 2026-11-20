#!/usr/bin/env python3
"""SENSITIVITY SWEEP over every numeric CONFIG key and the hard-coded
decision rules, on (a) a fixed deterministic stub universe and (b) the real
pilot dataset rows (ml_data/dataset_v1.npz) when present.

PHASE 2 PORT (v1.7.0-dev): ported by function name from v1.4.1's
scripts/sensitivity_sweep.py; every swept literal/CONFIG key was verified
present on this base before the port. The ONE addition: RISK_FALLBACK_RHO
(the phase-2 B2 CONFIG addition) is swept like every other numeric key.

For each rule: perturb -20% / +20%, record action flips, rank changes
(pairwise inversions), max conviction move, max weight move. Zero effect
on any metric = dead or unreachable rule for decisions.

Usage: python3 scripts/sensitivity_sweep.py
"""
from __future__ import annotations

import copy
import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import master                                                        # noqa: E402
from master import (Candidate, LayerSignal, MacroState,              # noqa: E402
                    fuse_candidate, size_portfolio, _rank_key)

SEED = 20261113

# ── the deterministic stub universe ────────────────────────────────────────
Q_GRID = [25.0, 39.9, 40.0, 45.0, 55.0, 60.0, 65.0, 72.0, 85.0, 100.0]
E_GRID = [None, 20.0, 40.0, 55.0, 70.0, 90.0]
SECTORS = ["tech", "consumer", "staples", "discretionary", "financials",
           "healthcare", "industrials", "energy", "utilities", "reits"]


def macro_states() -> dict[str, MacroState]:
    def st(key, cls, longs, degraded=False, status="OK"):
        return MacroState(status=("DEGRADED" if degraded else status),
                          scenario_key=key, regime_class=cls,
                          conviction_leverage=1.35, confidence=0.8, dominance=0.3,
                          credit="ON", quality_tier="MED", data_tier="public",
                          trade_month="2026-12", longs=longs, source="sweep",
                          engine_version="sweep")
    return {"risk_on": st("SOFT_LANDING_PIVOT", "risk_on", ("SPY", "QQQ", "XLY")),
            "risk_on_xl": st("EARLY_CYCLE_RE_ACCELERATION", "risk_on",
                             ("SPY", "QQQ", "XLE", "XLI", "XLV", "XLF")),
            "defensive": st("HARD_LANDING", "defensive", ("TLT", "BIL")),
            "defensive_damped": st("HARD_LANDING", "defensive", ("TLT", "BIL"),
                                   degraded=True),
            "neutral": st("NEUTRAL_WAIT_AND_SEE", "neutral", ("SPY",)),
            "down": st("", "", (), status="ERROR")}


def q_sig(t, score, sector, flags=()):
    return LayerSignal(t, "quality", score=score, status="OK", flags=flags,
                       facts={"sector": sector, "macro_sector": sector,
                              "rank": 1, "pool_size": 40, "engine_status": "OK"})


def e_sig(t, score, plan=None):
    if score is None:
        return LayerSignal(t, "earnings", status="MISSING_DATA",
                           facts={"plan": None, "now": False})
    return LayerSignal(t, "earnings", score=score, status="OK",
                       facts={"plan": plan, "now": plan == "LONG"})


def build_cases() -> list[dict]:
    """Deterministic boundary-covering case matrix (~150 cases)."""
    cases = []
    ms = macro_states()
    mkeys = list(ms)
    i = 0
    for q in Q_GRID:
        for e in E_GRID:
            mk = mkeys[i % len(mkeys)]
            sector = SECTORS[i % len(SECTORS)]
            flags = ("NEGATIVE_EQUITY",) if (i % 17 == 0 and q >= 40) else ()
            cases.append({"id": f"c{i:03d}", "q": q, "e": e, "sector": sector,
                          "flags": flags, "macro": mk, "weak": (i % 7 == 0),
                          "mode": "trigger" if i % 5 == 0 else "boost",
                          "plan": "LONG" if i % 3 == 0 else "open"})
            i += 1
    # extra boundary probes: exactly at the doors, gate edge, cap edge
    for q, e, mk, note in [(59.9, 80.0, "risk_on", "below LONG door"),
                           (60.0, 80.0, "risk_on", "at LONG door"),
                           (60.1, 80.0, "risk_on", "above LONG door"),
                           (44.9, None, "risk_on", "below WATCH door"),
                           (45.0, None, "risk_on", "at WATCH door"),
                           (61.0, 80.0, "defensive", "LONG-door defensive cap"),
                           (61.0, 80.0, "defensive_damped", "damped defensive"),
                           (85.0, 20.0, "risk_on", "great Q terrible E"),
                           (85.0, None, "risk_on", "great Q missing E"),
                           (85.0, 20.0, "risk_on", "great Q terrible E weak"),
                           (40.0, 95.0, "risk_on", "gate edge great E")]:
        cases.append({"id": f"x{len(cases):03d}:{note}", "q": q, "e": e,
                      "sector": "tech", "flags": (), "macro": mk,
                      "weak": "weak" in note, "mode": "boost", "plan": "LONG"})
    return cases


def run_cases(mod, cases) -> list[tuple]:
    out = []
    ms = macro_states()
    for c in cases:
        cand = Candidate(ticker=c["id"].split(":")[0], sector=c["sector"])
        d = mod.fuse_candidate(cand, q_sig("T", c["q"], c["sector"], c["flags"]),
                               e_sig("T", c["e"], c["plan"]),
                               ms[c["macro"]], c["mode"], c["weak"])
        out.append((c["id"], d.action, d.conviction, d.grade))
    return out


def sizer_cases() -> dict[str, dict]:
    return {
        "A_8names_2sec_rho35": (["L1", "L2", "L3", "L4", "W1", "W2", "W3", "W4"],
                                {"L1": .25, "L2": .30, "L3": .45, "L4": .60,
                                 "W1": .20, "W2": .35, "W3": .50, "W4": .80}, 0.35,
                                {"L1": "tech", "L2": "tech", "L3": "tech",
                                 "L4": "tech", "W1": "healthcare", "W2": "healthcare",
                                 "W3": "healthcare", "W4": "healthcare"}, 1.35),
        "B_2names_rhoNone": (["L1", "L2"], {"L1": .30, "L2": .50}, None,
                             {"L1": "tech", "L2": "tech"}, 1.35),
        "C_12names_1sec_rho8": ([f"N{i}" for i in range(12)],
                                {f"N{i}": .30 + .04 * i for i in range(12)}, 0.80,
                                {f"N{i}": "tech" for i in range(12)}, 1.0),
        "D_3names_hivol_rho99": (["L1", "L2", "L3"],
                                 {"L1": .20, "L2": 1.20, "L3": .90}, 0.99,
                                 {"L1": "tech", "L2": "tech", "L3": "tech"}, 2.0),
        "E_lowbudget": (["L1", "L2"], {"L1": .3, "L2": .4}, 0.5,
                        {"L1": "tech", "L2": "tech"}, 0.2),
        "F_30names_lowcorr_hivol": ([f"P{i}" for i in range(30)],
                                    {f"P{i}": 0.60 for i in range(30)}, 0.05,
                                    {f"P{i}": ["tech", "healthcare"][i % 2] for i in range(30)}, 2.0),
        "G_30names_at_dd_edge": ([f"Q{i}" for i in range(30)],
                                 {f"Q{i}": 0.45 for i in range(30)}, 0.06,
                                 {f"Q{i}": ["tech", "healthcare"][i % 2] for i in range(30)}, 1.56),
    }


def run_sizer(mod) -> dict[str, tuple]:
    out = {}
    for k, (longs, vols, rho, secs, bud) in sizer_cases().items():
        r = mod.size_portfolio(list(longs), dict(vols), rho, dict(secs), bud)
        out[k] = (tuple(sorted((t, round(w, 6)) for t, w in r["weights"].items())),
                  round(r["gross"], 6), r["veto"] != "")
    return out


def rank_key_of(rows):
    return [(a, -c, i) for i, a, c, _g in rows]


def inversions(base, other) -> int:
    b = {r[0]: (_ord(r[1]), -r[2]) for r in base}
    o = {r[0]: (_ord(r[1]), -r[2]) for r in other}
    ids = [r[0] for r in base]
    inv = 0
    for x in range(len(ids)):
        for y in range(x + 1, len(ids)):
            if (b[ids[x]] < b[ids[y]]) != (o[ids[x]] < o[ids[y]]):
                inv += 1
    return inv


def _ord(a):
    return {"LONG": 0, "WATCH": 1, "AVOID": 2}.get(a, 3)


def diff_rows(base, other):
    flips = sum(1 for b, o in zip(base, other) if b[1] != o[1])
    maxdc = max((abs(b[2] - o[2]) for b, o in zip(base, other)), default=0.0)
    gflips = sum(1 for b, o in zip(base, other) if b[3] != o[3])
    return flips, maxdc, gflips


NUMERIC_CFG = ["W_Q", "W_E", "E_MISSING_HAIRCUT", "EARNINGS_WEAK_SCALE",
               "MACRO_TILT_GAIN", "MACRO_DEGRADED_DAMP", "MIN_QUALITY",
               "ACTION_LONG_AT", "ACTION_WATCH_AT", "RISK_MAX_NAME_W",
               "RISK_MAX_SECTOR_W", "RISK_MIN_EFFECTIVE_BETS", "RISK_DD_FACTOR",
               "RISK_MAX_EST_DD", "RISK_MIN_BUDGET", "RISK_CAP_DEGRADED",
               "OVERLAY_MAX_ADJ", "ML_ADJ_MAX", "EARNINGS_MAX_AGE",
               "EARNINGS_PLAN_MIN", "EARNINGS_HOLD_DAYS", "EARNINGS_TP",
               "MACRO_SNAPSHOT_MAX_AGE_H", "PRICE_TTL_H", "RISK_VOL_LOOKBACK_TD",
               "RISK_CORR_LOOKBACK_TD", "RISK_MIN_HISTORY_TD",
               "RISK_MAX_PRICE_NAMES", "EARNINGS_QUARTERS", "DEFAULT_WORKERS",
               "LAYER_TIMEOUT_S", "EARNINGS_TOP_K", "PREFETCH_ALL_MAX",
               "WARM_TIMEOUT_S", "COLD_S_PER_NAME", "WARM_ETA_RANGE_S",
               "DEFAULT_TOP", "DEFAULT_MIN_CONV", "MIN_TERM_WIDTH",
               "MAX_TERM_WIDTH", "BAR_COLS", "MAX_REASONS", "DEFAULT_WATCHLIST",
               "RISK_FALLBACK_RHO"]   # phase-2 B2 addition: swept like the rest
BAND_KEYS = ["MASTER_GRADES", "QUALITY_NATIVE_GRADES", "EARNINGS_NATIVE_GRADES"]


def perturbed_module(literal: str, repl: str, tag: str):
    """Load a copy of master.py with ONE literal replaced (never touches
    the file on disk). Returns (module, n_replacements)."""
    src = (ROOT / "master.py").read_text(encoding="utf-8")
    n = src.count(literal)
    if n == 0:
        return None, 0
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / f"master_{tag}.py"
        p.write_text(src.replace(literal, repl), encoding="utf-8")
        spec = importlib.util.spec_from_file_location(f"master_{tag}", p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod, n


def main() -> int:
    print("SENSITIVITY SWEEP — stub universe + real pilot rows (v1.4.1 port)")
    print("=" * 88)
    cases = build_cases()
    base_rows = run_cases(master, cases)
    base_sz = run_sizer(master)
    results: list[tuple[int, str, str, str]] = []   # effect, key, pm, note

    def sweep_key(key, val, pm, rows=None, sz=None):
        old = master.CONFIG[key]
        master.CONFIG[key] = val
        try:
            r = run_cases(master, cases)
            s = run_sizer(master)
        finally:
            master.CONFIG[key] = old
        flips, maxdc, gfl = diff_rows(base_rows if rows is None else rows, r)
        inv = inversions(base_rows, r)
        wchg = 0.0
        szflips = 0
        for k in base_sz:
            if s[k] != base_sz[k]:
                szflips += 1
                b = dict(base_sz[k][0]); o = dict(s[k][0])
                for t in b:
                    wchg = max(wchg, abs(b[t] - o.get(t, 0.0)))
        note = (f"flips={flips} grade_flips={gfl} inversions={inv} "
                f"maxdconv={maxdc:.1f} sizer_cases_changed={szflips} maxdw={wchg:.3f}")
        results.append((flips + gfl + inv + szflips * 2 + round(maxdc * 10), key, pm, note))

    for key in NUMERIC_CFG:
        v = master.CONFIG[key]
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            for pm, f in (("-20%", 0.8), ("+20%", 1.2)):
                sweep_key(key, type(v)(v * f), pm)
        elif isinstance(v, tuple) and v and all(isinstance(x, (int, float))
                                                for x in v):
            for pm, f in (("-20%", 0.8), ("+20%", 1.2)):
                sweep_key(key, tuple(type(x)(x * f) for x in v), pm)
        else:
            results.append((0, key, "n/a", f"type={type(v).__name__} — not numeric, skipped"))

    for bk in BAND_KEYS:
        bands = master.CONFIG[bk]
        for pm, f in (("-20%", 0.8), ("+20%", 1.2)):
            nb = tuple((round(th * f, 1) if isinstance(th, float) else th, g)
                       for th, g in bands)
            sweep_key(bk, nb, pm)
        master.CONFIG[bk] = bands

    # hard-coded rules (source-copy perturbation; count must be exact)
    print("\nHARD-CODED RULE SWEEPS (source-copy, file untouched)")
    hc = [("-0.5\n        return 0.0", None), ]  # placeholder, real ones below
    for lit, repl, tag, where in [
            ("return -0.5", "return -0.4", "tiltA", "macro_tilt defensive -0.5 (x2 sites)"),
            ("return -0.5", "return -0.6", "tiltB", "macro_tilt defensive -0.5 (x2 sites)"),
            ("min(lev, 2.0)", "min(lev, 1.6)", "budgetA", "_risk_budget 2.0 cap"),
            ("min(lev, 2.0)", "min(lev, 2.4)", "budgetB", "_risk_budget 2.0 cap"),
            ("cap = round(CONFIG[\"ACTION_WATCH_AT\"] - 1.0, 1)",
             "cap = round(CONFIG[\"ACTION_WATCH_AT\"] - 0.8, 1)",
             "capA", "AVOID conviction cap WATCH-1"),
    ]:
        mod, n = perturbed_module(lit, repl, tag)
        if mod is None or n == 0:
            print(f"  {where}: literal not found — SKIPPED")
            continue
        r = run_cases(mod, cases)
        flips, maxdc, gfl = diff_rows(base_rows, r)
        inv = inversions(base_rows, r)
        s = run_sizer(mod)
        szf = sum(1 for k in base_sz if s[k] != base_sz[k])
        print(f"  {where}: sites={n} flips={flips} inversions={inv} "
              f"maxdconv={maxdc:.1f} sizer_changed={szf}")
        results.append((flips + inv + szf * 2, f"HC:{where}", "±20%",
                        f"flips={flips} inversions={inv} maxdconv={maxdc:.1f} "
                        f"sizer_changed={szf}"))

    # ── upstream-key mini-sweeps (act inside layer adapters, not fuse) ─────
    print("\nUPSTREAM KEY MINI-SWEEPS (act inside layer adapters, not fuse)")
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2025-01-02", periods=400)
    px = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.02, 400)),
                   index=[str(d) for d in idx])
    p2 = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.02, 400)),
                   index=[str(d) for d in idx])
    from master import _ann_vol, _rho_bar
    base_vol = _ann_vol(px)
    p3 = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.02, 400)),
                   index=[str(d) for d in idx])
    base_rho = _rho_bar({"A": px, "B": p2, "C": p3})
    for key in ("RISK_VOL_LOOKBACK_TD", "RISK_MIN_HISTORY_TD"):
        old = master.CONFIG[key]
        for pm, f in (("-20%", 0.8), ("+20%", 1.2)):
            master.CONFIG[key] = type(old)(int(old * f))
            v = _ann_vol(px)
            print(f"  {key} {pm}: ann vol {base_vol:.4f} -> {v:.4f} "
                  f"({'changed' if abs(v - base_vol) > 1e-9 else 'NO CHANGE'})")
        master.CONFIG[key] = old
    old = master.CONFIG["RISK_CORR_LOOKBACK_TD"]
    for pm, f in (("-20%", 0.8), ("+20%", 1.2)):
        master.CONFIG["RISK_CORR_LOOKBACK_TD"] = int(old * f)
        r = _rho_bar({"A": px, "B": p2, "C": p3})
        print(f"  RISK_CORR_LOOKBACK_TD {pm}: rho {base_rho} -> {r} "
              f"({'changed' if r != base_rho else 'NO CHANGE'})")
    master.CONFIG["RISK_CORR_LOOKBACK_TD"] = old
    print("  DEMO of the pairs cliff: _rho_bar with only TWO series returns "
          f"None (needs >=3 pairs): {_rho_bar({'A': px, 'B': p2})!r} "
          "-> correlation cap AND DD veto both OFF for <=2-name books")
    # overlay bound mini-sweep (_apply_overlays)
    from master import Decision, LayerResult, _apply_overlays
    dec = [Decision(ticker=f"O{i}", sector="tech") for i in range(4)]
    for d in dec:
        d.conviction, d.action, d.grade = 58.0, "WATCH", "C"
        d.layers["macro"] = master._macro_signal(d.ticker, macro_states()["risk_on"],
                                                 master.macro_view(macro_states()["risk_on"], "tech"))
    lr = LayerResult(name="ml", order=4, stage="overlay", status="OK")
    for i, adj in enumerate((5.0, -5.0, 11.0, -11.0)):
        lr.signals[dec[i].ticker] = LayerSignal(dec[i].ticker, "ml", status="OK",
                                                facts={"conviction_adj": adj})
    base_actions = []
    for key in ("ML_ADJ_MAX", "OVERLAY_MAX_ADJ"):
        old = master.CONFIG[key]
        for pm, f in (("-20%", 0.8), ("+20%", 1.2)):
            master.CONFIG[key] = type(old)(old * f)
            fresh = [Decision(ticker=d.ticker, sector=d.sector) for d in dec]
            for d in fresh:
                d.conviction, d.action, d.grade = 58.0, "WATCH", "C"
                d.layers["macro"] = dec[0].layers["macro"]
            _apply_overlays(fresh, {"ml": lr}, "boost")
            acts = tuple((d.action, d.conviction) for d in fresh)
            if not base_actions:
                base_actions.append(acts)
            print(f"  {key} {pm}: overlay'd (action,conv) {acts} "
                  f"({'changed' if acts != base_actions[0] else 'same'})")
        master.CONFIG[key] = old
    print("  NOTE EARNINGS_MAX_AGE / EARNINGS_PLAN_MIN / EARNINGS_TP / "
          "EARNINGS_HOLD_DAYS act inside EarningsLayer + engine (upstream of "
          "fuse_candidate); not sweepable at this layer — see M1 register.")

    # ── real pilot rows ────────────────────────────────────────────────────
    print("\nREAL PILOT ROWS (ml_data/dataset_v1.npz, latest date, replayed "
          "through fuse_candidate)")
    try:
        import numpy as np
        z = np.load(ROOT / "ml_data/dataset_v1.npz", allow_pickle=False)
        fn = list(z["feature_names"])
        iq, ie = fn.index("q_score"), fn.index("e_score")
        isec = fn.index("sector_tech")
        mask = z["as_of"] == z["as_of"].max()
        rows = []
        ms = macro_states()
        for j in np.where(mask)[0]:
            q = float(z["X"][j][iq]); e = float(z["X"][j][ie])
            if not np.isfinite(q) or q <= 0:
                continue
            e = e if (np.isfinite(e) and e > 0) else None
            cand = Candidate(ticker=str(z["tickers"][j]), sector="tech")
            d = master.fuse_candidate(cand, q_sig("T", q, "tech"),
                                      e_sig("T", e, "LONG" if (e or 0) >= 70 else "open"),
                                      ms["risk_on"], "boost", False)
            rows.append((str(z["tickers"][j]), d.action, d.conviction, d.grade,
                         q, e))
        base_real = [(r[0], r[1], r[2], r[3]) for r in rows]
        print(f"  rows replayed: {len(rows)}  LONG={sum(1 for r in rows if r[1]=='LONG')} "
              f"WATCH={sum(1 for r in rows if r[1]=='WATCH')} "
              f"AVOID={sum(1 for r in rows if r[1]=='AVOID')}")
        real_keys = ["W_Q", "W_E", "E_MISSING_HAIRCUT", "EARNINGS_WEAK_SCALE",
                     "MACRO_TILT_GAIN", "MIN_QUALITY", "ACTION_LONG_AT",
                     "ACTION_WATCH_AT"]
        print(f"  {'key':<22s}{'pm':>5s}{'flips':>7s}{'inversions':>11s}{'maxdconv':>10s}")
        for key in real_keys:
            v = master.CONFIG[key]
            for pm, f in (("-20%", 0.8), ("+20%", 1.2)):
                old = master.CONFIG[key]
                master.CONFIG[key] = type(v)(v * f)
                try:
                    rr = []
                    for r in rows:
                        cand = Candidate(ticker=r[0], sector="tech")
                        d = master.fuse_candidate(
                            cand, q_sig("T", r[4], "tech"),
                            e_sig("T", r[5], "LONG" if (r[5] or 0) >= 70 else "open"),
                            ms["risk_on"], "boost", False)
                        rr.append((r[0], d.action, d.conviction, d.grade))
                    flips, maxdc, _ = diff_rows(base_real, rr)
                    inv = inversions(base_real, rr)
                finally:
                    master.CONFIG[key] = old
                print(f"  {key:<22s}{pm:>5s}{flips:>7d}{inv:>11d}{maxdc:>10.1f}")
                results.append((flips + inv, f"REAL:{key}", pm,
                                f"flips={flips} inversions={inv} maxdconv={maxdc:.1f}"))
    except Exception as e:
        print(f"  UNVERIFIED — real rows unavailable: {e}")

    # ── PHASE 4 (P-6): door rounding flip count ─────────────────────────
    print("\nPHASE 4 (P-6) DOOR ROUNDING — how many decisions change when the "
          "LONG/WATCH doors compare UNROUNDED conviction (ruleset v2) instead "
          "of the rounded display value (legacy)")
    long_t = float(master.CONFIG["ACTION_LONG_AT"])
    watch_t = float(master.CONFIG["ACTION_WATCH_AT"])

    def _door_crossings(decs):
        """(crossings, comparable) — cases where round(raw,1) and raw fall on
        OPPOSITE sides of a door: the door verdict itself changes; every
        other decision is bit-identical under either comparison."""
        crossings = comparable = 0
        for d in decs:
            if d is None or d.blocked or d.conviction_raw is None:
                continue
            comparable += 1
            for t in (long_t, watch_t):
                if (round(d.conviction_raw, 1) >= t) != (d.conviction_raw >= t):
                    crossings += 1
                    break
        return crossings, comparable

    def _fuse_all():
        ms = macro_states()
        out = []
        for c in cases:
            cand = Candidate(ticker=c["id"].split(":")[0], sector=c["sector"])
            out.append(mod_fuse(cand, q_sig("T", c["q"], c["sector"], c["flags"]),
                                e_sig("T", c["e"], c["plan"]),
                                ms[c["macro"]], c["mode"], c["weak"]))
        return out

    mod_fuse = master.fuse_candidate
    legacy_decs = _fuse_all()
    cr, nn = _door_crossings(legacy_decs)
    print(f"  stub universe ({len(cases)} cases): {cr}/{nn} door-comparable "
          f"decisions flip on the unrounded comparison (isolated rounding effect)")
    master.CONFIG["RULESET"] = "v2"
    try:
        v2_decs = _fuse_all()
    finally:
        master.CONFIG["RULESET"] = "legacy"
    full_flips = sum(1 for a, b in zip(legacy_decs, v2_decs)
                     if a.action != b.action)
    print(f"  stub universe FULL v2 (conservative fill + unrounded doors): "
          f"{full_flips}/{len(cases)} actions change vs legacy")
    try:
        import numpy as np
        z = np.load(ROOT / "ml_data/dataset_v1.npz", allow_pickle=False)
        fn = list(z["feature_names"])
        iq, ie = fn.index("q_score"), fn.index("e_score")
        mask = z["as_of"] == z["as_of"].max()
        ms = macro_states()

        def _real_decisions():
            out = []
            for j in np.where(mask)[0]:
                q = float(z["X"][j][iq]); e = float(z["X"][j][ie])
                if not np.isfinite(q) or q <= 0:
                    continue
                e = e if (np.isfinite(e) and e > 0) else None
                cand = Candidate(ticker=str(z["tickers"][j]), sector="tech")
                out.append(master.fuse_candidate(
                    cand, q_sig("T", q, "tech"),
                    e_sig("T", e, "LONG" if (e or 0) >= 70 else "open"),
                    ms["risk_on"], "boost", False))
            return out

        real_dec = _real_decisions()
        cr_r, nn_r = _door_crossings(real_dec)
        print(f"  real pilot rows (latest date, {len(real_dec)} names): "
              f"{cr_r}/{nn_r} door-comparable decisions flip on the unrounded "
              f"comparison")
        master.CONFIG["RULESET"] = "v2"
        try:
            real_v2 = _real_decisions()
        finally:
            master.CONFIG["RULESET"] = "legacy"
        full_r = sum(1 for a, b in zip(real_dec, real_v2) if a.action != b.action)
        print(f"  real pilot rows FULL v2 (fill + doors): {full_r}/{len(real_dec)} "
              f"actions change vs legacy")
    except Exception as e:
        print(f"  real pilot rows: UNVERIFIED — {e}")

    # ── PHASE 4 (P-5): weak-E scale ablation ────────────────────────────
    print("\nPHASE 4 (P-5) WEAK-E ABLATION — EARNINGS_WEAK_SCALE 0.5 (shipped) "
          "vs alternatives")
    print("  reported WITHOUT tuning: the shipped 0.5 stays (owner decision "
          "P-5); any change is a proposal, never an edit")
    weak_rows = [c for c in cases if c["weak"] and c["e"] is not None]
    ms = macro_states()

    def _run_weak():
        out = []
        for c in weak_rows:
            cand = Candidate(ticker=c["id"].split(":")[0], sector=c["sector"])
            d = master.fuse_candidate(cand, q_sig("T", c["q"], c["sector"], c["flags"]),
                                      e_sig("T", c["e"], c["plan"]),
                                      ms[c["macro"]], c["mode"], True)
            out.append((d.action, d.conviction))
        return out

    base_weak = _run_weak()
    for scale in (0.25, 0.75, 1.0):
        master.CONFIG["EARNINGS_WEAK_SCALE"] = scale
        try:
            got = _run_weak()
        finally:
            master.CONFIG["EARNINGS_WEAK_SCALE"] = 0.5
        flips = sum(1 for a, b in zip(base_weak, got) if a[0] != b[0])
        maxdc = max((abs(a[1] - b[1]) for a, b in zip(base_weak, got)), default=0.0)
        print(f"  weak scale {scale:.2f}: action flips {flips}/{len(weak_rows)} "
              f"(weak-path cases), max conviction move {maxdc:.1f}")
    print("  NOTE: scale 1.0 = the weak verdict ignored (W_E unrenormalised); "
          "0.25 = a stronger haircut than shipped. No winner is picked here.")

    # ── summary table sorted by effect ────────────────────────────────────
    print("\n" + "=" * 88)
    print("SUMMARY — ALL RULES SORTED BY DECISION EFFECT (stub universe)")
    print(f"{'effect':>7s}  {'rule':<30s}{'pm':>5s}  note")
    for eff, key, pm, note in sorted(results, reverse=True):
        print(f"{eff:>7d}  {key:<30s}{pm:>5s}  {note}")
    dead = [k for e, k, p, n in results if e == 0 and not k.startswith("REAL")]
    print(f"\nZERO-EFFECT rules on the stub universe (dead or unreachable for "
          f"decisions): {', '.join(sorted(set(dead)))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
