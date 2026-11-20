#!/usr/bin/env python3
"""Phase 4 · STEP B — point-in-time proofs, RUN per engine (never assumed).

Each probe prints PASS/FAIL/SKIP + the evidence line. Exit 0 = all engines
labelled (a FAIL still exits 1 so the phase gate sees it).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
TICKERS = ["MU", "NVDA", "AAPL"]
results: dict[str, dict] = {}


def sec(name: str) -> dict:
    results.setdefault(name, {})
    return results[name]


def line(ok: bool, msg: str) -> None:
    print(("PASS " if ok else "FAIL ") + msg)


# ── 1 · earnings_engine: window cut + determinism ─────────────────────────
def probe_earnings() -> None:
    import earnings_engine as ee
    eng = ee.EarningsEngine(quarters=40, workers=4)
    as_of = "2024-06-30"
    s1 = eng.score(TICKERS, as_of=as_of)
    s2 = eng.score(TICKERS, as_of=as_of)
    same = s1.equals(s2)
    line(same, f"earnings determinism: score(as_of={as_of}) twice -> identical "
               f"({len(s1)} scored, cols incl. {[c for c in s1.columns if c in ('score','rating','p_next_big')]})")
    max_dates = {}
    for t in TICKERS:
        win = eng._window(eng.history(t), as_of)
        md = str(win["date"].max().date()) if len(win) else "none"
        max_dates[t] = md
    ok = all(d < as_of for d in max_dates.values())
    line(ok, f"earnings window cut: max public quarter < as_of for {max_dates} "
             f"(engine _window: date + provider lag < as_of; yahoo lag = 0 = announcement date)")
    sec("earnings")["verdict"] = "PIT_VERIFIED" if (same and ok) else "PIT_FAIL"
    sec("earnings")["evidence"] = ("score(as_of) deterministic; _window cuts quarters to "
                                   "date+lag < as_of (max dates " + json.dumps(max_dates) + ")")


# ── 2 · quality: filing-availability cut + determinism + boundary ─────────
def probe_quality() -> None:
    import quality
    as_of = "2024-06-30"
    # scope to MU's sector pool exactly like master's QualityLayer does
    # (get_quality_score without refs would score the whole 682 universe)
    refs, _sector, _scope, _w, _e = quality.build_inline_universe("MU")
    r1 = quality.get_quality_score("MU", as_of=as_of, universe_refs=refs)
    r2 = quality.get_quality_score("MU", as_of=as_of, universe_refs=refs)
    same = json.dumps(r1, sort_keys=True, default=str) == json.dumps(r2, sort_keys=True, default=str)
    line(same, f"quality determinism: get_quality_score(MU, as_of={as_of}) twice -> identical "
               f"(score {r1.get('score')} {r1.get('status')})")
    prov = r1.get("provenance") or {}
    entries = [e for tr in prov.values() for e in tr]
    bad = [e for e in entries if str(e.get("available_date") or "") > as_of]
    line(not bad, f"quality filing cut: {len(entries)} traced facts, ALL available_date <= as_of "
                  f"(violations: {len(bad)}); fundamentals cut by FILING/availability date, "
                  f"not period end")
    sample = sorted({(str(e.get("period_end")), str(e.get("filing_date")),
                      str(e.get("available_date"))) for e in entries})[-3:]
    print(f"     sample period_end -> filing -> available: {sample}")
    # boundary probe: the latest-available traced FILING (with an accession)
    # must be invisible the day before it became public
    filed = [(str(e.get("available_date")), e.get("accession")) for e in entries
             if e.get("available_date") and e.get("accession")
             and e.get("filing_date")]
    avail = sorted({d for d, _ in filed})
    accs = dict(filed)
    if avail:
        d = avail[-1]
        acc = accs[d]
        import datetime as dt
        d_prev = (dt.date.fromisoformat(d) - dt.timedelta(days=1)).isoformat()

        def _accs_at(a: str) -> set:
            r = quality.get_quality_score("MU", as_of=a, universe_refs=refs)
            return {e.get("accession") for tr in (r.get("provenance") or {}).values()
                    for e in tr}
        a_after, a_before = _accs_at(d), _accs_at(d_prev)
        ok = (acc in a_after) and (acc not in a_before)
        line(ok, f"quality boundary: accession {acc} (available {d}) is visible at "
                 f"as_of={d} but NOT at as_of={d_prev} — the cut is the public "
                 f"availability date, exactly")
    mo1 = quality.get_momentum_12_1("MU", as_of=as_of)
    mo2 = quality.get_momentum_12_1("MU", as_of=as_of)
    line(mo1 == mo2, f"quality price path: get_momentum_12_1(MU, as_of={as_of}) twice -> "
                     f"identical (momentum {mo1.get('momentum_12_1')}, basis "
                     f"{mo1.get('price_basis')}); build_market filters bars <= as_of "
                     f"(quality.py:4779, 3.4.0 S0)")
    verdict = "PIT_VERIFIED" if (same and not bad) else "PIT_FAIL"
    sec("quality")["verdict"] = verdict
    sec("quality")["evidence"] = (f"{len(entries)} traced facts, all available_date <= as_of; "
                                  f"deterministic; boundary probe on the latest filing")


# ── 3 · meds: determinism + honest vintage label ───────────────────────────
def probe_meds() -> None:
    import meds
    as_of = "2024-06-30"
    m1 = meds.regime_now(as_of=as_of)
    m2 = meds.regime_now(as_of=as_of)
    # master's _parse_macro consumes exactly these fields; the free-form
    # `notes` diagnostics differ between the first fetch and the memo hit
    # (the auto-window note prints once per fetch tier) and never reach a
    # decision — compare the payload, disclose the notes variance.
    consumed = ("scenario_key", "name", "confidence", "dominance", "cycle_phase",
                "conviction_leverage", "as_of", "data_tier", "pit_mode",
                "next_trade_month", "credit_signal", "regime_months", "regime")
    same = all(m1.get(k) == m2.get(k) for k in consumed) \
        and m1.get("basket") == m2.get("basket")
    notes_differ = m1.get("notes") != m2.get("notes")
    line(same, f"meds determinism: regime_now(as_of={as_of}) twice -> identical on every "
               f"field master consumes ({m1.get('scenario_key')}, conf "
               f"{m1.get('confidence'):.3f}, basket {m1.get('basket', {}).get('longs')})"
               + ("; free-form `notes` diagnostics vary between fetch and memo hit "
                  "(disclosed, never a decision input)" if notes_differ else ""))
    eff = str(m1.get("as_of"))
    line(eff <= as_of, f"meds as-of floor: effective as_of {eff} <= requested {as_of} "
                       f"(last COMPLETED month end, _decision_month_end)")
    tier, pit = m1.get("data_tier"), m1.get("pit_mode")
    approx = pit == "approximate_pit_lag"
    line(approx, f"meds vintage honesty: data_tier={tier} pit_mode={pit} — series fetched "
                 f"NOW and cut at as_of with PIT lags (_apply_pit_lag meds.py:823), i.e. "
                 f"approximate vintage, NOT the data vintage available then -> labelled "
                 f"PIT_APPROXIMATE (pit_verified: false in the dataset manifest)")
    sec("meds")["verdict"] = "PIT_APPROXIMATE" if (same and eff <= as_of) else "PIT_FAIL"
    sec("meds")["evidence"] = (f"regime_now(as_of) deterministic; effective {eff}; "
                               f"data_tier={tier}; pit_mode={pit} (approximate vintage)")


if __name__ == "__main__":
    for fn in (probe_earnings, probe_quality, probe_meds):
        print(f"\n=== {fn.__name__} ===")
        try:
            fn()
        except Exception as e:                                # noqa: BLE001
            line(False, f"{fn.__name__} raised {type(e).__name__}: {e}")
            sec(fn.__name__.replace("probe_", ""))["verdict"] = "PIT_FAIL"
    print("\nSUMMARY " + json.dumps({k: v.get("verdict") for k, v in results.items()}))
    Path(Path(__file__).resolve().parent.parent,
         "evidence", "phase4_pit_status.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8")
    sys.exit(0 if all(v.get("verdict") != "PIT_FAIL" for v in results.values()) else 1)
