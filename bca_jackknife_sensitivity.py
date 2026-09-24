"""Sensitivity of the reported BCa AUC interval to the jackknife subsample.

paper_a_classifier.py estimates the BCa acceleration from the FIRST 200
leave-one-out samples in file order (n_jack = min(len(y), 200); for i in
range(n_jack)). Records load in file order, so this is not a representative
jackknife. This script recomputes the interval three ways -- the superseded
first-200 form (since removed from the code), a random 200, and the full
leave-one-out jackknife -- to determine
whether the reported interval is sensitive to that choice.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.stats import norm
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

sys.path.insert(0, str(Path(__file__).parent))
from paper_a_classifier import load_data  # noqa: E402


def bca_interval(y, proba, auc, boot_aucs, jack_idx):
    jack = np.array([
        roc_auc_score(np.delete(y, i), np.delete(proba, i))
        if len(np.unique(np.delete(y, i))) >= 2 else auc
        for i in jack_idx
    ])
    jm = jack.mean()
    num = np.sum((jm - jack) ** 3)
    den = 6 * (np.sum((jm - jack) ** 2) ** 1.5)
    a_hat = num / den if den != 0 else 0.0
    z0 = norm.ppf(np.mean(boot_aucs <= auc) + 1e-10)
    out = []
    for q in (0.025, 0.975):
        z = norm.ppf(q)
        adj = z0 + (z0 + z) / (1 - a_hat * (z0 + z))
        out.append(np.percentile(boot_aucs, 100 * norm.cdf(adj)))
    return a_hat, out[0], out[1]


def main():
    records, _ = load_data()
    names = list(records[0]["features"].keys())
    X = np.array([[r["features"][f] for f in names] for r in records])
    y = np.array([r["label"] for r in records])
    print(f"N={len(y)}  positives={int(y.sum())}")

    clf = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    proba = cross_val_predict(clf, X, y, cv=cv, method="predict_proba")[:, 1]
    auc = roc_auc_score(y, proba)
    print(f"pooled out-of-fold AUC = {auc:.5f}")

    rng = np.random.RandomState(42)
    boot = np.array([
        roc_auc_score(y[i], proba[i]) if len(np.unique(y[i])) >= 2 else auc
        for i in (rng.choice(len(y), size=len(y), replace=True) for _ in range(10000))
    ])

    variants = {
        "first 200 (superseded form)": np.arange(min(len(y), 200)),
        "random 200 (seed 0)": np.random.RandomState(0).choice(len(y), 200, replace=False),
        "random 200 (seed 1)": np.random.RandomState(1).choice(len(y), 200, replace=False),
        "full jackknife (all N)": np.arange(len(y)),
    }
    print(f"\n{'variant':<26} {'a_hat':>12} {'lo':>9} {'hi':>9}")
    for label, idx in variants.items():
        a_hat, lo, hi = bca_interval(y, proba, auc, boot, idx)
        print(f"{label:<26} {a_hat:>12.6f} {lo:>9.5f} {hi:>9.5f}")

    # Is the first-200 block representative?
    print(f"\nLabel mean in first 200 rows: {y[:200].mean():.3f}  vs overall {y.mean():.3f}")


if __name__ == "__main__":
    main()
