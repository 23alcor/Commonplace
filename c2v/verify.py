"""Deterministic checks a NoteDraft must pass before it is written.

Usable as a library (verify_draft) and as a CLI the Managed Agent runs inside its sandbox:
    python -m c2v.verify --vault demo_vault --draft draft.json
Exit code 0 = ok, 1 = issues (printed as JSON).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .schemas import NoteDraft, VerifyIssue, VerifyReport
from .vault import Vault

REQUIRED_FRONTMATTER = ("type", "created")
ALLOWED_TYPES = {"idea", "task", "meeting", "class", "project-update", "reference", "journal", "other"}


def verify_draft(draft: NoteDraft, vault: Vault) -> VerifyReport:
    issues: list[VerifyIssue] = []

    if draft.folder not in vault.folders:
        issues.append(VerifyIssue(code="missing_folder", detail=f"folder '{draft.folder}' not in vault"))

    if draft.merge_into:
        if vault.resolve(draft.merge_into) is None:
            issues.append(VerifyIssue(code="broken_link", detail=f"merge target '{draft.merge_into}' not found"))
    elif vault.resolve(draft.title) is not None:
        issues.append(VerifyIssue(code="duplicate_title", detail=f"a note titled '{draft.title}' already exists"))

    for link in draft.links:
        if vault.resolve(link) is None:
            issues.append(VerifyIssue(code="broken_link", detail=f"[[{link}]] does not resolve"))

    for key in REQUIRED_FRONTMATTER:
        if key not in draft.frontmatter:
            issues.append(VerifyIssue(code="bad_frontmatter", detail=f"missing '{key}'"))
    ntype = draft.frontmatter.get("type")
    if ntype is not None and ntype not in ALLOWED_TYPES:
        issues.append(VerifyIssue(code="bad_frontmatter", detail=f"type '{ntype}' not in {sorted(ALLOWED_TYPES)}"))

    if len(draft.body.strip()) < 20:
        issues.append(VerifyIssue(code="empty_body", detail="body is empty or too short"))

    return VerifyReport(ok=not issues, issues=issues)


def render_markdown(draft: NoteDraft) -> str:
    import yaml

    fm = yaml.safe_dump(draft.frontmatter, sort_keys=False, allow_unicode=True).strip()
    links = ""
    if draft.links:
        links = "\n\n## Related\n" + "\n".join(f"- [[{t}]]" for t in draft.links)
    return f"---\n{fm}\n---\n\n{draft.body.strip()}{links}\n"


def write_draft(draft: NoteDraft, vault: Vault) -> Path:
    """Write (or merge) the draft into the vault. Call only after verify_draft(...).ok."""
    if draft.merge_into:
        title = vault.resolve(draft.merge_into)
        path = vault.root / vault.notes[title].path
        addition = f"\n\n## Update\n{draft.body.strip()}\n"
        if draft.links:
            addition += "\n".join(f"- [[{t}]]" for t in draft.links) + "\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(addition)
    else:
        path = vault.root / draft.folder / f"{draft.title}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(draft), encoding="utf-8")
    vault.reload()
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", required=True)
    ap.add_argument("--draft", required=True, help="path to NoteDraft JSON")
    args = ap.parse_args(argv)
    draft = NoteDraft.model_validate_json(Path(args.draft).read_text())
    report = verify_draft(draft, Vault(args.vault))
    print(json.dumps(report.model_dump(), indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
