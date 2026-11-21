import json, subprocess
import os; V = os.path.dirname(os.path.abspath(__file__))
data = json.load(open(f"{V}/results.json"))
html = open(f"{V}/cards2.html").read()
for k, v in data.items():
    html = html.replace(f"__{k}__", str(v))
open(f"{V}/cards2_built.html", "w").write(html)
cards = {"hook": 7.6, "lossy": 8.0, "title": 6.6, "twoai": 9.4, "results": 13.6, "end": 5.6}
procs = [subprocess.Popen(["node", f"{V}/cards.js", "cards2_built.html", c, str(s)]) for c, s in cards.items()]
for p in procs: p.wait()
print("cards ok")
