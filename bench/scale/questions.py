"""~30 questions per vault size, each with a gold note set derived from the vault's structure.

Four kinds (gold = titles of notes a good context for the question must contain):
  decision  "What did I decide about <aspect> for <project>?" -> the latest session on that aspect + the
            project note. Older, superseded sessions on the same aspect (and other projects' sessions on
            the same aspect) are the distractors.
  roundup   "Give me everything about <concept>." -> the concept + every note that links to it
            (sessions, courses, projects, near-duplicate variants). Only concepts with 2-8 backlinks.
  status    "What's the latest on <project>?" -> project note + its 2 most recent sessions.
  keyword   vague keyword-style lookup of a unique detail ("latency 269ms") -> that one session.
            Similarity search should do well here; ~1/3 of the set, so the test is fair to RAG.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from c2v.vault import Vault

VAULTS = Path(__file__).resolve().parent / "vaults"
MIX = {"decision": 7, "roundup": 7, "status": 6, "keyword": 10}


def backlinks(v: Vault) -> dict[str, set[str]]:
    bl: dict[str, set[str]] = {}
    for n in v.notes.values():
        for lk in n.links:
            t = v.resolve(lk)
            if t and t != n.title:
                bl.setdefault(t, set()).add(n.title)
    return bl


def make_questions(name: str, seed: int = 11) -> list[dict]:
    v = Vault(VAULTS / name)
    world = json.loads((VAULTS / f"{name}.meta.json").read_text())
    rng = random.Random(seed)
    sessions = world["sessions"]
    owners = world["projects"] + world["courses"]
    bl = backlinks(v)
    qs: list[dict] = []

    # decision: prefer aspects that also have a superseded session (stale distractor in the same project)
    stale_keys = {(s["owner"], s["aspect"]) for s in sessions if s["superseded"]}
    live = [s for s in sessions if not s["superseded"]]
    rng.shuffle(live)
    live.sort(key=lambda s: (s["owner"], s["aspect"]) not in stale_keys)  # stable: stale-backed first
    seen = set()
    for s in live:
        if sum(q["kind"] == "decision" for q in qs) >= MIX["decision"]:
            break
        if s["owner"] in seen:
            continue
        seen.add(s["owner"])
        qs.append({"kind": "decision", "q": f"What did I decide about {s['aspect']} for {s['owner']}?",
                   "gold": sorted({s["title"], s["owner"]})})

    concepts = [c[0] for c in world["concepts"] if 2 <= len(bl.get(c[0], ())) <= 8]
    for c in rng.sample(concepts, min(MIX["roundup"], len(concepts))):
        qs.append({"kind": "roundup", "q": f"Give me everything about {c}.", "gold": sorted({c} | bl[c])})

    with_sessions = [o for o in owners if sum(s["owner"] == o["name"] for s in sessions) >= 2]
    for o in rng.sample(with_sessions, min(MIX["status"], len(with_sessions))):
        mine = sorted((s for s in sessions if s["owner"] == o["name"]), key=lambda s: (s["date"], s["title"]))
        qs.append({"kind": "status", "q": f"What's the latest on {o['name']}?",
                   "gold": sorted({o["name"]} | {s["title"] for s in mine[-2:]})})

    for s in rng.sample(sessions, min(MIX["keyword"], len(sessions))):
        meas, val = s["detail"].split(" came out at ")
        qs.append({"kind": "keyword", "q": f"{meas} {val}?", "gold": [s["title"]]})

    for i, q in enumerate(qs):
        missing = [g for g in q["gold"] if g not in v.notes]
        assert not missing, (name, q, missing)
        q["id"] = f"{name}-{i:02d}"
    return qs


def main() -> None:
    for name in ["v50", "v500", "v5000"]:
        qs = make_questions(name)
        (VAULTS / f"{name}.questions.json").write_text(json.dumps(qs, indent=1))
        kinds = {k: sum(q["kind"] == k for q in qs) for k in MIX}
        print(name, len(qs), kinds, "mean gold", round(sum(len(q["gold"]) for q in qs) / len(qs), 1))
        for q in qs[:: max(1, len(qs) // 4)]:
            print("   ", q["q"], "->", q["gold"][:3], "..." if len(q["gold"]) > 3 else "")


if __name__ == "__main__":
    main()
