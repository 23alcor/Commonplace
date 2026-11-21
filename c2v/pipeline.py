"""LANE A. End-to-end: capture file -> FilingResult. Also the CLI used by the demo and the eval.

    python -m c2v.pipeline path/to/capture.jpg [--vault demo_vault] [--dry-run] [--agent-verify]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .config import VAULT_PATH
from .manage import draft_note, repair
from .route import needs_escalation, route
from .schemas import FilingResult
from .transcribe import transcribe
from .vault import Vault
from .verify import verify_draft, write_draft

MAX_REPAIRS = 2


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
        written = str(write_draft(draft, vault))
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
