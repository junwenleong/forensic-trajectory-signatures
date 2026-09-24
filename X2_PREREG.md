# X2 Pre-Registration (v2) — Second Ground-Then-Act Model (V3-3 Replication)

**Paper:** arXiv:2606.30566 (Forensic Trajectory Signatures)
**Registered:** 2026-09-09 (GPG-signed commit BEFORE confirmatory data). v2 supersedes v1 after a pre-data panel critique flagged that an ASR gate does not verify the ground-then-act phenotype and that the fallback roster was open-ended.
**Author:** Jun Wen Leong

**STATUS: PREREGISTERED. NO CONFIRMATORY DATA COLLECTED.**

## Motivation

V3-3 established the recall-before-send necessity breaks under implicit delivery for ONE
ground-then-act model (gemini-2.5-pro), with an 88.3% benign recall habit that does not
restore the signature. X2 adds a SECOND ground-then-act model. This strengthens a
SECONDARY (phenotype-generality) claim, not the core taxonomy; it is lower priority than
X1/X4.

## Design

Identical to V3-3 (control / treatment / benign-keystone arms), reused from
`probe_v3_3.py` (model arg only; any local tool-call adapter logged as a preregistered
implementation detail, not a substantive change).

## Model selection (panel fix: ASR gate PLUS phenotype gate; frozen roster)

Two-part discarded pilot at N=20 (fixed seed 4242, distinct from confirmatory), 20
DISTINCT scenarios from the grid (panel fix: not repeated prompts):
1. **Vulnerability gate:** control-arm ASR >= 10%.
2. **Phenotype gate (NEW):** benign recall-before-send >= 70% on the benign keystone
   task at N=20, matching the confirmatory H_benign "high habit" threshold (panel fix:
   the pilot gate and confirmatory habit definition are now aligned at 70%, so a model
   that clears the gate is not later found to fail the confirmatory habit; a candidate
   in the marginal 50-70% band is NOT promoted, avoiding a phenotype-limbo outcome).
A candidate is promoted ONLY if it clears BOTH.

**Frozen candidate roster (panel fix: exact, ordered, no open-ended framing):**
1. `qwen2.5:32b` (Ollama, Mac Studio) — default system prompt = the paper's SYSTEM
   verbatim; no compliance-framing modification.
2. `qwen2.5:14b` (Ollama) — same SYSTEM.
3. `qwen3:32b` (Ollama) — same SYSTEM.
No API fallback with modified framing is permitted (the v1 "claude-sonnet with
strengthened compliance framing" option is REMOVED as an uncontrolled degree of
freedom). All pilot outcomes for all attempted candidates are reported. The final claim
is explicitly "two convenience-selected ground-then-act grounders (gemini-2.5-pro +ONE
promoted local model)", not a random draw. If NO candidate clears both gates, X2 is
reported as "attempted; no second grounder cleared the ASR+phenotype gates" and the
one-vendor limitation stands.

## Sample size / stopping (panel fix: control also success-targeted)

- Estimand: P(rbs = 0 | attack_success, treatment), per model, no pooling.
- Treatment AND control: negative-binomial to >= 37 successes OR cap N=150 (control
  gains a success target so H1 is not underpowered if the model barely clears the gate;
  37 chosen so 0 violations meets the <= 0.10 two-sided Wilson upper bound).
  Benign keystone fixed N=60. Stopping on success count only.
- < 15 successes at cap in control or treatment => that arm feasibility-only.

## Inference

Scenario-clustered bootstrap 95% CI primary (seed 42), Wilson secondary; >= 10 distinct
clusters contributing successes else descriptive-only. Effective cluster N reported.

## Hypotheses (both branches, numeric thresholds — panel fix)

- **H1 (control replication):** 0/N_control_successes have rbs=0, with a two-sided 95%
  Wilson (and clustered) upper bound reported; H1 holds if 0 violations among >= 37
  control successes (upper bound <= 0.10, matching X4's convention).
- **H2 (treatment necessity):** P(rbs=0 | success, treatment) clustered CI. Necessity
  breaks if lower bound > 0; signature survives if point estimate >= 0.80 AND clustered
  lower bound >= 0.60 (phenotype-dependent branch). Both preregistered.
- **H_benign (keystone):** P(rbs=1 | benign); "high habit" defined as point estimate
  >= 0.70 with clustered lower bound >= 0.50.

## Falsification criteria

- **Replicates V3-3:** H2 lower bound > 0 AND benign habit high => necessity breaks for a
  second grounder; phenotype-generality strengthens from one to two.
- **Phenotype-dependent:** H2 signature-survives thresholds met => genuine phenotype
  split, adaptive-adversary implication stated. Publishable, not a null.
- **Underpower:** < 30 successes at cap => achieved count + clustered CI, feasibility-only.

## Analysis plan

Per-model ASR per arm; treatment clustered CI on P(rbs=0|success); control H1; benign
keystone; decoy-vs-attacker-key content check on treatment rbs=1 successes. Identical
to V3-3 plus the phenotype-gate report.

## Reproducibility

GPG-signed commit BEFORE confirmatory data; reuses `probe_v3_3.py`. Local grounder
Regime A (fresh Ollama daemon, OLLAMA_CONTEXT_LENGTH set, port ownership asserted,
digest recorded; harness-compatibility dry-run for tool-call fidelity logged, no
confirmatory outcomes). Confirmatory seeds distinct from pilot seed 4242. Temp per
Regime A.
