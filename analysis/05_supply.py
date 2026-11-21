"""H4 schemes, H5 allocation, H6 FEFO, H7 CFA expiry risk. Run: python -m analysis.05_supply"""
import numpy as np
import pandas as pd

from agent import data as d
from analysis_helpers import fq

pd.set_option("display.width", 220)
s, st, sk, b = d.sales().copy(), d.stock().copy(), d.skus(), d.batches()
c = pd.read_pickle("analysis/claims_flagged.pkl")
s["q"] = fq(s.invoice_date)
s["month"] = s.invoice_date.dt.to_period("M")
s["on_scheme"] = s.scheme_code != ""

# ---------------- H4: scheme phasing and claim rate by purchase type
s["day"] = s.invoice_date.dt.day
s["qtr_last_month"] = s.invoice_date.dt.month.isin([3, 6, 9, 12])
lastwin = s.qtr_last_month & (s.day >= 22)
print("share of quarter primary (value) invoiced in scheme window 22nd-end of qtr month, by FY quarter:")
print((s[lastwin].groupby("q").net_value_inr.sum() / s.groupby("q").net_value_inr.sum() * 100).round(1).to_dict())
sold = s[s.batch_no != ""]
buy = sold.groupby(["stockist_code", "batch_no"]).agg(packs=("invoiced_qty", "sum"), free=("free_qty", "sum"),
                                                     scheme_packs=("invoiced_qty", lambda x: x[sold.loc[x.index, "on_scheme"]].sum()))
buy["total"] = buy.packs + buy.free
buy["scheme_share"] = (buy.scheme_packs / buy.packs).fillna(0)
exp = c[c.claim_type.isin(["Near expiry", "Expired"]) & (c.status != "Rejected")]
claimed = exp.groupby(["stockist_code", "batch_no"]).qty_claimed.sum()
buy["claimed"] = claimed.reindex(buy.index).fillna(0)
buy["bucket"] = pd.cut(buy.scheme_share, [-0.01, 0.0, 0.5, 1.0], labels=["no scheme", "partly scheme", "mostly scheme"])
# only batches already past expiry by data end (complete outcome)
done = buy.join(b.expiry_date, on="batch_no")
done = done[done.expiry_date <= "2026-09-30"]
r = done.groupby("bucket", observed=True).agg(pairs=("total", "size"), bought=("total", "sum"), claimed=("claimed", "sum"))
r["claim_rate_pct"] = (r.claimed / r.bought * 100).round(2)
print("\nexpired batches: claim rate by how the stockist bought the batch\n", r.to_string())
# value of claims on scheme-bought lots (credited expiry claims)
exp = exp.join(buy.scheme_share, on=["stockist_code", "batch_no"])
exp["value_x_scheme"] = exp.value * exp.scheme_share.fillna(0)
print("expiry claims value attributable to scheme-bought packs (pro rata), INR cr by FY:",
      (exp.groupby(exp.claim_date.dt.year + (exp.claim_date.dt.month >= 4)).value_x_scheme.sum() / 1e7).round(3).to_dict())
print("expiry claim value by therapy area last 12m (cr):",
      (exp[exp.claim_date >= "2025-10-01"].groupby(exp.sku_code.map(sk.therapy_area)).value.sum() / 1e7).round(3).to_dict())
tier = {"A": "QS-FY25Q1-A SKUs", "B": "B"}
scheme_skus = set(s.loc[s.scheme_code.str.endswith("-A"), "sku_code"]) | set(s.loc[s.scheme_code.str.endswith("-B"), "sku_code"])
e12 = exp[exp.claim_date >= "2025-10-01"]
print("last-12m expiry claim value: scheme SKUs", round(e12[e12.sku_code.isin(scheme_skus)].value.sum() / 1e7, 3),
      "non-scheme SKUs", round(e12[~e12.sku_code.isin(scheme_skus)].value.sum() / 1e7, 3), "| #scheme skus", len(scheme_skus))
s12 = s[s.invoice_date >= "2025-10-01"]
print("last-12m primary gross: scheme SKUs", round((s12[s12.sku_code.isin(scheme_skus)].invoiced_qty * s12.pts_inr).sum() / 1e7, 2),
      "non-scheme", round((s12[~s12.sku_code.isin(scheme_skus)].invoiced_qty * s12.pts_inr).sum() / 1e7, 2))
# FOC above cap
s["gross"] = s.invoiced_qty * s.pts_inr
s["foc"] = s.free_qty * s.pts_inr
qq = s.groupby("q")[["gross", "foc"]].sum()
qq["excess_over_3pct_cr"] = ((qq.foc - 0.03 * qq.gross).clip(lower=0) / 1e7).round(3)
print("\nFOC over the 3% cap (INR cr) by quarter:", qq.excess_over_3pct_cr.to_dict())

# stock-norm proxy (§4.5): stockist's scheme-window purchase vs its avg monthly purchase prev 3 months
m = s.groupby(["stockist_code", "sku_code", "month"]).agg(packs=("invoiced_qty", "sum"), free=("free_qty", "sum")).reset_index()
m = m.sort_values("month")
m["avg3"] = m.groupby(["stockist_code", "sku_code"]).packs.transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
qe = m[m.month.dt.month.isin([3, 6, 9, 12]) & (m.free > 0)]
print("scheme-month purchase / prior avg monthly purchase (median, p90):", round((qe.packs / qe.avg3).median(), 2), round((qe.packs / qe.avg3).quantile(0.9), 2))

# ---------------- H5: allocation vs demand by CFA
first = s[s.ordered_qty.notna()]
line = s.groupby(["invoice_no", "sku_code"]).agg(cnf=("cnf_code", "first"), q=("q", "first"), pts=("pts_inr", "first"),
                                                 inv=("invoiced_qty", "sum"))
line["ord"] = first.groupby(["invoice_no", "sku_code"]).ordered_qty.sum().reindex(line.index)
line["short_val"] = (line.ord - line.inv).clip(lower=0) * line.pts
line["fy"] = line.q.str[:4]
dem = line.groupby(["fy", "cnf"]).ord.sum().unstack()
sup = line.groupby(["fy", "cnf"]).inv.sum().unstack()
print("\ndemand share % (ordered) by FY:\n", (dem.div(dem.sum(1), axis=0) * 100).round(1).to_string())
print("supply share % (invoiced) by FY:\n", (sup.div(sup.sum(1), axis=0) * 100).round(1).to_string())
l12 = line[line.index.get_level_values(0).isin(s12.invoice_no)]
print("short-supplied value at PTS, last 12m by CFA (INR cr):", (l12.groupby("cnf").short_val.sum() / 1e7).round(3).to_dict(),
      "total", round(l12.short_val.sum() / 1e7, 3))
print("short-supplied value by FY (cr):", (line.groupby("fy").short_val.sum() / 1e7).round(3).to_dict())

# CFA months of cover by snapshot
cov = st.groupby(["snapshot_date", "cnf_code"]).agg(oh=("qty_on_hand_packs", "sum"))
# outward per sku is repeated on each batch row -> take one per sku
out = st.drop_duplicates(["snapshot_date", "cnf_code", "sku_code"]).groupby(["snapshot_date", "cnf_code"]).avg_monthly_outward_packs.sum()
cov["months_cover"] = cov.oh / out
print("\nmonths of cover by CFA:\n", cov.months_cover.unstack().round(2).to_string())
zero = st[(st.batch_no == "") & (st.qty_on_hand_packs == 0)].groupby(["snapshot_date", "cnf_code"]).size().unstack().fillna(0)
print("SKUs out of stock at CFA:\n", zero.astype(int).to_string())
st["val"] = st.qty_on_hand_packs * st.sku_code.map(sk.pts_inr)
print("CFA inventory value at PTS (cr):\n", (st.groupby(["snapshot_date", "cnf_code"]).val.sum().unstack() / 1e7).round(2).to_string())
st.to_pickle("analysis/stock.pkl")
s.to_pickle("analysis/sales.pkl")
