"""Recompute leave-one-model-out recall denominators and Wilson CIs.

The paper reported the per-model recall CI using N=280 (total held-out sessions).
Recall is defined over POSITIVES only (tp+fn), so the denominator must be the
number of attack successes in the held-out model. This script recomputes both.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from paper_a_classifier import load_data  # noqa: E402

from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402


def wilson(k, n, z=1.96):
    """Wilson score interval for k successes in n trials."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z**2 / n
    c = p + z**2 / (2 * n)
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return ((c - half) / d, (c + half) / d)


def main():
    records, by_model = load_data()
    feature_names = list(records[0]["features"].keys())
    X = np.array([[r["features"][f] for f in feature_names] for r in records])
    y = np.array([r["label"] for r in records])
    models_arr = np.array([r["model"] for r in records])
    print(f"Total sessions: {len(y)}, positives: {int(y.sum())}")
    print()

    rows = []
    for held in sorted(set(models_arr)):
        held_idx = np.where(models_arr == held)[0]
        train_idx = np.where(models_arr != held)[0]
        if len(held_idx) < 5 or len(train_idx) < 50:
            continue
        y_test = y[held_idx]
        if len(np.unique(y_test)) < 2:
            continue
        clf = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42)
        clf.fit(X[train_idx], y[train_idx])
        proba = clf.predict_proba(X[held_idx])[:, 1]
        auc = roc_auc_score(y_test, proba)
        preds = (proba >= 0.5).astype(int)
        tp = int(((preds == 1) & (y_test == 1)).sum())
        fn = int(((preds == 0) & (y_test == 1)).sum())
        pos = tp + fn
        recall = tp / pos if pos else float("nan")
        lo_correct, hi_correct = wilson(tp, pos)
        lo_wrong, hi_wrong = wilson(len(held_idx), len(held_idx))
        rows.append((held, len(held_idx), pos, tp, fn, auc, recall,
                     lo_correct, hi_correct, lo_wrong, hi_wrong))
        print(f"{held:<26} Ntot={len(held_idx):>4}  POS={pos:>4}  tp={tp:>4} fn={fn:>3}  "
              f"AUC={auc:.3f}  recall={recall:.4f}  "
              f"Wilson(correct, n=POS)=[{lo_correct:.4f},{hi_correct:.4f}]  "
              f"Wilson(paper, n=Ntot)=[{lo_wrong:.4f},{hi_wrong:.4f}]")

    print()
    perfect = [r for r in rows if abs(r[6] - 1.0) < 1e-12 and r[5] >= 0.999]
    print(f"Models with AUC=1.000 and recall=1.000: {len(perfect)}")
    for r in perfect:
        print(f"  {r[0]:<26} POS={r[2]:>4}  Wilson=[{r[7]:.4f}, {r[8]:.4f}]")
    if perfect:
        min_pos = min(r[2] for r in perfect)
        worst = min(r[7] for r in perfect)
        pooled_pos = sum(r[2] for r in perfect)
        pooled_lo, pooled_hi = wilson(pooled_pos, pooled_pos)
        print()
        print(f"Smallest per-model positive count: {min_pos}")
        print(f"Weakest (lowest) per-model Wilson lower bound: {worst:.4f}")
        print(f"Pooled positives across these models: {pooled_pos}")
        print(f"Pooled Wilson CI: [{pooled_lo:.4f}, {pooled_hi:.4f}]")


if __name__ == "__main__":
    main()
