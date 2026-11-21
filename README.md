# capture-to-vault

**Explain your project once. Every AI gets it.**

A **context manager for AI**. Developers already juggle several stacks at once — we built this
hackathon entry with Claude, Codex and Cursor in parallel and still had to hand-write
`AGENTS.md`, `CLAUDE.md` and per-agent prompts just to share context. Those files are lossy,
per-tool, stale, and always fully loaded.

capture-to-vault turns messy media (voice memos, whiteboard photos, handwriting, screenshots,
scanned PDFs) into a filed, linked, **verified** context vault. Any model then calls one
`get_context` MCP tool and gets the right slice — not the whole dump. Built at the Gemini 4 NYC
Hackathon (Nov 21, 2026) for **Problem Statement 1: 5 Sigma**.

The UI is a capture page plus the resulting note (and a `/stage` graph for the demo) — not a
chat box. We serve context to agents; we don't build another chatbot.

## How it works: four models, four jobs

![capture-to-vault flow](docs/architecture.svg)

Say it out loud in the demo: **Hydrogen = transcriber**, **Decision 1 = router**, **Neon = vault
manager**, **Managed Agent = verifier**. Then any AI reads the vault through **`get_context`**.

| Step | Model | Job |
|---|---|---|
| Transcribe | Gemini 4 Hydrogen | Media to a structured capture (transcript, key terms, legibility) |
| Route | Gemini Decision 1 (Decisions API) | Note type, folder, merge target, each with a calibrated confidence |
| Manage | Gemini 4 Neon | Low-confidence cases: picks links and merges, writes the final markdown |
| Verify | Antigravity Managed Agent | In a sandbox, runs `c2v.verify` on the draft and fixes it until every check passes |
| Retrieve | `get_context` MCP _(Lane C)_ | Pack linked notes for a query so Claude / Gemini / Codex / Cursor share one source of truth |

High router confidence (≥ `ROUTE_CONFIDENCE_MIN`, default 0.75) can file without Neon. Low confidence
escalates with the router's probabilities as context. The Managed Agent loop is the “proof it works”
story for the Best use of Managed Agents prize.

## Not just RAG

| | Typical RAG chat | capture-to-vault |
|---|---|---|
| What you store | Chunks / embeddings of whatever you pasted | Filed Obsidian notes with folders, frontmatter, wikilinks |
| How it gets there | You upload text or hope crawl quality holds | Four Gemini jobs: transcribe → route → manage → verify |
| Retrieval | Top-k similar chunks; mid-chunk cuts common | Structure-aware `get_context` (seed + links + backlinks + parent) _(Lane C, in progress)_ |
| Freshness | Re-embed when something changes | New capture files or merges; graph stays consistent |
| Multi-tool | Separate indexes / prompts per product | One vault; every agent calls the same MCP tool _(Lane C, in progress)_ |
| Proof at scale | “It feels better” | Bench: see [`bench/SCALE.md`](bench/SCALE.md) _(Lane E placeholder — fill when the scale run lands)_ |

## Demo inputs

`demo_captures/` holds ten synthetic, unprepared-looking inputs keyed to `mock_vault/` topics
(EECE 448, PHYS 230, ECON 205, Plant Watering Bot, Homelab, Job Search). See
[`demo_captures/README.md`](demo_captures/README.md) for which note each file should land in or link to.

Live walkthrough: [`docs/demo-script.md`](docs/demo-script.md) (~3 minutes). Submission blurb, 1-minute
video shot list, and pre-submit checklist: [`docs/submission.md`](docs/submission.md).

## Results
_Filled in by `eval/run_eval.py`. Held-out notes were removed from the vault, re-rendered as noisy
voice memos, blurred screenshots and scanned PDFs, and filed again. The baseline is one Gemini 4
Hydrogen call._

| | Folder accuracy | Link F1 | Verify pass | Median latency |
|---|---|---|---|---|
| Baseline (1 call) | | | | |
| capture-to-vault | | | | |

Where it still fails: _TBD_

## Run it
```bash
cp .env.example .env   # add GEMINI_API_KEY
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
PYTHONPATH=. python -m c2v.pipeline demo_captures/01_voice_eece448_ridge.wav --vault mock_vault
uvicorn app.server:app --host 0.0.0.0 --port 8000   # capture page + /stage
```

`mock_vault/` is a synthetic vault, so the repo contains no personal notes. Point `VAULT_PATH`
at a private copy only for local eval — never commit a real vault or `.env`.

## Give any AI your vault: `get_context` over MCP
One tool gives an agent the right whole notes for a project, conversation or topic. It starts from the
best match, follows wikilinks, backlinks and the `project:`/`parent:` note it belongs to, and packs
whole notes to a token budget. HTTP: `GET /context?q=Solar%20Microgrid%20Capstone&max_tokens=4000`.

```bash
# Claude Code (run from the repo root; use absolute paths)
claude mcp add capture-to-vault -e VAULT_PATH="$PWD/demo_vault" -e PYTHONPATH="$PWD" \
  -- "$PWD/.venv/bin/python" -m c2v.mcp_server

# Gemini CLI
gemini mcp add capture-to-vault -e VAULT_PATH="$PWD/demo_vault" -e PYTHONPATH="$PWD" \
  "$PWD/.venv/bin/python" -m c2v.mcp_server
```
Or in `~/.gemini/settings.json`:
```json
{"mcpServers": {"capture-to-vault": {"command": "/abs/repo/.venv/bin/python",
  "args": ["-m", "c2v.mcp_server"], "cwd": "/abs/repo", "env": {"VAULT_PATH": "/abs/repo/demo_vault"}}}}
```
Tools: `get_context(query, max_tokens)`, `search_notes(query)`, `read_note(title)`. The vault is
re-read on every call, so a capture filed a moment ago is already in context.

## Built during the hackathon
Everything in this repo was written on Nov 21, 2026. Lanes: A pipeline, B eval, C verify + capture
page + `get_context`, D demo inputs + pitch docs, E scale bench.
