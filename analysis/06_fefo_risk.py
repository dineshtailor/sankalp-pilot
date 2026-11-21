"""H6 FEFO / RSL at dispatch, H7 CFA stock that will expire before it sells. Run after 05_supply."""
import pandas as pd

import config as C
from agent import data as d

pd.set_option("display.width", 220)
s = pd.read_pickle("analysis/sales.pkl")
st = pd.read_pickle("analysis/stock.pkl")
b, sk = d.batches(), d.skus()
s = s[s.batch_no != ""].copy()
s["expiry"] = s.batch_no.map(b.expiry_date)
s["shelf_m"] = s.sku_code.map(sk.shelf_life_months)
s["rsl_share"] = (s.expiry - s.invoice_date).dt.days / (s.shelf_m * 30.44)
s["days_left"] = (s.expiry - s.invoice_date).dt.days
s["low_rsl"] = s.rsl_share < C.MIN_RSL_SHARE_AT_INVOICE
s["ym"] = s.invoice_date.dt.to_period("M")
print("share of invoiced packs with RSL < 60% at invoice, by CFA and month (from 2025-10):")
x = s[s.invoice_date >= "2025-10-01"]
t = (x.invoiced_qty * x.low_rsl).groupby([x.ym, x.cnf_code]).sum() / x.groupby([x.ym, x.cnf_code]).invoiced_qty.sum() * 100
print(t.unstack().round(1).to_string())
print("dispatched with < 60 days to expiry (lines):", int((s.days_left < 60).sum()))

# FEFO: within a CFA and month, was an earlier-expiry batch of the same SKU also being dispatched?
# A line is 'non-FEFO' if a batch expiring earlier (and still > 60 days left) was dispatched by the same CFA in the same month AFTER this line's date.
s = s.sort_values("invoice_date")
g = s.groupby(["cnf_code", "sku_code", "ym"])
s["min_exp_month"] = g.expiry.transform("min")
s["n_batches_month"] = g.batch_no.transform("nunique")
s["older_avail"] = (s.expiry > s.min_exp_month)
mixed = s.groupby(["invoice_no", "sku_code"]).batch_no.nunique()
print("\ninvoice lines split across >1 batch, by CFA (count, from 2025-10):")
xs = s[s.invoice_date >= "2025-10-01"]
mx = xs.groupby(["invoice_no", "sku_code", "cnf_code"]).batch_no.nunique().reset_index()
print(mx[mx.batch_no > 1].groupby("cnf_code").size().to_dict())
fe = (xs.invoiced_qty * xs.older_avail).groupby([xs.ym, xs.cnf_code]).sum() / xs.groupby([xs.ym, xs.cnf_code]).invoiced_qty.sum() * 100
print("\n% packs shipped from a newer batch while an older batch of same SKU shipped same month (FEFO-breach proxy):")
print(fe.unstack().round(1).to_string())
# average days to expiry of dispatched stock by CFA by month
print("\nmedian days-to-expiry at dispatch by CFA by month:")
print(xs.groupby(["ym", "cnf_code"]).days_left.median().unstack().round(0).to_string())
print("\nSTK0061 INV/E01/2606/076199:")
print(d.sales()[d.sales().invoice_no == "INV/E01/2606/076199"][["src_row", "invoice_no", "invoice_date", "sku_code", "batch_no", "invoiced_qty", "free_qty"]].to_string())

# ---------------- H7: stock at CFA that cannot sell before the 60-day block (latest snapshot)
snap = st[st.snapshot_date == st.snapshot_date.max()].copy()
snap = snap[snap.batch_no != ""]
snap = snap.sort_values(["cnf_code", "sku_code", "expiry_date"])
snap["sell_days"] = ((snap.expiry_date - snap.snapshot_date).dt.days - C.MIN_DAYS_TO_EXPIRY_AT_DISPATCH).clip(lower=0)
# FEFO: earlier batches consume outward first
rows = []
for (cnf, sku), grp in snap.groupby(["cnf_code", "sku_code"]):
    rate = grp.avg_monthly_outward_packs.iloc[0] or 0
    used_days = 0.0
    for _, r in grp.iterrows():
        cap = max(r.sell_days - used_days, 0) / 30.44 * rate
        sell = min(r.qty_on_hand_packs, cap)
        used_days += sell / rate * 30.44 if rate else 0
        rows.append({**r.to_dict(), "sellable": sell, "at_risk": r.qty_on_hand_packs - sell})
risk = pd.DataFrame(rows)
risk["risk_val"] = risk.at_risk * risk.sku_code.map(sk.pts_inr)
print("\nCFA stock at 30-09-2026 that will hit the 60-day block before it sells (INR cr):",
      (risk.groupby("cnf_code").risk_val.sum() / 1e7).round(3).to_dict(), "total", round(risk.risk_val.sum() / 1e7, 3))
print(risk.sort_values("risk_val", ascending=False)[["src_row", "cnf_code", "sku_code", "batch_no", "expiry_date", "qty_on_hand_packs", "avg_monthly_outward_packs", "at_risk", "risk_val"]].head(10).to_string())
# historical: stock at CFA already inside 60 days of expiry at a snapshot (blocked -> destroyed, §7.2)
st2 = st[st.batch_no != ""].copy()
st2["dte"] = (st2.expiry_date - st2.snapshot_date).dt.days
blk = st2[st2.dte < 60]
print("\nstock already < 60 days to expiry at CFA, by snapshot (INR lakh):")
print((blk.groupby(["snapshot_date", "cnf_code"]).val.sum().unstack().fillna(0) / 1e5).round(2).to_string())
risk.to_pickle("analysis/risk.pkl")
