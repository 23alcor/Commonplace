"""LANE C. Managed Agent verifier: Antigravity, running in a Google-hosted sandbox, fixes a NoteDraft
until `python -m c2v.verify` exits 0. That is the "the agent checked its own work" story.

How it works (checked against google-genai 3.6 types and the Antigravity agent / agent-environment docs):
- Turn 1: beta.interactions.create(agent=..., environment={"type": "remote", "sources": [inline files]},
  agent_config={"type": "antigravity", ...}, background=True). The sandbox gets c2v/{schemas,vault,verify}.py,
  a *skeleton* of the vault (folders + titles + aliases, no note bodies, so private notes never leave
  the machine; verify only needs those) and draft.json.
- We poll interactions.get(id) and report each new step (commands run, results) as it appears.
- The fixed draft is read back by downloading the exact draft.json the agent verified
  (beta.environments.files.download); if that fails we parse the <draft> block from the final reply.
- Local verify_draft is the ground truth. If it still fails, turn N+1 reuses the same sandbox:
  previous_interaction_id=run.id, environment=run.environment_id.
- Every turn is appended to runs/agent_turns.jsonl (tokens, seconds, issues before/after, commands).
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Optional

from .config import MODEL_IDS, REPO_ROOT
from .schemas import NoteDraft, VerifyReport
from .vault import Vault
from .verify import ALLOWED_TYPES, REQUIRED_FRONTMATTER, verify_draft

AGENT_MODEL = os.environ.get("C2V_AGENT_MODEL", MODEL_IDS["manager"])  # gemini-4-neon
MAX_TURNS = int(os.environ.get("C2V_AGENT_TURNS", "3"))
TURN_TIMEOUT_S = float(os.environ.get("C2V_AGENT_TIMEOUT", "240"))
POLL_S = 2.0
MAX_TOKENS = 100_000
LOG_PATH = Path(os.environ.get("C2V_AGENT_LOG", REPO_ROOT / "runs" / "agent_turns.jsonl"))
TERMINAL = {"completed", "failed", "cancelled", "incomplete", "budget_exceeded", "requires_action", "idle"}
INLINE_LIMIT = 1_900_000  # docs: inline sources max 2 MB total
CODE_FILES = ("__init__.py", "schemas.py", "vault.py", "verify.py")
DRAFT_TAG = re.compile(r"<draft>\s*(\{.*?\})\s*</draft>", re.DOTALL)

OnEvent = Optional[Callable[..., None]]


# --- sandbox contents ----------------------------------------------------------------------------
def skeleton_sources(draft: NoteDraft, vault: Vault) -> list[dict]:
    """Inline sources: verifier code + vault skeleton (titles/aliases/folders only) + draft.json."""
    import yaml

    src: list[dict] = []
    for name in CODE_FILES:
        src.append({"type": "inline", "target": f"c2v/{name}",
                    "content": (REPO_ROOT / "c2v" / name).read_text(encoding="utf-8")})
    src.append({"type": "inline", "target": "requirements.txt", "content": "pydantic>=2.7\npyyaml>=6.0\n"})
    for folder in vault.folder_list():
        src.append({"type": "inline", "target": f"vault/{folder}/.keep", "content": "folder\n"})
    for note in vault.notes.values():
        fm = {"aliases": note.aliases} if note.aliases else {}
        head = f"---\n{yaml.safe_dump(fm, allow_unicode=True).strip()}\n---\n" if fm else ""
        src.append({"type": "inline", "target": f"vault/{note.path.as_posix()}",
                    "content": head + "(body withheld: skeleton copy for verification)\n"})
    src.append({"type": "inline", "target": "draft.json", "content": draft.model_dump_json(indent=2)})
    size = sum(len(s["content"].encode()) for s in src)
    if size > INLINE_LIMIT:
        raise ValueError(f"vault skeleton is {size} bytes, over the inline source limit")
    return src


def first_prompt(draft: NoteDraft, report: VerifyReport) -> str:
    issues = "\n".join(f"- {i.code}: {i.detail}" for i in report.issues)
    return f"""You are the verifier for an Obsidian vault filing pipeline. Your one job: make draft.json pass
the vault checks without changing what the note says.

Workspace: c2v/ (the checker), vault/ (folders and note titles of the real vault; bodies withheld),
draft.json (a NoteDraft: title, folder, frontmatter, body, links, merge_into).

1. If `python -c "import pydantic, yaml"` fails, run `pip install -r requirements.txt`.
2. Run: python -m c2v.verify --vault vault --draft draft.json
3. If the exit code is not 0, edit draft.json to fix every reported issue, then run step 2 again.
   Repeat until the exit code is 0.

Rules for fixes:
- broken_link: link only to notes that exist (`find vault -name '*.md'`; the title is the file name
  without .md, aliases also resolve). Change the link to the existing note it clearly means, or drop it.
- missing_folder: `folder` must be an existing directory under vault/, written relative to vault/
  (e.g. "10 Learning/EECE 448"). Pick the closest real folder. Never invent one.
- duplicate_title: either make the title specific and new, or set merge_into to the existing title if
  this capture is clearly an update to that note.
- bad_frontmatter: needs {list(REQUIRED_FRONTMATTER)}; type must be one of {sorted(ALLOWED_TYPES)};
  created is an ISO date (YYYY-MM-DD).
- empty_body: the body must keep the capture's content. Do not invent facts.
Keep body text as is unless an issue requires a change.

Current issues:
{issues}

When verify exits 0, reply with the final exit code and the final draft.json inside <draft>...</draft>."""


def followup_prompt(report: VerifyReport) -> str:
    issues = "\n".join(f"- {i.code}: {i.detail}" for i in report.issues)
    return ("I re-ran the checker against the real vault and draft.json still fails:\n" + issues +
            "\nFix draft.json, re-run `python -m c2v.verify --vault vault --draft draft.json` until it "
            "exits 0, then reply with the final draft.json inside <draft>...</draft>.")


# --- reading interactions ------------------------------------------------------------------------
def _get(obj: Any, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _text(obj: Any, limit: int = 600) -> str:
    """Flatten strings / content lists / text parts into one short string."""
    if obj is None:
        return ""
    if isinstance(obj, str):
        s = obj
    elif isinstance(obj, (list, tuple)):
        s = "\n".join(t for t in (_text(o, limit) for o in obj) if t)
    else:
        s = _get(obj, "text") or _text(_get(obj, "summary"), limit) or _text(_get(obj, "content"), limit)
        if not s and isinstance(obj, dict):
            s = json.dumps(obj, default=str)
    s = str(s).strip()
    return s if len(s) <= limit else s[: limit - 3] + "..."


def describe_step(step: Any) -> dict:
    """One compact log line per agent step."""
    kind = str(_get(step, "type", "unknown"))
    out: dict = {"type": kind}
    if kind == "code_execution_call":
        args = _get(step, "arguments")
        out["code"] = _text(_get(args, "code"), 400)
    elif kind == "code_execution_result":
        out["result"] = _text(_get(step, "result"), 600)
        out["is_error"] = bool(_get(step, "is_error"))
    elif kind in ("function_call", "mcp_server_tool_call"):
        out["name"] = _get(step, "name")
        args = _get(step, "arguments") or {}
        out["args"] = _text(json.dumps(args, default=str) if not isinstance(args, str) else args, 300)
    elif kind in ("function_result", "mcp_server_tool_result"):
        out["name"] = _get(step, "name")
        out["result"] = _text(_get(step, "result"), 600)
        out["is_error"] = bool(_get(step, "is_error"))
    elif kind == "thought":
        out["summary"] = _text(_get(step, "summary"), 300)
    elif kind == "model_output":
        out["text"] = _text(_get(step, "content"), 400)
    return out


def step_line(d: dict) -> str:
    t = d["type"]
    if t == "code_execution_call":
        return "$ " + (d.get("code") or "").replace("\n", "\n  ")
    if t == "code_execution_result":
        return ("! " if d.get("is_error") else "> ") + (d.get("result") or "")
    if t.endswith("_call"):
        return f"> {d.get('name')}({d.get('args', '')})"
    if t.endswith("_result"):
        return ("! " if d.get("is_error") else "< ") + f"{d.get('name') or ''} {d.get('result') or ''}".strip()
    if t == "thought":
        return "~ " + (d.get("summary") or "(thinking)")
    if t == "model_output":
        return d.get("text") or ""
    return t


def _tokens(run: Any) -> int | None:
    u = _get(run, "usage")
    return _get(u, "total_tokens") if u is not None else None


def parse_reply_draft(text: str | None) -> NoteDraft | None:
    m = DRAFT_TAG.search(text or "")
    if not m:
        return None
    try:
        return NoteDraft.model_validate_json(m.group(1))
    except Exception:
        return None


def download_draft(beta, environment_id: str | None) -> NoteDraft | None:
    if not environment_id:
        return None
    try:
        data = beta.environments.files.download(path="draft.json", environment_id=environment_id)
        if isinstance(data, (bytes, bytearray)) and data[:2] == b"\x1f\x8b":  # tarball, per REST docs
            import io
            import tarfile

            with tarfile.open(fileobj=io.BytesIO(data)) as tf:
                member = next(m for m in tf.getmembers() if m.name.endswith("draft.json"))
                data = tf.extractfile(member).read()
        return NoteDraft.model_validate_json(data)
    except Exception:
        return None


# --- the loop ------------------------------------------------------------------------------------
def _run_turn(beta, emit, turn: int, **create_kw) -> tuple[Any, list[dict], float]:
    t0 = time.time()
    run = beta.interactions.create(agent=MODEL_IDS["agent"], background=True, **create_kw)
    emit(f"turn {turn}: interaction {_get(run, 'id')} env {_get(run, 'environment_id')}")
    steps: list[dict] = []
    seen = 0
    while True:
        cur = list(_get(run, "steps") or [])
        for s in cur[seen:]:
            d = describe_step(s)
            steps.append(d)
            if d["type"] not in ("user_input",):
                emit(step_line(d))
        seen = len(cur)
        if str(_get(run, "status")) in TERMINAL:
            break
        if time.time() - t0 > TURN_TIMEOUT_S:
            try:
                beta.interactions.cancel(id=_get(run, "id"))
            except Exception:
                pass
            emit(f"turn {turn}: timed out after {TURN_TIMEOUT_S:.0f}s")
            break
        time.sleep(POLL_S)
        run = beta.interactions.get(id=_get(run, "id"))
    return run, steps, time.time() - t0


def _log(rec: dict) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
    except OSError:
        pass


def agent_fix(draft: NoteDraft, report: VerifyReport, vault: Vault, on_event: OnEvent = None,
              beta=None, max_turns: int = MAX_TURNS) -> tuple[NoteDraft, VerifyReport]:
    """Have the Antigravity managed agent fix `draft` in a sandbox until verify passes.

    Returns the best draft and its *local* verify report (the sandbox only sees a skeleton vault, so
    the local check is authoritative). On any agent failure the original draft/report come back.
    """
    emit = (lambda text, **d: on_event(text, **d)) if on_event else (lambda text, **d: None)
    if beta is None:
        from .config import clients

        _, beta = clients()

    run_id = f"{time.strftime('%Y%m%dT%H%M%S')}-{abs(hash(draft.title)) % 10_000:04d}"
    best, best_report = draft, report
    run = None
    for turn in range(1, max_turns + 1):
        before = [i.model_dump() for i in best_report.issues]
        if turn == 1:
            kw = dict(input=first_prompt(best, best_report),
                      environment={"type": "remote", "sources": skeleton_sources(best, vault)},
                      agent_config={"type": "antigravity", "model": AGENT_MODEL, "max_total_tokens": MAX_TOKENS})
        else:
            kw = dict(input=followup_prompt(best_report), previous_interaction_id=_get(run, "id"),
                      environment=_get(run, "environment_id"),
                      agent_config={"type": "antigravity", "model": AGENT_MODEL, "max_total_tokens": MAX_TOKENS})
        try:
            run, steps, secs = _run_turn(beta, emit, turn, **kw)
        except Exception as e:
            emit(f"turn {turn}: agent call failed: {type(e).__name__}: {e}")
            _log({"run": run_id, "turn": turn, "error": f"{type(e).__name__}: {e}", "issues_before": before})
            break

        env_id = _get(run, "environment_id")
        fixed = download_draft(beta, env_id)
        source = "sandbox draft.json"
        if fixed is None:
            fixed, source = parse_reply_draft(_get(run, "output_text")), "agent reply"
        new_report = verify_draft(fixed, vault) if fixed else None

        rec = {"run": run_id, "turn": turn, "interaction_id": _get(run, "id"), "environment_id": env_id,
               "status": str(_get(run, "status")), "seconds": round(secs, 1), "tokens": _tokens(run),
               "issues_before": before, "draft_source": source if fixed else None,
               "issues_after": [i.model_dump() for i in new_report.issues] if new_report else None,
               "ok_after": new_report.ok if new_report else False,
               "commands": [s["code"] for s in steps if s["type"] == "code_execution_call"],
               "steps": steps}
        _log(rec)
        if new_report is None:
            emit(f"turn {turn}: {rec['status']}, no usable draft returned ({secs:.0f}s, {rec['tokens']} tok)")
            continue
        emit(f"turn {turn}: {rec['status']} in {secs:.0f}s, {rec['tokens']} tok; local verify: "
             + ("pass" if new_report.ok else f"{len(new_report.issues)} issue(s)"),
             issues_before=len(before), issues_after=len(new_report.issues))
        if len(new_report.issues) <= len(best_report.issues):
            best, best_report = fixed, new_report
        if best_report.ok:
            break
    return best, best_report
