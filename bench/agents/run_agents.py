"""LANE F. Agent benchmark: does an agent answer project questions better with get_context?

Same model, same question, same system prompt, same ~4000-token context budget. Only the source of
context changes:

  no_context    question only (the "re-explain it every time" baseline)
  context_file  a frozen, model-written CLAUDE.md that summarizes the whole vault (bench/agents/context_file.md)
  rag           top chunks by gemini-embedding-2 cosine, packed to the budget
  c2v           the agent gets a get_context(query, max_tokens) function tool (c2v.context) and decides
                what to ask for; native function calling, max 3 tool calls, total retrieved <= budget

Scoring: one gemini-4-neon (thinking low) judge call per question grades every arm's answer at once,
blind (shuffled letters), against the gold answer and the gold notes' text: correct / partial / wrong,
plus a "hallucinated a fact not in the vault" flag.

Every API call is cached in bench/agents/cache/, so reruns are free:
    python -m bench.agents.run_agents              # run what isn't cached, judge, write results
    python -m bench.agents.run_agents --report     # from cache only, no API calls
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
sys.path.insert(0, str(REPO))

from c2v.config import REPO_ROOT  # noqa: E402,F401  (loads .env)
from c2v.context import estimate_tokens, get_context  # noqa: E402
from c2v.vault import Vault  # noqa: E402

VAULT = ROOT / "work" / "vault"
CACHE = ROOT / "cache"
QUESTIONS = ROOT / "questions.json"
CONTEXT_FILE = ROOT / "context_file.md"
RESULTS = ROOT / "results.json"
BUDGET = 4000          # the spec'd budget; the whole vault is ~3.5k tokens, so it barely binds
TIGHT = 1500           # ~40% of the vault: a budget where choosing context actually matters
MAX_TOOL_CALLS = 3
JUDGE_MODEL = "gemini-4-neon"
EMB_MODEL, EMB_DIM, CHUNK_TOKENS = "gemini-embedding-2", 768, 300
ARMS = ["no_context", "context_file", "rag", "c2v"]
H, N = "gemini-4-hydrogen", "gemini-4-neon"
RUNS = ([(H, a, BUDGET) for a in ARMS] + [(H, a, TIGHT) for a in ARMS[1:]]
        + [(N, "no_context", BUDGET), (N, "c2v", BUDGET)])  # (model, arm, budget)
PRICE = {"gemini-4-hydrogen": (1.50, 7.50), "gemini-4-neon": (3.00, 15.00)}  # USD / 1M (same as bench/run_bench.py)

SYSTEM = """You are the user's assistant. They ask about their own courses, projects, job search and
notes. Answer in one or two sentences with the specific fact asked for (a date, a number, a name, a
decision). If the information you have does not contain the answer, say "I don't know" rather than
guessing."""

TOOL = {
    "type": "function",
    "name": "get_context",
    "description": ("Fetch the relevant slice of the user's Obsidian vault (notes about their courses, "
                    "projects, job search, sessions and concepts). Pass a project, course, person, "
                    "concept or question. Returns whole notes, linked notes first."),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to look up, e.g. a project or course name"},
            "max_tokens": {"type": "integer", "description": "Context budget for this call (default 2000)"},
        },
        "required": ["query"],
    },
}

_client = None
_lock = threading.Lock()
API_CALLS = {"n": 0}


def client():
    global _client
    with _lock:
        if _client is None:
            from google import genai
            _client = genai.Client()
    return _client


def _retry(fn):
    delay = 5.0
    for attempt in range(6):
        try:
            with _lock:
                API_CALLS["n"] += 1
            return fn()
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if attempt < 5 and any(s in msg for s in ("429", "RESOURCE_EXHAUSTED", "500", "503", "UNAVAILABLE")):
                print(f"  backoff {delay:.0f}s: {msg[:80]}", flush=True)
                time.sleep(delay)
                delay *= 2
                continue
            raise


def _cache_path(kind: str, key: dict) -> Path:
    h = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:16]
    return CACHE / kind / f"{key.get('model', '')}__{key.get('arm', '')}__{key.get('qid', '')}__{h}.json"


def _usage(r) -> dict:
    u = r.usage
    return {"input": u.total_input_tokens or 0, "output": u.total_output_tokens or 0,
            "thought": u.total_thought_tokens or 0}


def _add(a: dict, b: dict) -> dict:
    return {k: a.get(k, 0) + b.get(k, 0) for k in ("input", "output", "thought")}


def cost(model: str, u: dict) -> float:
    pin, pout = PRICE[model]
    return (u["input"] * pin + (u["output"] + u["thought"]) * pout) / 1e6


# ------------------------------------------------------------------ context sources ----------------
def vault_dump(v: Vault) -> str:
    parts = []
    for t in sorted(v.notes):
        n = v.notes[t]
        parts.append(f"=== {n.path.as_posix()}\n" + (v.root / n.path).read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def build_context_file(v: Vault, offline: bool, budget: int = BUDGET) -> str:
    """Generate the static CLAUDE.md once with Neon, then freeze it (never regenerated if present)."""
    path = CONTEXT_FILE if budget == BUDGET else ROOT / f"context_file_{budget}.md"
    if path.exists():
        return path.read_text()
    if offline:
        raise SystemExit("context_file.md missing; run without --report first")
    prompt = (f"Below is the user's entire Obsidian vault. Write the CLAUDE.md context file a careful "
              f"user would hand-write so an AI assistant knows their projects, courses, job search, "
              f"decisions, dates and numbers without asking. Keep it under {int(budget * 0.85)} tokens "
              f"(about {int(budget * 0.85 * 0.75)} words). Markdown, dense, no preamble.\n\n" + vault_dump(v))
    r = _retry(lambda: client().interactions.create(
        model=JUDGE_MODEL, input=prompt, generation_config={"thinking_level": "low"}))
    text = r.output_text.strip()
    path.write_text(text + "\n")
    print(f"  wrote {path.name}: {estimate_tokens(text)} tokens (vault is {estimate_tokens(vault_dump(v))})")
    return text


class RAG:
    def __init__(self, v: Vault, offline: bool):
        import numpy as np
        self.np = np
        self.chunks: list[tuple[str, str]] = []
        for t, n in sorted(v.notes.items()):
            text = (v.root / n.path).read_text(encoding="utf-8")
            for c in self._chunk(text):
                self.chunks.append((t, c))
        self.path = CACHE / "embeddings.json"
        self.vecs: dict[str, list[float]] = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.offline = offline
        docs = [f"title: {t} | text: {c}" for t, c in self.chunks]
        self.mat = self.embed(docs)

    @staticmethod
    def _chunk(text: str) -> list[str]:
        paras, out, cur = text.split("\n\n"), [], ""
        for p in paras:
            if cur and estimate_tokens(cur) + estimate_tokens(p) > CHUNK_TOKENS:
                out.append(cur)
                cur = ""
            cur = (cur + "\n\n" + p) if cur else p
            while estimate_tokens(cur) > CHUNK_TOKENS:
                out.append(cur[:CHUNK_TOKENS * 4])
                cur = cur[CHUNK_TOKENS * 4:]
        if cur.strip():
            out.append(cur)
        return out

    def embed(self, texts: list[str]):
        np = self.np
        key = lambda t: hashlib.sha256(t.encode()).hexdigest()[:24]  # noqa: E731
        todo = [t for t in dict.fromkeys(texts) if key(t) not in self.vecs]
        if todo and self.offline:
            raise SystemExit("embeddings not cached; run without --report")
        from google.genai import types
        for i in range(0, len(todo), 100):
            part = todo[i:i + 100]
            r = _retry(lambda: client().models.embed_content(
                model=EMB_MODEL, contents=[types.Content(parts=[types.Part(text=t)]) for t in part],
                config=types.EmbedContentConfig(output_dimensionality=EMB_DIM)))
            for t, e in zip(part, r.embeddings):
                vec = np.asarray(e.values, dtype=np.float32)
                self.vecs[key(t)] = (vec / (np.linalg.norm(vec) or 1)).round(5).tolist()
        if todo:
            CACHE.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.vecs))
        return np.array([self.vecs[key(t)] for t in texts], dtype=np.float32)

    def prepare_queries(self, qs: list[str]):
        self.embed([f"task: search result | query: {q}" for q in qs])

    def retrieve(self, q: str, budget: int) -> tuple[str, list[str], int]:
        qv = self.embed([f"task: search result | query: {q}"])[0]
        used, picked = 0, []
        for i in self.np.argsort(-(self.mat @ qv)):
            t, c = self.chunks[i]
            if used + estimate_tokens(c) > budget:
                continue
            used += estimate_tokens(c)
            picked.append((t, c))
        text = "\n\n".join(f"=== {t}\n{c}" for t, c in picked)
        return text, list(dict.fromkeys(t for t, _ in picked)), used


# ------------------------------------------------------------------ arms ---------------------------
def answer(model: str, arm: str, budget: int, q: dict, ctx: dict, offline: bool) -> dict | None:
    key = {"model": model, "arm": arm, "qid": q["id"], "question": q["question"], "system": SYSTEM,
           "budget": budget if arm != "no_context" else 0, "v": 2}
    if arm == "context_file":
        key["ctx"] = hashlib.sha256(ctx["context_file"][budget].encode()).hexdigest()[:12]
    path = _cache_path("answers", {**key, "arm": f"{arm}{budget}"})
    if path.exists():
        return json.loads(path.read_text())
    if offline:
        return None
    gen = {"thinking_level": "low"}
    t0 = time.perf_counter()
    rec = {"key": key, "tool_calls": [], "notes_seen": [], "context_tokens": 0, "error": None}
    try:
        if arm == "no_context":
            r = _retry(lambda: client().interactions.create(
                model=model, system_instruction=SYSTEM, input=q["question"], generation_config=gen))
            usage = _usage(r)
        elif arm == "context_file":
            inp = f"<context file=\"CLAUDE.md\">\n{ctx['context_file'][budget]}\n</context>\n\nQuestion: {q['question']}"
            rec["context_tokens"] = estimate_tokens(ctx["context_file"][budget])
            r = _retry(lambda: client().interactions.create(
                model=model, system_instruction=SYSTEM, input=inp, generation_config=gen))
            usage = _usage(r)
        elif arm == "rag":
            text, notes, used = ctx["rag"].retrieve(q["question"], budget)
            rec.update(context_tokens=used, notes_seen=notes)
            inp = f"<context source=\"vault search\">\n{text}\n</context>\n\nQuestion: {q['question']}"
            r = _retry(lambda: client().interactions.create(
                model=model, system_instruction=SYSTEM, input=inp, generation_config=gen))
            usage = _usage(r)
        elif arm == "c2v":
            vault, remaining = ctx["vault"], budget
            sys_c2v = SYSTEM + ("\nYou can call get_context to read the user's vault before answering. "
                                f"You may call it at most {MAX_TOOL_CALLS} times; your total context budget is "
                                f"{budget} tokens.")
            r = _retry(lambda: client().interactions.create(
                model=model, system_instruction=sys_c2v, input=q["question"], tools=[TOOL],
                generation_config=gen))
            usage = _usage(r)
            for _ in range(MAX_TOOL_CALLS + 1):
                calls = [s for s in (r.steps or []) if getattr(s, "type", None) == "function_call"]
                if not calls:
                    break
                results = []
                for c in calls:
                    if len(rec["tool_calls"]) >= MAX_TOOL_CALLS or remaining <= 0:
                        out = {"error": "tool budget exhausted; answer with what you have"}
                    else:
                        want = int(c.arguments.get("max_tokens") or 2000)
                        got = get_context(vault, str(c.arguments.get("query", "")), max(1, min(want, remaining)))
                        remaining -= got["tokens"]
                        rec["context_tokens"] += got["tokens"]
                        rec["notes_seen"] += [n["title"] for n in got["notes"]]
                        out = {"notes": [{"title": n["title"], "why": n["why"], "text": n["text"]}
                                         for n in got["notes"]], "truncated": got["truncated"]}
                    rec["tool_calls"].append({"args": dict(c.arguments),
                                              "notes": [n["title"] for n in out.get("notes", [])]})
                    results.append({"type": "function_result", "call_id": c.id, "name": c.name,
                                    "result": json.dumps(out)})
                prev = r.id
                r = _retry(lambda: client().interactions.create(
                    model=model, previous_interaction_id=prev, input=results, tools=[TOOL],
                    generation_config=gen))
                usage = _add(usage, _usage(r))
        else:
            raise ValueError(arm)
        rec.update(answer=(r.output_text or "").strip(), usage=usage)
    except Exception as e:  # noqa: BLE001
        rec.update(answer=None, usage={"input": 0, "output": 0, "thought": 0}, error=str(e)[:400])
    rec["latency_s"] = round(time.perf_counter() - t0, 3)
    rec["notes_seen"] = list(dict.fromkeys(rec["notes_seen"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=1))
    print(f"  {model:18s} {arm:12s} {budget:5d} {q['id']:4s} {rec['latency_s']:6.1f}s  "
          f"tools={len(rec['tool_calls'])} {(rec['answer'] or rec['error'] or '')[:70]!r}", flush=True)
    return rec


# ------------------------------------------------------------------ judge --------------------------
JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"grades": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "label": {"type": "string"},
            "verdict": {"type": "string", "enum": ["correct", "partial", "wrong"]},
            "hallucinated": {"type": "boolean"},
            "reason": {"type": "string"},
        },
        "required": ["label", "verdict", "hallucinated", "reason"]}}},
    "required": ["grades"],
}

JUDGE_PROMPT = """You grade answers to a question about a user's personal notes vault.
You get the question, the gold answer, the text of the gold notes, the FULL VAULT (every note), and
several candidate answers labelled with letters (their source is hidden). For EACH candidate:
- verdict: "correct" if it states the gold answer's key fact(s); "partial" if it gets some but not all
  of a multi-part answer, or is right but vague; "wrong" if it is incorrect, says it doesn't know, or
  doesn't answer.
- hallucinated: true if it asserts a specific fact about the user (name, date, number, decision,
  link, note, folder) that is not supported anywhere in the FULL VAULT and is not common general
  knowledge. Facts from vault notes other than the gold notes are fine if the vault supports them. "I don't know" is NOT a
  hallucination. Generic advice is not a hallucination; made-up specifics about the user are.
Return one grade per label."""


def judge(q: dict, answers: dict[str, str], gold_text: str, vault_text: str, offline: bool) -> dict | None:
    """answers: run_id -> answer text. Returns run_id -> grade."""
    runs = sorted(answers)
    rnd = random.Random(q["id"])
    order = runs[:]
    rnd.shuffle(order)
    labels = {chr(65 + i): rid for i, rid in enumerate(order)}
    key = {"judge": JUDGE_MODEL, "qid": q["id"], "gold": q["gold"],
           "answers": {lab: answers[rid] for lab, rid in labels.items()}, "v": 2,
           "vault": hashlib.sha256(vault_text.encode()).hexdigest()[:12]}
    path = _cache_path("judge", {**key, "model": JUDGE_MODEL, "arm": "judge"})
    if path.exists():
        rec = json.loads(path.read_text())
    elif offline:
        return None
    else:
        cands = "\n\n".join(f"[{lab}] {answers[rid] or '(no answer)'}" for lab, rid in labels.items())
        inp = (f"QUESTION: {q['question']}\n\nGOLD ANSWER: {q['gold']}\n\nGOLD NOTES:\n{gold_text}\n\n"
               f"FULL VAULT:\n{vault_text}\n\nCANDIDATE ANSWERS:\n{cands}")
        r = _retry(lambda: client().interactions.create(
            model=JUDGE_MODEL, system_instruction=JUDGE_PROMPT, input=inp,
            generation_config={"thinking_level": "low"},
            response_format={"type": "text", "mime_type": "application/json", "schema": JUDGE_SCHEMA}))
        rec = {"key": key, "labels": labels, "grades": json.loads(r.output_text)["grades"], "usage": _usage(r)}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, indent=1))
        print(f"  judged {q['id']}", flush=True)
    by_label = {g["label"].strip("[] "): g for g in rec["grades"]}
    return {rid: by_label.get(lab) for lab, rid in rec["labels"].items()}


# ------------------------------------------------------------------ main ---------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="cache only, no API calls")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--answers-only", action="store_true", help="skip judging")
    args = ap.parse_args(argv)
    offline = args.report

    v = Vault(VAULT)
    qs = json.loads(QUESTIONS.read_text())
    ctx = {"vault": v, "context_file": {b: build_context_file(v, offline, b) for b in (BUDGET, TIGHT)}}
    ctx["rag"] = RAG(v, offline)
    if not offline:
        ctx["rag"].prepare_queries([q["question"] for q in qs])

    jobs = [(m, a, b, q) for m, a, b in RUNS for q in qs]
    with ThreadPoolExecutor(args.workers) as ex:
        recs = list(ex.map(lambda j: answer(*j, ctx, offline), jobs))
    by = {(j[0], j[1], j[2], j[3]["id"]): r for j, r in zip(jobs, recs)}
    if args.answers_only:
        print(f"answers done; API calls this run: {API_CALLS['n']}")
        return 0

    def gold_text(q):
        out = []
        for t in q["gold_notes"]:
            title = v.resolve(t)
            if title:
                out.append(f"=== {title}\n" + (v.root / v.notes[title].path).read_text(encoding="utf-8"))
        return "\n\n".join(out)

    def judge_q(q):
        ans = {f"{m}|{a}|{b}": (by[(m, a, b, q["id"])] or {}).get("answer") or "" for m, a, b in RUNS}
        return judge(q, ans, gold_text(q), vault_dump(v), offline)

    with ThreadPoolExecutor(args.workers) as ex:
        grades = dict(zip([q["id"] for q in qs], ex.map(judge_q, qs)))

    rows = []
    for q in qs:
        for m, a, b in RUNS:
            r = by[(m, a, b, q["id"])]
            g = (grades.get(q["id"]) or {}).get(f"{m}|{a}|{b}")
            if not r or not g:
                continue
            rows.append({"qid": q["id"], "kind": q["kind"], "model": m, "arm": a, "budget": b if a != "no_context" else 0,
                         "verdict": g["verdict"], "hallucinated": g["hallucinated"], "reason": g["reason"],
                         "answer": r["answer"], "error": r["error"], "context_tokens": r["context_tokens"],
                         "tool_calls": len(r["tool_calls"]), "tool_queries": [c["args"].get("query") for c in r["tool_calls"]],
                         "notes_seen": r["notes_seen"], "gold_notes": q["gold_notes"],
                         "latency_s": r["latency_s"], "usage": r["usage"], "cost_usd": cost(m, r["usage"])})
    RESULTS.write_text(json.dumps(rows, indent=1))
    print(f"\n{len(rows)} graded rows -> {RESULTS.relative_to(REPO)}; API calls this run: {API_CALLS['n']}")
    from bench.agents.report import report
    report(rows, qs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
