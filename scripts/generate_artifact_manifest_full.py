#!/usr/bin/env python3
"""Generate v4 artifact manifest for FTS (paper_a).

v4 correction (F8): the previous artifact_manifest.json (2026-07-02) covered only
V2-1 + probe10 files and omitted every load-bearing artifact behind the v4 claims.
This regenerates a complete content-hash manifest over: preregistrations, all
experiment/analysis scripts, V3-1/V3-2/cross-framework/prospective data, the
classifier, paper source, figures, and the lockfile.
"""
import hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CATEGORIES = {
    "prereg": ["V2_1_PREREG.md", "V3_1_PREREG.md", "V3_2_PREREG.md",
               "V3_3_PREREG.md", "V3_4_PREREG.md", "V3_5_PREREG.md",
               "scripts/cross_framework_preregistration.md",
               # X-program + B+ (added 2026-09-19; the v4 manifest omitted all of these
               # even though the v5 headline claims rest on them)
               "X1_PREREG.md", "X2_PREREG.md", "X3_NOTE.md", "X4_PREREG.md",
               "X5_ADAPTIVE_PREREG.md", "X6_BREADTH_PREREG.md", "BPLUS_PREREG.md",
               # V3-6/V3-6b (added -- were omitted from every prior generator revision
               # even though the committed artifact_manifest.json has always included
               # them, so running this generator could not reproduce the shipped manifest)
               "V3_6_PREREG.md", "V3_6B_PREREG.md",
               # v1.3 instrumentation amendment (GPG-signed BEFORE the 2026-09-19
               # B+ re-collection; see results/bplus/legacy_2026-09-11/ for the
               # superseded records it supersedes)
               "BPLUS_PREREG_v1_3_AMENDMENT.md",
               "PROGRAM_EXECUTION_ADDENDUM.md"],
    "scripts": ["probe_v3_1.py", "probe_v3_2.py", "probe_v3_3.py", "probe_v3_4.py",
                "probe_v3_5.py", "pilot_v3_3_asr.py", "paper_a_classifier.py",
                "paper_a_stress_test.py", "paper_a_figures.py", "paper_a_v2_harvest.py",
                "leave_one_family_out.py", "reanalysis_prereg_completion.py",
                "trace_v2_1_fpr.py", "bench_ct_cd.py",
                "exp_13a_gpt4o_armB_fresh.py", "exp_13c_save_provenance.py",
                "exp_format_confound.py",
                "scripts/exp_cross_framework.py",
                "scripts/exp_prospective_eval.py",
                "scripts/exp_cross_harness_holdout.py", "scripts/compute_ppv_table.py",
                # X-program probes, shared harness modules, scorer and validators
                "probe_x1.py", "probe_x2.py", "probe_x3_topk.py", "probe_x4.py",
                "probe_x5.py", "probe_x6.py", "probe_bplus.py",
                "x_grid.py", "x_content.py", "x_bootstrap.py", "x_scheduler.py",
                "score_xprogram.py", "validate_all.py", "build_manifest.py",
                "verify_frozen_rf.py",
                "purge_errors.py", "make_results_summary.py",
                "reanalysis_confounders.py", "reanalysis_implicit_bypass.py",
                # Self-audit correction scripts. The version note tells readers to
                # regenerate this revision's restated intervals with these four; the
                # previous manifest omitted all of them, so the hashed tree could not
                # reproduce the corrections that define the revision.
                "x1_cluster_bounds.py", "x4_cluster_bounds.py",
                "recompute_recall_ci.py", "bca_jackknife_sensitivity.py",
                # Secondary metrics that the paper cited with no producing script in the
                # hashed tree (single-rule baseline; the 13- and 14-feature pre-send
                # variants), plus an explicit record of the absent probe2 inputs.
                "emit_secondary_metrics.py",
                # Third self-audit pass: the two scripts that produce the corrections
                # defining this pass. Without them the hashed tree cannot reproduce the
                # measured provenance coverage or the uniform zero-event bounds.
                "emit_provenance_coverage.py", "necessity_cluster_bounds.py",
                "run_pipeline.sh", "run_macstudio_queue.sh",
                # V3-6/V3-6b probes+scorers and the changelog extractor (added -- same
                # omission as the preregs above: present in the committed manifest since
                # V3-6 shipped, never in this generator's list). conformance.py and
                # check_conformance.py are NOT listed here -- they belong exclusively
                # under the dedicated "conformance" category below, matching the
                # committed manifest.
                "probe_v3_6.py", "score_v3_6.py", "probe_v3_6b.py", "score_v3_6b.py",
                "extract_changelog.py"],
    "scenario_grids": ["v3_1_scenario_grid.json", "MECHANISM_MANIFEST.json"],
    "paper": ["paper.tex", "math_commands.tex", "references.bib"],
    "figures": ["figures/roc_curve.pdf", "figures/ablation.pdf",
                "figures/feature_importance.pdf", "figures/defense_stratified.pdf"],
    "results_toplevel": ["results/leave_one_family_out.json",
                         "results/reanalysis_prereg_completion.json",
                         "results/bench_ct_cd.json",
                         "results/xprogram_scored.json",
                         "results/x3_topk_scored.json",
                         # cluster-unit bounds emitted by the correction scripts, so
                         # the paper never quotes a bound absent from the artifact
                         "results/x1_cluster_bounds.json",
                         "results/x4_cluster_bounds.json",
                         # frozen estimator + the equivalence test that licenses
                         # describing E3 as a frozen-RF false-positive rate
                         "results/frozen_rf.joblib",
                         "results/frozen_rf_verification.json",
                         # emitted by emit_secondary_metrics.py
                         "results/secondary_metrics.json",
                         # third self-audit pass: measured git-provenance coverage
                         # replacing the false global claim, and the one-rule
                         # recomputation of every zero-event necessity cell
                         "results/provenance_coverage.json",
                         "results/necessity_cluster_bounds.json",
                         "results/RESULTS_DIGEST.md"],
    "correction_record": ["CHANGELOG.md"],
    "conformance": ["conformance.py", "check_conformance.py"],
}

# Raw-trial result directories walked recursively (hash every JSONL/JSON found).
# v3_6/v3_6b used to be built through a dedicated bare-filename loop (removed
# 2026-09-25) whose keys omitted their directory component, so every consumer that
# resolves ROOT / key -- prepare_public_release.py included -- looked for them at
# the repo root instead of under results/v3_6/ or results/v3_6b/ and silently
# skipped them. Routing them through RESULT_DIRS gives them the same full-relative-
# path keys as every other raw-trial directory, with no special-case code left to
# drift out of sync again.
RESULT_DIRS = [
    "results/v3_1", "results/v3_2", "results/cross_framework",
    "results/prospective_eval", "results/v3_3", "results/v3_4",
    "results/v3_5", "results/v3_1_saveprov", "results/v3_fmt",
    "results/v3_3_pilot",
    # X-program + B+ raw trials (added 2026-09-19)
    "results/x1", "results/x2", "results/x4", "results/x5", "results/x6",
    "results/bplus",
    # superseded/pilot trees retained for provenance
    "results/x1_v2_pilot", "results/x4_v2_pilot", "results/x4_detbug_v1",
    "results/x5_buggy_v1", "results/x6_buggy_v1",
    "results/v3_2_k2", "results/v3_2_k8",
    # V3-6 / V3-6b (added 2026-09-25, folded in from the removed bare-filename loop)
    "results/v3_6", "results/v3_6b",
]

def sha(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()

def add(d, rel):
    p = ROOT / rel
    if not p.exists():
        d[rel] = {"MISSING": True}
        return 0
    d[rel] = {"sha256": sha(p), "size_bytes": p.stat().st_size}
    return p.stat().st_size

manifest = {
    "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "manifest_version": "2026-09-25-v10-unify-v36-result-dirs",
    "purpose": ("Complete content-hash manifest for FTS (paper_a). Hashes every paper_a "
                "script, result file, figure and preregistration, and names (without "
                "vendoring) the two external inputs: the P1 factorial JSONL that trains "
                "the classifier and the V2-1 benign corpus that drives the deployment-FPR "
                "and PPV analyses; see external_dependencies below for their recorded "
                "digests. v9 fixes a generator/manifest parity gap: V3_6_PREREG.md, "
                "V3_6B_PREREG.md, probe_v3_6(.py|b.py), score_v3_6(.py|b.py), "
                "conformance.py, check_conformance.py, extract_changelog.py, and the "
                "correction_record/conformance/results_v3_6/results_v3_6b categories were "
                "present in every committed manifest since V3-6 shipped but absent from "
                "every prior revision of this generator, so running it could not "
                "reproduce the manifest it claims to regenerate. v7 had added the four "
                "self-audit correction scripts and emit_secondary_metrics.py; v6 had "
                "added the X-program and B+ artifacts omitted by v4/v5. v10 folds the "
                "results_v3_6/results_v3_6b categories into RESULT_DIRS (renamed "
                "data_v3_6/data_v3_6b) so their keys are full relative paths like every "
                "other raw-trial directory: v9 put the files in the manifest but kept "
                "their old bare-filename keys, which is why prepare_public_release.py "
                "still could not locate them under results/v3_6/ or results/v3_6b/ and "
                "skipped all eight as absent. No other reader of this manifest depended "
                "on the bare-name keys (checked before this change)."),
    "artifacts": {},
    "summary": {},
}

total_bytes = 0
counts = {}
for cat, files in CATEGORIES.items():
    manifest["artifacts"][cat] = {}
    if isinstance(files, dict):
        # results_v3_6 / results_v3_6b: key is a bare filename (matching the committed
        # manifest's convention for this category), value is the actual repo-relative
        # path used to locate and hash the file.
        for key, relpath in files.items():
            p = ROOT / relpath
            if not p.exists():
                manifest["artifacts"][cat][key] = {"MISSING": True}
            else:
                sz = p.stat().st_size
                manifest["artifacts"][cat][key] = {"sha256": sha(p), "size_bytes": sz}
                total_bytes += sz
        counts[cat] = len(files)
    else:
        for rel in files:
            total_bytes += add(manifest["artifacts"][cat], rel)
        counts[cat] = len(files)

# Enumerate all result data dirs dynamically (V3, cross_framework, prospective_eval,
# and -- added 2026-09-19 -- the full X-program and B+ raw-trial trees)
for sub in RESULT_DIRS:
    d = ROOT / sub
    if not d.is_dir():
        continue
    cat = "data_" + sub.split("/")[-1]
    manifest["artifacts"][cat] = {}
    n = 0
    for p in sorted(d.rglob("*")):
        if p.is_file() and p.suffix in (".jsonl", ".json", ".npz") and not p.name.endswith(".lock"):
            rel = str(p.relative_to(ROOT))
            total_bytes += add(manifest["artifacts"][cat], rel)
            n += 1
    counts[cat] = n

# lockfile (repo-root) -- prefer the newest dated lock
lock = ROOT.parent / "requirements-lock-2026-09-08.txt"
if not lock.exists():
    lock = ROOT.parent / "requirements-lock.txt"
manifest["artifacts"]["lockfile"] = {}
if lock.exists():
    manifest["artifacts"]["lockfile"][lock.name] = {
        "sha256": sha(lock), "size_bytes": lock.stat().st_size}
    total_bytes += lock.stat().st_size
    counts["lockfile"] = 1

manifest["summary"] = {
    "total_files": sum(counts.values()),
    "total_bytes": total_bytes,
    "categories": counts,
}

# ---- external dependencies -------------------------------------------------------
# The manifest's purpose statement says it "names the two external inputs". Naming
# them in prose is not enough to detect a swap, so record their digests here when
# they are resolvable on this machine. They are deliberately NOT vendored (the P1
# corpus alone is ~120 MB and belongs to the companion repository), so an absent
# path is recorded as unresolved rather than treated as an error.
EXTERNAL = {
    "p1_factorial_jsonl": {
        "role": "classifier training corpus (2,520 DTA runs)",
        "released_in": "companion repository stateful-agent-security-eval",
        "local_path_env": "P1_JSONL_PATH",
        # Portable hint only. The absolute resolution path is used to compute the digest
        # but is NOT written to the manifest: earlier revisions published the generating
        # machine's home-directory path, which leaks a local filesystem layout into a
        # public artifact and is useless to anyone else. Consumers set the env var above.
        "path_hint": "$P1_JSONL_PATH, default ~/projects/agentic/results/defense_factorial/results.jsonl",
        "_resolve": os.environ.get(
            "P1_JSONL_PATH",
            str(Path.home() / "projects/agentic/results/defense_factorial/results.jsonl")),
    },
    "v2_1_benign_corpus": {
        "role": "benign deployment-FPR and PPV analyses",
        "released_in": "companion program, paper_1_behavioral/results/",
        "local_path_env": "V2_1_RESULTS_DIR",
        "path_hint": "$V2_1_RESULTS_DIR, default <repo>/paper_1_behavioral/results",
        "_resolve": os.environ.get(
            "V2_1_RESULTS_DIR",
            str(ROOT.parent / "paper_1_behavioral" / "results")),
    },
}
for name, spec in EXTERNAL.items():
    p = Path(spec.pop("_resolve"))
    if p.is_file():
        spec["sha256"] = sha(p)
        spec["size_bytes"] = p.stat().st_size
    elif p.is_dir():
        # directory: hash the sorted (relative path, digest) listing so the whole
        # tree is pinned by one value
        h = hashlib.sha256()
        n_files = 0
        for q in sorted(p.rglob("*")):
            if q.is_file() and q.suffix in (".jsonl", ".json"):
                h.update(str(q.relative_to(p)).encode())
                h.update(sha(q).encode())
                n_files += 1
        spec["tree_sha256"] = h.hexdigest()
        spec["n_files_hashed"] = n_files
    else:
        spec["unresolved"] = True
        spec["note"] = "not present on the generating machine; digest not recorded"
manifest["external_dependencies"] = EXTERNAL

out = ROOT / "artifact_manifest.json"
out.write_text(json.dumps(manifest, indent=2))
print(f"Wrote {out}")
print(f"  total_files={manifest['summary']['total_files']} "
      f"total_bytes={total_bytes} ({total_bytes/1e6:.2f} MB)")
print("  categories:", json.dumps(counts))
for name, spec in EXTERNAL.items():
    state = ("unresolved" if spec.get("unresolved")
             else spec.get("sha256", spec.get("tree_sha256", "?"))[:16])
    print(f"  external {name}: {state}")
missing = [rel for cat in manifest["artifacts"].values()
           for rel, v in cat.items() if isinstance(v, dict) and v.get("MISSING")]
if missing:
    print("  WARNING missing:", missing)
