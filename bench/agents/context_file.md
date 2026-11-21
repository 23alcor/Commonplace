# CLAUDE.md

## Profile & Vault Conventions
- **User:** Senior Electrical Engineering student (Fall 2026), building hardware/software side projects and actively job hunting for embedded / ML / systems roles.
- **Last vault update:** `2026-11-21`.
- **Vault structure:**
  - `00 Home/` — `Home.md`, `01 About Me/`, `09 Journal/Daily Notes/`
  - `10 Learning and Teaching/11 Academic/` — `School.md` + Fall 2026 courses
  - `20 Work and Career/` — `Career.md`, `Job Search/Job Search.md`, `Job Search/Interview Prep.md`
  - `30 Project and Hobby/31 Pet Projects/` — `Projects.md` + active side projects
  - `40 Knowledge/Concepts/` — Atomic concept notes
  - `Sessions/2026-11/` — Dated session logs (`YYYY-MM-DD <Project/Course> - <Topic>.md`)

---

## Career & Job Search
- **Target roles:** Embedded ML, Firmware, On-device inference, Systems SWE.
- **Pipeline (as of `2026-11-21`):**
  - **ChipCo** — Embedded ML — **Screen** (scheduled for Thursday)
  - **GPU Labs** — On-device inference — **Technical**
  - **EdgeNet** — Firmware intern — **Applied**
  - **CloudForge** — Systems SWE — **Found**
- **Recent prep:**
  - `2026-11-15`: Weekly application review (informational interviews).
  - `2026-11-19` (updated `2026-11-21`): System design mock interview — **Rate Limiter** (token bucket vs. leaky bucket, Redis counters per API key, edge vs. central enforcement).
- **Open items:**
  - Prep for ChipCo screen (Thursday) / system design mock interview.
  - Tie rate limiter mock interview notes into `Interview Prep.md`.

---

## Fall 2026 Courses

### EECE 448 Machine Learning
*(Occasionally referenced as CS 448 in transcripts.)*
- **Key concepts:** Gradient descent, Regularization, Cross-validation, Bias-variance tradeoff.
- **Recent sessions:**
  - `2026-11-10` (updated `2026-11-21`): Ridge vs. Lasso on housing dataset — Ridge (L2) shrinks weights; Lasso (L1) drives some weights to zero.
  - `2026-11-17`: Bias-variance office hours.
- **Open items:** Tie Ridge and Lasso regularization back to gradient descent step size and class regularization notes.

### PHYS 230 Electromagnetics
- **Key concepts:** Maxwell's equations, Transmission lines, Smith chart.
- **Recent sessions:**
  - `2026-11-11`: Smith chart practice set. Key rules: toward generator → CW; toward load → CCW; match with series L then shunt C; check VSWR circle first. Example impedance: `z = 0.4 + j0.7`.
- **Open items:** Complete HW: practice set #3.

### ECON 205 Behavioral Economics
- **Key concepts:** Loss aversion (losses feel ~2x as bad as equal gains), Anchoring, Nudges.
- **Recent sessions:** `2026-11-13`: Anchoring lecture.

### EECE 410 Capstone Design — Solar Microgrid Capstone
- **Status:** Active team project.
- **Key concepts:** Fault detection, Relay baseline (conventional overcurrent relay logic used as comparison for ML detectors), Inverter control (grid-following inverters sync to grid voltage; fault behavior differs from generators).
- **Recent sessions:**
  - `2026-11-12`: Team meeting — agreed on relay baseline.
  - `2026-11-18`: Inverter fault simulation results.

---

## Active Side Projects

### Homelab Server
- **Hardware/Stack:** Headless Ubuntu box, Tailscale + MagicDNS, `tmux` (e.g., `tmux new -s agents` for long jobs surviving SSH drops), cron.
- **Decisions & milestones:**
  - `2026-11-14`: Moved cron jobs off laptop onto the homelab box (keep cron on the box, not laptop).
  - `2026-11-20`: Tailscale ACL cleanup (policy: only home devices).
- **Open items:** Document exit nodes; finish ACL cleanup after Nov 20 session; runbook setup checklist (`tailscale up`, `tmux new -s agents`, ACL: only home devices).

### Plant Watering Bot
- **Architecture:** `soil probe -> ESP32 ADC -> MQTT -> valve` (capacitive soil moisture sensor read via ESP32 ADC; publishes dry/wet status over MQTT; threshold triggers relay to open valve).
- **Calibration (`2026-11-12`, follow-up `2026-11-21`, ESP32 ADC):**
  - Air/dry: `820`
  - Damp: `540`
  - Saturated: `310`
  - **Draft watering threshold:** water below `480`.
- **Open items:** Finalize dry vs. saturated calibration; define next milestone.

### Recipe Scraper
- **Stack/Concepts:** Web scraping (respect `robots.txt`), SQLite.
- **Recent sessions:** `2026-11-16`: Deduplicated recipes by URL.
- **Open items:** Next milestone TBD.
