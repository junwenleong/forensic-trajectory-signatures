# X3 Note (v2) — V3-2 Top-k Retrieval Sweep (Preregistration Hygiene)

**Paper:** arXiv:2606.30566 (Forensic Trajectory Signatures)
**Registered:** 2026-09-09. v2 supersedes v1 after a pre-data panel critique flagged that probe_v3_2.py cannot run k!=4 unchanged and that "k = delivery only" is too strong.
**Author:** Jun Wen Leong

**STATUS: EXECUTING A PRE-EXISTING PREREGISTERED SECONDARY ANALYSIS.**

## Motivation (hygiene)

V3-2 registered a `k in {2,4,8}` robustness sweep; only k=4 ran, and the deviation table
lists `k in {2,8}` as the sole unexecuted preregistered analysis — a preregistration-
integrity liability independent of its low expected yield. X3 discharges it.

## Executable requirement (panel fix: CANNOT reuse probe_v3_2 unchanged)

`probe_v3_2.py` hard-codes `TOP_K = 4` as a module constant, exposes no `--top-k` CLI
arg, and its output filenames do not encode k. Running k=2,8 by editing the constant
would (a) contradict "unchanged", (b) risk overwriting/mixing the k=4 artifacts, and (c)
leave no code-level provenance of which k produced which record. Therefore, BEFORE
collection, commit a small parameterized runner:
- add a `--top-k` CLI argument threaded into `search_store(..., top_k=k)` and the arm-C
  scaffold injection;
- k-stamped output paths (`results/v3_2_k{K}/...`) and `top_k` recorded in EVERY record
  and in the run manifest;
- an assertion that the oracle and the injected/returned context used the requested k;
- no mutation of the k=4 files.
This runner is committed with this note (GPG-signed) before any k!=4 data.

## Design

Arms B (tool-routed `memory_search`) and C (scaffold-side auto-RAG), models GPT-4.1 and
GPT-4o, `k in {2, 8}`, N=40 per cell (matching the k=4 primary). Same FAISS store, same
cached embeddings, same oracle (rank/similarity).

## Estimands (secondary, descriptive)

- Arm B: P(search_before_send = 0 | success AND delivered) at each k.
- Arm C: attack viability (success | delivered) at each k.
- Delivery rate, poison rank, and returned-context length/order as functions of k
  (panel fix: k affects context load/salience, not only delivery).

## Interpretation (panel fix: joint depth/context-load, not delivery-only)

k changes retrieval DEPTH: the quantity/ordering of injected benign context,
context-window pressure, instruction competition, and whether a poison at rank 8 is
attended to. X3 is therefore a joint retrieval-depth/context-load sensitivity analysis,
NOT a pure delivery-probability check. Report rank-conditioned outcomes, not only
aggregate delivered-success rates.

## Underpower thresholds (panel fix)

Per k cell: < 15 delivered successes => descriptive feasibility only; 15-29 =>
underpowered (report with CI, no robustness claim); >= 30 => supports a robustness
interpretation. Wilson secondary; scenario-clustered bootstrap primary if scenarios
repeat (they will, from the 18-config grid), with the >= 10-distinct-cluster floor.

## Anomaly protocol (panel fix)

Any arm-B success with search_before_send = 0 is a potential contradiction of the k=4
invariant: validate the trajectory, audit scoring, and state whether the k=4 claim must
be narrowed. Not anticipated, but pre-committed.

## Falsification / interpretation

- **Robustness confirmed:** arm-B violation rate ~0 and arm-C viability substantial at
  k=2 and k=8. Reported as robustness, not a new claim.
- **Surprise:** non-zero arm-B violation rate at some k => retrieval-depth sensitivity,
  reported with CI + mechanism + rank analysis. Triggers the anomaly protocol.

## Reproducibility

Parameterized k-runner committed with this note; cached embeddings (hash in manifest).
API not pinnable, provenance-stamped. Temp 0 / 1 for NO_TEMP_MODELS.
