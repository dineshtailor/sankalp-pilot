"""Test each spoken claim in the six voice notes against the extracts. Run: python -m analysis.17_voice_tests"""
import pandas as pd

from agent import data as d

pd.set_option("display.width", 240, "display.max_columns", 40, "display.max_rows", 80)
s, c, st, sk, b, m = d.sales().copy(), d.claims(), d.stock().copy(), d.skus(), d.batches(), d.stockists()
s["ym"] = s.invoice_date.dt.to_period("M").astype(str)
s["gross"] = s.invoiced_qty * s.pts_inr
s["unsup"] = (s.batch_no == "")


def show(title):
    print("\n" + "=" * 8, title)


show("V1 Ludhiana STK0007: Monte-LC push and Amox-Clav cancellations")
x = s[(s.stockist_code == "STK0007") & (s.sku_code == "PFL1301")]
print(x.groupby("ym")[["invoiced_qty", "free_qty"]].sum().tail(9).T.to_string())
print(x[x.invoice_date >= "2026-09-01"][["src_row", "invoice_no", "invoice_date", "ordered_qty", "invoiced_qty", "free_qty", "scheme_code"]].to_string())
y = s[(s.stockist_code == "STK0007") & (s.sku_code == "PFL1002") & (s.invoice_date >= "2026-04-01")]
print(y[["src_row", "invoice_date", "batch_no", "ordered_qty", "invoiced_qty"]].to_string())

show("Scheme terms: free packs vs entitlement (Annexure B)")
sc = s[s.scheme_code != ""].copy()
sc["ratio"] = sc.scheme_code.map(lambda k: 0.1 if k.endswith("-B") or k[3:9] in ("FY25Q1", "FY25Q2") else 0.2)
sc["entitled"] = (sc.invoiced_qty * sc.ratio).round()
sc["excess"] = (sc.free_qty - sc.entitled).clip(lower=0)
print("lines", len(sc), "with free > entitled+1:", int((sc.excess > 1).sum()), "excess INR", round((sc.excess * sc.pts_inr).sum()))
print((sc.free_qty.sum() / sc.invoiced_qty.sum()).round(4), sc.groupby(sc.scheme_code.str[-1]).apply(lambda g: round(g.free_qty.sum() / g.invoiced_qty.sum(), 4)).to_dict())
out_win = sc[~((sc.invoice_date.dt.month.isin([3, 6, 9, 12])) & (sc.invoice_date.dt.day >= 22))]
print("scheme lines outside 22nd-month-end window", len(out_win))
mon = s.groupby(["stockist_code", "sku_code", s.invoice_date.dt.to_period("M")]).invoiced_qty.sum().rename("q").reset_index()
mon = mon.sort_values("invoice_date")
mon["prev3"] = mon.groupby(["stockist_code", "sku_code"]).q.transform(lambda v: v.shift(1).rolling(3, min_periods=3).mean())
sm = sc.groupby(["stockist_code", "sku_code", sc.invoice_date.dt.to_period("M")]).agg(sch=("invoiced_qty", "sum"), foc=("free_qty", "sum"), pts=("pts_inr", "first")).reset_index()
j = sm.merge(mon, on=["stockist_code", "sku_code", "invoice_date"]).dropna(subset=["prev3"])
below = j[j.sch < 1.5 * j.prev3]
print("scheme stockist-SKU-months", len(j), "below 1.5x MOQ", len(below), "FOC INR on those", round((below.foc * below.pts).sum()))

show("V2 Incentive push: last 10 days of each quarter; New Enterprises Guntur; Deccan stock")
for q_end in ("2026-06-30", "2026-09-30"):
    e = pd.Timestamp(q_end); st_q = e - pd.offsets.QuarterBegin(startingMonth=1) if False else (e - pd.DateOffset(months=3) + pd.offsets.Day(1))
    q = s[(s.invoice_date > e - pd.DateOffset(months=3)) & (s.invoice_date <= e)]
    print(q_end, "last 10 days share %", round(q[q.invoice_date > e - pd.Timedelta(days=10)].gross.sum() / q.gross.sum() * 100, 1), "last 7 days %", round(q[q.invoice_date > e - pd.Timedelta(days=7)].gross.sum() / q.gross.sum() * 100, 1))
ne = m[m.stockist_name.str.contains("New Enterprises", case=False) | (m.city.str.lower() == "guntur")]
print(ne[["stockist_code", "stockist_name", "cnf_code", "city"]].to_string())
for k in ne.stockist_code:
    w = s[(s.stockist_code == k) & (s.invoice_date >= "2026-09-22")]
    print(k, "22-30 Sep gross", round(w.gross.sum()), "free value", round((w.free_qty * w.pts_inr).sum()), "; monthly gross", s[s.stockist_code == k].groupby("ym").gross.sum().tail(4).round().to_dict())
last = st[st.snapshot_date == st.snapshot_date.max()]
print("CF-S02 on hand 30-Sep PFL1002, PFL1301:", last[(last.cnf_code == "CF-S02") & last.sku_code.isin(["PFL1002", "PFL1301"])].groupby("sku_code").qty_on_hand_packs.sum().to_dict())

show("V3 Allocation still on FY25 split? inflow share vs FY25 demand share")
ord_ = s[s.ordered_qty.notna()]
fy25 = ord_[ord_.invoice_date < "2025-04-01"].groupby("cnf_code").ordered_qty.sum()
fy25 = (fy25 / fy25.sum() * 100).round(1)
o = st[st.snapshot_date == "2026-03-31"].groupby("cnf_code").qty_on_hand_packs.sum()
e = st[st.snapshot_date == "2026-09-30"].groupby("cnf_code").qty_on_hand_packs.sum()
w = s[(s.invoice_date > "2026-03-31") & (s.invoice_date <= "2026-09-30")]
ship = (w.invoiced_qty + w.free_qty).groupby(w.cnf_code).sum()
inflow = e - o + ship
dem = w[w.ordered_qty.notna()].groupby("cnf_code").ordered_qty.sum()
print(pd.DataFrame({"fy25_demand_share": fy25, "apr_sep26_inflow_share": (inflow / inflow.sum() * 100).round(1), "apr_sep26_demand_share": (dem / dem.sum() * 100).round(1)}).to_string())

show("V4 Hooghly: lots stranded since March (all C&Fs for comparison)")
bq = st[st.batch_no != ""].groupby(["cnf_code", "batch_no", "snapshot_date"]).qty_on_hand_packs.sum().unstack()
snaps = [pd.Timestamp(x) for x in ("2026-03-31", "2026-04-30", "2026-05-31", "2026-06-30", "2026-07-31", "2026-08-31", "2026-09-30")]
bq = bq[snaps].dropna()
post = s[(s.batch_no != "") & (s.invoice_date > "2026-03-31")].groupby(["cnf_code", "batch_no"]).invoiced_qty.sum()
r = bq.reset_index()
r["sold_after_mar"] = [post.get((a, k), 0) for a, k in zip(r.cnf_code, r.batch_no)]
r["sku"] = r.batch_no.map(b.sku_code); r["ta"] = r.sku.map(sk.therapy_area); r["exp"] = r.batch_no.map(b.expiry_date)
r["q0"], r["q1"] = r[snaps[0]], r[snaps[-1]]
r["val"] = r.q1 * r.sku.map(sk.pts_inr)
strand = r[(r.q1 >= 0.95 * r.q0) & (r.q1 > 0)]
print("lots present in all 7 month-ends:", r.groupby("cnf_code").size().to_dict())
print("stranded (>=95% of March qty still there):", strand.groupby("cnf_code").agg(lots=("val", "size"), packs=("q1", "sum"), inr=("val", "sum")).round().to_string())
k = strand[strand.cnf_code == "CF-E01"].copy()
k["block_date"] = k.exp - pd.Timedelta(days=60)
print(k.groupby("ta").agg(lots=("val", "size"), inr=("val", "sum")).round().to_string())
print(k.sort_values("exp")[["batch_no", "sku", "ta", "exp", "block_date", "q0", "q1", "sold_after_mar", "val"]].head(25).to_string())
print("Kolkata stranded hitting 60-day block by 28-Feb-27:", int((k.block_date <= "2027-02-28").sum()), "lots INR", round(k[k.block_date <= "2027-02-28"].val.sum()))
print("by 30-Jun-27:", int((k.block_date <= "2027-06-30").sum()), "lots INR", round(k[k.block_date <= "2027-06-30"].val.sum()))
k.to_pickle("analysis/kolkata_stranded.pkl")

show("V5 Matrix Medicos claim; resend advice from Hyderabad C&F")
print(c[c.claim_no == "CLM-2607-02627"][["src_row", "claim_no", "claim_date", "stockist_code", "cnf_code", "sku_code", "batch_no", "qty_claimed", "claim_value_inr", "status"]].to_string())
f = pd.read_pickle("analysis/claims_flagged.pkl")
g = f[f.status != "Rejected"].groupby("cnf_code").agg(claims=("claim_no", "size"), repeats=("dup_same_qty", "sum"))
g["repeat_pct"] = (g.repeats / g.claims * 100).round(1)
print(g.to_string())
print("no invoice ref by C&F %:", (f.groupby("cnf_code").no_invoice_ref.mean() * 100).round(1).to_dict())
dup = f[f.dup_same_qty]
print("repeat claims with no invoice ref %:", round(dup.no_invoice_ref.mean() * 100, 1), "| all claims %:", round(f.no_invoice_ref.mean() * 100, 1))

show("V6 Gorakhpur STK0152: anti-infective supply; new UP stockists")
ai = sk[sk.therapy_area == "Anti-infectives"].index
x = s[(s.stockist_code == "STK0152") & s.sku_code.isin(ai) & (s.invoice_date >= "2026-03-01")]
print(x.groupby("ym").agg(lines=("src_row", "size"), unsupplied=("unsup", "sum"), invoiced=("invoiced_qty", "sum")).T.to_string())
print(x[(x.invoice_date >= "2026-09-01") & x.sku_code.isin(["PFL1001", "PFL1002"])][["src_row", "invoice_date", "sku_code", "batch_no", "ordered_qty", "invoiced_qty"]].to_string())
print(m[m.appointed_on.notna()][["stockist_code", "stockist_name", "cnf_code", "city", "appointed_on"]].to_string())
print("Lucknow on hand 30-Sep PFL1001/1002:", last[(last.cnf_code == "CF-N02") & last.sku_code.isin(["PFL1001", "PFL1002"])][["sku_code", "batch_no", "qty_on_hand_packs"]].to_string(index=False))
