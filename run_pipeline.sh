#!/usr/bin/env bash
# run_pipeline.sh — full X-program API pipeline, 2-key parallel, correct sequencing.
# KEY = FRONTIER_API_KEY (gpt-4.1 cells); KEY2 = FRONTIER_API_KEY_2 (gpt-4o cells).
set -u
# Resolve the repository root from this script's own location rather than hardcoding an
# absolute path. The previous `cd /Users/<user>/projects/arbitration` leaked the
# generating machine's filesystem layout into a published artifact and tripped the
# fail-closed absolute-path guard in scripts/prepare_public_release.py.
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY=.venv/bin/python
K1="$FRONTIER_API_KEY"
K2="$FRONTIER_API_KEY_2"
LOG=/tmp/xprog
mkdir -p $LOG
run41(){ FRONTIER_API_KEY="$K1" $PY "$@"; }   # gpt-4.1 on key 1
run4o(){ FRONTIER_API_KEY="$K2" $PY "$@"; }   # gpt-4o on key 2

# ── STAGE 0: mandatory fail-closed pre-flight ────────────────────────────────
# PROGRAM_EXECUTION_ADDENDUM specifies a committed pre-flight validate_all.py run
# before any confirmatory/X5/X6 collection. This gate was missing from the pipeline
# until 2026-09-19; collection could start with unvalidated frozen content. Now
# fail-closed: a non-zero exit aborts before a single API call is made.
echo "[$(date +%H:%M:%S)] STAGE 0: pre-flight validation (fail-closed)"
if ! $PY paper_a/validate_all.py > $LOG/validate_all.log 2>&1; then
    echo "[$(date +%H:%M:%S)] ABORT: validate_all.py FAILED — see $LOG/validate_all.log" >&2
    tail -30 $LOG/validate_all.log >&2
    exit 1
fi
echo "[$(date +%H:%M:%S)] pre-flight OK"

echo "[$(date +%H:%M:%S)] STAGE 1: B+ pilot (both models parallel)"
run41 paper_a/probe_bplus.py --model gpt-4.1 --phase pilot > $LOG/bplus_41.log 2>&1 &
run4o paper_a/probe_bplus.py --model gpt-4o   --phase pilot > $LOG/bplus_4o.log 2>&1 &
wait
echo "[$(date +%H:%M:%S)] B+ pilot done -> freeze"
$PY paper_a/probe_bplus.py --freeze > $LOG/bplus_freeze.log 2>&1
echo "[$(date +%H:%M:%S)] STAGE 1b: B+ confirmatory (both models parallel)"
run41 paper_a/probe_bplus.py --model gpt-4.1 --phase confirmatory > $LOG/bplus_conf_41.log 2>&1 &
run4o paper_a/probe_bplus.py --model gpt-4o   --phase confirmatory > $LOG/bplus_conf_4o.log 2>&1 &
wait
$PY paper_a/probe_bplus.py --score  > $LOG/bplus_score.log 2>&1

echo "[$(date +%H:%M:%S)] STAGE 2: X1 + X4 confirmatory (4 streams: {x1,x4}x{41,4o})"
run41 paper_a/probe_x1.py --model gpt-4.1 > $LOG/x1_41.log 2>&1 &
run4o paper_a/probe_x1.py --model gpt-4o  > $LOG/x1_4o.log 2>&1 &
run41 paper_a/probe_x4.py --model gpt-4.1 > $LOG/x4_41.log 2>&1 &
run4o paper_a/probe_x4.py --model gpt-4o  > $LOG/x4_4o.log 2>&1 &
wait
echo "[$(date +%H:%M:%S)] X1/X4 nopoison controls"
run41 paper_a/probe_x1.py --model gpt-4.1 --nopoison > $LOG/x1np_41.log 2>&1 &
run4o paper_a/probe_x1.py --model gpt-4o  --nopoison > $LOG/x1np_4o.log 2>&1 &
run41 paper_a/probe_x4.py --model gpt-4.1 --nopoison > $LOG/x4np_41.log 2>&1 &
run4o paper_a/probe_x4.py --model gpt-4o  --nopoison > $LOG/x4np_4o.log 2>&1 &
wait

echo "[$(date +%H:%M:%S)] STAGE 3: X5 adaptive + X6 breadth (parallel)"
run41 paper_a/probe_x5.py --model gpt-4.1 > $LOG/x5_41.log 2>&1 &
run4o paper_a/probe_x5.py --model gpt-4o  > $LOG/x5_4o.log 2>&1 &
run41 paper_a/probe_x6.py --sweep A --model gpt-4.1 > $LOG/x6A.log 2>&1 &
run4o paper_a/probe_x6.py --sweep M --arch faiss    > $LOG/x6M.log 2>&1 &
wait

echo "[$(date +%H:%M:%S)] STAGE 4: score everything"
$PY paper_a/score_xprogram.py --exp all > $LOG/score_all.log 2>&1
echo "[$(date +%H:%M:%S)] PIPELINE DONE"
