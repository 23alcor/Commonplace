# capture-to-vault — shared spec for every coding agent

Hackathon: Gemini 4 NYC (Cerebral Valley + Google DeepMind), Sat Nov 21 2026.
**Hard deadline: submissions due 5:00 PM ET.** Work in small, working increments and commit often.

## What we're building (Problem Statement 1: "5 Sigma")
Messy media in, then a clean, correctly filed and linked Obsidian note out, **reliably**, with an
eval that proves it beats a single-model baseline on inputs we did not prepare.

Input captures: voice memos (m4a/mp3/wav), whiteboard/handwritten photos (jpg/png/heic),
screenshots, PDFs (scanned or digital), short videos.

Pipeline (one capture):
1. **Transcribe** with `gemini-4-hydrogen` → `Capture` (structured output, see `c2v/schemas.py`).
2. **Route** with `gemini-decision-1` (Decisions API) → `RoutingDecision`: note type, destination
   folder (choice from the vault's real folders + `other`), merge-into-existing yes/no, and a
   confidence for each. If every confidence is ≥ `ROUTE_CONFIDENCE_MIN` (default 0.75), file it
   automatically. Otherwise escalate to step 3 with the router's probabilities as context.
3. **Manage** with `gemini-4-neon` → `NoteDraft`: final title, folder, frontmatter, body, and
   wikilinks to existing notes (candidates come from `c2v/vault.py` search), plus a merge target if any.
4. **Verify**: `c2v/verify.py` checks the draft against the vault (links resolve, frontmatter valid,
   no duplicate titles, folder exists). The **Managed Agent** (`c2v/agent_verify.py`, Antigravity in a
   Google-hosted sandbox holding a copy of the vault) writes the note, runs `python -m c2v.verify`,
   and fixes failures until it passes. That self-check is the "Proof it works" story and targets
   the $5K Best use of Managed Agents prize.
5. **Write** the note into the vault and return a `FilingResult`.

Every model has ONE clear job (a judging rule). Say it out loud in the demo:
Hydrogen = transcriber, Decision 1 = router, Neon = vault manager, Managed Agent = verifier.

## Judging weights (optimize for these)
- Live demo on real, unrehearsed inputs: 35%
- Proof it works (baseline comparison, honest failures, self-check): 25%
- Creativity / beyond a text box: 20%
- Gemini 4 + Decisions API use: 20%

## Rules that can disqualify us
- Repo must be public. **Never commit a real personal vault, .env, or API keys.** `demo_vault/` is
  synthetic and public-safe. Point `VAULT_PATH` at a private vault copy for local eval only.
- New work only: do not copy code from other personal projects (Bat Vault, Grimoire, Batcave).
- Banned: Streamlit, basic RAG chat, "dashboard is the main feature", image analyzers.
  Our UI is a capture page plus the resulting note. Eval charts are evidence, not the product.

## Gemini SDK notes (from the official hackathon builder guide; verify against live docs)
Install: `pip install -U "google-genai>=3.2.0"`. Add the docs MCP + skills to your agent:
`npx add-mcp "https://gemini-api-docs-mcp.dev"` and
`npx skills add google-gemini/gemini-skills --skill gemini-api-dev`.

```python
from google import genai
client = genai.Client()                                              # Interactions API
beta_client = genai.Client(http_options={"api_version": "v1beta"})  # Decisions + Managed Agents

r = client.interactions.create(model="gemini-4-hydrogen", input=[...],
        generation_config={"thinking_level": "low"})     # low|medium|high|xhigh
r.output_text
# chain: client.interactions.create(model="gemini-4-neon", previous_interaction_id=r.id, input="...")

d = beta_client.decisions.create(model="gemini-decision-1", input=[...media + text...],
        questions={"route": {"type": "choice", "instructions": "...",
                             "criteria": {"key": "description", ..., "other": "..."}},
                   "sev": {"type": "score", "instructions": "...", "criteria": ["lo", "mid", "hi"]}})
d.answers["route"].choice, d.answers["route"].confidence
# yes/no question type string was garbled in the guide PDF; check the Decisions API docs.

run = beta_client.interactions.create(agent="antigravity-preview-09-2026", environment="remote",
        agent_config={"type": "antigravity", "model": "gemini-4-neon", "max_total_tokens": 100000},
        input="...")
run.environment_id   # reuse with previous_interaction_id=run.id, environment=run.environment_id
```
Don't pass temperature/top_p/top_k/thinking_budget to Gemini 4 models. Don't use `minimal` thinking
on Neon/Hydrogen. Use native structured output / Decisions questions, not hand-parsed JSON.

## Lanes (one agent per lane, one git worktree per lane)
| Lane | Agent | Branch | Owns |
|---|---|---|---|
| A: pipeline | Claude Code | `lane-a` | `c2v/transcribe.py`, `c2v/route.py`, `c2v/manage.py`, `c2v/pipeline.py` |
| B: eval | Codex | `lane-b` | `eval/*` |
| C: verify + demo | Claude Code | `lane-c` | `c2v/agent_verify.py`, `app/*` |
| D: demo inputs + submission | Cursor | `lane-d` | `demo_captures/*`, `docs/*`, README prose |

Shared, already implemented (change only if broken, and say so in the commit):
`c2v/schemas.py`, `c2v/config.py`, `c2v/vault.py`, `c2v/verify.py`, `eval/score.py`.
**The schemas are the contract between lanes. Don't rename fields.** Add optional fields if you must.

Integration: lanes merge into `main` with `scripts/merge.sh`. Order: A, then C, then B.
Run `pytest -q` before every merge.

## Timeline (ET)
- 12:45: Lane A: one capture goes end to end to a markdown file. Lane B: held-out set builder works.
  Lane C: FastAPI capture page uploads a file.
- 1:45: Decision router + Neon manager live. Baseline runner done.
- 2:45: Managed Agent verify-fix loop live. Full eval runs.
- 3:45: Failure analysis, one fix, re-run eval. Freeze features.
- 4:30: Demo rehearsal, README with results table, 1-min video.
- 5:00: Repo public, submitted.
