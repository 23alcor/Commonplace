# Lane D task: new pitch wording (due 3:15 PM)

New angle: capture-to-vault is a **context manager for AI**. Developers now use several AI stacks at once
(we built this with Claude, Codex and Cursor in parallel and had to write AGENTS.md, CLAUDE.md and per-agent
prompts just to share context). Hand-written context files are lossy, per-tool, stale and always fully loaded.
Capture-to-vault turns messy media into a filed, linked, verified context vault, and any model calls one
`get_context` MCP tool to get the right context. Tagline: "Explain your project once. Every AI gets it."

Update README intro + "How it works", docs/demo-script.md and docs/submission.md to this angle. Keep the four
model jobs. Add a "Not just RAG" table (RAG vs capture-to-vault) to the README: mark get_context rows
"(Lane C, in progress)" until it merges, and leave a placeholder for bench/SCALE.md results.
Demo payoff to script: after a capture is filed, two different AIs answer the same question from it via get_context.
Commit after each file.
