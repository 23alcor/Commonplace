import base64, io, json, sys, wave
from google import genai
LINES = {
 "l1": "Every whiteboard photo and voice memo I take dies in my camera roll. Capture to Vault turns them into a filed, linked note in my Obsidian vault.",
 "l2": "Snap a photo. Gemini 4 Hydrogen reads it: handwriting, audio, even scans.",
 "l3": "Gemini Decision 1 routes it, with a calibrated confidence for every choice.",
 "l4": "When it isn't sure, it escalates. Gemini 4 Neon reads the vault, writes the note, and links it to the notes it belongs next to.",
 "l5": "Nothing gets filed until it passes verification. A Managed Agent checks every link, and fixes anything that breaks.",
 "l6": "On notes we held out and re-captured as noisy media, it beats a single-model baseline.",
 "l7": "One model, one job. Messy media in, clean notes out.",
}
only = sys.argv[1:] or list(LINES)
c = genai.Client(http_options={"api_version": "v1beta"})
style = ""
for k in only:
    r = c.interactions.create(model="gemini-3.8-flash-tts", input=style + LINES[k],
        response_format={"type": "audio"}, generation_config={"speech_config": [{"voice": "Puck"}]})
    d = r.output_audio.data; d = base64.b64decode(d) if isinstance(d, str) else d
    with wave.open(io.BytesIO(d)) as w: dur = w.getnframes() / w.getframerate()
    open(f"vo/{k}.wav", "wb").write(d); print(k, round(dur, 2))
