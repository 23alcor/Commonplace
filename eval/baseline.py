"""LANE B. Baseline = ONE gemini-4-hydrogen call per capture, no router, no vault search, no verify.

TODO(lane-b):
- Prompt: the media + vault.describe() + "write an Obsidian note for this capture: pick the folder,
  title, and [[links]] to existing notes". Structured output -> NoteDraft.
- This is the honest "how people would do it with one model call" baseline the problem statement asks for.
"""
