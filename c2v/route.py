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

import re
from collections import Counter
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


# --- folder descriptions (deterministic, from the vault itself, cached per vault load) -------
ATTACH = "_attachments"
HUB_TYPES = ("course", "project", "hub", "moc", "area", "home", "index")
SPECIFIC_TYPES = {"course": "Course", "project": "Project", "area": "Area"}
LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")
MAX_DESC = 320


def _plain(text: str) -> str:
    return " ".join(LINK.sub(lambda m: m.group(2) or m.group(1), text).replace("**", "").split())


def first_sentence(body: str) -> str:
    """First prose line of a note (headings, list bullets and tasks skipped), wikilinks as plain text."""
    for line in body.splitlines():
        t = line.strip()
        if not t or t.startswith(("#", "---", "- [", "```", ">", "|")):
            continue
        t = _plain(t.lstrip("-* "))
        if t:
            return re.split(r"(?<=[.!?])\s", t, maxsplit=1)[0][:160]
    return ""


def _hub(folder: str, notes: list) -> object | None:
    name = folder.rsplit("/", 1)[-1].lower()
    for n in notes:  # title matches the folder name ("PHYS 230 Electromagnetics/PHYS 230 Electromagnetics.md")
        if n.title.lower() == name:
            return n
    for t in HUB_TYPES:
        hits = sorted((n for n in notes if str(n.frontmatter.get("type", "")).lower() == t), key=lambda n: n.title)
        if hits:
            return hits[0]
    return None


def _mentions(name: str, vault: Vault, k: int = 3) -> list[str]:
    """Notes elsewhere whose title names this folder (or its course/project code, e.g. 'PHYS 230')."""
    keys = {name.lower()}
    if m := re.match(r"([A-Z]{2,5}\s?\d{2,4})\b", name):
        keys.add(m.group(1).lower())
    hits = sorted(n.title for n in vault.notes.values() if any(key in n.title.lower() for key in keys))
    return hits[:k]


def _describe(folder: str, notes: list, children: list[str], vault: Vault | None = None) -> str:
    types = Counter(str(n.frontmatter.get("type", "")).lower() for n in notes)
    main, count = types.most_common(1)[0] if types else ("", 0)
    hub = _hub(folder, notes)
    examples = [n.title for n in sorted(notes, key=lambda n: n.title) if n is not hub][:3]
    kids = [c.rsplit("/", 1)[-1] for c in children]
    parts: list[str] = []
    if main == "concept" and count >= max(3, len(notes) // 2):
        parts.append("One note per reusable concept (a definition or explanation that stands on its own, "
                     "not tied to one course or project).")
    elif main == "session" and count >= max(3, len(notes) // 2):
        parts.append("Dated session logs ('YYYY-MM-DD <course/project> - <what happened>'): a short record of "
                     "one work or study session ('worked on X', what got done, next steps), even when it names a "
                     "course or project. Reference material about the course/project itself goes in its folder.")
    elif main in ("daily", "journal") and count >= max(2, len(notes) // 2):
        parts.append("Daily journal notes, one per date.")
    elif hub is not None:
        htype = str(hub.frontmatter.get("type", "")).lower()
        gist = first_sentence(hub.body)
        if htype in SPECIFIC_TYPES:
            parts.append(f"{SPECIFIC_TYPES[htype]} folder for {hub.title}"
                         + (f" ({gist.rstrip('.')})" if gist else "") + f". File material about {hub.title} here.")
        else:
            parts.append(f"{hub.title} ({htype or 'note'})" + (f": {gist}" if gist else "."))
    if kids:
        parts.append(f"Parent of: {', '.join(kids[:6])}{'...' if len(kids) > 6 else ''}. If the capture is about "
                     f"one of these, choose that subfolder, not this one.")
    if examples:
        parts.append(f"e.g. {'; '.join(examples)}")
    if not parts or (not notes and not kids):
        name = folder.rsplit("/", 1)[-1]
        related = _mentions(name, vault) if vault is not None else []
        parts.insert(0, f"Folder for {name} (no notes inside yet). File material about {name} here."
                     + (f" Related notes elsewhere: {'; '.join(related)}." if related else ""))
    return " ".join(parts)[:MAX_DESC]


def folder_descriptions(vault: Vault) -> dict[str, str]:
    """{folder: one-line description}. Recomputed only when the vault's folders/notes change."""
    sig = (tuple(sorted(vault.folders)), tuple(sorted(str(n.path) for n in vault.notes.values())))
    cached = getattr(vault, "_c2v_folder_desc", None)
    if cached and cached[0] == sig:
        return cached[1]
    by_folder: dict[str, list] = {}
    for n in vault.notes.values():
        by_folder.setdefault(n.folder, []).append(n)
    folders = [f for f in vault.folder_list() if not f.startswith(ATTACH)]
    out = {}
    for f in folders:
        children = [c for c in folders if c.startswith(f + "/") and "/" not in c[len(f) + 1:]]
        out[f] = _describe(f, by_folder.get(f, []), children, vault)
    vault._c2v_folder_desc = (sig, out)
    return out


def folder_guide(vault: Vault) -> str:
    return "\n".join(f"- {f}: {d}" for f, d in folder_descriptions(vault).items())


def folder_options(capture: Capture, vault: Vault) -> dict[str, str]:
    """Folder option -> one-line description built from the vault (hub note, type, examples)."""
    folders = [f for f in vault.folder_list() if not f.startswith("_attachments")]
    if len(folders) + 1 > MAX_CHOICES:
        hits = vault.search(_query(capture), k=50)
        ranked = list(dict.fromkeys(n.folder for n in hits if n.folder))
        # keep folders of search hits first, then their parents, then fill alphabetically
        parents = [p for f in ranked for p in _parents(f)]
        ordered = list(dict.fromkeys(ranked + parents + folders))
        folders = sorted(ordered[: MAX_CHOICES - 1])
    desc = folder_descriptions(vault)
    opts = {f: desc.get(f, "Folder") for f in folders}
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
            "instructions": ("Which existing vault folder should this capture be filed in? Read each folder's "
                             "description. Decide what KIND of note this is, then choose the MOST SPECIFIC "
                             "folder for it: (1) a short log of one work/study session ('worked on X', what got "
                             "done, next steps) goes in the sessions folder even if it names a project; (2) "
                             "material about a named course or project that has its own folder goes in that "
                             "folder, never its parent or index folder; (3) a note explaining one reusable "
                             "concept on its own goes in the concepts folder."),
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
    # Video: the timestamped transcript already carries speech + on-screen content; re-sending the
    # video would double the upload and the video-token cost for no routing gain.
    if capture.media_kind not in (MediaKind.text, MediaKind.video) and src.exists():
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
    if capture.segments:  # linking each part of a video to the right notes is Neon's job
        decision.escalate = True
        decision.reason += "; video: Neon builds the linked timeline"
    return decision


def _fake_answer(choice: str, conf: float) -> RoutedAnswer:  # for tests / dry runs
    return RoutedAnswer(choice=choice, confidence=conf, probabilities={choice: conf})
