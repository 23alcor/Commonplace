"""LANE A. Vault manager: Gemini 4 Neon writes the final NoteDraft.

One job: turn a routed capture into a vault-correct note. Two paths:
  * fast path (router confident): build the draft deterministically from the router's choices.
  * escalated (router unsure): Neon gets the capture, the router's probabilities, the vault map and
    the full text of the top candidates, and answers with a structured NoteDraft.
repair(): Neon gets verify.py's issues and fixes the draft, chained with previous_interaction_id
when the draft came from Neon. If Neon is unreachable, a deterministic fix keeps the pipeline alive.
Video: Neon also returns a timeline (one entry per segment/chapter, each linked to the existing notes it
is about). Lane A renders it as "## Timeline" with [mm:ss] bullets, keeping only links that resolve,
plus "## Key moments" from the transcriber. A long video becomes one hub note linking out.
finalize_note(): after verification, append the full transcript under "## Source" and point
frontmatter `source:` at the original file copied into `_attachments/`, so the vault keeps the details.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path

from .config import MODEL_IDS
from .route import NEW, OTHER, folder_guide
from .schemas import Capture, MediaKind, NoteDraft, RoutingDecision, VerifyReport
from .vault import Vault
from .verify import ALLOWED_TYPES

ATTACH_DIR = "_attachments"
MAX_TIMELINE = 15  # long videos: Neon groups segments into at most this many chapters
OWNED_SECTIONS = ("## Timeline", "## Key moments", "## Source")  # rendered by lane A, not Neon
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

TIMELINE_SCHEMA = {
    **DRAFT_SCHEMA,
    "properties": {**DRAFT_SCHEMA["properties"], "timeline": {
        "type": "array", "maxItems": MAX_TIMELINE,
        "items": {"type": "object",
                  "properties": {"at": {"type": "string", "description": "mm:ss start of the segment/chapter"},
                                 "text": {"type": "string", "description": "What happens here, one sentence"},
                                 "links": {"type": "array", "items": {"type": "string"},
                                           "description": "Exact titles of existing notes this part is about"}},
                  "required": ["at", "text", "links"]}}},
    "required": [*DRAFT_SCHEMA["required"], "timeline"],
}

VIDEO_INSTRUCTIONS = f"""This capture is a VIDEO. Write a HUB note:
- body: what the video covers and why it matters, the decisions made and the action items as
  "- [ ]" checkboxes. Short. Do NOT include a timeline, key moments or the transcript in the body;
  those sections are added automatically from your timeline field and the transcriber's output.
- timeline: one entry per segment in order (merge adjacent segments on the same topic; at most
  {MAX_TIMELINE} entries for long videos). For each, links = the existing notes THAT PART is about,
  copied exactly from CANDIDATES or NOTES. Different parts of a video can link to different notes.
  Empty links when no existing note fits; never invent a title.
- links: every note linked anywhere in the timeline, plus any note related to the video as a whole.
- merge_into: "" unless the entire video is an update to one existing note."""

SYSTEM = """You are the vault manager for an Obsidian vault. You turn one transcribed capture into
one clean note that fits the vault. Rules:
- folder MUST be copied exactly from the FOLDERS list. Use the FOLDER GUIDE: decide what kind of note
  this is, then choose the MOST SPECIFIC folder for it. A short log of one work/study session ("worked on
  X", what got done, next steps) goes in the sessions folder even if it names a project. Material about a
  named course or project goes in that course/project's own folder, never its parent/index folder. A note
  explaining one reusable concept goes in the concepts folder.
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

    body = [capture.summary.strip()]  # full transcript is appended under ## Source by finalize_note
    if capture.action_items:
        body += ["", "## Action items", *[f"- [ ] {a}" for a in capture.action_items]]

    draft = NoteDraft(
        title=merge or clean_title(_title_from_capture(capture), vault),
        folder=vault.notes[merge].folder if merge else folder,
        frontmatter={"type": ntype, "created": _today(), "source": capture.media_kind.value,
                     "tags": [t for t in (_tag(k) for k in capture.key_terms) if t]},
        body="\n".join(body),
        links=links,
        merge_into=merge,
    )
    return with_timeline(draft, capture, [], vault) if capture.segments else draft


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
        *([video_context(capture)] if capture.segments else []),
        f"ROUTER (calibrated probabilities):\n{_routing_context(routing)}",
        f"VAULT MAP:\n{vault_map(vault)}",
        f"FOLDER GUIDE (what belongs in each folder):\n{folder_guide(vault)}",
        f"CANDIDATES (full text of the most related notes):\n{cand_text or '(none)'}",
        "Write the NoteDraft.",
    ])


def video_context(capture: Capture) -> str:
    segs = "\n".join(f"- [{s.start}-{s.end or ''}] {s.topic}" for s in capture.segments)
    moments = "\n".join(f"- [{k.at}] {k.kind}: {k.text}" for k in capture.key_moments) or "(none)"
    return f"{VIDEO_INSTRUCTIONS}\n\nSEGMENTS:\n{segs}\n\nKEY MOMENTS:\n{moments}"


def vault_map(vault: Vault) -> str:
    """vault.describe() minus the attachments folder, which is never a filing destination."""
    return "\n".join(line for line in vault.describe().splitlines()
                     if not line.startswith(f"- {ATTACH_DIR}"))


def parse_draft(raw: str) -> NoteDraft:
    data = json.loads(raw)
    data["merge_into"] = data.get("merge_into") or None
    return NoteDraft(**data)


def _neon(input_, client, previous_id: str | None = None, schema: dict = DRAFT_SCHEMA):
    kw = dict(
        model=MODEL_IDS["manager"],
        input=input_,
        system_instruction=SYSTEM,
        generation_config={"thinking_level": "low"},
        response_format={"type": "text", "mime_type": "application/json", "schema": schema},
    )
    if previous_id:
        kw["previous_interaction_id"] = previous_id
    r = client.interactions.create(**kw)
    data = json.loads(r.output_text)
    timeline = data.pop("timeline", None)
    draft = parse_draft(json.dumps(data))
    _INTERACTIONS[id(draft)] = r.id
    return (draft, timeline) if schema is TIMELINE_SCHEMA else draft


def neon_draft(capture: Capture, routing: RoutingDecision, vault: Vault, client=None) -> NoteDraft:
    prompt, client = build_prompt(capture, routing, vault), client or _default_client()
    if not capture.segments:
        return _neon(prompt, client)
    draft, timeline = _neon(prompt, client, schema=TIMELINE_SCHEMA)
    return with_timeline(draft, capture, timeline or [], vault)


# --- video: timeline + key moments ----------------------------------------------------------
def render_timeline(entries: list[dict], vault: Vault) -> tuple[str, list[str]]:
    """'- [mm:ss] text → [[A]], [[B]]' bullets with only resolvable links. Returns (markdown, links)."""
    from .transcribe import fmt_ts

    lines, used = ["## Timeline"], []
    for e in entries:
        resolved = list(dict.fromkeys(t for t in (vault.resolve(x) for x in e.get("links", [])) if t))
        used += resolved
        arrow = (" → " + ", ".join(f"[[{t}]]" for t in resolved)) if resolved else ""
        lines.append(f"- [{fmt_ts(e.get('at', 0))}] {' '.join(str(e.get('text', '')).split())}{arrow}")
    return "\n".join(lines), list(dict.fromkeys(used))


def key_moments_section(capture: Capture) -> str:
    if not capture.key_moments:
        return ""
    icon = {"decision": "Decision", "action": "Action", "diagram": "Diagram", "code": "Code", "fact": "Fact"}
    return "\n".join(["## Key moments"] + [f"- [{k.at}] **{icon.get(k.kind, k.kind.title())}:** {k.text}"
                                            for k in capture.key_moments])


def strip_owned(body: str) -> str:
    """Body without the sections lane A renders (so repairs and re-renders never duplicate them)."""
    cut = min([i for i in (body.find("\n" + h) for h in OWNED_SECTIONS) if i >= 0] + [len(body)])
    if body.startswith(OWNED_SECTIONS):
        cut = 0
    return body[:cut].rstrip()


def owned_tail(body: str) -> str:
    core = strip_owned(body)
    return body[len(core):].strip()


def with_timeline(draft: NoteDraft, capture: Capture, entries: list[dict], vault: Vault) -> NoteDraft:
    if not entries:  # Neon skipped it (or fast path): fall back to the transcriber's segments, unlinked
        entries = [{"at": s.start, "text": s.topic or s.text[:120], "links": []} for s in capture.segments]
    timeline, links = render_timeline(entries, vault)
    d = draft.model_copy(deep=True)
    d.body = "\n\n".join(x for x in (strip_owned(d.body), timeline, key_moments_section(capture)) if x)
    d.links = list(dict.fromkeys([*(t for t in (vault.resolve(x) for x in d.links) if t), *links]))
    return d


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
        parts.append(f"VAULT MAP:\n{vault_map(vault)}")
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
    """Neon fixes the issues on the draft's core body; lane-A-rendered sections are carried over."""
    prev = _INTERACTIONS.get(id(draft))
    tail = owned_tail(draft.body)
    core = draft.model_copy(update={"body": strip_owned(draft.body)})
    try:
        fixed = _neon(repair_prompt(core, report, vault, chained=bool(prev)), client or _default_client(), prev)
    except Exception:  # noqa: BLE001 - network/model failure must not lose the capture
        fixed = mechanical_fix(core, vault)
    if tail:
        new_id = _INTERACTIONS.pop(id(fixed), None)
        fixed = fixed.model_copy(update={"body": f"{strip_owned(fixed.body)}\n\n{tail}"})
        if new_id:
            _INTERACTIONS[id(fixed)] = new_id
    return fixed


# --- keep the source ------------------------------------------------------------------------
EMBEDDABLE = {MediaKind.image, MediaKind.pdf, MediaKind.audio, MediaKind.video}


def _digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def attachment_path(capture: Capture, draft: NoteDraft, vault: Vault) -> str:
    """Vault-relative path the original capture will live at: _attachments/<date> <title><ext>.
    Reuses an identical file already there; otherwise picks a name that doesn't collide."""
    src = Path(capture.source_path)
    title = draft.title if draft.title.startswith(_today()) else f"{_today()} {draft.title}"
    stem = BAD_TITLE_CHARS.sub(" ", title)
    stem = " ".join(stem.split()) or src.stem
    ext = src.suffix.lower()
    digest = _digest(src) if src.exists() else None
    for i in range(1, 100):
        name = f"{stem}{'' if i == 1 else f' {i}'}{ext}"
        target = vault.root / ATTACH_DIR / name
        if not target.exists() or (digest and _digest(target) == digest):
            return f"{ATTACH_DIR}/{name}"
    return f"{ATTACH_DIR}/{stem} {dt.datetime.now():%H%M%S%f}{ext}"


def source_section(capture: Capture, attachment: str | None) -> str:
    lines = ["## Source"]
    if attachment and capture.media_kind in EMBEDDABLE:
        lines.append(f"![[{attachment}]]")
    lines += ["", "> [!quote]- Transcript"]
    lines += [f"> {ln}" if ln.strip() else ">" for ln in capture.transcript.strip().splitlines()] or ["> (empty)"]
    if capture.notes:
        lines += ["", f"> [!note] Transcriber: {capture.notes}"]
    return "\n".join(lines)


def finalize_note(draft: NoteDraft, capture: Capture, attachment: str | None) -> NoteDraft:
    """Neon's summary stays on top; the full source goes underneath. Pure: copying the file is the
    caller's job (pipeline.write_note), so dry runs never touch the vault."""
    d = draft.model_copy(deep=True)
    body = re.split(r"\n## Source\b", d.body, maxsplit=1)[0].rstrip()  # idempotent
    d.body = f"{body}\n\n{source_section(capture, attachment)}"
    d.frontmatter["source"] = attachment or Path(capture.source_path).name
    d.frontmatter["media"] = capture.media_kind.value
    return d
