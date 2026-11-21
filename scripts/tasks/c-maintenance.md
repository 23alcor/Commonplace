# Lane C task 2: vault maintenance with Neon long context (after get_context demo; due 3:50 PM, stretch)
"It doesn't just add context, it keeps context true." New module c2v/maintain.py + CLI
`python -m c2v.maintain --project "<hub note>" [--apply]`:
1. Gather the project's whole neighborhood (get_context with a large budget, e.g. 200k tokens).
2. One Neon call (structured output) returns findings: contradictions (note A says X, note B says Y, which
   is newer), superseded decisions, stale open loops (unchecked tasks done in a later note), duplicate notes.
   Each finding cites note titles + quotes.
3. --apply: Managed Agent (reuse agent_verify) edits the vault in the sandbox: add `> [!warning] Superseded by
   [[...]]` callouts, tick done tasks, merge duplicates; verify passes; then write back.
4. Seed mock_vault COPY (never mock_vault/ itself) with 3 planted inconsistencies for the demo, show
   before/after in docs/maintenance-demo.md, and add a "Maintain" button or event on /stage only if trivial.
Commit after each step.
