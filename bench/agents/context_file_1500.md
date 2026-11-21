# CLAUDE.md

## Profile & Context
- **Role:** Senior Electrical Engineering student (Fall 2026), building embedded/infra side projects, actively job hunting for embedded / ML roles.
- **Current snapshot:** ~2026-11-21.
- **Vault layout:** Daily notes in `00 Home/09 Journal/Daily Notes/`; session logs in `Sessions/2026-11/`; courses in `10 Learning and Teaching/11 Academic/`; career in `20 Work and Career/Job Search/`; projects in `30 Project and Hobby/31 Pet Projects/`; atomic concepts in `40 Knowledge/Concepts/`.

## Job Search & Interview Prep
Target roles: Embedded / ML / Systems.
- **Pipeline (as of 2026-11-21):**
  - **ChipCo** — Embedded ML (**Screen** — scheduled for Thursday)
  - **GPU Labs** — On-device inference (**Technical**)
  - **EdgeNet** — Firmware intern (**Applied**)
  - **CloudForge** — Systems SWE (**Found**)
- **Recent activity:**
  - `2026-11-15`: Weekly application review (focus: informational interviews).
  - `2026-11-19` (updated `11-21`): System design mock interview — **Rate Limiter** (token bucket vs. leaky bucket, Redis counters per API key, edge vs. central enforcement).
- **Open items:**
  - Prep for ChipCo screen (Thursday).
  - Tie rate limiter mock notes into `Interview Prep`.

## Active Projects
### Solar Microgrid Capstone (`EECE 410`)
- **Goal:** ML-based fault detection for grid-following inverters, benchmarked against a conventional overcurrent relay baseline.
- **Log:**
  - `2026-11-12`: Team agreed on relay baseline.
  - `2026-11-18`: Ran inverter fault simulation results.

### Plant Watering Bot
- **Architecture:** `capacitive soil probe -> ESP32 ADC -> MQTT (dry/wet status) -> relay -> valve`
- **Calibration (`2026-11-12` & `2026-11-21`, ESP32 ADC):**
  - Air/dry: `820`
  - Damp: `540`
  - Saturated: `310`
  - **Draft threshold:** Water below `480`.

### Homelab Server
- **Stack:** Headless Ubuntu, Tailscale + MagicDNS (ACL restricted to home devices), `tmux` (`tmux new -s agents`) for persistent jobs.
- **Decisions & Log:**
  - `2026-11-14`: Moved cron jobs off laptop onto homelab box (keep cron on box).
  - `2026-11-20`: Tailscale ACL cleanup.
- **Open items:** Finish ACL cleanup post-Nov 20 session; document Tailscale exit nodes; verify `tailscale up` / `tmux` setup checklist.

### Recipe Scraper
- **Stack:** Web scraping + SQLite.
- **Log:** `2026-11-16` — Implemented URL-based recipe deduplication.

## Fall 2026 Courses
- **EECE 410 Capstone Design:** Team project is *Solar Microgrid Capstone* (see above).
- **EECE 448 Machine Learning:**
  - *Topics:* Gradient descent, regularization, cross-validation, bias-variance tradeoff.
  - `2026-11-10` (updated `11-21`): Ridge (L2, shrinks weights) vs. Lasso (L1, drives weights to zero) on housing dataset.
  - `2026-11-17`: Bias-variance office hours.
  - *Open item:* Tie Ridge/Lasso regularization back to gradient descent step size and class regularization notes.
- **PHYS 230 Electromagnetics:**
  - *Topics:* Maxwell's equations, transmission lines, Smith chart.
  - `2026-11-11`: Smith chart practice (`z = 0.4 + j0.7`). Rules: toward generator -> CW; toward load -> CCW; check VSWR circle first; match with series L then shunt C.
  - *Open item:* Complete HW practice set #3.
- **ECON 205 Behavioral Economics:**
  - *Topics:* Loss aversion, anchoring, nudges.
  - `2026-11-13`: Anchoring lecture.
