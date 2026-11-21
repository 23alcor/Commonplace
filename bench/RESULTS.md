# Which Gemini 4 model should do each step?

**Bottom line, stated plainly.** On our inputs, no model scored clearly higher than another on either
step. Both tasks are close to saturated, so **cost and latency decide.**
- **Transcribe: keep Hydrogen.** All four models wrote the same content. Hydrogen had the lowest p50
  latency (6.6 s). Carbon and Argon cost about 20% less per capture because they spent no thinking
  tokens at `low`. The differences are a few tenths of a cent.
- **Manage: the numbers do not favor Neon.** Argon matched Neon's folder accuracy (10/10) at **¼ of the
  cost and half the latency** ($0.008 vs $0.035 per note, p50 8.5 s vs 17.1 s). Neon's link precision
  was slightly higher (0.96 vs 0.91). Neon also had the worst tail of the four (p90 40.7 s), which is a
  real risk in a live demo.
- **If we keep Neon, run it at `thinking_level: "low"`, not `"medium"`.** On the same 5 cases the
  quality was identical (1.00 across the board), p50 latency fell from 18.4 s to 11.3 s, and cost fell
  28%.

Run: Nov 21 2026, 13:29 ET. 65 API calls, $1.10 total. All calls are cached in `bench/cache/calls/`,
so `python -m bench.run_bench --report` rebuilds these tables at no cost.

## What the docs say (checked live, not guessed)

`client.models.list()` lists four Gemini 4 chat models for our key: hydrogen, neon, argon and
carbon. Descriptions are quoted from each model page. Prices are Standard tier, USD per 1M tokens, and
the output price includes thinking tokens.

| Model | Docs describe it as | Thinking levels (default) | $ in / out |
|---|---|---|---|
| `gemini-4-hydrogen` | "cutting-edge intelligence to everyone, with speed and efficiency for everyday coding and agentic workflows" | low, medium, high, xhigh (high) | 1.50 / 7.50 |
| `gemini-4-neon` | "frontier-level intelligence with fast end-to-end task completion across complex software engineering, knowledge work, and science workflows" | low, medium, high, xhigh (high) | 3.00 / 15.00 |
| `gemini-4-argon` | "our efficient Gemini 4 frontier reasoning model… faster responses and lower token spend per turn compared to Gemini 4 Carbon" | low, medium, high (medium) | 2.00 / 10.00* |
| `gemini-4-carbon` | "our most capable reasoning model, built for complex software engineering, mathematical and scientific problem solving, high factual accuracy" | low, medium, high (medium) | 2.00 / 10.00* |
| `gemini-decision-1` | "a specialized multimodal model built for the Decisions API", returns "calibrated probabilities" with zero output tokens | not supported | 0.10 input |

\* Carbon and Argon prices double on Dec 1 2026, to 4.00 / 20.00.
All four chat models take text, image, video, audio and PDF input and have a 1,048,576-token context.
`minimal` thinking is not supported on Gemini 4.

Sources: [models](https://ai.google.dev/gemini-api/docs/models) ·
[hydrogen](https://ai.google.dev/gemini-api/docs/models/gemini-4-hydrogen) ·
[neon](https://ai.google.dev/gemini-api/docs/models/gemini-4-neon) ·
[argon](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon) ·
[carbon](https://ai.google.dev/gemini-api/docs/models/gemini-4-carbon) ·
[decision-1](https://ai.google.dev/gemini-api/docs/models/gemini-decision-1) ·
[pricing](https://ai.google.dev/gemini-api/docs/pricing) ·
[thinking](https://ai.google.dev/gemini-api/docs/thinking).
The ai.google.dev links currently redirect to the same paths on aistudio.google.com.
Two things the docs leave open: there is no separate audio-input price, and the decision-1 price came
from a truncated pricing page.
The docs also disagree on the default output cap for Carbon and Argon: the thinking page says 32,768
tokens and the model pages say 65,536.

## Step 1: Transcribe (media → Capture)

Inputs: 4 of lane D's `demo_captures/`: a voice memo (espeak TTS plus noise), a handwritten page, a
phone screenshot and a 2-page scanned PDF. The reference is the exact text each capture was rendered
from (`bench/references.json`). Prompt and schema are identical to lane A's `c2v/transcribe.py`. Lane A
ships `low` thinking.

| Model | thinking | n ok | WER (lower better) | key-term recall | p50 latency s | p90 latency s | $ / capture |
|---|---|---|---|---|---|---|---|
| gemini-4-hydrogen | low | 4/4 | 0.050 | 0.97 | 6.6 | 7.9 | 0.0070 |
| gemini-4-neon | low | 4/4 | 0.042 | 0.97 | 10.3 | 11.1 | 0.0182 |
| gemini-4-argon | low | 4/4 | 0.042 | 0.97 | 8.1 | 8.8 | 0.0057 |
| gemini-4-carbon | low | 4/4 | 0.008 | 0.97 | 6.9 | 8.0 | 0.0055 |
| gemini-4-carbon | medium | 4/4 | 0.042 | 0.97 | 25.1 | 30.7 | 0.0177 |

How to read it:
- **The WER gap is not a content gap.** All of the difference comes from one line on the screenshot:
  Carbon at `low` copied the phone status bar ("9:41 LTE 71%") and the others left it out. Every model
  produced the same note content.
- **Shared failure.** All four models transcribed the spoken "EECE 448" as **"CS 448"**. That is why
  key-term recall is 0.97 and not 1.00. The transcriber can't fix this. It is a job for the manager,
  which sees the vault, so it is worth showing in the demo.
- **Thinking-level check.** Carbon was the step winner, so we also ran it at `medium`. It got no better,
  took 3.6× longer and cost 3.2× more.
- **Why Hydrogen isn't cheapest per capture.** Hydrogen has the lowest per-token price, but at `low` it
  still spent about 400 thinking tokens per capture. Carbon and Argon spent none.

## Step 3: Manage (escalated capture → NoteDraft)

Cases: 10 notes held out of `mock_vault`, picked with seed 42, at least 2 resolving links each, spread
across all top-level folders. Each held-out note was removed from the in-memory vault. The model got
the note's text with the title and `[[ ]]` markup removed. It also got a simulated escalated router
output: folder probabilities from keyword search, all below 0.75, never derived from the truth. Prompt
and schema mirror lane A's `c2v/manage.py`. Lane A ships `medium` thinking. Scoring uses
`eval/score.py` and `c2v/verify.py`.

| Model | thinking | n ok | folder acc | link P | link R | link F1 | verify pass | p50 latency s | p90 latency s | $ / note |
|---|---|---|---|---|---|---|---|---|---|---|
| gemini-4-hydrogen | medium | 10/10 | 0.90 | 1.00 | 1.00 | 1.00 | 1.00 | 9.6 | 11.2 | 0.0171 |
| gemini-4-neon | medium | 10/10 | 1.00 | 0.96 | 1.00 | 0.97 | 1.00 | 17.1 | 40.7 | 0.0349 |
| gemini-4-argon | medium | 10/10 | 1.00 | 0.91 | 1.00 | 0.95 | 1.00 | 8.5 | 10.3 | 0.0077 |
| gemini-4-carbon | medium | 10/10 | 1.00 | 0.93 | 1.00 | 0.96 | 1.00 | 18.7 | 27.8 | 0.0165 |

Thinking-level check on the step winner, Neon, using the same 5 cases at both levels:

| Model | thinking | n ok | folder acc | link F1 | verify pass | p50 latency s | p90 latency s | $ / note |
|---|---|---|---|---|---|---|---|---|
| gemini-4-neon | medium | 5/5 | 1.00 | 1.00 | 1.00 | 18.4 | 31.0 | 0.0348 |
| gemini-4-neon | low | 5/5 | 1.00 | 1.00 | 1.00 | 11.3 | 13.0 | 0.0251 |

Per case at production thinking (✓/✗ = folder correct, plus link F1):

| Case (held-out note) | hydrogen | neon | argon | carbon |
|---|---|---|---|---|
| About Me | ✓ 1.00 | ✓ 1.00 | ✓ 1.00 | ✓ 1.00 |
| ECON 205 Behavioral Economics | ✓ 1.00 | ✓ 1.00 | ✓ 0.89 | ✓ 0.89 |
| Career | ✓ 1.00 | ✓ 1.00 | ✓ 1.00 | ✓ 1.00 |
| Homelab Server | ✓ 1.00 | ✓ 1.00 | ✓ 1.00 | ✓ 1.00 |
| 2026-11-10 EECE 448 - Ridge vs lasso on housing data | ✓ 1.00 | ✓ 1.00 | ✓ 1.00 | ✓ 1.00 |
| Home | ✓ 1.00 | ✓ 1.00 | ✓ 0.86 | ✓ 1.00 |
| PHYS 230 Electromagnetics | ✓ 1.00 | ✓ 1.00 | ✓ 0.89 | ✓ 0.89 |
| Job Search | ✓ 1.00 | ✓ 0.75 | ✓ 0.86 | ✓ 0.86 |
| Projects | ✗ 1.00 | ✓ 1.00 | ✓ 1.00 | ✓ 1.00 |
| 2026-11-20 Homelab - Tailscale ACL cleanup | ✓ 1.00 | ✓ 1.00 | ✓ 1.00 | ✓ 1.00 |

Honest limits:
- **The manage task is too easy as built, so it can't separate the models.** Only the `[[ ]]` markup
  was removed, not the linked titles themselves. The text still says "Tailscale" or "Interview Prep",
  so link recall is 1.00 for every model. Lane B's eval removes link text completely and is the harder
  test.
- **The router output is simulated, not real.** We did not call Decision 1 for these cases.
- **The sample is small** (n = 4 and n = 10), so a single case moves the score by 0.10. Treat ties as
  ties.

## Why Hydrogen transcribes and Neon manages

Hydrogen transcribes because all four models wrote the same content on our captures (key-term recall 0.97 for every model, including the same "CS 448" mishearing), so speed decides, and Hydrogen had the fastest p50 (6.6 s) at $0.007 per capture. Neon manages because it filed all 10 held-out notes in the right folder and passed verify on all 10, with higher link precision than Argon or Carbon (0.96 vs 0.91 and 0.93), and a wrong `[[link]]` is the error a user notices. The same numbers show what that costs: Argon ties Neon on folder accuracy at ¼ of the price and half the latency, and Neon at `low` thinking matched Neon at `medium` on all 5 shared cases while running 40% faster, so we should ship **Neon at `low`** and keep **Argon as the backup** if live-demo latency becomes a problem.
