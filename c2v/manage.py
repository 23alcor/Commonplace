"""LANE A. Vault manager: Gemini 4 Neon writes the final NoteDraft.

One job: turn a routed capture into a vault-correct note. Two paths:
  * fast path (router confident): build the draft deterministically from the router's choices.
  * escalated (router unsure): Neon gets the capture, the router's probabilities, the vault map and
    the full text of the top candidates, and answers with a structured NoteDraft.
repair(): Neon gets verify.py's issues and fixes the draft, chained with previous_interaction_id
when the draft came from Neon. If Neon is unreachable, a deterministic fix keeps the pipeline alive.
"""
from __future__ import annotations

import datetime as dt
import json
import re

from .config import MODEL_IDS
from .route import NEW, OTHER
from .schemas import Capture, NoteDraft, RoutingDecision, VerifyReport
from .vault import Vault
from .verify import ALLOWED_TYPES

FAST_LINKS = 3
CANDIDATES = 6
BAD_TITLE_CHARS = re.compile(r'[\\/:*?"<>|#^\[\]]')

# draft identity -> Neon interaction id, so repair() can chain on the same conversation
_INTERACTIONS: dict[int, str] = {}

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Short, specific note title. No / \\ : * ? \" < > | # ^ [ ]"},
        "folder": {"type": "string", "description": "Exactly one of the vault FOLDERS listed"},
        "frontmatter": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": sorted(ALLOWED_TYPES)},
                "created": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "source": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["type", "created", "source", "tags"],
        },
        "body": {"type": "string", "description": "Markdown body. No frontmatter, no Related section."},
        "links": {"type": "array", "items": {"type": "string"},
                  "description": "Exact titles of EXISTING notes to link; never invent titles"},
        "merge_into": {"type": "string", "description": "Existing note title to append to, or empty for a new note"},
    },
    "required": ["title", "folder", "frontmatter", "body", "links", "merge_into"],
}

SYSTEM = """You are the vault manager for an Obsidian vault. You turn one transcribed capture into
one clean note that fits the vault. Rules:
- folder MUST be copied exactly from the FOLDERS list.
- links MUST be copied exactly from existing note titles (CANDIDATES or NOTES list). Link only notes
  that are genuinely related. Never invent a title.
- title must not already exist in the vault unless you set merge_into to that note.
- merge_into: an existing note title only when this capture is an update to that exact note; else "".
  A merged body is appended under an "## Update" heading, so start it with a dated line, not a heading,
  and use ### for any sub-headings.
- frontmatter.type is one of: """ + ", ".join(sorted(ALLOWED_TYPES)) + """.
- body: clean markdown. Keep the transcript's facts, names and numbers; fix obvious transcription
  noise; turn action items into "- [ ]" checkboxes. Do not add a Related/links section (added later).
- The router's probabilities show where it was unsure; resolve that ambiguity using the vault."""


def _default_client():
    from .transcribe import _default_clients

    return _default_clients()[0]


def _today() -> str:
    return dt.date.today().isoformat()


def _tag(term: str) -> str:
    return re.sub(r"[^a-z0-9/_-]+", "-", term.lower()).strip("-")


def clean_title(raw: str, vault: Vault, max_words: int = 8) -> str:
    title = BAD_TITLE_CHARS.sub(" ", raw)
    title = " ".join(title.split()[:max_words]).strip(" .-") or "Untitled Capture"
    if vault.resolve(title) is None:
        return title
    for i in range(2, 100):
        cand = f"{title} {i}"
        if vault.resolve(cand) is None:
            return cand
    return f"{title} {dt.datetime.now():%H%M%S}"


def _title_from_capture(capture: Capture) -> str:
    first = re.split(r"(?<=[.!?])\s|\n", capture.summary.strip(), maxsplit=1)[0]
    return first or capture.transcript.strip().split("\n", 1)[0]


# --- fast path ------------------------------------------------------------------------------
def fast_draft(capture: Capture, routing: RoutingDecision, vault: Vault) -> NoteDraft:
    """Deterministic draft from the router's choices. Used when the router is confident."""
    ntype = routing.note_type.choice if routing.note_type.choice in ALLOWED_TYPES else "other"
    folder = routing.folder.choice if routing.folder.choice in vault.folders else ""
    merge = None
    if routing.merge_target and routing.merge_target.choice not in (NEW, OTHER):
        merge = vault.resolve(routing.merge_target.choice)

    query = " ".join([capture.summary, *capture.key_terms])
    links = [n.title for n in vault.search(query, k=FAST_LINKS + 1) if n.title != merge][:FAST_LINKS]

    body = [capture.summary.strip(), "", "## Transcript", capture.transcript.strip()]
    if capture.action_items:
        body += ["", "## Action items", *[f"- [ ] {a}" for a in capture.action_items]]
    if capture.notes:
        body += ["", f"> [!note] Transcriber: {capture.notes}"]

    return NoteDraft(
        title=merge or clean_title(_title_from_capture(capture), vault),
        folder=vault.notes[merge].folder if merge else folder,
        frontmatter={"type": ntype, "created": _today(), "source": capture.media_kind.value,
                     "tags": [t for t in (_tag(k) for k in capture.key_terms) if t]},
        body="\n".join(body),
        links=links,
        merge_into=merge,
    )


# --- Neon path ------------------------------------------------------------------------------
def _routing_context(routing: RoutingDecision) -> str:
    def fmt(name, a):
        if a is None:
            return f"{name}: (not asked)"
        top = sorted(a.probabilities.items(), key=lambda kv: -kv[1])[:4]
        return f"{name}: {a.choice} (conf {a.confidence:.2f}; top: " + ", ".join(f"{k}={v:.2f}" for k, v in top) + ")"

    return "\n".join([fmt("note_type", routing.note_type), fmt("folder", routing.folder),
                      fmt("merge_target", routing.merge_target), f"router says: {routing.reason}"])


def build_prompt(capture: Capture, routing: RoutingDecision, vault: Vault) -> str:
    query = " ".join([capture.summary, *capture.key_terms])
    cands = vault.search(query, k=CANDIDATES)
    cand_text = "\n\n".join(f"### {n.title}  [{n.folder or '/'}]\n{n.body.strip()[:1500]}" for n in cands)
    return "\n\n".join([
        f"TODAY: {_today()}",
        f"CAPTURE ({capture.media_kind.value}, legibility {capture.legibility:.2f})\n"
        f"SUMMARY: {capture.summary}\nKEY TERMS: {', '.join(capture.key_terms)}\n"
        f"ACTION ITEMS: {json.dumps(capture.action_items)}\nTRANSCRIBER NOTES: {capture.notes or '-'}\n"
        f"TRANSCRIPT:\n{capture.transcript}",
        f"ROUTER (calibrated probabilities):\n{_routing_context(routing)}",
        f"VAULT MAP:\n{vault.describe()}",
        f"CANDIDATES (full text of the most related notes):\n{cand_text or '(none)'}",
        "Write the NoteDraft.",
    ])


def parse_draft(raw: str) -> NoteDraft:
    data = json.loads(raw)
    data["merge_into"] = data.get("merge_into") or None
    return NoteDraft(**data)


def _neon(input_, client, previous_id: str | None = None):
    kw = dict(
        model=MODEL_IDS["manager"],
        input=input_,
        system_instruction=SYSTEM,
        generation_config={"thinking_level": "medium"},
        response_format={"type": "text", "mime_type": "application/json", "schema": DRAFT_SCHEMA},
    )
    if previous_id:
        kw["previous_interaction_id"] = previous_id
    r = client.interactions.create(**kw)
    draft = parse_draft(r.output_text)
    _INTERACTIONS[id(draft)] = r.id
    return draft


def neon_draft(capture: Capture, routing: RoutingDecision, vault: Vault, client=None) -> NoteDraft:
    return _neon(build_prompt(capture, routing, vault), client or _default_client())


def draft_note(capture: Capture, routing: RoutingDecision, vault: Vault, client=None) -> NoteDraft:
    if not routing.escalate:
        return fast_draft(capture, routing, vault)
    return neon_draft(capture, routing, vault, client)


# --- repair ---------------------------------------------------------------------------------
def repair_prompt(draft: NoteDraft, report: VerifyReport, vault: Vault, chained: bool) -> str:
    issues = "\n".join(f"- {i.code}: {i.detail}" for i in report.issues)
    parts = [f"The verifier rejected the draft. Fix every issue and return the full corrected NoteDraft.\n"
             f"ISSUES:\n{issues}",
             f"DRAFT:\n{draft.model_dump_json(indent=1)}"]
    if not chained:  # fresh conversation: give Neon the vault map it would otherwise already have
        parts.append(f"VAULT MAP:\n{vault.describe()}")
    return "\n\n".join(parts)


def mechanical_fix(draft: NoteDraft, vault: Vault) -> NoteDraft:
    """Deterministic last resort: drop what can't be fixed, fill what's missing."""
    d = draft.model_copy(deep=True)
    if d.merge_into and vault.resolve(d.merge_into) is None:
        d.merge_into = None
    if d.folder not in vault.folders:
        d.folder = next((f for f in sorted(vault.folders, key=len, reverse=True)
                         if f and d.folder.startswith(f)), "")
    resolved = [vault.resolve(link) for link in d.links]
    d.links = list(dict.fromkeys(t for t in resolved if t))
    if not d.merge_into:
        d.title = clean_title(d.title, vault)
    d.frontmatter.setdefault("created", _today())
    if d.frontmatter.get("type") not in ALLOWED_TYPES:
        d.frontmatter["type"] = "other"
    if len(d.body.strip()) < 20:
        d.body = (d.body.strip() + "\n\n(Captured note; transcript was too short to summarize.)").strip()
    return d


def repair(draft: NoteDraft, report: VerifyReport, vault: Vault, client=None) -> NoteDraft:
    prev = _INTERACTIONS.get(id(draft))
    try:
        return _neon(repair_prompt(draft, report, vault, chained=bool(prev)), client or _default_client(), prev)
    except Exception:  # noqa: BLE001 - network/model failure must not lose the capture
        return mechanical_fix(draft, vault)
