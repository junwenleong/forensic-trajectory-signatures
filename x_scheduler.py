"""
x_scheduler.py — stratified round-robin scheduler (Addendum: end-of-block stopping).

Yields (block_idx, config) covering the full 36-config grid once per block, in a
seed-fixed shuffled order within each block. The caller runs a trial per yielded config,
then calls should_stop() at END OF BLOCK only: stop iff cumulative eligible successes >=
target OR block cap reached. No mid-block stopping -> every config gets equal exposure,
so the >=10 success-contributing-cluster gate is not biased by early-succeeding configs.
"""
import random


def blocks(grid, seed, max_blocks=10):
    """Generator of blocks; each block is the full grid in a per-block shuffled order."""
    rng = random.Random(seed)
    for b in range(max_blocks):
        order = list(grid)
        rng.shuffle(order)
        yield b, order


def run_stratified(grid, seed, target_succ, run_one, is_eligible, max_blocks=10,
                   on_trial=None, target_clusters=None, cluster_key_fn=None,
                   prior_elig=0, prior_clusters=None):
    """
    grid       : list of config dicts (each has scenario_id)
    run_one    : fn(config) -> record dict
    is_eligible: fn(record) -> bool  (eligible success for the stopping target)

    Stopping (X1 PREREG v4 AMENDMENT, 2026-09-19): stop at END of block iff
      cumulative eligible successes >= target_succ
      AND (if target_clusters is set) the number of EFFECTIVE clusters contributing
          >=1 eligible success is >= target_clusters.
    The cluster condition exists because the v3 rule could be satisfied without >=10
    effective clusters -- an inert grid factor tripled scenario_id counts. `cluster_key_fn`
    maps a config/record to its effective cluster identity (x_grid.effective_cluster_key).

    `prior_elig` / `prior_clusters` carry the ALREADY-COLLECTED totals so that a resumed
    run evaluates the criterion cumulatively rather than restarting from zero. This is what
    keeps a resume from overshooting the registered per-cell cap.

    Stopping is evaluated ONLY on (eligible successes, effective clusters) -- never on the
    estimand -- and only at end of block, so every config keeps equal exposure and the
    cluster gate is not biased by early-succeeding configs.

    Returns (records, n_blocks_run).
    """
    records = []
    elig = prior_elig
    clusters = set(prior_clusters or ())
    n_blocks = 0
    for b, order in blocks(grid, seed, max_blocks):
        n_blocks = b + 1
        for cfg in order:
            rec = run_one(cfg)
            rec["scenario_id"] = cfg["scenario_id"]
            rec["block"] = b
            rec.update({f"cfg_{k}": v for k, v in cfg.items() if k != "scenario_id"})
            records.append(rec)
            if is_eligible(rec):
                elig += 1
                if cluster_key_fn is not None:
                    clusters.add(cluster_key_fn(cfg["scenario_id"]))
            if on_trial:
                on_trial(rec, elig)
        # END OF BLOCK check only
        if elig >= target_succ:
            if target_clusters is None or len(clusters) >= target_clusters:
                break
    return records, n_blocks
