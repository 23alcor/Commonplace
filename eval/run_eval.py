"""Resumeable baseline/system eval with aggregate, public-safe reports."""
from __future__ import annotations

import argparse
import json
import statistics
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from c2v.vault import Vault
from c2v.verify import verify_draft
from eval.baseline import run_baseline
from eval.score import CaseScore, score_case, summarize

ROOT = Path(__file__).resolve().parent
WRITE_LOCK = threading.Lock()


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def run_one(case: dict, method: str, vault_path: Path, agent_verify: bool = False) -> dict:
    start = time.monotonic()
    row = {"case_id": case["case_id"], "method": method,
           "media_kind": case["media_kind"], "difficulty": case.get("difficulty", {})}
    try:
        vault = Vault(vault_path)
        if method == "baseline":
            draft = run_baseline(case["media_path"], vault)
            path_taken = "single_call"
            report = verify_draft(draft, vault)  # scoring only; baseline has no repair step
        else:
            from c2v.pipeline import file_capture
            result = file_capture(case["media_path"], vault, dry_run=True,
                                  agent_verify=agent_verify)
            draft, report, path_taken = result.draft, result.verify, result.path_taken
        score = score_case(case["case_id"], case["folder"], case["links"],
                           draft.folder, draft.links, report.ok)
        row.update({"status": "ok", "score": vars(score), "path_taken": path_taken,
                    "latency_s": round(time.monotonic() - start, 3),
                    "issue_codes": [issue.code for issue in report.issues]})
    except Exception as exc:
        row.update({"status": "error", "error_type": type(exc).__name__,
                    "latency_s": round(time.monotonic() - start, 3), "path_taken": "error"})
    return row


def _aggregate(rows: list[dict]) -> dict:
    good = [r for r in rows if r["status"] == "ok"]
    scores = [CaseScore(**r["score"]) for r in good]
    metrics = summarize(scores)
    metrics.update({"attempted": len(rows), "completed": len(good),
                    "errors": len(rows) - len(good),
                    "median_latency_s": statistics.median(r["latency_s"] for r in good) if good else None})
    return metrics


def _reason(row: dict) -> str:
    if row["status"] != "ok":
        return f"run error ({row.get('error_type', 'unknown')})"
    s = row["score"]
    parts = []
    if not s["folder_correct"]:
        parts.append("wrong folder")
    if s["link_f1"] < 1:
        parts.append("missed or extra links")
    if not s["verify_ok"]:
        parts.append("verify: " + ", ".join(row.get("issue_codes", [])))
    return "; ".join(parts) or "passed"


def _chart(rows: list[dict], output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    buckets = defaultdict(list)
    for row in rows:
        if row["status"] != "ok":
            continue
        knobs = row.get("difficulty", {})
        if "snr_db" in knobs:
            bucket = "audio <10 dB" if knobs["snr_db"] < 10 else "audio ≥10 dB"
        else:
            blur = knobs.get("blur_px", 0)
            bucket = "blur <1 px" if blur < 1 else "blur ≥1 px"
        buckets[(row["method"], bucket)].append(row["score"]["folder_correct"])
    if not buckets:
        return
    labels = ["blur <1 px", "blur ≥1 px", "audio <10 dB", "audio ≥10 dB"]
    methods = sorted({key[0] for key in buckets})
    fig, ax = plt.subplots(figsize=(8, 4.5))
    width = 0.35
    for i, method in enumerate(methods):
        vals = [statistics.mean(buckets[(method, label)]) if buckets[(method, label)] else 0
                for label in labels]
        ax.bar([x + i * width for x in range(len(labels))], vals, width, label=method)
    ax.set_xticks([x + width * (len(methods) - 1) / 2 for x in range(len(labels))], labels)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Folder accuracy")
    ax.set_xlabel("Capture difficulty")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def write_summary(rows: list[dict], output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    methods = sorted({row["method"] for row in rows})
    summary = {method: _aggregate([r for r in rows if r["method"] == method])
               for method in methods}
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = ["# Held-out evaluation", "", "Scores include completed cases only; errors are reported separately.", "",
             "| Method | Done / attempted | Folder acc | Link P | Link R | Link F1 | Verify pass | Median latency |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for method in methods:
        m = summary[method]
        latency = f"{m['median_latency_s']:.2f}s" if m["median_latency_s"] is not None else "—"
        lines.append(f"| {method} | {m['completed']} / {m['attempted']} | {m['folder_accuracy']:.1%} | "
                     f"{m['link_precision']:.1%} | {m['link_recall']:.1%} | {m['link_f1']:.1%} | "
                     f"{m['verify_pass_rate']:.1%} | {latency} |")
    lines += ["", "## Failures by capture", "", "| Method | Media kind | Runs | Failures |", "|---|---|---:|---:|"]
    for method in methods:
        by_kind = defaultdict(list)
        for row in rows:
            if row["method"] == method:
                by_kind[row["media_kind"]].append(row)
        for kind, group in sorted(by_kind.items()):
            failures = sum(r["status"] != "ok" or not r["score"]["verify_ok"] or
                           not r["score"]["folder_correct"] for r in group)
            lines.append(f"| {method} | {kind} | {len(group)} | {failures} |")
    lines += ["", "## Failures by difficulty", "", "| Method | Difficulty | Runs | Failures |",
              "|---|---|---:|---:|"]
    for method in methods:
        by_difficulty = defaultdict(list)
        for row in rows:
            if row["method"] != method:
                continue
            knobs = row.get("difficulty", {})
            if "snr_db" in knobs:
                label = "audio SNR <10 dB" if knobs["snr_db"] < 10 else "audio SNR ≥10 dB"
            else:
                label = "blur <1 px" if knobs.get("blur_px", 0) < 1 else "blur ≥1 px"
            by_difficulty[label].append(row)
        for label, group in sorted(by_difficulty.items()):
            failures = sum(r["status"] != "ok" or not r["score"]["verify_ok"] or
                           not r["score"]["folder_correct"] for r in group)
            lines.append(f"| {method} | {label} | {len(group)} | {failures} |")
    lines += ["", "## Worst cases", ""]
    failures = sorted(rows, key=lambda r: (r["status"] == "ok",
        r.get("score", {}).get("folder_correct", False),
        r.get("score", {}).get("link_f1", 0)))
    for row in failures[:5]:
        lines.append(f"- {row['case_id']} ({row['method']}, {row['media_kind']}): {_reason(row)}")
    lines += ["", "![Accuracy by difficulty](accuracy_by_difficulty.png)", ""]
    (output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    _chart(rows, output_dir / "accuracy_by_difficulty.png")
    return summary


def run(cases_path: Path, vault_path: Path, output_dir: Path,
        system: bool = False, workers: int = 6, agent_verify: bool = False) -> dict:
    cases = load_jsonl(cases_path)
    if not cases:
        raise ValueError(f"No cases in {cases_path}; run python -m eval.build_heldout first")
    if not vault_path.is_dir():
        raise FileNotFoundError(vault_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "results.jsonl"
    existing = load_jsonl(result_path)
    valid_ids = {case["case_id"] for case in cases}
    latest = {(r["case_id"], r["method"]): r for r in existing if r["case_id"] in valid_ids}
    rows = list(latest.values())
    done = {(r["case_id"], r["method"]) for r in rows if r["status"] == "ok"}
    methods = ["baseline", "system"] if system else ["baseline"]
    tasks = [(case, method) for case in cases for method in methods
             if (case["case_id"], method) not in done]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_one, case, method, vault_path, agent_verify)
                   for case, method in tasks]
        for future in as_completed(futures):
            row = future.result()
            with WRITE_LOCK, result_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            rows = [r for r in rows if (r["case_id"], r["method"]) !=
                    (row["case_id"], row["method"])]
            rows.append(row)
            print(f"{row['case_id']} {row['method']}: {row['status']}", flush=True)
    return write_summary(rows, output_dir)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", type=Path, default=ROOT / "cases/cases.jsonl")
    ap.add_argument("--vault", type=Path, default=ROOT / "work/vault")
    ap.add_argument("--results", type=Path, default=ROOT / "results")
    ap.add_argument("--system", action="store_true", help="include the Lane A pipeline")
    ap.add_argument("--agent-verify", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    print(json.dumps(run(args.cases, args.vault, args.results,
                         args.system, args.workers, args.agent_verify), indent=2))


if __name__ == "__main__":
    main()
