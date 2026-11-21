"""Run every email and a few claims through the graph (code-only mode). Run: python -m analysis.13_graph_smoke"""
import json
import time

from agent import data as d
from agent.graph import mermaid, run

t = time.time()
d.load_all()
print("load", round(time.time() - t, 1))
open("analysis/graph.mmd", "w").write(mermaid())
for eid in sorted(d.emails().index):
    r = run("email", {"email_id": eid})
    lines = [(x["line"].get("batch_no"), x["line"].get("qty"), x["decision"]) for x in (r["results"] or [])]
    print(f"{eid} {str(r['decision']):13s} {r['fields']['intent']:6s} {lines} flags={r['flags']} :: {r['explanation'][:160]}")
for cn in ["CLM-2605-04488", "CLM-2505-00135", "CLM-9999-00000"]:
    r = run("claim", {"claim_no": cn})
    print(cn, r["decision"], r["explanation"][:200])
r = run("month", {"month": "2026-09"})
print(json.dumps(r["report"]["summary"]), r["meter"])
