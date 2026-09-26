#!/usr/bin/env bash
# run_macstudio_queue.sh — X6 open-weight interaction sweep (Regime A), QUEUED after API pipeline.
set -u
# Resolve the repository root from this script's own location rather than hardcoding an
# absolute path (see the matching note in run_pipeline.sh).
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY=.venv/bin/python
LOG=/tmp/xprog
PIPE_PID="${1:-}"

echo "[$(date +%H:%M:%S)] MAC-STUDIO QUEUE: waiting for API pipeline (PID $PIPE_PID) to finish..."
if [ -n "$PIPE_PID" ]; then
  while kill -0 "$PIPE_PID" 2>/dev/null; do sleep 60; done
fi
echo "[$(date +%H:%M:%S)] API pipeline done. Opening SSH tunnel to Studio Ollama."

# tunnel local :11436 -> Studio 127.0.0.1:11434
pkill -f "ssh.*11436:127.0.0.1:11434" 2>/dev/null; sleep 1
# Remote Ollama host, e.g. user@host. Supplied by the operator; never hardcoded.
: "${OLLAMA_SSH_TARGET:?set OLLAMA_SSH_TARGET=user@host for the remote Ollama machine}"
ssh -f -N -L 11436:127.0.0.1:11434 "$OLLAMA_SSH_TARGET"
sleep 3
# Ollama's OpenAI-compatible endpoint is /v1
export FRONTIER_API_BASE="http://127.0.0.1:11436/v1"
export FRONTIER_API_KEY="ollama"   # Ollama ignores the key

echo "[$(date +%H:%M:%S)] X6 interaction sweep MA: qwen2.5:32b x {faiss,bm25,summary}"
for arch in faiss bm25 summary; do
  $PY paper_a/probe_x6.py --arch "$arch" --model qwen2.5:32b --armset both > $LOG/x6MA_${arch}.log 2>&1
done

echo "[$(date +%H:%M:%S)] tearing down tunnel + re-scoring"
pkill -f "ssh.*11436:127.0.0.1:11434" 2>/dev/null
unset FRONTIER_API_BASE FRONTIER_API_KEY
$PY paper_a/score_xprogram.py --exp all > $LOG/score_final.log 2>&1
echo "[$(date +%H:%M:%S)] MAC-STUDIO QUEUE DONE"
