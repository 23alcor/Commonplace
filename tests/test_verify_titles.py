import shutil

import pytest

from c2v.manage import mechanical_fix
from c2v.schemas import NoteDraft
from c2v.vault import Vault
from c2v.verify import verify_draft, write_draft


@pytest.fixture
def vault(tmp_path):
    shutil.copytree("demo_vault", tmp_path / "vault")
    return Vault(tmp_path / "vault")


def _draft(title):
    return NoteDraft(title=title, folder="", frontmatter={"type": "idea", "created": "2026-11-21"},
                     body="a body that is long enough to pass", links=[], merge_into=None)


@pytest.mark.parametrize("title", ["../../escaped", "Projects/Sneaky", "", "  ", "a:b", "trailing."])
def test_unsafe_titles_rejected(vault, title):
    report = verify_draft(_draft(title), vault)
    assert not report.ok and "bad_title" in {i.code for i in report.issues}


def test_mechanical_fix_makes_title_safe(vault):
    fixed = mechanical_fix(_draft("../../escaped"), vault)
    assert verify_draft(fixed, vault).ok


def test_write_draft_refuses_outside_vault(vault):
    with pytest.raises(ValueError):
        write_draft(_draft("../../escaped"), vault)
