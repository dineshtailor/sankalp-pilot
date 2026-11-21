"""Reconcile cleaned data to the QBR scorecard (doc 06 §1). Run: python -m analysis.01_reconcile"""
import pandas as pd

from agent import data as d

s, c, sk = d.sales(), d.claims(), d.skus()


def fq(ts: pd.Series) -> pd.Series:
    """Indian financial quarter label, e.g. 2025-04-01 -> FY26Q1."""
    fy = ts.dt.year + (ts.dt.month >= 4).astype(int)
    q = ((ts.dt.month - 4) % 12) // 3 + 1
    return "FY" + (fy % 100).astype(str).str.zfill(2) + "Q" + q.astype(str)


s = s.assign(q=fq(s.invoice_date), gross=s.invoiced_qty * s.pts_inr, foc=s.free_qty * s.pts_inr)
c = c.assign(q=fq(c.claim_date))
# fill rate: ordered_qty is on the first row of a split line; blank batch = not supplied
first = s[s.ordered_qty.notna()]
line_key = ["invoice_no", "sku_code"]
inv_by_line = s.groupby(line_key).invoiced_qty.sum()
ordered = first.groupby(line_key).agg(ordered=("ordered_qty", "sum"), q=("q", "first"), cnf=("cnf_code", "first"))
ordered["invoiced"] = inv_by_line.reindex(ordered.index).fillna(0)

out = pd.DataFrame({
    "primary_gross_cr": s.groupby("q").gross.sum() / 1e7,
    "net_value_cr": s.groupby("q").net_value_inr.sum() / 1e7,
    "foc_pct": s.groupby("q").foc.sum() / s.groupby("q").gross.sum() * 100,
    "claims_logged_cr": c.groupby("q").claim_value_inr.sum() / 1e7,
    "claims_all_types_value_from_qty_cr": (c.qty_claimed * c.sku_code.map(sk.pts_inr)).groupby(c.q).sum() / 1e7,
    "fill_rate_pct": ordered.groupby("q").invoiced.sum() / ordered.groupby("q").ordered.sum() * 100,
})
out["claims_pct_primary"] = out.claims_logged_cr / out.primary_gross_cr * 100
pd.set_option("display.width", 200)
print(out.round(3).to_string())
print("\nclaim types by value (INR lakh):")
print((c.groupby(["q", "claim_type"]).claim_value_inr.sum().unstack().fillna(0) / 1e5).round(2).to_string())
print("\nfill rate by CFA and quarter:")
print((ordered.groupby(["q", "cnf"]).invoiced.sum() / ordered.groupby(["q", "cnf"]).ordered.sum() * 100).unstack().round(1).to_string())
