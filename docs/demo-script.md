# Live demo script (~3 minutes)

**Two screens, one pipeline**

| Device | URL | Audience sees |
|---|---|---|
| **Projector / laptop** | `http://<host>:8000/stage` | Live vault graph (`mock_vault`) + the four model steps lighting up as the pipeline runs |
| **Phone** | `http://<host>:8000/` (capture page) | Upload / camera / mic only — you never type a note |

**Before you start:** `/stage` fullscreen on the projector, capture page unlocked on the phone
(Tailscale URL if judges are remote), `demo_captures/` on the phone or airdropped, one dry-run
already filed today so the graph is warm. Results table (README) on a glance card if numbers exist.

Say the product once: *messy media in, a clean Obsidian note out — filed, linked, and self-checked.*

---

## 0:00–0:20 — Hook (projector)

**Audience sees on `/stage`:** the vault graph — clusters for Learning (EECE / PHYS / ECON), Job
Search, Plant Watering Bot, Homelab — before any new node appears.

> “Fifty-three notes in a synthetic vault shaped like a real one. Phone uploads junk; the projector
> shows the graph and which model is working. Four models, four jobs.”

Point at the empty step rail / idle state on `/stage`.

---

## 0:20–1:15 — Capture 1: high-confidence path

**Phone:** upload `demo_captures/01_voice_eece448_ridge.wav` (or hit Record and play it).

**Say each job as `/stage` advances — narrate what the room is looking at:**

| Step | You say | Audience sees on `/stage` |
|---|---|---|
| 1 | **Hydrogen = transcriber** | Step 1 active; transcript / key terms for the EECE 448 ridge-vs-lasso memo |
| 2 | **Decision 1 = router** | Step 2 active; folder toward EECE 448 / Sessions; confidences all high (≥ 0.75) |
| 3 | **Neon = vault manager** | Step 3 may be brief or skipped if auto-file; else title + wikilinks drafting |
| 4 | **Managed Agent = verifier** | Step 4 active; verify pass; new node appears on the graph linked to [[EECE 448 Machine Learning]] / [[Regularization]] / [[Gradient descent]] |

> “No chat box. Phone sent audio; the graph grew a note.”

Leave the new node highlighted.

---

## 1:15–1:55 — Capture 2: merge into an existing note

**Phone:** upload `demo_captures/08_merge_soil_sensor_followup.jpg`.

**Audience sees:**

1. Hydrogen pulls calibration numbers (dry 820 / wet 310) from the skewed page.
2. Decision 1: **merge-yes** toward [[Plant Watering Bot]] or the Nov 12 soil-sensor session —
   point at the confidence for merge.
3. Neon (if needed) attaches body + links [[ESP32]], [[Soil moisture sensing]].
4. Verifier green; **graph does not explode with a duplicate** — the existing Plant Watering Bot
   node gains a link / the session updates.

> “Same project, more data. Router chose merge instead of a second orphan note.”

---

## 1:55–2:25 — Capture 3: ambiguous → escalate to Neon

**Phone:** upload `demo_captures/09_ambiguous_salary_anchor.jpg`.

**Audience sees on `/stage`:**

1. Hydrogen transcript: salary anchoring + Job Search + EECE bias-variance aside.
2. Decision 1: **split probabilities** across Job Search / ECON 205 / maybe EECE — at least one
   confidence **below** `ROUTE_CONFIDENCE_MIN` (default 0.75). Call it out:
   > “Router is unsure. That is the feature — we escalate.”
3. **Neon = vault manager** step lights and stays longer: picks a home, writes frontmatter, chooses
   links ([[Anchoring]], [[Job Search]], …).
4. Managed Agent verifies; a node appears where Neon landed.

> “Decision 1 routes when confident; Neon manages when it is not.”

---

## 2:25–2:45 — Proof: baseline comparison

Keep `/stage` visible; glance or cut to README Results (Lane B).

> “Baseline is one Hydrogen call on the same held-out messy inputs. We win on folder accuracy and
> link F1; verify-pass is the Managed Agent loop you just watched.”

If the table is still empty, show one scored case artifact — do not invent numbers.

---

## 2:45–3:00 — Honest failure + close

Name one real miss (eval or a pre-run): wrong folder, bad merge, or a link the verifier had to fix.

> “Here is a failure we measured. We are not claiming five sigma — we are instrumenting toward it.”

Close on `/stage` with the three new/updated nodes visible:

> “Phone captures. Projector shows the vault graph and four jobs: Hydrogen, Decision 1, Neon,
> Managed Agent.”

Stop talking.

---

## Fallback if the network drops

Do **not** refresh both devices. Projector stays on `/stage` if it still has the last good graph;
otherwise switch to a frozen screenshot of `/stage` + a pre-filed note.

1. Phone: open a photo of `01_voice_eece448_ridge.wav` / play the WAV locally so judges hear messy input.
2. Walk the four jobs against a saved Capture → RoutingDecision → NoteDraft / `FilingResult`.
3. For the ambiguous story, hold up `09_ambiguous_salary_anchor.jpg` and show a pre-captured
   `/stage` frame where Decision 1 confidences were low and Neon was highlighted.
4. Results table / eval charts substitute for a live API call.
5. If only the Managed Agent sandbox is down: run `PYTHONPATH=. python -m c2v.verify` on a draft
   and say the agent wraps that loop remotely.

**Hard rule:** never open `.env` or paste an API key on the projector.
