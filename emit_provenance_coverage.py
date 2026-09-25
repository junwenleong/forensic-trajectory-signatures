"""Measure, rather than assert, the git-provenance coverage of the released trial records.

The paper previously said "All experiments record exact package versions, git commit
hashes, and run manifests." That is false of the released tree, and the third self-audit
pass replaces it with the measured figures this script emits. It walks every raw JSONL
under paper_a/results/ and reports, per collection:

  * how many records carry a git SHA at all;
  * how many of those SHAs are `-dirty` (i.e. the working tree had uncommitted edits, so
    the exact code is not recoverable from the commit alone);
  * how many distinct SHAs appear within a single file (a mid-collection resume-after-edit);
  * whether prompt_hash / tool_schema_hash are constant where SHAs vary, which is the
    guard that bounds the consequence.

Writes results/provenance_coverage.json.

Usage: .venv/bin/python paper_a/emit_provenance_coverage.py
"""
from __future__ import annotations

import collections
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
RESULTS = HERE / "results"

SHA_KEYS = ("git_sha", "git_commit")
GUARD_KEYS = ("prompt_hash", "tool_schema_hash")


def collection_of(rel: str) -> str:
    """Group files into the collections the paper names."""
    parts = pathlib.PurePath(rel).parts
    return parts[0] if len(parts) > 1 else "(top level)"


def main() -> int:
    per_file: dict[str, dict] = {}
    totals = collections.Counter()
    shas_global: collections.Counter = collections.Counter()

    for f in sorted(RESULTS.rglob("*.jsonl")):
        rel = str(f.relative_to(RESULTS))
        n = n_sha = n_dirty = 0
        shas: collections.Counter = collections.Counter()
        guards = {k: collections.Counter() for k in GUARD_KEYS}
        for line in f.open(errors="replace"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(r, dict):
                continue
            n += 1
            sha = next((r[k] for k in SHA_KEYS if r.get(k)), None)
            if sha:
                n_sha += 1
                shas[str(sha)] += 1
                shas_global[str(sha)] += 1
                if str(sha).endswith("-dirty"):
                    n_dirty += 1
            for k in GUARD_KEYS:
                if r.get(k):
                    guards[k][str(r[k])] += 1
        totals["records"] += n
        totals["records_with_sha"] += n_sha
        totals["records_dirty"] += n_dirty
        totals["files"] += 1
        if n_sha:
            totals["files_with_sha"] += 1
        per_file[rel] = {
            "collection": collection_of(rel),
            "n_records": n,
            "n_with_sha": n_sha,
            "n_dirty": n_dirty,
            "distinct_shas": dict(shas),
            "n_distinct_shas": len(shas),
            "guard_hashes_constant": {
                k: (len(guards[k]) == 1) for k in GUARD_KEYS if guards[k]
            },
        }

    by_collection: dict[str, dict] = {}
    for rel, d in per_file.items():
        c = by_collection.setdefault(
            d["collection"],
            {"n_records": 0, "n_with_sha": 0, "n_dirty": 0, "files": 0,
             "files_with_sha": 0, "shas": set()})
        c["n_records"] += d["n_records"]
        c["n_with_sha"] += d["n_with_sha"]
        c["n_dirty"] += d["n_dirty"]
        c["files"] += 1
        if d["n_with_sha"]:
            c["files_with_sha"] += 1
        c["shas"].update(d["distinct_shas"])
    for c in by_collection.values():
        c["shas"] = sorted(c["shas"])
        c["stamped"] = c["n_with_sha"] > 0

    unstamped = sorted(k for k, v in by_collection.items() if not v["stamped"])
    multi_sha_files = {k: v["distinct_shas"] for k, v in per_file.items()
                       if v["n_distinct_shas"] > 1}

    out = {
        "purpose": (
            "Measured git-provenance coverage of the released raw trial records. Replaces "
            "the paper's earlier unqualified claim that all experiments record git commit "
            "hashes, which the released tree does not support."),
        "totals": {
            "files": totals["files"],
            "files_with_any_sha": totals["files_with_sha"],
            "records": totals["records"],
            "records_with_sha": totals["records_with_sha"],
            "pct_records_with_sha": round(
                100.0 * totals["records_with_sha"] / max(totals["records"], 1), 2),
            "records_with_dirty_sha": totals["records_dirty"],
            "pct_of_stamped_that_are_dirty": round(
                100.0 * totals["records_dirty"] / max(totals["records_with_sha"], 1), 2),
            "distinct_shas": dict(sorted(shas_global.items())),
        },
        "unstamped_collections": unstamped,
        "files_with_multiple_shas": multi_sha_files,
        "by_collection": by_collection,
        "per_file": per_file,
    }

    dest = RESULTS / "provenance_coverage.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n")
    t = out["totals"]
    print(f"{t['records_with_sha']}/{t['records']} records carry a git SHA "
          f"({t['pct_records_with_sha']}%), in {t['files_with_any_sha']}/{t['files']} files")
    print(f"{t['records_with_dirty_sha']} of those "
          f"({t['pct_of_stamped_that_are_dirty']}%) are -dirty")
    print(f"unstamped collections: {', '.join(unstamped)}")
    print(f"files with >1 SHA: {list(multi_sha_files)}")
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
