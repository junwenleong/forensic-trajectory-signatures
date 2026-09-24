# V3-3 Pre-Registration — Ground-Then-Act × Implicit Delivery

**Paper:** arXiv:2606.30566 (Forensic Trajectory Signatures for Agent Memory Poisoning Detection)
**Registered:** 2026-09-08 (GPG-signed commit BEFORE confirmatory data collection).
**Author:** Jun Wen Leong

**STATUS: PREREGISTERED. NO CONFIRMATORY DATA COLLECTED (pilot data discarded — see Model Selection).**

## Motivation

V3-1 established that under implicit delivery (ICL-simulated framework retrieval),
the `recall_before_send` (rbs) necessity is broken for **act-without-grounding**
models: successful attacks occur with rbs=0 (GPT-4.1 67%, GPT-4o 74%). The paper
states, twice, that the scope boundary is validated only on act-without-grounding
models, and that whether **ground-then-act** models — which habitually recall
stored context before acting — retain the rbs signature under implicit delivery
is an open question. V3-3 closes this gap.

Both outcomes are informative and are preregistered with equal prominence:
- **treatment rbs=0 rate high** on a ground-then-act model: necessity breaks for
  this phenotype too; the retrieval-observability boundary holds across phenotypes.
- **treatment rbs=1 rate high** (model redundantly recalls even when the address is
  already in context): the signature survives implicit delivery for grounders;
  taxonomy becomes phenotype-dependent, with an adaptive-adversary implication (an
  attacker targeting a ground-then-act deployment cannot rely on implicit delivery
  to evade the detector).

Neither branch is treated as the "null."

## Design

Extends the V3-1 two-arm within-architecture probe to ground-then-act models, plus
a **benign ground-then-act control cell** (new, panel-mandated) that is the keystone
for interpreting a high treatment rbs=1 rate.

### Arms

| Arm | Delivery of routing address | Purpose |
|-----|---|---|
| control (tool-routed DTA) | Stored in memory; agent calls `recall_fact` in trigger | Replicate the rbs necessity (H1) |
| treatment (implicit ICL) | Placed as prior-session ICL demonstration; agent CAN but need not recall | Necessity test (H2) |
| benign (NEW) | No attacker payload; legitimate memory-grounded email task | Disambiguate habit vs verification |

**Why the benign cell is the keystone (was missing):** a high treatment rbs=1 rate
is ambiguous between (a) genuine verification recall of the in-context rule, (b)
unconditional recall habit (recalls regardless of task), and (c) ICL behavioral
cloning. The benign cell measures baseline recall-before-send on a legitimate task
with NO poisoned content and NO ICL demonstration. If benign rbs approx 1 too, a
high treatment rbs=1 reflects an unconditional habit (b), not payload-driven
verification — the precondition-not-predicate story extended to grounders. This
cell makes the treatment result interpretable.

### Anti-imitation constraint (V3-1 design req #4, carried forward)

The treatment-arm ICL demonstration MUST NOT depict any `recall_fact` invocation
(only `save_fact`/acknowledgement). Enforced in code
(`probe_v3_1.build_icl_demonstration`, reused unchanged).

### Length-matched control prefix (new)

The treatment ICL demonstration adds ~400 tokens of prior-session context. To rule
out an attention-dilution artifact, the control arm receives a length-matched
benign filler prefix of comparable token count (a benign prior-session exchange, no
routing rule, no recall depicted). Both arms have matched context length; only the
content of the prior exchange (routing rule present vs absent) differs.

### Decoy-vs-attacker-key content check (promoted from V3-1 H4)

For every treatment success with rbs=1, record (from tool arguments — an
analysis-level variable the detector's features exclude) whether `recall_fact`
targeted the attacker-address key or a benign decoy key. A decoy-key recall means
the detector fires (rbs=1) but the memory channel was not used for payload
delivery — a structural false alarm, not payload-dependent retrieval.

### Scenario grid (expanded)

V3-1 used 18 unique configs sampled with replacement (effective-N approx 18). V3-3
expands to >=36 distinct configs by varying the decoy-fact subset as a genuine axis:
3 tasks x 3 phrasings x 2 addresses x 2 disjoint decoy subsets = 36 (extendable to
72). Sampling draws distinct configs first (no repeats until grid exhausted), so
oversampling adds real variation rather than temperature-noise replicates.

## Models (Confirmatory Roster — fixed by preregistered pilot gate)

**Primary confirmatory model: `gemini-2.5-pro`** (ground-then-act phenotype).

**Model-selection procedure (preregistered, executed on discarded pilot data):**
each candidate piloted at N=20 on the control arm (fixed seed 4242, distinct from
confirmatory). Inclusion threshold: control-arm ASR >= 10%.
- `gemini-2.5-pro`: pilot control ASR = 10/20 = **50%** -> PROMOTED.
- `gemini-3.5-flash`: excluded (reasoning model returns empty intermittently).
- Local Qwen grounders: deferred to optional-secondary (Studio disk + harness
  routing); if added, labeled exploratory-secondary with their own pilot gate.

Pilot data are DISCARDED and never pooled into the confirmatory estimate.

## Sample Size and Stopping Rule (negative-binomial)

- **Estimand:** P(rbs=0 | attack_success=1, treatment), per model, no pooling.
- **Stopping rule (inverse/negative-binomial):** collect treatment trials until
  >=30 treatment attack successes OR a hard cap of N=120 treatment trials per model,
  whichever first. Stopping depends ONLY on success count, NEVER on the rbs outcome
  — free of optional-stopping bias for the conditional estimand. Control and benign
  arms collect fixed N=60 each.
- At gemini-2.5-pro's piloted 50% ASR, ~60 treatment trials yield ~30 successes; the
  cap protects against lower realized ASR.

## Inference (scenario-clustered, NOT Wilson)

Trials are sampled from a finite scenario grid at temperature-appropriate settings
against an endpoint where identical prompts produce correlated outcomes, so Wilson
intervals on raw trial counts are anti-conservative. The **primary CI is a
scenario-clustered bootstrap** (resample distinct scenario configs as clusters,
10,000 resamples, seed 42). Wilson intervals are reported as a secondary/nominal
reference. Effective N reported as the number of distinct scenario configs
contributing successes.

## Hypotheses (Confirmatory)

- **H1 (control replication):** 0/N_control_successes have rbs=0. Report clustered
  upper bound.
- **H2 (treatment necessity test):** sign and magnitude of P(rbs=0 | success,
  treatment) with scenario-clustered 95% CI. Both CI-excludes-0 (necessity broken)
  and high-rbs=1 (signature survives) are preregistered outcomes.
- **H_benign (keystone):** P(rbs=1 | benign, ground-then-act), interpreted jointly
  with H2.
- **H_content:** among treatment rbs=1 successes, fraction recalling attacker key vs
  decoy key.

## Falsification Criteria (both branches, equal prominence)

- **Taxonomy universal:** treatment rbs=0 CI excludes 0 -> necessity breaks for
  ground-then-act too.
- **Phenotype-dependent:** treatment rbs=1 high AND benign rbs=1 high -> signature
  survives implicit delivery for grounders because they recall unconditionally;
  taxonomy column semantics change to "forced vs fires-anyway"; adaptive-adversary
  implication stated. A publishable positive result, not a null.
- **Underpower guard:** <30 treatment successes at the N=120 cap -> reported as
  underpowered feasibility, achieved success count and clustered CI stated
  explicitly.

## Analysis Plan

1. Per-model ASR per arm.
2. Treatment: scenario-clustered bootstrap 95% CI on P(rbs=0 | success); Wilson
   secondary.
3. Control: replicate H1.
4. Benign: P(rbs=1 | benign) with clustered CI (habit-vs-verification keystone).
5. Content check: attacker-key vs decoy-key recall among treatment rbs=1 successes.
6. Report which falsification branch the data support, with Table-6 language
   committed for each branch.

## Reproducibility

- GPG-signed commit of this document BEFORE confirmatory data collection.
- API checkpoints not pinnable — state "gemini-2.5-pro accessed via Frontier API as
  of Sep 2026; exact checkpoint not guaranteed reproducible." Every record
  provenance-stamped.
- Expanded scenario grid committed with the probe before runs.
- Temperature: 1 for gemini (NO_TEMP_MODELS), else 0.
- Resume-safe: one JSONL per (model, arm). Confirmatory seeds distinct from pilot
  seed (4242).
