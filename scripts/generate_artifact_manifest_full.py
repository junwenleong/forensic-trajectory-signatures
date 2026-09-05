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
               "scripts/cross_framework_preregistration.md"],
    "scripts": ["probe_v3_1.py", "probe_v3_2.py", "paper_a_classifier.py",
                "paper_a_stress_test.py", "paper_a_figures.py", "paper_a_v2_harvest.py",
                "leave_one_family_out.py", "scripts/exp_cross_framework.py",
                "scripts/exp_prospective_eval.py",
                "scripts/exp_cross_harness_holdout.py", "scripts/compute_ppv_table.py"],
    "scenario_grids": ["v3_1_scenario_grid.json"],
    "paper": ["paper.tex", "math_commands.tex", "references.bib"],
    "figures": ["figures/roc_curve.pdf", "figures/ablation.pdf",
                "figures/feature_importance.pdf", "figures/defense_stratified.pdf"],
    "results_toplevel": ["results/leave_one_family_out.json"],
}

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
    "manifest_version": "2026-09-recipient-corrected",
    "purpose": ("Complete content-hash manifest for FTS (paper_a) v4. Supersedes the "
                "2026-07-02 V2-only manifest, which omitted V3/cross-framework/prospective "
                "artifacts, the classifier, paper source, and figures."),
    "artifacts": {},
    "summary": {},
}

total_bytes = 0
counts = {}
for cat, files in CATEGORIES.items():
    manifest["artifacts"][cat] = {}
    for rel in files:
        total_bytes += add(manifest["artifacts"][cat], rel)
    counts[cat] = len(files)

# Enumerate all result data dirs dynamically (V3-1, V3-2, cross_framework, prospective_eval)
for sub in ["results/v3_1", "results/v3_2", "results/cross_framework",
            "results/prospective_eval"]:
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

# lockfile (repo-root)
lock = ROOT.parent / "requirements-lock.txt"
manifest["artifacts"]["lockfile"] = {}
if lock.exists():
    manifest["artifacts"]["lockfile"]["requirements-lock.txt"] = {
        "sha256": sha(lock), "size_bytes": lock.stat().st_size}
    total_bytes += lock.stat().st_size
    counts["lockfile"] = 1

manifest["summary"] = {
    "total_files": sum(counts.values()),
    "total_bytes": total_bytes,
    "categories": counts,
}

out = ROOT / "artifact_manifest.json"
out.write_text(json.dumps(manifest, indent=2))
print(f"Wrote {out}")
print(f"  total_files={manifest['summary']['total_files']} "
      f"total_bytes={total_bytes} ({total_bytes/1e6:.2f} MB)")
print("  categories:", json.dumps(counts))
missing = [rel for cat in manifest["artifacts"].values()
           for rel, v in cat.items() if isinstance(v, dict) and v.get("MISSING")]
if missing:
    print("  WARNING missing:", missing)
