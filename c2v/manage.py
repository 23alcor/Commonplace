"""LANE A. Vault manager: Gemini 4 Neon writes the final NoteDraft.

TODO(lane-a):
- Input: Capture, RoutingDecision (with probabilities), vault.describe(), and the full text of the
  top-k candidates from vault.search(capture.summary + key_terms).
- Output (structured): NoteDraft. Links must be titles that exist (verify.py will check).
- Frontmatter must include: type, created (ISO date), source (media kind), tags.
- If the router was confident, you may skip Neon and build the draft from the router's choices +
  capture (the fast path). Log which path was taken.
- On a VerifyReport with issues, call Neon again with the issues (previous_interaction_id) to repair.
"""
from __future__ import annotations

from .schemas import Capture, NoteDraft, RoutingDecision, VerifyReport
from .vault import Vault


def draft_note(capture: Capture, routing: RoutingDecision, vault: Vault) -> NoteDraft:
    raise NotImplementedError("lane-a: call gemini-4-neon here")


def repair(draft: NoteDraft, report: VerifyReport, vault: Vault) -> NoteDraft:
    raise NotImplementedError("lane-a: ask gemini-4-neon to fix the listed issues")
