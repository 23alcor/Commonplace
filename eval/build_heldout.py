"""LANE B. Build the held-out set with ground truth for free.

TODO(lane-b):
- Pick N notes (default 30) from VAULT_PATH with seed=42: prefer notes with >=2 outgoing links that
  resolve and a body of >=60 words. Stratify across folders.
- For each: record truth = {case_id, title, folder, links (resolved only)} in eval/cases/cases.jsonl.
- Build an eval vault copy (eval/work/vault) with those notes REMOVED, so the system can't find them.
- Hand each case to render_media.py to make its messy capture.
- eval/work/ and eval/cases/ from a private vault are gitignored. Only commit results/summary.
"""
