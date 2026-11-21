"""LANE E. Per-step model benchmark: which Gemini 4 model should transcribe, and which should manage?

Same inputs, same prompts (mirrored from lane A's c2v/transcribe.py and c2v/manage.py), only the
model (and thinking level) changes. Every API result is cached in bench/cache/calls/, so reruns are
free and `--report` alone rebuilds RESULTS tables from cache.

    python -m bench.run_bench            # run what isn't cached yet, then print tables
    python -m bench.run_bench --report   # tables from cache only, no API calls

Steps
  transcribe: 4 of lane D's demo captures (voice, handwritten, screenshot, scanned PDF). Reference =
              the exact text each was rendered from (bench/references.json). Metrics: WER, key-term recall.
  manage:     10 notes held out of mock_vault (removed from the in-memory vault). The model gets the
              note's text (title + wikilink markup stripped) and a simulated *escalated* router output
              (low-confidence folder probabilities from keyword search; never sees the truth).
              Metrics: folder accuracy, link P/R/F1 (eval/score.py), verify pass rate (c2v/verify.py).
  thinking:   the alternate thinking level on each step's winner.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import random
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO))

from c2v.config import REPO_ROOT  # noqa: E402  (loads .env)
from c2v.schemas import NoteDraft  # noqa: E402
from c2v.vault import Vault, WIKILINK  # noqa: E402
from c2v.verify import ALLOWED_TYPES, verify_draft  # noqa: E402
from eval.score import score_case, summarize  # noqa: E402

CACHE = ROOT / "cache"
CALLS = CACHE / "calls"
MODELS = ["gemini-4-hydrogen", "gemini-4-neon", "gemini-4-argon", "gemini-4-carbon"]
# USD per 1M tokens, Standard paid tier, from https://ai.google.dev/gemini-api/docs/pricing (Nov 21 2026).
# Output price includes thinking tokens. Carbon/Argon are the pre-Dec-1 prices.
PRICE = {
    "gemini-4-hydrogen": (1.50, 7.50),
    "gemini-4-neon": (3.00, 15.00),
    "gemini-4-argon": (2.00, 10.00),
    "gemini-4-carbon": (2.00, 10.00),
}
PROD_THINKING = {"transcribe": "low", "manage": "medium"}  # what lane A ships
ALT_THINKING = {"low": "medium", "medium": "low"}
TRANSCRIBE_CAPTURES = ["01_voice_eece448_ridge.wav", "03_handwritten_anchoring.jpg",
                       "04_screenshot_job_search.jpg", "05_scanned_homelab_tmux.pdf"]
N_MANAGE = 10
N_MANAGE_ALT = 5  # thinking-level ablation on the manage winner: first 5 cases (keeps total ~65 calls)
TODAY = "2026-11-21"

# ---------------------------------------------------------------- prompts (mirror lane A) ------
TRANSCRIBE_PROMPT = """You transcribe a personal capture (voice memo, whiteboard photo, handwritten page,
screenshot, PDF or short video) for an Obsidian vault. Be faithful: write what is actually said or
shown, keep names/course codes/project names exactly, mark unreadable parts as [illegible].
Keep the original layout in the transcript: one line per written line or spoken sentence, using \\n.
Return: transcript, summary (1-3 sentences), key_terms, action_items, legibility (0-1), notes.
legibility is your honest read of input quality: 1.0 = crisp and complete, 0.5 = you guessed at a
lot, below 0.3 = mostly unreadable or inaudible."""

CAPTURE_SCHEMA = {
    "type": "object",
    "properties": {
        "transcript": {"type": "string"}, "summary": {"type": "string"},
        "key_terms": {"type": "array", "items": {"type": "string"}},
        "action_items": {"type": "array", "items": {"type": "string"}},
        "legibility": {"type": "number", "minimum": 0, "maximum": 1},
        "notes": {"type": "string"},
    },
    "required": ["transcript", "summary", "key_terms", "action_items", "legibility"],
}

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Short, specific note title. No / \\ : * ? \" < > | # ^ [ ]"},
        "folder": {"type": "string", "description": "Exactly one of the vault FOLDERS listed"},
        "frontmatter": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": sorted(ALLOWED_TYPES)},
                "created": {"type": "string"}, "source": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["type", "created", "source", "tags"],
        },
        "body": {"type": "string"},
        "links": {"type": "array", "items": {"type": "string"},
                  "description": "Exact titles of EXISTING notes to link; never invent titles"},
        "merge_into": {"type": "string"},
    },
    "required": ["title", "folder", "frontmatter", "body", "links", "merge_into"],
}

MANAGE_SYSTEM = """You are the vault manager for an Obsidian vault. You turn one transcribed capture into
one clean note that fits the vault. Rules:
- folder MUST be copied exactly from the FOLDERS list.
- links MUST be copied exactly from existing note titles (CANDIDATES or NOTES list). Link only notes
  that are genuinely related. Never invent a title.
- title must not already exist in the vault unless you set merge_into to that note.
- merge_into: an existing note title only when this capture is an update to that exact note; else "".
- frontmatter.type is one of: """ + ", ".join(sorted(ALLOWED_TYPES)) + """.
- body: clean markdown. Keep the transcript's facts, names and numbers; fix obvious transcription
  noise; turn action items into "- [ ]" checkboxes. Do not add a Related/links section (added later).
- The router's probabilities show where it was unsure; resolve that ambiguity using the vault."""

MIME = {".wav": "audio/wav", ".jpg": "image/jpeg", ".png": "image/png", ".pdf": "application/pdf"}
BLOCK = {".wav": "audio", ".jpg": "image", ".png": "image", ".pdf": "document"}


# ---------------------------------------------------------------- API + cache ------------------
_client = None
_lock = threading.Lock()


def client():
    global _client
    with _lock:  # one shared client; racing threads each built one and the losers got closed
        if _client is None:
            from google import genai
            _client = genai.Client()
    return _client


def cached_call(key: dict, build, offline: bool) -> dict | None:
    """Run one interactions.create, cache {output_text, latency_s, usage}. Backs off on 429/5xx."""
    h = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:16]
    path = CALLS / f"{key['step']}__{key['model']}__{key['thinking']}__{key['case']}__{h}.json"
    if path.exists():
        return json.loads(path.read_text())
    if offline:
        return None
    kw = build()
    delay = 5.0
    for attempt in range(6):
        t0 = time.perf_counter()
        try:
            r = client().interactions.create(**kw)
            lat = time.perf_counter() - t0
            u = r.usage
            rec = {"key": key, "output_text": r.output_text, "latency_s": round(lat, 3),
                   "usage": {"input": u.total_input_tokens or 0, "output": u.total_output_tokens or 0,
                             "thought": u.total_thought_tokens or 0}, "error": None}
            break
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if any(s in msg for s in ("429", "RESOURCE_EXHAUSTED", "500", "503", "UNAVAILABLE")) and attempt < 5:
                print(f"  backoff {delay:.0f}s ({key['model']} {key['case']}): {msg[:80]}", flush=True)
                time.sleep(delay)
                delay *= 2
                continue
            rec = {"key": key, "output_text": None, "latency_s": None, "usage": None, "error": msg[:500]}
            break
    if rec["error"] and "client has been closed" in rec["error"]:
        return rec  # local bug, not a model failure: don't cache it
    path.write_text(json.dumps(rec, indent=1))
    print(f"  {key['step']:10s} {key['model']:18s} {key['thinking']:6s} {key['case'][:40]:40s} "
          f"{rec['latency_s'] or 'ERR'}", flush=True)
    return rec


def cost_usd(model: str, usage: dict | None) -> float:
    if not usage:
        return 0.0
    pin, pout = PRICE[model]
    return (usage["input"] * pin + (usage["output"] + usage["thought"]) * pout) / 1e6


# ---------------------------------------------------------------- metrics ----------------------
def words(s: str) -> list[str]:
    s = s.lower().replace("$", " $ ").replace("—", " ").replace("→", " ")
    return re.findall(r"[a-z0-9$%]+", s)


def wer(ref: str, hyp: str) -> float:
    r, h = words(ref), words(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev = cur
    return d[len(h)] / max(1, len(r))


def term_recall(terms: list[str], hyp: str) -> float:
    hw = " " + " ".join(words(hyp)) + " "
    hits = [t for t in terms if " " + " ".join(words(t)) + " " in hw]
    return len(hits) / max(1, len(terms))


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


# ---------------------------------------------------------------- transcribe step --------------
def capture_path(name: str) -> Path:
    local = REPO_ROOT / "demo_captures" / name
    if local.exists():
        return local
    out = CACHE / "captures" / name
    if not out.exists():  # demo_captures lives on lane D's branch until merge
        out.parent.mkdir(parents=True, exist_ok=True)
        blob = subprocess.run(["git", "show", f"origin/lane-d:demo_captures/{name}"], cwd=REPO,
                              capture_output=True, check=True).stdout
        out.write_bytes(blob)
    return out


def transcribe_jobs(models: list[str], thinking: str):
    refs = json.loads((ROOT / "references.json").read_text())
    for name in TRANSCRIBE_CAPTURES:
        p = capture_path(name)
        for m in models:
            key = {"step": "transcribe", "model": m, "thinking": thinking, "case": name}

            def build(p=p, m=m):
                block = {"type": BLOCK[p.suffix], "mime_type": MIME[p.suffix],
                         "data": base64.b64encode(p.read_bytes()).decode("ascii")}
                return dict(model=m, input=[{"type": "text", "text": TRANSCRIBE_PROMPT}, block],
                            generation_config={"thinking_level": thinking},
                            response_format={"type": "text", "mime_type": "application/json",
                                             "schema": CAPTURE_SCHEMA})
            yield key, build, refs[name]


def score_transcribe(rec: dict, ref: dict) -> dict:
    if not rec or rec["error"]:
        return {"ok": False}
    try:
        t = json.loads(rec["output_text"])["transcript"]
    except Exception:  # noqa: BLE001
        return {"ok": False}
    return {"ok": True, "wer": wer(ref["text"], t), "term_recall": term_recall(ref["key_terms"], t)}


# ---------------------------------------------------------------- manage step ------------------
def strip_links(text: str) -> str:
    return re.sub(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]",
                  lambda m: (m.group(2) or m.group(1)).strip(), text)


def pick_manage_cases(vault: Vault, n: int = N_MANAGE, seed: int = 42) -> list[str]:
    """Notes with >=2 resolving outgoing links, stratified round-robin across top-level folders."""
    by_top: dict[str, list[str]] = {}
    for note in vault.notes.values():
        links = {vault.resolve(lk) for lk in note.links} - {None, note.title}
        if len(links) >= 2 and note.folder:
            by_top.setdefault(note.folder.split("/")[0], []).append(note.title)
    rng = random.Random(seed)
    for v in by_top.values():
        v.sort()
        rng.shuffle(v)
    picked, tops = [], sorted(by_top)
    while len(picked) < n and any(by_top.values()):
        for t in tops:
            if by_top[t] and len(picked) < n:
                picked.append(by_top[t].pop())
    return picked


def held_out_vault(title: str) -> tuple[Vault, dict]:
    v = Vault(REPO_ROOT / "mock_vault")
    note = v.notes[title]
    truth = {"title": title, "folder": note.folder,
             "links": sorted({v.resolve(lk) for lk in note.links} - {None, title})}
    del v.notes[title]
    v._alias_to_title = {a: t for a, t in v._alias_to_title.items() if t != title}
    body = re.sub(r"^#\s+.*\n?", "", note.body.strip(), count=1)  # drop the "# Title" heading
    truth["text"] = strip_links(body).strip()
    return v, truth


def simulated_router(v: Vault, text: str) -> str:
    """Escalated router stand-in: folder probabilities from keyword search, capped below 0.75."""
    hits = v.search(text, k=8)
    score: dict[str, float] = {}
    for rank, n in enumerate(hits):
        score[n.folder or "/"] = score.get(n.folder or "/", 0) + 1 / (rank + 1)
    score["other"] = 0.5
    tot = sum(score.values())
    probs = sorted(((k, s / tot) for k, s in score.items()), key=lambda kv: -kv[1])[:4]
    top = probs[0]
    return (f"note_type: other (conf 0.40; top: other=0.40, reference=0.30, project-update=0.30)\n"
            f"folder: {top[0]} (conf {min(top[1], 0.6):.2f}; top: "
            + ", ".join(f"{k}={p:.2f}" for k, p in probs) + ")\n"
            "merge_target: new (conf 0.55; top: new=0.55)\n"
            "router says: low confidence on folder; escalating to the vault manager")


def manage_prompt(v: Vault, truth: dict) -> str:
    text = truth["text"]
    cands = v.search(text, k=6)
    cand_text = "\n\n".join(f"### {n.title}  [{n.folder or '/'}]\n{n.body.strip()[:1500]}" for n in cands)
    return "\n\n".join([
        f"TODAY: {TODAY}",
        f"CAPTURE (text, legibility 1.00)\nSUMMARY: {text[:200]}\nKEY TERMS: \nACTION ITEMS: []\n"
        f"TRANSCRIBER NOTES: -\nTRANSCRIPT:\n{text}",
        f"ROUTER (calibrated probabilities):\n{simulated_router(v, text)}",
        f"VAULT MAP:\n{v.describe()}",
        f"CANDIDATES (full text of the most related notes):\n{cand_text or '(none)'}",
        "Write the NoteDraft.",
    ])


_VAULTS: dict[str, tuple[Vault, dict]] = {}


def manage_jobs(models: list[str], thinking: str, n: int = N_MANAGE):
    base = Vault(REPO_ROOT / "mock_vault")
    for title in pick_manage_cases(base)[:n]:
        if title not in _VAULTS:
            _VAULTS[title] = held_out_vault(title)
        v, truth = _VAULTS[title]
        prompt = manage_prompt(v, truth)
        for m in models:
            key = {"step": "manage", "model": m, "thinking": thinking, "case": title,
                   "prompt_sha": hashlib.sha256(prompt.encode()).hexdigest()[:12]}

            def build(m=m, prompt=prompt):
                return dict(model=m, input=prompt, system_instruction=MANAGE_SYSTEM,
                            generation_config={"thinking_level": thinking},
                            response_format={"type": "text", "mime_type": "application/json",
                                             "schema": DRAFT_SCHEMA})
            yield key, build, (v, truth)


def score_manage(rec: dict, ctx) -> dict:
    v, truth = ctx
    if not rec or rec["error"]:
        return {"ok": False}
    try:
        data = json.loads(rec["output_text"])
        data["merge_into"] = data.get("merge_into") or None
        draft = NoteDraft(**data)
    except Exception:  # noqa: BLE001
        return {"ok": False}
    rep = verify_draft(draft, v)
    pred_links = [v.resolve(lk) or lk for lk in draft.links]
    s = score_case(truth["title"], truth["folder"], truth["links"], draft.folder, pred_links, rep.ok)
    return {"ok": True, "score": s, "pred_folder": draft.folder, "pred_links": pred_links,
            "issues": [i.code for i in rep.issues]}


# ---------------------------------------------------------------- driver -----------------------
def run(jobs, offline: bool, workers: int = 4):
    jobs = list(jobs)
    with ThreadPoolExecutor(workers) as ex:
        recs = list(ex.map(lambda j: cached_call(j[0], j[1], offline), jobs))
    return [(j[0], r, j[2]) for j, r in zip(jobs, recs)]


def table_transcribe(rows) -> tuple[str, dict]:
    out = ["| Model | thinking | n ok | WER (lower better) | key-term recall | p50 latency s | p90 latency s | $ / capture |",
           "|---|---|---|---|---|---|---|---|"]
    agg = {}
    for (m, th) in dict.fromkeys((k["model"], k["thinking"]) for k, _, _ in rows):
        rs = [(r, score_transcribe(r, ref)) for k, r, ref in rows if (k["model"], k["thinking"]) == (m, th)]
        ok = [s for _, s in rs if s.get("ok")]
        lat = [r["latency_s"] for r, _ in rs if r and r["latency_s"]]
        cost = [cost_usd(m, r["usage"]) for r, _ in rs if r and r["usage"]]
        a = {"n": len(rs), "ok": len(ok),
             "wer": sum(s["wer"] for s in ok) / max(1, len(ok)),
             "recall": sum(s["term_recall"] for s in ok) / max(1, len(ok)),
             "p50": pct(lat, .5), "p90": pct(lat, .9), "cost": sum(cost) / max(1, len(cost))}
        agg[(m, th)] = a
        out.append(f"| {m} | {th} | {a['ok']}/{a['n']} | {a['wer']:.3f} | {a['recall']:.2f} | "
                   f"{a['p50']:.1f} | {a['p90']:.1f} | {a['cost']:.4f} |")
    return "\n".join(out), agg


def table_manage(rows) -> tuple[str, dict]:
    out = ["| Model | thinking | n ok | folder acc | link P | link R | link F1 | verify pass | p50 latency s | p90 latency s | $ / note |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    agg = {}
    for (m, th) in dict.fromkeys((k["model"], k["thinking"]) for k, _, _ in rows):
        rs = [(r, score_manage(r, ctx)) for k, r, ctx in rows if (k["model"], k["thinking"]) == (m, th)]
        # failed calls count as wrong folder / zero links / verify fail
        scores = [s["score"] if s.get("ok") else score_case("x", "truth", ["t"], "", [], False) for _, s in rs]
        su = summarize(scores)
        lat = [r["latency_s"] for r, _ in rs if r and r["latency_s"]]
        cost = [cost_usd(m, r["usage"]) for r, _ in rs if r and r["usage"]]
        a = {**su, "ok": sum(1 for _, s in rs if s.get("ok")), "p50": pct(lat, .5), "p90": pct(lat, .9),
             "cost": sum(cost) / max(1, len(cost))}
        agg[(m, th)] = a
        out.append(f"| {m} | {th} | {a['ok']}/{su['n']} | {su['folder_accuracy']:.2f} | {su['link_precision']:.2f} | "
                   f"{su['link_recall']:.2f} | {su['link_f1']:.2f} | {su['verify_pass_rate']:.2f} | "
                   f"{a['p50']:.1f} | {a['p90']:.1f} | {a['cost']:.4f} |")
    return "\n".join(out), agg


def per_case_manage(rows) -> str:
    out = ["| Case (held-out note) | truth folder | " + " | ".join(m.replace("gemini-4-", "") for m in MODELS) + " |",
           "|---|---|" + "---|" * len(MODELS)]
    cases = list(dict.fromkeys(k["case"] for k, _, _ in rows))
    for c in cases:
        cells, tf = [], ""
        for m in MODELS:
            hit = [(r, ctx) for k, r, ctx in rows if k["case"] == c and k["model"] == m
                   and k["thinking"] == PROD_THINKING["manage"]]
            if not hit:
                cells.append("-")
                continue
            r, ctx = hit[0]
            tf = ctx[1]["folder"]
            s = score_manage(r, ctx)
            cells.append("ERR" if not s.get("ok") else
                         f"{'✓' if s['score'].folder_correct else '✗'} F1 {s['score'].link_f1:.2f}")
        out.append(f"| {c} | {tf} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def winner(agg: dict, step: str) -> str:
    th = PROD_THINKING[step]
    cands = {m: a for (m, t), a in agg.items() if t == th}
    if step == "transcribe":
        return max(cands, key=lambda m: (cands[m]["ok"] / cands[m]["n"], round(cands[m]["recall"], 2), -cands[m]["wer"], -cands[m]["cost"]))
    return max(cands, key=lambda m: (cands[m]["ok"] / cands[m]["n"], round(cands[m]["folder_accuracy"] + cands[m]["link_f1"], 2),
                                     -cands[m]["cost"]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="cache only, no API calls")
    ap.add_argument("--step", choices=["transcribe", "manage", "all"], default="all")
    args = ap.parse_args(argv)
    CALLS.mkdir(parents=True, exist_ok=True)
    report = {}

    if args.step in ("transcribe", "all"):
        rows = run(transcribe_jobs(MODELS, PROD_THINKING["transcribe"]), args.report)
        _, agg = table_transcribe(rows)
        w = winner(agg, "transcribe")
        rows += run(transcribe_jobs([w], ALT_THINKING[PROD_THINKING["transcribe"]]), args.report)
        report["transcribe"], report["transcribe_agg"] = table_transcribe(rows)
        report["transcribe_winner"] = w
        print("\n## Transcribe\n" + report["transcribe"] + f"\nwinner: {w}")

    if args.step in ("manage", "all"):
        rows = run(manage_jobs(MODELS, PROD_THINKING["manage"]), args.report)
        _, agg = table_manage(rows)
        w = winner(agg, "manage")
        rows += run(manage_jobs([w], ALT_THINKING[PROD_THINKING["manage"]], N_MANAGE_ALT), args.report)
        t, agg = table_manage(rows)
        # apples-to-apples for the ablation: winner at prod thinking on the same first N_MANAGE_ALT cases
        alt_cases = set(list(dict.fromkeys(k["case"] for k, _, _ in rows))[:N_MANAGE_ALT])
        sub = [x for x in rows if x[0]["model"] == w and x[0]["case"] in alt_cases]
        t_sub, _ = table_manage(sub)
        report["manage"] = t
        report["manage_ablation"] = t_sub
        report["manage_cases"] = per_case_manage(rows)
        report["manage_winner"] = w
        print("\n## Manage\n" + t + f"\nwinner: {w}\n\n### thinking ablation (same {N_MANAGE_ALT} cases)\n"
              + t_sub + "\n\n### per case\n" + report["manage_cases"])

    n_calls = len(list(CALLS.glob("*.json")))
    total = 0.0
    for p in CALLS.glob("*.json"):
        r = json.loads(p.read_text())
        total += cost_usd(r["key"]["model"], r["usage"])
    print(f"\ncached calls: {n_calls}  total spend: ${total:.3f}  ({dt.datetime.now():%H:%M})")
    out = {k: (v[0] if isinstance(v, tuple) else v) for k, v in report.items() if not k.endswith("_agg")}
    (ROOT / "results.json").write_text(json.dumps({**out, "n_calls": n_calls, "total_usd": round(total, 4)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
