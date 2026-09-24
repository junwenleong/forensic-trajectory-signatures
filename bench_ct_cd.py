"""
C_T / C_D benchmark for the Deployment Economics section.

Replaces the retracted "10^2--10^3x" hypothetical with a MEASURED per-session
cost ratio between:
  C_T = trajectory feature extraction (19 features from a tool-call sequence)
  C_D = one content-level DLP pass (an LLM classifying whether an outbound
        email body contains sensitive content)

C_T is measured locally over the real V2-1/P1 tool-call sequences (thousands of
reps for a stable mean). C_D is measured against a local Ollama content-
classifier (representative of a self-hosted DLP model) over a representative
email body, via the always-on Ollama HTTP API on the Mac Studio.

This is a system micro-benchmark, not a probe experiment: no model behavior is
being studied, only wall-clock cost. Report as a measured ratio with the
hardware/model stated, superseding the asymptotic-only claim.
"""
from __future__ import annotations
import json
import time
import statistics
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_a_classifier import extract_features_from_sequence

HERE = Path(__file__).resolve().parent

# A representative outbound email body a content-DLP layer would inspect.
SAMPLE_EMAIL = (
    "Subject: Q3 Project Status Update\n\n"
    "Hi team, here is this week's summary. The Q3 report is on track for the "
    "2026-09-15 deadline; the draft is with Sarah for review. Standup remains "
    "9:30 AM in Room 4B. Please submit expense receipts via Concur before "
    "end of week. Client deliverables for the Acme account are 80% complete; "
    "the remaining items are the security review and the final QA pass. "
    "Let me know if anything is blocked. Thanks."
)

DLP_PROMPT = (
    "You are a data-loss-prevention classifier. Decide whether the following "
    "outbound email contains sensitive information (credentials, PII, secrets, "
    "confidential financials, or restricted data) that should be blocked. "
    "Answer with exactly one word: BLOCK or ALLOW.\n\nEMAIL:\n" + SAMPLE_EMAIL
)


def load_sample_sequences(n=200):
    """Grab real tool-call sequences from V2-1 benign logs for C_T timing."""
    seqs = []
    import glob
    for f in glob.glob(str(HERE.parent / "paper_1_behavioral" / "results" / "v2_1_*.jsonl")):
        for l in open(f):
            if not l.strip():
                continue
            try:
                r = json.loads(l)
            except json.JSONDecodeError:
                continue
            s = r.get("call_sequence")
            if s:
                seqs.append(s)
            if len(seqs) >= n:
                return seqs
    return seqs


def bench_ct(seqs, reps=20):
    """Median per-session feature-extraction time (microseconds)."""
    # Warmup
    for s in seqs[:10]:
        extract_features_from_sequence(s)
    per_session = []
    for _ in range(reps):
        t0 = time.perf_counter()
        for s in seqs:
            extract_features_from_sequence(s)
        dt = time.perf_counter() - t0
        per_session.append(dt / len(seqs))
    return statistics.median(per_session)


def bench_cd_ollama(model, host="127.0.0.1:11434", n=10):
    """Median per-call content-DLP latency (seconds) via Ollama HTTP API.
    Run this ON the Mac Studio (localhost Ollama)."""
    import urllib.request
    url = f"http://{host}/api/generate"
    lat = []
    for i in range(n):
        payload = json.dumps({
            "model": model, "prompt": DLP_PROMPT, "stream": False,
            "options": {"temperature": 0, "num_predict": 5},
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=120) as resp:
            _ = json.loads(resp.read())
        dt = time.perf_counter() - t0
        if i > 0:  # drop first (load) call
            lat.append(dt)
    return statistics.median(lat) if lat else float("nan")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "ct"
    if mode == "ct":
        seqs = load_sample_sequences(200)
        ct = bench_ct(seqs)
        print(json.dumps({"C_T_seconds_per_session": ct,
                          "C_T_microseconds": ct * 1e6,
                          "n_sequences": len(seqs),
                          "mean_seq_len": statistics.mean(len(s) for s in seqs)}))
    elif mode == "cd":
        model = sys.argv[2] if len(sys.argv) > 2 else "qwen2.5:32b"
        cd = bench_cd_ollama(model)
        print(json.dumps({"model": model, "C_D_seconds_per_call": cd}))
