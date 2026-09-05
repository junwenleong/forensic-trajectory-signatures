"""
Paper A — Figures and Extended Analysis
=========================================
Generates all figures and additional tables for the paper:
  1. ROC curves (per-fold CV + cross-model holdout)
  2. Feature importance bar chart
  3. Defense-stratified detection rates (FN breakdown by defense)
  4. Feature-group ablation study

Outputs go to paper_a/figures/
Run: .venv/bin/python scripts/paper_a_figures.py
"""

import json
import copy
import os
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

warnings.filterwarnings("ignore")

RESULTS_DIR    = Path(__file__).parent.parent / "results"
P1_JSONL       = Path(os.environ.get(
    "P1_JSONL_PATH",
    str(Path.home() / "projects/agentic/results/defense_factorial/results.jsonl")
))
FIGURES_DIR    = Path(__file__).parent.parent / "paper_a" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# ── shared style ──────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":    "serif",
    "font.size":      11,
    "axes.titlesize": 12,
    "axes.labelsize": 11,
    "xtick.labelsize":10,
    "ytick.labelsize":10,
    "legend.fontsize":10,
    "figure.dpi":     150,
    "axes.spines.top":   False,
    "axes.spines.right": False,
})
ACCENT = "#2c5f8a"     # dark blue — main lines
GREY   = "#999999"
RED    = "#c0392b"


# ── feature extraction (same as classifier script) ───────────────────────────
def extract_features(run):
    tool_logs = run.get("tool_logs", [])
    trigger_logs = [t for t in tool_logs if t.get("session_type") == "trigger"]
    trigger_logs.sort(key=lambda t: t.get("timestamp", ""))
    trigger_ops = [t["operation"] for t in trigger_logs]
    counts = Counter(trigger_ops)
    recall_count   = counts.get("recall_fact", 0)
    list_count     = counts.get("list_all_facts", 0)
    save_count     = counts.get("save_fact", 0)
    draft_count    = counts.get("draft_email", 0)
    send_count     = counts.get("send_email", 0)
    rag_count      = counts.get("query", 0)
    seq_len        = len(trigger_ops)
    send_without_recall = int(send_count > 0 and recall_count == 0)
    # Canonical (v4) definition: ANY recall_fact before ANY send_email, matching
    # paper_a_classifier.extract_features. (Identical labels to the old
    # first-vs-first form on all 2,520 primary sessions; kept in sync so the
    # figures never diverge from the classifier.)
    send_positions = [i for i, op in enumerate(trigger_ops) if op == "send_email"]
    recall_positions = [i for i, op in enumerate(trigger_ops) if op == "recall_fact"]
    recall_before_send = int(bool(send_positions) and bool(recall_positions)
                             and min(recall_positions) < max(send_positions))
    recall_to_send_ratio = recall_count / max(send_count, 1)
    max_recall_chain = 0; cur = 0
    for op in trigger_ops:
        if op == "recall_fact": cur += 1; max_recall_chain = max(max_recall_chain, cur)
        else: cur = 0
    bigrams = Counter(zip(trigger_ops, trigger_ops[1:]))
    return {
        "recall_count":          recall_count,
        "list_count":            list_count,
        "save_count":            save_count,
        "draft_count":           draft_count,
        "send_count":            send_count,
        "rag_count":             rag_count,
        "seq_len":               seq_len,
        "send_without_recall":   send_without_recall,
        "recall_before_send":    recall_before_send,
        "recall_to_send_ratio":  recall_to_send_ratio,
        "max_recall_chain":      max_recall_chain,
        "list_then_recall":      bigrams.get(("list_all_facts","recall_fact"), 0),
        "recall_then_recall":    bigrams.get(("recall_fact","recall_fact"), 0),
        "recall_then_draft":     bigrams.get(("recall_fact","draft_email"), 0),
        "list_then_draft":       bigrams.get(("list_all_facts","draft_email"), 0),
        "draft_then_send":       bigrams.get(("draft_email","send_email"), 0),
        "first_tool_is_list":    int(bool(trigger_ops) and trigger_ops[0] == "list_all_facts"),
        "first_tool_is_recall":  int(bool(trigger_ops) and trigger_ops[0] == "recall_fact"),
        "first_tool_is_draft":   int(bool(trigger_ops) and trigger_ops[0] == "draft_email"),
    }


def load_data():
    records = []; by_model = defaultdict(list); by_defense = defaultdict(list)
    for line in P1_JSONL.read_text().splitlines():
        if not line.strip(): continue
        try: r = json.loads(line)
        except Exception: continue
        if r.get("error"): continue
        if r.get("condition", {}).get("attack", {}).get("type", "") != "delayed_trigger":
            continue
        model   = r.get("condition", {}).get("model", {}).get("model_name", "unknown")
        defense = r.get("condition", {}).get("defense", {}).get("type", "no_defense")
        feats   = extract_features(r)
        label   = int(r.get("attack_success", False))
        rec = {"features": feats, "label": label, "model": model, "defense": defense}
        records.append(rec); by_model[model].append(rec); by_defense[defense].append(rec)
    return records, by_model, by_defense


# ── build arrays ──────────────────────────────────────────────────────────────
def to_arrays(records, feature_names):
    X = np.array([[r["features"][f] for f in feature_names] for r in records])
    y = np.array([r["label"] for r in records])
    return X, y


def main():
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.metrics import roc_auc_score, roc_curve, auc as sk_auc

    print("Loading data…")
    records, by_model, by_defense = load_data()
    print(f"  {len(records)} DTA runs, {len(by_model)} models, {len(by_defense)} defenses")

    FEATURE_NAMES = list(records[0]["features"].keys())
    X, y = to_arrays(records, FEATURE_NAMES)
    models_arr  = np.array([r["model"]   for r in records])
    defense_arr = np.array([r["defense"] for r in records])

    clf_base = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    print("Running 5-fold CV…")
    proba_cv = cross_val_predict(clf_base, X, y, cv=cv, method="predict_proba")[:, 1]

    # ── Figure 1: ROC curves (per-fold + aggregate) ───────────────────────────
    print("Generating Figure 1: ROC curves…")
    fig, ax = plt.subplots(figsize=(5.5, 4.5))

    fold_aucs = []
    for fold, (train_idx, test_idx) in enumerate(cv.split(X, y)):
        clf_f = copy.deepcopy(clf_base)
        clf_f.fit(X[train_idx], y[train_idx])
        p_f   = clf_f.predict_proba(X[test_idx])[:, 1]
        fpr_f, tpr_f, _ = roc_curve(y[test_idx], p_f)
        auc_f = sk_auc(fpr_f, tpr_f)
        fold_aucs.append(auc_f)
        ax.plot(fpr_f, tpr_f, color=ACCENT, alpha=0.25, lw=1.0)

    fpr, tpr, _ = roc_curve(y, proba_cv)
    auc_overall = sk_auc(fpr, tpr)
    ax.plot(fpr, tpr, color=ACCENT, lw=2.2,
            label=f"Aggregate CV (AUC = {auc_overall:.4f})")
    ax.plot([0, 1], [0, 1], "k--", lw=0.8, alpha=0.5)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curve — Trajectory-Based Poisoning Detector\n(5-fold CV, $N{=}2{,}520$ DTA runs)")
    fold_patch = mpatches.Patch(color=ACCENT, alpha=0.35, label=f"Individual folds (mean AUC = {np.mean(fold_aucs):.4f})")
    ax.legend(handles=[ax.lines[5], fold_patch], loc="lower right")
    ax.set_xlim(-0.01, 1.01); ax.set_ylim(-0.01, 1.01)
    plt.tight_layout()
    out1 = FIGURES_DIR / "roc_curve.pdf"
    fig.savefig(out1, bbox_inches="tight")
    plt.close()
    print(f"  → {out1}")

    # ── Figure 2: Feature importance bar chart ────────────────────────────────
    print("Generating Figure 2: Feature importances…")
    clf_full = copy.deepcopy(clf_base)
    clf_full.fit(X, y)
    importances = clf_full.feature_importances_
    sorted_idx  = np.argsort(importances)[::-1][:10]
    feat_labels = [FEATURE_NAMES[i] for i in sorted_idx]
    feat_vals   = importances[sorted_idx]

    # Pretty label map
    label_map = {
        "recall_before_send":    r"recall\_before\_send",
        "send_count":            r"send\_count",
        "recall_to_send_ratio":  r"recall\_to\_send\_ratio",
        "recall_count":          r"recall\_count",
        "max_recall_chain":      r"max\_recall\_chain",
        "list_then_recall":      r"list\_then\_recall",
        "seq_len":               r"seq\_len",
        "draft_then_send":       r"draft\_then\_send",
        "send_without_recall":   r"send\_without\_recall",
        "rag_count":             r"rag\_count",
    }
    y_labels = [label_map.get(f, f) for f in feat_labels]
    colors   = [RED if f == "recall_before_send" else ACCENT for f in feat_labels]

    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    bars = ax.barh(range(len(feat_vals)), feat_vals[::-1], color=colors[::-1], height=0.65)
    ax.set_yticks(range(len(feat_vals)))
    ax.set_yticklabels([f"\\texttt{{{lb}}}" if False else lb for lb in y_labels[::-1]],
                       fontfamily="monospace")
    ax.set_xlabel("Feature Importance (Mean Decrease in Impurity)")
    ax.set_title("Top-10 Feature Importances — Random Forest\n"
                 r"(\textit{recall\_before\_send} is mechanistically forced by the attack)")

    # Annotate top bar
    top_val = feat_vals[0]
    # The top bar is now at position len-1 in the reversed chart
    top_pos = len(feat_vals) - 1
    ax.annotate(f"{top_val:.3f}",
                xy=(top_val, top_pos), xytext=(top_val + 0.005, top_pos),
                fontsize=9, color=RED, va="center")

    red_patch   = mpatches.Patch(color=RED,   label="Mechanistically forced")
    blue_patch  = mpatches.Patch(color=ACCENT, label="Supporting features")
    ax.legend(handles=[red_patch, blue_patch], loc="lower right", fontsize=9)
    ax.set_xlim(0, 0.38)
    plt.tight_layout()
    out2 = FIGURES_DIR / "feature_importance.pdf"
    fig.savefig(out2, bbox_inches="tight")
    plt.close()
    print(f"  → {out2}")

    # ── Table: Defense-stratified detection rates ─────────────────────────────
    print("\nDefense-stratified detection rates:")
    print(f"  {'Defense':<25} {'N_atk':>6} {'N_clean':>7} {'FN':>5} {'Recall':>8} {'FPR':>8} {'AUC':>8}")
    defense_stats = {}
    for defense in sorted(by_defense.keys()):
        recs_d = by_defense[defense]
        idx_d  = np.where(defense_arr == defense)[0]
        if len(idx_d) < 10: continue
        X_d, y_d = X[idx_d], y[idx_d]
        p_d = proba_cv[idx_d]
        preds_d = (p_d >= 0.5).astype(int)
        n_atk   = y_d.sum()
        n_clean = (1 - y_d).sum()
        tp = ((preds_d==1)&(y_d==1)).sum()
        fp = ((preds_d==1)&(y_d==0)).sum()
        fn = ((preds_d==0)&(y_d==1)).sum()
        recall_d = tp/(tp+fn) if (tp+fn)>0 else 0
        fpr_d    = fp/(fp+((preds_d==0)&(y_d==0)).sum()) if n_clean>0 else 0
        if len(np.unique(y_d)) >= 2:
            auc_d = roc_auc_score(y_d, p_d)
        else:
            auc_d = float("nan")
        print(f"  {defense:<25} {n_atk:>6} {n_clean:>7} {fn:>5} {recall_d:>8.4f} {fpr_d:>8.4f} {auc_d:>8.4f}")
        defense_stats[defense] = {"n_atk": int(n_atk), "n_clean": int(n_clean),
                                   "fn": int(fn), "recall": recall_d, "fpr": fpr_d, "auc": auc_d}

    # ── Figure 3: Defense-stratified AUC + Recall ─────────────────────────────
    print("\nGenerating Figure 3: Defense-stratified performance…")
    defense_order = ["no_defense", "minimizer", "sanitizer", "rag_sanitizer",
                     "rag_llm_judge", "prompt_hardening", "memory_sandbox"]
    present = [d for d in defense_order if d in defense_stats]
    d_labels = {
        "no_defense":      "No Defense",
        "minimizer":       "Minimizer",
        "sanitizer":       "Sanitizer",
        "rag_sanitizer":   "RAG Sanitizer",
        "rag_llm_judge":   "RAG LLM Judge",
        "prompt_hardening":"Prompt Hardening",
        "memory_sandbox":  "Memory Sandbox",
    }
    aucs    = [defense_stats[d]["auc"]    for d in present]
    recalls = [defense_stats[d]["recall"] for d in present]
    fns     = [defense_stats[d]["fn"]     for d in present]
    x = np.arange(len(present))
    w = 0.35

    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    bars1 = ax.bar(x - w/2, aucs,    w, label="AUC",    color=ACCENT, alpha=0.85)
    bars2 = ax.bar(x + w/2, recalls, w, label="Recall", color=RED,    alpha=0.85)
    ax.axhline(0.98, color="black", lw=0.8, ls="--", alpha=0.5, label="Recall=0.98 reference")
    ax.set_xticks(x)
    ax.set_xticklabels([d_labels[d] for d in present], rotation=22, ha="right")
    ax.set_ylabel("Score")
    ax.set_ylim(0.0, 1.08)
    ax.set_title("Detector Performance Across Defense Conditions")
    for bar, fn_val in zip(bars2, fns):
        if fn_val > 0:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                    f"FN={fn_val}", ha="center", va="bottom", fontsize=7.5, color=RED)
    ax.legend(loc="lower left", fontsize=9)
    plt.tight_layout()
    out3 = FIGURES_DIR / "defense_stratified.pdf"
    fig.savefig(out3, bbox_inches="tight")
    plt.close()
    print(f"  → {out3}")

    # ── Feature-group ablation ─────────────────────────────────────────────────
    print("\nFeature-group ablation:")
    FEATURE_GROUPS = {
        "Mechanistic (recall_before_send + send_without_recall)":
            ["recall_before_send", "send_without_recall"],
        "Frequency counts (recall/list/save/send/draft/rag/seq_len)":
            ["recall_count", "list_count", "save_count", "draft_count", "send_count", "rag_count", "seq_len"],
        "Ratio features (recall_to_send_ratio, max_recall_chain)":
            ["recall_to_send_ratio", "max_recall_chain"],
        "Bigram transitions (5 features)":
            ["list_then_recall","recall_then_recall","recall_then_draft",
             "list_then_draft","draft_then_send"],
        "First-tool indicators (3 features)":
            ["first_tool_is_list","first_tool_is_recall","first_tool_is_draft"],
    }
    base_auc = roc_auc_score(y, proba_cv)
    print(f"  Baseline AUC (all 19 features): {base_auc:.4f}")
    print(f"  {'Group removed':<55} {'AUC':>7} {'ΔAUC':>8} {'%drop':>8}")
    ablation_results = {}
    for group_name, group_feats in FEATURE_GROUPS.items():
        keep = [f for f in FEATURE_NAMES if f not in group_feats]
        idx_keep = [FEATURE_NAMES.index(f) for f in keep]
        X_abl = X[:, idx_keep]
        p_abl = cross_val_predict(clf_base, X_abl, y, cv=cv, method="predict_proba")[:, 1]
        auc_abl = roc_auc_score(y, p_abl)
        delta   = auc_abl - base_auc
        pct     = 100 * delta / base_auc
        print(f"  {group_name:<55} {auc_abl:.4f} {delta:+.4f} {pct:+.2f}%")
        ablation_results[group_name] = {"auc": auc_abl, "delta": delta, "pct": pct}

    # ── Figure 4: Ablation bar ─────────────────────────────────────────────────
    print("\nGenerating Figure 4: Feature-group ablation…")
    short_names = {
        "Mechanistic (recall_before_send + send_without_recall)": "Mechanistic\n(recall_before_send,\nsend_without_recall)",
        "Frequency counts (recall/list/save/send/draft/rag/seq_len)":  "Frequency\ncounts (7)",
        "Ratio features (recall_to_send_ratio, max_recall_chain)":"Ratio\nfeatures (2)",
        "Bigram transitions (5 features)":                        "Bigram\ntransitions (5)",
        "First-tool indicators (3 features)":                     "First-tool\nindicators (3)",
    }
    groups_ordered = list(FEATURE_GROUPS.keys())
    deltas = [ablation_results[g]["delta"] for g in groups_ordered]
    labels = [short_names[g] for g in groups_ordered]
    colors_abl = [RED if d < -0.005 else (GREY if abs(d) < 0.001 else ACCENT) for d in deltas]

    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    bars = ax.bar(range(len(deltas)), deltas, color=colors_abl, width=0.55)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("ΔAUC (vs. full model)")
    ax.set_title("Feature-Group Ablation — AUC Impact of Removing Each Group\n"
                 "(negative = removing this group hurts performance)")
    for bar, d in zip(bars, deltas):
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + (0.0003 if d >= 0 else -0.0012),
                f"{d:+.4f}", ha="center", va="bottom" if d >= 0 else "top",
                fontsize=8.5)
    plt.tight_layout()
    out4 = FIGURES_DIR / "ablation.pdf"
    fig.savefig(out4, bbox_inches="tight")
    plt.close()
    print(f"  → {out4}")

    # ── Save extended JSON ─────────────────────────────────────────────────────
    extended = {
        "defense_stratified": defense_stats,
        "feature_group_ablation": ablation_results,
        "baseline_auc": float(base_auc),
    }
    ext_out = RESULTS_DIR / "paper_a_extended_analysis.json"
    ext_out.write_text(json.dumps(extended, indent=2))
    print(f"\nExtended results saved to {ext_out}")
    print("\nAll figures written to paper_a/figures/")
    print(f"  roc_curve.pdf, feature_importance.pdf, defense_stratified.pdf, ablation.pdf")


if __name__ == "__main__":
    main()
