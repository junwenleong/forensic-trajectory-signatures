import json, glob, os, sys
from pathlib import Path
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paper_a_classifier import extract_features, extract_features_from_sequence

FEATS = ["recall_count","list_count","save_count","draft_count","send_count","rag_count",
    "seq_len","send_without_recall","recall_before_send","recall_to_send_ratio","max_recall_chain",
    "list_then_recall","recall_then_recall","recall_then_draft","list_then_draft","draft_then_send",
    "first_tool_is_list","first_tool_is_recall","first_tool_is_draft"]

# --- TRAIN: LangGraph/SQLite factorial (the FTS training harness) ---
P1 = Path.home()/"projects/agentic/results/defense_factorial/results.jsonl"
Xtr, ytr = [], []
for l in P1.read_text().splitlines():
    if not l.strip(): continue
    try: r=json.loads(l)
    except: continue
    if r.get("error"): continue
    if r.get("condition",{}).get("attack",{}).get("type","")!="delayed_trigger": continue
    f=extract_features(r)
    Xtr.append([f[k] for k in FEATS]); ytr.append(int(r.get("attack_success",False)))
Xtr, ytr = np.array(Xtr), np.array(ytr)
print(f"TRAIN (LangGraph harness): N={len(ytr)} attacks={int(ytr.sum())}")

# Frozen classifier spec: must match paper_a_classifier.py exactly (no class_weight).
# The paper describes this as "we froze that classifier and applied it without retraining";
# the estimator hyperparameters must therefore be identical to the trained artifact.
clf = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42)
clf.fit(Xtr, ytr)

# --- TEST: raw-OpenAI-loop cross_framework harness (out-of-harness) ---
# Use corrected v4 labels; attack condition only.
def score_file(fn, label_field="attack_success_v4"):
    rows=[json.loads(l) for l in open(fn) if l.strip()]
    rows=[r for r in rows if r.get("condition")=="attack" and not r.get("error")]
    if not rows: return None
    X=np.array([[extract_features_from_sequence(r.get("call_sequence",[]))[k] for k in FEATS] for r in rows])
    y=np.array([int(r.get(label_field, r.get("attack_success",False))) for r in rows])
    proba=clf.predict_proba(X)[:,1]; preds=(proba>=0.5).astype(int)
    n=len(rows); natk=int(y.sum())
    tp=int(((preds==1)&(y==1)).sum()); fn=int(((preds==0)&(y==1)).sum())
    recall=tp/(tp+fn) if (tp+fn)>0 else float("nan")
    auc=roc_auc_score(y,proba) if len(np.unique(y))>1 else float("nan")
    return n,natk,recall,auc,proba[y==1].mean() if natk>0 else float("nan")

print("\nTEST (raw-OpenAI-loop cross_framework harness, v4 labels):")
print(f"{'file':<40} {'N':>4} {'atk':>4} {'recall':>7} {'AUC':>7} {'mean_p(atk)':>11}")
tot_tp=tot_atk=0; all_proba=[]; all_y=[]
_CF_DIR = Path(__file__).resolve().parent.parent / "results" / "cross_framework"
for fn in sorted(glob.glob(str(_CF_DIR / "*_attack.jsonl"))):
    res=score_file(fn)
    if not res: continue
    n,natk,recall,auc,mp=res
    print(f"{os.path.basename(fn):<40} {n:>4} {natk:>4} {recall:>7.3f} {auc if auc==auc else float('nan'):>7.3f} {mp:>11.3f}")
    # pooled recall among attack-success
    rows=[json.loads(l) for l in open(fn) if l.strip()]
    rows=[r for r in rows if r.get("condition")=="attack" and not r.get("error")]
    X=np.array([[extract_features_from_sequence(r.get("call_sequence",[]))[k] for k in FEATS] for r in rows])
    y=np.array([int(r.get("attack_success_v4", r.get("attack_success",False))) for r in rows])
    p=clf.predict_proba(X)[:,1]
    tot_tp+=int(((p>=0.5)&(y==1)).sum()); tot_atk+=int(y.sum())
    all_proba+=list(p); all_y+=list(y)
print(f"\nPOOLED cross-harness recall (v4-attack-success sessions): {tot_tp}/{tot_atk} = {tot_tp/tot_atk:.3f}")
