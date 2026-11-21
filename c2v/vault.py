"""Read-only index of an Obsidian vault: folders, titles, aliases, wikilinks, keyword search."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)
IGNORED_DIRS = {".obsidian", ".git", ".trash", "node_modules"}
WORD = re.compile(r"[a-z0-9]+")


@dataclass
class Note:
    title: str
    path: Path  # vault-relative
    folder: str
    frontmatter: dict
    body: str
    links: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)


def split_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER.match(text)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {"__invalid__": True}
    if not isinstance(fm, dict):
        fm = {"__invalid__": True}
    return fm, text[m.end():]


def parse_links(text: str) -> list[str]:
    return [m.group(1).strip() for m in WIKILINK.finditer(text)]


class Vault:
    def __init__(self, root: Path | str):
        self.root = Path(root).expanduser().resolve()
        self.notes: dict[str, Note] = {}
        self.folders: set[str] = set()
        self._alias_to_title: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        self.notes.clear()
        self.folders.clear()
        self._alias_to_title.clear()
        for p in sorted(self.root.rglob("*")):
            rel = p.relative_to(self.root)
            if any(part in IGNORED_DIRS for part in rel.parts):
                continue
            if p.is_dir():
                self.folders.add(rel.as_posix())
            elif p.suffix == ".md":
                self._add(p, rel)
        self.folders.add("")  # vault root

    def _add(self, p: Path, rel: Path) -> None:
        text = p.read_text(encoding="utf-8", errors="replace")
        fm, body = split_frontmatter(text)
        aliases = fm.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]
        note = Note(
            title=p.stem,
            path=rel,
            folder=rel.parent.as_posix() if rel.parent.as_posix() != "." else "",
            frontmatter=fm,
            body=body,
            links=parse_links(body),
            aliases=[str(a) for a in aliases],
        )
        self.notes[note.title] = note
        for a in note.aliases:
            self._alias_to_title[a.lower()] = note.title

    # --- lookups -----------------------------------------------------------
    def resolve(self, link: str) -> str | None:
        """Return the note title a [[link]] points to, or None if it doesn't resolve."""
        target = link.split("/")[-1].strip()
        if target.endswith(".md"):
            target = target[:-3]
        if target in self.notes:
            return target
        lowered = {t.lower(): t for t in self.notes}
        return lowered.get(target.lower()) or self._alias_to_title.get(target.lower())

    def folder_list(self) -> list[str]:
        return sorted(f for f in self.folders if f)

    def search(self, query: str, k: int = 8) -> list[Note]:
        """Cheap keyword overlap search over title, aliases and body. Good enough for candidates."""
        q = set(WORD.findall(query.lower()))
        if not q:
            return []
        scored = []
        for n in self.notes.values():
            title_words = set(WORD.findall((n.title + " " + " ".join(n.aliases)).lower()))
            body_words = set(WORD.findall(n.body.lower()))
            score = 3 * len(q & title_words) + len(q & body_words)
            if score:
                scored.append((score, n.title, n))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [n for _, _, n in scored[:k]]

    def describe(self, max_notes: int = 400) -> str:
        """Compact text map of the vault for model context."""
        lines = ["FOLDERS:"] + [f"- {f}" for f in self.folder_list()] + ["NOTES:"]
        for n in list(self.notes.values())[:max_notes]:
            alias = f" (aliases: {', '.join(n.aliases)})" if n.aliases else ""
            lines.append(f"- [{n.folder or '/'}] {n.title}{alias}")
        return "\n".join(lines)
