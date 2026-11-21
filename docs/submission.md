# Submission pack — capture-to-vault

Hackathon: Gemini 4 NYC (Cerebral Valley + Google DeepMind), Sat Nov 21 2026.
Problem Statement 1: **5 Sigma**. Deadline: **5:00 PM ET**.

**Tagline:** Explain your project once. Every AI gets it.

## Project description (paste into the form)

**capture-to-vault** is a **context manager for AI**. Developers use several AI stacks at once
(we built this with Claude, Codex and Cursor in parallel) and still hand-write `AGENTS.md`,
`CLAUDE.md` and per-agent prompts — lossy, per-tool, stale, and always fully loaded.

We turn messy media — voice memos, whiteboard photos, handwritten pages, screenshots, scanned
PDFs — into a filed, wikilinked, **verified** Obsidian context vault. Any model then calls one
`get_context` MCP tool for the right slice of that vault. Not a chatbot: we capture context in,
and serve context out to agents.

Four Gemini pieces write the vault; each has one job:

- **Gemini 4 Hydrogen** transcribes media into a structured Capture.
- **Gemini Decision 1** (Decisions API) routes note type, folder, and merge-or-new with
  calibrated confidences; high confidence files automatically.
- **Gemini 4 Neon** manages the vault for low-confidence cases: title, frontmatter, body,
  links to existing notes.
- An **Antigravity Managed Agent** verifies the draft in a sandbox (`c2v.verify`) and fixes
  failures until checks pass — our “proof it works” loop and Managed Agents prize shot.

Retrieval is structure-aware `get_context` (seed note + links + backlinks + parent), not
another RAG chat box. We eval filing against a single-model Hydrogen baseline on held-out
messy re-captures, and scale retrieval vs RAG in `bench/SCALE.md` as vault size grows.
`mock_vault/` and `demo_captures/` are synthetic and public-safe; no personal notes or secrets
in the repo.

Repo: _add public GitHub URL before submit_
1-minute video: _add link before submit_

## 1-minute video shot list

Total runtime target: **55–65 seconds**. Vertical or 16:9; burn-in captions optional.
No face required — voiceover + screen is enough.

| Time | Shot | Audio / VO |
|---|---|---|
| 0:00–0:08 | Title: **capture-to-vault** + tagline over `/stage` vault graph | “Explain your project once. Every AI gets it.” |
| 0:08–0:18 | Phone capture: `01_voice_eece448_ridge.wav`; `/stage` **① Transcribe** | “Hydrogen turns messy media into structured context.” |
| 0:18–0:28 | **② Route** confidence bars; folder lands in EECE 448 | “Decision 1 routes with calibrated confidence.” |
| 0:28–0:38 | **③ Manage** / **④ Verify** → new graph node + wikilinks | “Neon manages; a Managed Agent verifies until green.” |
| 0:38–0:50 | Split terminals: Claude + Gemini both call `get_context` on the new note; same answer | “Two AIs. One tool. Same vault.” |
| 0:50–0:55 | Not just RAG / Results or SCALE chart flash | “Filed and linked beats paste-and-pray RAG.” |
| 0:55–1:00 | End card: repo URL + “Gemini 4 NYC / 5 Sigma” | Silence or soft stinger. |

**B-roll reserve:** pre-filed note on `/stage`, `09_ambiguous_salary_anchor.jpg` escalate-to-Neon,
saved `docs/get-context-demo.md` transcript if live MCP flakes.

**Export:** 1080p, H.264, under 100 MB if the form caps size. Filename:
`capture-to-vault-1min.mp4` (do not commit the binary unless the form requires a repo path).

## Pre-submit checklist

Do these in order. Stop if any box fails.

### Repo hygiene (disqualifiers)

- [ ] Repository is **public** on GitHub.
- [ ] No `.env`, API keys, or credentials in any commit (`git log -p -- .env` is empty / file gitignored).
- [ ] No real personal vault in git history (only `mock_vault/` / synthetic notes).
- [ ] `private_vault/`, `eval/work/`, `eval/cases/`, `eval/media/` are gitignored and untracked.
- [ ] `git status` clean on `main` after final merge (`scripts/merge.sh`).

### Product + proof

- [ ] End-to-end pipeline files at least one `demo_captures/` input into `mock_vault/`.
- [ ] Capture page + `/stage` show the resulting note on the graph.
- [ ] Managed Agent verify-fix path demonstrated once (or local `c2v.verify` fallback documented).
- [ ] `get_context` MCP (or `GET /context`) answers a question only the new note can answer —
      transcript in `docs/get-context-demo.md` when Lane C lands.
- [ ] README **Results** table filled by Lane B; **Not just RAG** rows still mark Lane C in progress
      until MCP merges; `bench/SCALE.md` filled or explicitly placeholder.
- [ ] README “Where it still fails” is an honest sentence, not empty TBD.
- [ ] `docs/demo-script.md` rehearsed once (four model jobs + two-AI `get_context` payoff).

### Submission form assets

- [ ] Project description pasted (section above) — includes tagline and context-manager angle.
- [ ] Public repo URL confirmed.
- [ ] 1-minute video uploaded; link works in an incognito window.
- [ ] Team / lane credits accurate if the form asks.
- [ ] Submitted before **5:00 PM ET**.

### Final 10-minute gate

- [ ] Projector shows `/stage` + agent terminals, not a terminal full of secrets.
- [ ] Fallback packet ready: pre-filed note, `get_context` JSON / demo transcript, Results table.
- [ ] Someone other than the typer reads the README Results numbers aloud once.
