"""Backtest Module C: run the stock-norm screen as of 2025-08-31 (before the Sep-2025 scheme window)
and compare expiry claims in the following 12 months for WITHHOLD vs OK pairs."""
import json

import pandas as pd

from agent import data as d
from agent import reports as rp

AS_OF = "2025-08-31"
res = rp.scheme_screen(as_of=AS_OF)
df = pd.DataFrame(res["rows"])
c = d.claims()
nxt = c[(c.claim_date > AS_OF) & (c.claim_date <= "2026-08-31") & c.claim_type.isin(["Near expiry", "Expired"]) & (c.status != "Rejected")]
cl = nxt.groupby(["stockist_code", "sku_code"]).claim_value_inr.sum()
s = d.sales()
sep = s[(s.invoice_date >= "2025-09-22") & (s.invoice_date <= "2025-09-30") & (s.scheme_code != "")]
foc = (sep.free_qty * sep.pts_inr).groupby([sep.stockist_code, sep.sku_code]).sum()
df["claims_next12m"] = [cl.get((a, b), 0.0) for a, b in zip(df.stockist_code, df.sku_code)]
df["sep25_foc_inr"] = [foc.get((a, b), 0.0) for a, b in zip(df.stockist_code, df.sku_code)]
g = df.groupby("decision").agg(pairs=("sku_code", "size"), claims_next12m=("claims_next12m", "sum"), sep25_foc=("sep25_foc_inr", "sum"))
g["claims_per_pair"] = (g.claims_next12m / g.pairs).round(0)
print(g.to_string())
w = df[df.decision == "WITHHOLD"]
out = {"as_of": AS_OF, "pairs": len(df), "withhold_pairs": len(w), "share_withheld_pct": round(len(w) / len(df) * 100, 1),
       "claims_next12m_withhold_inr": round(w.claims_next12m.sum()), "claims_next12m_all_inr": round(df.claims_next12m.sum()),
       "share_of_claims_in_withhold_pct": round(w.claims_next12m.sum() / df.claims_next12m.sum() * 100, 1),
       "foc_saved_sep25_inr": round(w.sep25_foc_inr.sum())}
print(out)
F = json.load(open("analysis/findings.json"))
F["P2_backtest"] = out
json.dump(F, open("analysis/findings.json", "w"), indent=1, default=float)
