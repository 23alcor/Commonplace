"""LANE A. Router: Gemini Decision 1 (Decisions API) picks type, folder and merge target.

One job: calibrated routing. A single `beta_client.decisions.create` call answers three choice
questions against the original media + Hydrogen's transcript:
  * note_type    over NOTE_TYPES (includes "other")
  * folder       over the vault's real folders + "other" (pre-filtered when > 255 options)
  * merge_target over the top-k candidate note titles + "new"
Escalate to Neon when any confidence < ROUTE_CONFIDENCE_MIN, legibility < 0.6, or a choice is
"other". Probabilities are kept on every answer: Neon reads them, the eval logs them.
"""
from __future__ import annotations

from pathlib import Path

from .config import MODEL_IDS, ROUTE_CONFIDENCE_MIN
from .schemas import Capture, MediaKind, RoutedAnswer, RoutingDecision
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
MAX_CHOICES = 255
MERGE_CANDIDATES = 6
NEW = "new"
OTHER = "other"
LEGIBILITY_MIN = 0.6


def needs_escalation(d: RoutingDecision, capture: Capture) -> bool:
    answers = [d.note_type, d.folder] + ([d.merge_target] if d.merge_target else [])
    return (
        any(a.confidence < ROUTE_CONFIDENCE_MIN for a in answers)
        or capture.legibility < LEGIBILITY_MIN
        or any(a.choice == OTHER for a in answers)
    )


def escalation_reason(d: RoutingDecision, capture: Capture) -> str:
    named = {"note_type": d.note_type, "folder": d.folder}
    if d.merge_target:
        named["merge_target"] = d.merge_target
    bits = [f"{k}={a.choice} ({a.confidence:.2f} < {ROUTE_CONFIDENCE_MIN})"
            for k, a in named.items() if a.confidence < ROUTE_CONFIDENCE_MIN]
    bits += [f"{k}=other" for k, a in named.items() if a.choice == OTHER]
    if capture.legibility < LEGIBILITY_MIN:
        bits.append(f"legibility {capture.legibility:.2f} < {LEGIBILITY_MIN}")
    return "escalate: " + "; ".join(bits) if bits else "confident: all answers >= threshold"


# --- question building (pure, testable) -----------------------------------------------------
def _query(capture: Capture) -> str:
    return " ".join([capture.summary, *capture.key_terms, capture.transcript[:500]])


def folder_options(capture: Capture, vault: Vault) -> dict[str, str]:
    """Folder option -> description (a few note titles in it, so the router knows what lives there)."""
    folders = vault.folder_list()
    if len(folders) + 1 > MAX_CHOICES:
        hits = vault.search(_query(capture), k=50)
        ranked = list(dict.fromkeys(n.folder for n in hits if n.folder))
        # keep folders of search hits first, then their parents, then fill alphabetically
        parents = [p for f in ranked for p in _parents(f)]
        ordered = list(dict.fromkeys(ranked + parents + folders))
        folders = sorted(ordered[: MAX_CHOICES - 1])
    by_folder: dict[str, list[str]] = {}
    for n in vault.notes.values():
        by_folder.setdefault(n.folder, []).append(n.title)
    opts = {}
    for f in folders:
        titles = sorted(by_folder.get(f, []))[:5]
        opts[f] = f"Contains: {', '.join(titles)}" if titles else "Folder (no notes directly inside)"
    opts[OTHER] = "No existing folder fits"
    return opts


def _parents(folder: str) -> list[str]:
    parts = folder.split("/")
    return ["/".join(parts[:i]) for i in range(len(parts) - 1, 0, -1)]


def merge_options(capture: Capture, vault: Vault) -> dict[str, str]:
    opts = {}
    for n in vault.search(_query(capture), k=MERGE_CANDIDATES):
        gist = " ".join(n.body.split())[:160]
        opts[n.title] = f"[{n.folder or '/'}] {gist}"
    opts[NEW] = "This capture is new material and should become its own note"
    return opts


def build_questions(capture: Capture, vault: Vault) -> dict:
    return {
        "note_type": {
            "type": "choice",
            "instructions": "What kind of note is this capture? Pick the single best type.",
            "criteria": NOTE_TYPES,
        },
        "folder": {
            "type": "choice",
            "instructions": ("Which existing vault folder should this capture be filed in? Prefer the most "
                             "specific folder whose notes cover the same course, project or topic."),
            "criteria": folder_options(capture, vault),
        },
        "merge_target": {
            "type": "choice",
            "instructions": ("Should this capture be appended to an existing note, or become a new note? "
                             "Pick an existing note only if the capture is clearly an update to that exact "
                             "note's subject (same meeting, same running log, same spec). Otherwise 'new'."),
            "criteria": merge_options(capture, vault),
        },
    }


def build_input(capture: Capture, client=None) -> list[dict]:
    text = (f"CAPTURE ({capture.media_kind.value}) transcribed by the transcriber:\n"
            f"SUMMARY: {capture.summary}\nKEY TERMS: {', '.join(capture.key_terms)}\n"
            f"LEGIBILITY: {capture.legibility:.2f}\nTRANSCRIPT:\n{capture.transcript}")
    parts: list[dict] = [{"type": "text", "text": text}]
    src = Path(capture.source_path)
    if capture.media_kind is not MediaKind.text and src.exists():
        from .transcribe import media_part

        parts.insert(0, media_part(src, client))
    return parts


def to_routed(answer, valid: set[str] | None = None) -> RoutedAnswer:
    probs = {k: float(v) for k, v in (getattr(answer, "probabilities", None) or {}).items()}
    choice = answer.choice
    if valid is not None and choice not in valid:  # defensive: never pass an unknown option on
        choice = OTHER if OTHER in valid else NEW
    return RoutedAnswer(choice=choice, confidence=float(answer.confidence), probabilities=probs)


# --- the call -------------------------------------------------------------------------------
def route(capture: Capture, vault: Vault, beta_client=None, client=None) -> RoutingDecision:
    if beta_client is None:
        from .transcribe import _default_clients

        client, beta_client = _default_clients()
    questions = build_questions(capture, vault)
    d = beta_client.decisions.create(
        model=MODEL_IDS["router"], input=build_input(capture, client), questions=questions,
    )
    ans = d.answers or {}
    nt = to_routed(ans["note_type"], set(NOTE_TYPES))
    fo = to_routed(ans["folder"], set(questions["folder"]["criteria"]))
    mt = to_routed(ans["merge_target"], set(questions["merge_target"]["criteria"])) if "merge_target" in ans else None
    decision = RoutingDecision(note_type=nt, folder=fo, merge_target=mt)
    decision.escalate = needs_escalation(decision, capture)
    decision.reason = escalation_reason(decision, capture)
    return decision


def _fake_answer(choice: str, conf: float) -> RoutedAnswer:  # for tests / dry runs
    return RoutedAnswer(choice=choice, confidence=conf, probabilities={choice: conf})
