# Live demo script (~3 minutes)

**Setup before you start:** capture page open (`uvicorn app.server:app`), Obsidian or a
markdown preview on `demo_vault/`, `demo_captures/` folder visible, eval results table on
screen two (or a printed card). Network check: one dry-run capture already filed today.

Say the product in one breath: *messy media in, a clean Obsidian note out — filed, linked,
and self-checked.*

---

## 0:00–0:20 — Hook

Show the vault Home note. Point at the folders: Learning, Job Hunting, Batcave, Homelab.

> “Judges hate rehearsed demos. These captures are synthetic but messy on purpose — voice
> noise, skewed whiteboard, phone JPEG mush. We did not hand-tune prompts on these three.”

## 0:20–1:10 — Capture 1: voice memo (Hydrogen → Decision 1 → Neon → Managed Agent)

Upload `demo_captures/01_voice_gd_momentum.wav`.

**Say each model’s one job out loud as the pipeline steps:**

1. **Hydrogen = transcriber** — media becomes a structured Capture (transcript, key terms).
2. **Decision 1 = router** — note type, folder, merge yes/no, each with a confidence. If every
   confidence ≥ 0.75, we can file without drama; otherwise we escalate.
3. **Neon = vault manager** — title, frontmatter, body, wikilinks into real vault notes.
4. **Managed Agent = verifier** — Antigravity sandbox writes the draft, runs `python -m c2v.verify`,
   and fixes until links resolve, folder exists, no duplicate titles.

Open the filed note. Expect links to [[Gradient Descent Notes]] / EECE 448.

## 1:10–1:50 — Capture 2: whiteboard photo

Upload `demo_captures/02_whiteboard_regularization.jpg`.

> “Same four jobs, different modality. Router should land in Learning / EECE 448 and attach to
> Regularization Notes.”

Show the note in the vault. One sentence on Decisions API: *calibrated route confidences, not
hand-parsed JSON.*

## 1:50–2:20 — Proof: baseline comparison

Flip to the Results table in the README (Lane B numbers).

> “Baseline is a single Gemini 4 Hydrogen call. Same held-out messy inputs. We win on folder
> accuracy and link F1; verify-pass is the Managed Agent story.”

If numbers are still TBD, show the eval command and one scored case JSON instead — do not invent
digits.

## 2:20–2:45 — Honest failure

Pick one real miss from eval or from a pre-run of `05_scanned_homelab.pdf` / a low-confidence
route:

> “Here is where we still fail: [wrong folder | broken wikilink | merge when it should be new].
> The verifier caught / did not catch it. That is the honest failure — we are not claiming five
> sigma yet, we are measuring toward it.”

## 2:45–3:00 — Close + optional third capture

If time: drop `04_screenshot_job_pipeline.jpg` and stop at the routed folder.

> “Four models, four jobs. Capture page in, vault note out, self-check in a Managed Agent.”

Stop talking. Leave the note on screen.

---

## Fallback if the network drops

Do **not** refresh frantically. Switch to the pre-baked path:

1. Open a note already filed earlier today under `demo_vault/` (or a screenshot of the filed
   note + verify log).
2. Walk the same four jobs against the frozen Capture → RoutingDecision → NoteDraft artifacts
   in `eval/results/` or a local `FilingResult` printout.
3. Play 20 seconds of `01_voice_gd_momentum.wav` so judges still hear a messy input.
4. Show the Results table / charts as the “proof it works” substitute for a live API call.
5. If only the Managed Agent sandbox is down: run `PYTHONPATH=. python -m c2v.verify` locally
   on a draft path and narrate that the agent wraps this loop remotely.

**Hard rule:** never paste an API key or open `.env` on the projector.
