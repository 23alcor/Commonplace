"""LANE C. Vault maintenance: it doesn't just add context, it keeps context true.

    python -m c2v.maintain --project "Solar Microgrid Capstone" --vault <copy> [--apply]
    python -m c2v.maintain --seed-demo <dst>     # copy of mock_vault with 3 planted inconsistencies
    python -m c2v.maintain --check --vault vault # used by the Managed Agent inside its sandbox

1. Gather the project's whole neighbourhood with get_context (large budget).
2. One Neon call (structured output) lists findings: contradictions, superseded decisions, stale open
   loops (tasks done in a later note), duplicate notes. Each cites note titles and quotes. We check every
   quote against the note text locally and mark findings whose quotes don't appear as unverified.
3. --apply: the Antigravity Managed Agent gets the neighbourhood notes (full text) plus a skeleton of the
   rest of the vault, edits the notes in its sandbox (superseded callouts, tick done tasks, merge
   duplicates), runs `python -m c2v.maintain --check` until it exits 0, and we download each edited note
   and write it back. Never run --apply on a vault you can't lose: it is meant for a copy.
   Note: with --apply the neighbourhood notes' full text is sent to the sandbox.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

from .vault import Vault, split_frontmatter

KINDS = ["contradiction", "superseded", "stale_task", "duplicate"]

FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": KINDS},
                    "summary": {"type": "string", "description": "One sentence: what is inconsistent"},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string", "description": "Exact note title"},
                                "quote": {"type": "string", "description": "Verbatim text copied from that note"},
                            },
                            "required": ["title", "quote"],
                        },
                    },
                    "current_title": {"type": "string",
                                      "description": "The note that holds the current truth (newer / canonical)"},
                    "stale_title": {"type": "string",
                                    "description": "The note that is outdated, superseded or the duplicate"},
                    "action": {"type": "string", "description": "The concrete edit that makes the vault true again"},
                },
                "required": ["kind", "summary", "evidence", "current_title", "stale_title", "action"],
            },
        }
    },
    "required": ["findings"],
}

SYSTEM = """You maintain an Obsidian vault so it stays TRUE. You get every note around one project, each
with its title, path and date. Find only real problems:
- contradiction: two notes state different facts about the same thing (numbers, owners, dates, methods).
- superseded: a decision in an older note was replaced by a later decision; the older note doesn't say so.
- stale_task: an unchecked "- [ ]" task that a later note shows is already done.
- duplicate: two notes cover the same topic and should be one.
Rules: quote text VERBATIM from the notes (short quotes, copied exactly). Use exact note titles.
Prefer the newer note (frontmatter date/created, or date in the title) as current_title.
Do not report style issues, missing links, or vague "follow up" placeholder tasks. If nothing is wrong,
return an empty list."""


# --- 1. gather -----------------------------------------------------------------------------------
def gather(vault: Vault, project: str, max_tokens: int = 200_000) -> dict:
    from .context import get_context

    return get_context(vault, project, max_tokens=max_tokens)


def _note_date(text: str, title: str) -> str:
    fm, _ = split_frontmatter(text)
    d = fm.get("date") or fm.get("created")
    if d:
        return str(d)
    m = re.match(r"(\d{4}-\d{2}-\d{2})", title)
    return m.group(1) if m else "undated"


def build_input(ctx: dict) -> str:
    parts = [f"PROJECT: {ctx['query']}\n{len(ctx['notes'])} notes follow.\n"]
    for n in ctx["notes"]:
        parts.append(f"\n===== NOTE: {n['title']} | path: {n['path']} | date: {_note_date(n['text'], n['title'])} "
                     f"| included as: {n['why']}\n{n['text'].strip()}\n")
    return "".join(parts)


# --- 2. find -------------------------------------------------------------------------------------
def _norm(s: str) -> str:
    s = s.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", s).strip().lower()


def check_quotes(findings: list[dict], ctx: dict) -> list[dict]:
    """Mark each finding verified only if every quote really appears in the cited note."""
    texts = {n["title"].lower(): _norm(n["text"]) for n in ctx["notes"]}
    for f in findings:
        misses = []
        for ev in f.get("evidence", []):
            body = texts.get(ev.get("title", "").lower())
            if body is None or _norm(ev.get("quote", "")) not in body:
                misses.append(ev.get("title", "?"))
        f["verified"] = not misses and bool(f.get("evidence"))
        if misses:
            f["unverified_quotes_in"] = misses
    return findings


def find_issues(ctx: dict, client=None) -> tuple[list[dict], dict]:
    from .config import MODEL_IDS, clients

    if client is None:
        client, _ = clients()
    t0 = time.time()
    r = client.interactions.create(
        model=MODEL_IDS["manager"], input=build_input(ctx), system_instruction=SYSTEM,
        generation_config={"thinking_level": "medium"},
        response_format={"type": "text", "mime_type": "application/json", "schema": FINDINGS_SCHEMA},
    )
    findings = json.loads(r.output_text).get("findings", [])
    usage = getattr(r, "usage", None)
    meta = {"interaction_id": getattr(r, "id", None), "seconds": round(time.time() - t0, 1),
            "input_tokens": getattr(usage, "total_input_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None)}
    return check_quotes(findings, ctx), meta


# --- vault-level check (runs locally and inside the sandbox) -------------------------------------
def check_vault(vault: Vault, scope: list[str] | None = None) -> dict:
    """Every note in scope: frontmatter parses, every [[link]] resolves. Exit 0 when ok."""
    issues = []
    titles = scope if scope is not None else list(vault.notes)
    for t in titles:
        n = vault.notes.get(t)
        if n is None:
            issues.append({"note": t, "issue": "note is missing (was it deleted or renamed?)"})
            continue
        if n.frontmatter.get("__invalid__"):
            issues.append({"note": t, "issue": "frontmatter does not parse"})
        for link in n.links:
            if vault.resolve(link) is None:
                issues.append({"note": t, "issue": f"[[{link}]] does not resolve"})
    return {"ok": not issues, "issues": issues}


# --- 3. apply with the Managed Agent -------------------------------------------------------------
def agent_sources(vault: Vault, ctx: dict, findings: list[dict]) -> list[dict]:
    from .config import REPO_ROOT

    full = {n["path"] for n in ctx["notes"]}
    src = [{"type": "inline", "target": f"c2v/{f}", "content": (REPO_ROOT / "c2v" / f).read_text(encoding="utf-8")}
           for f in ("__init__.py", "vault.py", "maintain.py")]
    src.append({"type": "inline", "target": "requirements.txt", "content": "pyyaml>=6.0\n"})
    for n in vault.notes.values():
        p = n.path.as_posix()
        if p in full:
            content = (vault.root / n.path).read_text(encoding="utf-8")
        else:
            head = f"---\naliases: {json.dumps(n.aliases)}\n---\n" if n.aliases else ""
            content = head + "(skeleton: body withheld, do not edit)\n"
        src.append({"type": "inline", "target": f"vault/{p}", "content": content})
    src.append({"type": "inline", "target": "scope.json", "content": json.dumps(sorted(full), indent=1)})
    src.append({"type": "inline", "target": "findings.json", "content": json.dumps(findings, indent=1)})
    return src


def apply_prompt(findings: list[dict]) -> str:
    return f"""You maintain an Obsidian vault. vault/ holds the notes; the notes listed in scope.json have full
text, every other note is a skeleton you must not edit. findings.json lists {len(findings)} verified problems.
Fix each one by editing markdown files under vault/ (only files listed in scope.json):
- superseded / contradiction: in the stale note, right under the frontmatter's closing --- and the H1 title,
  add a callout:
  > [!warning] Superseded by [[<current note title>]]
  > <one line: what changed>
  If a concept note states the old fact, update that sentence to the current fact and cite [[<current note>]].
- stale_task: change "- [ ]" to "- [x]" for the task that is done and append " (done, see [[<note>]])".
- duplicate: move any facts that exist only in the duplicate into the canonical note, then replace the
  duplicate's body (keep its frontmatter) with:
  > [!note] Merged into [[<canonical title>]]
  and change links that pointed at the duplicate (in scope notes) to the canonical title.
Never delete or rename files, never touch frontmatter except to keep it valid, keep all other text.
Then run: python -m c2v.maintain --check --vault vault --scope scope.json
(pip install -r requirements.txt first if yaml is missing). Fix and re-run until it exits 0.
Finally reply with one line per finding: what you changed, and the final exit code."""


def apply_with_agent(vault: Vault, ctx: dict, findings: list[dict], on_event=print, beta=None) -> dict:
    from . import agent_verify as av
    from .config import MODEL_IDS, clients

    if beta is None:
        _, beta = clients()
    emit = lambda text, **d: on_event(text)  # noqa: E731
    run, steps, secs = av._run_turn(
        beta, emit, 1, input=apply_prompt(findings),
        environment={"type": "remote", "sources": agent_sources(vault, ctx, findings)},
        agent_config={"type": "antigravity", "model": av.AGENT_MODEL, "max_total_tokens": 200_000})
    env_id = av._get(run, "environment_id")
    changed = []
    for n in ctx["notes"]:
        try:
            data = beta.environments.files.download(path=f"vault/{n['path']}", environment_id=env_id)
        except Exception as e:  # never delete locally because a download failed
            on_event(f"download failed for {n['path']}: {type(e).__name__}")
            continue
        new = bytes(data).decode("utf-8")
        local = vault.root / n["path"]
        if new != local.read_text(encoding="utf-8"):
            local.write_text(new, encoding="utf-8")
            changed.append(n["path"])
    vault.reload()
    check = check_vault(vault, [n["title"] for n in ctx["notes"]])
    rec = {"agent": MODEL_IDS["agent"], "interaction_id": av._get(run, "id"), "environment_id": env_id,
           "status": str(av._get(run, "status")), "seconds": round(secs, 1), "tokens": av._tokens(run),
           "changed": changed, "check": check, "reply": av._get(run, "output_text"),
           "commands": [s["code"] for s in steps if s["type"] == "code_execution_call"]}
    av._log({"kind": "maintain", **{k: v for k, v in rec.items() if k != "reply"}})
    return rec


# --- 4. demo seed --------------------------------------------------------------------------------
CAP = "10 Learning and Teaching/11 Academic/EECE 410 Capstone Design/Solar Microgrid Capstone.md"
SEED = {
    # (1) superseded decision + contradiction: 11-12 and the concept note say definite-time; 11-20 changes it
    "Sessions/2026-11/2026-11-12 Capstone - Agreed on relay baseline.md": """---
type: session
category: meeting
project: "[[Solar Microgrid Capstone]]"
date: "2026-11-12"
tags: [session, meeting]
---
# Agreed on relay baseline

## Summary
Met with the capstone team. Decided the ML detector will be compared against a definite-time overcurrent
relay: 50 ms delay, pickup at 1.2x rated current. Worked on [[Solar Microgrid Capstone]].

Concepts: [[Relay baseline]] · [[Fault detection]]

## Next steps
- [ ] Implement the definite-time relay in the sim harness
""",
    "Sessions/2026-11/2026-11-20 Capstone - Switched relay baseline.md": """---
type: session
category: meeting
project: "[[Solar Microgrid Capstone]]"
date: "2026-11-20"
tags: [session, meeting]
---
# Switched relay baseline

## Summary
Prof. Okafor rejected the definite-time relay as too weak a baseline. The baseline is now an inverse-time
overcurrent relay on the IEC standard inverse curve (TMS 0.1, pickup 1.1x). Worked on
[[Solar Microgrid Capstone]].

Concepts: [[Relay Baseline Notes]] · [[Fault detection]]

## Next steps
- [ ] Re-run the comparison against the inverse-time relay
""",
    "40 Knowledge/Concepts/Relay baseline.md": """---
type: concept
tags: [concept]
---
# Relay baseline
Conventional overcurrent relay logic used as the comparison for ML detectors. In the capstone this is a
definite-time relay with a 50 ms delay.
""",
    # (3) duplicate concept note
    "40 Knowledge/Concepts/Relay Baseline Notes.md": """---
type: concept
tags: [concept]
---
# Relay Baseline Notes
The relay baseline is standard overcurrent relay logic that ML fault detectors are compared against.
Inverse-time relays trip faster for larger fault currents.
""",
    # (2) stale open loop: the project still lists the sims as to-do, 11-18 says they are done
    "Sessions/2026-11/2026-11-18 Capstone - Inverter fault sim results.md": """---
type: session
category: coding
project: "[[Solar Microgrid Capstone]]"
date: "2026-11-18"
tags: [session, coding]
---
# Inverter fault sim results

## Summary
Ran all inverter fault sims: arc faults and line-to-ground faults are done, 240 runs, results saved to
sims/results.csv. Worked on [[Solar Microgrid Capstone]].

Concepts: [[Inverter control]] · [[Fault detection]]

## Next steps
- [ ] Label the arc-fault runs for the ML detector
""",
    CAP: """---
type: project
status: active
parent: "[[Projects]]"
tags: [project]
---
# Solar Microgrid Capstone

Concepts: [[Fault detection]] · [[Relay baseline]] · [[Inverter control]]

## Open loops
- [ ] Run the inverter fault sims (arc + line-to-ground)
- [ ] Pick the relay baseline

## Log
- 2026-11-12 [[2026-11-12 Capstone - Agreed on relay baseline|Agreed on relay baseline]] (meeting)
- 2026-11-18 [[2026-11-18 Capstone - Inverter fault sim results|Inverter fault sim results]] (coding)
- 2026-11-20 [[2026-11-20 Capstone - Switched relay baseline|Switched relay baseline]] (meeting)
""",
}


def seed_demo(dst: Path) -> Path:
    from .config import REPO_ROOT

    src = REPO_ROOT / "mock_vault"
    dst = Path(dst).expanduser().resolve()
    if dst == src.resolve() or src.resolve() in dst.parents:
        raise SystemExit("refusing to seed inside mock_vault/; give a separate copy path")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    for rel, text in SEED.items():
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        (dst / rel).write_text(text, encoding="utf-8")
    return dst


def _guard(vault: Vault) -> None:
    from .config import REPO_ROOT

    for protected in ("mock_vault", "demo_vault"):
        if vault.root == (REPO_ROOT / protected).resolve():
            raise SystemExit(f"--apply refuses to edit {protected}/ itself; run it on a copy (--seed-demo)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    ap.add_argument("--vault")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max-tokens", type=int, default=200_000)
    ap.add_argument("--out", help="write findings/apply JSON here")
    ap.add_argument("--check", action="store_true", help="vault check: links resolve, frontmatter parses")
    ap.add_argument("--scope", help="JSON list of note paths to check (default: all)")
    ap.add_argument("--seed-demo", metavar="DST")
    a = ap.parse_args(argv)

    if a.seed_demo:
        print(seed_demo(Path(a.seed_demo)))
        return 0
    if a.check:
        v = Vault(a.vault or "vault")
        scope = None
        if a.scope:
            paths = set(json.loads(Path(a.scope).read_text()))
            scope = [n.title for n in v.notes.values() if n.path.as_posix() in paths]
            scope += [Path(p).stem for p in paths if Path(p).stem not in v.notes]
        rep = check_vault(v, scope)
        print(json.dumps(rep, indent=2))
        return 0 if rep["ok"] else 1
    if not a.project:
        ap.error("--project is required")

    from .config import VAULT_PATH

    vault = Vault(a.vault or VAULT_PATH)
    ctx = gather(vault, a.project, a.max_tokens)
    print(f"gathered {len(ctx['notes'])} notes, ~{ctx['tokens']} tokens", file=sys.stderr)
    findings, meta = find_issues(ctx)
    out = {"project": a.project, "neon": meta, "notes": [n["title"] for n in ctx["notes"]], "findings": findings}
    for f in findings:
        mark = "ok " if f["verified"] else "?? "
        print(f"{mark}[{f['kind']}] {f['summary']}\n     stale: {f['stale_title']} -> current: {f['current_title']}",
              file=sys.stderr)
    if a.apply:
        _guard(vault)
        todo = [f for f in findings if f["verified"]]
        out["apply"] = apply_with_agent(vault, ctx, todo, on_event=lambda t: print("  | " + t[:300], file=sys.stderr))
    text = json.dumps(out, indent=2, default=str)
    if a.out:
        Path(a.out).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
