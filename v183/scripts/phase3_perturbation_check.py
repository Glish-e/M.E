#!/usr/bin/env python3
"""scripts/phase3_perturbation_check.py — PHASE 3 evidence generator.

Runs the M2 perturbation contract end-to-end on a 26-feature synthetic
panel (> FEATURE_CAP) and prints the per-fold selected feature sets for
the ORIGINAL panel and the TEST-FOLD-PERTURBED panel (last group's labels
flipped + feature values jittered — a test fold's rows, in NO training
fold's train window) side by side, then asserts every fold's selection is
identical. This is the paste for evidence/phase3_perturbation.txt; the
same contract is asserted permanently by
TestMLGatesPhase3.test_m2_selection_perturbation_test_fold_only and
TestFeatureCap.test_select_features_fold_cap_and_train_only.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ml_train as mt  # noqa: E402


def panel(path: Path, months=10, names=30, seed=7, perturb=False) -> Path:
    import numpy as np
    feats = ["q_score", "q_rank_pct", "q_coverage", "q_flag_count", "q_veto",
             "conviction", "macro_tilt", "macro_confidence", "macro_leverage",
             "macro_credit_on", "macro_regime_defensive", "macro_regime_risk_on",
             "sector_financials", "sector_industrials", "sector_healthcare",
             "sector_tech", "sector_communication", "sector_consumer",
             "sector_energy", "sector_materials", "sector_reits",
             "sector_utilities", "sector_specialty", "q_missing", "r_q_score",
             "r_conviction"]
    f = len(feats)
    rng = np.random.default_rng(seed)
    ticks, asofs, groups, secs, rows, ys = [], [], [], [], [], []
    for g in range(months):
        as_of = (f"2025-{g + 1:02d}-28" if g < 12
                 else f"2026-{g - 11:02d}-28")
        for i in range(names):
            q = rng.uniform(25.0, 95.0)
            mt_ = rng.uniform(-0.5, 1.0)
            y = 1.0 if (q - 60.0) / 12.0 + 1.1 * (mt_ - 0.25) \
                + rng.normal(0, 0.6) > 0 else 0.0
            row = [0.0] * f
            row[0] = q
            row[feats.index("macro_tilt")] = mt_
            row[feats.index("sector_tech")] = float(i % 2)
            for j in range(f):
                if j not in (0, feats.index("macro_tilt"),
                             feats.index("sector_tech")):
                    row[j] = rng.normal(0, 1.0)
            if perturb and g == months - 1:
                y = 1.0 - y                          # flip the label
                row[0] = 95.0 - row[0]               # jitter features
                row[feats.index("macro_tilt")] = -row[feats.index("macro_tilt")]
            ticks.append(f"T{i:02d}")
            asofs.append(as_of)
            groups.append(g)
            secs.append("tech" if i % 2 else "healthcare")
            rows.append(row)
            ys.append(y)
    n = len(ys)
    np.savez_compressed(path, X=np.array(rows, dtype=np.float32),
                        feature_names=np.array(feats),
                        tickers=np.array(ticks),
                        as_of=np.array(asofs, dtype="datetime64[D]"),
                        sector=np.array(secs),
                        y_q=np.array(ys, dtype=np.float32),
                        y_e=np.full(n, np.nan, dtype=np.float32),
                        ret_21=np.zeros(n, dtype=np.float32),
                        ret_63=np.zeros(n, dtype=np.float32),
                        group=np.array(groups, dtype=np.int64),
                        event_date=np.array([""] * n),
                        label_end_63=np.array([""] * n),
                        macro_X=np.zeros((0, 9), dtype=np.float32),
                        macro_feature_names=np.array([], dtype="<U24"),
                        macro_etf=np.array([], dtype="<U8"),
                        macro_as_of=np.array([], dtype="datetime64[D]"),
                        y_m=np.array([], dtype=np.float32),
                        macro_group=np.array([], dtype=np.int64),
                        macro_ret_1m=np.array([], dtype=np.float32))
    return path


def main() -> int:
    argv_tail = ["--heads", "q", "--embargo-months", "1",
                 "--min-train-months", "3", "--model", "logistic"]
    with tempfile.TemporaryDirectory() as tmp:
        a = panel(Path(tmp) / "a.npz", seed=7)
        b = panel(Path(tmp) / "b.npz", seed=7, perturb=True)
        for tag, ds in (("A (original)", a), ("B (test-fold rows perturbed)", b)):
            rc = mt.main(["--dataset", str(ds), "--out",
                          str(Path(tmp) / tag.split()[0])] + argv_tail)
            assert rc == 0, (tag, rc)
        ra = json.loads((Path(tmp) / "A" / "validation_q.json").read_text())
        rb = json.loads((Path(tmp) / "B" / "validation_q.json").read_text())
        print("per-fold selected feature sets (cap %d of 26 candidates):"
              % mt.FEATURE_CAP)
        print(f"{'test group':>10} | {'A selected':<58} | identical")
        all_same = True
        for fa, fb in zip(ra["folds"], rb["folds"]):
            same = fa["features"] == fb["features"]
            all_same &= same
            print(f"{fa['test_group']:>10} | {','.join(fa['features'])[:58]:<58} "
                  f"| {'YES' if same else 'NO — ' + ','.join(fb['features'])}")
        print()
        print("perturbed rows: last group's labels FLIPPED and q_score / "
              "macro_tilt values jittered (a test fold's rows; in no "
              "training fold's train window)")
        print("result:", "EVERY fold's selected feature set is bit-identical"
              if all_same else "MISMATCH — LEAK")
        print("final refit selection (all labeled rows, the shipped model):")
        print("  A:", ",".join(ra["feature_selection"]["selected"]))
        print("  B:", ",".join(rb["feature_selection"]["selected"]))
        print("  (may legitimately differ — the final model trains on ALL "
              "labeled rows incl. the perturbed group; the OOS judgement "
              "folds above are the leak-sensitive surface)")
        return 0 if all_same else 1


if __name__ == "__main__":
    raise SystemExit(main())
