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


VIDEO_JSON = {
    "segments": [
        {"start": "0:00", "end": "0:42", "topic": "Momentum recap", "text": "So momentum keeps a running average.",
         "on_screen": "v = beta*v + grad\nw = w - lr*v"},
        {"start": "42s", "end": "1:30", "topic": "Plant bot wiring", "text": "Next, the ESP32 soil sensor.",
         "on_screen": ""},
    ],
    "key_moments": [{"at": "0:20", "kind": "diagram", "text": "momentum update equations"},
                    {"at": "01:10", "kind": "decision", "text": "use GPIO 34 for the soil sensor"}],
    "summary": "Momentum recap for EECE 448, then ESP32 soil sensor wiring for the plant bot.",
    "key_terms": ["EECE 448", "ESP32"], "action_items": ["order capacitive sensor"], "legibility": 0.9,
    "notes": "",
}


def test_video_transcribe_segments_and_key_moments(tmp_path):
    vid = tmp_path / "clip.mov"
    vid.write_bytes(b"\x00" * 64)
    c = fake_client(VIDEO_JSON)
    cap = transcribe(vid, client=c)
    kw = c.interactions.calls[0]
    assert kw["input"][1] == {**kw["input"][1], "type": "video", "mime_type": "video/mov"}
    assert kw["input"][1]["processing"] == "agentic"  # fake bytes: ffprobe can't read a length
    assert "segments" in kw["response_format"]["schema"]["required"]
    assert [s.start for s in cap.segments] == ["00:00", "00:42"] and cap.segments[1].end == "01:30"
    assert cap.segments[1].on_screen is None
    assert [(k.at, k.kind) for k in cap.key_moments] == [("00:20", "diagram"), ("01:10", "decision")]
    lines = cap.transcript.splitlines()
    assert lines[0] == "[00:00] (Momentum recap) So momentum keeps a running average."
    assert lines[1] == "[00:00] ON SCREEN: v = beta*v + grad / w = w - lr*v"
    assert lines[2].startswith("[00:42] (Plant bot wiring)")
    # images keep the plain prompt and schema
    c2 = fake_client(CAPTURE_JSON)
    img = tmp_path / "b.png"
    img.write_bytes(PNG)
    cap2 = transcribe(img, client=c2)
    assert "segments" not in c2.interactions.calls[0]["response_format"]["schema"]["properties"]
    assert cap2.segments == [] and cap2.key_moments == []


def test_big_video_goes_through_files_api_and_waits_for_active(tmp_path, monkeypatch):
    from c2v import transcribe as tr

    monkeypatch.setattr(tr, "INLINE_MAX_BYTES", 10)
    vid = tmp_path / "long.mp4"
    vid.write_bytes(b"\x00" * 64)
    states = iter(["PROCESSING", "ACTIVE"])
    files = SimpleNamespace(
        upload=lambda file: SimpleNamespace(name="files/1", uri="gs://u", state=SimpleNamespace(name="PROCESSING")),
        get=lambda name: SimpleNamespace(name=name, uri="gs://u", state=SimpleNamespace(name=next(states))))
    client = SimpleNamespace(files=files)
    monkeypatch.setattr(tr.time, "sleep", lambda s: None)
    part = media_part(vid, client)
    assert part["uri"] == "gs://u" and "data" not in part
    failed = SimpleNamespace(upload=lambda file: SimpleNamespace(name="f", uri="u", state="FAILED"))
    with pytest.raises(RuntimeError):
        media_part(vid, SimpleNamespace(files=failed))


# --- keep the source (scripts/tasks/a-keep-source.md) -------------------------------------
def _fast_beta(merge=NEW):
    return fake_beta(note_type=("class", 0.92), folder=("10 Learning/EECE 448", 0.88), merge_target=(merge, 0.81))


def test_written_note_keeps_full_source(vault, image):
    cap_json = {**CAPTURE_JSON, "transcript": "line one of the board\nline two: v = beta*v + grad\n\nTODO HW3"}
    res = file_capture(image, vault, client=fake_client(cap_json), beta_client=_fast_beta())
    assert res.verify.ok and res.written_path
    from c2v.vault import split_frontmatter

    fm, body = split_frontmatter(Path(res.written_path).read_text())
    # (b) frontmatter source -> original file copied under _attachments/, byte-identical
    assert fm["source"].startswith("_attachments/") and fm["media"] == "image"
    copied = vault.root / fm["source"]
    assert copied.read_bytes() == image.read_bytes()
    # (a) full transcript under ## Source in a collapsed callout, embed for images; summary on top
    assert body.lstrip().startswith(CAPTURE_JSON["summary"])
    src = body.split("## Source", 1)[1]
    assert f"![[{fm['source']}]]" in src and "> [!quote]- Transcript" in src
    assert "> line two: v = beta*v + grad\n>\n> TODO HW3" in src
    # the vault still indexes fine and the attachments folder is never offered as a destination
    vault.reload()
    assert verify_draft(NoteDraft(**{**res.draft.model_dump(), "title": "Another One"}), vault).ok
    assert "_attachments" not in build_questions(capture(), vault)["folder"]["criteria"]
    assert "_attachments" not in manage.vault_map(vault)


def test_dry_run_shows_source_but_touches_nothing(vault, image):
    res = file_capture(image, vault, dry_run=True, client=fake_client(CAPTURE_JSON), beta_client=_fast_beta())
    assert "## Source" in res.draft.body and res.draft.frontmatter["source"].startswith("_attachments/")
    assert not (vault.root / "_attachments").exists() and res.written_path is None


def test_merge_appends_source(vault, image):
    res = file_capture(image, vault, client=fake_client(CAPTURE_JSON), beta_client=_fast_beta("Gradient Descent Notes"))
    text = Path(res.written_path).read_text()
    assert res.written_path.endswith("Gradient Descent Notes.md")
    assert "## Update" in text and "> [!quote]- Transcript" in text and "![[_attachments/" in text


def test_finalize_idempotent_and_attachment_names(vault, image):
    from c2v.pipeline import write_note

    d = fast_draft(capture(source_path=str(image)), routing(), vault)
    _, final, rep = write_note(d, capture(source_path=str(image)), vault)
    assert rep.ok and final.body.count("## Source") == 1
    again = manage.finalize_note(final, capture(source_path=str(image)), final.frontmatter["source"])
    assert again.body.count("## Source") == 1
    # same bytes -> reuse the existing attachment; different bytes -> new name
    assert manage.attachment_path(capture(source_path=str(image)), d, vault) == final.frontmatter["source"]
    other = image.with_name("other.png")
    other.write_bytes(PNG + b"x")
    assert manage.attachment_path(capture(source_path=str(other)), d, vault) != final.frontmatter["source"]


def test_audio_source_embeds_player_and_text_has_no_embed():
    a = manage.source_section(capture(media_kind=MediaKind.audio), "_attachments/memo.m4a")
    assert "![[_attachments/memo.m4a]]" in a
    t = manage.source_section(capture(media_kind=MediaKind.text), "_attachments/note.txt")
    assert "![[" not in t and "> [!quote]- Transcript" in t


# --- video step 2: linked timeline ----------------------------------------------------------
NEON_VIDEO = {
    "title": "Momentum and Plant Bot Walkthrough", "folder": "10 Learning/EECE 448",
    "frontmatter": {"type": "reference", "created": "2026-11-21", "source": "video", "tags": ["video"]},
    "body": "Two-part walkthrough: momentum recap, then the plant bot soil sensor.\n\n- [ ] order capacitive sensor",
    "links": ["EECE 448 Machine Learning"], "merge_into": "",
    "timeline": [
        {"at": "0:00", "text": "Momentum update rule recap", "links": ["Gradient Descent Notes", "eece448"]},
        {"at": "42", "text": "ESP32 soil sensor wiring", "links": ["Plant Watering Bot"]},  # invented
    ],
}


def video_capture(tmp_path):
    vid = tmp_path / "clip.mp4"
    vid.write_bytes(b"\x00" * 64)
    return transcribe(vid, client=fake_client(VIDEO_JSON)), vid


def test_video_routes_to_neon_without_resending_video(vault, tmp_path):
    cap, _ = video_capture(tmp_path)
    beta = _fast_beta()  # router fully confident...
    d = route(cap, vault, beta_client=beta)
    assert d.escalate and "timeline" in d.reason  # ...but video still goes to Neon
    assert all(p["type"] == "text" for p in beta.decisions.calls[0]["input"])


def test_neon_video_timeline_links_resolve(vault, tmp_path):
    cap, _ = video_capture(tmp_path)
    c = fake_client(NEON_VIDEO)
    d = draft_note(cap, routing(conf=0.5, escalate=True), vault, client=c)
    kw = c.interactions.calls[0]
    assert "timeline" in kw["response_format"]["schema"]["required"] and "SEGMENTS:" in kw["input"]
    tl = d.body.split("## Timeline\n", 1)[1].split("\n\n")[0].splitlines()
    assert tl[0] == "- [00:00] Momentum update rule recap → [[Gradient Descent Notes]], [[EECE 448 Machine Learning]]"
    assert tl[1] == "- [00:42] ESP32 soil sensor wiring"  # invented link dropped, not rendered
    assert "- [01:10] **Decision:** use GPIO 34 for the soil sensor" in d.body
    assert d.links == ["EECE 448 Machine Learning", "Gradient Descent Notes"]
    assert d.body.startswith("Two-part walkthrough") and verify_draft(d, vault).ok


def test_repair_keeps_timeline(vault, tmp_path):
    cap, _ = video_capture(tmp_path)
    bad = {**NEON_VIDEO, "folder": "Nowhere"}
    fixed_out = {k: v for k, v in NEON_VIDEO.items() if k != "timeline"}
    fixed_out["body"] = "Fixed hub body, long enough to pass."
    c = fake_client(bad, fixed_out)
    d = draft_note(cap, routing(conf=0.5, escalate=True), vault, client=c)
    rep = verify_draft(d, vault)
    assert not rep.ok
    f = repair(d, rep, vault, client=c)
    assert "## Timeline" not in c.interactions.calls[1]["input"]  # Neon never sees the owned sections
    assert f.body.startswith("Fixed hub body") and f.body.count("## Timeline") == 1
    assert "[[Gradient Descent Notes]]" in f.body and verify_draft(f, vault).ok


def test_video_pipeline_writes_hub_note(vault, tmp_path):
    _, vid = video_capture(tmp_path)
    res = file_capture(vid, vault, client=fake_client(VIDEO_JSON, NEON_VIDEO), beta_client=_fast_beta())
    assert res.verify.ok and res.path_taken == "escalated"
    text = Path(res.written_path).read_text()
    order = [text.index(h) for h in ("Two-part walkthrough", "## Timeline", "## Key moments", "## Source", "## Related")]
    assert order == sorted(order)
    assert "> [00:42] (Plant bot wiring) Next, the ESP32 soil sensor." in text
    assert "![[_attachments/" in text and text.count("## Timeline") == 1


def test_fast_draft_video_gets_unlinked_timeline(vault, tmp_path):
    cap, _ = video_capture(tmp_path)
    d = fast_draft(cap, routing(), vault)
    assert "- [00:00] Momentum recap" in d.body and "- [00:42] Plant bot wiring" in d.body
    assert verify_draft(d, vault).ok


def test_video_processing_mode_by_length(monkeypatch):
    from c2v import transcribe as tr

    monkeypatch.setattr(tr, "video_duration_s", lambda p: 212.7)
    assert tr.video_processing(Path("x.mp4")) == {"type": "static", "fps": 0.5}
    monkeypatch.setattr(tr, "video_duration_s", lambda p: 1800.0)
    assert tr.video_processing(Path("x.mp4")) == "agentic"
    monkeypatch.setattr(tr, "video_duration_s", lambda p: None)
    assert tr.video_processing(Path("x.mp4")) == "agentic"


def test_attachment_name_does_not_double_the_date(vault, image):
    today = manage._today()
    d = NoteDraft(title=f"{today} Saturday Session", folder="", frontmatter={}, body="x" * 30)
    assert manage.attachment_path(capture(source_path=str(image)), d, vault) == f"_attachments/{today} Saturday Session.png"
    d2 = d.model_copy(update={"title": "Saturday Session"})
    assert manage.attachment_path(capture(source_path=str(image)), d2, vault) == f"_attachments/{today} Saturday Session.png"


# --- folder descriptions (scripts/tasks/a-folder-fix.md) -----------------------------------
MOCK = Path(__file__).resolve().parent.parent / "mock_vault"


def test_folder_descriptions_on_mock_vault():
    from c2v.route import folder_descriptions, folder_options

    v = Vault(MOCK)
    d = folder_descriptions(v)
    phys = d["10 Learning and Teaching/11 Academic/PHYS 230 Electromagnetics"]
    assert phys.startswith("Course folder for PHYS 230 Electromagnetics") and "Smith chart" in phys
    academic = d["10 Learning and Teaching/11 Academic"]
    assert "PHYS 230 Electromagnetics" in academic and "choose that subfolder" in academic
    plant = d["30 Project and Hobby/31 Pet Projects/Plant Watering Bot"]
    assert plant.startswith("Project folder for Plant Watering Bot") and "ESP32" in plant
    assert d["40 Knowledge/Concepts"].startswith("One note per reusable concept")
    assert d["Sessions/2026-11"].startswith("Dated session logs")
    assert all(0 < len(x) <= 320 for x in d.values())
    # deterministic + cached per vault load, recomputed when the vault changes
    assert folder_descriptions(v) is d and folder_descriptions(Vault(MOCK)) == d
    # the router and Neon both get them
    cap = capture(summary="PHYS 230 memo on Smith charts", key_terms=["PHYS 230"])
    opts = folder_options(cap, v)
    assert opts["10 Learning and Teaching/11 Academic/PHYS 230 Electromagnetics"] == phys
    q = build_questions(cap, v)["folder"]["instructions"]
    assert "MOST SPECIFIC" in q
    prompt = manage.build_prompt(cap, routing(folder="10 Learning and Teaching/11 Academic"), v)
    assert "FOLDER GUIDE" in prompt and phys in prompt


def test_folder_descriptions_cache_invalidates(vault):
    from c2v.route import folder_descriptions

    before = folder_descriptions(vault)
    (vault.root / "New Area").mkdir()
    vault.reload()
    after = folder_descriptions(vault)
    assert "New Area" in after and "New Area" not in before


def test_empty_course_folder_still_described(tmp_path):
    """Eval held-out case: the course hub note is removed, so its folder is empty."""
    from c2v.route import folder_descriptions

    shutil.copytree(MOCK, tmp_path / "v")
    phys = tmp_path / "v/10 Learning and Teaching/11 Academic/PHYS 230 Electromagnetics"
    (phys / "PHYS 230 Electromagnetics.md").unlink()
    d = folder_descriptions(Vault(tmp_path / "v"))["10 Learning and Teaching/11 Academic/PHYS 230 Electromagnetics"]
    assert d.startswith("Folder for PHYS 230 Electromagnetics (no notes inside yet)")
    assert "2026-11-11 PHYS 230 - Smith chart practice set" in d
