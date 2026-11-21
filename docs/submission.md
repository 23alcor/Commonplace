# Submission pack — capture-to-vault

Hackathon: Gemini 4 NYC (Cerebral Valley + Google DeepMind), Sat Nov 21 2026.
Problem Statement 1: **5 Sigma**. Deadline: **5:00 PM ET**.

## Project description (paste into the form)

**capture-to-vault** turns messy personal captures — voice memos, whiteboard photos,
handwritten pages, screenshots, scanned PDFs — into correctly filed, wikilinked Obsidian
notes. Not a chat box: one upload, one note, self-checked.

Four Gemini pieces, each with one job:

- **Gemini 4 Hydrogen** transcribes media into a structured Capture.
- **Gemini Decision 1** (Decisions API) routes note type, folder, and merge-or-new with
  calibrated confidences; high confidence files automatically.
- **Gemini 4 Neon** manages the vault for low-confidence cases: title, frontmatter, body,
  links to existing notes.
- An **Antigravity Managed Agent** verifies the draft in a sandbox (`c2v.verify`) and fixes
  failures until checks pass — our “proof it works” loop and Managed Agents prize shot.

We evaluate against a single-model Hydrogen baseline on held-out, re-rendered vault notes
(noisy audio, blurred screenshots, scanned PDFs). Demo vault and `demo_captures/` are
synthetic and public-safe; no personal notes or secrets in the repo.

Repo: _add public GitHub URL before submit_
1-minute video: _add link before submit_

## 1-minute video shot list

Total runtime target: **55–65 seconds**. Vertical or 16:9; burn-in captions optional.
No face required — voiceover + screen is enough.

| Time | Shot | Audio / VO |
|---|---|---|
| 0:00–0:08 | Title card: **capture-to-vault** + “messy media → filed Obsidian note” over a still of `demo_vault/00 Home/Home.md` | “Messy captures in. A clean, linked note out.” |
| 0:08–0:18 | Capture page: drag `01_voice_gd_momentum.wav` | “Hydrogen transcribes.” |
| 0:18–0:28 | Cut to router panel / logs: Decision 1 choice + confidence | “Decision 1 routes with confidence.” |
| 0:28–0:38 | Neon draft preview: title, folder, `[[Gradient Descent Notes]]` | “Neon manages the vault — links that resolve.” |
| 0:38–0:48 | Managed Agent / verify loop: fail → fix → `verify` pass | “Managed Agent verifies and repairs until green.” |
| 0:48–0:55 | Split: Results table (baseline vs us) + honest-failure one-liner | “Beats a single-call baseline. We still miss sometimes — and we measure it.” |
| 0:55–1:00 | End card: repo URL + “Gemini 4 NYC / 5 Sigma” | Silence or soft stinger. |

**B-roll reserve (if a live call flakes while recording):** pre-filed note open in Obsidian,
`02_whiteboard_regularization.jpg` on the capture page, README Results table.

**Export:** 1080p, H.264, under 100 MB if the form caps size. Filename:
`capture-to-vault-1min.mp4` (do not commit the binary unless the form requires a repo path).

## Pre-submit checklist

Do these in order. Stop if any box fails.

### Repo hygiene (disqualifiers)

- [ ] Repository is **public** on GitHub.
- [ ] No `.env`, API keys, or credentials in any commit (`git log -p -- .env` is empty / file gitignored).
- [ ] No real personal vault in git history (only `demo_vault/` synthetic notes).
- [ ] `private_vault/`, `eval/work/`, `eval/cases/`, `eval/media/` are gitignored and untracked.
- [ ] `git status` clean on `main` after final merge (`scripts/merge.sh`: A → C → B).

### Product + proof

- [ ] End-to-end pipeline files at least one `demo_captures/` input into `demo_vault/`.
- [ ] Capture page (`app/`) uploads and shows the resulting note.
- [ ] Managed Agent verify-fix path demonstrated once (or local `c2v.verify` fallback documented).
- [ ] README **Results** table filled by Lane B (`eval/run_eval.py`) — folder accuracy, link F1,
      verify pass, median latency for baseline vs capture-to-vault.
- [ ] README “Where it still fails” is an honest sentence, not empty TBD.
- [ ] `docs/demo-script.md` rehearsed once out loud (names all four model jobs).

### Submission form assets

- [ ] Project description pasted (section above).
- [ ] Public repo URL confirmed.
- [ ] 1-minute video uploaded; link works in an incognito window.
- [ ] Team / lane credits accurate if the form asks.
- [ ] Submitted before **5:00 PM ET**.

### Final 10-minute gate

- [ ] Projector / share screen shows capture page + vault, not a terminal full of secrets.
- [ ] Fallback packet ready: one pre-filed note, Results table, `demo-script.md` fallback section.
- [ ] Someone other than the typer reads the README Results numbers aloud once.
