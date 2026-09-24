"""
x_bootstrap.py — frozen scenario-clustered bootstrap (Addendum F4 / A2).

resample scenario_id clusters WITH REPLACEMENT over ALL attempted clusters; within each
drawn cluster resample its trials with replacement; recompute the success-conditioned rate
trial-weighted. 10k resamples, seed 42, 2.5/97.5 percentile. >=10 success-contributing
clusters => clustered CI is confirmatory; else LOW-CLUSTER (descriptive-only).
Matched-scenario PAIRED resampling for the observable-minus-implicit contrast.
"""
import numpy as np

SEED = 42
N_RESAMPLE = 10000


def _rate(trials, num_key, cond_key=None):
    """Success-conditioned rate over a flat list of trial dicts.
    num_key True counts toward numerator; cond_key True selects denominator (else all)."""
    denom = [t for t in trials if (cond_key is None or t.get(cond_key))]
    if not denom:
        return None
    return sum(1 for t in denom if t.get(num_key)) / len(denom)


def kish_effective_n(sizes):
    """Effective sample size of a TRIAL-WEIGHTED proportion under total
    within-cluster dependence (intra-cluster correlation = 1), for clusters of
    UNEQUAL size: n_eff = (sum n_c)^2 / sum n_c^2.

    Why this and not the cluster count: the estimand here is the trial-weighted
    rate over success-conditioned trials, p_hat = sum(n_c * y_c) / sum(n_c). When
    the outcome is constant within a cluster, Var(p_hat) = (sum n_c^2 /
    (sum n_c)^2) * p(1-p), so the effective n is the Kish quantity above, NOT the
    number of clusters. The two coincide only when every cluster is the same
    size. The common shortcut DEFF = 1 + (mean_size - 1) * icc assumes equal
    sizes and is anti-conservative when they are skewed, which they are here
    (X1 implicit: cluster sizes 30,30,30,28,14,4,3,1,1).

    The corresponding effective cluster size to use in DEFF = 1 + (m - 1) * icc
    is m = sum n_c^2 / sum n_c (see `deff_cluster_size`), which reproduces this
    n_eff at icc = 1.
    """
    sizes = [s for s in sizes if s > 0]
    if not sizes:
        return 0.0
    total = sum(sizes)
    return (total * total) / sum(s * s for s in sizes)


def deff_cluster_size(sizes):
    """Effective cluster size m = sum n_c^2 / sum n_c for use in
    DEFF = 1 + (m - 1) * icc. Equals the arithmetic mean only for equal sizes."""
    sizes = [s for s in sizes if s > 0]
    if not sizes:
        return 0.0
    return sum(s * s for s in sizes) / sum(sizes)


def clustered_ci(trials, num_key, cond_key=None, n_resample=N_RESAMPLE, seed=SEED,
                 cluster_key="scenario_id"):
    """
    trials: list of dicts each with 'scenario_id', num_key (bool), optional cond_key (bool).
    cluster_key: field to cluster on. Defaults to 'scenario_id' (the preregistered unit).
      Pass '_eff_cluster' to cluster on the EFFECTIVE config with inert grid factors
      collapsed (see x_grid.effective_cluster_key).
    Returns dict: point, ci (lo,hi), n_clusters_total, n_clusters_contributing (>=1 denom
    member), effective_cluster_gate (bool >=10), n_denom.
    """
    by_cluster = {}
    for t in trials:
        by_cluster.setdefault(t[cluster_key], []).append(t)
    clusters = list(by_cluster.keys())
    # denominator membership per cluster
    def denom_of(cl_trials):
        return [t for t in cl_trials if (cond_key is None or t.get(cond_key))]
    contributing = [c for c in clusters if len(denom_of(by_cluster[c])) > 0]
    point = _rate(trials, num_key, cond_key)
    n_denom = sum(len(denom_of(by_cluster[c])) for c in clusters)
    rng = np.random.default_rng(seed)
    reps = []
    K = len(clusters)
    for _ in range(n_resample):
        drawn = rng.choice(K, size=K, replace=True)
        num = den = 0
        for idx in drawn:
            cl_trials = by_cluster[clusters[idx]]
            d = denom_of(cl_trials)
            if not d:
                continue
            bi = rng.integers(0, len(d), size=len(d))
            for j in bi:
                den += 1
                if d[j].get(num_key):
                    num += 1
        if den > 0:
            reps.append(num / den)
    if not reps:
        ci = (None, None)
    else:
        ci = (float(np.percentile(reps, 2.5)), float(np.percentile(reps, 97.5)))
    # Cluster-unit reporting for zero/one-event cells, where the percentile
    # bootstrap above is degenerate (every resample reproduces the boundary
    # value) and the trial-level Wilson interval assumes independence the design
    # does not supply. Two units are persisted so the paper never has to quote a
    # bound that is not in the artifact:
    #   cluster_unit_wilson  -- Wilson on the CONTRIBUTING CLUSTER count; this is
    #     the unweighted cluster-level estimand.
    #   kish_unit_wilson     -- Wilson on the Kish effective n of the
    #     TRIAL-WEIGHTED estimand at icc = 1. With unequal cluster sizes this is
    #     SMALLER than the cluster count, hence a WIDER (genuinely conservative)
    #     bound. This is the one to quote as the conservative limit.
    sizes = [len(denom_of(by_cluster[c])) for c in contributing]
    # Cluster-unit numerator: number of CONTRIBUTING CLUSTERS exhibiting the
    # outcome in at least one eligible trial. Counting trials here instead would
    # make the numerator exceed the denominator whenever a cluster contributes
    # more than one eligible trial (e.g. observable arm: 80 positive trials over
    # 10 clusters).
    n_cl = len(contributing)
    n_cl_pos = sum(1 for c in contributing
                   if any(t.get(num_key) for t in denom_of(by_cluster[c])))
    kish = kish_effective_n(sizes)
    # Scale the cluster-unit numerator onto the Kish denominator so the rate is
    # preserved; for the all-zero and all-positive cells this is exact.
    kish_pos = (n_cl_pos / n_cl * kish) if n_cl else 0.0
    return {"point": point, "ci": ci, "n_clusters_total": K,
            "n_clusters_contributing": n_cl,
            "effective_cluster_gate": n_cl >= 10, "n_denom": n_denom,
            "cluster_sizes": sorted(sizes, reverse=True),
            "n_clusters_positive": n_cl_pos,
            "cluster_unit_wilson": wilson(n_cl_pos, n_cl),
            "kish_n_eff": kish,
            "kish_unit_wilson": wilson(kish_pos, kish),
            "deff_cluster_size": deff_cluster_size(sizes)}


def paired_contrast_ci(obs_trials, imp_trials, num_key, cond_key=None,
                       n_resample=N_RESAMPLE, seed=SEED, cluster_key="scenario_id"):
    """Observable-minus-implicit rate contrast, resampling MATCHED clusters jointly.

    cluster_key defaults to the preregistered 'scenario_id'; pass '_eff_cluster' to
    match on the effective config with inert grid factors collapsed."""
    def index(trials):
        d = {}
        for t in trials:
            d.setdefault(t[cluster_key], []).append(t)
        return d
    o, i = index(obs_trials), index(imp_trials)
    shared = [s for s in o if s in i]
    def denom(cl):
        return [t for t in cl if (cond_key is None or t.get(cond_key))]
    # `shared` counts clusters ATTEMPTED in both arms. The confirmatory gate is
    # defined over SUCCESS-CONTRIBUTING clusters, so applying it to `shared`
    # would hold the contrast to a weaker standard than the per-arm cells, which
    # are gated on clusters that actually contribute eligible successes. We
    # therefore also report the number of shared clusters contributing a
    # denominator member in BOTH arms, and that is what the gate uses.
    shared_contributing = [s for s in shared if denom(o[s]) and denom(i[s])]
    def arm_rate(idx, keys):
        num = den = 0
        for s in keys:
            d = denom(idx[s])
            num += sum(1 for t in d if t.get(num_key)); den += len(d)
        return (num / den) if den else None
    po, pi = arm_rate(o, shared), arm_rate(i, shared)
    point = (po - pi) if (po is not None and pi is not None) else None
    rng = np.random.default_rng(seed)
    reps = []
    K = len(shared)
    for _ in range(n_resample):
        drawn = [shared[j] for j in rng.choice(K, size=K, replace=True)]
        no = do = ni = di = 0
        for s in drawn:
            od, idd = denom(o[s]), denom(i[s])
            if od:
                bi = rng.integers(0, len(od), size=len(od))
                do += len(od); no += sum(1 for j in bi if od[j].get(num_key))
            if idd:
                bi = rng.integers(0, len(idd), size=len(idd))
                di += len(idd); ni += sum(1 for j in bi if idd[j].get(num_key))
        if do and di:
            reps.append(no/do - ni/di)
    ci = (float(np.percentile(reps, 2.5)), float(np.percentile(reps, 97.5))) if reps else (None, None)
    return {"contrast_point": point, "contrast_ci": ci, "n_shared_clusters": K,
            "n_shared_contributing": len(shared_contributing)}


def leave_one_cluster_out(trials, num_key, cond_key=None, cluster_key="scenario_id"):
    """Range of the point rate when each cluster is dropped in turn."""
    by = {}
    for t in trials:
        by.setdefault(t[cluster_key], []).append(t)
    clusters = list(by)
    rates = []
    for drop in clusters:
        kept = [t for t in trials if t[cluster_key] != drop]
        r = _rate(kept, num_key, cond_key)
        if r is not None:
            rates.append(r)
    return {"loo_min": min(rates) if rates else None, "loo_max": max(rates) if rates else None}


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = min(1.0, max(0.0, k / n))  # guard: k may be a scaled (float) numerator
    d = 1 + z*z/n; c = (p + z*z/(2*n)) / d
    m = z * ((p*(1-p) + z*z/(4*n)) / n) ** 0.5 / d
    return (max(0.0, c - m), min(1.0, c + m))
