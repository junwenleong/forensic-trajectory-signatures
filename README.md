# Forensic Trajectory Signatures (FTS)

Artifact repository for the paper *Retrieval Observability Bounds on Provenance
Detection for Agent Memory Poisoning: Measured Coverage and a Falsified
Standalone Detector* (arXiv:2606.30566).

This repository contains the code, preregistrations, result data, and paper
source needed to reproduce the analyses. Model results served through an
institutional API gateway are auditable via per-record provenance stamps but
are not bitwise reproducible (API-served checkpoints are mutable). Open-weight
results were produced under Ollama with fixed seeds.

## Layout

- `paper.tex`, `paper.pdf`, `references.bib`, `math_commands.tex` : paper source and build.
- `CHANGELOG.md` : append-only audit ledger of every preregistration deviation,
  withdrawn claim, and correction across all versions of the paper.
- `V*_PREREG.md`, `X*_PREREG.md`, `BPLUS_PREREG*.md` : preregistrations for every
  probe (V2-1 through V3-6b, X1-X6, B+), each GPG-signed before data collection.
- `probe_*.py`, `score_*.py`, `x_*.py` : probe implementations and scorers for
  every preregistered collection, including the X-program (X1-X6), B+, and the
  V3-6/V3-6b store-versus-context replications.
- `paper_a_classifier.py` : trajectory-signature classifier (feature extraction + training).
- `validate_all.py`, `conformance.py`, `check_conformance.py` : fail-closed
  completeness and conformance checks run before any confirmatory collection.
- `leave_one_family_out.py` : leave-one-defense-family-out generalization analysis.
- `reanalysis_implicit_bypass.py`, `reanalysis_confounders.py` : re-analyses (existing data only)
  behind the write-observability subsection: the recall-ablated vs full-classifier catch rates on
  implicit-bypass attacks, the save-before-send signature, its benign FPR, and the both-implicit
  (scaffold-side write) quadrant.
- `scripts/` : cross-framework / cross-harness / prospective-eval / PPV-table experiments.
- `results/` : raw trial data (JSONL) for every probe, including the X-program,
  B+, and V3-6/V3-6b subdirectories, plus scored-summary JSON per collection.
- `artifact_manifest.json` : SHA-256 content-hash manifest over every released file.

## Configuration

Experiment scripts read the API gateway base URL and key from the environment:

```
export FRONTIER_API_BASE=<your OpenAI-compatible gateway base URL>
export FRONTIER_API_KEY=<your key>
```

Model identifiers in the code and data use bare names (e.g. `claude-sonnet-4-6`,
`gpt-5.1`, `gemini-2.5-pro`); route them through your own gateway as needed.

The classifier training data (the P1 defense factorial) is archived in the
companion repository: https://github.com/junwenleong/stateful-agent-security-eval

## Integrity

Verify released files against the manifest (files are grouped by category; each
entry records a SHA-256 digest and size in bytes, or `MISSING: true` for an
external input that is named but not vendored):

```python
import json, hashlib

m = json.load(open("artifact_manifest.json"))
n = 0
for category, files in m["artifacts"].items():
    if category == "lockfile":
        continue
    for rel, meta in files.items():
        if isinstance(meta, dict) and meta.get("MISSING"):
            continue
        digest = hashlib.sha256(open(rel, "rb").read()).hexdigest()
        assert digest == meta["sha256"], f"mismatch: {rel}"
        n += 1
print("all", n, "files verified")
```
