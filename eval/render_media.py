"""LANE B. Turn a held-out note into a messy, realistic capture. Mix the kinds across cases.

TODO(lane-b):
- voice memo: read a casual retelling of the note (not the exact text) with gemini-3.8-flash-tts,
  then add background noise / crosstalk with numpy (SNR 5-15 dB). Save .wav.
- screenshot: render the note's text to a PNG with PIL, then blur, rotate +-5 deg, JPEG q=35.
- "handwritten": render with a handwriting-style font if available, plus perspective warp and shadow.
- scanned PDF: render to an image, add noise, save as PDF (img2pdf or PIL).
- Strip the [[wikilinks]] and the title from what gets rendered, so links must be inferred.
- Record difficulty knobs per case (snr_db, blur, rotation) so failures can be plotted against them.
- Also add 5-10 REAL captures from today (whiteboard photos, voice memos) under eval/real/ with a
  hand-written truth line each. The rules forbid evals made up entirely of team-written examples.
"""
