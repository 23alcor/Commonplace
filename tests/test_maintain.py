import json

import pytest

from c2v import maintain as m
from c2v.vault import Vault


def test_seed_copy_plants_issues_and_guards_mock_vault(tmp_path):
    with pytest.raises(SystemExit):
        from c2v.config import REPO_ROOT
        m.seed_demo(REPO_ROOT / "mock_vault")
    dst = m.seed_demo(tmp_path / "v")
    v = Vault(dst)
    assert "Relay Baseline Notes" in v.notes and "2026-11-20 Capstone - Switched relay baseline" in v.notes
    assert m.check_vault(v)["ok"]
    ctx = m.gather(v, "Solar Microgrid Capstone")
    titles = [n["title"] for n in ctx["notes"]]
    assert "2026-11-20 Capstone - Switched relay baseline" in titles and "Relay baseline" in titles


def test_quotes_are_checked(tmp_path):
    v = Vault(m.seed_demo(tmp_path / "v"))
    ctx = m.gather(v, "Solar Microgrid Capstone")
    good = {"evidence": [{"title": "Relay baseline", "quote": "definite-time relay with a 50 ms delay"}]}
    bad = {"evidence": [{"title": "Relay baseline", "quote": "a 75 ms delay"}]}
    out = m.check_quotes([good, bad], ctx)
    assert out[0]["verified"] and not out[1]["verified"]


def test_check_cli_finds_broken_link(tmp_path):
    dst = m.seed_demo(tmp_path / "v")
    p = dst / "40 Knowledge/Concepts/Relay baseline.md"
    p.write_text(p.read_text() + "\nSee [[No Such Note]].\n")
    scope = tmp_path / "scope.json"
    scope.write_text(json.dumps(["40 Knowledge/Concepts/Relay baseline.md"]))
    assert m.main(["--check", "--vault", str(dst), "--scope", str(scope)]) == 1
    p.unlink()
    assert m.main(["--check", "--vault", str(dst), "--scope", str(scope)]) == 1  # missing note is an issue


def test_apply_refuses_repo_vaults():
    from c2v.config import REPO_ROOT
    with pytest.raises(SystemExit):
        m._guard(Vault(REPO_ROOT / "mock_vault"))
