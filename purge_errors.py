"""purge_errors.py — strip error-record lines from result JSONL so resume retries them."""
import json, sys, glob
from pathlib import Path

for exp in sys.argv[1:]:
    for f in sorted(glob.glob(f"paper_a/results/{exp}/*.jsonl")):
        recs = [l for l in open(f) if l.strip()]
        good = [l for l in recs if not json.loads(l).get("error")]
        if len(good) != len(recs):
            Path(f).write_text("".join(good))
            print(f"{f.split('/')[-1]}: {len(recs)} -> {len(good)} good (stripped {len(recs)-len(good)} errors)")
        else:
            print(f"{f.split('/')[-1]}: {len(good)} good (clean)")
