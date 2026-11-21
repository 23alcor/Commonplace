# capture-to-vault

Messy media in, a clean, correctly filed and linked Obsidian note out. Built at the Gemini 4 NYC
Hackathon (Nov 21, 2026) for **Problem Statement 1: 5 Sigma**.

Throw it a voice memo, a whiteboard photo, a handwritten page, a screenshot or a scanned PDF. It
transcribes the capture, decides where the note belongs, links it to the right existing notes, checks
its own work and files it. The UI is a capture page plus the resulting note — not a dashboard, not a
chat box.

## How it works: four models, four jobs

![capture-to-vault flow](docs/architecture.svg)

Say it out loud in the demo: **Hydrogen = transcriber**, **Decision 1 = router**, **Neon = vault
manager**, **Managed Agent = verifier**.

| Step | Model | Job |
|---|---|---|
| Transcribe | Gemini 4 Hydrogen | Media to a structured capture (transcript, key terms, legibility) |
| Route | Gemini Decision 1 (Decisions API) | Note type, folder, merge target, each with a calibrated confidence |
| Manage | Gemini 4 Neon | Low-confidence cases: picks links and merges, writes the final markdown |
| Verify | Antigravity Managed Agent | In a sandbox, runs `c2v.verify` on the draft and fixes it until every check passes |

High router confidence (≥ `ROUTE_CONFIDENCE_MIN`, default 0.75) can file without Neon. Low confidence
escalates with the router's probabilities as context. The Managed Agent loop is the “proof it works”
story for the Best use of Managed Agents prize.

## Demo inputs

`demo_captures/` holds ten synthetic, unprepared-looking inputs keyed to `demo_vault/` topics
(EECE 448, job hunt, Batcave, homelab). See [`demo_captures/README.md`](demo_captures/README.md) for
which note each file should land in or link to.

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
PYTHONPATH=. python -m c2v.pipeline demo_captures/01_voice_gd_momentum.wav --vault demo_vault
uvicorn app.server:app --host 0.0.0.0 --port 8000   # capture page
```

`demo_vault/` is a small synthetic vault, so the repo contains no personal notes. Point `VAULT_PATH`
at a private copy only for local eval — never commit a real vault or `.env`.

## Built during the hackathon
Everything in this repo was written on Nov 21, 2026. Lanes: A pipeline, B eval, C verify + capture
page, D demo inputs + submission docs.
