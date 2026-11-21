"""LANE A. Transcriber: Gemini 4 Hydrogen turns one media file into a Capture.

One job: faithful transcription. Media goes in as an Interactions content block (inline base64 for
small files, Files API upload for big ones); Hydrogen answers with native structured output
(response_format JSON schema), which we validate straight into `Capture`.

Video is first-class: Hydrogen returns timestamped segments (speech +
on-screen content) and key moments (decisions, actions, diagrams, code). The flat transcript is
rebuilt from the segments as "[mm:ss] ..." lines so every downstream consumer keeps working.
Processing mode (measured on the 3.5 min demo video, see commit log): static 0.5 fps for videos up to
10 min (full audio every time, 15-23 s, ~$0.05); agentic above that (docs: more token-efficient on
long-form). Agentic picks what to look at, and in 1 of 7 short-video runs it skipped ~40 words of speech.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import re
import subprocess
import time
from functools import lru_cache
from pathlib import Path

from .config import MODEL_IDS
from .schemas import Capture, KeyMoment, MediaKind, Segment

EXT_KIND = {
    ".m4a": MediaKind.audio, ".mp3": MediaKind.audio, ".wav": MediaKind.audio, ".ogg": MediaKind.audio,
    ".jpg": MediaKind.image, ".jpeg": MediaKind.image, ".png": MediaKind.image, ".heic": MediaKind.image,
    ".webp": MediaKind.image, ".pdf": MediaKind.pdf, ".mp4": MediaKind.video, ".mov": MediaKind.video,
    ".webm": MediaKind.video,
    ".txt": MediaKind.text, ".md": MediaKind.text,
}
MIME = {
    ".m4a": "audio/m4a", ".mp3": "audio/mp3", ".wav": "audio/wav", ".ogg": "audio/ogg",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".heic": "image/heic",
    ".webp": "image/webp", ".pdf": "application/pdf", ".mp4": "video/mp4", ".mov": "video/mov",
    ".webm": "video/webm",
}
CONTENT_TYPE = {MediaKind.audio: "audio", MediaKind.image: "image", MediaKind.pdf: "document",
                MediaKind.video: "video"}
# Docs: use the Files API once the whole request passes 20 MB. base64 inflates by 4/3, so keep raw
# inline media under ~14 MB and leave room for the prompt.
INLINE_MAX_BYTES = 14 * 1024 * 1024
FILE_ACTIVE_TIMEOUT_S = 600
STATIC_MAX_S = 600          # <= 10 min: static (complete audio); longer or unknown length: agentic
VIDEO_STATIC_FPS = 0.5      # slides/whiteboards/screens change slowly; halves frame tokens vs 1 fps

PROMPT = """You transcribe a personal capture (voice memo, whiteboard photo, handwritten page,
screenshot, PDF or short video) for an Obsidian vault. Be faithful: write what is actually said or
shown, keep names/course codes/project names exactly, mark unreadable parts as [illegible].
Keep the original layout in the transcript: one line per written line or spoken sentence, using \n.
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


VIDEO_PROMPT = """You transcribe a VIDEO capture (a recorded conversation, lecture, screen recording or
walkthrough) for an Obsidian vault. Capture BOTH channels: the speech AND anything shown on screen
(slides, whiteboard, diagrams, code, terminal output), even if the speaker never mentions it.
Be faithful: verbatim speech, names/course codes/project names exactly, [illegible]/[inaudible] where
needed. Timestamps are MM:SS from the start of the video.
Return:
- segments: consecutive spans covering the whole video, a new segment whenever the topic or the screen
  changes (typically 15-60 s each). Each: start, end, topic (3-8 words), text (verbatim speech in the
  span), on_screen (text/code/diagram visible in the span, transcribed; empty if nothing new).
- key_moments: only the moments worth keeping: decisions made, action items, diagrams or code worth
  keeping, important facts. Each: at (MM:SS), kind (decision|action|diagram|code|fact), text.
- summary (1-3 sentences covering every topic in the video), key_terms, action_items,
  legibility (0-1, honest: audio clarity and screen readability), notes (anything unclear, or topics
  that are unrelated to each other)."""

VIDEO_SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {"type": "array", "items": {
            "type": "object",
            "properties": {"start": {"type": "string"}, "end": {"type": "string"},
                           "topic": {"type": "string"}, "text": {"type": "string"},
                           "on_screen": {"type": "string"}},
            "required": ["start", "end", "topic", "text"]}},
        "key_moments": {"type": "array", "items": {
            "type": "object",
            "properties": {"at": {"type": "string"},
                           "kind": {"type": "string", "enum": ["decision", "action", "diagram", "code", "fact"]},
                           "text": {"type": "string"}},
            "required": ["at", "kind", "text"]}},
        **{k: v for k, v in CAPTURE_SCHEMA["properties"].items() if k != "transcript"},
    },
    "required": ["segments", "key_moments", "summary", "key_terms", "action_items", "legibility"],
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
        f = _wait_active(client, client.files.upload(file=str(path)))
        block["uri"] = f.uri
    if kind is MediaKind.video:
        block["processing"] = video_processing(path)
    return block


def video_duration_s(path: Path) -> float | None:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                              str(path)], capture_output=True, text=True, timeout=20)
        return float(out.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def video_processing(path: Path):
    dur = video_duration_s(path)
    if dur is not None and dur <= STATIC_MAX_S:
        return {"type": "static", "fps": VIDEO_STATIC_FPS}
    return "agentic"


def _state(f) -> str:
    st = getattr(f, "state", None)
    return str(getattr(st, "name", st) or "")


def _wait_active(client, f, poll_s: float = 2.0):
    """Uploaded video is PROCESSING for a while; using it before ACTIVE fails (docs: poll files.get)."""
    deadline = time.time() + FILE_ACTIVE_TIMEOUT_S
    while _state(f) not in ("ACTIVE", "STATE_ACTIVE", ""):
        if "FAIL" in _state(f):
            raise RuntimeError(f"file upload failed: {f.name}")
        if time.time() > deadline:
            raise TimeoutError(f"file {f.name} not ACTIVE after {FILE_ACTIVE_TIMEOUT_S}s")
        time.sleep(poll_s)
        f = client.files.get(name=f.name)
    return f


def fmt_ts(raw) -> str:
    """'65s' | '1:05' | '01:05' | '0:01:05' | 65 -> '01:05' ('1:01:05' past an hour)."""
    if isinstance(raw, (int, float)):
        secs = int(raw)
    else:
        txt = str(raw).strip().strip("[]()")
        if m := re.fullmatch(r"(\d+(?:\.\d+)?)\s*s?", txt):
            secs = int(float(m.group(1)))
        else:
            parts = [int(float(p)) for p in re.findall(r"\d+(?:\.\d+)?", txt)][-3:] or [0]
            secs = 0
            for p in parts:
                secs = secs * 60 + p
    h, rem = divmod(max(secs, 0), 3600)
    m, s_ = divmod(rem, 60)
    return f"{h}:{m:02d}:{s_:02d}" if h else f"{m:02d}:{s_:02d}"


def segments_transcript(segments: list[Segment]) -> str:
    lines = []
    for seg in segments:
        head = f"[{seg.start}]" + (f" ({seg.topic})" if seg.topic else "")
        lines.append(f"{head} {seg.text.strip()}".rstrip())
        if seg.on_screen:
            lines.append(f"[{seg.start}] ON SCREEN: {' / '.join(seg.on_screen.strip().splitlines())}")
    return "\n".join(lines)


def parse_video_capture(raw: str, path: Path) -> Capture:
    data = json.loads(raw)
    segs = [Segment(start=fmt_ts(s.get("start", 0)), end=fmt_ts(s["end"]) if s.get("end") else None,
                    topic=s.get("topic", ""), text=s.get("text", ""), on_screen=s.get("on_screen") or None)
            for s in data.pop("segments", [])]
    moments = [KeyMoment(at=fmt_ts(k.get("at", 0)), kind=k.get("kind", "fact"), text=k.get("text", ""))
               for k in data.pop("key_moments", [])]
    data["transcript"] = segments_transcript(segs) or "[no speech or on-screen content detected]"
    cap = parse_capture(json.dumps(data), path, MediaKind.video)
    cap.segments, cap.key_moments = segs, moments
    return cap


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
    if kind is MediaKind.video:
        r = client.interactions.create(
            model=MODEL_IDS["transcriber"],
            input=[{"type": "text", "text": VIDEO_PROMPT}, media_part(path, client)],
            generation_config={"thinking_level": "low"},
            response_format={"type": "text", "mime_type": "application/json", "schema": VIDEO_SCHEMA},
        )
        return parse_video_capture(r.output_text, path)
    r = client.interactions.create(
        model=MODEL_IDS["transcriber"],
        input=[{"type": "text", "text": PROMPT}, media_part(path, client)],
        generation_config={"thinking_level": "low"},
        response_format={"type": "text", "mime_type": "application/json", "schema": CAPTURE_SCHEMA},
    )
    return parse_capture(r.output_text, path, kind)
