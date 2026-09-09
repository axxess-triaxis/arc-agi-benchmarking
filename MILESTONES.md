# Milestones

Real, evidence-backed results from running this harness against Groq's free-tier
open-weight models. Every entry here is a directly-observed result (exact command,
exact score, exact date) — not a projection or an assumption.

## 2026-09-09 — AGI-2 public demo: 100% (2/2) on first attempt

**Result:** `groq-allam-2-7b` scored **100.00% (2.00/2)** on the bundled AGI-2
public sample-task demo — both tasks solved correctly on the first real attempt.

**Command:**
```bash
uv run cli/run_all.py --config groq-allam-2-7b \
  --data_dir data/sample/tasks \
  --save_submission_dir submissions/sample-demo \
  --logs-base-dir logs/sample-demo
```

**Scoring:**
```bash
uv run src/arc_agi_benchmarking/scoring/scoring.py \
  --task_dir data/sample/tasks \
  --submission_dir submissions/sample-demo \
  --results_dir results/sample-demo
```

**Model:** `allam-2-7b` (SDAIA, open-weight, 4096-token context window), hosted
free on Groq. Config: `src/arc_agi_benchmarking/models.yml` → `groq-allam-2-7b`.

**Stats:** 4 total attempts, 718 avg total tokens/task, $0.00 cost, 0% empty-list
rate, ~113s avg duration/task.

**Context — what this result does and doesn't mean:**
- This is the small, bundled 2-task demo set (`data/sample/tasks`) that this
  repo's own README uses as its quickstart example — the same small public
  demo most people report a first result against, not the full evaluation set.
- On the **real, full ARC-AGI-2 public evaluation set** (120 tasks,
  `data/arc-agi/data/evaluation`, cloned from `arcprize/ARC-AGI-2`), the same
  model scored **0% on every attempt tried so far** (a 10-task batch and
  several individual tests, all real, scored, $0 cost). The demo tasks are
  simpler, hand-picked puzzles; the real evaluation set is deliberately hard.
- Read this as: **pipeline and model are proven to work correctly end-to-end**
  (real API calls, real scoring, real answers) — not as evidence that
  `allam-2-7b` can solve ARC-AGI-2 in general. It cannot, at least not yet.

## 2026-09-09 — AGI-3 baseline: 0/7 levels, 48 real actions (`ls20`)

**Result:** `groq-gpt-oss-20b` on the `ls20` public demo game — **score 0.0,
0/7 levels completed, 48 total actions, 4 resets**, over ~24 minutes. Every
action was mechanically valid (real frame parsed, real action chosen and
sent) — the run ended because it hit `gpt-oss-20b`'s own daily token quota
(199,711/200,000 TPD), not because it exhausted level 1's own 110-action
budget (it used 48 of those).

**Command (from `arc-agi-3-benchmarking`):**
```bash
uv run main.py --game=ls20 --config=groq-gpt-oss-20b
```

**Scorecard:** https://arcprize.org/scorecards/04f5c3cf-2096-44d9-b62f-2ee00b44de87

**How this config was reached — three models tried, in order, each ruled out
or confirmed for a distinct, live-verified reason:**
1. `groq-allam-2-7b` — real context window is only 4096 tokens (confirmed via
   Groq's own model API); `ls20`'s first-turn frame alone exceeds it, so
   every attempt failed with `context_length_exceeded` before taking a
   single action.
2. `groq-gpt-oss-120b` — works mechanically (18 real actions taken in an
   earlier attempt the same day) but its daily quota was already exhausted
   from AGI-2 testing earlier, so a fresh attempt only got 3 actions before
   hitting the same wall.
3. `groq-qwen3-8-27b` — huge 131K context window, but Groq enforces a
   separate input-tokens-per-minute cap of 7,000 for this model specifically;
   `ls20`'s first-turn frame needs 8,894 input tokens, exceeding it on the
   very first request regardless of pacing.
4. `groq-gpt-oss-20b` (used for this result) — same model family as
   `gpt-oss-120b`, but its own independent 200,000 TPD quota pool, which
   still had headroom. Config added to
   `arc-agi-3-benchmarking/benchmarking/model_configs.yaml`.

**Honest read:** the AGI-3 pipeline is proven to work end-to-end (real frames,
real actions, real quota tracking) — this is not a crash or a fabricated
number. But the model has not demonstrated it can solve `ls20`'s level 1
within the actions it got; it explored and reset several times without
finding the mechanic. Same evidentiary bar as the AGI-2 numbers above: a real
baseline, not a claim of capability beyond what was actually observed.

**Next step:** re-attempt with more of `gpt-oss-20b`'s daily quota once it
recovers (rolling 24h window), or try a fresh model/day for a longer,
uninterrupted run at more of level 1's 110-action budget.
