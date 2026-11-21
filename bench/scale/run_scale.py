"""Scale benchmark: RAG vs keyword vs get_context on 50 / 500 / 5000-note vaults, same 4000-token budget.

    python -m bench.scale.make_vaults && python -m bench.scale.questions
    python -m bench.scale.run_scale [--systems rag,keyword,get_context]

RAG: notes chunked to <=500 tokens (paragraph-packed), embedded once with gemini-embedding-2 (768-d,
documented prompt prefixes for retrieval), top chunks by cosine until the budget. Embeddings are
cached in bench/cache/embeddings/ keyed by text hash, so each chunk is embedded exactly once.
keyword: c2v.vault.Vault.search ranking, whole notes until the budget.
get_context: c2v.context.get_context (lane C). If it isn't merged yet, it is loaded from origin/lane-c.
Tokens are estimated as chars/4 for every system (same rule get_context uses).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))

from c2v.config import REPO_ROOT  # noqa: E402,F401  (loads .env)
from c2v.vault import Vault  # noqa: E402

VAULTS = HERE / "vaults"
EMB_DIR = REPO / "bench" / "cache" / "embeddings"
RESULTS = HERE / "results"
EMB_MODEL, EMB_DIM = "gemini-embedding-2", 768
EMB_PRICE = 0.20  # USD / 1M input tokens, https://ai.google.dev/gemini-api/docs/pricing
BUDGET = 4000
CHUNK_TOKENS = 500
SIZES = ["v50", "v500", "v5000"]


def toks(s: str) -> int:
    return len(s) // 4


# ------------------------------------------------------------------ embedding cache ---------------
class EmbCache:
    def __init__(self):
        EMB_DIR.mkdir(parents=True, exist_ok=True)
        self.path = EMB_DIR / f"{EMB_MODEL}_{EMB_DIM}.npz"
        self.vecs: dict[str, np.ndarray] = {}
        self.meta_path = EMB_DIR / "query_latency.json"
        self.qlat: dict[str, float] = json.loads(self.meta_path.read_text()) if self.meta_path.exists() else {}
        self.embedded_tokens = 0
        if self.path.exists():
            z = np.load(self.path)
            self.vecs = dict(zip(z["keys"].tolist(), z["vecs"].astype(np.float32)))

    def save(self):
        keys = list(self.vecs)
        np.savez(self.path, keys=np.array(keys), vecs=np.stack([self.vecs[k] for k in keys]).astype(np.float16))
        self.meta_path.write_text(json.dumps(self.qlat))

    @staticmethod
    def key(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:24]

    def embed(self, texts: list[str], batch: int = 100) -> np.ndarray:
        from google.genai import types
        todo = [t for t in dict.fromkeys(texts) if self.key(t) not in self.vecs]
        client = _client()
        for i in range(0, len(todo), batch):
            part = todo[i:i + batch]
            delay = 5.0
            for attempt in range(7):
                try:
                    r = client.models.embed_content(
                        model=EMB_MODEL, contents=[types.Content(parts=[types.Part(text=t)]) for t in part],
                        config=types.EmbedContentConfig(output_dimensionality=EMB_DIM))
                    break
                except Exception as e:  # noqa: BLE001
                    if attempt < 6 and any(s in str(e) for s in ("429", "RESOURCE_EXHAUSTED", "500", "503")):
                        print(f"  backoff {delay:.0f}s: {str(e)[:80]}", flush=True)
                        time.sleep(delay)
                        delay *= 2
                        continue
                    raise
            for t, e in zip(part, r.embeddings):
                v = np.asarray(e.values, dtype=np.float32)
                self.vecs[self.key(t)] = v / (np.linalg.norm(v) or 1)
            self.embedded_tokens += sum(toks(t) for t in part)
            if (i // batch) % 10 == 9:
                print(f"  embedded {i + len(part)}/{len(todo)}", flush=True)
                self.save()
        if todo:
            self.save()
        return np.stack([self.vecs[self.key(t)] for t in texts])

    def query(self, q: str) -> tuple[np.ndarray, float]:
        text = f"task: search result | query: {q}"
        k = self.key(text)
        if k not in self.vecs:
            t0 = time.perf_counter()
            self.embed([text])
            self.qlat[k] = time.perf_counter() - t0
        return self.vecs[k], self.qlat.get(k, float("nan"))


_c = None


def _client():
    global _c
    if _c is None:
        from google import genai
        _c = genai.Client()
    return _c


# ------------------------------------------------------------------ systems -----------------------
def note_text(v: Vault, title: str) -> str:
    return (v.root / v.notes[title].path).read_text(encoding="utf-8")


def chunk_note(title: str, text: str) -> list[str]:
    paras, chunks, cur = text.split("\n\n"), [], ""
    for p in paras:
        if cur and toks(cur) + toks(p) > CHUNK_TOKENS:
            chunks.append(cur)
            cur = ""
        cur = (cur + "\n\n" + p) if cur else p
        while toks(cur) > CHUNK_TOKENS:
            chunks.append(cur[:CHUNK_TOKENS * 4])
            cur = cur[CHUNK_TOKENS * 4:]
    if cur.strip():
        chunks.append(cur)
    return chunks


class RAG:
    name = "rag"

    def __init__(self, v: Vault, emb: EmbCache):
        self.v, self.emb = v, emb
        self.chunks: list[tuple[str, str]] = []
        for t in v.notes:
            for c in chunk_note(t, note_text(v, t)):
                self.chunks.append((t, c))
        docs = [f"title: {t} | text: {c}" for t, c in self.chunks]
        self.mat = emb.embed(docs)

    def run(self, q: str, budget: int) -> dict:
        qv, qlat = self.emb.query(q)
        t0 = time.perf_counter()
        order = np.argsort(-(self.mat @ qv))
        used, notes = 0, []
        for i in order:
            t, c = self.chunks[i]
            if used + toks(c) > budget:
                if budget - used < 50:
                    break
                continue
            used += toks(c)
            notes.append(t)
        return {"notes": list(dict.fromkeys(notes)), "tokens": used,
                "latency_s": time.perf_counter() - t0 + qlat}


class Keyword:
    name = "keyword"

    def __init__(self, v: Vault, emb=None):
        self.v = v

    def run(self, q: str, budget: int) -> dict:
        t0 = time.perf_counter()
        used, notes = 0, []
        for n in self.v.search(q, k=400):
            tk = toks(note_text(self.v, n.title))
            if used + tk > budget:
                if budget - used < 50:
                    break
                continue
            used += tk
            notes.append(n.title)
        return {"notes": notes, "tokens": used, "latency_s": time.perf_counter() - t0}


def load_get_context():
    try:
        from c2v.context import get_context
        return get_context, "c2v.context (merged)"
    except ImportError:
        pass
    src = subprocess.run(["git", "show", "origin/lane-c:c2v/context.py"], cwd=REPO, capture_output=True)
    if src.returncode != 0:
        return None, "unavailable"
    sha = subprocess.run(["git", "rev-parse", "--short", "origin/lane-c"], cwd=REPO, capture_output=True,
                         text=True).stdout.strip()
    tmp = REPO / "bench" / "cache" / "lane_c_context.py"
    tmp.write_bytes(src.stdout)
    spec = importlib.util.spec_from_file_location("c2v._lane_c_context", tmp,
                                                  submodule_search_locations=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "c2v"  # so its relative imports (from .vault import Vault) resolve
    spec.loader.exec_module(mod)
    return mod.get_context, f"origin/lane-c@{sha}"


class GetContext:
    name = "get_context"
    fn = None

    def __init__(self, v: Vault, emb=None):
        self.v = v

    def run(self, q: str, budget: int) -> dict:
        t0 = time.perf_counter()
        out = type(self).fn(self.v, q, max_tokens=budget)
        lat = time.perf_counter() - t0
        notes = [n["title"] for n in out["notes"]]
        used = sum(toks(n.get("text", "")) for n in out["notes"])
        return {"notes": list(dict.fromkeys(notes)), "tokens": used, "latency_s": lat}


# ------------------------------------------------------------------ driver ------------------------
def score(gold: list[str], got: list[str]) -> tuple[float, float]:
    g, p = {x.lower() for x in gold}, {x.lower() for x in got}
    tp = len(g & p)
    return tp / len(g), (tp / len(p) if p else 0.0)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default="rag,keyword,get_context")
    ap.add_argument("--sizes", default=",".join(SIZES))
    args = ap.parse_args(argv)
    systems = {"rag": RAG, "keyword": Keyword, "get_context": GetContext}
    wanted = args.systems.split(",")
    if "get_context" in wanted:
        GetContext.fn, src = load_get_context()
        print("get_context source:", src)
        if GetContext.fn is None:
            wanted.remove("get_context")
    emb = EmbCache()
    RESULTS.mkdir(exist_ok=True)
    rows = []
    for size in args.sizes.split(","):
        v = Vault(VAULTS / size)
        qs = json.loads((VAULTS / f"{size}.questions.json").read_text())
        for sname in wanted:
            sys_ = systems[sname](v, emb)
            for q in qs:
                r = sys_.run(q["q"], BUDGET)
                rec, prec = score(q["gold"], r["notes"])
                rows.append({"size": size, "n_notes": len(v.notes), "system": sname, "id": q["id"],
                             "kind": q["kind"], "recall": rec, "precision": prec, "tokens": r["tokens"],
                             "n_returned": len(r["notes"]), "latency_s": r["latency_s"],
                             "gold": q["gold"], "returned": r["notes"][:40]})
            print(f"{size:6s} {sname:12s} done", flush=True)
    emb.save()
    out = RESULTS / f"rows_{'_'.join(wanted)}.jsonl"
    out.write_text("\n".join(json.dumps(r) for r in rows))
    print(f"embedded {emb.embedded_tokens} new tokens this run (~${emb.embedded_tokens * EMB_PRICE / 1e6:.3f})")
    print(summary_table(rows))
    return 0


def summary_table(rows: list[dict], by_kind: bool = False) -> str:
    import statistics as st
    keyf = (lambda r: (r["size"], r["system"], r["kind"])) if by_kind else (lambda r: (r["size"], r["system"]))
    groups: dict = {}
    for r in rows:
        groups.setdefault(keyf(r), []).append(r)
    hdr = "| vault | system |" + (" kind |" if by_kind else "") + \
        " n q | recall | precision | tokens | notes returned | p50 latency ms |"
    lines = [hdr, "|" + "---|" * (hdr.count("|") - 1)]
    for k, rs in groups.items():
        lat = sorted(x["latency_s"] for x in rs)
        lines.append(f"| {rs[0]['n_notes']} | {k[1]} |" + (f" {k[2]} |" if by_kind else "") +
                     f" {len(rs)} | {st.mean(x['recall'] for x in rs):.2f} | {st.mean(x['precision'] for x in rs):.2f} |"
                     f" {st.mean(x['tokens'] for x in rs):.0f} | {st.mean(x['n_returned'] for x in rs):.1f} |"
                     f" {1000 * lat[len(lat) // 2]:.1f} |")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
