"""Lane A: transcribe / route / manage / pipeline with fake Gemini clients (no network)."""
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from c2v import manage
from c2v.manage import draft_note, fast_draft, mechanical_fix, repair
from c2v.pipeline import file_capture
from c2v.route import NEW, build_questions, route
from c2v.schemas import Capture, MediaKind, NoteDraft, RoutedAnswer, RoutingDecision
from c2v.transcribe import media_part, transcribe
from c2v.vault import Vault
from c2v.verify import verify_draft

DEMO = Path(__file__).resolve().parent.parent / "demo_vault"
PNG = bytes.fromhex(  # 1x1 transparent png
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")

CAPTURE_JSON = {
    "transcript": "Momentum: v = beta*v + grad; w -= lr*v. Stops zig-zag in narrow valleys. "
                  "TODO try beta=0.9 on HW3 for EECE 448.",
    "summary": "Whiteboard on momentum for gradient descent in EECE 448.",
    "key_terms": ["EECE 448", "momentum", "gradient descent"],
    "action_items": ["Try beta=0.9 on HW3"],
    "legibility": 0.9,
    "notes": "",
}


class FakeInteractions:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return SimpleNamespace(id=f"int-{len(self.calls)}", output_text=json.dumps(out))


class FakeDecisions:
    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(answers={
            k: SimpleNamespace(type="choice", choice=c, confidence=p, probabilities={c: p, "other": 1 - p})
            for k, (c, p) in self.answers.items()})


def fake_client(*outputs):
    return SimpleNamespace(interactions=FakeInteractions(outputs))


def fake_beta(**answers):
    return SimpleNamespace(decisions=FakeDecisions(answers))


@pytest.fixture
def vault(tmp_path):
    shutil.copytree(DEMO, tmp_path / "v")
    return Vault(tmp_path / "v")


@pytest.fixture
def image(tmp_path):
    p = tmp_path / "board.png"
    p.write_bytes(PNG)
    return p


def capture(**kw):
    base = dict(source_path="x.png", media_kind=MediaKind.image, **CAPTURE_JSON)
    base.update(kw)
    base["notes"] = base["notes"] or None
    return Capture(**base)


def routing(conf=0.9, folder="10 Learning/EECE 448", merge=NEW, escalate=False):
    a = lambda c: RoutedAnswer(choice=c, confidence=conf, probabilities={c: conf})  # noqa: E731
    return RoutingDecision(note_type=a("class"), folder=a(folder), merge_target=a(merge), escalate=escalate)


# --- transcribe ---------------------------------------------------------------------------
def test_media_part_inline_image(image):
    part = media_part(image)
    assert part["type"] == "image" and part["mime_type"] == "image/png" and part["data"]


def test_transcribe_structured_output(image):
    c = fake_client(CAPTURE_JSON)
    cap = transcribe(image, client=c)
    assert cap.media_kind is MediaKind.image and cap.legibility == 0.9 and cap.notes is None
    kw = c.interactions.calls[0]
    assert kw["model"] == "gemini-4-hydrogen"
    assert kw["response_format"]["schema"]["required"][0] == "transcript"
    assert kw["input"][1]["type"] == "image"
    assert "temperature" not in kw


def test_transcribe_clamps_legibility(image):
    cap = transcribe(image, client=fake_client({**CAPTURE_JSON, "legibility": 1.7}))
    assert cap.legibility == 1.0


# --- route --------------------------------------------------------------------------------
def test_build_questions_use_real_folders_and_candidates(vault):
    q = build_questions(capture(), vault)
    assert "10 Learning/EECE 448" in q["folder"]["criteria"] and "other" in q["folder"]["criteria"]
    assert "Gradient Descent Notes" in q["merge_target"]["criteria"] and NEW in q["merge_target"]["criteria"]
    assert all(2 <= len(v["criteria"]) <= 255 for v in q.values())


def test_route_confident(vault):
    beta = fake_beta(note_type=("class", 0.92), folder=("10 Learning/EECE 448", 0.88), merge_target=(NEW, 0.81))
    d = route(capture(), vault, beta_client=beta)
    assert not d.escalate and d.folder.choice == "10 Learning/EECE 448"
    assert d.folder.probabilities["10 Learning/EECE 448"] == 0.88
    assert beta.decisions.calls[0]["model"] == "gemini-decision-1"


def test_route_escalates_on_low_confidence_and_legibility(vault):
    beta = fake_beta(note_type=("class", 0.92), folder=("10 Learning/EECE 448", 0.51), merge_target=(NEW, 0.9))
    d = route(capture(), vault, beta_client=beta)
    assert d.escalate and "folder" in d.reason
    beta = fake_beta(note_type=("class", 0.92), folder=("10 Learning/EECE 448", 0.95), merge_target=(NEW, 0.9))
    assert route(capture(legibility=0.3), vault, beta_client=beta).escalate


def test_route_unknown_choice_becomes_other(vault):
    beta = fake_beta(note_type=("class", 0.9), folder=("Made Up", 0.99), merge_target=(NEW, 0.9))
    d = route(capture(), vault, beta_client=beta)
    assert d.folder.choice == "other" and d.escalate


# --- manage -------------------------------------------------------------------------------
def test_fast_draft_verifies(vault):
    d = fast_draft(capture(), routing(), vault)
    assert verify_draft(d, vault).ok, verify_draft(d, vault)
    assert d.frontmatter["type"] == "class" and "- [ ] Try beta=0.9 on HW3" in d.body
    assert "Gradient Descent Notes" in d.links


def test_fast_draft_merge(vault):
    d = fast_draft(capture(), routing(merge="Gradient Descent Notes"), vault)
    assert d.merge_into == "Gradient Descent Notes" and verify_draft(d, vault).ok


def test_draft_note_escalated_calls_neon(vault):
    neon_out = {"title": "Momentum Whiteboard", "folder": "10 Learning/EECE 448",
                "frontmatter": {"type": "class", "created": "2026-11-21", "source": "image", "tags": ["eece-448"]},
                "body": "Momentum smooths gradient descent updates.", "links": ["Gradient Descent Notes"],
                "merge_into": ""}
    c = fake_client(neon_out)
    d = draft_note(capture(), routing(conf=0.5, escalate=True), vault, client=c)
    assert d.merge_into is None and verify_draft(d, vault).ok
    kw = c.interactions.calls[0]
    assert kw["model"] == "gemini-4-neon" and "conf 0.50" in kw["input"]


def test_repair_chains_and_falls_back(vault):
    bad = {"title": "Gradient Descent Notes", "folder": "Nowhere",
           "frontmatter": {"type": "class", "created": "2026-11-21", "source": "image", "tags": []},
           "body": "Momentum smooths gradient descent updates.", "links": ["Ghost"], "merge_into": ""}
    good = {**bad, "title": "Momentum Whiteboard", "folder": "10 Learning/EECE 448", "links": []}
    c = fake_client(bad, good)
    d = draft_note(capture(), routing(conf=0.5, escalate=True), vault, client=c)
    rep = verify_draft(d, vault)
    assert not rep.ok
    fixed = repair(d, rep, vault, client=c)
    assert verify_draft(fixed, vault).ok
    assert c.interactions.calls[1]["previous_interaction_id"] == "int-1"
    # Neon down -> deterministic fix still produces a valid draft
    fixed2 = repair(d, rep, vault, client=fake_client(RuntimeError("503")))
    assert verify_draft(fixed2, vault).ok


def test_mechanical_fix_keeps_parent_folder(vault):
    d = NoteDraft(title="X note", folder="10 Learning/EECE 448/Nope", frontmatter={"type": "weird"},
                  body="Body text long enough to pass.", links=["eece448", "Ghost"])
    f = mechanical_fix(d, vault)
    assert f.folder == "10 Learning/EECE 448" and f.links == ["EECE 448 Machine Learning"]
    assert verify_draft(f, vault).ok


# --- pipeline -----------------------------------------------------------------------------
def test_pipeline_end_to_end_fast_path(vault, image):
    beta = fake_beta(note_type=("class", 0.92), folder=("10 Learning/EECE 448", 0.88), merge_target=(NEW, 0.81))
    res = file_capture(image, vault, client=fake_client(CAPTURE_JSON), beta_client=beta)
    assert res.verify.ok and res.path_taken == "auto"
    written = Path(res.written_path)
    assert written.exists() and written.parent.name == "EECE 448"
    assert "[[Gradient Descent Notes]]" in written.read_text()


def test_pipeline_escalated_path(vault, image):
    beta = fake_beta(note_type=("idea", 0.4), folder=("10 Learning/EECE 448", 0.6), merge_target=(NEW, 0.5))
    neon_out = {"title": "Momentum Idea", "folder": "10 Learning/EECE 448",
                "frontmatter": {"type": "class", "created": "2026-11-21", "source": "image", "tags": []},
                "body": "Momentum smooths gradient descent updates.", "links": ["EECE 448 Machine Learning"],
                "merge_into": ""}
    res = file_capture(image, vault, client=fake_client(CAPTURE_JSON, neon_out), beta_client=beta)
    assert res.verify.ok and res.path_taken == "escalated" and res.written_path
    manage._INTERACTIONS.clear()


def test_video_prompt_asks_for_both_channels(tmp_path):
    vid = tmp_path / "clip.mp4"
    vid.write_bytes(b"\x00" * 64)
    c = fake_client(CAPTURE_JSON)
    transcribe(vid, client=c)
    kw = c.interactions.calls[0]
    assert "ON SCREEN" in kw["input"][0]["text"]
    assert kw["input"][1]["type"] == "video" and kw["input"][1]["processing"] == "agentic"
    c2 = fake_client(CAPTURE_JSON)
    img = tmp_path / "b.png"
    img.write_bytes(PNG)
    transcribe(img, client=c2)
    assert "ON SCREEN" not in c2.interactions.calls[0]["input"][0]["text"]
