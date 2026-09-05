"""
Leave-One-Scenario-Family-Out Reanalysis for Paper A v4
=======================================================
Holds out each defense condition (scenario family) from training,
trains on the remaining families, and evaluates on the held-out family.
Reports per-family AUC and generalization uncertainty.

This is a stronger test than leave-one-model-out because defense conditions
alter the attack trajectory structure (Memory Sandbox removes recall tools,
Prompt Hardening produces sleeper sessions, etc.)
"""

import json
import sys
import os
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np

# Reuse the feature extractor from paper_a_classifier
sys.path.insert(0, str(Path(__file__).parent))
from paper_a_classifier import extract_features, P1_JSONL

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, recall_score, precision_score


def load_data_with_defense():
    """Load data with defense condition labels."""
    records = []
    for line in P1_JSONL.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("error"):
            continue
        attack_type = r.get("condition", {}).get("attack", {}).get("type", "")
        if attack_type != "delayed_trigger":
            continue

        model = r.get("condition", {}).get("model", {}).get("model_name", "unknown")
        defense = r.get("condition", {}).get("defense", {}).get("name", "none")
        feats = extract_features(r)
        label = int(r.get("attack_success", False))

        records.append({
            "features": feats,
            "label": label,
            "model": model,
            "defense": defense,
        })
    return records


def run_leave_one_family_out():
    """Train RF on all families except one, test on held-out family."""
    records = load_data_with_defense()
    print(f"Total records: {len(records)}")

    # Group by defense
    by_defense = defaultdict(list)
    for r in records:
        by_defense[r["defense"]].append(r)

    print(f"\nDefense families: {sorted(by_defense.keys())}")
    for d, recs in sorted(by_defense.items()):
        labels = [r["label"] for r in recs]
        print(f"  {d}: N={len(recs)}, attacks={sum(labels)}, non-attacks={len(labels)-sum(labels)}")

    # Feature names
    feat_names = sorted(records[0]["features"].keys())

    results = []
    print(f"\n{'='*70}")
    print(f"LEAVE-ONE-DEFENSE-FAMILY-OUT EVALUATION")
    print(f"{'='*70}")
    print(f"{'Held-Out Defense':<25} {'N':>5} {'AUC':>7} {'Recall':>7} {'Prec':>7} {'Atks':>5} {'NonAtk':>6}")
    print(f"{'-'*70}")

    for held_out_defense in sorted(by_defense.keys()):
        # Split
        train_recs = [r for r in records if r["defense"] != held_out_defense]
        test_recs = by_defense[held_out_defense]

        X_train = np.array([[r["features"][f] for f in feat_names] for r in train_recs])
        y_train = np.array([r["label"] for r in train_recs])
        X_test = np.array([[r["features"][f] for f in feat_names] for r in test_recs])
        y_test = np.array([r["label"] for r in test_recs])

        # Skip if only one class in test set
        if len(set(y_test)) < 2:
            auc = float('nan')
            recall = recall_score(y_test, np.ones_like(y_test)) if sum(y_test) > 0 else float('nan')
            prec = float('nan')
        else:
            # Train RF
            clf = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42)
            clf.fit(X_train, y_train)

            # Predict
            y_prob = clf.predict_proba(X_test)[:, 1]
            y_pred = (y_prob >= 0.5).astype(int)

            auc = roc_auc_score(y_test, y_prob)
            recall = recall_score(y_test, y_pred)
            prec = precision_score(y_test, y_pred, zero_division=0)

        n_atk = int(sum(y_test))
        n_nonatk = len(y_test) - n_atk

        results.append({
            "defense": held_out_defense,
            "n": len(y_test),
            "n_attacks": n_atk,
            "n_non_attacks": n_nonatk,
            "auc": auc,
            "recall": recall,
            "precision": prec,
        })

        auc_str = f"{auc:.4f}" if not np.isnan(auc) else "N/A"
        rec_str = f"{recall:.4f}" if not np.isnan(recall) else "N/A"
        prec_str = f"{prec:.4f}" if not np.isnan(prec) else "N/A"
        print(f"{held_out_defense:<25} {len(y_test):>5} {auc_str:>7} {rec_str:>7} {prec_str:>7} {n_atk:>5} {n_nonatk:>6}")

    print(f"{'-'*70}")

    # Summary statistics
    valid_aucs = [r["auc"] for r in results if not np.isnan(r["auc"])]
    if valid_aucs:
        print(f"\nSummary (families with both classes):")
        print(f"  Mean AUC: {np.mean(valid_aucs):.4f}")
        print(f"  Min AUC:  {np.min(valid_aucs):.4f} ({[r['defense'] for r in results if r['auc'] == np.min(valid_aucs)][0]})")
        print(f"  Max AUC:  {np.max(valid_aucs):.4f}")
        print(f"  Std AUC:  {np.std(valid_aucs):.4f}")

    # Also do leave-one-MODEL-out for comparison
    print(f"\n{'='*70}")
    print(f"LEAVE-ONE-MODEL-OUT (for comparison)")
    print(f"{'='*70}")

    by_model = defaultdict(list)
    for r in records:
        by_model[r["model"]].append(r)

    print(f"{'Held-Out Model':<25} {'N':>5} {'AUC':>7} {'Recall':>7}")
    print(f"{'-'*50}")

    model_aucs = []
    for held_out_model in sorted(by_model.keys()):
        train_recs = [r for r in records if r["model"] != held_out_model]
        test_recs = by_model[held_out_model]

        X_train = np.array([[r["features"][f] for f in feat_names] for r in train_recs])
        y_train = np.array([r["label"] for r in train_recs])
        X_test = np.array([[r["features"][f] for f in feat_names] for r in test_recs])
        y_test = np.array([r["label"] for r in test_recs])

        if len(set(y_test)) < 2:
            auc = float('nan')
        else:
            clf = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42)
            clf.fit(X_train, y_train)
            y_prob = clf.predict_proba(X_test)[:, 1]
            auc = roc_auc_score(y_test, y_prob)
            y_pred = (y_prob >= 0.5).astype(int)
            recall = recall_score(y_test, y_pred)

        auc_str = f"{auc:.4f}" if not np.isnan(auc) else "N/A"
        rec_str = f"{recall:.4f}" if not np.isnan(recall) else "N/A"
        print(f"{held_out_model:<25} {len(y_test):>5} {auc_str:>7} {rec_str:>7}")
        if not np.isnan(auc):
            model_aucs.append(auc)

    if model_aucs:
        print(f"\n  Mean AUC (model holdout): {np.mean(model_aucs):.4f}")
        print(f"  Min AUC:  {np.min(model_aucs):.4f}")

    # Save results
    out_path = Path(__file__).parent / "results" / "leave_one_family_out.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    run_leave_one_family_out()
