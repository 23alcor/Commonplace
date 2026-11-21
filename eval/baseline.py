"""One-call Hydrogen baseline: media plus the same static vault map for every case."""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from c2v.config import MODEL_IDS
from c2v.schemas import NoteDraft
from c2v.vault import Vault


def media_input(path: str | Path) -> dict:
    path = Path(path)
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    kind = "document" if mime == "application/pdf" else "audio" if mime.startswith("audio/") else "image"
    return {"type": kind, "data": base64.b64encode(path.read_bytes()).decode("ascii"),
            "mime_type": mime}


def run_baseline(path: str | Path, vault: Vault, client=None) -> NoteDraft:
    if client is None:
        from google import genai
        client = genai.Client()
    prompt = ("Write one Obsidian note for this capture. Choose its title and a folder from "
              "the vault map, and link relevant existing notes by exact title. "
              "Return title, folder, frontmatter, body, links, and merge_into. "
              "Frontmatter needs type and created (today's ISO date). "
              "Do not invent notes or folders.\n\n" + vault.describe())
    response = client.interactions.create(
        model=MODEL_IDS["transcriber"],
        input=[{"type": "text", "text": prompt}, media_input(path)],
        response_format={"type": "text", "mime_type": "application/json",
                         "schema": NoteDraft.model_json_schema()},
        generation_config={"thinking_level": "low"})
    return NoteDraft.model_validate_json(response.output_text)
