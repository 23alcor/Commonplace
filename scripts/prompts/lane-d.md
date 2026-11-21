You are the Lane D agent (demo inputs + submission) for a hackathon. Read AGENTS.md first: it is the spec, the rules and the timeline. Submissions are due 5:00 PM ET.

Your files: demo_captures/, docs/, and the README sections other than the Results table (Lane B fills that). Do not edit c2v/, app/ or eval/.

Goal by 1:00: demo_captures/ holds 8-10 realistic, unprepared-looking test inputs that match demo_vault's topics: a short voice memo (generate with TTS, add noise), a whiteboard photo and a handwritten page (render with PIL, skew + blur), a phone screenshot, a scanned-looking PDF. Synthetic only, no personal data. Add demo_captures/README.md saying which vault note each one should file into or link to.
Then: docs/demo-script.md, a 3-minute live demo script that names each model's one job (Hydrogen = transcriber, Decision 1 = router, Neon = vault manager, Managed Agent = verifier), the baseline comparison, one honest failure, and a fallback if the network drops.
Then: docs/submission.md with the project description, a 1-minute video shot list, and a pre-submit checklist (repo public, no .env or real vault in git history, results table filled).

Commit after every working step.
