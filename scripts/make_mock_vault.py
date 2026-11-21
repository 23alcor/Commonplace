"""Generate mock_vault/: a synthetic vault shaped like a real personal Obsidian vault.

Folder layout and frontmatter conventions mirror a real PARA-style vault (Home, Learning,
Work, Projects, Sessions, concept notes, daily notes). Every name, course, project and
event here is invented. Safe to commit.  Run: python scripts/make_mock_vault.py
"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent / "mock_vault"

COURSES = {
    "EECE 448 Machine Learning": ("EECE 448", ["Gradient descent", "Regularization", "Cross-validation", "Bias-variance tradeoff"]),
    "PHYS 230 Electromagnetics": ("PHYS 230", ["Maxwell's equations", "Transmission lines", "Smith chart"]),
    "ECON 205 Behavioral Economics": ("ECON 205", ["Loss aversion", "Anchoring", "Nudges"]),
}
PROJECTS = {
    "Homelab Server": ("30 Project and Hobby/31 Pet Projects/Homelab", ["Tailscale", "tmux", "Cron jobs"]),
    "Plant Watering Bot": ("30 Project and Hobby/31 Pet Projects/Plant Watering Bot", ["ESP32", "Soil moisture sensing", "MQTT"]),
    "Recipe Scraper": ("30 Project and Hobby/31 Pet Projects/Recipe Scraper", ["Web scraping", "SQLite"]),
    "Capture to Vault": ("30 Project and Hobby/31 Pet Projects/Capture to Vault", ["Context management", "Decisions API", "Managed Agents"]),
    "Solar Microgrid Capstone": ("10 Learning and Teaching/11 Academic/EECE 410 Capstone Design", ["Fault detection", "Relay baseline", "Inverter control"]),
}
SESSIONS = [
    ("2026-11-10", "EECE 448", "Ridge vs lasso on housing data", "study", "EECE 448 Machine Learning", ["Regularization", "Cross-validation"]),
    ("2026-11-11", "PHYS 230", "Smith chart practice set", "study", "PHYS 230 Electromagnetics", ["Smith chart", "Transmission lines"]),
    ("2026-11-12", "Plant Watering Bot", "Calibrated soil sensor", "coding", "Plant Watering Bot", ["Soil moisture sensing", "ESP32"]),
    ("2026-11-12", "Capstone", "Agreed on relay baseline", "meeting", "Solar Microgrid Capstone", ["Relay baseline", "Fault detection"]),
    ("2026-11-13", "ECON 205", "Anchoring lecture", "lecture", "ECON 205 Behavioral Economics", ["Anchoring", "Loss aversion"]),
    ("2026-11-14", "Homelab", "Moved cron jobs off laptop", "coding", "Homelab Server", ["Cron jobs", "tmux"]),
    ("2026-11-15", "Career", "Weekly application review", "planning", "Job Search", ["Informational interviews"]),
    ("2026-11-16", "Recipe Scraper", "Dedupe recipes by URL", "coding", "Recipe Scraper", ["SQLite", "Web scraping"]),
    ("2026-11-17", "EECE 448", "Bias-variance office hours", "meeting", "EECE 448 Machine Learning", ["Bias-variance tradeoff"]),
    ("2026-11-18", "Capstone", "Inverter fault sim results", "coding", "Solar Microgrid Capstone", ["Inverter control", "Fault detection"]),
    ("2026-11-19", "Career", "Mock interview, system design", "study", "Job Search", ["System design interviews"]),
    ("2026-11-20", "Homelab", "Tailscale ACL cleanup", "coding", "Homelab Server", ["Tailscale"]),
]
CONCEPT_BLURBS = {
    "Gradient descent": "Iteratively step against the gradient of the loss. Learning rate sets step size.",
    "Regularization": "Penalize model complexity (L2 ridge, L1 lasso) to reduce overfitting.",
    "Cross-validation": "Estimate generalization by rotating which fold is held out.",
    "Bias-variance tradeoff": "Simpler models underfit (bias); flexible ones overfit (variance).",
    "Maxwell's equations": "Four equations relating electric and magnetic fields to charges and currents.",
    "Transmission lines": "Lines long relative to wavelength; characteristic impedance and reflections matter.",
    "Smith chart": "Graphical tool for impedance matching on transmission lines.",
    "Loss aversion": "Losses feel about twice as bad as equal gains feel good.",
    "Anchoring": "Estimates drift toward an initial reference number, even an irrelevant one.",
    "Nudges": "Changes to choice architecture that steer behavior without removing options.",
    "Tailscale": "WireGuard-based mesh VPN; gives every device a stable private address.",
    "tmux": "Terminal multiplexer; sessions survive SSH disconnects.",
    "Cron jobs": "Scheduled commands; crontab syntax is minute hour day month weekday.",
    "ESP32": "Cheap Wi-Fi + Bluetooth microcontroller with ADC pins.",
    "Soil moisture sensing": "Capacitive probes read dielectric change; calibrate dry vs saturated.",
    "MQTT": "Lightweight pub/sub protocol for IoT devices.",
    "Web scraping": "Fetch pages and extract structured data; respect robots.txt.",
    "SQLite": "Single-file SQL database; good default for small apps.",
    "Fault detection": "Classify abnormal current/voltage events fast enough to trip protection.",
    "Relay baseline": "Conventional overcurrent relay logic used as the comparison for ML detectors.",
    "Inverter control": "Grid-following inverters sync to grid voltage; behavior during faults differs from generators.",
    "Informational interviews": "Short chats with people in a target role to learn, not to ask for a job.",
    "System design interviews": "Open-ended architecture questions: requirements, scale, tradeoffs.",
    "Context management": "Keeping an AI's working context filed, linked and current so any model can retrieve it.",
    "Decisions API": "Gemini API that answers choice/yes-no questions with calibrated probabilities instead of text.",
    "Managed Agents": "Agents that run in a provider-hosted sandbox, executing code and checking their own work.",
}

def w(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n", encoding="utf-8")

def links(xs): return " · ".join(f"[[{x}]]" for x in xs)

def main():
    shutil.rmtree(ROOT, ignore_errors=True)
    w("00 Home/Home.md", """---
type: home
tags: [home]
---
# Home
- [[School]] · [[Career]] · [[Projects]]
- Daily notes live in 00 Home/09 Journal/Daily Notes. Sessions live in Sessions/.""")
    w("00 Home/01 About Me/About Me.md", """---
type: profile
tags: [about]
---
# About Me
Fictional demo owner: senior electrical engineering student who builds side projects and is job hunting.
See [[School]], [[Career]], [[Projects]].""")
    w("10 Learning and Teaching/11 Academic/School.md", "---\ntype: hub\ntags: [school]\n---\n# School\n" + "\n".join(f"- [[{c}]]" for c in list(COURSES) + ["EECE 410 Capstone Design"]))
    w("10 Learning and Teaching/11 Academic/EECE 410 Capstone Design/EECE 410 Capstone Design.md",
      '---\ntype: course\ncode: EECE 410\nterm: Fall 2026\nparent: "[[School]]"\ntags: [course]\n---\n# EECE 410 Capstone Design\nTeam project: [[Solar Microgrid Capstone]].\n\n## Log\n')
    for name, (code, concepts) in COURSES.items():
        w(f"10 Learning and Teaching/11 Academic/{name}/{name}.md",
          f'---\ntype: course\ncode: {code}\nterm: Fall 2026\nparent: "[[School]]"\ntags: [course]\n---\n# {name}\n\n## Key concepts\n{links(concepts)}\n\n## Log\n')
    w("30 Project and Hobby/Projects.md", "---\ntype: hub\ntags: [projects]\n---\n# Projects\n" + "\n".join(f"- [[{p}]]" for p in PROJECTS))
    for name, (folder, concepts) in PROJECTS.items():
        w(f"{folder}/{name}.md", f'---\ntype: project\nstatus: active\nparent: "[[Projects]]"\ntags: [project]\n---\n# {name}\n\nConcepts: {links(concepts)}\n\n## Open loops\n- [ ] Next milestone TBD\n\n## Log\n')
    w("20 Work and Career/Career.md", "---\ntype: hub\ntags: [career]\n---\n# Career\n- [[Job Search]]\n- [[Interview Prep]]")
    w("20 Work and Career/Job Search/Job Search.md", '---\ntype: project\nstatus: active\nparent: "[[Career]]"\ntags: [project, career]\n---\n# Job Search\nPipeline of applications to embedded / ML roles. See [[Interview Prep]].\n\n## Log\n')
    w("20 Work and Career/Job Search/Interview Prep.md", '---\ntype: reference\nparent: "[[Career]]"\ntags: [career]\n---\n# Interview Prep\n' + links(["System design interviews", "Informational interviews"]))
    for c, blurb in CONCEPT_BLURBS.items():
        w(f"40 Knowledge/Concepts/{c}.md", f"---\ntype: concept\ntags: [concept]\n---\n# {c}\n{blurb}")
    for date, prefix, title, cat, project, concepts in SESSIONS:
        full = f"{date} {prefix} - {title}"
        w(f"Sessions/2026-11/{full}.md", f"""---
type: session
category: {cat}
project: "[[{project}]]"
date: "{date}"
tags: [session, {cat}]
---
# {title}

## Summary
{title}. Worked on [[{project}]].

Concepts: {links(concepts)}

## Next steps
- [ ] Follow up next session""")
        # append to the hub log, like the real vault's course/project logs
        for p in ROOT.rglob(f"{project}.md"):
            p.write_text(p.read_text() + f"- {date} [[{full}|{title}]] ({cat})\n")
    for d, wd in [("2026-11-18", "Wednesday"), ("2026-11-19", "Thursday"), ("2026-11-20", "Friday")]:
        today = [s for s in SESSIONS if s[0] == d]
        w(f"00 Home/09 Journal/Daily Notes/{d}.md", f'---\ntype: daily\ndate: "{d}"\ntags: [daily]\n---\n# {wd}, November {d[-2:]}, 2026\n## Summary\n' +
          "\n".join(f"- {s[2]} ([[{s[4]}]])" for s in today))
    print(f"wrote {sum(1 for _ in ROOT.rglob('*.md'))} notes to {ROOT}")

if __name__ == "__main__":
    main()
