# Lane A task: video capture (after keep-source; due 3:30 PM)
Pitch: "context from any conversation or video watched." Make video a first-class capture:
1. transcribe.py: for mp4/mov/webm, send the video to Hydrogen (check the docs for video input, inline vs
   Files API by size) and return a Capture whose transcript is segmented with timestamps
   ([mm:ss] lines), plus key moments: decisions, action items, on-screen diagrams/code worth keeping.
   Add an optional `segments` field to Capture if needed (optional field only; don't rename anything).
2. The filed note keeps a "## Timeline" with [mm:ss] bullets, and Neon links each segment to the right
   existing notes. Long videos may produce one hub note plus links, not one giant blob.
3. Test on a real 3-5 min video: make one with no personal data (e.g. record /stage plus a
   narrated explanation, or ffmpeg-stitch demo_captures with TTS narration about EECE 448 + Plant
   Watering Bot so it spans two projects). Put it in demo_captures/11_video_*.mp4 if < 25 MB.
4. Report latency and cost of one video capture. Commit after each step.
