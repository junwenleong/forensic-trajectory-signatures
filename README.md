# Forensic Trajectory Signatures (FTS)

Artifact repository for the paper *Forensic Trajectory Signatures: Retrieval
Observability Determines the Detection Boundary* (arXiv:2606.30566).

This repository contains the code, preregistrations, result data, and paper
source needed to reproduce the analyses. Model results served through an
institutional API gateway are auditable via per-record provenance stamps but
are not bitwise reproducible (API-served checkpoints are mutable). Open-weight
results were produced under Ollama with fixed seeds.

## Layout

- `paper.tex`, `paper.pdf`, `references.bib` : paper source and build.
- `probe_v3_1.py`, `probe_v3_2.py` : preregistered retrieval-observability probes (V3-1, V3-2).
- `paper_a_classifier.py` : trajectory-signature classifier (feature extraction + training).
- `leave_one_family_out.py` : leave-one-defense-family-out generalization analysis.
- `reanalysis_implicit_bypass.py`, `reanalysis_confounders.py` : re-analyses (existing data only)
  behind the write-observability subsection: the recall-ablated vs full-classifier catch rates on
  implicit-bypass attacks, the save-before-send signature, its benign FPR, and the both-implicit
  (scaffold-side write) quadrant.
- `scripts/` : cross-framework / cross-harness / prospective-eval / PPV-table experiments.
- `results/` : raw trial data (JSONL) for V3-1, V3-2, cross-framework, and prospective eval.
- `V2_1_PREREG.md`, `V3_1_PREREG.md`, `V3_2_PREREG.md`, `scripts/cross_framework_preregistration.md` : preregistrations.
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

Verify released files against the manifest:

```python
import json, hashlib
m = json.load(open("artifact_manifest.json"))
for rel, meta in m["files"].items():
    assert hashlib.sha256(open(rel, "rb").read()).hexdigest() == meta["sha256"], rel
print("all", len(m["files"]), "files verified")
```
