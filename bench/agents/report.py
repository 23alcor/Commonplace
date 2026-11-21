"""LANE F. Tables + bar chart for the agent benchmark. Called by run_agents.py; reads results.json."""
from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LABEL = {"no_context": "no context", "context_file": "CLAUDE.md file", "rag": "RAG (embeddings)",
         "c2v": "capture-to-vault get_context"}
SCORE = {"correct": 1.0, "partial": 0.5, "wrong": 0.0}


def _agg(rs: list[dict]) -> dict:
    n = len(rs)
    return {
        "n": n,
        "correct": sum(r["verdict"] == "correct" for r in rs) / n,
        "score": sum(SCORE[r["verdict"]] for r in rs) / n,
        "halluc": sum(bool(r["hallucinated"]) for r in rs) / n,
        "tokens": statistics.mean(r["context_tokens"] for r in rs),
        "input": statistics.mean(r["usage"]["input"] for r in rs),
        "tools": statistics.mean(r["tool_calls"] for r in rs),
        "lat": statistics.median(r["latency_s"] for r in rs),
        "cost": sum(r["cost_usd"] for r in rs),
    }


def report(rows: list[dict], qs: list[dict]) -> str:
    runs = list(dict.fromkeys((r["model"], r["arm"], r["budget"]) for r in rows))
    sel = lambda rs, k: [r for r in rs if (r["model"], r["arm"], r["budget"]) == k]  # noqa: E731
    lines = ["| model | arm | budget | n | correct | score (partial=0.5) | hallucination rate | context tokens (mean) "
             "| model input tokens (mean) | tool calls (mean) | latency p50 (s) | cost (USD) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    aggs = {}
    for m, a, b in runs:
        g = aggs[(m, a, b)] = _agg(sel(rows, (m, a, b)))
        lines.append(f"| {m.replace('gemini-4-', '')} | {LABEL[a]} | {b or '-'} | {g['n']} | {g['correct']:.0%} | {g['score']:.0%} "
                     f"| {g['halluc']:.0%} | {g['tokens']:.0f} | {g['input']:.0f} | {g['tools']:.1f} "
                     f"| {g['lat']:.1f} | {g['cost']:.3f} |")
    kinds = list(dict.fromkeys(q["kind"] for q in qs))
    lines += ["", "Score (partial=0.5) by question kind:", "",
              "| model | arm | budget | " + " | ".join(f"{k} (n={sum(q['kind'] == k for q in qs)})" for k in kinds) + " |",
              "|---|---|---|" + "---|" * len(kinds)]
    for m, a, b in runs:
        cells = []
        for k in kinds:
            rs = [r for r in sel(rows, (m, a, b)) if r["kind"] == k]
            cells.append(f"{_agg(rs)['score']:.0%}" if rs else "-")
        lines.append(f"| {m.replace('gemini-4-', '')} | {LABEL[a]} | {b or '-'} | " + " | ".join(cells) + " |")
    table = "\n".join(lines)
    (ROOT / "tables.md").write_text(table + "\n")
    print(table)
    chart(aggs)
    return table


def chart(aggs: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    keys = list(aggs)
    names = [f"{LABEL[a]}\n{m.replace('gemini-4-', '')}" + (f", {b} tok" if b else "") for m, a, b in keys]
    correct = [aggs[k]["correct"] * 100 for k in keys]
    partial = [(aggs[k]["score"] - aggs[k]["correct"]) * 100 for k in keys]  # half-credit share
    halluc = [aggs[k]["halluc"] * 100 for k in keys]
    colors = {"no_context": "#9aa0a6", "context_file": "#c58af9", "rag": "#fbbc04", "c2v": "#1a73e8"}
    fig, ax = plt.subplots(figsize=(13, 5), dpi=150)
    xs = range(len(keys))
    ax.bar(xs, correct, color=[colors[a] for _, a, _ in keys], label="correct",
           hatch=None)
    ax.bar(xs, partial, bottom=correct, color=[colors[a] for _, a, _ in keys], alpha=0.35,
           label="partial (half credit)")
    ax.scatter(xs, halluc, marker="x", color="#d93025", zorder=3, s=60, label="hallucination rate")
    for x, c, p, k in zip(xs, correct, partial, keys):
        ax.text(x, c + p + 1.5, f"{c + p:.0f}", ha="center", fontsize=9)
        if c > 20:
            ax.text(x, c / 2, f"{aggs[k]['tokens']:.0f}\nctx tok", ha="center", va="center", fontsize=8,
                    color="white")
    ax.set_xticks(list(xs), names, fontsize=7)
    ax.set_ylabel("% of 25 questions")
    ax.set_ylim(0, 105)
    ax.set_title("25 questions about the user's own projects: same model and prompt, only the context source changes")
    ax.legend(fontsize=8, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(ROOT / "accuracy.png")
    print(f"wrote {ROOT / 'accuracy.png'}")


if __name__ == "__main__":
    rows = json.loads((ROOT / "results.json").read_text())
    qs = json.loads((ROOT / "questions.json").read_text())
    report(rows, qs)
