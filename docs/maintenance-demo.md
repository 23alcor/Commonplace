# Vault maintenance demo: it doesn't just add context, it keeps context true

`python -m c2v.maintain --project "Solar Microgrid Capstone" --vault <copy> [--apply]`

Recorded 2026-11-21. All numbers, findings and diffs below are copied from the real run. The vault is a
**copy** of `mock_vault/` made by `python -m c2v.maintain --seed-demo <dst>`, which plants 3 inconsistencies
(`mock_vault/` itself is never edited, and `--apply` refuses to run on it).

## Planted inconsistencies
1. **Superseded decision / contradiction.** `2026-11-12 Capstone - Agreed on relay baseline` picks a
   definite-time relay (50 ms). `2026-11-20 Capstone - Switched relay baseline` replaces it with an
   inverse-time relay. The concept note `Relay baseline` still says definite-time.
2. **Stale open loop.** The project note still lists "Run the inverter fault sims" as open, but
   `2026-11-18 ... Inverter fault sim results` says all 240 runs are done.
3. **Duplicate.** `Relay Baseline Notes` duplicates `Relay baseline`, and the 11-20 note links to it.

## Step 1: gather (get_context)
12 notes, from the project note out along links, backlinks and parents. They went to Neon in one call.

## Step 2: find (gemini-4-neon, one structured-output call)
41.9 s, 6318 tokens. Every quote is checked word for word against the cited note before
anything acts on it ("Quotes verified").

| # | Kind | Finding | Stale note | Current note | Quotes verified |
|---|---|---|---|---|---|
| 1 | stale_task | The project note still lists running the inverter fault sims as an open task even though they were completed on 2026-11-18. | Solar Microgrid Capstone | 2026-11-18 Capstone - Inverter fault sim results | yes |
| 2 | stale_task | The project note still lists picking the relay baseline as an open task even though a baseline was chosen on 2026-11-12 and finalized as an inverse-time relay on 2026-11-20. | Solar Microgrid Capstone | 2026-11-20 Capstone - Switched relay baseline | yes |
| 3 | superseded | The 2026-11-12 decision to use a definite-time overcurrent relay baseline was replaced on 2026-11-20 by an inverse-time overcurrent relay, but the older meeting note does not indicate it was superseded. | 2026-11-12 Capstone - Agreed on relay baseline | 2026-11-20 Capstone - Switched relay baseline | yes |
| 4 | contradiction | The Relay baseline concept note states the capstone uses a definite-time relay with a 50 ms delay, contradicting the 2026-11-20 meeting note that switched the baseline to an inverse-time overcurrent relay. | Relay baseline | 2026-11-20 Capstone - Switched relay baseline | yes |
| 5 | duplicate | Relay baseline and Relay Baseline Notes are duplicate concept notes covering the same overcurrent relay baseline topic. | Relay Baseline Notes | Relay baseline | yes |

All 3 planted problems were found. Neon split them into 5 findings, and #2 is a real fourth issue:
"Pick the relay baseline" was still open on the project note.

<details><summary>Evidence quotes Neon cited</summary>

- **stale_task**: [[Solar Microgrid Capstone]]: "- [ ] Run the inverter fault sims (arc + line-to-ground)"; [[2026-11-18 Capstone - Inverter fault sim results]]: "Ran all inverter fault sims: arc faults and line-to-ground faults are done, 240 runs, results saved to sims/results.csv."
- **stale_task**: [[Solar Microgrid Capstone]]: "- [ ] Pick the relay baseline"; [[2026-11-20 Capstone - Switched relay baseline]]: "The baseline is now an inverse-time overcurrent relay on the IEC standard inverse curve (TMS 0.1, pickup 1.1x)."
- **superseded**: [[2026-11-12 Capstone - Agreed on relay baseline]]: "Decided the ML detector will be compared against a definite-time overcurrent relay: 50 ms delay, pickup at 1.2x rated current."; [[2026-11-20 Capstone - Switched relay baseline]]: "Prof. Okafor rejected the definite-time relay as too weak a baseline. The baseline is now an inverse-time overcurrent relay on the IEC standard inverse curve (TMS 0.1, pickup 1.1x)."
- **contradiction**: [[Relay baseline]]: "In the capstone this is a definite-time relay with a 50 ms delay."; [[2026-11-20 Capstone - Switched relay baseline]]: "The baseline is now an inverse-time overcurrent relay on the IEC standard inverse curve (TMS 0.1, pickup 1.1x)."
- **duplicate**: [[Relay baseline]]: "Conventional overcurrent relay logic used as the comparison for ML detectors."; [[Relay Baseline Notes]]: "The relay baseline is standard overcurrent relay logic that ML fault detectors are compared against. Inverse-time relays trip faster for larger fault currents."
</details>

## Step 3: fix (Managed Agent, Antigravity in a Google-hosted sandbox)
The sandbox got the 12 neighbourhood notes in full, a skeleton of the rest of the vault, the checker
and `findings.json`. The agent edited the notes, then ran the vault check itself:

```
$ python3 -m c2v.maintain --check --vault vault --scope scope.json; echo "EXIT_CODE=$?"
```
The check passed in the sandbox. We downloaded each note, wrote back only the 5 that changed,
and re-ran the check locally: ok=True, issues=0.
Agent run: 80.1 s, 84017 tokens, status `completed`.

**The agent's report (verbatim, file links trimmed):**

> 1. **stale_task (inverter fault sims)**: Marked `- [x] Run the inverter fault sims (arc + line-to-ground) (done, see [[2026-11-18 Capstone - Inverter fault sim results]])` in [Solar Microgrid Capstone.md].
> 2. **stale_task (relay baseline)**: Marked `- [x] Pick the relay baseline (done, see [[2026-11-20 Capstone - Switched relay baseline]])` in [Solar Microgrid Capstone.md].
> 3. **superseded (2026-11-12 relay baseline decision)**: Added a `> [!warning] Superseded by [[2026-11-20 Capstone - Switched relay baseline]]` callout under the H1 heading in [2026-11-12 Capstone - Agreed on relay baseline.md].
> 4. **contradiction (Relay baseline concept)**: Updated the capstone baseline sentence in [Relay baseline.md] to the IEC standard inverse-time overcurrent relay (TMS 0.1, pickup 1.1x) citing `[[2026-11-20 Capstone - Switched relay baseline]]`.
> 5. **duplicate (Relay Baseline Notes)**: Moved the unique inverse-time tripping fact into [Relay baseline.md], replaced the body of [Relay Baseline Notes.md] with `> [!note] Merged into [[Relay baseline]]`, and updated the link in [2026-11-20 Capstone - Switched relay baseline.md] to `[[Relay baseline]]`.
>
> Final exit code: `0` (`{"ok": true, "issues": []}`).

## Before / after (real diff)
```diff
--- 10 Learning and Teaching/11 Academic/EECE 410 Capstone Design/Solar Microgrid Capstone.md
+++ 10 Learning and Teaching/11 Academic/EECE 410 Capstone Design/Solar Microgrid Capstone.md
@@ -9,8 +9,8 @@
 Concepts: [[Fault detection]] · [[Relay baseline]] · [[Inverter control]]
 
 ## Open loops
-- [ ] Run the inverter fault sims (arc + line-to-ground)
-- [ ] Pick the relay baseline
+- [x] Run the inverter fault sims (arc + line-to-ground) (done, see [[2026-11-18 Capstone - Inverter fault sim results]])
+- [x] Pick the relay baseline (done, see [[2026-11-20 Capstone - Switched relay baseline]])
 
 ## Log
 - 2026-11-12 [[2026-11-12 Capstone - Agreed on relay baseline|Agreed on relay baseline]] (meeting)
--- 40 Knowledge/Concepts/Relay baseline.md
+++ 40 Knowledge/Concepts/Relay baseline.md
@@ -3,5 +3,4 @@
 tags: [concept]
 ---
 # Relay baseline
-Conventional overcurrent relay logic used as the comparison for ML detectors. In the capstone this is a
-definite-time relay with a 50 ms delay.
+Conventional overcurrent relay logic used as the comparison for ML detectors. Inverse-time relays trip faster for larger fault currents. In the capstone this is an inverse-time overcurrent relay on the IEC standard inverse curve (TMS 0.1, pickup 1.1x) ([[2026-11-20 Capstone - Switched relay baseline]]).
--- 40 Knowledge/Concepts/Relay Baseline Notes.md
+++ 40 Knowledge/Concepts/Relay Baseline Notes.md
@@ -2,6 +2,4 @@
 type: concept
 tags: [concept]
 ---
-# Relay Baseline Notes
-The relay baseline is standard overcurrent relay logic that ML fault detectors are compared against.
-Inverse-time relays trip faster for larger fault currents.
+> [!note] Merged into [[Relay baseline]]
--- Sessions/2026-11/2026-11-12 Capstone - Agreed on relay baseline.md
+++ Sessions/2026-11/2026-11-12 Capstone - Agreed on relay baseline.md
@@ -7,6 +7,9 @@
 ---
 # Agreed on relay baseline
 
+> [!warning] Superseded by [[2026-11-20 Capstone - Switched relay baseline]]
+> Definite-time overcurrent relay baseline (50 ms delay, 1.2x pickup) was rejected and replaced by an IEC standard inverse-time overcurrent relay (TMS 0.1, pickup 1.1x).
+
 ## Summary
 Met with the capstone team. Decided the ML detector will be compared against a definite-time overcurrent
 relay: 50 ms delay, pickup at 1.2x rated current. Worked on [[Solar Microgrid Capstone]].
--- Sessions/2026-11/2026-11-20 Capstone - Switched relay baseline.md
+++ Sessions/2026-11/2026-11-20 Capstone - Switched relay baseline.md
@@ -12,7 +12,7 @@
 overcurrent relay on the IEC standard inverse curve (TMS 0.1, pickup 1.1x). Worked on
 [[Solar Microgrid Capstone]].
 
-Concepts: [[Relay Baseline Notes]] · [[Fault detection]]
+Concepts: [[Relay baseline]] · [[Fault detection]]
 
 ## Next steps
 - [ ] Re-run the comparison against the inverse-time relay
```

## Step 4: re-check
Running the findings pass again on the fixed vault returns **0 findings** (30.6 s).

## Honest gaps
- The old 11-12 note still has an open task, "Implement the definite-time relay in the sim harness". It is
  moot now that the baseline changed, but neither pass flagged it (the callout above it says superseded).
- The merged duplicate keeps its file, as a redirect callout. We never delete notes automatically.
- `--apply` sends the neighbourhood notes' full text to the sandbox. The rest of the vault goes as titles only.
