import numpy as np

# Inputs from the paper (existing numbers, no new data):
# TPR (recall) among attack-success sessions:
#   in-distribution 5-fold: 0.9838; leave-one-model-out: ~1.0 on 6/9 models;
#   cross-harness holdout (this run): 0.989. Use 0.98 as a representative recall.
TPR = 0.98

# Benign FPR: the paper's V2-1 benign study. Two regimes:
#   unconditional benign FPR: 24.7% (best cell) .. 57.6% (worst, k=1)
#   conditional on recall_before_send=1: ~100%
# We tabulate PPV across a realistic FPR range that brackets these.
FPRs = [0.01, 0.05, 0.10, 0.247, 0.40, 0.576, 1.00]

# Realistic attack prevalences (base rate of memory-poisoning among monitored sessions).
# Memory-poisoning is RARE in production traffic; span optimistic->pessimistic.
prevalences = [0.0001, 0.001, 0.01, 0.05, 0.10]

def ppv(tpr, fpr, pi):
    num = tpr * pi
    den = tpr * pi + fpr * (1 - pi)
    return num / den if den > 0 else float("nan")

print(f"PPV table (TPR={TPR:.2f} fixed; rows=benign FPR, cols=attack prevalence pi)\n")
hdr = "FPR \\ pi   " + "".join(f"{p:>10}" for p in prevalences)
print(hdr)
for fpr in FPRs:
    row = f"{fpr:>8.3f}   " + "".join(f"{ppv(TPR,fpr,p)*100:>9.2f}%" for p in prevalences)
    print(row)

print("\nInterpretation anchors:")
for fpr,label in [(0.247,"best benign cell"),(0.576,"worst benign cell k=1"),(1.00,"conditional on rbs=1")]:
    print(f"  FPR={fpr:.3f} ({label}):")
    for p in [0.001,0.01,0.10]:
        print(f"    pi={p:<6}: PPV={ppv(TPR,fpr,p)*100:6.2f}%  (alerts per true positive = {1/ppv(TPR,fpr,p):.1f})")
