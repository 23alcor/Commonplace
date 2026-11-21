# Lane A task: keep the full source in every filed note (due 2:45 PM)

Pitch claim: unlike a hand-written CLAUDE.md, the vault keeps the details. Make it true:
every note the pipeline writes must keep (a) the full Hydrogen transcript under a `## Source` heading
(collapsed callout is fine: `> [!quote]- Transcript`), and (b) frontmatter `source:` pointing at the
original capture file, copied into the vault under `_attachments/` (embedded with `![[...]]` for images/PDF).
Neon's summary stays on top. Check verify.py still passes; add a test. Commit.
