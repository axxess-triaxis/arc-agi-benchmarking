#!/usr/bin/env bash
# Polls the free-tier Gemini quota every 5 minutes; the moment a real
# generate_content call succeeds, runs the real 10-task ARC-AGI-1 batch
# (data/sample/task_lists/gemini_eval_10.txt) and scores it, then exits.
# See docs/gemini_free_tier_experiments.md for why this exists: the
# 20/day free-tier quota for gemini-3.6-flash was exhausted 2026-09-18.
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
source .env
set +a

echo "$(date -u '+%Y-%m-%d %H:%M:%S') UTC -- starting quota poll (every 5 min)"

while true; do
  if uv run python -c "
from google import genai
client = genai.Client(api_key='${GOOGLE_API_KEY}')
client.models.generate_content(model='gemini-3.6-flash', contents='Say OK')
" >/tmp/quota_check.log 2>&1; then
    echo "$(date -u '+%Y-%m-%d %H:%M:%S') UTC -- quota available, starting real 10-task run"
    break
  fi
  echo "$(date -u '+%Y-%m-%d %H:%M:%S') UTC -- still quota-blocked, retrying in 5 min"
  sleep 300
done

uv run cli/run_all.py \
  --task_list_file data/sample/task_lists/gemini_eval_10.txt \
  --config gemini-3-6-flash \
  --data_dir data/arc-agi-1/data/evaluation \
  --save_submission_dir submissions/gemini-3-6-flash-eval10 \
  --max-concurrency 1

echo "$(date -u '+%Y-%m-%d %H:%M:%S') UTC -- run finished, scoring"

uv run src/arc_agi_benchmarking/scoring/scoring.py \
  --task_dir data/arc-agi-1/data/evaluation \
  --submission_dir submissions/gemini-3-6-flash-eval10 \
  --results_dir results/gemini-3-6-flash-eval10

echo "$(date -u '+%Y-%m-%d %H:%M:%S') UTC -- done, see results/gemini-3-6-flash-eval10/results.json"
