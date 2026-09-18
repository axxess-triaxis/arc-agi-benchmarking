# Gemini free-tier ARC-AGI-1 experiments (2026-09-18)

Real, live-run log for benchmarking `gemini-3-6-flash` (model id `gemini-3.6-flash`,
via the existing `GeminiAdapter` / `google-genai` `generate_content` API) against the
actual public ARC-AGI-1 evaluation set, using a free-tier ("AXESS TRiaxis") AI Studio
API key. Written up in full per this program's evidence-chain discipline: every
number below is read off a real `results.json` or a real run log, not estimated.

## Runs, in order

| # | Time (UTC, from log) | What | Config | Real result |
|---|---|---|---|---|
| 1 | ~18:18 | `client.models.generate_content(model='gemini-3.6-flash', contents='Say OK')` ad hoc smoke test | n/a | Succeeded (`OK`) |
| 2 | ~18:19:19–18:19:31 | Single sample task `66e6c45b`, `data/sample/tasks/` | `gemini-3-6-flash` | **1/1 (100%)** — `results/gemini-3-6-flash-test/results.json` |
| 3 | 18:20:35–18:25:32 (297.15s) | 20-task real random sample (seed 42) of the actual ARC-AGI-1 evaluation set (400 tasks, `data/arc-agi-1/`) | `gemini-3-6-flash`, `--max-concurrency 2` | **2/20 (10%)** — `results/gemini-3-6-flash-eval20/results.json`. 42 total attempts, 0 empty-list attempts, real non-zero token usage (avg 289.9 prompt / 61.45 output tokens per task). Correct: `31d5ba1a`, `60a26a3e`. |
| 4 | 18:27:45–18:42:01 (855.88s) | 100-task real sample (seed 42, `gemini_eval_100.txt` — the 20-task list above is its first 20 entries, i.e. a strict superset) | `gemini-3-6-flash`, `--max-concurrency 3` | **0/100 (0%)** — but see "What actually happened" below. Not usable as a capability measurement. |
| 5 | after run 4 | Repeat of the run-1 smoke test, to check whether quota had recovered | n/a | Still blocked: `429 RESOURCE_EXHAUSTED` |

## What actually happened in run 4

Run 4 is **not a real measurement of `gemini-3.6-flash`'s ARC-AGI-1 accuracy**. Every
one of its 214 attempts failed with the same error:

```
429 RESOURCE_EXHAUSTED
* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests
  quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier
  quotaValue: '20'
```

Google's own error identifies this as a **daily** quota (`...PerDayPerProjectPerModel`)
of only **20 `generate_content` requests/day** for `gemini-3.6-flash` on this specific
free-tier project. By the time run 4 started, this session had already made
1 (smoke test) + 2 (run 2) + 42 (run 3) = **45 real requests** against that same
20/day limit -- more than double it.

The reason run 3 (42 requests) itself didn't get blocked, while run 4 was blocked
immediately, is quota-enforcement lag: run 3's calls landed as a fast concurrent
burst and evidently completed before Google's daily-quota counter caught up and
started rejecting; by the ~2-minute gap before run 4 started, enforcement had
caught up, and every subsequent request -- for the rest of the day, confirmed by
the repeated smoke test in row 5 above still failing -- was rejected before any
inference happened. Total attempts (214) and total tasks attempted (100) are
real and reflect exactly what was sent; the 0% score reflects a quota wall, not
100 real reasoning failures.

**Do not read run 4's 0% as "gemini-3.6-flash scored worse at scale."** The only
real capability signal from this session is run 3: **2/20 (10%)** on a real random
ARC-AGI-1 evaluation sample, for $0 (free tier). That is still a small sample and
should not be over-generalized either -- but it is real, and it is a measured
improvement over every open-source-model attempt tried previously on this same
harness (`results/allam-agi1` 0/30, `results/gptoss20b-agi1` 1/20, `results/groq-*`
0/5 to 0/10 -- see those `results.json` files for the raw numbers).

## What this means for a real 50-100 task run

To get a real (non-quota-blocked) larger sample on this exact free-tier project,
one of the following is required:
- Wait for the daily quota to reset (Google's own docs govern the reset window;
  not independently re-verified here) and run a smaller batch that stays under
  ~20 requests/day (e.g. 8-10 tasks at `--num_attempts 2`).
- Spread a 50-100 task run across multiple days, a handful of tasks per day.
- Use a different, less quota-constrained key/project or a paid tier -- out of
  scope for this write-up; flagging as founder-stated-but-unverified-cost if
  pursued, since this repo's other Gemini configs assume paid pricing
  (`pricing.input`/`pricing.output` > 0) that this free-tier project's own
  billing status has not been checked against.

## Reproduction

```bash
# Run 3 (real, 10%):
uv run cli/run_all.py \
  --task_list_file data/sample/task_lists/gemini_eval_20.txt \
  --config gemini-3-6-flash \
  --data_dir data/arc-agi-1/data/evaluation \
  --save_submission_dir submissions/gemini-3-6-flash-eval20 \
  --max-concurrency 2

# Run 4 (quota-blocked, kept only as a documented negative result):
uv run cli/run_all.py \
  --task_list_file data/sample/task_lists/gemini_eval_100.txt \
  --config gemini-3-6-flash \
  --data_dir data/arc-agi-1/data/evaluation \
  --save_submission_dir submissions/gemini-3-6-flash-eval100 \
  --max-concurrency 3

# Scoring (either run):
uv run src/arc_agi_benchmarking/scoring/scoring.py \
  --task_dir data/arc-agi-1/data/evaluation \
  --submission_dir submissions/<run-dir> \
  --results_dir results/<run-dir>
```

`data/sample/task_lists/gemini_eval_100.txt` is a deterministic seed-42 shuffle of
`data/arc-agi-1/data/evaluation`'s 400 task ids (`shuf --random-source=<(yes 42)`);
its first 20 entries are byte-identical to `gemini_eval_20.txt`, so run 3's 20
tasks are a strict subset of run 4's intended 100.

## Planned run 5 (next real data point)

Decision, 2026-09-18: wait for the free-tier daily quota to reset, then run a
real 8-10 task batch (well under the 20/day cap, leaving headroom for retries)
rather than the full 100 at once. `scripts/wait_and_run_gemini_batch.sh`
polls `generate_content` every 5 minutes and, the moment a call succeeds
(quota available again), immediately runs:

```bash
uv run cli/run_all.py \
  --task_list_file data/sample/task_lists/gemini_eval_10.txt \
  --config gemini-3-6-flash \
  --data_dir data/arc-agi-1/data/evaluation \
  --save_submission_dir submissions/gemini-3-6-flash-eval10 \
  --max-concurrency 1
```

`gemini_eval_10.txt` is entries 21-30 of `gemini_eval_100.txt` (same seed-42
ordering) -- deliberately *not* entries 1-20, since those are the tasks run 3
already scored (`gemini_eval_20.txt`). This keeps every task's score unique
across runs: run 3 covers entries 1-20, this planned run covers 21-30, and a
future larger run can pick up at entry 31 -- all consistent subsets of the
same seed-42 100-task ordering, no task ever re-scored. Real result (score,
timing, whether the wait itself needed more than one polling window) will be
appended above as a new row once it actually runs -- not written in advance.
