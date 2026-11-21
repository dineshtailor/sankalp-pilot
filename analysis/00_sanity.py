"""Sanity checks on the cleaned data: counts, ranges, joins. Run: python -m analysis.00_sanity"""
import time

t = time.time()
from agent import data as d  # noqa: E402

d.load_all()
print("load seconds", round(time.time() - t, 1))
print(d.QUALITY)
s, c, st = d.sales(), d.claims(), d.stock()
print("sales dates", s.invoice_date.min(), s.invoice_date.max(), "null", s.invoice_date.isna().sum())
print("stockists in sales", s.stockist_code.nunique(), "not in master", sorted(set(s.stockist_code) - set(d.stockists().index))[:10])
print("claims dates", c.claim_date.min(), c.claim_date.max(), "null", c.claim_date.isna().sum())
print("claim stockists not in master", sorted(set(c.stockist_code) - set(d.stockists().index))[:20])
print("claim sku not in master", sorted(set(c.sku_code) - set(d.skus().index)))
print("claim batch not in master", (~c.batch_no.isin(d.batches().index)).sum())
print("sales batch not in master", (~s.batch_no[s.batch_no != ""].isin(d.batches().index)).sum())
print("cnf in stock", st.cnf_code.unique())
print("schemes", s.scheme_code.value_counts().to_dict())
dup = c[c.claim_no.duplicated(keep=False)].sort_values("claim_no")
print("repeated claim_no rows", len(dup))
print(dup[["src_row", "claim_no", "claim_date", "stockist_code", "batch_no", "qty_claimed", "status", "credit_note_no"]].head(10).to_string())
