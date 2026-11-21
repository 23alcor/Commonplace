"""LANE C. stdio MCP server: any agent (Claude Code, Gemini CLI, Codex, Cursor) gets vault context
through one tool.

    python -m c2v.mcp_server [--vault PATH]      (default: $VAULT_PATH, else demo_vault)

Tools: get_context(query, max_tokens), search_notes(query), read_note(title).
The vault is re-indexed on every call, so a capture filed a second ago is already visible.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

from .config import VAULT_PATH
from .context import get_context as _get_context
from .vault import Vault

INSTRUCTIONS = (
    "capture-to-vault serves the user's personal knowledge vault (Obsidian notes that are filed, linked "
    "and verified). Call get_context with a project, course, person or question before answering "
    "anything about the user's own work, notes, decisions or plans.")

mcp = _Server("capture-to-vault", instructions=INSTRUCTIONS)
_vault_root: Path = Path(os.environ.get("VAULT_PATH", VAULT_PATH))
_vault: Vault | None = None


def vault() -> Vault:
    global _vault
    if _vault is None:
        _vault = Vault(_vault_root)
    else:
        _vault.reload()
    return _vault


@mcp.tool()
def get_context(query: str, max_tokens: int = 4000) -> str:
    """Get the right context from the user's vault for a project, conversation or topic.

    Returns whole notes, starting from the best match and following its links, backlinks and
    parent project/course, packed to fit max_tokens. Each note is labelled with why it was included.
    """
    r = _get_context(vault(), query, max_tokens=max(200, min(int(max_tokens), 200_000)))
    if not r["notes"]:
        return f"No notes in the vault match {query!r}."
    parts = [f"# Vault context for: {query}\n({len(r['notes'])} notes, ~{r['tokens']} tokens"
             f"{', more available with a larger max_tokens' if r['truncated'] else ''})"]
    for n in r["notes"]:
        parts.append(f"\n---\n## {n['title']}  [{n['why']}]  ({n['path']})\n\n{n['text'].strip()}")
    return "\n".join(parts)


@mcp.tool()
def search_notes(query: str) -> str:
    """Keyword search over note titles, aliases and bodies. Returns matching titles and paths."""
    hits = vault().search(query, k=10)
    if not hits:
        return f"No notes match {query!r}."
    return "\n".join(f"- {n.title}  ({n.path.as_posix()})" for n in hits)


@mcp.tool()
def read_note(title: str) -> str:
    """Read one note in full by its title or alias (as in an Obsidian [[wikilink]])."""
    v = vault()
    t = v.resolve(title)
    if t is None:
        return f"No note titled {title!r}. Try search_notes."
    n = v.notes[t]
    return f"# {t}  ({n.path.as_posix()})\n\n" + (v.root / n.path).read_text(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> None:
    global _vault_root
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=None)
    a = ap.parse_args(argv)
    if a.vault:
        _vault_root = Path(a.vault).expanduser()
    print(f"capture-to-vault MCP serving {_vault_root.resolve()}", file=sys.stderr)
    mcp.run("stdio")


if __name__ == "__main__":
    main()
