import json
import shutil
from pathlib import Path

from c2v.route import _fake_answer, needs_escalation
from c2v.schemas import Capture, MediaKind, NoteDraft, RoutingDecision
from c2v.vault import Vault
from c2v.verify import main as verify_main, verify_draft, write_draft
from eval.score import score_case, summarize

DEMO = Path(__file__).resolve().parent.parent / "demo_vault"


def good_draft(**kw):
    base = dict(
        title="Momentum Whiteboard",
        folder="10 Learning/EECE 448",
        frontmatter={"type": "class", "created": "2026-11-21"},
        body="Momentum keeps a running average of gradients so updates stop zig-zagging.",
        links=["Gradient Descent Notes", "eece448"],  # second one is an alias
    )
    base.update(kw)
    return NoteDraft(**base)


def test_vault_index():
    v = Vault(DEMO)
    assert "Gradient Descent Notes" in v.notes
    assert "10 Learning/EECE 448" in v.folders
    assert v.resolve("eece448") == "EECE 448 Machine Learning"
    assert v.resolve("gradient descent notes") == "Gradient Descent Notes"
    assert v.resolve("Nope") is None
    assert v.search("tailscale magicdns")[0].title == "Tailscale Setup"
    assert v.resolve("home-pc") == "Homelab Server"


def test_verify_ok_and_issues():
    v = Vault(DEMO)
    assert verify_draft(good_draft(), v).ok
    bad = good_draft(title="Gradient Descent Notes", folder="Nowhere", links=["Ghost"],
                     frontmatter={"type": "weird"}, body="hi")
    codes = {i.code for i in verify_draft(bad, v).issues}
    assert codes == {"missing_folder", "duplicate_title", "broken_link", "bad_frontmatter", "empty_body"}


def test_write_and_merge(tmp_path):
    root = tmp_path / "vault"
    shutil.copytree(DEMO, root)
    v = Vault(root)
    p = write_draft(good_draft(), v)
    assert p.exists() and "Momentum Whiteboard" in v.notes
    assert "[[Gradient Descent Notes]]" in p.read_text()
    m = write_draft(good_draft(merge_into="Tailscale Setup", links=[]), v)
    assert "## Update" in m.read_text()


def test_verify_cli(tmp_path):
    f = tmp_path / "draft.json"
    f.write_text(good_draft().model_dump_json())
    assert verify_main(["--vault", str(DEMO), "--draft", str(f)]) == 0
    f.write_text(good_draft(links=["Ghost"]).model_dump_json())
    assert verify_main(["--vault", str(DEMO), "--draft", str(f)]) == 1


def test_escalation_rules():
    cap = Capture(source_path="x.jpg", media_kind=MediaKind.image, transcript="t", summary="s")
    sure = RoutingDecision(note_type=_fake_answer("class", 0.95), folder=_fake_answer("10 Learning", 0.9))
    assert not needs_escalation(sure, cap)
    unsure = RoutingDecision(note_type=_fake_answer("class", 0.95), folder=_fake_answer("10 Learning", 0.5))
    assert needs_escalation(unsure, cap)
    blurry = cap.model_copy(update={"legibility": 0.4})
    assert needs_escalation(sure, blurry)


def test_score():
    s = score_case("c1", "A/B", ["X", "Y"], "a/b", ["x", "Z"], True)
    assert s.folder_correct and s.link_precision == 0.5 and s.link_recall == 0.5
    summary = summarize([s, score_case("c2", "A", [], "B", [], False)])
    assert summary["n"] == 2 and summary["folder_accuracy"] == 0.5
    json.dumps(summary)
