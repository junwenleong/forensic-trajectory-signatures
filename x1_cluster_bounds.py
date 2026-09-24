"""Cluster-aware upper bounds for the X1 implicit arm (orp = 0/141).

Earlier revisions reported a trial-level Wilson upper bound of 0.0265 on 0/141.
That bound assumes 141 independent Bernoulli trials, but the trials are nested in
effective configurations (12 attempted, 9 contributing eligible successes) and
`observable_read_of_poison` is a deterministic property of the delivery path
within a configuration, so the trial-level bound is anti-conservative.

This script derives the cluster structure FROM THE RAW TRIALS (it does not
hardcode cluster sizes) and reports the trial unit, the cluster unit, and a
design-effect ladder computed with the correct unequal-cluster arithmetic.

Correction in this revision: the ladder previously used
DEFF = 1 + (mean_cluster_size - 1) * icc, which assumes EQUAL cluster sizes. The
X1 implicit arm's contributing clusters are strongly unequal (30, 30, 30, 28, 14,
4, 3, 1, 1), so at icc = 1 the effective n of the trial-weighted rate is the Kish
quantity (sum n)^2 / sum n^2 = 5.36, not the cluster count 9. The conservative
limit is therefore looser than the cluster-count bound, and the earlier claim
that icc = 1 "coincides with the cluster-level bound" held only under the
equal-size assumption.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import x_bootstrap as bs  # noqa: E402
import x_grid  # noqa: E402

RESULTS = pathlib.Path(__file__).parent / "results" / "x1"
CELLS = {
    "implicit (gpt-4.1)": "x1_minja_implicit_gpt_4_1.jsonl",
    "observable (gpt-4.1)": "x1_minja_observable_gpt_4_1.jsonl",
}


def wilson_upper(k, n, z=1.96):
    if not n:
        return float("nan")
    return bs.wilson(k, n, z)[1]


def clopper_pearson_upper(k, n, alpha=0.05):
    """Two-sided-equivalent upper limit; for k=0 reduces to 1-(alpha/2)^(1/n)."""
    from scipy.stats import beta
    if n <= 0:
        return float("nan")
    if k >= n:
        return 1.0
    return float(beta.ppf(1 - alpha / 2, k + 1, n - k))


def load(fname):
    path = RESULTS / fname
    trials = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("error"):
            continue
        r["_eff_cluster"] = x_grid.effective_cluster_key(r.get("scenario_id"))
        r["_elig"] = bool(r.get("attack_success") and r.get("poison_delivered"))
        r["_orp"] = bool(r.get("observable_read_of_poison"))
        trials.append(r)
    return trials


def report(label, trials):
    elig = [t for t in trials if t["_elig"]]
    n_elig = len(elig)
    n_orp = sum(1 for t in elig if t["_orp"])
    by = {}
    for t in elig:
        by.setdefault(t["_eff_cluster"], []).append(t)
    sizes = sorted((len(v) for v in by.values()), reverse=True)
    n_cl = len(sizes)
    # cluster-unit numerator counts CLUSTERS exhibiting the outcome, not trials
    n_cl_pos = sum(1 for v in by.values() if any(t["_orp"] for t in v))
    attempted = len({t["_eff_cluster"] for t in trials})

    print(f"=== {label} ===")
    print(f"  eligible successes            : {n_orp}/{n_elig}")
    print(f"  effective configs attempted   : {attempted}")
    print(f"  effective configs contributing: {n_cl}  (exhibiting outcome: {n_cl_pos})")
    print(f"  contributing cluster sizes    : {sizes}")
    print()
    print(f"  trial unit   {n_orp}/{n_elig:<4} Wilson upper = {wilson_upper(n_orp, n_elig):.4f}"
          f"   CP upper = {clopper_pearson_upper(n_orp, n_elig):.4f}"
          f"   [anti-conservative: assumes independence]")
    print(f"  cluster unit {n_cl_pos}/{n_cl:<4} Wilson upper = {wilson_upper(n_cl_pos, n_cl):.4f}"
          f"   CP upper = {clopper_pearson_upper(n_cl_pos, n_cl):.4f}"
          f"   [unweighted cluster-level estimand]")
    print()

    m_mean = (n_elig / n_cl) if n_cl else 0.0
    m_deff = bs.deff_cluster_size(sizes)
    kish = bs.kish_effective_n(sizes)
    print(f"  mean cluster size                      m_mean = {m_mean:.2f}")
    print(f"  effective cluster size (sum n^2/sum n) m_deff = {m_deff:.2f}")
    print(f"  Kish effective n at icc=1                     = {kish:.2f}"
          f"   (cluster count = {n_cl})")
    print()
    print("  design-effect ladder, DEFF = 1 + (m_deff - 1) * icc")
    print(f"  {'icc':>5} {'DEFF':>8} {'n_eff':>8} {'Wilson upper':>13}")
    for icc in (0.0, 0.1, 0.25, 0.5, 1.0):
        deff = 1 + (m_deff - 1) * icc
        n_eff = n_elig / deff
        k_eff = n_orp / n_elig * n_eff
        print(f"  {icc:>5} {deff:>8.2f} {n_eff:>8.2f} {wilson_upper(k_eff, n_eff):>13.4f}")
    print()
    if n_orp == 0:
        print(f"  CONSERVATIVE LIMIT (icc=1, unequal clusters): {wilson_upper(0, kish):.4f}")
        print(f"  Unweighted cluster-level bound              : {wilson_upper(0, n_cl):.4f}")
        print("  The two differ because cluster sizes are unequal; the Kish figure")
        print("  is the conservative one for the trial-weighted rate the paper reports.")
    print()
    return {"n_elig": n_elig, "n_orp": n_orp, "n_clusters": n_cl,
            "n_clusters_positive": n_cl_pos,
            "attempted": attempted, "sizes": sizes,
            "trial_wilson_upper": wilson_upper(n_orp, n_elig),
            "cluster_wilson_upper": wilson_upper(n_cl_pos, n_cl),
            "deff_cluster_size": m_deff,
            "kish_n_eff": kish,
            "kish_wilson_upper": wilson_upper(n_orp / n_elig * kish if n_elig else 0, kish)}


def h2_reachability(n_orp, sizes_all_attempted, threshold=0.20):
    """How many zero-event clusters would the registered H2 bound require?

    X1_PREREG H2 requires a clustered upper bound <= 0.20. Under the cluster-unit
    convention this revision adopts, that is a statement about the number of
    zero-event clusters, so it is worth stating explicitly whether the registered
    threshold was reachable at all within the registered grid.
    """
    print("=== Registered H2 reachability (implicit arm) ===")
    print(f"  H2 requires clustered upper bound <= {threshold}")
    need = None
    for n in range(1, 60):
        if wilson_upper(0, n) <= threshold:
            need = n
            break
    for n in (9, 10, 12, 16, 17):
        print(f"    0/{n:<3} cluster-unit Wilson upper = {wilson_upper(0, n):.4f}")
    print(f"  smallest zero-event cluster count meeting {threshold}: {need}")
    print(f"  effective configs in the registered grid            : {sizes_all_attempted}")
    if need and need > sizes_all_attempted:
        print(f"  => UNREACHABLE: the grid contains only {sizes_all_attempted} effective")
        print("     configurations, so even a fully-populated implicit arm could not")
        print(f"     have met the registered <= {threshold} bound on the cluster unit.")
        print("     'One cluster short of the 10-cluster gate' is therefore a")
        print("     statement about the GATE, not about H2.")
    print()


def main():
    out = {}
    for label, fname in CELLS.items():
        out[label] = report(label, load(fname))
    impl = out["implicit (gpt-4.1)"]
    h2_reachability(impl["n_orp"], impl["attempted"])
    print("Note: for an outcome identically 0 in every cluster the intra-cluster")
    print("correlation is not identified from the data, so the icc=1 row is")
    print("reported as the conservative limit rather than as an estimate.")
    dest = pathlib.Path(__file__).parent / "results" / "x1_cluster_bounds.json"
    dest.write_text(json.dumps(out, indent=1, default=float))
    print(f"\nwrote {dest.relative_to(pathlib.Path(__file__).parent)}")


if __name__ == "__main__":
    main()
