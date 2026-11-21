"""LANE C. get_context: the one tool any AI calls to get the right slice of the vault.

    get_context(vault, "Solar Microgrid Capstone", max_tokens=4000)

1. Seeds: notes whose title/alias is the query or appears in it; otherwise the top keyword hits.
2. Expand along the vault's structure: wikilinks, backlinks, and `project:` / `parent:` frontmatter
   (which leads to the course / project / hub note a note belongs to). Two hops max; the second hop
   only follows parent edges and forward links so busy hubs don't flood the result.
3. Rank by graph distance, then edge kind (seed, parent, link, backlink), then keyword relevance.
4. Pack whole notes until max_tokens (tokens ~ chars/4). A note that doesn't fit is dropped whole.
"""
from __future__ import annotations

import re

from .vault import WORD, Note, Vault, parse_links

PARENT_KEYS = ("project", "parent", "course", "up", "hub")
WHY_ORDER = {"seed": 0, "parent": 1, "link": 2, "backlink": 3}
MAX_SEEDS = 3
MAX_CANDIDATES = 60


def estimate_tokens(text: str) -> int:
    return (len(text) + 3) // 4


def _parents(note: Note) -> list[str]:
    out: list[str] = []
    for k in PARENT_KEYS:
        v = note.frontmatter.get(k)
        for item in (v if isinstance(v, list) else [v]):
            if isinstance(item, str):
                found = parse_links(item) or ([item.strip()] if item.strip() else [])
                out.extend(found)
    return out


def _backlinks(vault: Vault) -> dict[str, list[str]]:
    """title -> titles linking to it (body links + parent frontmatter). Cached per vault state."""
    key = (len(vault.notes), id(vault.notes))
    cached = getattr(vault, "_c2v_backlinks", None)
    if cached and cached[0] == key:
        return cached[1]
    back: dict[str, list[str]] = {}
    for n in vault.notes.values():
        for ref in set(n.links) | set(_parents(n)):
            t = vault.resolve(ref)
            if t and t != n.title:
                back.setdefault(t, []).append(n.title)
    vault._c2v_backlinks = (key, back)
    return back


def _relevance(note: Note, q: set[str]) -> int:
    if not q:
        return 0
    title = set(WORD.findall((note.title + " " + " ".join(note.aliases)).lower()))
    body = set(WORD.findall(note.body.lower()))
    return 3 * len(q & title) + len(q & body)


def _seeds(vault: Vault, query: str) -> list[str]:
    exact = vault.resolve(query.strip()) if query.strip() else None
    if exact:
        return [exact]
    ql = f" {query.lower()} "
    named = []
    for n in vault.notes.values():
        for name in [n.title, *n.aliases]:
            nl = name.lower()
            if len(nl) >= 3 and re.search(rf"(?<!\w){re.escape(nl)}(?!\w)", ql):
                named.append((len(nl), n.title))
                break
    if named:
        named.sort(key=lambda x: -x[0])
        return list(dict.fromkeys(t for _, t in named))[:MAX_SEEDS]
    hits = vault.search(query, k=MAX_SEEDS)
    return [h.title for h in hits]


def get_context(vault: Vault, query: str, max_tokens: int = 4000) -> dict:
    q = set(WORD.findall(query.lower()))
    back = _backlinks(vault)
    seeds = _seeds(vault, query)

    # title -> (distance, why)
    found: dict[str, tuple[int, str]] = {t: (0, "seed") for t in seeds}

    def neighbours(title: str, hop: int):
        n = vault.notes[title]
        for p in _parents(n):
            yield vault.resolve(p), "parent"
        if not (hop == 2 and found[title][1] == "parent"):  # a hub's other children are noise
            for link in n.links:
                yield vault.resolve(link), "link"
        if hop == 1:
            for b in back.get(title, []):
                yield b, "backlink"

    frontier = list(seeds)
    for hop in (1, 2):
        nxt = []
        for t in frontier:
            for nb, why in neighbours(t, hop):
                if nb and nb not in found:
                    found[nb] = (hop, why)
                    nxt.append(nb)
        frontier = nxt

    ranked = sorted(found.items(), key=lambda kv: (kv[1][0], WHY_ORDER[kv[1][1]],
                                                    -_relevance(vault.notes[kv[0]], q), kv[0]))
    ranked = ranked[:MAX_CANDIDATES]

    notes, used, truncated = [], 0, False
    for title, (dist, why) in ranked:
        n = vault.notes[title]
        text = (vault.root / n.path).read_text(encoding="utf-8", errors="replace")
        cost = estimate_tokens(text)
        if used + cost > max_tokens:
            truncated = True
            continue
        used += cost
        notes.append({"title": title, "path": n.path.as_posix(), "why": why, "distance": dist, "text": text})
    if len(found) > len(ranked):
        truncated = True
    return {"query": query, "notes": notes, "tokens": used, "truncated": truncated}
