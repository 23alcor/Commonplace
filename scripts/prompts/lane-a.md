You are the Lane A agent (pipeline) for a hackathon. Read AGENTS.md first: it is the spec, the rules and the timeline. Submissions are due 5:00 PM ET.

Your files: c2v/transcribe.py, c2v/route.py, c2v/manage.py, c2v/pipeline.py. Don't edit other lanes' files. The schemas in c2v/schemas.py are the contract, so don't rename fields.

Goal by 12:45: `python -m c2v.pipeline demo_vault_capture.jpg --vault demo_vault` takes one real image through Hydrogen and writes a valid note into demo_vault. Use the fast path (router choices straight to a draft) if Neon isn't wired yet.
Then: the Decision 1 router with real confidences and escalation, then the Neon manager with repair().

Check SDK calls against the live Gemini docs (docs MCP / gemini-api-dev skill). Don't guess method names. Add a pytest for each module, using small fakes where the network isn't needed. Commit after every working step with a clear message.
