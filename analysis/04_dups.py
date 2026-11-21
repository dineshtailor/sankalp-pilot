"""Look at repeat claims on the same stockist + batch. Run after 03_claims."""
import pandas as pd

c = pd.read_pickle("analysis/claims_flagged.pkl")
pd.set_option("display.width", 220)
nonrej = c[c.status != "Rejected"]
g = nonrej.groupby(["stockist_code", "batch_no"])
multi = nonrej[g.claim_no.transform("size") > 1].sort_values(["stockist_code", "batch_no", "claim_date"])
cols = ["src_row", "claim_no", "claim_date", "stockist_code", "batch_no", "claim_type", "qty_claimed", "sold_packs", "status", "credit_note_no", "original_invoice_ref", "remarks"]
print("groups with >1 claim:", multi.groupby(["stockist_code", "batch_no"]).ngroups)
same_qty = multi[multi.duplicated(["stockist_code", "batch_no", "qty_claimed"], keep=False)]
print("groups with same qty repeated:", same_qty.groupby(["stockist_code", "batch_no"]).ngroups)
print(same_qty[cols].head(12).to_string())
# gap between same-qty repeats
sq = same_qty.sort_values("claim_date")
gap = sq.groupby(["stockist_code", "batch_no", "qty_claimed"]).claim_date.diff().dt.days.dropna()
print("gap days same-qty repeat:", gap.describe().round(0).to_dict())
# sum of qty in multi groups vs sold
agg = multi.groupby(["stockist_code", "batch_no"]).agg(n=("claim_no", "size"), qty=("qty_claimed", "sum"), sold=("sold_packs", "first"))
print("multi groups where total claimed > sold:", int((agg.qty > agg.sold).sum()), " of", len(agg))
print("rejected duplicates sample:"); print(c[c.status == "Rejected"][cols].head(4).to_string())
print("STK0025 F2440122:"); print(c[(c.stockist_code == "STK0025") & (c.batch_no == "F2440122")][cols].to_string())
print("STK0007 B2430142:"); print(c[(c.stockist_code == "STK0007") & (c.batch_no == "B2430142")][cols].to_string())
