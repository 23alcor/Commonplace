from pathlib import Path

from c2v.context import estimate_tokens, get_context
from c2v.vault import Vault

MOCK = Path(__file__).resolve().parent.parent / "mock_vault"


def titles(r):
    return [n["title"] for n in r["notes"]]


def test_shape_and_seed_first():
    r = get_context(Vault(MOCK), "Solar Microgrid Capstone")
    assert set(r) == {"query", "notes", "tokens", "truncated"}
    assert r["notes"][0]["title"] == "Solar Microgrid Capstone" and r["notes"][0]["why"] == "seed"
    for n in r["notes"]:
        assert {"title", "path", "why", "text"} <= set(n)
        assert n["why"] in {"seed", "link", "backlink", "parent"}


def test_expands_links_backlinks_and_parent():
    r = get_context(Vault(MOCK), "Solar Microgrid Capstone", max_tokens=8000)
    why = {n["title"]: n["why"] for n in r["notes"]}
    assert why["Projects"] == "parent"
    assert why["Relay baseline"] == "link"
    assert why["EECE 410 Capstone Design"] == "backlink"
    assert "Recipe Scraper" not in why  # sibling under the hub is not pulled in


def test_title_inside_question_and_backlinked_session():
    r = get_context(Vault(MOCK), "what did I decide about the relay baseline?")
    assert titles(r)[0] == "Relay baseline"
    assert "2026-11-12 Capstone - Agreed on relay baseline" in titles(r)


def test_budget_packs_whole_notes():
    v = Vault(MOCK)
    full = get_context(v, "Solar Microgrid Capstone", max_tokens=100_000)
    small = get_context(v, "Solar Microgrid Capstone", max_tokens=300)
    assert small["tokens"] <= 300 and small["truncated"]
    assert len(small["notes"]) < len(full["notes"])
    for n in small["notes"]:
        on_disk = (v.root / n["path"]).read_text(encoding="utf-8")
        assert n["text"] == on_disk  # never cut mid-note
    assert small["tokens"] == sum(estimate_tokens(n["text"]) for n in small["notes"])


def test_keyword_fallback_and_no_match():
    v = Vault(MOCK)
    assert get_context(v, "soil moisture calibration")["notes"]
    empty = get_context(v, "quantum knitting")
    assert empty["notes"] == [] and empty["tokens"] == 0
