import base64, io, sys, wave
from google import genai
LINES = {
 "h1": "Today I built this project with three different AIs. And I had to explain the same project to every one of them.",
 "h2": "Context files help. But they're written by hand, they're tied to one tool, and whatever you leave out is gone.",
 "h3": "So I built a context manager.",
 "h4": "Throw it anything: a whiteboard, a voice memo, a video. Gemini 4 Hydrogen reads it.",
 "h5": "Decision 1 decides where it belongs. When it's unsure, Gemini 4 Neon files it and links it to the right notes.",
 "h6": "And a Managed Agent verifies every note before it's saved.",
 "h7": "Now any AI calls one tool: get context. Claude and Gemini both answer from the note I captured seconds ago.",
 "h8": "Without context, agents answered zero questions correctly. With get context, they answered all of them, with five times fewer tokens than RAG. And it holds up at five thousand notes.",
 "h9": "Explain your project once. Every AI gets it.",
}
c = genai.Client(http_options={"api_version": "v1beta"})
for k in (sys.argv[1:] or LINES):
    r = c.interactions.create(model="gemini-3.8-flash-tts", input=LINES[k], response_format={"type": "audio"},
                              generation_config={"speech_config": [{"voice": "Puck"}]})
    d = r.output_audio.data; d = base64.b64decode(d) if isinstance(d, str) else d
    open(f"vo/{k}.wav", "wb").write(d); print(k, flush=True)
