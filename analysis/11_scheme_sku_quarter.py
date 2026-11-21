"""Claim-back rate of scheme lots by SKU and by scheme quarter: which SKUs should not be in which circular?"""
import json

import pandas as pd

from agent import data as d

pd.set_option("display.width", 250)
s, c, sk, b = d.sales(), d.claims(), d.skus(), d.batches()
sch = s[(s.scheme_code != "") & (s.batch_no != "")].copy()
sch["qtr"] = sch.scheme_code.str[3:9]  # FY25Q3
sch["packs"] = sch.invoiced_qty + sch.free_qty
# attribute expiry claims on (stockist,batch) pro-rata to the scheme lots of that pair
pair_tot = s[s.batch_no != ""].assign(p=lambda x: x.invoiced_qty + x.free_qty).groupby(["stockist_code", "batch_no"]).p.sum()
ex = c[c.claim_type.isin(["Near expiry", "Expired"]) & (c.status != "Rejected")].groupby(["stockist_code", "batch_no"]).qty_claimed.sum()
sch["pair_total"] = [pair_tot.get(k, 0) for k in zip(sch.stockist_code, sch.batch_no)]
sch["pair_claim"] = [ex.get(k, 0) for k in zip(sch.stockist_code, sch.batch_no)]
sch["claimed_attr"] = sch.pair_claim * sch.packs / sch.pair_total
sch["exp"] = sch.batch_no.map(b.expiry_date)
done = sch[sch.exp <= "2026-09-30"]  # outcome known
done = done.assign(ta=done.sku_code.map(sk.therapy_area))
t = done.groupby(["sku_code"]).agg(ta=("ta", "first"), packs=("packs", "sum"), claimed=("claimed_attr", "sum"))
t["claim_rate_pct"] = (t.claimed / t.packs * 100).round(1)
print("scheme-lot claim-back rate by SKU (batches already expired):")
print(t.sort_values("claim_rate_pct", ascending=False).to_string())
q = done.groupby(["qtr", "ta"]).agg(packs=("packs", "sum"), claimed=("claimed_attr", "sum"))
q["rate"] = (q.claimed / q.packs * 100).round(1)
print("\nby scheme quarter x therapy area (claim-back %):")
print(q.rate.unstack().to_string())
# non-scheme baseline by SKU
ns = s[(s.scheme_code == "") & (s.batch_no != "")].copy()
ns["packs"] = ns.invoiced_qty + ns.free_qty
ns["pair_total"] = [pair_tot.get(k, 0) for k in zip(ns.stockist_code, ns.batch_no)]
ns["pair_claim"] = [ex.get(k, 0) for k in zip(ns.stockist_code, ns.batch_no)]
ns["claimed_attr"] = ns.pair_claim * ns.packs / ns.pair_total
ns = ns[ns.batch_no.map(b.expiry_date) <= "2026-09-30"]
nb = ns.groupby("sku_code").agg(packs=("packs", "sum"), claimed=("claimed_attr", "sum"))
t["non_scheme_rate_pct"] = (nb.claimed / nb.packs * 100).round(2).reindex(t.index)
t["pts"] = sk.pts_inr.reindex(t.index)
t.to_csv("analysis/scheme_sku_rates.csv")
print("\n", t[["ta", "claim_rate_pct", "non_scheme_rate_pct"]].sort_values("claim_rate_pct", ascending=False).to_string())
