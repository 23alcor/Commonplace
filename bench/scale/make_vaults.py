"""Procedurally grow mock_vault's shape to 50 / 500 / 5000 notes (no API calls, deterministic).

Same layout and conventions as scripts/make_mock_vault.py: hubs, courses, projects, concept notes,
sessions with `project:` frontmatter that log back into their course/project note, daily notes.
Realistic noise, on purpose:
  - near-duplicate names: "Kalman filter" / "Kalman filter basics" / "Advanced Kalman filter",
    "Homelab Server" / "Homelab Server v2"
  - overlapping terms: concepts and decision aspects are shared across many projects
  - stale sessions: earlier sessions on the same aspect whose decision was later superseded

Also writes <vault>/../<name>.meta.json with the structure (sessions, decisions, details) that
questions.py derives gold answers from.   Run: python -m bench.scale.make_vaults
"""
from __future__ import annotations

import datetime as dt
import json
import random
import shutil
from pathlib import Path

OUT = Path(__file__).resolve().parent / "vaults"
SIZES = {"v50": 50, "v500": 500, "v5000": 5000}

DOMAINS = {
    "ml": ["Gradient descent", "Regularization", "Cross-validation", "Bias-variance tradeoff", "Random forests",
           "Kalman filter", "Backpropagation", "Batch normalization", "Learning rate schedules", "Feature scaling",
           "Confusion matrix", "Transfer learning", "Dropout", "Precision and recall", "Embeddings"],
    "ee": ["Maxwell's equations", "Transmission lines", "Smith chart", "Impedance matching", "Op-amp feedback",
           "PWM", "Buck converter", "Fault detection", "Relay baseline", "Inverter control", "Phasors",
           "Bode plots", "Ground loops", "Decoupling capacitors", "ADC sampling"],
    "econ": ["Loss aversion", "Anchoring", "Nudges", "Present bias", "Mental accounting", "Sunk cost",
             "Framing effects", "Default effects", "Hyperbolic discounting", "Endowment effect"],
    "infra": ["Tailscale", "tmux", "Cron jobs", "Docker Compose", "Reverse proxy", "ZFS snapshots",
              "Systemd units", "SSH keys", "Backups 3-2-1", "Prometheus metrics", "DNS records", "WireGuard"],
    "iot": ["ESP32", "Soil moisture sensing", "MQTT", "Deep sleep", "I2C bus", "LoRa", "OTA updates",
            "Battery sizing", "Capacitive sensing", "Home Assistant"],
    "web": ["Web scraping", "SQLite", "Rate limiting", "REST pagination", "Caching headers", "OAuth",
            "Full-text search", "Background jobs", "Schema migrations", "Webhooks"],
    "career": ["Informational interviews", "System design interviews", "Behavioral questions", "Salary negotiation",
               "Resume bullets", "Take-home projects", "Referrals"],
}
QUALIFIERS = ["", " basics", " in practice", "Advanced ", " (lecture notes)", " cheat sheet", " pitfalls",
              " worked examples", " for embedded", " revisited", " deep dive", " exam review"]
PROJECT_THEMES = [
    ("Homelab Server", "infra"), ("Plant Watering Bot", "iot"), ("Recipe Scraper", "web"),
    ("Solar Microgrid Capstone", "ee"), ("Drone Telemetry Logger", "iot"), ("Budget Tracker App", "web"),
    ("Stock Sentiment Model", "ml"), ("Guitar Pedal Build", "ee"), ("Weather Station", "iot"),
    ("Habit Nudge App", "econ"), ("Media Server", "infra"), ("Resume Site", "web"), ("Fall Detector", "ml"),
    ("E-bike Battery Monitor", "ee"), ("Job Search", "career"), ("Garage Door Opener", "iot"),
    ("Price Anchoring Study", "econ"), ("Backup Pipeline", "infra"), ("Bird Call Classifier", "ml"),
    ("Mesh Chat Radio", "iot"),
]
PROJECT_SUFFIX = ["", " v2", " (old)", " Mk3", " rewrite", " prototype"]
COURSES = [("EECE 448", "Machine Learning", "ml"), ("PHYS 230", "Electromagnetics", "ee"),
           ("ECON 205", "Behavioral Economics", "econ"), ("EECE 410", "Capstone Design", "ee"),
           ("CMPE 320", "Operating Systems", "infra"), ("EECE 362", "Embedded Systems", "iot"),
           ("CMPE 340", "Web Systems", "web"), ("EECE 450", "Deep Learning", "ml"),
           ("EECE 331", "Power Electronics", "ee"), ("ECON 310", "Game Theory", "econ"),
           ("EECE 370", "Signals and Systems", "ee"), ("CMPE 410", "Distributed Systems", "infra")]
ASPECTS = ["the sampling rate", "the data pipeline", "error handling", "the test setup", "deployment",
           "the power budget", "the storage layer", "the alert thresholds", "the baseline model",
           "the enclosure", "logging", "the retry policy", "the evaluation metric", "the update schedule",
           "authentication", "the wiring harness", "the training split", "the cache policy"]
OPTIONS = ["a simple heuristic", "the ML model", "polling every 5 min", "event-driven updates", "SQLite",
           "Postgres", "a 3-cell pack", "USB power", "nightly cron", "a systemd timer", "k-fold CV",
           "a fixed holdout", "MQTT", "plain HTTP", "the cheaper sensor", "the calibrated sensor",
           "JSON logs", "plain text logs", "exponential backoff", "fixed retries"]
VERBS = ["Benchmarked", "Debugged", "Reviewed", "Sketched", "Refactored", "Measured", "Planned", "Tested",
         "Calibrated", "Documented"]
MEASURES = [("latency", "ms"), ("current draw", "mA"), ("accuracy", "%"), ("throughput", " req/s"),
            ("noise floor", " dBm"), ("ADC reading", " counts"), ("loss", ""), ("temperature", " C")]
CATS = ["study", "coding", "meeting", "lecture", "planning"]


def links(xs):
    return " · ".join(f"[[{x}]]" for x in xs)


def build(size: int, seed: int = 7) -> dict:
    rng = random.Random(seed * 1000 + size)
    n_daily = max(3, size // 20)
    n_courses = min(len(COURSES), max(3, size // 80))
    n_projects = max(4, min(len(PROJECT_THEMES) * len(PROJECT_SUFFIX), size // 35))
    n_projects = min(n_projects, len(PROJECT_THEMES) * len(PROJECT_SUFFIX))
    n_concepts = min(max(18, size // 4), sum(len(t) for t in DOMAINS.values()) * len(QUALIFIERS))
    n_hubs = 4
    n_sessions = max(12, size - n_daily - n_courses - n_projects - n_concepts - n_hubs - 1)

    # concepts: base terms first, then near-duplicate variants
    concepts, by_domain = [], {d: [] for d in DOMAINS}
    for q in QUALIFIERS:
        for d, terms in DOMAINS.items():
            for t in terms:
                name = (q + t) if q.endswith(" ") else (t + q)
                concepts.append((name, d, t))
    concepts = concepts[:n_concepts]
    for name, d, base in concepts:
        by_domain[d].append(name)

    projects = []
    for i in range(n_projects):
        theme, d = PROJECT_THEMES[i % len(PROJECT_THEMES)]
        name = theme + PROJECT_SUFFIX[i // len(PROJECT_THEMES)]
        projects.append({"name": name, "domain": d, "kind": "project",
                         "concepts": rng.sample(by_domain[d], min(4, len(by_domain[d]))),
                         "folder": f"30 Project and Hobby/31 Pet Projects/{theme}"
                         if theme != "Job Search" else "20 Work and Career/Job Search"})
    courses = []
    for code, subj, d in COURSES[:n_courses]:
        courses.append({"name": f"{code} {subj}", "code": code, "domain": d, "kind": "course",
                        "concepts": rng.sample(by_domain[d], min(4, len(by_domain[d]))),
                        "folder": f"10 Learning and Teaching/11 Academic/{code} {subj}"})
    owners = projects + courses

    start = dt.date(2025, 1, 6)
    sessions, used_titles, details = [], set(), set()
    for j in range(n_sessions):
        o = rng.choice(owners)
        date = start + dt.timedelta(days=int(j * 680 / n_sessions) + rng.randint(0, 3))
        aspect = rng.choice(ASPECTS)
        a, b = rng.sample(OPTIONS, 2)
        meas, unit = rng.choice(MEASURES)
        val = f"{rng.randint(11, 989)}{unit}"
        while (meas, val) in details:
            val = f"{rng.randint(11, 989)}{unit}"
        details.add((meas, val))
        verb = rng.choice(VERBS)
        title = f"{verb} {aspect.replace('the ', '')}"
        prefix = o.get("code") or o["name"]
        full = f"{date.isoformat()} {prefix} - {title}"
        k = 2
        while full in used_titles:
            full = f"{date.isoformat()} {prefix} - {title} {k}"
            k += 1
        used_titles.add(full)
        pool = o["concepts"] + rng.sample(by_domain[o["domain"]], min(2, len(by_domain[o["domain"]])))
        sessions.append({"title": full, "short": title, "date": date.isoformat(), "owner": o["name"],
                         "cat": rng.choice(CATS), "aspect": aspect, "decision": f"use {a} instead of {b}",
                         "concepts": sorted(set(rng.sample(pool, min(2, len(pool))))),
                         "detail": f"{meas} came out at {val}", "superseded": False})
    # stale: an earlier session on the same owner+aspect is superseded by the later one
    latest: dict = {}
    for s in sessions:
        key = (s["owner"], s["aspect"])
        if key in latest:
            latest[key]["superseded"] = True
        latest[key] = s
    return {"size": size, "concepts": concepts, "projects": projects, "courses": courses,
            "sessions": sessions, "n_daily": n_daily}


def write(world: dict, root: Path) -> int:
    shutil.rmtree(root, ignore_errors=True)

    def w(rel, text):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text.strip() + "\n", encoding="utf-8")

    projects, courses, sessions = world["projects"], world["courses"], world["sessions"]
    w("00 Home/Home.md", "---\ntype: home\ntags: [home]\n---\n# Home\n- [[School]] · [[Career]] · [[Projects]]")
    w("10 Learning and Teaching/11 Academic/School.md",
      "---\ntype: hub\ntags: [school]\n---\n# School\n" + "\n".join(f"- [[{c['name']}]]" for c in courses))
    w("30 Project and Hobby/Projects.md",
      "---\ntype: hub\ntags: [projects]\n---\n# Projects\n" + "\n".join(f"- [[{p['name']}]]" for p in projects))
    w("20 Work and Career/Career.md", "---\ntype: hub\ntags: [career]\n---\n# Career\n- [[Job Search]]")
    log: dict[str, list[str]] = {}
    for s in sessions:
        log.setdefault(s["owner"], []).append(f"- {s['date']} [[{s['title']}|{s['short']}]] ({s['cat']})")
    for o in projects + courses:
        parent = "Projects" if o["kind"] == "project" else "School"
        extra = f"code: {o['code']}\nterm: Fall 2026\n" if o["kind"] == "course" else "status: active\n"
        w(f"{o['folder']}/{o['name']}.md",
          f'---\ntype: {o["kind"]}\n{extra}parent: "[[{parent}]]"\ntags: [{o["kind"]}]\n---\n# {o["name"]}\n\n'
          f"Concepts: {links(o['concepts'])}\n\n## Log\n" + "\n".join(log.get(o["name"], [])))
    rng = random.Random(world["size"])
    for name, d, base in world["concepts"]:
        rel = f"Related: [[{base}]]\n" if name != base else ""
        w(f"40 Knowledge/Concepts/{name}.md",
          f"---\ntype: concept\ntags: [concept, {d}]\n---\n# {name}\n{rel}Notes on {base.lower()} ({d}). "
          f"Key idea #{rng.randint(1, 9)}; see course and project logs for where it came up.")
    for s in sessions:
        stale = " (superseded later)" if s["superseded"] else ""
        w(f"Sessions/{s['date'][:7]}/{s['title']}.md",
          f'---\ntype: session\ncategory: {s["cat"]}\nproject: "[[{s["owner"]}]]"\ndate: "{s["date"]}"\n'
          f'tags: [session, {s["cat"]}]\n---\n# {s["short"]}\n\n## Summary\n{s["short"]} for [[{s["owner"]}]], '
          f"focused on {s['aspect']}.\nDecision{stale}: {s['decision']} for {s['aspect']}.\n"
          f"Detail: {s['detail']}.\n\nConcepts: {links(s['concepts'])}\n\n## Next steps\n- [ ] Follow up next session")
    by_date: dict[str, list] = {}
    for s in sessions:
        by_date.setdefault(s["date"], []).append(s)
    for d in sorted(by_date)[-world["n_daily"]:]:
        w(f"00 Home/09 Journal/Daily Notes/{d}.md", f'---\ntype: daily\ndate: "{d}"\ntags: [daily]\n---\n# {d}\n## Summary\n'
          + "\n".join(f"- {s['short']} ([[{s['owner']}]])" for s in by_date[d]))
    return sum(1 for _ in root.rglob("*.md"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, size in SIZES.items():
        world = build(size)
        n = write(world, OUT / name)
        (OUT / f"{name}.meta.json").write_text(json.dumps(world, indent=0))
        print(f"{name}: {n} notes, {len(world['sessions'])} sessions, {len(world['projects'])} projects, "
              f"{len(world['concepts'])} concepts")


if __name__ == "__main__":
    main()
