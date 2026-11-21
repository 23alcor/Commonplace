"""LANE C. Managed Agent verifier (targets the $5K Best use of Managed Agents prize).

TODO(lane-c):
- Start once per run: beta_client.interactions.create(agent=MODEL_IDS["agent"], environment="remote",
  agent_config={"type": "antigravity", "model": "gemini-4-neon", "max_total_tokens": 100000},
  input=...). Give the sandbox this repo (c2v/ + the vault copy) via the repository/source option in
  the Managed Agents docs, or by pasting the files on the first turn. Keep run.environment_id.
- Each fix: previous_interaction_id + environment=environment_id, input = draft JSON + issues +
  "write draft.json, run `python -m c2v.verify --vault <vault> --draft draft.json`, fix the draft until
  exit code 0, print the final draft JSON". Parse it back into NoteDraft and re-verify locally.
- Log every agent turn (tokens, seconds, issues before/after). These logs become the demo's
  "the agent checked its own work" slide.
"""
from __future__ import annotations

from .schemas import NoteDraft, VerifyReport
from .vault import Vault


def agent_fix(draft: NoteDraft, report: VerifyReport, vault: Vault) -> tuple[NoteDraft, VerifyReport]:
    raise NotImplementedError("lane-c: run the Antigravity managed agent verify-fix loop")
