"""LANE B. Run baseline vs system on every held-out case and write results.

TODO(lane-b):
- For each case: run baseline.py and c2v.pipeline.file_capture(..., dry_run=True) against the eval vault.
- Score both with eval/score.py, plus latency and path_taken (auto / escalated / agent_fixed).
- Write eval/results/results.jsonl, eval/results/summary.json and eval/results/summary.md:
  a table (baseline vs system: folder acc, link P/R/F1, verify pass rate, median latency), then
  failures grouped by media kind and difficulty knob, plus the 5 worst cases with a short reason each.
- Run cases in parallel (ThreadPoolExecutor, ~6 workers) and resume from existing results on restart.
- Make one PNG chart (matplotlib) for the README and demo: accuracy vs noise/blur, baseline vs system.
"""
