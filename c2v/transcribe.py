"""LANE A. Transcriber: Gemini 4 Hydrogen turns one media file into a Capture.

TODO(lane-a):
- Upload media with client.files.upload(file=path) (audio, image, pdf, video).
  For video, pass {"type": "video", "uri": f.uri, "processing": "agentic"}.
- Ask Hydrogen (thinking_level "low" or "medium") for structured output matching Capture.
  Prefer the SDK's native structured output (response schema) over parsing free text.
- Fill legibility honestly; low legibility should push the router to escalate.
"""
from __future__ import annotations

from pathlib import Path

from .schemas import Capture, MediaKind

EXT_KIND = {
    ".m4a": MediaKind.audio, ".mp3": MediaKind.audio, ".wav": MediaKind.audio, ".ogg": MediaKind.audio,
    ".jpg": MediaKind.image, ".jpeg": MediaKind.image, ".png": MediaKind.image, ".heic": MediaKind.image,
    ".webp": MediaKind.image, ".pdf": MediaKind.pdf, ".mp4": MediaKind.video, ".mov": MediaKind.video,
    ".txt": MediaKind.text, ".md": MediaKind.text,
}

PROMPT = """You transcribe a personal capture (voice memo, whiteboard photo, handwritten page,
screenshot, PDF or short video) for an Obsidian vault. Be faithful: write what is actually said or
shown, keep names/course codes/project names exactly, mark unreadable parts as [illegible].
Return: transcript, summary (1-3 sentences), key_terms, action_items, legibility (0-1), notes."""


def media_kind(path: Path) -> MediaKind:
    return EXT_KIND.get(path.suffix.lower(), MediaKind.text)


def transcribe(path: str | Path) -> Capture:
    path = Path(path)
    kind = media_kind(path)
    if kind is MediaKind.text:  # offline path, handy for tests and dry runs
        text = path.read_text(encoding="utf-8", errors="replace")
        return Capture(source_path=str(path), media_kind=kind, transcript=text, summary=text[:200])
    raise NotImplementedError("lane-a: call gemini-4-hydrogen here")
