"""Smoke-run the modules and store their headline numbers. Run: python -m analysis.12_modules_smoke"""
import json
import time

from agent import reports as rp
from agent import tools as T

t = time.time()
cc = rp.circular_check()
print("circular check", round(time.time() - t, 1), "s")
print(json.dumps(cc["summary"], indent=1))
for r in cc["rows"]:
    print(r["sku_code"], r.get("decision"), r.get("scheme_claimback_pct"), r.get("non_scheme_claimback_pct"), r.get("foc_cost_l12m_inr"), r.get("excess_returns_l12m_inr"))
print("watchlist top 3:", cc["watchlist"][:3])
t = time.time()
rb = rp.rebalance()
print("\nrebalance", round(time.time() - t, 1), "s  total", rb["total_value_inr"], "moves", len(rb["moves"]))
print(rb["cnf_cover"]); print(rb["fefo"]); print(rb["allocation"])
print(rb["moves"][:3])
for ln in [
    {"claim_no": "CLM-2605-04488", "stockist_code": "STK0025", "batch_no": "F2440122", "qty": 272, "claim_type": "Near expiry", "claim_date": "2026-05-12", "cnf_code": "CF-N01"},
    {"stockist_code": "STK0117", "batch_no": "L2400579", "qty": 38, "claim_type": "Near expiry", "claim_date": "2026-10-16", "invoice_ref": "INV/S01/2507/044588"},
]:
    r = T.check_claim_line(ln)
    print("\n", r["decision"], r["value_inr"]); [print("  ", c["status"], c["check"], c["detail"]) for c in r["checks"]]
F = json.load(open("analysis/findings.json"))
F["module_C_circular_check"] = cc["summary"]
F["module_B_rebalance_now"] = {"snapshot": rb["snapshot_date"], "moves": len(rb["moves"]), "value_inr": rb["total_value_inr"]}
json.dump(F, open("analysis/findings.json", "w"), indent=1, default=float)
