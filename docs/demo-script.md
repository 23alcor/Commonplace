# Live demo script (~3 minutes)

**Pitch in one line:** *Explain your project once. Every AI gets it.* capture-to-vault is a
**context manager** — messy media becomes a filed, linked, verified vault; any model calls one
`get_context` tool instead of each stack keeping its own stale prompt file.

**No audience involvement.** Time is short — you run the phone; judges only watch.

**Two screens, one pipeline**

| Device | URL | Audience sees |
|---|---|---|
| **Projector / laptop** | `http://<host>:8000/stage` | Live vault graph (`mock_vault`) + the four model steps |
| **Phone** | `http://<host>:8000/` (capture page) | Camera / upload — you never type a note |

**Before you start:** `/stage` fullscreen on the projector (graph warm, [[Capture to Vault]] node
visible under Projects). Capture page open on the phone. One agent CLI ready with `get_context`
MCP (or `GET /context` backup). Pre-taken fallback photo of `/stage` already on the phone
(see Fallbacks). Results glance card optional.

---

## 0:00–0:20 — Hook (projector)

**Audience sees on `/stage`:** vault graph — Learning, Job Search, Plant Watering Bot, Homelab,
and the **Capture to Vault** project node.

> “We built this with Claude, Codex and Cursor in parallel and still wrote AGENTS.md by hand —
> lossy, per-tool, always fully loaded. This vault is the shared context. Watch one unprepared
> capture file itself, then an AI read it back.”

Point at idle four-step rail. Do **not** pass the phone to the room.

---

## 0:20–1:40 — Live unprepared moment: photo of the app

This is the unrehearsed beat (no planted `demo_captures/` file).

1. **Projector stays on `/stage`.** You hold the phone; point the camera at the projected app
   (graph + step rail visible on screen).
2. **Photo tip:** shoot at a **slight angle** (not dead-on perpendicular) so the projector pixels
   don't moiré / rainbow against the phone sensor. Avoid standing in the beam (glare / your
   shadow on the wall).
3. **Phone:** Capture / upload that photo immediately.
4. **Narrate the four jobs as `/stage` advances:**

| Step | You say | Audience sees on `/stage` |
|---|---|---|
| 1 | **Hydrogen = transcriber** | Reads the screen photo (UI chrome, “capture-to-vault”, graph labels) |
| 2 | **Decision 1 = router** | Lands under `30 Project and Hobby/…/Capture to Vault/` (or merge into [[Capture to Vault]]) |
| 3 | **Neon = vault manager** | Title / links if confidence dipped; else brief |
| 4 | **Managed Agent = verifier** | Verify pass; new or updated node on the **Capture to Vault** project |

> “Unprepared input: a photo of the running app. It filed itself into the Capture to Vault project.”

Leave that node highlighted.

### Fallback if the live photo is glare-heavy / unreadable

Do **not** retry more than once. Upload the **pre-taken photo of the app** already on the phone
(shot earlier today at a slight angle under the same projector, or a clean laptop screenshot of
`/stage` transferred to the phone). Say one line:

> “Projector glare — using a photo we took of the same screen a minute ago. Still unprepared
> media, still the live pipeline.”

Then continue from Decision 1 / the filing result as usual.

---

## 1:40–2:30 — Close: AI explains the project via `get_context`

Keep `/stage` on the filed Capture to Vault note. On the projector (second window or cut), run
**one** agent — not two, time is short:

```text
get_context("capture to vault")
```

Ask it to explain the project from that context.

**Audience sees:** tool return packing [[Capture to Vault]] (+ linked notes), then a spoken/ typed
summary grounded in the vault — including the note that just filed from the screen photo.

> “One tool. The vault just learned from a photo of itself. Explain your project once — every AI
> gets it.”

If MCP is flaky: `GET /context?q=capture%20to%20vault` in the browser and read the packed notes
aloud while the agent (or you) summarizes.

---

## 2:30–3:00 — Proof beat (optional if time) + honest failure

One sentence on Results / Not just RAG / `bench/SCALE.md` if numbers are up:

> “Filed and linked beats paste-and-pray RAG — [point at real numbers only].”

Name one measured miss if you still have ten seconds, then stop on `/stage` + the `get_context`
answer. No Q&A phone pass.

---

## Fallbacks (network / pipeline)

1. Keep `/stage` on the last good graph (or a screenshot).
2. Live photo bad → pre-taken app photo (above). Pipeline down → walk a saved Capture →
   RoutingDecision → NoteDraft that targeted [[Capture to Vault]].
3. `get_context` down → open saved JSON / `docs/get-context-demo.md` for query
   `capture to vault`.
4. Managed Agent down → local `python -m c2v.verify` on a draft.

**Hard rule:** never open `.env` or paste an API key on the projector. Never hand the phone to
the audience.
