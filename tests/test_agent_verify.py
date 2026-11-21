"""Offline tests for the managed-agent verify loop (fake client shaped like google-genai's)."""
import json
from pathlib import Path
from types import SimpleNamespace as NS

import c2v.agent_verify as av
from c2v.schemas import NoteDraft
from c2v.vault import Vault
from c2v.verify import verify_draft

DEMO = Path(__file__).resolve().parent.parent / "demo_vault"


def bad_draft():
    return NoteDraft(title="Momentum Whiteboard", folder="10 Learning/EECE448",
                     frontmatter={"type": "class", "created": "2026-11-21"},
                     body="Momentum keeps a running average of gradients so updates stop zig-zagging.",
                     links=["Gradient Descent Notes", "Gradient Descnt"])


class FakeInteractions:
    def __init__(self, polls):
        self.polls, self.calls = polls, []

    def create(self, **kw):
        self.calls.append(kw)
        return self.polls.pop(0)

    def get(self, id):
        return self.polls.pop(0)

    def cancel(self, id):
        pass


class FakeBeta:
    def __init__(self, polls, files):
        self.interactions = FakeInteractions(polls)
        self.environments = NS(files=NS(download=lambda path, environment_id: files.pop(0)))


def step(**kw):
    return NS(**kw)


def test_skeleton_has_no_bodies():
    v = Vault(DEMO)
    src = av.skeleton_sources(bad_draft(), v)
    targets = {s["target"] for s in src}
    assert "c2v/verify.py" in targets and "draft.json" in targets
    note = next(s for s in src if s["target"].endswith("Gradient Descent Notes.md"))
    assert "Momentum smooths" not in note["content"]
    alias = next(s for s in src if s["target"].endswith("EECE 448 Machine Learning.md"))
    assert "eece448" in alias["content"]


def test_agent_fix_loop(tmp_path, monkeypatch):
    monkeypatch.setattr(av, "LOG_PATH", tmp_path / "turns.jsonl")
    monkeypatch.setattr(av, "POLL_S", 0)
    v = Vault(DEMO)
    d = bad_draft()
    rep = verify_draft(d, v)
    assert not rep.ok

    fixed = d.model_copy(update={"folder": "10 Learning/EECE 448", "links": ["Gradient Descent Notes"]})
    call = step(type="code_execution_call", id="c1",
                arguments=NS(code="python -m c2v.verify --vault vault --draft draft.json"))
    res = step(type="code_execution_result", call_id="c1", result='{"ok": true}', is_error=False)
    polls = [
        NS(id="i1", environment_id="env1", status="in_progress", steps=[], usage=None, output_text=None),
        NS(id="i1", environment_id="env1", status="in_progress", steps=[call], usage=None, output_text=None),
        NS(id="i1", environment_id="env1", status="completed", steps=[call, res],
           usage=NS(total_tokens=1234), output_text="exit 0"),
    ]
    beta = FakeBeta(polls, [fixed.model_dump_json().encode()])
    seen = []
    out, out_rep = av.agent_fix(d, rep, v, on_event=lambda t, **k: seen.append(t), beta=beta)

    assert out_rep.ok and out.folder == "10 Learning/EECE 448"
    kw = beta.interactions.calls[0]
    assert kw["agent"] == "antigravity-preview-09-2026" and kw["background"] is True
    assert kw["environment"]["type"] == "remote"
    assert any(t.startswith("$ python -m c2v.verify") for t in seen)
    rec = json.loads((tmp_path / "turns.jsonl").read_text().splitlines()[0])
    assert rec["tokens"] == 1234 and rec["ok_after"] and rec["draft_source"] == "sandbox draft.json"
    assert len(rec["issues_before"]) == 2


def test_second_turn_reuses_environment_and_falls_back_to_reply(tmp_path, monkeypatch):
    monkeypatch.setattr(av, "LOG_PATH", tmp_path / "turns.jsonl")
    monkeypatch.setattr(av, "POLL_S", 0)
    v = Vault(DEMO)
    d = bad_draft()
    rep = verify_draft(d, v)
    still_bad = d.model_copy(update={"folder": "10 Learning/EECE 448"})
    fixed = still_bad.model_copy(update={"links": ["Gradient Descent Notes"]})
    polls = [
        NS(id="i1", environment_id="env1", status="completed", steps=[], usage=None,
           output_text=f"<draft>{still_bad.model_dump_json()}</draft>"),
        NS(id="i2", environment_id="env1", status="completed", steps=[], usage=None,
           output_text=f"done <draft>{fixed.model_dump_json()}</draft>"),
    ]
    beta = FakeBeta(polls, [b"not json", b"not json"])
    out, out_rep = av.agent_fix(d, rep, v, beta=beta)
    assert out_rep.ok
    second = beta.interactions.calls[1]
    assert second["previous_interaction_id"] == "i1" and second["environment"] == "env1"
