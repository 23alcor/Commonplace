"""LANE C. Demo server: phone camera / mic -> pipeline -> the new note.

    uvicorn app.server:app --host 0.0.0.0 --port 8000

TODO(lane-c):
- POST /capture (multipart file) -> run c2v.pipeline.file_capture, stream progress steps to the page
  with SSE: "Hydrogen transcribing", "Decision 1 routing (conf 0.91)", "Neon linking",
  "Managed Agent verifying", "Filed to <folder>/<title>.md".
- GET /note?path=... -> rendered markdown of the written note + its links.
- Static page app/static/index.html: big Capture button (<input type=file accept="image/*,audio/*,
  application/pdf" capture>), a Record button (MediaRecorder for voice memos), and the live step log.
- NOT Streamlit, and not a dashboard. The note appearing (and Obsidian's graph view) is the payoff.
- Reach it from the phone over Tailscale: http://skull-fort:8000
"""
from __future__ import annotations
