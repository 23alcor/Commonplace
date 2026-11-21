# get_context demo: a capture filed one minute ago answers an agent's question

**Claim:** after capture-to-vault files a new capture, any agent that has the `capture-to-vault` MCP server
gets that note through one `get_context` call, with the project around it, and answers from it.

Recorded 2026-11-21 on the dev machine. Every output below is copied from the real run; nothing was edited
except trimming long lines where marked.

## 1. Setup

Vault: a scratch copy of `mock_vault/` (53 synthetic notes). The MCP server was registered with Claude Code:

```bash
claude mcp add -s local capture-to-vault -e VAULT_PATH=<scratch>/ctx_vault -e PYTHONPATH="$PWD" \
  -- "$PWD/.venv/bin/python" -m c2v.mcp_server
claude mcp list   # capture-to-vault: ... - ✔ Connected
```

**Control:** before the capture, `get_context` for the same query returns 10 notes
(Solar Microgrid Capstone, Projects, 2026-11-18 Capstone - Inverter fault sim results, 2026-11-12 Capstone - Agreed on relay baseline, ...). None of them mentions Prof. Okafor, 10 kHz, Dec 3 or Maya, so the facts
asked about below are not in the vault until the capture is filed.

## 2. File a capture through the pipeline

The input is a whiteboard photo (generated for this test) with these lines:

```
CAPSTONE sync w/ Prof. Okafor  11/21
- relay baseline vs ML detector:  final comparison due DEC 3
- resample inverter fault sims to 10 kHz  (5 kHz aliased the arc faults)
- Maya owns the dataset, I own the eval
TODO: email Okafor the confusion matrix
```

```bash
python -m c2v.pipeline capstone_whiteboard.jpg --vault <scratch>/ctx_vault --agent-verify
```

| | |
|---|---|
| Router (Decision 1) | type `meeting` (0.63), folder `10 Learning and Teaching/11 Academic/EECE 410 Capstone Design` (0.92) |
| Path taken | `escalated` (sent to Neon) |
| Verify | ok=True, issues=0 (the Managed Agent was not needed) |
| Latency | 25.2 s |
| Written | `Sessions/2026-11/2026-11-21 Capstone - Sync with Prof. Okafor.md` |

The filed note:

```markdown
---
type: meeting
created: '2026-11-21'
source: image
tags:
- capstone
- meeting
- eece-410
---

# Capstone Sync with Prof. Okafor

## Summary
Synced with Prof. Okafor on 2026-11-21 regarding the relay baseline vs. ML detector evaluation for the Solar Microgrid Capstone.

## Key Points
- **Relay baseline vs. ML detector**: Final comparison is due December 3.
- **Inverter fault simulations**: Resample to 10 kHz (5 kHz aliased the arc faults).
- **Ownership**: Maya owns the dataset; I own the evaluation.

## Action Items
- [ ] Complete final comparison of relay baseline vs. ML detector by Dec 3
- [ ] Resample inverter fault simulations to 10 kHz
- [ ] Email Prof. Okafor the confusion matrix

## Related
- [[Solar Microgrid Capstone]]
- [[Relay baseline]]
- [[Fault detection]]
- [[Inverter control]]
- [[2026-11-12 Capstone - Agreed on relay baseline]]
- [[2026-11-18 Capstone - Inverter fault sim results]]
```

## 3. Ask an agent

Claude Code (`claude -p`, model `claude-sonnet-5-5`). The agent was given only the three capture-to-vault MCP tools;
Bash, Read, Grep, Glob, Edit, Write, WebFetch and WebSearch were disallowed, so it could not read files directly.

**Question:** For my solar microgrid capstone: when is the relay vs ML detector comparison due, what sampling rate should the inverter fault sims use and why, and who owns the dataset? Use my vault.

**Tool calls the agent made:**
- `ToolSearch` `{"query": "select:mcp__capture-to-vault__get_context,mcp__capture-to-vault__search_notes,mcp__capture-to-vault__read_note", "max_results": 5}`
- `mcp__capture-to-vault__get_context` `{"query": "solar microgrid capstone relay vs ML detector comparison inverter fault simulation sampling rate dataset owner", "max_tokens": 6000}`

(`ToolSearch` only loads the deferred MCP tool schemas. The single `get_context` call was the real retrieval.)

**What `get_context` returned:** 11 whole notes, ranked by graph distance from the seed:

| # | Note | Why included |
|---|---|---|
| 1 | Solar Microgrid Capstone | seed |
| 2 | Projects | parent |
| 3 | 2026-11-18 Capstone - Inverter fault sim results | link |
| 4 | 2026-11-12 Capstone - Agreed on relay baseline | link |
| 5 | Relay baseline | link |
| 6 | Fault detection | link |
| 7 | Inverter control | link |
| 8 | 2026-11-21 Capstone - Sync with Prof. Okafor | backlink |
| 9 | EECE 410 Capstone Design | backlink |
| 10 | 2026-11-18 | backlink |
| 11 | School | parent |

The new note came in as a **backlink** from the project note "Solar Microgrid Capstone", because the vault
manager linked it to that project when it was filed.

<details><summary>Full get_context output (4335 chars)</summary>

```markdown
# Vault context for: solar microgrid capstone relay vs ML detector comparison inverter fault simulation sampling rate dataset owner
(11 notes, ~767 tokens)

---
## Solar Microgrid Capstone  [seed]  (10 Learning and Teaching/11 Academic/EECE 410 Capstone Design/Solar Microgrid Capstone.md)

---
type: project
status: active
parent: "[[Projects]]"
tags: [project]
---
# Solar Microgrid Capstone

Concepts: [[Fault detection]] · [[Relay baseline]] · [[Inverter control]]

## Open loops
- [ ] Next milestone TBD

## Log
- 2026-11-12 [[2026-11-12 Capstone - Agreed on relay baseline|Agreed on relay baseline]] (meeting)
- 2026-11-18 [[2026-11-18 Capstone - Inverter fault sim results|Inverter fault sim results]] (coding)

---
## Projects  [parent]  (30 Project and Hobby/Projects.md)

---
type: hub
tags: [projects]
---
# Projects
- [[Homelab Server]]
- [[Plant Watering Bot]]
- [[Recipe Scraper]]
- [[Solar Microgrid Capstone]]

---
## 2026-11-18 Capstone - Inverter fault sim results  [link]  (Sessions/2026-11/2026-11-18 Capstone - Inverter fault sim results.md)

---
type: session
category: coding
project: "[[Solar Microgrid Capstone]]"
date: "2026-11-18"
tags: [session, coding]
---
# Inverter fault sim results

## Summary
Inverter fault sim results. Worked on [[Solar Microgrid Capstone]].

Concepts: [[Inverter control]] · [[Fault detection]]

## Next steps
- [ ] Follow up next session

---
## 2026-11-12 Capstone - Agreed on relay baseline  [link]  (Sessions/2026-11/2026-11-12 Capstone - Agreed on relay baseline.md)

---
type: session
category: meeting
project: "[[Solar Microgrid Capstone]]"
date: "2026-11-12"
tags: [session, meeting]
---
# Agreed on relay baseline

## Summary
Agreed on relay baseline. Worked on [[Solar Microgrid Capstone]].

Concepts: [[Relay baseline]] · [[Fault detection]]

## Next steps
- [ ] Follow up next session

---
## Relay baseline  [link]  (40 Knowledge/Concepts/Relay baseline.md)

---
type: concept
tags: [concept]
---
# Relay baseline
Conventional overcurrent relay logic used as the comparison for ML detectors.

---
## Fault detection  [link]  (40 Knowledge/Concepts/Fault detection.md)

---
type: concept
tags: [concept]
---
# Fault detection
Classify abnormal current/voltage events fast enough to trip protection.

---
## Inverter control  [link]  (40 Knowledge/Concepts/Inverter control.md)

---
type: concept
tags: [concept]
---
# Inverter control
Grid-following inverters sync to grid voltage; behavior during faults differs from generators.

---
## 2026-11-21 Capstone - Sync with Prof. Okafor  [backlink]  (Sessions/2026-11/2026-11-21 Capstone - Sync with Prof. Okafor.md)

---
type: meeting
created: '2026-11-21'
source: image
tags:
- capstone
- meeting
- eece-410
---

# Capstone Sync with Prof. Okafor

## Summary
Synced with Prof. Okafor on 2026-11-21 regarding the relay baseline vs. ML detector evaluation for the Solar Microgrid Capstone.

## Key Points
- **Relay baseline vs. ML detector**: Final comparison is due December 3.
- **Inverter fault simulations**: Resample to 10 kHz (5 kHz aliased the arc faults).
- **Ownership**: Maya owns the dataset; I own the evaluation.

## Action Items
- [ ] Complete final comparison of relay baseline vs. ML detector by Dec 3
- [ ] Resample inverter fault simulations to 10 kHz
- [ ] Email Prof. Okafor the confusion matrix

## Related
- [[Solar Microgrid Capstone]]
- [[Relay baseline]]
- [[Fault detection]]
- [[Inverter control]]
- [[2026-11-12 Capstone - Agreed on relay baseline]]
- [[2026-11-18 Capstone - Inverter fault sim results]]

---
## EECE 410 Capstone Design  [backlink]  (10 Learning and Teaching/11 Academic/EECE 410 Capstone Design/EECE 410 Capstone Design.md)

---
type: course
code: EECE 410
term: Fall 2026
parent: "[[School]]"
tags: [course]
---
# EECE 410 Capstone Design
Team project: [[Solar Microgrid Capstone]].

## Log

---
## 2026-11-18  [backlink]  (00 Home/09 Journal/Daily Notes/2026-11-18.md)

---
type: daily
date: "2026-11-18"
tags: [daily]
---
# Wednesday, November 18, 2026
## Summary
- Inverter fault sim results ([[Solar Microgrid Capstone]])

---
## School  [parent]  (10 Learning and Teaching/11 Academic/School.md)

---
type: hub
tags: [school]
---
# School
- [[EECE 448 Machine Learning]]
- [[PHYS 230 Electromagnetics]]
- [[ECON 205 Behavioral Economics]]
- [[EECE 410 Capstone Design]]
```
</details>

**Agent's answer (verbatim):**

> From your 2026-11-21 sync note with Prof. Okafor:
>
> - **Due date:** The relay baseline vs. ML detector comparison is due **December 3**.
> - **Sampling rate:** Resample the inverter fault sims to **10 kHz**. The note gives the reason: 5 kHz aliased the arc faults. Arc faults have fast, high-frequency content, so a 5 kHz rate puts it above Nyquist and folds it into lower frequencies. The note doesn't give a Nyquist calculation, so that part is my explanation.
> - **Dataset owner:** **Maya** owns the dataset. You own the evaluation.
>
> The same note lists two open action items: resample the sims to 10 kHz, and email Prof. Okafor the confusion matrix.
>
> The project note still says "Next milestone TBD". You may want to update it with the Dec 3 date.

Run stats: 3 turns, 5.8 s, $0.116.

## 4. What this shows

- The answer comes only from the note filed about a minute earlier (Dec 3, 10 kHz plus the aliasing reason,
  Maya), and the agent cites that note.
- The agent marks which part is its own reasoning (the Nyquist explanation) and which part is in the note.
- The agent also noticed that the project note is stale ("Next milestone TBD"). That is real follow-up work for
  the vault manager. (In an earlier identical run it also pointed out that the project note doesn't link back to
  the new note yet.)
- The same server works in any MCP client (Gemini CLI, Codex, Cursor); see the README for how to register it.
