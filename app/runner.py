"""Staged pipeline runner for the demo page: same flow as c2v.pipeline.file_capture, but it reports
each step through `emit` so the page can show live progress over SSE.

Any Lane A stage that still raises NotImplementedError is replaced by a clearly labelled stub, so the
page works end to end before Lane A merges. Set C2V_NO_STUBS=1 to make missing stages fail loudly.
"""
from __future__ import annotations

import datetime as dt
import os
import time
import traceback
from pathlib import Path
from typing import Callable

from c2v.schemas import (Capture, FilingResult, MediaKind, NoteDraft, RoutedAnswer, RoutingDecision,
                         VerifyReport)
from c2v.vault import Vault
from c2v.verify import verify_draft, write_draft

Emit = Callable[..., None]  # emit(step, status, text, **data)
MAX_REPAIRS = 2


def _stub_ok() -> bool:
    return os.environ.get("C2V_NO_STUBS") != "1"


# --- stubs (only used while Lane A's functions are unimplemented) --------------------------------
def _stub_capture(path: Path) -> Capture:
    from c2v.transcribe import media_kind

    try:
        kind = media_kind(path)
    except Exception:
        kind = MediaKind.text
    return Capture(source_path=str(path), media_kind=kind,
                   transcript=f"(stub transcript of {path.name}) Momentum keeps a running average of gradients.",
                   summary="Stub capture: Lane A transcriber not merged yet.", key_terms=["momentum"],
                   legibility=0.5)


def _stub_routing(vault: Vault) -> RoutingDecision:
    folders = vault.folder_list()
    folder = next((f for f in folders if "Learning" in f), folders[0] if folders else "")
    return RoutingDecision(note_type=RoutedAnswer(choice="idea", confidence=0.6),
                           folder=RoutedAnswer(choice=folder, confidence=0.6),
                           escalate=True, reason="stub router")


def _stub_draft(capture: Capture, routing: RoutingDecision, vault: Vault) -> NoteDraft:
    hits = [n.title for n in vault.search(" ".join(capture.key_terms) + " " + capture.summary, k=2)]
    return NoteDraft(title=f"Capture {dt.datetime.now():%Y-%m-%d %H%M%S}", folder=routing.folder.choice,
                     frontmatter={"type": routing.note_type.choice, "created": dt.date.today().isoformat(),
                                  "source": Path(capture.source_path).name},
                     body=f"{capture.summary}\n\n{capture.transcript}", links=hits)


def _call(stage: str, emit: Emit, fn, stub, *args):
    try:
        return fn(*args), False
    except NotImplementedError:
        if not _stub_ok():
            raise
        emit(stage, "info", "not implemented yet, using stub")
        return stub(), True


# --- the run -------------------------------------------------------------------------------------
def run_capture(path: str | Path, vault: Vault, emit: Emit, agent_verify: bool = True,
                dry_run: bool = False) -> FilingResult:
    from c2v.config import ROUTE_CONFIDENCE_MIN
    from c2v.manage import draft_note, repair
    from c2v.route import needs_escalation, route
    from c2v.transcribe import transcribe

    path = Path(path)
    t0 = time.time()

    emit("transcribe", "start", "Hydrogen transcribing")
    capture, _ = _call("transcribe", emit, transcribe, lambda: _stub_capture(path), path)
    emit("transcribe", "done", capture.summary, capture=capture.model_dump(mode="json"))

    emit("route", "start", "Decision 1 routing")
    routing, stubbed = _call("route", emit, route, lambda: _stub_routing(vault), capture, vault)
    if not stubbed:
        routing.escalate = routing.escalate or needs_escalation(routing, capture)
    conf = min(routing.note_type.confidence, routing.folder.confidence)
    emit("route", "done",
         f"{routing.note_type.choice} -> {routing.folder.choice or '/'} (conf {conf:.2f}"
         f"{', escalating' if routing.escalate else ''}; min {ROUTE_CONFIDENCE_MIN})",
         routing=routing.model_dump(mode="json"))

    emit("manage", "start", "Neon drafting and linking" if routing.escalate else "Building note")
    draft, _ = _call("manage", emit, draft_note, lambda: _stub_draft(capture, routing, vault),
                     capture, routing, vault)
    emit("manage", "done", f"'{draft.title}' with {len(draft.links)} links",
         draft=draft.model_dump(mode="json"))

    report = verify_draft(draft, vault)
    emit("verify", "done" if report.ok else "warn",
         "all checks pass" if report.ok else f"{len(report.issues)} issue(s): "
         + "; ".join(i.detail for i in report.issues), report=report.model_dump(mode="json"))
    path_taken = "escalated" if routing.escalate else "auto"

    for _ in range(MAX_REPAIRS):
        if report.ok:
            break
        if agent_verify:
            from c2v.agent_verify import agent_fix

            emit("agent", "start", "Managed Agent verifying in a Google-hosted sandbox")
            draft, report = agent_fix(draft, report, vault,
                                      on_event=lambda text, **d: emit("agent", "info", text, **d))
            path_taken = "agent_fixed"
            emit("agent", "done" if report.ok else "warn",
                 "verify exit 0" if report.ok else f"still {len(report.issues)} issue(s)",
                 draft=draft.model_dump(mode="json"), report=report.model_dump(mode="json"))
        else:
            emit("repair", "start", "Neon repairing")
            draft, _ = _call("repair", emit, repair, lambda: draft, draft, report, vault)
            report = verify_draft(draft, vault)
            emit("repair", "done" if report.ok else "warn", f"{len(report.issues)} issue(s) left")

    written = None
    if report.ok and not dry_run:
        written = str(write_draft(draft, vault))
        rel = Path(written).relative_to(vault.root).as_posix()
        emit("write", "done", f"Filed to {rel}", path=rel)
    elif not report.ok:
        emit("write", "error", "not filed: draft still fails verification")
    return FilingResult(capture=capture, routing=routing, draft=draft, verify=report,
                        written_path=written, path_taken=path_taken, latency_s=time.time() - t0)


def safe_run(path, vault, emit, **kw) -> FilingResult | None:
    try:
        return run_capture(path, vault, emit, **kw)
    except Exception as e:  # surface every failure on the page; honest failures are part of the demo
        emit("error", "error", f"{type(e).__name__}: {e}", trace=traceback.format_exc(limit=4))
        return None
