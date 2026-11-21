"""Build a seeded held-out set and an eval vault without source-note leakage."""
from __future__ import annotations

import argparse
import json
import random
import shutil
from collections import defaultdict
from pathlib import Path

from c2v.config import VAULT_PATH
from c2v.vault import Vault
from eval.render_media import KINDS, render_image, render_voice

ROOT = Path(__file__).resolve().parent


def select_notes(vault: Vault, count: int, seed: int) -> list:
    rng = random.Random(seed)
    notes = list(vault.notes.values())
    rng.shuffle(notes)
    def rank(note):
        resolved = {vault.resolve(link) for link in note.links} - {None, note.title}
        return (len(note.body.split()) >= 60 and len(resolved) >= 2,
                len(resolved) >= 2, len(note.body.split()) >= 60)
    notes.sort(key=rank, reverse=True)
    by_folder = defaultdict(list)
    for note in notes:
        by_folder[note.folder].append(note)
    folders = sorted(by_folder)
    rng.shuffle(folders)
    selected = []
    selected_titles: set[str] = set()
    protected_targets: set[str] = set()
    while len(selected) < count:
        progressed = False
        for folder in folders:
            choices = by_folder[folder]
            for i, note in enumerate(choices):
                targets = {vault.resolve(link) for link in note.links} - {None, note.title}
                if note.title in protected_targets or targets & selected_titles:
                    continue
                selected.append(note)
                selected_titles.add(note.title)
                protected_targets.update(targets)
                choices.pop(i)
                progressed = True
                break
            if len(selected) >= count:
                break
        if not progressed:
            break
    return selected


def build(vault_path: Path = VAULT_PATH, count: int = 30, seed: int = 42,
          cases_dir: Path = ROOT / "cases", work_dir: Path = ROOT / "work",
          voice: bool = False) -> list[dict]:
    vault_path = vault_path.expanduser().resolve()
    if not vault_path.is_dir():
        raise FileNotFoundError(vault_path)
    if work_dir.resolve().is_relative_to(vault_path):
        raise ValueError("eval/work is inside VAULT_PATH; point --vault at a vault directory")
    vault = Vault(vault_path)
    selected = select_notes(vault, count, seed)
    if not selected:
        raise ValueError("no eligible notes in vault")
    copy_path = work_dir / "vault"
    if copy_path.exists():
        shutil.rmtree(copy_path)
    shutil.copytree(vault_path, copy_path,
                    ignore=shutil.ignore_patterns(".git", ".obsidian", ".trash", "node_modules"))
    cases_dir.mkdir(parents=True, exist_ok=True)
    media_dir = work_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    for index, note in enumerate(selected):
        case_id = f"h{index + 1:03d}"
        kind = "voice_memo" if voice and index % 4 == 3 else KINDS[index % len(KINDS)]
        extension = ".wav" if kind == "voice_memo" else ".pdf" if kind == "scanned_pdf" else ".png"
        media_path = media_dir / f"{case_id}{extension}"
        markdown = (vault_path / note.path).read_text(encoding="utf-8", errors="replace")
        knobs = (render_voice(markdown, media_path, seed + index) if kind == "voice_memo"
                 else render_image(markdown, media_path, kind, seed + index))
        (copy_path / note.path).unlink()
        links = sorted({title for link in note.links if (title := vault.resolve(link)) and title != note.title})
        cases.append({"case_id": case_id, "title": note.title, "folder": note.folder,
                      "links": links, "media_kind": kind, "media_path": str(media_path.resolve()),
                      "difficulty": knobs})
    with (cases_dir / "cases.jsonl").open("w", encoding="utf-8") as stream:
        for case in cases:
            stream.write(json.dumps(case, ensure_ascii=False) + "\n")
    return cases


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vault", type=Path, default=VAULT_PATH)
    ap.add_argument("--count", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--voice", action="store_true", help="use Gemini TTS for every fourth case")
    args = ap.parse_args()
    cases = build(args.vault, args.count, args.seed, voice=args.voice)
    print(f"Built {len(cases)} held-out cases in {ROOT / 'cases'}")


if __name__ == "__main__":
    main()
