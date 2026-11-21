"""Resumeable baseline/system eval with aggregate, public-safe reports."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
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


class BudgetExceeded(RuntimeError):
    pass


class ApiBudget:
    """Persist request attempts so restarts and rate-limit retries respect the cap."""
    def __init__(self, path: Path, limit: int):
        self.path, self.limit = path, limit
        self.lock = threading.Lock()
        self.used = json.loads(path.read_text())["used"] if path.exists() else 0

    def consume(self) -> None:
        with self.lock:
            if self.used >= self.limit:
                raise BudgetExceeded(f"API budget reached: {self.used}/{self.limit}")
            self.used += 1
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"used": self.used, "limit": self.limit}) + "\n")


def _rate_limited(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(token in message for token in ("429", "resource_exhausted", "rate limit", "quota exceeded", "503"))


class EndpointProxy:
    def __init__(self, endpoint, budget: ApiBudget):
        self.endpoint, self.budget = endpoint, budget

    def __getattr__(self, name):
        value = getattr(self.endpoint, name)
        if name not in {"create", "upload"} or not callable(value):
            return value
        def call(*args, **kwargs):
            for attempt in range(4):
                self.budget.consume()
                try:
                    return value(*args, **kwargs)
                except Exception as exc:
                    if not _rate_limited(exc) or attempt == 3:
                        raise
                    time.sleep(min(16, 2 ** (attempt + 1)) + random.uniform(0, 0.5))
        return call


class ClientProxy:
    def __init__(self, client, budget: ApiBudget):
        self.client, self.budget = client, budget

    def __getattr__(self, name):
        value = getattr(self.client, name)
        return EndpointProxy(value, self.budget) if name in {"interactions", "decisions", "files"} else value


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _fingerprint(case: dict) -> str:
    digest = hashlib.sha256()
    digest.update(Path(case["media_path"]).read_bytes())
    digest.update(json.dumps({key: case[key] for key in ("folder", "links")},
                             sort_keys=True).encode())
    return digest.hexdigest()[:16]


def run_one(case: dict, method: str, vault_path: Path, agent_verify: bool = False,
            client=None, beta_client=None) -> dict:
    start = time.monotonic()
    row = {"case_id": case["case_id"], "method": method,
           "media_kind": case["media_kind"], "difficulty": case.get("difficulty", {}),
           "fingerprint": case["fingerprint"]}
    try:
        vault = Vault(vault_path)
        if method == "baseline":
            draft = run_baseline(case["media_path"], vault, client=client)
            path_taken = "single_call"
            report = verify_draft(draft, vault)  # scoring only; baseline has no repair step
        else:
            from c2v.pipeline import file_capture
            result = file_capture(case["media_path"], vault, dry_run=True,
                                  agent_verify=agent_verify, client=client,
                                  beta_client=beta_client)
            draft, report, path_taken = result.draft, result.verify, result.path_taken
            row["routing"] = result.routing.model_dump(mode="json")
            row["capture_legibility"] = result.capture.legibility
        score = score_case(case["case_id"], case["folder"], case["links"],
                           draft.folder, draft.links, report.ok)
        row.update({"status": "ok", "score": vars(score), "path_taken": path_taken,
                    "latency_s": round(time.monotonic() - start, 3),
                    "issue_codes": [issue.code for issue in report.issues],
                    "pred_folder": draft.folder, "pred_links": draft.links,
                    "truth_folder": case["folder"], "truth_links": case["links"]})
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
                    "escalation_rate": (sum(r["path_taken"] in {"escalated", "agent_fixed"} for r in good) /
                                        len(good)) if good and any(r["method"] == "system" for r in good) else None,
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
    cache = ROOT / "work" / "matplotlib"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    buckets = defaultdict(list)
    for row in rows:
        if row["status"] != "ok":
            continue
        knobs = row.get("difficulty", {})
        bucket = knobs.get("difficulty") or ("audio" if "snr_db" in knobs else "visual")
        buckets[(row["method"], bucket)].append(row["score"]["folder_correct"])
    if not buckets:
        return
    labels = [label for label in ("clean", "noisy", "hard", "audio", "visual")
              if any((method, label) in buckets for method, _ in buckets)]
    methods = sorted({key[0] for key in buckets})
    fig, ax = plt.subplots(figsize=(8, 4.5))
    width = 0.35
    for i, method in enumerate(methods):
        vals = [statistics.mean(buckets[(method, label)]) if buckets[(method, label)] else float("nan")
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


def write_summary(rows: list[dict], output_dir: Path, dataset: str = "unspecified") -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    methods = sorted({row["method"] for row in rows})
    summary = {method: _aggregate([r for r in rows if r["method"] == method])
               for method in methods}
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = ["# Held-out evaluation", "", f"Dataset: {dataset}. "
             "Scores include completed cases only; errors are reported separately.", "",
             "| Method | Done / attempted | Folder acc | Link P | Link R | Link F1 | Verify pass | Escalation | Median latency |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for method in methods:
        m = summary[method]
        latency = f"{m['median_latency_s']:.2f}s" if m["median_latency_s"] is not None else "—"
        escalation = f"{m['escalation_rate']:.1%}" if m["escalation_rate"] is not None else "—"
        lines.append(f"| {method} | {m['completed']} / {m['attempted']} | {m['folder_accuracy']:.1%} | "
                     f"{m['link_precision']:.1%} | {m['link_recall']:.1%} | {m['link_f1']:.1%} | "
                     f"{m['verify_pass_rate']:.1%} | {escalation} | {latency} |")
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
            label = knobs.get("difficulty") or ("audio" if "snr_db" in knobs else "visual")
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
        system: bool = False, workers: int = 6, agent_verify: bool = False,
        rerun: bool = False, max_api_calls: int = 97,
        system_only: bool = False) -> dict:
    cases = load_jsonl(cases_path)
    if not cases:
        raise ValueError(f"No cases in {cases_path}; run python -m eval.build_heldout first")
    if not vault_path.is_dir():
        raise FileNotFoundError(vault_path)
    if agent_verify:
        raise ValueError("Managed Agent calls cannot be counted by this budgeted runner; use local verify/repair")
    for case in cases:
        case["fingerprint"] = _fingerprint(case)
    output_dir.mkdir(parents=True, exist_ok=True)
    budget = ApiBudget(output_dir / "api_calls.json", max_api_calls)
    from google import genai
    client = ClientProxy(genai.Client(), budget)
    beta_client = ClientProxy(genai.Client(http_options={"api_version": "v1beta"}), budget)
    result_path = output_dir / "results.jsonl"
    existing = load_jsonl(result_path)
    fingerprints = {case["case_id"]: case["fingerprint"] for case in cases}
    latest = {(r["case_id"], r["method"]): r for r in existing
              if r["case_id"] in fingerprints and
              r.get("fingerprint") == fingerprints[r["case_id"]]}
    rows = list(latest.values())
    done = set() if rerun else {(r["case_id"], r["method"]) for r in rows if r["status"] == "ok"}
    methods = ["system"] if system_only else (["baseline", "system"] if system else ["baseline"])
    tasks = [(case, method) for case in cases for method in methods
             if (case["case_id"], method) not in done]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_one, case, method, vault_path, agent_verify, client, beta_client)
                   for case, method in tasks]
        for future in as_completed(futures):
            row = future.result()
            with WRITE_LOCK, result_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            rows = [r for r in rows if (r["case_id"], r["method"]) !=
                    (row["case_id"], row["method"])]
            rows.append(row)
            print(f"{row['case_id']} {row['method']}: {row['status']}", flush=True)
    summary = write_summary(rows, output_dir, cases[0].get("dataset", "unspecified"))
    print(f"API calls: {budget.used}/{budget.limit}")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", type=Path, default=ROOT / "cases/cases.jsonl")
    ap.add_argument("--vault", type=Path, default=ROOT / "work/vault")
    ap.add_argument("--results", type=Path, default=ROOT / "results")
    ap.add_argument("--system", action="store_true", help="include the Lane A pipeline")
    ap.add_argument("--system-only", action="store_true", help="run only the pipeline, preserving baseline results")
    ap.add_argument("--agent-verify", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--rerun", action="store_true", help="rerun completed cases after a prompt change")
    ap.add_argument("--max-api-calls", type=int, default=97,
                    help="persistent API attempt cap; leaves room for three TTS calls")
    args = ap.parse_args()
    print(json.dumps(run(args.cases, args.vault, args.results,
                         args.system, args.workers, args.agent_verify, args.rerun,
                         args.max_api_calls, args.system_only), indent=2))


if __name__ == "__main__":
    main()
