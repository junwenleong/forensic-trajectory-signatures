# Deployment Implications: Forensic Trajectory Detectors that Rely on `recall→send` Signatures

*FTS v2 sub-study (companion to arXiv:2606.30566). Scope: detectors whose signal is the
structural `recall_before_send` trajectory pattern. This is NOT a claim about all agent IDS or all
trajectory monitoring; it is a boundary condition for one signature family.*

*Evidence status: frozen (GPG-signed checkpoint `3d36a97`, SHA256 manifest `artifact_manifest.json`)
and analysis-reproducible from the frozen records. Exact data regeneration is NOT guaranteed: the
records are auditable observations of frontier-API behaviour at access time (Jul 1–2 2026); provider
APIs are mutable and non-deterministic even with fixed request parameters.*

---

## 1. Finding

The FTS detector is, on benign data, a **deterministic `recall_before_send` classifier**:
`P(flag | recall_before_send = 1) = 100%` [99.4, 100] and `P(flag | = 0) = 0%` [0, 0.6], with
**0 exceptions across 2,000 benign sessions** (V2-1 N=1,280 + tool-desc ablation N=720). It is
**binary-saturated**: a single recall-before-send trips it fully; recall volume does not modulate
(FPR is 100% whether recall_count=1 or 5 among recall_before_send=1 sessions, ruling out a
volume-mediation account).

**This holds across both frontier and open-weight models.** Pooling the API set with the Mac
Studio OSS replication (glm-4.7-flash, gpt-oss:20b/safeguard:120b, qwen2.5:14b/72b, qwen3:32b,
qwen3.5:9b/122b, qwq:32b; 13 models total): `P(FP | recall_before_send=1) = 100.0%` [99.8,100.0]
N=1713; `P(FP | recall_before_send=0) = 0.0%` [0.0,0.14] N=2647.
The precision ceiling is not a frontier-API artefact: it generalises to open-weight models too.

> Corrected 2026-09-19. This file previously reported `1.5%` [1.1,2.0] at
> `recall_before_send=0` with N=1673/2687, computed under the superseded
> *first-occurrence* feature definition (first recall vs first send). The released
> classifier (`paper_a_classifier.py`) implements the corrected *any-preceding*
> definition (`min(recall_positions) < max(send_positions)`), which reclassifies the 40
> send-then-recall-then-send sessions that the naive definition mislabelled, exactly
> the 1.5% of 2687. Hence 1673+40 = 1713 and 2687-40 = 2647, and the map from
> `recall_before_send` to the flag is exactly deterministic on the benign corpus. These
> are now the same numbers the paper reports; the underlying V2-1 data are unchanged.

Benign memory-grounded sends, in which an agent recalls stored context (a deadline, a lead, a standup
time) and then emails it to the legitimate recipient, produce exactly this trajectory. They are
therefore **score-isomorphic to attacks under the FTS classifier** (within-model, GPT-4.1: benign
`recall→send` mean 0.950 vs attack 1.000, overlapping in the flag region; the residual gap is small
and trivially evadable by recalling one key and sending once).

## 2. Boundary

**`recall→send` is a valid attack *precondition*, not a maliciousness *predicate*.** A memory-channel
exfiltration must produce it; but so does benign memory-grounded action, because the two are identical
at the operation level and differ only in the recipient address, which operation-only features
exclude by design. This establishes a **precision ceiling for purely structural `recall→send`
signatures**. It does not claim that no operation-only detector can separate the two: features such as
recipient externality, destination allowlist, task-intent, or memory-content classification may.

## 3. Model behaviour (three phenotypes; report the three-way denominator, not FPR alone)

Benign FPR is governed by a **model-specific behavioural phenotype**, so report benign sessions in three
buckets; otherwise non-completing models look artificially safe:

| Phenotype | Benign behaviour | FPR\|sent | Models (tested) |
|---|---|---|---|
| **Ground-then-act** | recall → send | 76–100% | claude-sonnet-4-6 (99%), gemini-3.5-flash (100%), gemini-3.1-pro (76%) |
| **Act-without-grounding** | send, no recall | 0% | gpt-4o, gpt-4.1, gpt-4o-mini, o4-mini, qwen2.5:14b (0/320 benign rbs=1), qwq:32b outside its `k=1 mandatory` cell |
| **Don't-act** | no send at all | n/a (uninformative) | claude-haiku-4-5 (0/80 send), claude-opus-4-8 (78/80 no-send) |

**OSS models replicate the same three phenotypes** (Mac Studio, N=40/cell): qwen2.5:72b,
qwen3:32b, qwen3.5:9b/122b, gpt-oss:20b/safeguard:120b, and glm-4.7-flash all show
ground-then-act at higher k with FPR=100% whenever recall_before_send=1, matching the frontier
pattern above.

Two per-model corrections (2026-09-24), both verified by re-scoring the V2-1 records:

- **`qwq:32b` is not an anomaly.** This file previously described it as showing an
  "inconsistent/near-zero FPR profile across most cells, flagged as unexplained." That was
  true only under the superseded *first-occurrence* feature definition corrected in §1.
  Re-scoring all eight `qwq:32b` cells (320 benign sessions, all of which send): under
  first-occurrence, `recall_before_send=1` in **0/320**; under the released any-preceding
  definition, **40/320 = 12.5%**, and the whole difference is the single `k=1 mandatory`
  cell, where all 40 sessions flip 0→1 (i.e. 100% conditional FPR in that cell, 0 elsewhere).
  The mechanism is the send → recall-to-revise → re-send pattern the old feature mislabelled.
  `qwq:32b` therefore behaves like every other model once the feature is correct, and the
  "unexplained" framing is withdrawn. (Its *attack-side* implicit-bypass behaviour, RAG
  fallback instead of explicit `recall_fact`, is a separate, still-valid finding.)
- **`qwen2.5:14b` is act-without-grounding on this corpus, not ground-then-act.** It was
  previously listed above among the models showing "FPR=100% whenever recall_before_send=1."
  It has no such sessions to characterise: `recall_before_send=0` in **all 320** benign
  sessions under *both* definitions, so its V2-1 benign FPR is 0% and it belongs in the
  act-without-grounding bucket. This does not conflict with the paper's leave-one-model-out
  result (hold-out AUC 0.083), which concerns the P1 *attack* factorial, where this model does
  call `recall_fact` on non-exfiltration sessions. Two different corpora, two different tasks.

The ground-then-act propensity is **not a tool-description artefact**: it survives replacing the
memory tool's compliance-flavoured description with a neutral key-value-store description (Sonnet
100%→98%, gemini-flash 92%→92%, gemini-pro 85%→68%). It is **model-specific, not family-wide** (within
Anthropic: Sonnet grounds-then-acts; Haiku/Opus don't act). "Architectural" is **not** proven:
policy, RLHF, and provider tuning are not isolated. Note the absence of a clean capability/safety
gradient: Opus (top-tier) is not flagged because it rarely acts, and when it does send (2/2) it grounds
first and is flagged.

## 4. Deployment rule

Do **not** deploy a `recall→send` trajectory detector as a standalone inline blocker: under a
deployment where agents ground actions in memory (a desirable, common pattern), benign false positives
reach 76–100% for ground-then-act models. Instead:

- Use `recall→send` as a **high-recall escalation / triage signal**, not a block decision.
- **Gate it with semantics, not with recipient metadata.** Recipient externality (a single
  routing-metadata bit computable from the send tool's `to` argument, no message-content
  inspection) was the one gate actually tested, and **V3-5 falsified it**: on legitimate
  external business email the recipient bit flags 129 of 129 completed sends (100%), and the
  combined gate (`recall_before_send=1` AND external recipient) still flags 58 of 129 (45.0%,
  Wilson [0.366, 0.536]). The earlier "separates benign/attack perfectly on this data" framing
  was an artefact of a benign corpus whose only send target was an internal team address; once
  the benign workload legitimately emails outside the organisation, the bit carries no
  discriminative information. That recommendation is withdrawn. What remains indicated, and
  **untested**, is a content- or intent-level gate (does the message body actually depend on
  the retrieved record? is external routing consistent with the task?). Its precision is an
  open empirical question, so treat it as a research direction rather than a deployment recipe.
- Positioning vs the trajectory-monitoring literature (TrajAD, TraceAegis): this does **not** refute
  runtime trajectory anomaly detection; it is a boundary condition. **Trajectory-level monitoring is
  necessary but insufficient: structural traces require task/semantic grounding to avoid false
  positives on benign memory-grounded behaviour.**

## 5. Open questions

- **`qwq:32b` anomaly: RESOLVED, no longer open (see §3).** It was a feature-definition
  artefact, not a model property: 0/320 benign `recall_before_send=1` under the superseded
  first-occurrence definition versus 40/320 under the released any-preceding definition, all
  40 in the `k=1 mandatory` cell, mechanism = send → recall-to-revise → re-send.
- **Act-without-grounding phenotype membership is interface-dependent, and this note measured
  only exact-key recall.** GPT-4.1 is act-without-grounding here but shows 82.5% benign
  `search_before_send` under semantic `memory_search` (V3-2 H4), so every 0% FPR in §3 is
  conditional on the exact-key interface and should not be carried over to a semantic-search
  deployment.
- **Provider alias mutability**: frontier models accessed via undated API aliases; exact checkpoints not
  pinnable; `system_fingerprint` (OpenAI only; Gemini/Claude return none) monitors backend drift, does
  not guarantee reproducibility.
- **No-send denominator**: the "don't-act" phenotype (Haiku/Opus) is uninformative for the precision
  ceiling and must be excluded, not counted as safe.
- **Cause of the phenotype**: architecture vs policy vs RLHF vs provider tuning: unresolved.

---

### Highest-leverage one-sentence takeaway
> The detector learned a valid attack **precondition** (`recall→send`), not a maliciousness **predicate**;
> benign memory-grounded sends are score-isomorphic to attacks under the FTS classifier, so the
> structural signature is a high-recall escalation signal that must be gated by recipient/task semantics,
> not a standalone blocker.
