# Lane C task: get_context API + MCP server (due 2:50 PM)

New pitch: capture-to-vault is a **context manager**. It keeps a context vault filed, linked and verified so ANY AI (Claude, Gemini, Codex, Cursor) can call one `get_context` tool and get the right context for a project, conversation or topic. Read AGENTS.md for rules (no chat UI: we serve context to agents, we don't build a chatbot).

Build, in this order, committing after each:
1. `c2v/context.py` (new file, you own it):
   `get_context(vault: Vault, query: str, max_tokens: int = 4000) -> dict`
   - find the best starting note(s) for the query (title/alias match first, then vault.search)
   - expand along structure: the note's wikilinks, its backlinks, its `project:`/`parent:` frontmatter, and the hub/course/project note it belongs to; rank by graph distance then relevance
   - pack whole notes (never cut mid-note; drop lowest-ranked notes instead) until max_tokens (estimate tokens as chars/4)
   - return {"query", "notes": [{"title","path","why": "seed|link|backlink|parent", "text"}], "tokens", "truncated": bool}
   Lane E's scale benchmark imports exactly this signature, so keep it.
2. `GET /context?q=...&max_tokens=...` in app/server.py returning that dict.
3. `c2v/mcp_server.py`: a stdio MCP server (use the `mcp` Python package) with tools `get_context(query, max_tokens)`, `search_notes(query)`, `read_note(title)`. Add a README snippet showing how to register it in Claude Code (`claude mcp add`) and Gemini CLI.
4. Prove it: register the MCP server with a real agent CLI on this machine, file a capture through the pipeline, then ask the agent a question only that new note answers. Save the transcript to docs/get-context-demo.md.
5. Tests in tests/test_context.py on mock_vault.

Don't touch eval/, bench/, docs/ (except the demo transcript) or Lane A files.
