"""LANE A. Router: Gemini Decision 1 (Decisions API) picks type, folder and merge target.

TODO(lane-a):
- One beta_client.decisions.create call with three questions:
  * note_type: choice over NOTE_TYPES (+ "other")
  * folder: choice over vault.folder_list() (+ "other"). Max 255 choices; if the vault has more,
    pre-filter with vault.search(capture.summary) to the top folders.
  * merge_target: choice over top-k candidate note titles from vault.search(...) + "new"
- Input = the original media (image/audio/pdf) + capture.transcript as text.
- escalate = any confidence < ROUTE_CONFIDENCE_MIN, or capture.legibility < 0.6, or a choice == "other".
- Keep the probabilities: Neon gets them as context when escalated, and the eval logs them.
"""
from __future__ import annotations

from .config import ROUTE_CONFIDENCE_MIN
from .schemas import Capture, RoutedAnswer, RoutingDecision
from .vault import Vault

NOTE_TYPES = {
    "idea": "A new idea, concept or brainstorm",
    "task": "Something to do, with or without a deadline",
    "meeting": "Notes from a meeting, call or conversation",
    "class": "Lecture or course material",
    "project-update": "Progress, decision or status on an existing project",
    "reference": "Facts, specs, links or how-to to keep for later",
    "journal": "Personal reflection or daily log",
    "other": "None of the above, or unreadable",
}


def needs_escalation(d: RoutingDecision, capture: Capture) -> bool:
    answers = [d.note_type, d.folder] + ([d.merge_target] if d.merge_target else [])
    return (
        any(a.confidence < ROUTE_CONFIDENCE_MIN for a in answers)
        or capture.legibility < 0.6
        or any(a.choice == "other" for a in answers)
    )


def route(capture: Capture, vault: Vault) -> RoutingDecision:
    raise NotImplementedError("lane-a: call gemini-decision-1 here")


def _fake_answer(choice: str, conf: float) -> RoutedAnswer:  # for tests / dry runs
    return RoutedAnswer(choice=choice, confidence=conf, probabilities={choice: conf})
