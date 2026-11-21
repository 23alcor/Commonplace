# Lane F task: agent benchmark, with vs without capture-to-vault (due 3:45 PM)

Question: does an AI agent answer project questions better when it can call our `get_context` tool than when it can't?
Report whatever the numbers say. Your files: bench/agents/ only (+ bench/AGENTS_RESULTS.md).

## Setup
- Vault: a copy of mock_vault/ in bench/agents/work/ plus 5-8 notes filed THROUGH THE PIPELINE from demo_captures/
  (python -m c2v.pipeline <file> --vault <copy>), so some answers only exist in freshly captured notes.
- 25 questions with gold answers (short facts: a decision, a date, a number, which project, which concept links
  where). Write them by reading the notes; mix: ~10 single-note facts, ~10 that need 2+ linked notes, ~5 about
  the freshly captured notes. Store as bench/agents/questions.json with the gold note titles too.

## Arms (same model, same question, same token budget ~4000 context tokens)
1. no-context: model answers from the question alone (the "re-explain it every time" baseline)
2. context-file: a hand-written-style CLAUDE.md: the vault summarized into one ~4000-token file
   (generate it once with a model, then freeze it; it is the lossy static file in our pitch)
3. RAG: top-k chunks by Gemini embeddings, packed to the budget (reuse Lane E's runner if merged, else your own)
4. capture-to-vault: the agent gets a `get_context(query, max_tokens)` function tool (from c2v.context) and
   decides what to ask for (function calling, max 3 tool calls)

Agent model: gemini-4-hydrogen (cheap) for all arms; if budget allows, repeat arm 1 and 4 with gemini-4-neon to
show it holds across models. Use native function calling, thinking_level low.

## Scoring
- correctness: LLM judge (gemini-4-neon, low) gets question + gold answer + agent answer -> correct / partial /
  wrong, plus a "hallucinated a fact not in the vault" flag. Spot-check 5 judgments by hand and note it.
- context tokens consumed, tool calls, latency.

## Output
bench/AGENTS_RESULTS.md: table (arm x accuracy x hallucination rate x tokens x latency), one bar chart
(bench/agents/accuracy.png), 3-sentence takeaway, limitations (synthetic vault, LLM judge, one model family).
Cache every call; cap ~150 API calls / ~$5; back off on rate limits. Commit after each step.
