"""me/risk.py — the portfolio sizer + risk context (v1.8.0 split from
master.py §3.6). size_portfolio is the L5 sizer: position weights from
conviction x inverse vol under the legacy eff/8 correlation cap or the
opt-in vol_target gross solve; risk_ctx_out publishes the portfolio risk
context for the report/footer; _ann_vol/_rho_bar are the trailing
annualised-vol and mean-correlation estimators (RISK_* CONFIG keys)."""
from __future__ import annotations

import math
import statistics
from typing import Any

from me.core import CONFIG



def size_portfolio(longs: list[str], vols: dict[str, float | None] | None,
                   rho_bar: float | None, sectors: dict[str, str],
                   budget: float, mode: str = "legacy",
                   advs: "dict[str, float] | None" = None) -> dict:
    """PURE inverse-vol sizer: name cap -> sector cap -> correlation-aware
    gross cap (effective bets) -> estimated-drawdown portfolio veto.
    Weights are absolute exposures summing to <= budget; cash = budget -
    gross is explicit; vetoed books are all-zero with the reason. vols /
    rho_bar None -> equal-weight fallback (never invented numbers). No IO,
    no clocks: the whole sizer is testable as a function (phase-5 gate).

    Phase 4 (P-2, spec 3.3) adds the OPT-IN `mode="vol_target"` (default
    legacy — byte-for-byte the shipped behaviour, asserted by
    test_legacy_mode_is_unchanged): the SAME inverse-vol weights, name cap
    and sector cap, but the correlation-aware scaling is expressed as a
    VOLATILITY TARGET — gross is solved so the estimated portfolio vol
    (equicorrelation, the same inputs incl. the B2 fallback rho) hits
    RISK_VOL_TARGET, capped at the budget (no leverage). Any deployment
    looser than the legacy norm for the same book prints a
    'looser than norm by X%' note with X computed from the actual grosses;
    a target whose at-target est DD exceeds RISK_MAX_EST_DD prints the
    envelope warning (the DD veto then fires at target).

    v1.4.1 hardening (B1/B2/B3), ported in phase 2: non-finite or
    non-positive vols are unusable inputs -> treated like MISSING vols
    (peer median, or the equal-weight fallback when none are usable) with
    a visible note — never a silent zero weight and never a
    ZeroDivisionError. When vols exist but rho is unavailable (1-2 names,
    no rho from _rho_bar, or a non-finite rho_bar) the correlation cap
    stays OFF and the DD estimate uses the documented RISK_FALLBACK_RHO —
    both disclosed (note + footer + JSON via rho_fallback/rho_used), never
    silent. A non-finite budget is a stand-down veto (same shape as the
    low-budget stand-down) so NaN can never reach weights, cash or the
    JSON summary. Every guard-off/fallback ALSO records a stable W_*
    warning code in out["warn_codes"] (printed in the footer, carried in
    the JSON summary and the freeze manifest — the phase-5 ERRORS &
    WARNINGS block reads these codes)."""
    b = float(budget)
    out: dict[str, Any] = {"weights": {}, "gross": 0.0, "cash": b, "est_dd": None,
                           "eff_bets": None,
                           "rho_bar": (None if rho_bar is None else float(rho_bar)),
                           "rho_fallback": False, "rho_used": None,
                           "veto": "", "notes": [], "fallback": False,
                           "budget": b, "warn_codes": [],
                           "adv_checked": advs is not None}   # F9 (v1.8.3)
    if not longs:
        out["notes"].append("no LONG names — all cash")
        return out
    if not math.isfinite(b):
        out["veto"] = (f"budget {b!r} is not a finite number — "
                       "macro state unusable, sizer stand-down (all cash)")
        out["notes"].append(out["veto"])
        out["warn_codes"].append("W_BUDGET_STANDDOWN")
        return out
    if b < float(CONFIG["RISK_MIN_BUDGET"]):
        out["veto"] = (f"budget {b:.2f} < {CONFIG['RISK_MIN_BUDGET']:.2f} "
                       "(macro stand-down)")
        out["notes"].append(out["veto"])
        out["warn_codes"].append("W_BUDGET_STANDDOWN")
        return out

    def _usable_vol(v: Any) -> bool:
        """A vol we can invert: a finite positive number (B1). Strings,
        NaN, inf, 0 and negatives are unusable data, not zero weight."""
        try:
            fv = float(v)
        except (TypeError, ValueError):
            return False
        return math.isfinite(fv) and fv > 0.0

    vmap = vols or {}
    bad = [t for t in longs
           if vmap.get(t) is not None and not _usable_vol(vmap[t])]
    have = {t: float(v) for t, v in vmap.items() if _usable_vol(v)}
    if bad:
        out["notes"].append("unusable vols for " + ", ".join(bad)
                            + " (non-finite or <=0) — treated as missing, "
                            "never as zero weight")
        out["warn_codes"].append("W_UNUSABLE_VOL")
    if have:
        med = statistics.median(sorted(have.values()))
        vol = {t: have.get(t, med) for t in longs}    # unpriced -> peer median
        inv = {t: 1.0 / vol[t] for t in longs}
        s = sum(inv.values())
        if s > 0.0 and math.isfinite(s):
            w = {t: inv[t] / s for t in longs}
        else:                                          # degenerate inverses
            out["fallback"] = True
            w = {t: 1.0 / len(longs) for t in longs}
            out["notes"].append("inverse-vol weights unusable (sum not a "
                                "finite positive number) — equal-weight "
                                "fallback")
            out["warn_codes"].append("W_EQW_FALLBACK")
    else:
        out["fallback"] = True
        w = {t: 1.0 / len(longs) for t in longs}
        out["notes"].append(
            ("no usable vols (all non-finite or <=0) — equal-weight fallback "
             "(vol/corr caps not applied)") if bad else
            ("no price history — equal-weight fallback "
             "(vol/corr caps not applied)"))
        out["warn_codes"].append("W_EQW_FALLBACK")
    for t in w:                                        # single-name cap
        w[t] = min(w[t], float(CONFIG["RISK_MAX_NAME_W"]))
    by_sec: dict[str, list[str]] = {}
    for t in longs:                                    # sector cap
        by_sec.setdefault(sectors.get(t) or "-", []).append(t)
    for sec, ts in by_sec.items():
        ssum = sum(w[t] for t in ts)
        cap = float(CONFIG["RISK_MAX_SECTOR_W"])
        if ssum > cap:
            k = cap / ssum
            for t in ts:
                w[t] *= k
            out["notes"].append(f"sector {sec} capped")
    # v1.8.0 (W5): ADV participation guard — OPT-IN via the advs kwarg
    # (advs=None keeps the legacy path byte-identical, R15). advs are
    # average daily $ volumes expressed in the SAME units as the budget
    # (ADV$ / portfolio$ — the owner divides before passing). A name with
    # ADV data is capped at RISK_ADV_MAX_PARTICIPATION x its ADV; a name
    # with NO ADV row warns loudly (W_ADV_UNAVAILABLE per name) — the
    # guard only binds where the data exists, never inventing liquidity.
    if advs is not None:
        part = float(CONFIG["RISK_ADV_MAX_PARTICIPATION"])
        for t in longs:
            adv = (advs or {}).get(t)
            try:
                adv = float(adv) if adv is not None else None
            except (TypeError, ValueError):
                adv = None
            if adv is None or not math.isfinite(adv) or adv <= 0.0:
                out["warn_codes"].append("W_ADV_UNAVAILABLE")
                out["notes"].append(
                    f"{t}: no ADV data — participation unverified "
                    "[W_ADV_UNAVAILABLE]")
                continue
            cap_w = part * adv
            if w.get(t, 0.0) > cap_w:
                w[t] = cap_w
                out["notes"].append(
                    f"{t} capped by ADV participation "
                    f"({part:.0%} x ADV {adv:g} budget-units)")
    n = len(longs)
    vt = (str(mode) == "vol_target")                # phase 4 (P-2) opt-in
    out["mode"] = str(mode)
    rho = None
    rho_in: float | None = None                     # B3: reject unusable rho
    if rho_bar is not None:
        try:
            rb = float(rho_bar)
        except (TypeError, ValueError):
            rb = None
        if rb is not None and math.isfinite(rb):
            rho_in = rb
    if rho_in is not None and have and n >= 2:        # correlation-aware cap
        rho = min(max(rho_in, 0.0), 0.999)
        eff = n / (1.0 + (n - 1) * rho)
        out["eff_bets"] = eff
        if not vt and eff < float(CONFIG["RISK_MIN_EFFECTIVE_BETS"]):
            # legacy: the eff/8 gross cap. Under vol_target the correlation
            # awareness is expressed by the target itself (a correlated
            # book has a higher unit vol -> a lower solved gross), so this
            # scaling is REPLACED, not stacked.
            k = eff / float(CONFIG["RISK_MIN_EFFECTIVE_BETS"])
            for t in w:
                w[t] *= k
            out["notes"].append(f"correlation cap (eff bets {eff:.1f})")
    elif have:
        # B2: vols exist but the correlation input is unavailable (1-2
        # names, _rho_bar returned None — <42 overlapping rows or its broad
        # except — or a non-finite rho_bar). The guards must not switch off
        # silently: the correlation cap stays OFF and the DD estimate uses
        # the documented conservative fallback rho; both facts disclosed.
        out["rho_fallback"] = True
        out["rho_used"] = (0.0 if n < 2 else float(CONFIG["RISK_FALLBACK_RHO"]))
        out["notes"].append(
            ("single-name book — correlation cap n/a; est DD assumes no "
             "diversification (rho 0)") if n < 2 else
            (f"rho unavailable — correlation cap OFF; est DD at fallback "
             f"rho {out['rho_used']:.2f} (documented conservative "
             "assumption)"))
        out["warn_codes"].append("W_RHO_FALLBACK")
    # ── phase 4 (P-2): the vol_target gross solve ─────────────────────
    g = 1.0
    if vt:
        if have and b > 0.0:
            rho_t = (rho if rho is not None else out["rho_used"])
            sv_u = sum(w[t] * vol[t] for t in longs)
            sq_u = sum(w[t] * w[t] * vol[t] * vol[t] for t in longs)
            var_u = sq_u + (rho_t or 0.0) * (sv_u * sv_u - sq_u)
            unit = max(0.0, var_u) ** 0.5           # vol at FULL budget deploy
            target = float(CONFIG["RISK_VOL_TARGET"])
            # the target is the ABSOLUTE portfolio vol of the deployed book
            # (the same scale the legacy est-DD veto compares): solve the
            # gross multiplier so g x b x unit == target, capped at 1 (no
            # leverage). Coherent with the DD envelope at ANY budget.
            g = (min(target / (b * unit), 1.0) if unit > 0.0 else 1.0)
            out["_vt"] = {"target": target, "full_vol": b * unit,
                           "rho_real": rho is not None}
            if target * float(CONFIG["RISK_DD_FACTOR"]) \
                    > float(CONFIG["RISK_MAX_EST_DD"]) + 1e-12:
                # CONFIG-coherence disclosure: at target the est DD EXCEEDS
                # the veto line — the DD guard fires at-target (hostile
                # scenario: stand-down), the owner must know the target is
                # looser than the legacy DD envelope.
                out["notes"].append(
                    f"vol_target {target:.0%} x DD factor "
                    f"{float(CONFIG['RISK_DD_FACTOR']):g} = est DD at target "
                    f"{target * float(CONFIG['RISK_DD_FACTOR']):.0%} > "
                    f"RISK_MAX_EST_DD {float(CONFIG['RISK_MAX_EST_DD']):.0%} "
                    "— target looser than the DD envelope; the DD veto fires "
                    "at target")
        else:
            out["notes"].append(
                "vol_target n/a (no usable vols) — equal-weight fallback, "
                "the same treatment legacy gives the book")
    W = {t: w[t] * (g * b if vt else b) for t in longs}
    out["weights"] = W
    out["gross"] = float(sum(W.values()))
    out["cash"] = float(b - out["gross"])
    _vt = out.pop("_vt", None)          # temp solve facts (never shipped)
    if vt and b > 0 and out["gross"] > 0.0:
        # P-2 disclosure: the mode line names the REAL deployment (the caps
        # may bind below the solved gross), and every deployment looser
        # than the LEGACY norm for the SAME book prints 'looser than norm
        # by X%'. The norm is what legacy would deploy on the identical
        # inputs (the capped weights through the eff/8 scaling when it
        # applies; the rho-fallback book has no corr cap in legacy and is
        # the norm then).
        if _vt is not None:
            out["notes"].append(
                f"vol_target: deploys {out['gross'] / b:.0%} of budget "
                f"(target ann vol {_vt['target']:.0%} absolute; full-deploy "
                f"vol {_vt['full_vol']:.1%}; rho "
                f"{'real' if _vt['rho_real'] else 'fallback'})")
        wl = dict(w)
        eff_n = out["eff_bets"]
        if eff_n is not None and eff_n < float(CONFIG["RISK_MIN_EFFECTIVE_BETS"]):
            kk = eff_n / float(CONFIG["RISK_MIN_EFFECTIVE_BETS"])
            for t in wl:
                wl[t] *= kk
        lf = sum(wl.values())                     # legacy deployment fraction
        vf = out["gross"] / b
        if vf > lf + 1e-9 and lf > 0.0:
            pct = round((vf / lf - 1.0) * 100.0)
            out["notes"].append(
                f"vol_target deploys {vf:.0%} of budget vs legacy {lf:.0%} "
                f"— looser than norm by {pct}%")
    dd_rho = rho                                        # real rho when capped
    if dd_rho is None and out["rho_fallback"]:
        dd_rho = out["rho_used"]                        # B2 documented fallback
    if have and dd_rho is not None:                     # est DD (equicorr model)
        sv = sum(W[t] * vol[t] for t in longs)
        sq = sum(W[t] * W[t] * vol[t] * vol[t] for t in longs)
        var = sq + dd_rho * (sv * sv - sq)
        pvol = max(0.0, var) ** 0.5
        out["est_dd"] = float(CONFIG["RISK_DD_FACTOR"]) * pvol
        # phase 4: +1e-9 float-noise tolerance on the boundary tie — a
        # vol_target book sitting EXACTLY at its target has est_dd == the
        # veto line by construction and must not be vetoed by a 1-ulp
        # rounding difference (organic books are ~1e-3 from the line; the
        # legacy verdict is unchanged for every one of them).
        if out["est_dd"] > float(CONFIG["RISK_MAX_EST_DD"]) + 1e-9:
            out["veto"] = (f"est max DD ~{out['est_dd']:.0%} > "
                           f"{CONFIG['RISK_MAX_EST_DD']:.0%} after caps — "
                           "portfolio veto")
            out["notes"].append(out["veto"])
            out["warn_codes"].append("W_DD_VETO")
            out["weights"] = {t: 0.0 for t in longs}
            out["gross"] = 0.0
            out["cash"] = b
    out["warn_codes"] = list(dict.fromkeys(out["warn_codes"]))
    return out


def risk_ctx_out(sized: dict) -> dict:
    """ctx_out for a sized book: the footer portfolio LINES plus the JSON
    summary — one builder shared by RiskLayer and the stub sizer.
    v1.4.1 (B2/B3), ported in phase 2: a rho-fallback book gets a
    dedicated footer line (carrying the stable W_RHO_FALLBACK code) and
    rho_fallback/rho_used JSON fields; non-finite numbers are emitted as
    null (never NaN) so the JSON stays strictly parseable. The stable
    warn_codes list travels in the summary so offline/replay/JSON surfaces
    all carry the guard-off disclosure."""
    b = sized["budget"]

    def _jf(x: Any) -> float | None:
        """JSON-safe number: None for missing/non-finite (B3), else rounded."""
        try:
            x = float(x)
        except (TypeError, ValueError):
            return None
        return round(x, 4) if math.isfinite(x) else None

    if math.isfinite(b) and b > 0:
        line = (f"risk: gross {sized['gross'] / b:.0%} of {b:.2f} budget · "
                f"cash {sized['cash'] / b:.0%}")
    elif not math.isfinite(b):
        line = (f"risk: budget {b!r} not finite — all cash (vetoed, "
                "see risk veto line)")
    else:
        line = "risk: budget 0 — all cash"
    if sized["est_dd"] is not None:
        line += (f" · est max DD ~{sized['est_dd']:.0%} "
                 f"({CONFIG['RISK_DD_FACTOR']:.0f}x ann vol — estimate, "
                 "not a probability)")
    if sized["eff_bets"] is not None:
        line += f" · eff bets {sized['eff_bets']:.1f}"
    if sized.get("fallback"):
        line += " · equal-weight fallback"
    lines = [line]
    if sized.get("rho_fallback"):
        lines.append("risk guard: rho unavailable — correlation cap OFF; "
                     f"est DD at fallback rho "
                     f"{float(sized.get('rho_used') or 0.0):.2f} "
                     "(documented conservative assumption) [W_RHO_FALLBACK]")
    if sized["veto"]:
        # B3/B8 (phase 2): the veto line carries the stable warn codes so a
        # stand-down / DD veto is printed WITH its code (the phase-5 ERRORS &
        # WARNINGS block reads these).
        vt = sized["veto"] + " — weights 0, all cash"
        codes = list(sized.get("warn_codes") or ())
        if sized.get("rho_fallback") and "W_RHO_FALLBACK" not in codes:
            codes.append("W_RHO_FALLBACK")
        if codes:
            vt += f" [{', '.join(codes)}]"
        lines.append("risk veto: " + vt)
    if sized["notes"]:
        lines.append("risk caps: " + ", ".join(sized["notes"]))
    # v1.8.0 (W5): the live cost model — GROSS and an estimated NET on
    # one line. The live plan is GROSS of costs (research screener, no
    # live trades); the honest estimate is the same round-trip the
    # backtest nets (10 bps/side x 2 on a full deployment — a first
    # position trades ~100% of its weight; shown as an estimate, never
    # as a net return claim).
    if sized["gross"] > 0 and math.isfinite(b) and b > 0:
        bps_side = 10.0                      # prereg baseline (me/backtest)
        rt = 2.0 * bps_side / 10000.0
        lines.append(
            "costs: live plan is GROSS of costs — est round-trip "
            f"2 x {bps_side:g} bps/side ~{rt * 100:.2f}% one-off on the "
            f"deployed {sized['gross'] / b:.0%} (the backtest nets the "
            "same 10 bps/side; estimate, not a net-return claim)")
    codes = list(sized.get("warn_codes") or ())
    if sized.get("rho_fallback") and "W_RHO_FALLBACK" not in codes:
        codes.append("W_RHO_FALLBACK")
    return {"portfolio": lines,
            "summary": {"gross": _jf(sized["gross"]),
                        "cash": _jf(sized["cash"]),
                        "budget": _jf(b),
                        "est_dd": _jf(sized["est_dd"]),
                        "eff_bets": (None if sized["eff_bets"] is None
                                     else round(sized["eff_bets"], 2)),
                        "rho_fallback": bool(sized.get("rho_fallback")),
                        "rho_used": _jf(sized.get("rho_used")),
                        "warn_codes": codes,
                        "veto": sized["veto"],
                        "fallback": bool(sized.get("fallback")),
                        "sizing_mode": str(sized.get("mode") or "legacy"),
                        "caps": {"name": CONFIG["RISK_MAX_NAME_W"],
                                 "sector": CONFIG["RISK_MAX_SECTOR_W"],
                                 "dd_max": CONFIG["RISK_MAX_EST_DD"]},
                        "n_sized": len(sized["weights"])}}


def _ann_vol(series: Any, as_of: str | None = None) -> float | None:
    """Annualised daily-return vol over the trailing RISK_VOL_LOOKBACK_TD
    rows (ending at the last row <= as_of when given); None below
    RISK_MIN_HISTORY_TD rows — never a made-up number."""
    try:
        import numpy as np
        vals = series.to_numpy(float)
        if as_of:
            idx = series.index
            pos = int(idx.searchsorted(as_of, side="right")) - 1
            vals = vals[:pos + 1]
        if len(vals) < int(CONFIG["RISK_MIN_HISTORY_TD"]) + 1:
            return None
        vals = vals[-(int(CONFIG["RISK_VOL_LOOKBACK_TD"]) + 1):]
        rets = np.diff(vals) / vals[:-1]
        if len(rets) < int(CONFIG["RISK_MIN_HISTORY_TD"]):
            return None
        return float(rets.std(ddof=1) * (252.0 ** 0.5))
    except Exception:
        return None


def _rho_bar(series_map: dict[str, Any], as_of: str | None = None) -> float | None:
    """Average pairwise correlation of daily returns (the equicorrelation
    input), clipped to [0, 0.999]; None when fewer than 3 usable pairs."""
    try:
        import itertools
        import pandas as pd
        if len(series_map) < 2:
            return None
        df = pd.DataFrame({t: s for t, s in series_map.items()})
        if as_of:
            df = df.loc[:as_of]
        df = df.tail(int(CONFIG["RISK_CORR_LOOKBACK_TD"]))
        if len(df) < int(CONFIG["RISK_MIN_HISTORY_TD"]):
            return None
        c = df.pct_change().corr()
        vals = [float(c.iloc[i, j])
                for i, j in itertools.combinations(range(len(c)), 2)
                if c.iloc[i, j] == c.iloc[i, j]]
        if len(vals) < 3:
            return None
        return float(min(max(sum(vals) / len(vals), 0.0), 0.999))
    except Exception:
        return None


