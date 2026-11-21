"""LANE C. Demo server: phone camera / mic -> pipeline -> the new note.

    uvicorn app.server:app --host 0.0.0.0 --port 8000

POST /capture (multipart `file`, optional `agent_verify`)   -> {"job": id}
GET  /events/{job}   SSE stream of step events, ends with event "end"
GET  /note?path=...  or ?title=...                          -> rendered note + its links
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from c2v.config import VAULT_PATH
from c2v.context import get_context
from c2v.vault import Vault, split_frontmatter

from .render import render_note
from .runner import safe_run

STATIC = Path(__file__).parent / "static"
UPLOADS = Path(os.environ.get("C2V_UPLOAD_DIR", Path(tempfile.gettempdir()) / "c2v-uploads"))
UPLOADS.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="capture-to-vault")
vault = Vault(VAULT_PATH)
vault_lock = threading.Lock()  # one capture writes to the vault at a time
jobs: dict[str, dict] = {}


class Job:
    def __init__(self) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.events: list[dict] = []
        self.done = False
        self.t0 = time.time()

    def emit(self, step: str, status: str, text: str = "", **data) -> None:
        self.events.append({"step": step, "status": status, "text": text,
                            "t": round(time.time() - self.t0, 2), **data})


def _work(job: Job, path: Path, agent_verify: bool) -> None:
    job.emit("upload", "done", f"received {path.name} ({path.stat().st_size // 1024} KB)")
    with vault_lock:
        vault.reload()
        res = safe_run(path, vault, job.emit, agent_verify=agent_verify)
    if res is not None:
        rel = Path(res.written_path).relative_to(vault.root).as_posix() if res.written_path else None
        job.emit("result", "done", res.path_taken, written=rel, latency_s=round(res.latency_s, 1),
                 result=res.model_dump(mode="json"))
    job.done = True


_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


latest: dict[str, str | None] = {"job": None}


@app.post("/capture")
async def capture(file: UploadFile = File(...), agent_verify: bool = Form(True)):
    job = Job()
    name = _SAFE.sub("_", file.filename or "capture.bin")[-80:]
    dest = UPLOADS / f"{job.id}-{name}"
    dest.write_bytes(await file.read())
    jobs[job.id] = {"job": job}
    latest["job"] = job.id
    threading.Thread(target=_work, args=(job, dest, agent_verify), daemon=True).start()
    return {"job": job.id}


@app.get("/events/{job_id}")
async def events(job_id: str, request: Request):
    if job_id not in jobs:
        raise HTTPException(404, "unknown job")
    job: Job = jobs[job_id]["job"]

    async def gen():
        i = 0
        while True:
            if await request.is_disconnected():
                return
            while i < len(job.events):
                yield {"event": "step", "id": str(i), "data": json.dumps(job.events[i], default=str)}
                i += 1
            if job.done and i >= len(job.events):
                yield {"event": "end", "data": "{}"}
                return
            await asyncio.sleep(0.25)

    return EventSourceResponse(gen(), ping=10)


@app.get("/note")
def note(path: str | None = None, title: str | None = None):
    vault.reload()
    if title:
        t = vault.resolve(title)
        if t is None:
            raise HTTPException(404, f"no note [[{title}]]")
        path = vault.notes[t].path.as_posix()
    if not path:
        raise HTTPException(400, "path or title required")
    p = (vault.root / path).resolve()
    if vault.root not in p.parents or p.suffix != ".md" or not p.exists():
        raise HTTPException(404, "note not found")
    text = p.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    return {"path": path, "title": p.stem, "frontmatter": fm, "markdown": text,
            "html": render_note(body, vault)}


@app.get("/context")
def context(q: str, max_tokens: int = 4000):
    """The context-manager API: the right notes for a project, conversation or topic."""
    vault.reload()
    return get_context(vault, q, max_tokens=max(200, min(max_tokens, 200_000)))


@app.get("/graph")
def graph():
    """Vault as nodes + edges for the stage view."""
    vault.reload()
    nodes = [{"id": t, "folder": n.folder, "type": str(n.frontmatter.get("type", ""))}
             for t, n in vault.notes.items()]
    edges = []
    for t, n in vault.notes.items():
        for link in n.links:
            r = vault.resolve(link)
            if r and r != t:
                edges.append({"source": t, "target": r})
    return {"nodes": nodes, "edges": edges}


@app.get("/jobs/latest")
def latest_job():
    """Lets the stage screen follow captures taken on a phone."""
    return {"job": latest["job"]}


@app.get("/stage")
def stage():
    return FileResponse(STATIC / "stage.html")


@app.get("/static/{name}")
def static_file(name: str):
    p = (STATIC / name).resolve()
    if p.parent != STATIC.resolve() or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/health")
def health():
    return {"ok": True, "vault": str(vault.root), "notes": len(vault.notes)}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
