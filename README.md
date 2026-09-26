# Forensic Trajectory Signatures (FTS)

Artifact repository for the paper *Retrieval Observability Bounds on Provenance
Detection for Agent Memory Poisoning: Measured Coverage and a Falsified
Standalone Detector* (arXiv:2606.30566). Corresponds to arXiv v3; see the paper
for the formal version history.

This repository contains the code, preregistrations, result data, and paper
source needed to reproduce the analyses. Model results served through an
institutional API gateway are auditable via per-record provenance stamps but
are not bitwise reproducible (API-served checkpoints are mutable). Open-weight
results were produced under Ollama with fixed seeds.

## Layout

- `paper.tex`, `paper.pdf`, `references.bib`, `math_commands.tex`: paper source and build.
- `CHANGELOG.md`: append-only audit ledger of every preregistration deviation,
  withdrawn claim, and correction across all versions of the paper.
- `V*_PREREG.md`, `X*_PREREG.md`, `BPLUS_PREREG*.md`: preregistrations for every
  probe (V2-1 through V3-6b, X1-X6, B+), each GPG-signed before data collection.
- `probe_*.py`, `score_*.py`, `x_*.py`: probe implementations and scorers for
  every preregistered collection, including the X-program (X1-X6), B+, and the
  V3-6/V3-6b store-versus-context replications.
- `paper_a_classifier.py`: trajectory-signature classifier (feature extraction + training).
- `trace_v2_1_fpr.py`, `bench_ct_cd.py`: benign deployment-FPR trace and the cost
  micro-benchmark, both reading the V2-1 benign corpus in `results/v2_1_benign/`.
- `validate_all.py`, `conformance.py`, `check_conformance.py`: fail-closed
  completeness and conformance checks run before any confirmatory collection.
- `leave_one_family_out.py`: leave-one-defense-family-out generalization analysis.
- `reanalysis_implicit_bypass.py`, `reanalysis_confounders.py`: re-analyses of
  existing data behind the write-observability subsection.
- `scripts/`: cross-framework, cross-harness, prospective-eval and PPV-table experiments.
- `results/`: raw trial data (JSONL) for every probe, including the V2-1 benign
  corpus (`results/v2_1_benign/`), the X-program, B+, and V3-6/V3-6b, plus
  scored-summary JSON per collection.
- `artifact_manifest.json`: SHA-256 content-hash manifest over every released file.

## Configuration

Experiment scripts read the API gateway base URL and key from the environment:

```
export FRONTIER_API_BASE=<your OpenAI-compatible gateway base URL>
export FRONTIER_API_KEY=<your key>
```

Model identifiers in the code and data use bare names (e.g. `claude-sonnet-4-6`,
`gpt-5.1`, `gemini-2.5-pro`); route them through your own gateway as needed.
`run_macstudio_queue.sh` reaches a remote Ollama host over SSH and reads the
target from `OLLAMA_SSH_TARGET=user@host`.

The classifier training data (the P1 defense factorial) is the one input not
vendored here. It is archived in the companion repository
https://github.com/junwenleong/stateful-agent-security-eval
(`results/defense_factorial/results.jsonl`); point `P1_JSONL_PATH` at it.

## Integrity

Every released file is listed in `artifact_manifest.json` under `files`, with the
SHA-256 of the published bytes. A small number of data files had institutional
infrastructure identifiers removed before release; those entries carry
`"scrubbed": true` and also record the internal digest. Verify with:

```python
import json, hashlib

m = json.load(open("artifact_manifest.json"))
for rel, meta in m["files"].items():
    digest = hashlib.sha256(open(rel, "rb").read()).hexdigest()
    assert digest == meta["sha256_published"], f"mismatch: {rel}"
print("all", len(m["files"]), "files verified;", m["summary"]["scrubbed_files"], "scrubbed")
```
