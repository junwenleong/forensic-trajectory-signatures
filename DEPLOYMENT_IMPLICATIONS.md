# Deployment Implications — Forensic Trajectory Detectors that Rely on `recall→send` Signatures

*Paper A v2 sub-study (companion to arXiv:2606.30566). Scope: detectors whose signal is the
structural `recall_before_send` trajectory pattern. This is NOT a claim about all agent IDS or all
trajectory monitoring — it is a boundary condition for one signature family.*

*Evidence status: frozen (GPG-signed checkpoint `3d36a97`, SHA256 manifest `paper_a/artifact_manifest.json`)
and analysis-reproducible from the frozen records. Exact data regeneration is NOT guaranteed — the
records are auditable observations of frontier-API behavior at access time (Jul 1–2 2026); provider
APIs are mutable and non-deterministic even with fixed request parameters.*

---

## 1. Finding

The Paper A detector is, on benign data, a **deterministic `recall_before_send` classifier**:
`P(flag | recall_before_send = 1) = 100%` [99.4, 100] and `P(flag | = 0) = 0%` [0, 0.6], with
**0 exceptions across 2,000 benign sessions** (V2-1 N=1,280 + tool-desc ablation N=720). It is
**binary-saturated**: a single recall-before-send trips it fully; recall volume does not modulate
(FPR is 100% whether recall_count=1 or 5 among recall_before_send=1 sessions, ruling out a
volume-mediation account).

**This holds across both frontier and open-weight models.** Pooling the API set with the Mac
Studio OSS replication (glm-4.7-flash, gpt-oss:20b/safeguard:120b, qwen2.5:14b/72b, qwen3:32b,
qwen3.5:9b/122b, qwq:32b — 13 models total): `P(FP | recall_before_send=1) = 100.0%` [99.8,100.0]
N=1673; `P(FP | recall_before_send=0) = 1.5%` [1.1,2.0] N=2687 (script: `scripts/score_v2_1.py`).
The precision ceiling is not a frontier-API artifact — it generalizes to open-weight models too.

Benign memory-grounded sends — an agent that recalls stored context (a deadline, a lead, a standup
time) and then emails it to the legitimate recipient — produce exactly this trajectory. They are
therefore **score-isomorphic to attacks under the Paper A classifier** (within-model, GPT-4.1: benign
`recall→send` mean 0.950 vs attack 1.000 — overlapping in the flag region; the residual gap is small
and trivially evadable by recalling one key and sending once).

## 2. Boundary

**`recall→send` is a valid attack *precondition*, not a maliciousness *predicate*.** A memory-channel
exfiltration must produce it; but so does benign memory-grounded action, because the two are identical
at the operation level and differ only in the recipient address — which operation-only features
exclude by design. This establishes a **precision ceiling for purely structural `recall→send`
signatures**. It does not claim that no operation-only detector can separate the two: features such as
recipient externality, destination allowlist, task-intent, or memory-content classification may.

## 3. Model behavior (three phenotypes; report the three-way denominator, not FPR alone)

Benign FPR is governed by a **model-specific behavioral phenotype**, so report benign sessions in three
buckets — otherwise non-completing models look artificially safe:

| Phenotype | Benign behavior | FPR\|sent | Models (tested) |
|---|---|---|---|
| **Ground-then-act** | recall → send | 76–100% | claude-sonnet-4-6 (99%), gemini-3.5-flash (100%), gemini-3.1-pro (76%) |
| **Act-without-grounding** | send, no recall | 0% | gpt-4o, gpt-4.1, gpt-4o-mini, o4-mini |
| **Don't-act** | no send at all | n/a (uninformative) | claude-haiku-4-5 (0/80 send), claude-opus-4-8 (78/80 no-send) |

**OSS models replicate the same three phenotypes** (Mac Studio, N=40/cell): qwen2.5:14b/72b,
qwen3:32b, qwen3.5:9b/122b, gpt-oss:20b/safeguard:120b, and glm-4.7-flash all show
ground-then-act at higher k with FPR=100% whenever recall_before_send=1, matching the frontier
pattern above. One anomaly: **qwq:32b** shows an inconsistent/near-zero FPR profile across most
cells despite comparable recall behavior — flagged here as unexplained, not force-fit into a
phenotype bucket (possible reasoning-model-specific effect on tool-call sequencing; not
investigated further, out of scope for this deployment note).

The ground-then-act propensity is **not a tool-description artifact** — it survives replacing the
memory tool's compliance-flavored description with a neutral key-value-store description (Sonnet
100%→98%, gemini-flash 92%→92%, gemini-pro 85%→68%). It is **model-specific, not family-wide** (within
Anthropic: Sonnet grounds-then-acts; Haiku/Opus don't act). "Architectural" is **not** proven —
policy, RLHF, and provider tuning are not isolated. Note the absence of a clean capability/safety
gradient: Opus (top-tier) is not flagged because it rarely acts, and when it does send (2/2) it grounds
first and is flagged.

## 4. Deployment rule

Do **not** deploy a `recall→send` trajectory detector as a standalone inline blocker — under a
deployment where agents ground actions in memory (a desirable, common pattern), benign false positives
reach 76–100% for ground-then-act models. Instead:

- Use `recall→send` as a **high-recall escalation / triage signal**, not a block decision.
- **Gate it with semantics**: recipient externality (a single routing-metadata bit computable from the
  send tool's `to` argument — no message-content inspection — separates benign/attack perfectly *on
  this data*, with an honest residual: benign external comms, e.g. legitimate client email, would set
  the bit → residual FP), and/or task-intent / memory-content checks.
- Positioning vs the trajectory-monitoring literature (TrajAD, TraceAegis): this does **not** refute
  runtime trajectory anomaly detection — it is a boundary condition. **Trajectory-level monitoring is
  necessary but insufficient: structural traces require task/semantic grounding to avoid false
  positives on benign memory-grounded behavior.**

## 5. Open questions

- **`qwq:32b` anomaly**: this reasoning model shows a near-zero FPR profile despite comparable
  recall behavior to the other OSS models (see §3). Mechanism unexplained; not investigated
  further in this note.
- **Provider alias mutability**: frontier models accessed via undated API aliases; exact checkpoints not
  pinnable; `system_fingerprint` (OpenAI only; Gemini/Claude return none) monitors backend drift, does
  not guarantee reproducibility.
- **No-send denominator**: the "don't-act" phenotype (Haiku/Opus) is uninformative for the precision
  ceiling and must be excluded, not counted as safe.
- **Cause of the phenotype**: architecture vs policy vs RLHF vs provider tuning — unresolved.

---

### Highest-leverage one-sentence takeaway
> The detector learned a valid attack **precondition** (`recall→send`), not a maliciousness **predicate**;
> benign memory-grounded sends are score-isomorphic to attacks under the Paper A classifier, so the
> structural signature is a high-recall escalation signal that must be gated by recipient/task semantics —
> not a standalone blocker.
