"""Build the SCALE.md tables and the recall/precision-vs-size chart from results/*.jsonl (no API calls)."""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bench.scale.run_scale import summary_table  # noqa: E402

HERE = Path(__file__).resolve().parent
ROWS = HERE / "results" / "rows_rag_keyword_get_context.jsonl"
# validated categorical slots 1-3 (dataviz reference palette, light mode), fixed order per system
COLOR = {"get_context": "#2a78d6", "rag": "#eb6834", "keyword": "#1baf7a"}
LABEL = {"get_context": "get_context (managed vault)", "rag": "RAG (gemini-embedding-2)", "keyword": "keyword search"}
INK, MUTED, GRID = "#1f1f1e", "#6b6a63", "#e6e5e0"


def main() -> None:
    rows = [json.loads(line) for line in ROWS.read_text().splitlines()]
    sizes = sorted({r["n_notes"] for r in rows})
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), dpi=150, sharey=False)
    for ax, metric in zip(axes, ["recall", "precision"]):
        ends = []
        for s in ["get_context", "rag", "keyword"]:
            ys = [st.mean(r[metric] for r in rows if r["system"] == s and r["n_notes"] == n) for n in sizes]
            ax.plot(sizes, ys, color=COLOR[s], lw=2, marker="o", ms=8, mec="white", mew=2, label=LABEL[s])
            ends.append((ys[-1], s))
        top = 1.05 if metric == "recall" else 0.4
        gap = top * 0.06  # nudge end labels apart so close values don't collide
        placed = []
        for y, s in sorted(ends, reverse=True):
            ly = min([y] + [p - gap for p in placed])
            placed.append(ly)
            ax.annotate(f"{y:.2f}", (sizes[-1], y), xytext=(sizes[-1] * 1.25, ly), textcoords="data",
                        va="center", fontsize=9, color=INK)
        ax.set_xscale("log")
        ax.set_xticks(sizes, [f"{n:,}" for n in sizes])
        ax.minorticks_off()
        ax.set_xlim(sizes[0] * 0.7, sizes[-1] * 2.2)
        ax.set_ylim(0, top)
        ax.set_title(f"{metric.capitalize()} of gold notes", loc="left", fontsize=11, color=INK)
        ax.set_xlabel("notes in vault (log scale)", fontsize=9, color=MUTED)
        ax.grid(axis="y", color=GRID, lw=1)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        ax.tick_params(colors=MUTED, labelsize=9)
    axes[0].legend(frameon=False, fontsize=9, loc="lower left")
    fig.suptitle("Context retrieval at a 4,000-token budget, 26-30 questions per vault size", x=0.01, ha="left",
                 fontsize=12, color=INK)
    fig.tight_layout()
    fig.savefig(HERE / "scale_chart.png", facecolor="white")
    print(summary_table(rows))
    print()
    print(summary_table(rows, by_kind=True))


if __name__ == "__main__":
    main()
