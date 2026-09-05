"""
Paper A Stress Test — "Break My Paper" Audit
=============================================
Runs all adversarial checks from the audit feedback:
1. Trivial baseline: does `recall_before_send == 1` alone match RF AUC?
2. Clean session activity: are clean sessions just idle agents?
3. Feature ablation: drop recall_before_send, what happens?
4. Operational framing: is recall_before_send post-hoc (time-travel)?
5. Expanded frontier validation: use all probe2 trajectory data
"""

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, recall_score, accuracy_score
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).parent))
from paper_a_classifier import extract_features, extract_features_from_sequence, P1_JSONL

RESULTS_DIR = Path(__file__).parent.parent / "results"
FEATURE_NAMES = [
    "recall_count", "list_count", "save_count", "draft_count", "send_count",
    "rag_count", "seq_len", "send_without_recall", "recall_before_send",
    "recall_to_send_ratio", "max_recall_chain", "list_then_recall",
    "recall_then_recall", "recall_then_draft", "list_then_draft",
    "draft_then_send", "first_tool_is_list", "first_tool_is_recall",
    "first_tool_is_draft",
]


def load_data():
    """Load Agentic factorial data and extract features."""
    runs = []
    for line in P1_JSONL.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("error"):
            continue
        # Only DTA runs
        attack_type = r.get("condition", {}).get("attack", {}).get("type", "")
        if attack_type != "delayed_trigger":
            continue
        runs.append(r)

    features, labels, models, defenses = [], [], [], []
    for r in runs:
        f = extract_features(r)
        features.append([f[k] for k in FEATURE_NAMES])
        labels.append(int(r.get("attack_success", False)))
        models.append(r.get("condition", {}).get("model", {}).get("model_name", "unknown"))
        defenses.append(r.get("condition", {}).get("defense", {}).get("type", "none"))
    return np.array(features), np.array(labels), np.array(models), np.array(defenses)


def check1_trivial_baseline(X, y):
    """Is `recall_before_send == 1` alone a perfect classifier?"""
    print("\n" + "="*70)
    print("CHECK 1: TRIVIAL BASELINE — Single-rule vs RF")
    print("="*70)

    rbs_idx = FEATURE_NAMES.index("recall_before_send")
    rbs = X[:, rbs_idx]

    # Simple rule: predict attack if recall_before_send == 1
    rule_preds = (rbs == 1).astype(int)
    rule_acc = accuracy_score(y, rule_preds)
    rule_recall = recall_score(y, rule_preds)
    # For AUC, use the binary feature as the score
    rule_auc = roc_auc_score(y, rbs)

    # RF with all features (5-fold CV)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    rf_proba = np.zeros(len(y))
    for train_idx, test_idx in skf.split(X, y):
        clf = RandomForestClassifier(n_estimators=200, max_depth=8,
                                     class_weight="balanced", random_state=42)
        clf.fit(X[train_idx], y[train_idx])
        rf_proba[test_idx] = clf.predict_proba(X[test_idx])[:, 1]
    rf_auc = roc_auc_score(y, rf_proba)
    rf_recall = recall_score(y, (rf_proba >= 0.5).astype(int))

    # RF with ONLY recall_before_send
    single_proba = np.zeros(len(y))
    for train_idx, test_idx in skf.split(X, y):
        clf = RandomForestClassifier(n_estimators=200, max_depth=8,
                                     class_weight="balanced", random_state=42)
        clf.fit(X[train_idx, rbs_idx:rbs_idx+1], y[train_idx])
        single_proba[test_idx] = clf.predict_proba(X[test_idx, rbs_idx:rbs_idx+1])[:, 1]
    single_auc = roc_auc_score(y, single_proba)
    single_recall = recall_score(y, (single_proba >= 0.5).astype(int))

    print(f"\n  Simple rule (if recall_before_send == 1 → attack):")
    print(f"    AUC    = {rule_auc:.4f}")
    print(f"    Recall = {rule_recall:.4f}")
    print(f"    Acc    = {rule_acc:.4f}")
    print(f"\n  RF with ONLY recall_before_send:")
    print(f"    AUC    = {single_auc:.4f}")
    print(f"    Recall = {single_recall:.4f}")
    print(f"\n  RF with ALL 19 features:")
    print(f"    AUC    = {rf_auc:.4f}")
    print(f"    Recall = {rf_recall:.4f}")
    print(f"\n  ΔAUC (full RF - single rule): {rf_auc - rule_auc:+.4f}")
    print(f"  ΔAUC (full RF - single-feat RF): {rf_auc - single_auc:+.4f}")

    if rf_auc - rule_auc < 0.005:
        print("\n  ⚠️  WARNING: Full RF barely beats the trivial rule.")
        print("     The paper is effectively a one-feature detector wrapped in ML.")
        print("     This is NOT necessarily fatal — but framing must acknowledge it.")
    else:
        print(f"\n  ✓ Full RF meaningfully outperforms single rule (Δ={rf_auc - rule_auc:+.4f})")

    return {"rule_auc": rule_auc, "single_rf_auc": single_auc, "full_rf_auc": rf_auc}


def check2_clean_session_activity(X, y, models):
    """Are clean sessions just 'agents doing nothing'?"""
    print("\n" + "="*70)
    print("CHECK 2: CLEAN SESSION ACTIVITY — Are clean sessions idle?")
    print("="*70)

    seq_len_idx = FEATURE_NAMES.index("seq_len")
    send_idx = FEATURE_NAMES.index("send_count")
    draft_idx = FEATURE_NAMES.index("draft_count")
    list_idx = FEATURE_NAMES.index("list_count")

    poisoned = y == 1
    clean = y == 0

    print(f"\n  {'Metric':<30} {'Poisoned (N={int(poisoned.sum())})':<25} {'Clean (N={int(clean.sum())})':<25}")
    print(f"  {'-'*80}")

    for name, idx in [("seq_len (total tools)", seq_len_idx),
                      ("send_count", send_idx),
                      ("draft_count", draft_idx),
                      ("list_count", list_idx)]:
        p_mean = X[poisoned, idx].mean()
        c_mean = X[clean, idx].mean()
        p_std = X[poisoned, idx].std()
        c_std = X[clean, idx].std()
        print(f"  {name:<30} {p_mean:.2f} ± {p_std:.2f}          {c_mean:.2f} ± {c_std:.2f}")

    # Critical check: what fraction of clean sessions have seq_len == 0?
    clean_empty = (X[clean, seq_len_idx] == 0).sum()
    clean_no_send = (X[clean, send_idx] == 0).sum()
    print(f"\n  Clean sessions with seq_len == 0: {clean_empty}/{int(clean.sum())} ({clean_empty/clean.sum()*100:.1f}%)")
    print(f"  Clean sessions with send_count == 0: {clean_no_send}/{int(clean.sum())} ({clean_no_send/clean.sum()*100:.1f}%)")

    if clean_empty / clean.sum() > 0.5:
        print("\n  ⚠️  WARNING: >50% of clean sessions have zero tool activity.")
        print("     Classifier may be detecting 'activity vs inactivity', not attack signature.")
    elif X[clean, seq_len_idx].mean() < 2.0:
        print("\n  ⚠️  WARNING: Clean sessions average <2 tool calls.")
        print("     The baseline may be unrealistically idle.")
    else:
        print(f"\n  ✓ Clean sessions are active (mean seq_len={X[clean, seq_len_idx].mean():.2f})")
        print(f"    Clean sessions ARE doing work — not trivially idle.")


def check3_ablation_recall_before_send(X, y):
    """Drop recall_before_send entirely. What happens to AUC?"""
    print("\n" + "="*70)
    print("CHECK 3: ABLATION — Drop recall_before_send")
    print("="*70)

    rbs_idx = FEATURE_NAMES.index("recall_before_send")

    # Also drop send_without_recall (it's the inverse)
    swr_idx = FEATURE_NAMES.index("send_without_recall")

    # Full model
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    full_proba = np.zeros(len(y))
    for train_idx, test_idx in skf.split(X, y):
        clf = RandomForestClassifier(n_estimators=200, max_depth=8,
                                     class_weight="balanced", random_state=42)
        clf.fit(X[train_idx], y[train_idx])
        full_proba[test_idx] = clf.predict_proba(X[test_idx])[:, 1]
    full_auc = roc_auc_score(y, full_proba)

    # Drop recall_before_send only
    drop_rbs = np.delete(X, rbs_idx, axis=1)
    rbs_proba = np.zeros(len(y))
    for train_idx, test_idx in skf.split(drop_rbs, y):
        clf = RandomForestClassifier(n_estimators=200, max_depth=8,
                                     class_weight="balanced", random_state=42)
        clf.fit(drop_rbs[train_idx], y[train_idx])
        rbs_proba[test_idx] = clf.predict_proba(drop_rbs[test_idx])[:, 1]
    rbs_auc = roc_auc_score(y, rbs_proba)

    # Drop both mechanistic features (recall_before_send + send_without_recall)
    drop_both = np.delete(X, sorted([rbs_idx, swr_idx])[::-1], axis=1)
    both_proba = np.zeros(len(y))
    for train_idx, test_idx in skf.split(drop_both, y):
        clf = RandomForestClassifier(n_estimators=200, max_depth=8,
                                     class_weight="balanced", random_state=42)
        clf.fit(drop_both[train_idx], y[train_idx])
        both_proba[test_idx] = clf.predict_proba(drop_both[test_idx])[:, 1]
    both_auc = roc_auc_score(y, both_proba)

    # Drop ALL recall-related features
    recall_features = ["recall_before_send", "send_without_recall", "recall_count",
                       "recall_to_send_ratio", "max_recall_chain", "recall_then_recall",
                       "recall_then_draft", "list_then_recall", "first_tool_is_recall"]
    recall_idxs = sorted([FEATURE_NAMES.index(f) for f in recall_features], reverse=True)
    drop_all_recall = np.delete(X, recall_idxs, axis=1)
    all_recall_proba = np.zeros(len(y))
    for train_idx, test_idx in skf.split(drop_all_recall, y):
        clf = RandomForestClassifier(n_estimators=200, max_depth=8,
                                     class_weight="balanced", random_state=42)
        clf.fit(drop_all_recall[train_idx], y[train_idx])
        all_recall_proba[test_idx] = clf.predict_proba(drop_all_recall[test_idx])[:, 1]
    all_recall_auc = roc_auc_score(y, all_recall_proba)

    print(f"\n  Full model (19 features):                    AUC = {full_auc:.4f}")
    print(f"  Drop recall_before_send (18 features):       AUC = {rbs_auc:.4f}  (ΔAUC = {rbs_auc - full_auc:+.4f})")
    print(f"  Drop both mechanistic (17 features):         AUC = {both_auc:.4f}  (ΔAUC = {both_auc - full_auc:+.4f})")
    print(f"  Drop ALL recall-related (10 features):       AUC = {all_recall_auc:.4f}  (ΔAUC = {all_recall_auc - full_auc:+.4f})")

    if rbs_auc - full_auc > -0.01:
        print(f"\n  ✓ Graceful degradation. Removing recall_before_send barely hurts.")
        print(f"    Signature is overdetermined — other features compensate.")
    elif all_recall_auc > 0.90:
        print(f"\n  ✓ Even without ALL recall features, AUC > 0.90.")
        print(f"    Signal exists in non-recall features (send patterns, bigrams).")
    else:
        print(f"\n  ⚠️  AUC collapses when recall features are removed.")
        print(f"     Paper is essentially a single-mechanism detector.")


def check4_operational_framing(X, y):
    """Is recall_before_send computed post-hoc? Does it require seeing send_email first?"""
    print("\n" + "="*70)
    print("CHECK 4: OPERATIONAL FRAMING — Time-travel check")
    print("="*70)

    print("""
  Feature definition from code (v4):
    recall_before_send = 1 iff ANY recall_fact occurs before ANY send_email
    (min(recall_positions) < max(send_positions)) in the trigger session.

  This checks temporal ordering of recall relative to send within the session.

  Question: Does computing this require seeing the FULL session (including send)?
  Answer: YES. This feature is a POST-HOC indicator.

  It CANNOT be used as a real-time gate to block send_email BEFORE it happens,
  because you need to know send_email occurred to set the feature to 1.

  HOWEVER: The paper claims "State-Space IDS" (forensic, not inline).
  For forensic analysis of completed sessions (audit logs), this is valid.

  Verification: Could we build a CAUSAL (pre-send) version?
    causal_recall_before_send = int(recall_count > 0)  (at time of send)
  This is computable BEFORE send_email fires — but it's just recall_count > 0.
  Let's check if recall_count > 0 alone achieves similar performance.
""")

    recall_idx = FEATURE_NAMES.index("recall_count")
    causal_feature = (X[:, recall_idx] > 0).astype(float)
    causal_auc = roc_auc_score(y, causal_feature)

    rbs_idx = FEATURE_NAMES.index("recall_before_send")
    posthoc_auc = roc_auc_score(y, X[:, rbs_idx])

    print(f"  Post-hoc recall_before_send (requires seeing send): AUC = {posthoc_auc:.4f}")
    print(f"  Causal recall_count > 0 (available before send):    AUC = {causal_auc:.4f}")
    print(f"  Difference: {causal_auc - posthoc_auc:+.4f}")

    if abs(causal_auc - posthoc_auc) < 0.01:
        print(f"\n  ✓ Causal version performs equally well.")
        print(f"    A real-time gate could fire on recall_count > 0 before send.")
        print(f"    No time-travel issue for inline deployment.")
    else:
        print(f"\n  The post-hoc version benefits from seeing send_email.")
        print(f"  Paper framing as 'forensic IDS' is correct and necessary.")
        print(f"  DO NOT claim real-time blocking with this specific feature.")


def check5_expanded_frontier(X, y):
    """Validate on all available probe2 data, not just N=20."""
    print("\n" + "="*70)
    print("CHECK 5: EXPANDED FRONTIER VALIDATION")
    print("="*70)

    # Train full RF on Agentic data
    clf = RandomForestClassifier(n_estimators=200, max_depth=8,
                                 class_weight="balanced", random_state=42)
    clf.fit(X, y)

    # Find all probe2 trajectory files that have call_sequence
    probe2_files = sorted(RESULTS_DIR.glob("p2_*.jsonl"))
    print(f"\n  Found {len(probe2_files)} probe2 result files")

    # Filter for files with attack_success and call_sequence
    total_attack = 0
    total_detected = 0
    total_clean = 0
    total_fp = 0
    model_results = {}

    for f in probe2_files:
        recs = []
        for line in f.read_text().splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "call_sequence" in r and "attack_success" in r:
                recs.append(r)
        if not recs:
            continue

        # Extract features
        Xv = np.array([[extract_features_from_sequence(r["call_sequence"])[feat]
                        for feat in FEATURE_NAMES] for r in recs])
        yv = np.array([int(r["attack_success"]) for r in recs])
        proba = clf.predict_proba(Xv)[:, 1]
        preds = (proba >= 0.5).astype(int)

        n_atk = int(yv.sum())
        n_clean = int((1-yv).sum())
        tp = int(((preds==1)&(yv==1)).sum())
        fp = int(((preds==1)&(yv==0)).sum())
        fn = int(((preds==0)&(yv==1)).sum())

        if n_atk > 0:
            total_attack += n_atk
            total_detected += tp
        if n_clean > 0:
            total_clean += n_clean
            total_fp += fp

        # Collect per-model if the file has model info
        model = recs[0].get("model", f.stem)
        if model not in model_results:
            model_results[model] = {"n_atk": 0, "tp": 0, "n_clean": 0, "fp": 0}
        model_results[model]["n_atk"] += n_atk
        model_results[model]["tp"] += tp
        model_results[model]["n_clean"] += n_clean
        model_results[model]["fp"] += fp

    overall_recall = total_detected / total_attack if total_attack > 0 else 0
    overall_fpr = total_fp / total_clean if total_clean > 0 else 0

    print(f"\n  Aggregate frontier validation:")
    print(f"    Total attack sessions:  {total_attack}")
    print(f"    Detected (TP):          {total_detected}")
    print(f"    Missed (FN):            {total_attack - total_detected}")
    print(f"    Recall:                 {overall_recall:.4f}")
    print(f"    Total clean sessions:   {total_clean}")
    print(f"    False positives:        {total_fp}")
    print(f"    FPR:                    {overall_fpr:.4f}")

    # Top models with most data
    print(f"\n  Per-model breakdown (top by N):")
    sorted_models = sorted(model_results.items(), key=lambda x: x[1]["n_atk"], reverse=True)
    print(f"  {'Model':<45} {'N_atk':>6} {'TP':>5} {'Recall':>8} {'N_clean':>7} {'FP':>4}")
    for model, d in sorted_models[:15]:
        r = d["tp"]/d["n_atk"] if d["n_atk"] > 0 else float("nan")
        print(f"  {model:<45} {d['n_atk']:>6} {d['tp']:>5} {r:>8.3f} {d['n_clean']:>7} {d['fp']:>4}")


def main():
    print("Paper A Stress Test — 'Break My Paper' Audit")
    print("=" * 70)
    print("Loading Agentic factorial data...")
    X, y, models, defenses = load_data()
    print(f"  N={len(y)}, attacks={y.sum()}, clean={(1-y).sum()}")
    print(f"  Models: {len(np.unique(models))}, Defenses: {len(np.unique(defenses))}")

    results = {}
    results["check1"] = check1_trivial_baseline(X, y)
    check2_clean_session_activity(X, y, models)
    check3_ablation_recall_before_send(X, y)
    check4_operational_framing(X, y)
    check5_expanded_frontier(X, y)

    print("\n" + "="*70)
    print("STRESS TEST COMPLETE")
    print("="*70)


if __name__ == "__main__":
    main()
