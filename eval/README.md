# Evaluation workflow

From the repository root:

```bash
python -m eval.build_heldout --vault demo_vault --voice
python -m eval.run_eval
python -m eval.run_eval --system --agent-verify
```

Set `VAULT_PATH` to a **private vault copy** for the actual held-out run and omit `--vault`. The builder removes selected source notes from `eval/work/vault`, preserves their link targets, and writes the truth to `eval/cases/cases.jsonl`. With `--voice`, every fourth case uses Gemini TTS; the other media types render locally. Voice generation needs a Gemini API key and network access. The baseline and system runs need the same key.

`eval/run_eval.py` resumes completed case/method pairs and reruns cases if their media or truth changes. Use `--rerun` after changing a prompt or model. It defaults to baseline only, so it works while the pipeline is under development. Results contain aggregate metrics and a chart in `eval/results/`; raw per-case rows are ignored by git.

For real captures, place media under ignored `eval/real/` and create a manually checked JSONL truth file. Each row needs `case_id`, `title`, `folder`, `links`, `media_kind`, `media_path`, and `difficulty`. `media_path` points to the capture. Run it with `python -m eval.run_eval --cases eval/real/cases.jsonl --vault eval/work/vault --results eval/results/real`. Do not commit the media, truth file, vault copy, or raw results. Report the real-capture sample size separately from rendered cases.

The synthetic `demo_vault` is a smoke test, not evidence that the system beats the baseline. The four available demo notes yield four link-safe held-out cases; use a larger private vault and unrehearsed real captures for the judging comparison.
