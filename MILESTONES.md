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

## Pending — AGI-3 baseline

**Status:** Not yet established. `allam-2-7b`'s 4096-token context window is too
small for even one ARC-AGI-3 game turn (confirmed live via Groq's own model API
and a real `ls20` run — `context_length_exceeded` on turn 1, every retry).
`groq-gpt-oss-120b` works mechanically instead (18 real actions taken on `ls20`
in ~3 minutes, actively parsing frames and choosing valid actions) but hit
Groq's shared daily token quota (200,000 TPD) mid-run before completing even
level 1 (18/22 baseline actions).

**Next step:** re-attempt a full `ls20` run once the daily quota has recovered,
to get a real baseline score (not just "it can take actions" — an actual
completion/score number). Quota is a rolling 24-hour window; a fresh attempt is
worth trying again after several hours, checked live rather than assumed.
