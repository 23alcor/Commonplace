# 1-minute video script

Record at 1920x1080. Screen: `/stage` full screen, with the phone capture page mirrored in a
corner (QuickTime → New Movie Recording → pick the iPhone as camera), or record the phone
separately and cut between them. Voice-over is about 150 words, which fits in 60 seconds.

| Time | On screen | Voice-over |
|---|---|---|
| 0:00–0:07 | Hook: a messy whiteboard photo and a voice memo, then the vault graph. Title: **capture → vault** | "Every whiteboard photo and voice memo I take dies in my camera roll. This turns them into a filed, linked note in my vault." |
| 0:07–0:15 | Phone: tap **Capture**, snap `02_whiteboard_smith_chart.jpg`. `/stage` lights up **① Transcribe** (blue) | "Gemini 4 Hydrogen reads the media: handwriting, audio, scans." |
| 0:15–0:25 | **② Route** (orange): confidence bars rise past the 0.75 line. Zoom in on the bars | "Gemini Decision 1 picks the note type and folder, with a calibrated confidence for each. If it's sure, the note is filed right away." |
| 0:25–0:35 | Cut to `09_ambiguous_salary_anchor.jpg`: the bars stop **below** the line, "escalate to Neon", then **③ Manage** (purple). The yellow node flies into the graph and links to Anchoring and Job Search | "When it isn't sure, it escalates. Gemini 4 Neon reads the vault and writes the note, with links to the notes it belongs next to." |
| 0:35–0:45 | **④ Verify** (green): one ✗ check turns into ✓ checks. Show a line of the Managed Agent log | "Nothing is filed until it passes verification. A Managed Agent runs our checker in a sandbox and fixes whatever breaks." |
| 0:45–0:55 | README results table: baseline vs capture-to-vault (folder accuracy, link F1, verify pass) | "On notes we held out and re-captured as noisy media, it beats a single-model baseline: [X]% vs [Y]% folder accuracy." |
| 0:55–1:00 | Back to the graph with the new yellow note, then the repo link | "One model, one job. Messy media in, a clean note out. github.com/23alcor/Commonplace" |

## Before you record
- Fill in [X] and [Y] from the README Results table (lane B, about 3:45).
- Do one dry run per capture so the vault already has the links you want to show. Then reset the vault with `python scripts/make_mock_vault.py`.
- Close terminals and `.env`. Nothing secret on screen.
- If Neon is slow, record the steps live and cut the waiting out in editing. Say "sped up" in a caption.
