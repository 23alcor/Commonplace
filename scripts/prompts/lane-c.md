You are the Lane C agent (Managed Agent verifier + demo app) for a hackathon. Read AGENTS.md first: it is the spec, the rules and the timeline. Submissions are due 5:00 PM ET.

Your files: c2v/agent_verify.py and app/. c2v/verify.py (deterministic checks plus a CLI) is shared and already implemented.

Goal by 12:45: a FastAPI app (app/server.py) with a phone-friendly capture page that takes a photo, file or mic recording and POSTs it to /capture. Stub the pipeline call until Lane A merges.
Then: agent_fix() using the Antigravity Managed Agent in a Google-hosted sandbox. It runs `python -m c2v.verify` on the draft, fixes issues until the exit code is 0, and logs each agent turn. Check the Managed Agents API against the live Gemini docs (docs MCP / gemini-api-dev skill). Don't guess.
Then: live step-by-step progress on the page with SSE, ending with the rendered note.

No Streamlit, and no dashboard-as-product. Commit after every working step.
