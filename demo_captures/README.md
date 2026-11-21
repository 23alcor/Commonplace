# Demo captures

Synthetic, unprepared-looking inputs for live demo and held-out-style smoke tests.
No personal data. Regenerated with `python3 demo_captures/generate.py` (needs Pillow,
numpy, `espeak-ng`, `ffmpeg`).

Each file is keyed to topics already in `demo_vault/`. Expected filing is a judgment
call for the router/manager — this table is the ground-truth intent for demos and evals.

| File | Kind | Should file into / link |
|---|---|---|
| `01_voice_gd_momentum.wav` | Voice memo (TTS + pink noise) | New or merge under `10 Learning/EECE 448/`. Link [[Gradient Descent Notes]]; optionally [[EECE 448 Machine Learning]]. |
| `02_whiteboard_regularization.jpg` | Whiteboard photo (skew + blur) | `10 Learning/EECE 448/` → merge or sibling of [[Regularization Notes]]; link [[EECE 448 Machine Learning]]. |
| `03_handwritten_interview_prep.jpg` | Handwritten page | `20 Work and Career/Job Hunting/` → [[Interview Prep Plan]] (merge) or new weekly prep note linking it + [[Job Search Pipeline]]. |
| `04_screenshot_job_pipeline.jpg` | Phone screenshot | `20 Work and Career/Job Hunting/` → update/merge [[Job Search Pipeline]]; link [[Target Companies]]. |
| `05_scanned_homelab.pdf` | Scanned 2-page PDF | `30 Projects/Homelab/` → [[Homelab Server]] and/or [[Tailscale Setup]] (prefer linking both). |
| `06_whiteboard_batcave_cache.jpg` | Whiteboard photo | `30 Projects/Batcave/` → merge into [[Batcave Database Limits]]; link [[Batcave Dashboard]]. |
| `07_voice_weekly_review.wav` | Voice memo | `00 Home/` → [[Weekly Review]] (merge) or new Sunday journal in `Sessions/` linking [[Job Search Pipeline]] + [[Batcave Dashboard]]. |
| `08_screenshot_tailscale.jpg` | Phone screenshot | `30 Projects/Homelab/` → [[Tailscale Setup]] (merge); link [[Homelab Server]]. |
| `09_handwritten_study_session.jpg` | Handwritten page | `Sessions/` new study journal; link [[Gradient Descent Notes]] and [[EECE 448 Machine Learning]]. |
| `10_screenshot_batcave_error.jpg` | Phone screenshot | `30 Projects/Batcave/` → [[Batcave Database Limits]] (merge); link [[Batcave Dashboard]]. |

## Live-demo shortlist (3 minutes)

Use these three first — they cover audio, camera, and screen modalities:

1. `01_voice_gd_momentum.wav`
2. `02_whiteboard_regularization.jpg`
3. `04_screenshot_job_pipeline.jpg`

Keep `05_scanned_homelab.pdf` ready as a fourth if time allows, or as the honest-failure backup
(scan OCR / multi-page routing can wobble).
