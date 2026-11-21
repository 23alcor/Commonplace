"""LANE A. End-to-end: capture file -> FilingResult. Also the CLI used by the demo and the eval.

    python -m c2v.pipeline path/to/capture.jpg [--vault demo_vault] [--dry-run] [--agent-verify]
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from .config import VAULT_PATH
from .manage import attachment_path, draft_note, finalize_note, repair
from .route import needs_escalation, route
from .schemas import Capture, FilingResult, NoteDraft, VerifyReport
from .transcribe import transcribe
from .vault import Vault
from .verify import verify_draft, write_draft

MAX_REPAIRS = 2


def finalize(draft: NoteDraft, capture: Capture, vault: Vault) -> tuple[NoteDraft, str | None]:
    """Draft with the full source attached, plus the vault-relative attachment path (not copied yet)."""
    src = Path(capture.source_path)
    attachment = attachment_path(capture, draft, vault) if src.is_file() else None
    return finalize_note(draft, capture, attachment), attachment


def write_note(draft: NoteDraft, capture: Capture, vault: Vault) -> tuple[Path | None, NoteDraft, VerifyReport]:
    """Copy the original capture into _attachments/, attach the transcript, re-verify, write.
    Call with a draft that already passed verify_draft. The demo runner should call this instead of
    verify.write_draft so demo-filed notes keep their source too."""
    final, attachment = finalize(draft, capture, vault)
    report = verify_draft(final, vault)
    if not report.ok:  # attaching the source must never break a verified note
        return None, final, report
    if attachment:
        target = vault.root / attachment
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(capture.source_path, target)
    return write_draft(final, vault), final, report


def file_capture(path: str | Path, vault: Vault, dry_run: bool = False, agent_verify: bool = False,
                 client=None, beta_client=None) -> FilingResult:
    """client/beta_client: inject fakes in tests; default to real Gemini clients."""
    t0 = time.time()
    capture = transcribe(path, client=client)
    routing = route(capture, vault, beta_client=beta_client, client=client)
    routing.escalate = routing.escalate or needs_escalation(routing, capture)
    draft = draft_note(capture, routing, vault, client=client)
    report = verify_draft(draft, vault)
    path_taken = "escalated" if routing.escalate else "auto"

    for _ in range(MAX_REPAIRS):
        if report.ok:
            break
        if agent_verify:
            from .agent_verify import agent_fix  # lane C

            draft, report = agent_fix(draft, report, vault)
            path_taken = "agent_fixed"
        else:
            draft = repair(draft, report, vault, client=client)
            report = verify_draft(draft, vault)

    written = None
    if report.ok and not dry_run:
        path_written, draft, report = write_note(draft, capture, vault)
        written = str(path_written) if path_written else None
    elif report.ok:
        draft, _ = finalize(draft, capture, vault)  # dry run: show the final note, touch nothing
    return FilingResult(capture=capture, routing=routing, draft=draft, verify=report,
                        written_path=written, path_taken=path_taken, latency_s=time.time() - t0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("capture")
    ap.add_argument("--vault", default=str(VAULT_PATH))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--agent-verify", action="store_true")
    a = ap.parse_args()
    res = file_capture(a.capture, Vault(a.vault), dry_run=a.dry_run, agent_verify=a.agent_verify)
    print(json.dumps(res.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
