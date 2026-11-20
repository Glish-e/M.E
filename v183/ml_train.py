#!/usr/bin/env python3
"""ml_train.py — walk-forward trainer for master's ML overlay heads (v1.0.0).

Phase 5. One CALIBRATED model per head (Q, E, macro), trained on the
phase-4 dataset (ml_data/dataset_v1.npz) with adapters only: it imports
master (CONFIG + version), never edits an engine, and never fetches data.

Protocol (fixed a priori — no in-sample tuning):
  * rows are grouped by as-of month (`group`); NEVER shuffled;
  * expanding-window walk-forward: a test group g is predicted from the
    groups <= g - embargo_months - 1, so train and test label windows can
    never overlap (embargo >= the label horizon: 3 monthly periods for the
    monthly grid, 1 for quarterly — read from the dataset manifest);
  * logistic first (light C grid {0.01, 0.1, 1.0} chosen by an inner
    group-aware CV inside the TRAIN window only); gradient boosting is
    tried and kept ONLY if it beats logistic on pooled out-of-sample
    monthly-mean rank IC;
  * calibration: Platt (2 parameters) fit on the train window's inner-OOF
    predictions, then applied to the test logits — the shipped probability
    is post-calibration and always carries its sample size;
  * judged by per-month rank IC, top-minus-bottom decile spread and
    Brier skill vs the base rate; baselines = the constant base rate and
    the raw engine score (q_score / e_score / tilt_mean);
  * verdict rule (phase 3, M4): "beats" IFF >= 12 usable OOS periods AND
    >= 100 usable OOS rows AND a final model calibrated on inner OOF AND
    monthly-mean rank IC > 0 AND > the raw-score baseline's IC (judged on
    IDENTICAL rows — verdict_basis) AND Brier skill vs base > 0; any
    failed sample gate makes the verdict "insufficient evidence" naming
    the condition that failed. No in-sample calibration fallback, ever.

States: every model ships as SHADOW (logged, changes no decision — master's
MLayer enforces this). --activate HEAD rewrites the state to ACTIVE only
when validation_{head}.json exists, its verdict is "beats", AND its
model_sha256/dataset_sha256 pins match this model file and its training
dataset (M5: hash-bound activation; any mismatch refuses with exit 2).

Saved model (head_X.npz, loadable with allow_pickle=False): pure-numpy
logistic (impute medians, scaler, coef, intercept, Platt a/b) — inference
needs NO sklearn and NO network. A winning GBM is saved as a joblib
sidecar (head_X.joblib) and loads only where sklearn is importable.

Usage:
  python3 ml_train.py --dataset ml_data/dataset_v1.npz --out ml_data/models
  python3 ml_train.py --dataset ... --out ... --heads q,e,macro
  python3 ml_train.py --dataset ... --out ... --activate q

Exit codes: 0 ok · 1 unexpected error · 2 honest refusal (no data / leakage
/ too few months / activation without a passing report) · 64 bad usage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import master  # noqa: E402  (CONFIG + version only; never an engine edit)

__version__ = "1.1.0"        # B-5: the v1.5.0 docs claimed "1.1.0-pinned"
                              # while code+sidecars said 1.0.0; this bump
                              # makes the claim real (see CHANGELOG v1.7.0-dev)

try:
    import numpy as np
except Exception as e:                                   # pragma: no cover
    raise SystemExit(f"ml_train: numpy is required for training ({e})")


def _atomic_write_text(path: "Path | str", text: str) -> None:
    """v1.4.1 port (B8, phase 2) + the fsync extension: write temp + fsync +
    rename so a crash mid-write leaves the PREVIOUS validation report intact
    and never a truncated json a later --activate would trust. The temp file
    is removed on failure."""
    import os
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()

HEADS: dict[str, dict] = {
    "q": {
        "target": "y_q", "source": "ticker",
        "features": [
            "q_score", "q_rank_pct", "q_coverage", "q_flag_count", "q_veto",
            "q_pillar_profitability", "q_pillar_growth",
            "q_pillar_financial_strength", "q_pillar_earnings_quality",
            "q_pillar_valuation", "q_pillar_shareholder_yield",
            "conviction", "macro_tilt", "macro_confidence", "macro_leverage",
            "macro_credit_on", "macro_regime_defensive", "macro_regime_risk_on",
            "sector_financials", "sector_industrials", "sector_healthcare",
            "sector_tech", "sector_communication", "sector_consumer",
            "sector_energy", "sector_materials", "sector_reits",
            "sector_utilities", "sector_specialty",
            "q_missing", "r_q_score", "r_conviction"],
        "baseline": "q_score",
        "label": "63-td forward return beats SPY",
    },
    "e": {
        "target": "y_e", "source": "ticker",
        "features": [
            "e_score", "p_next_big", "beat_rate", "last4_big", "streak_big",
            "qtrs_since_big", "days_since_last_earnings", "e_confidence",
            "q_score", "conviction",
            "macro_tilt", "macro_confidence", "macro_leverage",
            "macro_credit_on", "macro_regime_defensive", "macro_regime_risk_on",
            "e_missing", "p_next_big_missing", "days_since_missing",
            "r_e_score", "r_p_next_big"],
        "baseline": "e_score",
        "label": "~30-td post-event return beats SPY",
    },
    "macro": {
        "target": "y_m", "source": "macro",
        "features": [  # ml_dataset.macro_feature_names()
            "regime_confidence", "regime_dominance", "regime_leverage",
            "regime_credit_on", "regime_defensive", "regime_risk_on",
            "etf_in_longs", "etf_in_shorts", "tilt_mean"],
        "baseline": "tilt_mean",
        "label": "sector ETF beats SPY next month",
    },
}
C_GRID = (0.01, 0.1, 1.0)          # the whole light-tuning budget
MIN_OOS_PERIODS = 12             # M4: a beats verdict needs >= 12 USABLE
                                 # out-of-sample periods (months), not 12
                                 # total groups — the pilot (12 groups, 5
                                 # folds) must fail this and stay SHADOW


def _label_horizon_td(head: str) -> int:
    """M1: one head's label horizon in TRADING DAYS, from the dataset
    contract (ml_dataset's constants — the same numbers its manifest
    embargo statement documents). q: 63 td (~3 months) · e: 63+30=93 td
    (~5 months) · macro: ~21 td (next calendar month)."""
    import ml_dataset
    if head == "q":
        return int(ml_dataset.Y_Q_HORIZON_TD)
    if head == "e":
        return int(ml_dataset.Y_E_EVENT_WINDOW_TD) + int(ml_dataset.Y_E_HOLD_TD)
    return 21                       # y_m: next-month ETF label


def _inner_embargo_months(head: str) -> int:
    """M1: the INNER-CV embargo for one head = ceil(label horizon in
    months), NEVER a hard-coded 1: inner folds choose the hyper-parameter
    AND the Platt calibration, so their train label windows must not
    overlap the inner test month either. q -> 3, e -> 5, macro -> 1."""
    td = _label_horizon_td(head)
    return max(1, -(-td // 21))     # ceil(td / 21)


# ── data ──────────────────────────────────────────────────────────────────
def load_dataset(path: str) -> dict:
    """npz -> dict of arrays (allow_pickle=False, like the loader)."""
    z = np.load(path, allow_pickle=False)
    return {k: z[k] for k in z.files}


def dataset_meta(path: str) -> dict:
    """The sibling manifest.json (freq -> default embargo, provenance)."""
    p = Path(path)
    for cand in (p.parent / "manifest.json", p.parent.parent / "manifest.json"):
        if cand.exists():
            try:
                return json.loads(cand.read_text(encoding="utf-8"))
            except Exception:
                return {}
    return {}


def walk_forward_splits(groups, embargo_months: int, min_train_months: int):
    """(train_idx, test_idx) list, expanding window, group-granular purge +
    embargo: a test group is only predicted from groups at least
    `embargo_months` FULL months earlier (train_max <= test - embargo - 1),
    so overlapping 63-td label windows can never straddle the split."""
    ug = np.unique(np.asarray(groups))
    splits = []
    for g in ug:
        train_g = ug[ug <= g - embargo_months - 1]
        if len(train_g) < min_train_months:
            continue
        tr = np.flatnonzero(np.isin(groups, train_g))
        te = np.flatnonzero(groups == g)
        if len(tr) and len(te):
            splits.append((tr, te))
    return splits


# ── metrics (numpy only) ──────────────────────────────────────────────────
def _rankdata(x):
    """Average ranks (ties share the mean rank) — Spearman without scipy."""
    x = np.asarray(x, dtype=np.float64)
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), dtype=np.float64)
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and x[order[j + 1]] == x[order[i]]:
            j += 1
        ranks[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    return ranks


def _spearman(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3:
        return float("nan")
    ra, rb = _rankdata(a), _rankdata(b)
    ra -= ra.mean()
    rb -= rb.mean()
    da, db = float((ra * ra).sum()), float((rb * rb).sum())
    if da <= 0 or db <= 0:
        return float("nan")
    return float((ra * rb).sum() / (da * db) ** 0.5)


def _ece(p, y, bins: int = 5) -> float:
    p, y = np.asarray(p, float), np.asarray(y, float)
    if not len(p):
        return float("nan")
    ece, edges = 0.0, np.linspace(0.0, 1.0, bins + 1)
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi if hi < 1.0 else p <= hi)
        if m.any():
            ece += abs(float(y[m].mean()) - float(p[m].mean())) * float(m.mean())
    return ece


def _decile_spread(p, y) -> float:
    p, y = np.asarray(p, float), np.asarray(y, float)
    if len(p) < 20:
        return float("nan")
    order = np.argsort(p, kind="mergesort")
    k = max(1, len(p) // 10)
    return float(y[order[-k:]].mean() - y[order[:k]].mean())


def metrics_block(y, p, groups, base) -> dict:
    """The judgement block: per-month rank IC (the primary), decile spread,
    Brier + skill vs the base rate, ECE. Sample sizes always included.
    v1.4.1 (M3/M4, ported phase 3): empty input is a legal, honest block
    (n=0) — a head whose every fold was calibration-insufficient reports
    zeros, not in-sample numbers."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    n = int(len(y))
    if not n:
        return {"n": 0, "base_rate": float("nan"),
                "rank_ic_pooled": float("nan"),
                "rank_ic_monthly_mean": float("nan"),
                "rank_ic_monthly_min": float("nan"),
                "decile_spread": float("nan")}
    out = {"n": n, "base_rate": (float(np.nanmean(y)) if n else float("nan")),
           "rank_ic_pooled": _spearman(p, y),
           "rank_ic_monthly_mean": float("nan"),
           "rank_ic_monthly_min": float("nan"),
           "decile_spread": _decile_spread(p, y)}
    ics = []
    for g in np.unique(groups):
        m = groups == g
        if m.sum() >= 3:
            ic = _spearman(p[m], y[m])
            if ic == ic:
                ics.append(ic)
    if ics:
        out["rank_ic_monthly_mean"] = float(np.mean(ics))
        out["rank_ic_monthly_min"] = float(np.min(ics))
        out["n_months"] = len(ics)
    if n:
        brier = float(np.mean((p - y) ** 2))
        brier_base = float(np.mean((base - y) ** 2))
        out["brier"] = brier
        out["brier_base"] = brier_base
        out["brier_skill_vs_base"] = (1.0 - brier / brier_base
                                      if brier_base > 0 else float("nan"))
        out["ece_5bin"] = _ece(p, y)
    return out


# ── sklearn helpers (train-time only; inference never needs them) ──────────
def _pipe(C: float):
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    return Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("sc", StandardScaler()),
        ("lr", LogisticRegression(C=C, max_iter=2000, solver="lbfgs"))])


def _gbm(seed: int):
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(
        max_iter=120, learning_rate=0.05, max_leaf_nodes=8, l2_regularization=1.0,
        min_samples_leaf=20, random_state=seed)


def _inner_splits(groups, embargo_months: int):
    """M1: the (train_groups, test_groups) pairs _inner_oof walks —
    exposed so the no-leakage property is directly testable: no train
    group's label window may reach the earliest inner test month."""
    ug = np.unique(np.asarray(groups))
    n_folds = min(3, max(1, len(ug) - 1))
    out = []
    for f in range(n_folds):
        lo_i = int(f * len(ug) / n_folds)
        hi_i = min(int((f + 1) * len(ug) / n_folds), len(ug))
        te_g = ug[lo_i:hi_i]
        if not len(te_g):
            continue
        tr_g = ug[ug <= te_g.min() - embargo_months - 1]
        out.append((tr_g, te_g))
    return out


def _inner_oof(X, y, groups, make, key, embargo_months: int):
    """Group-aware inner CV INSIDE the train window: out-of-fold scores +
    the chosen hyper-parameter (no test data is ever touched). v1.4.1
    (M1, ported phase 3): the inner embargo is TARGET-AWARE — passed in
    by the caller as at least the head's label horizon in months
    (_inner_embargo_months), never the old hard-coded 1 month that let
    inner-fold label windows overlap the inner test month. Folds whose
    train slice is single-class are skipped (tiny samples)."""
    grid = (C_GRID if key == "C" else (None,))
    best, best_z, best_loss = None, None, float("inf")
    for c in grid:
        z = np.full(len(y), np.nan)
        for tr_g, te_g in _inner_splits(groups, embargo_months):
            tri = np.flatnonzero(np.isin(groups, tr_g))
            tei = np.flatnonzero(np.isin(groups, te_g))
            if not len(tri) or not len(tei) or len(np.unique(y[tri])) < 2:
                continue
            try:
                m = make(c) if key == "C" else make()
                m.fit(X[tri], y[tri])
                s = (m.decision_function(X[tei]) if key == "C"
                     else m.predict_proba(X[tei])[:, 1])
            except Exception:
                continue
            z[tei] = s
        msk = z == z
        if not msk.any():
            continue
        with np.errstate(over="ignore"):
            p = np.clip(1.0 / (1.0 + np.exp(-z[msk])), 1e-6, 1.0 - 1e-6)
        loss = float(np.mean((p - y[msk]) ** 2))
        if loss < best_loss:
            best, best_z, best_loss = c, z, loss
    return best, best_z


def _platt(z, y):
    """2-parameter Platt scaling by Newton iterations (numpy only)."""
    z, y = np.asarray(z, float), np.asarray(y, float)
    msk = z == z
    z, y = z[msk], y[msk]
    if len(z) < 20 or len(np.unique(y)) < 2:
        return 1.0, 0.0
    a, b = 1.0, 0.0
    for _ in range(100):
        with np.errstate(over="ignore"):
            p = 1.0 / (1.0 + np.exp(-np.clip(a * z + b, -500.0, 500.0)))
        w = np.clip(p * (1 - p), 1e-6, None)
        g_a = float(np.sum((p - y) * z))
        g_b = float(np.sum(p - y))
        h_aa = float(np.sum(w * z * z)) + 1e-6
        h_ab = float(np.sum(w * z))
        h_bb = float(np.sum(w)) + 1e-6
        det = h_aa * h_bb - h_ab * h_ab
        if abs(det) < 1e-12:
            break
        da = (g_a * h_bb - g_b * h_ab) / det
        db = (g_b * h_aa - g_a * h_ab) / det
        a, b = a - da, b - db
        if abs(da) < 1e-8 and abs(db) < 1e-8:
            break
    return float(a), float(b)


def _sigmoid(x):
    with np.errstate(over="ignore"):
        return 1.0 / (1.0 + np.exp(-x))


# ── one head ──────────────────────────────────────────────────────────────
def head_rows(ds: dict, head: str):
    """(X, y, groups, baseline_values) for one head; NaN-target rows are
    DROPPED from training/evaluation (they stay in the dataset, and the
    missing pattern itself is a feature — see DESIGN_NOTES.md)."""
    spec = HEADS[head]
    if spec["source"] == "macro":
        names = [str(x) for x in ds["macro_feature_names"]]
        Xall, y, groups = ds["macro_X"], ds["y_m"], ds["macro_group"]
    else:
        names = [str(x) for x in ds["feature_names"]]
        Xall, y, groups = ds["X"], ds[spec["target"]], ds["group"]
    have = set(names)
    feats = [f for f in spec["features"] if f in have]
    if len(feats) < 3:
        raise RuntimeError(f"head {head}: only {len(feats)} of its features "
                           f"exist in the dataset")
    idx = [names.index(f) for f in feats]
    m = y == y                                     # labeled rows only
    X = np.asarray(Xall, dtype=np.float64)[:, idx][m]
    yy = np.asarray(y, dtype=np.float64)[m]
    gg = np.asarray(groups)[m]
    base = None
    if spec["baseline"] in have:
        base = np.asarray(Xall, dtype=np.float64)[:, names.index(spec["baseline"])][m]
    return X, yy, gg, feats, base


def _test_offsets(splits):
    """Row offsets of each fold's test block inside the pooled OOS arrays
    (test blocks are appended in fold order)."""
    off, i = [], 0
    for _tr, te in splits:
        off.append(i)
        i += len(te)
    return off


FEATURE_CAP = 20            # final phase §7.2: max features per head


def select_features_fold(X, y, feats, train_idx,
                         cap: int = FEATURE_CAP) -> tuple:
    """§7.2 + phase-3 M2: rank features by |standardised logistic coef|
    fit on ONE window's rows — a training fold's TRAIN window for the
    walk-forward folds, all labeled rows for the final refit — and keep
    the top `cap`. Selection runs INSIDE each training fold, never pooled
    across folds: the v1.5.0 pooled ranking averaged importances over
    EVERY fold's train window, which for early folds includes later test
    periods' rows — exactly the leak the phase-3 prompt removes (F16).
    Returns (keep_idx, record) — the record travels per fold in the
    validation report."""
    if len(feats) <= cap:
        return list(range(len(feats))), {"cap": cap, "method": "not needed "
                                          f"({len(feats)} <= {cap})",
                                          "selected": list(feats),
                                          "dropped": []}
    try:
        pipe = _pipe(1.0).fit(X[train_idx], y[train_idx])
        imp = np.abs(pipe["lr"].coef_[0])      # standardised pipeline
    except Exception:
        return list(range(len(feats))), {"cap": cap,
                                         "method": "unrankable (window not "
                                         "fittable) — kept all, disclosed",
                                         "selected": list(feats),
                                         "dropped": []}
    order = sorted(range(len(feats)), key=lambda i: (-imp[i], feats[i]))
    keep = sorted(order[:cap])
    return keep, {"cap": cap,
                  "method": ("|standardised logistic coef| on this fold's "
                             "train window only (per-fold selection; no "
                             "test row, no other fold's data)"),
                  "selected": [feats[i] for i in sorted(order[:cap],
                                                         key=lambda i: feats[i])],
                  "dropped": [feats[i] for i in order[cap:]],
                  "importance": {feats[i]: float(imp[i]) for i in order}}


def _rowset_sha(groups, y) -> str:
    """M4: a digest of the EXACT (period, label) row set a verdict
    comparison used — the report carries one for the model side and one
    for the baseline side; equal digests prove identical rows."""
    key = "|".join(f"{int(g)}:{float(v):.6f}" for g, v in zip(groups, y))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def train_head(ds: dict, head: str, args) -> tuple[dict, dict, tuple]:
    """Walk-forward evaluation + final refit for one head. Returns
    (bundle, report, fitinfo); the bundle ships as SHADOW."""
    X, y, groups, feats, base = head_rows(ds, head)
    splits = walk_forward_splits(groups, args.embargo_months, args.min_train_months)
    if not splits:
        raise RuntimeError(
            f"head {head}: no walk-forward split fits (embargo "
            f"{args.embargo_months}m + min train {args.min_train_months}m vs "
            f"{len(np.unique(groups))} groups) — NOT ENOUGH DATA, refusing")
    # B-2/B-1: sklearn is a TRAIN-time dependency only (inference is pure
    # numpy). Data-sufficiency refusals above stay sklearn-independent; the
    # dep check is an honest RuntimeError -> exit 2 with the reason, so the
    # suite is green (asserting the refusal) even where sklearn is absent.
    try:
        import sklearn  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            f"head {head}: sklearn not importable ({e}) — training requires "
            "scikit-learn (inference never does); install it or train on "
            "the pinned machine")
    t0 = time.time()
    inner_em = _inner_embargo_months(head)          # M1: target-aware
    oos = {"y": [], "p": [], "g": [], "base": [], "p_gbm": [], "bcol": [],
           "ok": []}
    folds = []
    per_fold_sel: dict[str, list] = {}
    for tr, te in splits:
        # M2 (phase 3): selection INSIDE this training fold — THIS fold's
        # train window only; the pooled-across-folds ranking that used to
        # run here read later test periods' training data (leak, F16).
        keep_f, _rec_f = select_features_fold(X, y, feats, tr)
        Xf = X[:, keep_f]
        feats_f = [feats[i] for i in keep_f]
        C, z_in = _inner_oof(Xf[tr], y[tr], groups[tr], _pipe, "C", inner_em)
        C = C or C_GRID[1]
        calib, a, b = "inner_oof", None, None
        if z_in is None:
            # M3: NEVER calibrate on the rows the model was fit on — the
            # old in-sample fallback function is gone. This fold gets NO
            # calibrated probability, is marked insufficient, and cannot
            # support a positive verdict.
            calib = "insufficient"
        else:
            a, b = _platt(z_in, y[tr])
        pipe = _pipe(C).fit(Xf[tr], y[tr])
        z_te = pipe.decision_function(Xf[te])
        p_te = (np.clip(_sigmoid(a * z_te + b), 0.0, 1.0) if a is not None
                else np.full(len(te), np.nan))
        tr_base = float(np.mean(y[tr]))
        fold = {"train_groups": [int(groups[tr].min()), int(groups[tr].max())],
                "test_group": int(groups[te][0]), "C": C,
                "platt": ([float(a), float(b)] if a is not None else None),
                "calibration": calib, "features": list(feats_f),   # M2 record
                "n_train": int(len(tr)), "n_test": int(len(te))}
        if args.model in ("gbm", "auto"):
            try:
                _, zg_in = _inner_oof(Xf[tr], y[tr], groups[tr],
                                      lambda: _gbm(args.seed), "gbm", inner_em)
                if zg_in is None:             # M3: same rule for the GBM
                    p_gbm = np.full(len(te), np.nan)
                else:
                    ag, bg = _platt(np.log(np.clip(zg_in, 1e-6, 1 - 1e-6) /
                                           (1 - np.clip(zg_in, 1e-6, 1 - 1e-6))), y[tr])
                    gbm = _gbm(args.seed).fit(Xf[tr], y[tr])
                    pg = gbm.predict_proba(Xf[te])[:, 1]
                    zg = np.log(np.clip(pg, 1e-6, 1 - 1e-6) /
                                (1 - np.clip(pg, 1e-6, 1 - 1e-6)))
                    p_gbm = np.clip(_sigmoid(ag * zg + bg), 0.0, 1.0)
                    fold["gbm_ic"] = _spearman(p_gbm, y[te])
                oos["p_gbm"].extend(p_gbm.tolist())
            except Exception:
                oos["p_gbm"].extend([float("nan")] * len(te))
        oos["y"].extend(y[te].tolist())
        oos["p"].extend(p_te.tolist())
        oos["g"].extend(groups[te].tolist())
        oos["base"].extend([tr_base] * len(te))
        oos["ok"].extend([a is not None] * len(te))
        if base is not None:
            oos["bcol"].extend(base[te].tolist())
        per_fold_sel[str(fold["test_group"])] = list(feats_f)
        folds.append(fold)
    yv, pv, gv, bv = (np.array(oos["y"]), np.array(oos["p"]),
                      np.array(oos["g"]), np.array(oos["base"]))
    ok = np.asarray(oos["ok"], bool)                # M3: usable rows only
    pooled = metrics_block(yv[ok], pv[ok], gv[ok], bv[ok])
    baselines = {"base_rate": metrics_block(yv[ok], bv[ok], gv[ok], bv[ok])}
    bcol = (np.array(oos["bcol"]) if base is not None
            and len(oos["bcol"]) == len(yv) else None)
    # M4: the model and the raw-engine baseline are judged on IDENTICAL
    # OOS rows and time groups — rows the raw score cannot price are
    # dropped from BOTH sides of that comparison, never just the baseline.
    cmp = (ok & (bcol == bcol)) if bcol is not None else ok
    verdict_model = pooled
    verdict_mask = ok
    bp = None
    if bcol is not None and cmp.any():
        # the raw engine score as a ranking baseline, scaled to a
        # probability per-fold from that fold's TRAIN window only
        # (IC is scale-free; the scaling just makes Brier computable).
        bp = np.empty(len(bcol))
        for (tr, te), i0 in zip(splits, _test_offsets(splits)):
            lo, hi = float(np.nanmin(base[tr])), float(np.nanmax(base[tr]))
            n_te = len(te)
            bp[i0:i0 + n_te] = ((bcol[i0:i0 + n_te] - lo) / (hi - lo)
                                if hi > lo else 0.5)
        baselines["raw_engine_score"] = metrics_block(yv[cmp], bp[cmp],
                                                       gv[cmp], bv[cmp])
        verdict_model = metrics_block(yv[cmp], pv[cmp], gv[cmp], bv[cmp])
        verdict_mask = cmp
    pg = (np.array(oos["p_gbm"]) if args.model in ("gbm", "auto")
          and len(oos["p_gbm"]) == len(yv) else None)
    okg = (ok & (pg == pg)) if pg is not None else None
    pooled_gbm = None
    if okg is not None and okg.any():
        pooled_gbm = metrics_block(yv[okg], pg[okg], gv[okg], bv[okg])
    use_gbm = False
    if pooled_gbm is not None and pooled["rank_ic_monthly_mean"] == \
            pooled["rank_ic_monthly_mean"]:
        # M4: logistic-vs-GBM is also an identical-rows comparison
        both = (okg & ((bcol == bcol) if bcol is not None else True))
        if both.any():
            g_cmp = metrics_block(yv[both], pg[both], gv[both], bv[both])
            l_cmp = metrics_block(yv[both], pv[both], gv[both], bv[both])
            gic = g_cmp.get("rank_ic_monthly_mean", float("nan"))
            lic = l_cmp.get("rank_ic_monthly_mean", float("nan"))
            use_gbm = bool(gic == gic and lic == lic and gic > lic)
    if use_gbm:
        # M4 (phase-3 strengthening over v1.4.1, disclosed in port_map.md):
        # the GBM winner's verdict numbers are re-based to the row set it
        # shares with the raw-score baseline, so the model-vs-baseline
        # comparison in the report is ALWAYS identical-rows (v1.4.1
        # compared the GBM winner's all-usable-rows block against the
        # cmp-row baseline — different row sets).
        vbad = ((cmp & okg) if bcol is not None else okg)
        if vbad.any():
            verdict_model = metrics_block(yv[vbad], pg[vbad], gv[vbad], bv[vbad])
            if bcol is not None:
                baselines["raw_engine_score"] = metrics_block(
                    yv[vbad], bp[vbad], gv[vbad], bv[vbad])
            verdict_mask = vbad
    # final refit on ALL labeled rows (this is what ships). M2: its feature
    # selection runs on all labeled rows — the SHIPPED model's own window,
    # disclosed in feature_selection.method; the OOS judgement above used
    # each fold's train-window selection (the leak-sensitive surface).
    keep_fin, rec_fin = select_features_fold(X, y, feats, np.arange(len(y)))
    Xs = X[:, keep_fin]
    feats_final = [feats[i] for i in keep_fin]
    C, z_in = _inner_oof(Xs, y, groups, _pipe, "C", inner_em)
    C = C or C_GRID[1]
    final_calib = "inner_oof"
    if z_in is None:
        # M3: no in-sample fallback — the shipped head is NOT probability-
        # calibrated (identity calib) and can never support activation
        a, b = 1.0, 0.0
        final_calib = "uncalibrated_insufficient_inner_oof"
    else:
        a, b = _platt(z_in, y)
    model_type = "logistic_np"
    bundle = {
        "schema_version": 1, "model_type": model_type, "head": head,
        "feature_names": feats_final, "base_rate": float(np.mean(y)),
        "n_train": int(len(y)), "embargo_months": int(args.embargo_months),
        "train_from": str(ds["_as_of_min"]), "train_to": str(ds["_as_of_max"]),
        "trained_at": date.today().isoformat(), "state": "SHADOW",
        "master_version": master.__version__, "ml_train_version": __version__,
        "dataset_sha256": ds["_sha"], "config_hash": ds["_cfg_hash"],
    }
    if use_gbm:
        model_type = "gbm_joblib"
        bundle["model_type"] = model_type
        bundle["platt"] = [a, b]
    else:
        pipe = _pipe(C).fit(Xs, y)
        lr, sc, imp = pipe["lr"], pipe["sc"], pipe["imp"]
        bundle.update({
            "coef": lr.coef_[0].astype(np.float64),
            "intercept": float(lr.intercept_[0]),
            "impute_medians": imp.statistics_.astype(np.float64),
            "scaler_mean": sc.mean_.astype(np.float64),
            "scaler_scale": sc.scale_.astype(np.float64),
            "calib_a": float(a), "calib_b": float(b), "C": float(C)})
    feature_selection = {
        "cap": FEATURE_CAP,
        "method": ("per-fold |standardised logistic coef| computed on THAT "
                   "fold's train window only (M2: never pooled across "
                   "folds — the old pooled ranking read later test periods' "
                   "training data); the final refit selects on all "
                   "labeled rows (the shipped model, disclosed)"),
        "selected": list(rec_fin["selected"]),   # the shipped model's set
        "dropped": list(rec_fin.get("dropped", [])),
        "per_fold": per_fold_sel,
    }
    winner = pooled_gbm if use_gbm else verdict_model
    winner_mask = ((verdict_mask & okg) if (use_gbm and okg is not None)
                   else verdict_mask)
    n_oos_periods = int(len(np.unique(gv[winner_mask]))) if len(gv) else 0
    n_insufficient = int(sum(1 for f in folds
                             if f.get("calibration") == "insufficient"))
    rowset_sha = (_rowset_sha(gv[winner_mask], yv[winner_mask])
                  if len(gv) else "")
    min_oos = 100                    # a priori: below this nothing is judged
    enough = (winner.get("n", 0) >= min_oos
              and n_oos_periods >= MIN_OOS_PERIODS
              and final_calib == "inner_oof")
    beats_ic = (winner.get("rank_ic_monthly_mean", float("nan"))
                == winner.get("rank_ic_monthly_mean", float("nan"))
                and winner["rank_ic_monthly_mean"] > 0.0
                and (baselines.get("raw_engine_score") is None
                     or winner["rank_ic_monthly_mean"] >
                     baselines["raw_engine_score"].get("rank_ic_monthly_mean",
                                                       float("nan"))))
    brier_ok = winner.get("brier_skill_vs_base", float("nan")) > 0.0
    verdict = ("beats" if (enough and beats_ic and brier_ok)
               else ("insufficient evidence" if not enough else "fails"))
    if not enough:
        bits = []
        if winner.get("n", 0) < min_oos:
            bits.append(f"n_oos {winner.get('n', 0)} < {min_oos} rows")
        if n_oos_periods < MIN_OOS_PERIODS:
            bits.append(f"only {n_oos_periods} usable OOS period(s) < "
                        f"{MIN_OOS_PERIODS} — sample too small to judge, "
                        "however good the numbers look")
        if final_calib != "inner_oof":
            bits.append("final model not probability-calibrated (inner OOF "
                        "unavailable — no in-sample fallback, ever)")
        verdict_why = "; ".join(bits)
    elif not beats_ic:
        verdict_why = "monthly rank IC does not beat zero and the raw engine score"
    elif not brier_ok:
        verdict_why = "Brier skill vs the base rate is not positive"
    else:
        verdict_why = ("all conditions hold (IC, baseline, calibration, "
                       f">= {MIN_OOS_PERIODS} usable OOS periods)")
    has_baseline = baselines.get("raw_engine_score") is not None
    report = {
        "head": head, "label": HEADS[head]["label"],
        "model_type": model_type, "features": feats_final,
        "feature_selection": feature_selection,
        "embargo_months": int(args.embargo_months),
        "embargo_rule": ("test group predicted only from groups <= test - "
                         f"{args.embargo_months} - 1 (label windows can never "
                         "straddle a split; walk-forward, never shuffled)"),
        "inner_embargo_months": int(inner_em),
        "inner_embargo_rule": ("inner CV embargo >= the head's label horizon "
                                f"in months ({inner_em}m for this head, "
                                "_inner_embargo_months) — inner-fold label "
                                "windows can never overlap an inner test "
                                "month"),
        "n_groups": int(len(np.unique(groups))), "n_train_rows": int(len(y)),
        "n_oos_rows": int(winner.get("n", 0)), "n_oos_periods": n_oos_periods,
        "n_insufficient_folds": n_insufficient,
        "final_calibration": final_calib,
        "verdict_basis": {"n_rows": int(winner.get("n", 0)),
                          "n_periods": n_oos_periods,
                          "model_rowset_sha256": rowset_sha,
                          "baseline_rowset_sha256": (rowset_sha
                                                     if has_baseline else None),
                          "note": ("no raw-score baseline exists for this "
                                   "head — the verdict basis is the model's "
                                   "usable OOS rows alone"
                                   if not has_baseline else
                                   "model vs raw-engine baseline judged on "
                                   "identical OOS rows and time groups "
                                   "(equal row-set digests prove it)")},
        "folds": folds,
        "pooled": pooled, "pooled_gbm": pooled_gbm,
        "baselines": baselines, "verdict": verdict, "verdict_why": verdict_why,
        "verdict_rule": (f"beats IFF n_oos >= 100 rows AND >= {MIN_OOS_PERIODS} "
                         "usable OOS periods AND final model calibrated via "
                         "inner OOF AND monthly-mean rank IC > 0 AND > "
                         "raw-engine-score baseline IC (identical rows) AND "
                         "Brier skill vs base rate > 0; a failed sample gate "
                         "is 'insufficient evidence' naming the condition"),
        "sample_warning": (f"{len(splits)} test fold(s) on "
                           f"{len(np.unique(groups))} monthly groups — a PILOT-"
                           "size sample: treat every metric as indicative, "
                           "never as proof; the head ships SHADOW either way"),
        "elapsed_s": round(time.time() - t0, 1),
    }
    bundle["metrics_json"] = json.dumps(
        {k: (None if v != v else v) for k, v in winner.items()}, default=str)
    return bundle, report, (use_gbm, C, a, b, Xs, y, groups)


def save_model(path: Path, bundle: dict, fit=None, pin_versions: bool = True) -> dict:
    """npz (allow_pickle=False); a GBM winner also drops a joblib sidecar.
    Final phase (§7.1): the sidecar is written FIRST, then pinned — its
    sha256 (+ sklearn + master versions) travel inside the npz so master
    can refuse to unpickle an unhashed or tampered file. B-1 (§3.1): the
    pin set is the FULL training environment — sklearn, numpy, joblib AND
    python — so a load on a different interpreter marks the head
    UNAVAILABLE instead of attempting a cross-version unpickle.
    pin_versions=False (--activate) keeps the ORIGINAL pins (the file is
    not retrained, so its training-environment pins must never be
    rewritten by whichever machine flips the state bit) and needs NO
    sklearn/joblib import. Returns the pins dict."""
    path.parent.mkdir(parents=True, exist_ok=True)
    _PIN_KEYS = ("sklearn_version", "numpy_version", "joblib_version",
                 "python_version", "master_version")
    if pin_versions:
        import sklearn
        import joblib
        pins: dict = {"sklearn_version": str(sklearn.__version__),
                      "numpy_version": str(np.__version__),
                      "joblib_version": str(joblib.__version__),
                      "python_version": sys.version.split()[0],
                      "master_version": str(master.__version__)}
        # §7.1: EVERY fresh-trained head pins the versions it was trained
        # with; a GBM head additionally pins its joblib sidecar's sha256.
        for key in _PIN_KEYS:
            if key not in bundle:
                bundle[key] = pins[key]
    else:
        pins = {k: str(bundle.get(k, "")) for k in _PIN_KEYS}
        if bundle.get("sidecar_sha256"):
            pins["sidecar_sha256"] = str(bundle["sidecar_sha256"])
    import os
    if bundle.get("model_type") == "gbm_joblib" and fit is not None:
        import joblib
        side = path.with_suffix(".joblib")
        # B8 (v1.4.1 port + phase-2 fsync): the sidecar is written atomically
        # (tmp + fsync + rename) — a crash mid-write leaves the previous
        # pickle intact, never a truncated model a later run would load.
        tmp_j = side.with_name(side.name + ".tmp")
        try:
            joblib.dump(fit, tmp_j)
            fd = os.open(tmp_j, os.O_RDWR)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(tmp_j, side)
        finally:
            if tmp_j.exists():
                tmp_j.unlink()
        import hashlib
        pins["sidecar_sha256"] = hashlib.sha256(side.read_bytes()).hexdigest()
        bundle["sidecar_sha256"] = pins["sidecar_sha256"]
    # B8 (v1.4.1 port + phase-2 fsync): the npz is written atomically too
    # (tmp + fsync + rename) — same contract as the sidecar.
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "wb") as fh:
            np.savez(fh, **{k: (np.asarray(v) if not isinstance(v, str) else v)
                            for k, v in bundle.items()})
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    return pins


def load_model(path) -> dict:
    """Load exactly the way master.MLLayer does (allow_pickle=False)."""
    z = np.load(path, allow_pickle=False)
    b = {k: z[k] for k in z.files}
    b["feature_names"] = [str(x) for x in np.asarray(b["feature_names"]).tolist()]
    for k in ("coef", "impute_medians", "scaler_mean", "scaler_scale"):
        if k in b:
            b[k] = np.asarray(b[k], dtype=np.float64)
    return b


def predict(bundle: dict, X) -> np.ndarray:
    """Master.MLLayer's inference path, verbatim semantics: impute to the
    training medians, scale, logistic, Platt — pure numpy, [0, 1]."""
    X = np.asarray(X, dtype=np.float64)
    if X.ndim == 1:
        X = X.reshape(1, -1)
    if bundle.get("model_type") == "gbm_joblib":
        import joblib
        m = joblib.load(Path(bundle["_path"]).with_suffix(".joblib")) \
            if "_path" in bundle else None
        if m is None:
            raise RuntimeError("gbm_joblib bundle needs _path for prediction")
        return m.predict_proba(X)[:, 1]
    med = bundle["impute_medians"]
    X = np.where(np.isnan(X), med, X)
    Z = (X - bundle["scaler_mean"]) / bundle["scaler_scale"]
    Z = Z @ bundle["coef"] + bundle["intercept"]
    return np.clip(_sigmoid(bundle["calib_a"] * Z + bundle["calib_b"]), 0.0, 1.0)


# ── CLI ───────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ml_train.py", description=__doc__.splitlines()[0])
    p.add_argument("--dataset", default="ml_data/dataset_v1.npz",
                   help="the phase-4 dataset (npz, allow_pickle=False)")
    p.add_argument("--out", default="ml_data/models",
                   help="model + validation-report directory")
    p.add_argument("--heads", default="q,e,macro",
                   help="subset of q,e,macro (comma list)")
    p.add_argument("--embargo-months", type=int, default=None,
                   help="purge+embargo in months (default: 3 monthly grid / "
                        "1 quarterly — read from the dataset manifest; must "
                        "be >= the label horizon)")
    p.add_argument("--min-train-months", type=int, default=4,
                   help="expanding-window minimum train groups (default 4)")
    p.add_argument("--model", choices=("logistic", "gbm", "auto"), default="auto",
                   help="auto = logistic first, GBM kept only if it beats "
                        "logistic out of sample (the spec's rule)")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--activate", default=None, metavar="HEAD",
                   help="flip a shipped head to ACTIVE — refused (exit 2) "
                        "without a validation report whose verdict is 'beats'")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    heads = [h.strip() for h in args.heads.split(",") if h.strip()]
    bad = [h for h in heads if h not in HEADS]
    if bad or (args.activate and args.activate not in heads):
        print(f"ml_train: unknown head(s) {', '.join(bad or [args.activate])} "
              f"(known: {', '.join(HEADS)})", file=sys.stderr)
        return 64
    ds_path = Path(args.dataset)
    if not ds_path.exists():
        print(f"ml_train: dataset not found: {ds_path} (build it with "
              "ml_dataset.py)", file=sys.stderr)
        return 2
    ds = load_dataset(str(ds_path))
    meta = dataset_meta(str(ds_path))
    # v1.8.0 (W6, R7): REFUSE datasets whose manifest is SYNTHETIC or
    # lacks API provenance — no verdict (not even a training run) from
    # synthetic data; the shipped pilot is REAL-API (backfilled manifest
    # field, additive).
    _prov = (meta or {}).get("data_provenance") or {}
    _syn_ok = str(os.environ.get("MASTER_ALLOW_SYNTHETIC", "")).strip().lower() \
        in ("1", "true")
    if not _syn_ok and not _prov.get("class"):
        print(f"ml_train: REFUSED — dataset manifest lacks data_provenance "
              f"(no API provenance: {ds_path}) — rebuild with "
              "python3 ml_dataset.py (real engine fetches; the owner "
              "network run)", file=sys.stderr)
        return 2
    if str(_prov.get("class", "")).upper() != "REAL-API":
        if not _syn_ok:
            print(f"ml_train: REFUSED — dataset data_provenance is "
                  f"{_prov.get('class')!r} (synthetic fixtures are unit-test "
                  "only; training for a verdict needs real API data — R7)",
                  file=sys.stderr)
            return 2
        print("ml_train: SYNTHETIC dataset ALLOWED "
              "(MASTER_ALLOW_SYNTHETIC=1 — unit-test fixture path; "
              "never real evidence, never a verdict — R7)",
              file=sys.stderr)
    ds["_sha"] = hashlib.sha256(ds_path.read_bytes()).hexdigest()[:12]
    # v1.8.0 (D-18-002): deterministic CONFIG hash (shared recipe with
    # me/backtest and ml_dataset — see master._canonical_json).
    ds["_cfg_hash"] = hashlib.sha256(master._canonical_json(
        master.CONFIG).encode()).hexdigest()[:16]
    asofs = np.asarray(ds.get("as_of", []), dtype="datetime64[D]")
    ds["_as_of_min"] = str(asofs.min()) if len(asofs) else ""
    ds["_as_of_max"] = str(asofs.max()) if len(asofs) else ""
    if args.embargo_months is None:
        freq = str(meta.get("build", {}).get("freq", "monthly"))
        args.embargo_months = 1 if freq == "quarterly" else 3
    if args.embargo_months < 1:
        print("ml_train: --embargo-months must be >= 1 (the label horizon)",
              file=sys.stderr)
        return 64
    # leakage guards (phase-5 gate): a dataset that already carries label
    # columns inside X is refused before anything is trained
    feats_all = {str(x) for x in ds.get("feature_names", [])}
    forbidden = sorted(feats_all & set(master.CONFIG["ML_FORBIDDEN_FEATURES"]))
    if forbidden:
        print(f"ml_train: REFUSED — feature(s) {', '.join(forbidden)} are "
              "label-window derived (future-dated); the dataset is leaking",
              file=sys.stderr)
        return 2
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.activate:
        head = args.activate
        model_p = out_dir / f"head_{head}.npz"
        rep_p = out_dir / f"validation_{head}.json"
        if not model_p.exists():
            print(f"ml_train: --activate {head}: no model at {model_p}",
                  file=sys.stderr)
            return 2
        if not rep_p.exists():
            print(f"ml_train: --activate {head} REFUSED — no validation report "
                  f"({rep_p.name}); ACTIVE needs a report that beats the "
                  "baselines", file=sys.stderr)
            return 2
        verdict = ""
        rep: dict = {}
        try:
            rep = json.loads(rep_p.read_text(encoding="utf-8"))
            verdict = str(rep.get("verdict", ""))
        except Exception:
            verdict = ""
        if verdict != "beats":
            print(f"ml_train: --activate {head} REFUSED — validation verdict "
                  f"is {verdict!r}, not 'beats'", file=sys.stderr)
            return 2
        # M5 (phase 3): the report must be hash-bound to THIS model file
        # and the dataset it was trained on — a verdict alone is not
        # evidence. The model hash is checked BEFORE the npz is parsed, so
        # a corrupted/tampered file refuses cleanly instead of crashing.
        model_sha = hashlib.sha256(model_p.read_bytes()).hexdigest()
        if str(rep.get("model_sha256", "")) != model_sha:
            print(f"ml_train: --activate {head} REFUSED — the report's "
                  "model_sha256 does not match this model file (train or "
                  "re-validate first)", file=sys.stderr)
            return 2
        b_check = load_model(model_p)
        ds_pin = str(b_check.get("dataset_sha256", "") or "")
        rep_ds = str(rep.get("dataset_sha256", "") or "")
        if not ds_pin or rep_ds != ds_pin:
            # stricter than v1.4.1 (disclosed in port_map.md): an npz with
            # no dataset pin is a malformed/legacy artifact — activation
            # requires BOTH sides of the pin to exist and agree.
            print(f"ml_train: --activate {head} REFUSED — the report's "
                  "dataset_sha256 does not match the model's training "
                  "dataset pin", file=sys.stderr)
            return 2
        b = dict(b_check)
        b["state"] = "ACTIVE"
        b["activated_at"] = date.today().isoformat()
        if b.get("model_type") == "gbm_joblib" and not str(
                b.get("sidecar_sha256", "") or ""):
            print(f"ml_train: --activate {head} REFUSED — GBM sidecar has "
                  "no integrity pin (sidecar_sha256); retrain with this "
                  "version first", file=sys.stderr)
            return 2
        save_model(model_p, b, pin_versions=False)   # keep the TRAINING pins
        # the state rewrite changes the npz bytes -> re-bind the report to
        # the ACTIVATED artifact (the sanctioned rewrite; any later byte
        # change breaks this pin and master downgrades the head to SHADOW)
        rep["model_sha256"] = hashlib.sha256(model_p.read_bytes()).hexdigest()
        rep["activated_at"] = date.today().isoformat()
        _atomic_write_text(rep_p, json.dumps(rep, indent=2, default=str))
        print(f"ml_train: head {head} -> ACTIVE (hash-bound validation "
              "report on file)")
        return 0
    rc = 0
    for head in heads:
        try:
            bundle, report, fitinfo = train_head(ds, head, args)
        except RuntimeError as e:                     # honest refusal
            print(f"ml_train: head {head}: {e}", file=sys.stderr)
            rc = 2
            continue
        use_gbm, C, a, b, X, y, groups = fitinfo
        fit = None
        if use_gbm:
            fit = _gbm(args.seed).fit(X, y)
        pins = save_model(out_dir / f"head_{head}.npz", bundle, fit)
        report["pins"] = pins
        # M5 (phase 3): bind the report to the exact artifacts it was
        # produced from — model_sha256 (the npz just written) and the
        # dataset pin inside it; --activate and master's loader verify.
        report["model_sha256"] = hashlib.sha256(
            (out_dir / f"head_{head}.npz").read_bytes()).hexdigest()
        report["dataset_sha256"] = str(bundle["dataset_sha256"])
        _atomic_write_text(out_dir / f"validation_{head}.json",
                           json.dumps(report, indent=2, default=str))
        # v1.8.0 (W6): the feature-stability report — how often each
        # feature survived per-fold selection (selection runs INSIDE each
        # fold's train window, M2). Frequency 1.0 = stable across every
        # fold; 0.x = unstable; reported, not acted on (no tuning).
        _pf = (report.get("feature_selection") or {}).get("per_fold") or {}
        _stab = {"head": head, "folds": len(_pf),
                 "features": {}, "note":
                 "selection frequency across walk-forward folds (per-fold "
                 "train-window selection, M2); descriptive — never a "
                 "tuning signal"}
        for _f, _sel in _pf.items():
            for _name in _sel:
                _e = _stab["features"].setdefault(
                    _name, {"selected": 0, "folds": len(_pf)})
                _e["selected"] += 1
        for _e in _stab["features"].values():
            _e["freq"] = round(_e["selected"] / max(1, _e["folds"]), 3)
        _stab["features"] = dict(sorted(
            _stab["features"].items(),
            key=lambda kv: (-kv[1]["freq"], kv[0])))
        _atomic_write_text(out_dir / f"stability_{head}.json",
                           json.dumps(_stab, indent=2, default=str))
        w = report["pooled_gbm"] if use_gbm else report["pooled"]
        print(f"[ml_train] head {head}: {report['model_type']} · "
              f"{report['n_train_rows']} train rows · {report['n_oos_rows']} "
              f"usable OOS rows over {len(report['folds'])} fold(s) · "
              f"{report['n_insufficient_folds']} insufficient · embargo "
              f"{args.embargo_months}m (inner {report['inner_embargo_months']}m)")
        print(f"[ml_train]   usable OOS periods {report['n_oos_periods']} · "
              f"final calibration {report['final_calibration']}")
        print(f"[ml_train]   monthly rank IC "
              f"{w.get('rank_ic_monthly_mean', float('nan')):+.3f} · decile "
              f"spread {w.get('decile_spread', float('nan')):+.3f} · Brier "
              f"skill {w.get('brier_skill_vs_base', float('nan')):+.3f} · "
              f"verdict {report['verdict']}")
        bsc = report["baselines"].get("raw_engine_score")
        if bsc:
            print(f"[ml_train]   baseline raw score IC "
                  f"{bsc.get('rank_ic_monthly_mean', float('nan')):+.3f} "
                  f"(identical rows: verdict_basis n="
                  f"{report['verdict_basis']['n_rows']})")
        print(f"[ml_train]   model_sha256 {report['model_sha256'][:16]}… · "
              f"dataset_sha256 {report['dataset_sha256']}")
        print(f"[ml_train]   shipped SHADOW -> {out_dir / f'head_{head}.npz'}")
    return rc


if __name__ == "__main__":                                # pragma: no cover
    raise SystemExit(main())
