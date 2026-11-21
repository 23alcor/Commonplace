You are the Lane B agent (evaluation) for a hackathon. Read AGENTS.md first: it is the spec, the rules and the timeline. Submissions are due 5:00 PM ET.

Your files: everything in eval/. eval/score.py is already implemented and shared. The TODOs in eval/build_heldout.py, eval/render_media.py, eval/baseline.py and eval/run_eval.py are your plan.

Goal by 12:45: build_heldout.py makes cases from VAULT_PATH (it defaults to demo_vault; the real run will point at a private vault copy), and render_media.py renders screenshot-style and noisy-image captures with no API calls.
Then: TTS voice memos with background noise, the baseline runner, and run_eval.py producing eval/results/summary.md and one chart. Lane A's pipeline may not be ready yet. Write run_eval.py so the system side can be switched on later, and get the baseline numbers first.

Never commit private vault content or generated media made from it. Keep eval/work/ and eval/cases/ gitignored. Commit after every working step.
