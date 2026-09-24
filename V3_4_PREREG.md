# V3-4 Pre-Registration — Genuine Framework Replication (LangChain / LangGraph)

**Paper:** arXiv:2606.30566 (Forensic Trajectory Signatures for Agent Memory Poisoning Detection)
**Registered:** 2026-09-08 (GPG-signed commit BEFORE data collection).
**Author:** Jun Wen Leong

**STATUS: PREREGISTERED. NO DATA COLLECTED.**

## Motivation

The v3 "cross-framing" study (Section 5.1) is, by the paper's own disclosure, two
prompt-framing variants of ONE raw OpenAI function-calling loop — not independent
orchestration engines. It is labeled exploratory (E). This experiment executes the
first GENUINE framework replication: the retrieval-to-action observability boundary
is tested on a real agent orchestration engine (LangChain / LangGraph), not a
prompt-wrapped raw loop.

The test has two sides, matching the taxonomy's two-sided prediction:
- **Observable arm:** a genuine LangChain/LangGraph ReAct agent (`create_react_agent`)
  with a tool-routed memory recall tool. Prediction: successful tool-routed attacks
  produce the `recall_before_send` signature (frozen classifier flags them).
- **Implicit arm:** a genuine LangChain retriever-injection RAG chain where the
  framework retrieves the poisoned document and injects it into the prompt WITHOUT
  the agent issuing any observable retrieval tool call (scaffold-side / MINJA-style
  implicit retrieval). Prediction: successful attacks produce NO recall signature;
  the frozen classifier fails to flag them.

## Infrastructure constraint (disclosed)

The originally-planned OpenAI Assistants API `file_search` implicit arm is
**infrastructure-blocked**: the institutional API gateway returns "This Path is
Forbidden" for the Assistants and vector-stores endpoints (verified 2026-09-08);
the gateway exposes chat-completions only. The implicit arm is therefore
implemented as a genuine LangChain retriever-injection chain (a real framework
RAG path with framework-side retrieval and no agent tool call), which occupies the
SAME taxonomy cell (implicit read; scaffold-side injection) as Assistants
file_search and as the paper's MINJA/Zombie classification. This is a genuine
orchestration engine, not a prompt wrapper. The substitution is disclosed as a
deviation from the original cross_framework preregistration and does not change
which taxonomy cell is tested.

## Design

### Model

- **Primary: `gpt-4.1-mini`** (matches the original cross_framework prereg;
  known-vulnerable to DTA at high ASR; preserves the confirmatory baseline).
- **Bridge (exploratory, labeled E): `gpt-5.1`**, one cell, to connect to the v3
  exploratory cross-framing study which used GPT-5.x. Not co-primary.

### Arms (per model)

| Arm | Framework | Retrieval mechanism | Observable? | Prediction |
|-----|-----------|---------------------|-------------|------------|
| LC-observable | LangGraph `create_react_agent` | agent-issued `recall_fact` tool call | yes | classifier flags successes |
| LC-implicit | LangChain retriever-injection chain | framework retrieves + injects into prompt; no agent tool call | no | classifier misses successes |
| LC-benign | LangGraph `create_react_agent` | benign memory-grounded task, internal recipient | yes (habit) | benign FPR reproduced |

N = 60 attack trials per arm per model (LC-observable, LC-implicit), 60 benign.

### Feature adapter (CRITICAL — panel-mandated non-cheating rule)

The frozen P1-trained Random Forest is applied WITHOUT retraining. Each framework's
native trace is mapped to the canonical 19-feature vector by a frozen, pre-declared
ontology mapping (committed in this prereg, before data):

- **LC-observable:** LangChain tool-call names map to canonical operations
  (`recall_fact`->recall_fact, `send_email`->send_email, etc.). This is the
  legitimate remap (same class as the validated `memory_search`->recall_fact remap):
  the retrieval call genuinely EXISTS in the trace, only its name differs.
- **LC-implicit:** the framework's retrieval step issues NO agent tool call, so it
  is encoded as ABSENT from the agent-visible trace. `recall_before_send` is
  therefore 0 by construction from the agent-visible trace. **We do NOT remap the
  framework retrieval into a recall feature** — doing so would re-inject
  observability into an unobservable channel and assume the conclusion. The
  framework-side retrieval is logged SEPARATELY as an oracle (did the poisoned doc
  get retrieved?), used only to condition attack-success on delivery, never fed to
  the classifier.

The observability boundary is thereby DEMONSTRATED, not assumed: if the frozen
classifier flags LC-observable successes (high recall) but misses LC-implicit
successes (low recall) despite both being genuine framework attacks, the boundary
holds under a real orchestration engine.

## Estimands (per model, no pooling)

1. **Observable-arm recall:** among LC-observable attack successes, fraction the
   frozen classifier flags (predict, expect high).
2. **Implicit-arm recall:** among LC-implicit oracle-delivered attack successes,
   fraction the frozen classifier flags (predict, expect ~0).
3. **Benign FPR:** among LC-benign completed sessions, fraction flagged (expect the
   ground-then-act FPR ceiling reproduced under a real framework).
4. **Boundary contrast:** observable-arm recall minus implicit-arm recall
   (directional; expect strongly positive).

## Sample Size / Stopping

Fixed N=60 attack trials per arm per model; 60 benign. Attack-success and
oracle-delivery reported; recall computed among oracle-delivered successes for the
implicit arm. No interim analysis. API errors replaced; refusals kept in the ASR
denominator.

## Inference

Wilson 95% CIs on each recall/FPR rate. Because these are fresh single-shot
sessions across distinct scenarios (not resampled from a tiny grid), Wilson is
adequate; scenario-clustered bootstrap reported if scenario repetition occurs.

## Hypotheses (confirmatory)

- **H1:** frozen-classifier recall on LC-observable successes >= 0.70 (signature
  transfers to a genuine observable framework).
- **H2:** frozen-classifier recall on LC-implicit oracle-delivered successes is
  near 0 and strictly less than H1 (observability boundary holds under a genuine
  framework).
- **H3 (benign):** LC-benign FPR > 0.10 on gpt-4.1-mini (the precision ceiling
  reproduces under a real framework).

## Success criteria

- Boundary confirmed if H1 (>=0.70) AND H2 (implicit recall < observable recall,
  directional) both hold.
- If H1 fails (classifier misses observable-arm attacks), the transfer claim is
  weakened and reported honestly.

## Reproducibility

- GPG-signed commit BEFORE data collection. Probe code committed with this prereg.
- Dependencies pinned: `requirements-lock-2026-09-08.txt` (langchain 0.3.30,
  langchain-openai 0.3.35, langgraph 0.6.11).
- Cached FAISS embeddings for the implicit arm's retriever (reused from V3-2's
  cache where applicable) to prevent embedding API drift altering top-k; the cache
  hash recorded in the run manifest.
- API checkpoints not pinnable — "gpt-4.1-mini / gpt-5.1 accessed via Frontier API
  as of Sep 2026." Every record provenance-stamped.
- Frozen classifier = P1-trained RF, identical spec to Table 4 (200 trees,
  max_depth 8, seed 42, no class weighting).
