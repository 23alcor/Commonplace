# Lane E task: scale benchmark, managed vault vs RAG (due 3:40 PM)

Claim to test, honestly: as a context vault grows, RAG-style retrieval has to guess from similarity, while structured retrieval over a managed vault (filed, linked, verified) stays accurate. Report whatever the numbers say.

1. `bench/scale/make_vaults.py`: extend scripts/make_mock_vault.py's style procedurally (no API calls) to vaults of 50, 500 and 5000 notes: more courses/projects/sessions/concepts plus realistic noise (near-duplicate names, overlapping terms across projects, stale sessions). Output to bench/scale/vaults/ (gitignore the big ones; commit the generator).
2. `bench/scale/questions.py`: ~30 questions per size with known gold note sets, derived from structure (e.g. "what did I decide about the relay baseline" -> that session + its project note; "everything about Smith charts" -> concept + course + sessions that link it). Include ~1/3 vague keyword-style questions where similarity search should do well, so the test is fair.
3. Three systems on identical questions and a ~4000-token budget:
   - RAG: chunk (~500 tokens), embed with the Gemini embeddings model (check the docs for the id), top-k by cosine until the budget
   - keyword: vault.search top-k
   - get_context: `from c2v.context import get_context` (Lane C is building it now, merged ~2:50; build 1-2 and the RAG/keyword runners first, plug it in when it lands)
4. Metrics per system x vault size: recall of gold notes, precision of returned notes, tokens returned, latency. Cache embeddings in bench/cache/ (5000 notes must be embedded once only), back off on rate limits, keep cost under ~$5.
5. bench/SCALE.md: a table plus one chart (precision and recall vs vault size, one line per system), a 3-sentence takeaway, and a limitations paragraph (synthetic vault; structure comes from our pipeline). Commit after each step.
