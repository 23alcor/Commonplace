# Demo captures

Synthetic, unprepared-looking inputs for the live demo and smoke tests against
**`mock_vault/`** (53 notes; default `VAULT_PATH`). No personal data.

Regenerate: `python3 demo_captures/generate.py` (Pillow, numpy, `espeak-ng`, `ffmpeg`).

Expected filing is the ground-truth intent for demos/evals. Paths are under `mock_vault/`.

| File | Kind | Expected folder | Should link / merge |
|---|---|---|---|
| `01_voice_eece448_ridge.wav` | Voice memo (TTS + noise) | `10 Learning and Teaching/11 Academic/EECE 448 Machine Learning/` or new `Sessions/2026-11/` study note | Link [[EECE 448 Machine Learning]], [[Regularization]], [[Gradient descent]] |
| `02_whiteboard_smith_chart.jpg` | Whiteboard photo | `10 Learning and Teaching/11 Academic/PHYS 230 Electromagnetics/` or `Sessions/` study | Link [[PHYS 230 Electromagnetics]], [[Smith chart]], optionally [[Transmission lines]] |
| `03_handwritten_anchoring.jpg` | Handwritten page | `10 Learning and Teaching/11 Academic/ECON 205 Behavioral Economics/` or `Sessions/` lecture | Link [[ECON 205 Behavioral Economics]], [[Anchoring]]; maybe [[Nudges]] / [[Loss aversion]] |
| `04_screenshot_job_search.jpg` | Phone screenshot | `20 Work and Career/Job Search/` | Link or update [[Job Search]]; optionally [[Interview Prep]] |
| `05_scanned_homelab_tmux.pdf` | Scanned 2-page PDF | `30 Project and Hobby/31 Pet Projects/Homelab/` | Link [[Homelab Server]], [[Tailscale]], [[tmux]], [[Cron jobs]] |
| `06_whiteboard_plant_bot_esp32.jpg` | Whiteboard photo | `30 Project and Hobby/31 Pet Projects/Plant Watering Bot/` | Link [[Plant Watering Bot]], [[ESP32]], [[Soil moisture sensing]], [[MQTT]] |
| `07_voice_homelab_tmux.wav` | Voice memo | `30 Project and Hobby/31 Pet Projects/Homelab/` or `Sessions/` | Link [[Homelab Server]], [[tmux]], [[Tailscale]] |
| `08_merge_soil_sensor_followup.jpg` | Handwritten **MERGE** | Same project as existing soil work | **Merge into** [[Plant Watering Bot]] and/or [[2026-11-12 Plant Watering Bot - Calibrated soil sensor]]; concepts [[ESP32]], [[Soil moisture sensing]] |
| `09_ambiguous_salary_anchor.jpg` | Handwritten **AMBIGUOUS** | Unclear on purpose | Router should show **low confidence** and escalate to Neon. Plausible homes: `20 Work and Career/Job Search/`, `ECON 205…/`, or even EECE 448 (bias-variance aside). Links may include [[Anchoring]], [[Job Search]], [[Interview Prep]], [[Bias-variance tradeoff]] |
| `10_screenshot_interview_prep.jpg` | Phone screenshot | `20 Work and Career/Job Search/` | Link [[Interview Prep]], [[System design interviews]], [[Job Search]] |

## Special cases (call out in the demo)

- **Merge:** `08_merge_soil_sensor_followup.jpg` — clear continuation of the Nov 12 calibration; Decision 1 should lean merge-yes.
- **Ambiguous / escalate:** `09_ambiguous_salary_anchor.jpg` — coffee-dump that straddles salary negotiation (Job Search), anchoring (ECON 205), and a bias-variance aside (EECE 448). Expect confidence below `ROUTE_CONFIDENCE_MIN` → Neon vault manager.

## Live-demo shortlist (~3 minutes)

Phone uploads; projector watches `/stage`.

1. `01_voice_eece448_ridge.wav` — clean high-confidence path (all four steps).
2. `08_merge_soil_sensor_followup.jpg` — merge into Plant Watering Bot.
3. `09_ambiguous_salary_anchor.jpg` — low-confidence escalate to Neon.

Backup modalities: `02_whiteboard_smith_chart.jpg`, `05_scanned_homelab_tmux.pdf`.
