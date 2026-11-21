# Agent benchmark: does an agent answer project questions better with `get_context`?

**Lane F, Nov 21 2026.** Code: `bench/agents/run_agents.py`, `bench/agents/report.py`. Raw per-answer rows:
`bench/agents/results.json`. Every API call is cached in `bench/agents/cache/`, so
`python -m bench.agents.run_agents --report` rebuilds every number here without calling the API.

## Setup
- **Vault:** a copy of `mock_vault/` (53 notes) plus 7 of lane D's demo captures filed **through the real
  pipeline** (`python -m c2v.pipeline <capture> --vault bench/agents/work/vault`): voice memo, whiteboard,
  screenshot, scanned PDF, merge follow-up. The pipeline created 1 new note (`Homelab Runbook`) and merged
  6 captures into existing notes, so some answers only exist in freshly captured text. The result is
  54 notes, **~3.5k tokens in total** (chars/4).
- **25 questions** with gold answers and gold note titles (`bench/agents/questions.json`): 10 single-note
  facts, 9 that need 2+ linked notes, and 6 about the freshly captured content (ADC calibration numbers,
  job-pipeline stage, runbook tmux name, and so on).
- **Arms.** Every arm uses the same model, the same system prompt ("answer the specific fact, or say I
  don't know"), and `thinking_level: low`. Only the context source changes:
  1. **no context:** the question alone.
  2. **CLAUDE.md file:** Neon summarized the whole vault once into a context file, which is then frozen
     (`bench/agents/context_file.md`, `context_file_1500.md`).
  3. **RAG:** `gemini-embedding-2` (768-d) over ≤300-token paragraph chunks, with the top chunks by cosine
     packed to the budget.
  4. **capture-to-vault:** native function calling with a `get_context(query, max_tokens)` tool backed by
     `c2v.context.get_context`. The model gets at most 3 calls, and everything it retrieves counts against
     the budget.
- **Budgets.** The spec'd ~4000 tokens is larger than the whole vault (3.5k), so at 4000 RAG simply gets
  every chunk. We also ran **1500 tokens** (about 40% of the vault), where the retriever has to choose.
- **Models:** `gemini-4-hydrogen` for every arm. `gemini-4-neon` repeats no-context and capture-to-vault.
- **Judge:** `gemini-4-neon` (thinking low) grades each question in one call. It sees all 9 answers,
  shuffled and unlabeled, plus the gold answer, the gold notes, and the full vault. Each answer gets
  correct / partial / wrong and a flag for "asserts a specific fact about the user that the vault does not
  support".

## Results

| model | arm | budget | correct | score (partial=0.5) | hallucination | context tokens (mean) | model input tokens (mean) | tool calls (mean) | latency p50 (s) | cost, 25 q (USD) |
|---|---|---|---|---|---|---|---|---|---|---|
| hydrogen | no context | - | 0% | 0% | 0% | 0 | 125 | 0 | 2.5 | 0.029 |
| hydrogen | CLAUDE.md file | 4000 | 88% | 90% | 0% | 1079 | 1431 | 0 | 3.5 | 0.084 |
| hydrogen | RAG (embeddings) | 4000 | 100% | 100% | 0% | 3538 | 5025 | 0 | 2.4 | 0.222 |
| hydrogen | **capture-to-vault get_context** | 4000 | **100%** | **100%** | 0% | **644** | 1702 | 1.0 | 4.4 | 0.101 |
| hydrogen | CLAUDE.md file | 1500 | 88% | 90% | 0% | 836 | 1183 | 0 | 2.9 | 0.075 |
| hydrogen | RAG (embeddings) | 1500 | 100% | 100% | 0% | 1492 | 2271 | 0 | 2.2 | 0.121 |
| hydrogen | **capture-to-vault get_context** | 1500 | **100%** | **100%** | 0% | **613** | 1671 | 1.0 | 5.3 | 0.104 |
| neon | no context | - | 0% | 0% | 0% | 0 | 125 | 0 | 4.3 | 0.054 |
| neon | **capture-to-vault get_context** | 4000 | **100%** | **100%** | 0% | 644 | 1711 | 1.0 | 7.8 | 0.212 |

Score by question kind (partial=0.5):

| model | arm | budget | single (n=10) | multi-note (n=9) | fresh captures (n=6) |
|---|---|---|---|---|---|
| hydrogen | no context | - | 0% | 0% | 0% |
| hydrogen | CLAUDE.md file | 4000 | 100% | **72%** | 100% |
| hydrogen | RAG | 4000 | 100% | 100% | 100% |
| hydrogen | capture-to-vault | 4000 | 100% | 100% | 100% |
| hydrogen | CLAUDE.md file | 1500 | 100% | **72%** | 100% |
| hydrogen | RAG | 1500 | 100% | 100% | 100% |
| hydrogen | capture-to-vault | 1500 | 100% | 100% | 100% |
| neon | no context | - | 0% | 0% | 0% |
| neon | capture-to-vault | 4000 | 100% | 100% | 100% |

Retrieval: both get_context and RAG surfaced every gold note (gold-note recall: get_context 100%,
RAG 99–100%). get_context did it with about 9.5 notes per question. RAG at 1500 tokens returned pieces
of 18 notes, and at 4000 it returned all 54.

![accuracy](agents/accuracy.png)

## Takeaway
With no context, the same agent answers **0 of 25** questions about the user's own projects; it says "I
don't know" every time, with both Hydrogen and Neon. With the `get_context` tool it answers **25 of 25**
with one tool call and about **640 context tokens**. That is 82% fewer than RAG at 4k (3538) and 57% fewer
than RAG at 1.5k (1492), and the result holds on Neon. The frozen CLAUDE.md file scores 90% and loses
exactly where the pitch says it would: on multi-note questions (72%). Its summary dropped the
session-level concept links ("which concept came up in both capstone sessions?") and one project.
**What the numbers do not show:** on this small vault, RAG ties get_context on accuracy. Here the
advantage is context size and cost, not correctness.

## Honest notes and failures
- **The benchmark saturates.** The vault is ~3.5k tokens, and both retrievers find every gold note. To
  separate RAG from get_context on accuracy you need a larger vault; lane E's scale benchmark
  (`bench/scale/`) covers 50/500/5000 notes.
- **Judge v1 was wrong about hallucinations, and we fixed it.** The first judge saw only the gold notes and
  flagged 16 answers as hallucinated: 6 from the CLAUDE.md arms and 10 from the get_context runs. We
  checked every flag by hand. All 16 were facts the vault supports, taken from *other* vault notes, such as the `Homelab Runbook`, the
  capstone's course code, or the Nov 18 daily note. The flag is meant to mean "not in the vault", so judge
  v2 also gets the full vault. Its flags dropped to 0. The v1 rows are kept in
  `bench/agents/results_judge_v1.json` and `tables_judge_v1.md`. Lesson: a judge that sees only the gold
  notes penalizes an agent for reading *more* of the vault.
- **Hand spot-check of 5 judge v2 verdicts** (random sample, seed 7, plus one partial): 5 of 5 agree with
  us. One is lenient: the CLAUDE.md arm answered "Embedded, ML and Systems roles" for s06, and the judge
  accepted "Systems" because the pipeline lists a Systems SWE job.
- **Question s09** ("what results did I log on Nov 18?") is ambiguous. The note contains only a title. In
  judge v1, RAG and CLAUDE.md answered "only the title is logged" and got *partial* because they didn't name
  the linked concepts. Judge v2 marks them correct. We kept the gold answer as written before the runs.
- **The CLAUDE.md file is shorter than its budget.** Neon was allowed ~3.4k tokens and wrote 1.1k, so the
  static file is lossier than it had to be. It is frozen as generated and not tuned.
- **get_context used far less than its budget.** The agent always made exactly one call, and it rarely asked
  for more than ~650 tokens. That is why the 1500 and 4000 rows are nearly identical. We never saw a
  second call that could have helped.
- **API calls: ~400** through the runner (answer turns including tool round trips, 2 context-file
  generations, embeddings, 50 judge calls, and retries), plus ~20 for pipeline filing. That is over the
  ~150-call guideline because we added the 1500-token budget and the Neon repeat. Spend was about
  **$2.4**: answers $1.00 and judges $1.38 (the v2 judge reads the full vault 25 times). That is under
  the $5 cap.

## Limitations
- The vault is synthetic and tiny (54 notes, ~3.5k tokens), and its structure is cleaner than a real vault.
- Questions and gold answers were written by us (an agent) after reading the vault, which favors lookups
  that can be phrased with note titles.
- Correctness comes from an LLM judge in the same model family as the agents, checked by hand on only 5
  verdicts.
- Only the Gemini 4 model family was tested, at thinking level low. n=25 per arm, single run, no confidence
  intervals.
