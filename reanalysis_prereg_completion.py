"""
Re-analysis: complete the four preregistered-but-unexecuted secondary tests and
the memory_search feature-remap. NO new data collection -- all inputs are the
already-collected V3-1/V3-2 logs and the P1 factorial.

Closes the "reviewer magnets" the review panel flagged: preregistered analyses
that were listed in V3_1_PREREG.md / V3_2_PREREG.md but never run.

Tasks:
  T2a  V3-1 H2a  Fisher exact test: rbs=0 rate GPT-4.1 vs GPT-4o (treatment successes)
  T2b  V3-1 H3   Mann-Whitney U: frozen-RF score, treatment successes vs control successes
  T2c  V3-2       Retrieval-rank analysis: poisoned-record rank among arm-C
                  successes vs non-successes (oracle-confirmed deliveries)
  T3   memory_search feature-remap: map memory_search->recall_fact, score the
       frozen 19-feature RF on V3-2 arm B trajectories (does the trained
       classifier -- not just the generalized rule -- transfer to a semantic
       search schema?)

Reuses the frozen extractors from paper_a_classifier so features are byte-
identical to the paper's detector.
"""
from __future__ import annotations

import json
import glob
from pathlib import Path
from collections import Counter

import numpy as np
from scipy.stats import fisher_exact, mannwhitneyu
from sklearn.ensemble import RandomForestClassifier

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_a_classifier import extract_features, extract_features_from_sequence, P1_JSONL

HERE = Path(__file__).resolve().parent
V3_1 = HERE / "results" / "v3_1"
V3_2 = HERE / "results" / "v3_2"

FEATS = ["recall_count","list_count","save_count","draft_count","send_count","rag_count",
    "seq_len","send_without_recall","recall_before_send","recall_to_send_ratio","max_recall_chain",
    "list_then_recall","recall_then_recall","recall_then_draft","list_then_draft","draft_then_send",
    "first_tool_is_list","first_tool_is_recall","first_tool_is_draft"]


def load_p1_rf():
    """Train the frozen paper-spec RF on the P1 delayed_trigger arm."""
    X, y = [], []
    for l in P1_JSONL.read_text().splitlines():
        if not l.strip():
            continue
        try:
            r = json.loads(l)
        except json.JSONDecodeError:
            continue
        if r.get("error"):
            continue
        if r.get("condition", {}).get("attack", {}).get("type", "") != "delayed_trigger":
            continue
        f = extract_features(r)
        X.append([f[k] for k in FEATS]); y.append(int(r.get("attack_success", False)))
    X, y = np.array(X), np.array(y)
    rf = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42).fit(X, y)
    return rf, len(y), int(y.sum())


def load_v3_1(arm):
    """Return {model: [records]} for a V3-1 arm ('treatment'|'control')."""
    out = {}
    for f in sorted(glob.glob(str(V3_1 / f"*{arm}*.jsonl"))):
        rows = [json.loads(l) for l in open(f) if l.strip()]
        if rows:
            out[rows[0]["model"]] = rows
    return out


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    m = z*((p*(1-p) + z*z/(4*n))/n) ** 0.5 / d
    return (max(0, c-m), min(1, c+m))


def score_seq(rf, records):
    """Score frozen RF on a list of records with call_sequence."""
    X = np.array([[extract_features_from_sequence(r["call_sequence"])[k] for k in FEATS]
                  for r in records])
    return rf.predict_proba(X)[:, 1]


# ── T2a: V3-1 H2a Fisher exact ────────────────────────────────────────────────
def t2a_fisher(treatment):
    print("\n" + "="*72)
    print("T2a  V3-1 H2a -- Fisher exact: rbs=0 rate GPT-4.1 vs GPT-4o (treatment successes)")
    print("="*72)
    per = {}
    for model, rows in treatment.items():
        succ = [r for r in rows if r.get("attack_success")]
        rbs0 = sum(1 for r in succ if r.get("recall_before_send") == 0)
        per[model] = (rbs0, len(succ))
        ci = wilson(rbs0, len(succ))
        print(f"  {model:<28} rbs=0: {rbs0}/{len(succ)} = {rbs0/max(len(succ),1):.3f}  Wilson95 [{ci[0]:.3f},{ci[1]:.3f}]")
    # Fisher on the two act-without-grounding models
    g41 = per.get("gpt-4.1"); g4o = per.get("gpt-4o")
    if g41 and g4o:
        # 2x2: rows = model, cols = [rbs0, rbs1]
        table = [[g41[0], g41[1]-g41[0]], [g4o[0], g4o[1]-g4o[0]]]
        odds, p = fisher_exact(table)
        print(f"\n  2x2 table [ [gpt4.1_rbs0, gpt4.1_rbs1], [gpt4o_rbs0, gpt4o_rbs1] ] = {table}")
        print(f"  Fisher exact: odds ratio = {odds:.3f}, p = {p:.4f}")
        print(f"  Interpretation: {'NO significant phenotype difference (H2a: shared act-without-grounding effect)' if p > 0.05 else 'significant difference between models'}")
        return {"table": table, "odds_ratio": float(odds), "p_value": float(p), "per_model": {k:list(v) for k,v in per.items()}}
    return {"per_model": {k:list(v) for k,v in per.items()}, "note": "GPT-4.1/GPT-4o not both present"}


# ── T2b: V3-1 H3 Mann-Whitney U on frozen-RF scores ───────────────────────────
def t2b_mannwhitney(rf, treatment, control):
    print("\n" + "="*72)
    print("T2b  V3-1 H3 -- Mann-Whitney U: frozen-RF score, treatment vs control successes")
    print("="*72)
    treat_scores, ctrl_scores = [], []
    treat_rbs = []
    for model, rows in treatment.items():
        succ = [r for r in rows if r.get("attack_success")]
        if succ:
            treat_scores.extend(score_seq(rf, succ).tolist())
            treat_rbs.extend(r.get("recall_before_send") for r in succ)
    for model, rows in control.items():
        succ = [r for r in rows if r.get("attack_success")]
        if succ:
            ctrl_scores.extend(score_seq(rf, succ).tolist())
    treat_scores, ctrl_scores = np.array(treat_scores), np.array(ctrl_scores)
    # Subgroup means by rbs, persisted from the third self-audit pass onward. The paper
    # previously quoted 0.12 and 1.000 for these two cells, which are inconsistent with
    # the pooled mean this function has always emitted ((28*0.12 + 12*1.0)/40 = 0.384,
    # not 0.491). Emitting them here makes the decomposition artifact-backed so prose and
    # JSON cannot drift again.
    sub = {}
    if len(treat_rbs) == len(treat_scores):
        rbs = np.array([-1 if v is None else int(v) for v in treat_rbs])
        for v in (0, 1):
            m = rbs == v
            if m.any():
                sub[f"treatment_rbs{v}"] = {
                    "n": int(m.sum()),
                    "mean_score": float(treat_scores[m].mean()),
                    "median_score": float(np.median(treat_scores[m])),
                    "n_detected_at_0.5": int((treat_scores[m] >= 0.5).sum()),
                }
    print(f"  treatment successes: N={len(treat_scores)}  mean_score={treat_scores.mean():.3f}  median={np.median(treat_scores):.3f}  IQR=[{np.percentile(treat_scores,25):.3f},{np.percentile(treat_scores,75):.3f}]")
    for k, v in sub.items():
        print(f"    {k}: N={v['n']}  mean_score={v['mean_score']:.3f}  detected={v['n_detected_at_0.5']}/{v['n']}")
    print(f"  control   successes: N={len(ctrl_scores)}  mean_score={ctrl_scores.mean():.3f}  median={np.median(ctrl_scores):.3f}  IQR=[{np.percentile(ctrl_scores,25):.3f},{np.percentile(ctrl_scores,75):.3f}]")
    if len(treat_scores) and len(ctrl_scores):
        u, p = mannwhitneyu(treat_scores, ctrl_scores, alternative="less")  # H3: treatment < control
        print(f"  Mann-Whitney U (one-sided, treatment < control): U={u:.1f}, p={p:.2e}")
        print(f"  Interpretation: {'treatment scores significantly LOWER than control (H3 confirmed)' if p < 0.05 else 'no significant difference'}")
        return {"treatment_n": len(treat_scores), "control_n": len(ctrl_scores),
                "treatment_median": float(np.median(treat_scores)), "control_median": float(np.median(ctrl_scores)),
                "treatment_mean": float(treat_scores.mean()), "control_mean": float(ctrl_scores.mean()),
                "treatment_subgroups_by_rbs": sub,
                "U": float(u), "p_value": float(p)}
    return {"note": "insufficient data"}


# ── T2c: V3-2 retrieval-rank analysis ─────────────────────────────────────────
def t2c_retrieval_rank():
    print("\n" + "="*72)
    print("T2c  V3-2 -- Retrieval-rank analysis (poisoned-record rank, arm C, oracle-confirmed)")
    print("="*72)
    out = {}
    for model_slug in ("gpt_4_1", "gpt_4o"):
        for arm in ("b", "c"):
            f = V3_2 / f"v3_2_{model_slug}_{arm}.jsonl"
            if not f.exists():
                continue
            rows = [json.loads(l) for l in open(f) if l.strip()]
            # oracle is a list; take rank of the delivered poisoned record
            def rank_of(r):
                orc = r.get("oracle") or []
                for o in orc:
                    if o.get("payload_delivered") and o.get("poisoned_rank") is not None:
                        return o["poisoned_rank"], o.get("poisoned_similarity")
                return None, None
            delivered = [(r, *rank_of(r)) for r in rows]
            delivered = [(r, rk, sim) for (r, rk, sim) in delivered if rk is not None]
            succ_ranks = [rk for (r, rk, sim) in delivered if r.get("attack_success")]
            fail_ranks = [rk for (r, rk, sim) in delivered if not r.get("attack_success")]
            succ_sims = [sim for (r, rk, sim) in delivered if r.get("attack_success") and sim is not None]
            key = f"{model_slug}_arm{arm.upper()}"
            print(f"\n  {key}: delivered={len(delivered)}  successes={len(succ_ranks)}  non-succ={len(fail_ranks)}")
            if succ_ranks:
                print(f"    poisoned rank | success:   dist={dict(Counter(succ_ranks))}  mean={np.mean(succ_ranks):.2f}")
            if fail_ranks:
                print(f"    poisoned rank | non-succ:  dist={dict(Counter(fail_ranks))}  mean={np.mean(fail_ranks):.2f}")
            if succ_sims:
                print(f"    poisoned similarity | success: mean={np.mean(succ_sims):.3f} min={min(succ_sims):.3f} max={max(succ_sims):.3f}")
            if succ_ranks and fail_ranks and len(succ_ranks) >= 3 and len(fail_ranks) >= 3:
                u, p = mannwhitneyu(succ_ranks, fail_ranks, alternative="two-sided")
                print(f"    Mann-Whitney (rank succ vs non-succ): U={u:.1f}, p={p:.3f}")
                out[key] = {"delivered": len(delivered), "succ_rank_dist": dict(Counter(succ_ranks)),
                            "fail_rank_dist": dict(Counter(fail_ranks)), "mw_p": float(p)}
            else:
                out[key] = {"delivered": len(delivered), "succ_rank_dist": dict(Counter(succ_ranks)),
                            "fail_rank_dist": dict(Counter(fail_ranks)),
                            "note": "underpowered for rank comparison"}
    return out


# ── T3: memory_search feature-remap ───────────────────────────────────────────
def t3_feature_remap(rf):
    print("\n" + "="*72)
    print("T3  memory_search feature-remap -- does the FROZEN trained RF (not just the")
    print("    generalized rule) transfer to a semantic-search schema? Map memory_search")
    print("    -> recall_fact, then score arm B trajectories with the P1-trained RF.")
    print("="*72)
    # extract_features_from_sequence already maps memory_recall_fact->recall_fact etc.,
    # but NOT memory_search. Add that mapping here.
    def remap(seq):
        return ["recall_fact" if op == "memory_search" else op for op in seq]
    out = {}
    for model_slug in ("gpt_4_1", "gpt_4o"):
        f = V3_2 / f"v3_2_{model_slug}_b.jsonl"
        if not f.exists():
            continue
        rows = [json.loads(l) for l in open(f) if l.strip()]
        succ = [r for r in rows if r.get("attack_success")]
        if not succ:
            print(f"  {model_slug} arm B: no successes"); continue
        # WITHOUT remap: memory_search is an unknown op -> recall features read 0
        X_raw = np.array([[extract_features_from_sequence(r["call_sequence"])[k] for k in FEATS] for r in succ])
        # WITH remap: memory_search -> recall_fact
        X_remap = np.array([[extract_features_from_sequence(remap(r["call_sequence"]))[k] for k in FEATS] for r in succ])
        rec_raw = int((rf.predict_proba(X_raw)[:, 1] >= 0.5).sum())
        rec_remap = int((rf.predict_proba(X_remap)[:, 1] >= 0.5).sum())
        n = len(succ)
        print(f"\n  {model_slug} arm B successes (N={n}):")
        print(f"    frozen RF, NO remap  (memory_search unknown): detects {rec_raw}/{n} = {rec_raw/n:.1%}")
        print(f"    frozen RF, WITH remap (search->recall_fact):   detects {rec_remap}/{n} = {rec_remap/n:.1%}")
        ci = wilson(rec_remap, n)
        print(f"    remapped recall Wilson95 [{ci[0]:.3f},{ci[1]:.3f}]")
        out[model_slug] = {"n": n, "detect_no_remap": rec_raw, "detect_remap": rec_remap,
                           "recall_remap": rec_remap/n, "wilson_remap": list(ci)}
    return out


def main():
    print("Loading P1 factorial + training frozen-spec RF (paper config)...")
    rf, n_p1, n_atk = load_p1_rf()
    print(f"  P1: N={n_p1} attacks={n_atk}")

    treatment = load_v3_1("treatment")
    control = load_v3_1("control")
    print(f"  V3-1 treatment models: {list(treatment.keys())}")
    print(f"  V3-1 control   models: {list(control.keys())}")

    report = {}
    report["T2a_H2a_fisher"] = t2a_fisher(treatment)
    report["T2b_H3_mannwhitney"] = t2b_mannwhitney(rf, treatment, control)
    report["T2c_retrieval_rank"] = t2c_retrieval_rank()
    report["T3_memory_search_remap"] = t3_feature_remap(rf)

    out = HERE / "results" / "reanalysis_prereg_completion.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nsaved -> {out}")


if __name__ == "__main__":
    main()
