You are the Lane E agent (model benchmarking) for a hackathon. Read AGENTS.md first: it is the spec, the rules and the timeline. Submissions are due 5:00 PM ET.

Your files: bench/ only (plus a "Why these models" section you write to bench/RESULTS.md). Do not edit c2v/, app/, eval/ or docs/. Lane B owns the end-to-end eval in eval/; you answer a different question: which Gemini 4 model should do each step, and why.

1. Check the live Gemini docs (docs MCP / gemini-api-dev skill) for every Gemini 4 model available to us (Hydrogen, Neon, any others) and what each is described as good at. Write what the docs actually say, with links. Don't guess.
2. bench/run_bench.py: for each step, run every candidate model on the same small inputs and record latency (p50/p90), tokens/cost if reported, and quality:
   - Transcribe: the captures in demo_captures/ (if present) or a few you render; score transcript vs a reference (word error rate / key-term recall).
   - Manage: 10 escalated cases from mock_vault (remove a note, give its text + router output); score folder accuracy and link F1 with eval/score.py.
   - Also try thinking_level low vs medium on the winner.
   Keep it small: at most ~60 API calls total, cache results to bench/cache/ so reruns are free, and back off on rate-limit errors.
3. bench/RESULTS.md: one table per step (model x latency x quality x cost) and a 3-sentence "why Hydrogen transcribes and Neon manages" grounded in your numbers. If the numbers say a different assignment is better, say so plainly at the top.

Deadline: results table by 2:30 PM. Commit after every working step.
