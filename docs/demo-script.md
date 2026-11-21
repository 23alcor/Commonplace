# Live demo script (~3 minutes)

**Pitch in one line:** *Explain your project once. Every AI gets it.* capture-to-vault is a
**context manager** — messy media becomes a filed, linked, verified vault; any model calls one
`get_context` tool instead of each stack keeping its own stale prompt file.

**Two screens, one pipeline**

| Device | URL | Audience sees |
|---|---|---|
| **Projector / laptop** | `http://<host>:8000/stage` | Live vault graph (`mock_vault`) + the four model steps lighting up as the pipeline runs |
| **Phone** | `http://<host>:8000/` (capture page) | Upload / camera / mic only — you never type a note |

**Before you start:** `/stage` fullscreen on the projector, capture page on the phone, two agent
CLIs ready with the same `get_context` MCP (e.g. Claude Code + Gemini CLI), `demo_captures/` on the
phone, one dry-run filed so the graph is warm. If Lane C MCP is not merged yet, stage a
`GET /context?q=...` browser tab and a second agent with the same HTTP call as backup.

---

## 0:00–0:20 — Hook (projector)

**Audience sees on `/stage`:** the vault graph — Learning, Job Search, Plant Watering Bot, Homelab.

> “We built this with Claude, Codex and Cursor in parallel and still wrote AGENTS.md and per-tool
> prompts by hand. Those files are lossy, per-tool, and always fully loaded. This vault is the
> shared context. Phone captures; any AI reads it through one tool.”

Point at the idle four-step rail on `/stage`.

---

## 0:20–1:05 — Capture: four models, four jobs

**Phone:** upload `demo_captures/01_voice_eece448_ridge.wav` (or Record and play it).

| Step | You say | Audience sees on `/stage` |
|---|---|---|
| 1 | **Hydrogen = transcriber** | Step 1 active; transcript / key terms for the EECE 448 ridge-vs-lasso memo |
| 2 | **Decision 1 = router** | Step 2 active; folder toward EECE 448 / Sessions; high confidences |
| 3 | **Neon = vault manager** | Brief or skipped if auto-file; else title + wikilinks |
| 4 | **Managed Agent = verifier** | Verify pass; new node on the graph linked to [[EECE 448 Machine Learning]] / [[Regularization]] / [[Gradient descent]] |

> “Not a chat UI. We filed context into the vault.”

Optional 20s if time: flash `08_merge_soil_sensor_followup.jpg` (merge) or
`09_ambiguous_salary_anchor.jpg` (low confidence → Neon) — one sentence each, do not both.

---

## 1:05–2:10 — Payoff: two AIs, one `get_context`

This is the new close. Keep `/stage` showing the note you just filed.

**Same question to two different agents** (side-by-side on projector or cut between terminals):

> “What did I just capture about ridge versus lasso for EECE 448?”

1. **Agent A** (e.g. Claude Code) calls MCP `get_context` — audience sees the tool return the new
   note (+ linked course/concepts), then a correct answer grounded in that text.
2. **Agent B** (e.g. Gemini CLI or Cursor) calls the **same** `get_context` — same vault slice,
   coherent answer, no pasted `AGENTS.md` blob.

> “One capture. Two stacks. Same tool. Explain it once — every AI gets it.”

If MCP is still “(Lane C, in progress)”: hit `GET /context?q=ridge%20lasso%20EECE%20448` twice in
two browsers/agents and narrate that the MCP wrapper is the product surface.

---

## 2:10–2:40 — Proof: not just RAG + baseline

Glance at README **Not just RAG** and Results (Lane B) / [`bench/SCALE.md`](../bench/SCALE.md) when
Lane E lands.

> “RAG guesses similar chunks. We file, link, verify, then retrieve along the graph. Filing quality
> beats a single Hydrogen call on held-out messy inputs — [point at numbers, never invent them].”

---

## 2:40–3:00 — Honest failure + close

Name one real miss (wrong folder, bad merge, or a link verify had to fix).

> “We still fail sometimes. We measure it. Context managers earn trust with receipts.”

Close on `/stage` + the two agent answers still visible:

> “Four Gemini jobs write the vault. `get_context` is how every AI reads it.”

Stop talking.

---

## Fallback if the network drops

1. Keep `/stage` on the last good graph (or a screenshot).
2. Play `01_voice_eece448_ridge.wav` locally so judges hear messy input.
3. Walk Capture → RoutingDecision → NoteDraft from a saved artifact.
4. For the payoff: open a saved `get_context` / `/context` JSON for that note and read the two
   agent answers from `docs/get-context-demo.md` if present.
5. Results / SCALE chart substitute for live API calls.
6. Managed Agent down → local `python -m c2v.verify` on a draft.

**Hard rule:** never open `.env` or paste an API key on the projector.
