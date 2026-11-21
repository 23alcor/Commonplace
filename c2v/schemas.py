"""Contracts between lanes. Do not rename fields; add optional ones if needed."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MediaKind(str, Enum):
    audio = "audio"
    image = "image"
    pdf = "pdf"
    video = "video"
    text = "text"


class Capture(BaseModel):
    """Output of the transcriber (Hydrogen)."""

    source_path: str
    media_kind: MediaKind
    transcript: str = Field(description="Faithful text of what was said, written or shown")
    summary: str = Field(description="1-3 sentence gist")
    key_terms: list[str] = Field(default_factory=list, description="Names, projects, courses, tools")
    action_items: list[str] = Field(default_factory=list)
    legibility: float = Field(1.0, ge=0, le=1, description="Transcriber's own read of input quality")
    notes: Optional[str] = Field(None, description="Anything unreadable or ambiguous")


class RoutedAnswer(BaseModel):
    choice: str
    confidence: float = Field(ge=0, le=1)
    probabilities: dict[str, float] = Field(default_factory=dict)


class RoutingDecision(BaseModel):
    """Output of the router (Decision 1)."""

    note_type: RoutedAnswer
    folder: RoutedAnswer
    merge_target: Optional[RoutedAnswer] = None  # choice = existing note title, or "new"
    escalate: bool = False
    reason: str = ""


class NoteDraft(BaseModel):
    """Output of the manager (Neon), or built directly from a confident RoutingDecision."""

    title: str
    folder: str  # vault-relative folder, must exist
    frontmatter: dict = Field(default_factory=dict)
    body: str
    links: list[str] = Field(default_factory=list, description="Titles of existing notes to [[link]]")
    merge_into: Optional[str] = Field(None, description="Existing note title to append to instead")


class VerifyIssue(BaseModel):
    code: str  # broken_link | missing_folder | duplicate_title | bad_frontmatter | empty_body
    detail: str


class VerifyReport(BaseModel):
    ok: bool
    issues: list[VerifyIssue] = Field(default_factory=list)


class FilingResult(BaseModel):
    capture: Capture
    routing: RoutingDecision
    draft: NoteDraft
    verify: VerifyReport
    written_path: Optional[str] = None
    path_taken: str = "auto"  # auto | escalated | agent_fixed
    latency_s: float = 0.0
