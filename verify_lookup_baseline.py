"""EXPLORATORY re-analysis (issue 4): fold-safe memorization baselines for the
19-feature classifier, to be reported beside the 5-fold CV. Reads IED factorial
(read-only). git_dirty expected; commits forbidden. No API calls.

Reports:
 (1) exact train/test vector overlap under the paper's 5-fold CV (seed 42),
 (2) OUT-OF-FOLD majority-vote lookup baseline (train-fold labels only; unseen
     test vectors fall back to the training-fold prior), on the same folds,
 (3) leave-one-vector-out (GroupKFold grouped on the 22 distinct vectors):
     the honest generalization-to-unseen-vector number.
"""
import numpy as np
from collections import Counter, defaultdict
from paper_a_classifier import load_data
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score

records, _ = load_data()
FN = list(records[0]["features"].keys())
X = np.array([[r["features"][f] for f in FN] for r in records])
y = np.array([r["label"] for r in records])
n = len(y)
keys = [tuple(row) for row in X]

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

# (1) + (2): out-of-fold lookup
oof_pred = np.zeros(n)
oof_prob = np.zeros(n)
seen = np.zeros(n, dtype=bool)
for tr, te in cv.split(X, y):
    train_prob = defaultdict(list)
    for i in tr:
        train_prob[keys[i]].append(y[i])
    prior = y[tr].mean()
    for i in te:
        k = keys[i]
        if k in train_prob:
            p = np.mean(train_prob[k]); seen[i] = True
        else:
            p = prior
        oof_prob[i] = p
        oof_pred[i] = int(p >= 0.5)
overlap = seen.mean()
lookup_acc = (oof_pred == y).mean()
lookup_auc = roc_auc_score(y, oof_prob)
print(f"(1) 5-fold exact train/test vector overlap: {overlap:.4f} ({int(seen.sum())}/{n})")
print(f"(2) OUT-OF-FOLD lookup: acc={lookup_acc:.4f}  AUC={lookup_auc:.4f}")

# (3) leave-one-VECTOR-out: group by distinct vector -> test vectors never in train
uniq = {k: idx for idx, k in enumerate(dict.fromkeys(keys))}
groups = np.array([uniq[k] for k in keys])
lovo_pred = np.zeros(n)
lovo_prob = np.zeros(n)
for g in set(groups):
    te = np.where(groups == g)[0]
    tr = np.where(groups != g)[0]
    prior = y[tr].mean()          # unseen vector -> only the global prior is available
    lovo_prob[te] = prior
    lovo_pred[te] = int(prior >= 0.5)
lovo_acc = (lovo_pred == y).mean()
try:
    lovo_auc = roc_auc_score(y, lovo_prob)
except ValueError:
    lovo_auc = float("nan")
print(f"(3) leave-one-VECTOR-out lookup: acc={lovo_acc:.4f}  AUC={lovo_auc:.4f}  (n_groups={len(set(groups))})")
print(f"    majority class prior = {max(y.mean(), 1-y.mean()):.4f}")
