"""LANE A. Transcriber: Gemini 4 Hydrogen turns one media file into a Capture.

One job: faithful transcription. Media goes in as an Interactions content block (inline base64 for
small files, Files API upload for big ones); Hydrogen answers with native structured output
(response_format JSON schema), which we validate straight into `Capture`.
"""
from __future__ import annotations

import base64
import json
import mimetypes
from functools import lru_cache
from pathlib import Path

from .config import MODEL_IDS
from .schemas import Capture, MediaKind

EXT_KIND = {
    ".m4a": MediaKind.audio, ".mp3": MediaKind.audio, ".wav": MediaKind.audio, ".ogg": MediaKind.audio,
    ".jpg": MediaKind.image, ".jpeg": MediaKind.image, ".png": MediaKind.image, ".heic": MediaKind.image,
    ".webp": MediaKind.image, ".pdf": MediaKind.pdf, ".mp4": MediaKind.video, ".mov": MediaKind.video,
    ".txt": MediaKind.text, ".md": MediaKind.text,
}
MIME = {
    ".m4a": "audio/m4a", ".mp3": "audio/mp3", ".wav": "audio/wav", ".ogg": "audio/ogg",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".heic": "image/heic",
    ".webp": "image/webp", ".pdf": "application/pdf", ".mp4": "video/mp4", ".mov": "video/quicktime",
}
CONTENT_TYPE = {MediaKind.audio: "audio", MediaKind.image: "image", MediaKind.pdf: "document",
                MediaKind.video: "video"}
INLINE_MAX_BYTES = 15 * 1024 * 1024  # above this, go through the Files API

PROMPT = """You transcribe a personal capture (voice memo, whiteboard photo, handwritten page,
screenshot, PDF or short video) for an Obsidian vault. Be faithful: write what is actually said or
shown, keep names/course codes/project names exactly, mark unreadable parts as [illegible].
Return: transcript, summary (1-3 sentences), key_terms, action_items, legibility (0-1), notes.
legibility is your honest read of input quality: 1.0 = crisp and complete, 0.5 = you guessed at a
lot, below 0.3 = mostly unreadable or inaudible."""

# Hand-written (not model_json_schema()) so it stays inside the structured-output schema subset.
CAPTURE_SCHEMA = {
    "type": "object",
    "properties": {
        "transcript": {"type": "string", "description": "Faithful text of what was said, written or shown"},
        "summary": {"type": "string", "description": "1-3 sentence gist"},
        "key_terms": {"type": "array", "items": {"type": "string"},
                      "description": "Names, projects, courses, tools"},
        "action_items": {"type": "array", "items": {"type": "string"}},
        "legibility": {"type": "number", "minimum": 0, "maximum": 1},
        "notes": {"type": "string", "description": "Anything unreadable or ambiguous; empty if none"},
    },
    "required": ["transcript", "summary", "key_terms", "action_items", "legibility"],
}


@lru_cache(maxsize=1)
def _default_clients():
    from .config import clients

    return clients()


def media_kind(path: Path) -> MediaKind:
    return EXT_KIND.get(path.suffix.lower(), MediaKind.text)


def mime_type(path: Path) -> str:
    return MIME.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def media_part(path: str | Path, client=None) -> dict:
    """Interactions/Decisions content block for a media file. Shared with the router."""
    path = Path(path)
    kind = media_kind(path)
    block: dict = {"type": CONTENT_TYPE[kind], "mime_type": mime_type(path)}
    if path.stat().st_size <= INLINE_MAX_BYTES:
        block["data"] = base64.b64encode(path.read_bytes()).decode("ascii")
    else:
        client = client or _default_clients()[0]
        f = client.files.upload(file=str(path))
        block["uri"] = f.uri
    if kind is MediaKind.video:
        block["processing"] = "agentic"
    return block


def parse_capture(raw: str, path: Path, kind: MediaKind) -> Capture:
    data = json.loads(raw)
    data["legibility"] = min(1.0, max(0.0, float(data.get("legibility", 1.0))))
    data["notes"] = data.get("notes") or None
    return Capture(source_path=str(path), media_kind=kind, **data)


def transcribe(path: str | Path, client=None) -> Capture:
    path = Path(path)
    kind = media_kind(path)
    if kind is MediaKind.text:  # offline path, handy for tests and dry runs
        text = path.read_text(encoding="utf-8", errors="replace")
        return Capture(source_path=str(path), media_kind=kind, transcript=text, summary=text[:200])

    client = client or _default_clients()[0]
    r = client.interactions.create(
        model=MODEL_IDS["transcriber"],
        input=[{"type": "text", "text": PROMPT}, media_part(path, client)],
        generation_config={"thinking_level": "low"},
        response_format={"type": "text", "mime_type": "application/json", "schema": CAPTURE_SCHEMA},
        response_mime_type="application/json",
    )
    return parse_capture(r.output_text, path, kind)
