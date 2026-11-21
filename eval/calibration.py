"""Replay Decision 1 on held-out captures and plot confidence calibration.

The original comparison saved only path_taken. This replay stores routing answers
in ignored eval/work/ so the public report contains aggregate figures only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from eval.run_eval import ApiBudget, ClientProxy, ROOT, _fingerprint, load_jsonl

THRESHOLD = 0.75
TYPE_GOLD = {
    "h001": "meeting", "h002": "reference", "h003": "journal",
    "h004": "class", "h005": "other", "h006": "reference",
    "h007": "class", "h008": "reference", "h009": "class",
    "h010": "other", "h011": "reference", "h012": "meeting",
    "h013": "journal", "h014": "reference", "h015": "project-update",
}


def collect(cases_path: Path, vault_path: Path, output: Path, budget_path: Path,
            max_api_calls: int) -> list[dict]:
    from google import genai
    from c2v.route import route
    from c2v.transcribe import transcribe
    from c2v.vault import Vault

    cases = load_jsonl(cases_path)
    saved = {r["case_id"]: r for r in load_jsonl(output)}
    budget = ApiBudget(budget_path, max_api_calls)
    client = ClientProxy(genai.Client(), budget)
    beta_client = ClientProxy(genai.Client(http_options={"api_version": "v1beta"}), budget)
    vault = Vault(vault_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        cid = case["case_id"]
        fingerprint = _fingerprint(case)
        if cid in saved and saved[cid].get("fingerprint") == fingerprint:
            continue
        capture = transcribe(case["media_path"], client=client)
        routing = route(capture, vault, beta_client=beta_client, client=client)
        row = {"case_id": cid, "fingerprint": fingerprint,
               "routing": routing.model_dump(mode="json"),
               "capture_legibility": capture.legibility}
        with output.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row) + "\n")
        saved[cid] = row
        print(f"{cid}: routed; {budget.used}/{budget.limit} budget calls", flush=True)
    return [saved[c["case_id"]] for c in cases]


def analyze(cases_path: Path, routes_path: Path, results_path: Path) -> dict:
    cases = {c["case_id"]: c for c in load_jsonl(cases_path)}
    routes = {r["case_id"]: r for r in load_jsonl(routes_path)
              if r["case_id"] in cases and r.get("fingerprint") == _fingerprint(cases[r["case_id"]])}
    results = {r["case_id"]: r for r in load_jsonl(results_path)
               if r.get("method") == "system" and r.get("truth_folder") and
               r.get("case_id") in cases and r.get("fingerprint") == _fingerprint(cases[r["case_id"]])}
    if len(routes) != len(cases):
        raise ValueError(f"Only {len(routes)}/{len(cases)} route replays completed")
    answers = []
    case_rows = []
    for cid, case in cases.items():
        routing = routes[cid]["routing"]
        gold = {"note_type": TYPE_GOLD[cid], "folder": case["folder"], "merge_target": "new"}
        routed = [routing[k] for k in gold if routing.get(k)]
        for key, truth in gold.items():
            answer = routing.get(key)
            if answer is None:
                continue
            answers.append({"case_id": cid, "question": key,
                            "confidence": float(answer["confidence"]),
                            "was_correct": answer["choice"] == truth})
        minimum = min(a["confidence"] for a in routed)
        final = results.get(cid, {}).get("pred_folder")
        case_rows.append({"case_id": cid, "minimum_confidence": minimum,
                          "router_folder_correct": routing["folder"]["choice"] == case["folder"],
                          "final_folder_correct": final == case["folder"],
                          "actual_escalation": routing["escalate"]})
    bins = [(0.0, 0.5)] + [(i / 10, (i + 1) / 10) for i in range(5, 10)]
    bucket_rows = []
    for low, high in bins:
        group = [a for a in answers if low <= a["confidence"] < high or
                 (high == 1.0 and a["confidence"] == 1.0)]
        bucket_rows.append({"low": low, "high": high, "n": len(group),
                            "mean_confidence": sum(a["confidence"] for a in group) / len(group) if group else None,
                            "accuracy": sum(a["was_correct"] for a in group) / len(group) if group else None})
    ece = sum(b["n"] / len(answers) * abs(b["accuracy"] - b["mean_confidence"])
              for b in bucket_rows if b["n"])
    auto = [r for r in case_rows if r["minimum_confidence"] >= THRESHOLD]
    escalated = [r for r in case_rows if r["minimum_confidence"] < THRESHOLD]
    wrong_escalated = [r for r in escalated if not r["router_folder_correct"]]
    return {"n_cases": len(cases), "n_answers": len(answers), "bins": bucket_rows,
            "ece": ece,
            "auto": {"n": len(auto), "router_folder_accuracy": _accuracy(auto)},
            "escalated": {"n": len(escalated), "router_folder_accuracy": _accuracy(escalated)},
            "cross_run_folder_recovery": {
                "final_correct": sum(r["final_folder_correct"] for r in wrong_escalated),
                "replay_router_wrong": len(wrong_escalated)},
            "actual_escalations": sum(r["actual_escalation"] for r in case_rows),
            "answer_rows": answers}


def _accuracy(rows: list[dict]) -> float | None:
    return sum(r["router_folder_correct"] for r in rows) / len(rows) if rows else None


def chart(data: dict, path: Path) -> None:
    cache = ROOT / "work" / "matplotlib"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot([0, 1], [0, 1], color="gray", linestyle="--", label="Perfect calibration")
    occupied = [b for b in data["bins"] if b["n"]]
    ax.scatter([b["mean_confidence"] for b in occupied], [b["accuracy"] for b in occupied],
               s=[35 + 12 * b["n"] for b in occupied], color="#176b91", zorder=3)
    for b in occupied:
        ax.annotate(f"n={b['n']}", (b["mean_confidence"], b["accuracy"]),
                    xytext=(5, 7), textcoords="offset points", fontsize=9)
    ax.axvline(THRESHOLD, color="#b35a00", linestyle=":", label="Auto-file threshold 0.75")
    ax.set(xlim=(0, 1.03), ylim=(0, 1.05), xlabel="Mean stated confidence",
           ylabel="Observed answer accuracy", title="Decision 1 reliability (route replay)")
    ax.grid(alpha=0.2)
    ax.legend(loc="upper left")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def write_section(data: dict, summary_path: Path) -> None:
    lines = ["## Is Decision 1's confidence trustworthy?", "",
             "A separate route-only replay on the same 15 captures recorded all 45 Decision 1 "
             "answers (note type, folder, merge target). The original pipeline run saved only "
             "whether it escalated, so these confidence values are from a replay. "
             "Gold note types map the source note's frontmatter to the router's categories; "
             "all held-out notes have `new` as the merge target because their source notes "
             "were removed from the eval vault.", "",
             f"Expected calibration error (ECE): **{data['ece']:.1%}** across "
             f"{data['n_answers']} answers. Lower is better; zero is perfect. "
             "The model was overconfident in this small sample.", "",
             "| Confidence bin | Answers | Mean confidence | Accuracy |",
             "|---|---:|---:|---:|"]
    for b in data["bins"]:
        mean = f"{b['mean_confidence']:.1%}" if b["n"] else "—"
        accuracy = f"{b['accuracy']:.1%}" if b["n"] else "—"
        lines.append(f"| {b['low']:.1f}–{b['high']:.1f} | {b['n']} | {mean} | {accuracy} |")
    auto, esc = data["auto"], data["escalated"]
    lines += ["", f"At the 0.75 minimum-confidence threshold, **{auto['n']}/15** cases "
              "qualified for auto-file, so auto-file accuracy is undefined. "
              f"The other **{esc['n']}/15** escalated; their replay router folder accuracy "
              f"was **{esc['router_folder_accuracy']:.1%}**. The actual pipeline run also "
              f"escalated {data['actual_escalations']}/15 cases.", ""]
    recovery = data["cross_run_folder_recovery"]
    lines += [f"For **{recovery['final_correct']}/{recovery['replay_router_wrong']}** cases "
              "where the replay router chose the wrong folder, the original pipeline's final "
              "folder was correct. Because those decisions came from separate runs, this is "
              "only a cross-run comparison; the exact number Neon fixed in the original run "
              "cannot be recovered from its logs. With 15 cases and sparse high-confidence "
              "bins, this calibration estimate is preliminary.", "",
              "![Decision 1 reliability](calibration.png)", ""]
    prefix = summary_path.read_text(encoding="utf-8").split("## Is Decision 1's confidence trustworthy?")[0].rstrip()
    summary_path.write_text(prefix + "\n\n" + "\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=Path, default=ROOT / "cases/cases.jsonl")
    ap.add_argument("--vault", type=Path, default=ROOT / "work/vault")
    ap.add_argument("--routes", type=Path, default=ROOT / "work/calibration_routes.jsonl")
    ap.add_argument("--results", type=Path, default=ROOT / "results/results.jsonl")
    ap.add_argument("--max-api-calls", type=int, default=97)
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()
    if not args.report_only:
        collect(args.cases, args.vault, args.routes, ROOT / "results/api_calls.json",
                args.max_api_calls)
    data = analyze(args.cases, args.routes, args.results)
    chart(data, ROOT / "results/calibration.png")
    answers_path = ROOT / "work/calibration_answers.jsonl"
    answers_path.write_text("".join(json.dumps(row) + "\n" for row in data["answer_rows"]),
                            encoding="utf-8")
    write_section(data, ROOT / "results/summary.md")
    print(json.dumps({k: v for k, v in data.items() if k != "answer_rows"}, indent=2))


if __name__ == "__main__":
    main()
