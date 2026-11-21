"""Follow-ups from the voice-note tests: stranded lots, MOQ measured three ways, Guntur push, Gorakhpur orders."""
import json

import pandas as pd

import config as C
from agent import data as d

pd.set_option("display.width", 240, "display.max_columns", 40, "display.max_rows", 70)
s, st, sk, b = d.sales().copy(), d.stock(), d.skus(), d.batches()
s["gross"] = s.invoiced_qty * s.pts_inr
SNAP = st.snapshot_date.max()
OUT = {}

print("== Stranded: stock at 30-Sep with no dispatch for 90 days while a NEWER batch of the same SKU shipped")
cut = SNAP - pd.Timedelta(days=90)
oh = st[(st.snapshot_date == SNAP) & (st.batch_no != "")].groupby(["cnf_code", "sku_code", "batch_no"]).agg(qty=("qty_on_hand_packs", "sum"), rows=("src_row", list)).reset_index()
oh = oh[oh.qty > 0]
oh["exp"] = oh.batch_no.map(b.expiry_date)
disp = s[s.batch_no != ""].groupby(["cnf_code", "batch_no"]).invoice_date.max()
oh["last_dispatch"] = [disp.get((a, x), pd.NaT) for a, x in zip(oh.cnf_code, oh.batch_no)]
rec = s[(s.batch_no != "") & (s.invoice_date > cut)].assign(exp=lambda x: x.batch_no.map(b.expiry_date))
newest = rec.groupby(["cnf_code", "sku_code"]).exp.max()
oh["newer_shipped"] = [newest.get((a, k), pd.NaT) > e for a, k, e in zip(oh.cnf_code, oh.sku_code, oh.exp)]
oh["idle"] = oh.last_dispatch.isna() | (oh.last_dispatch <= cut)
oh["val"] = oh.qty * oh.sku_code.map(sk.pts_inr)
oh["ta"] = oh.sku_code.map(sk.therapy_area)
oh["block"] = oh.exp - pd.Timedelta(days=C.MIN_DAYS_TO_EXPIRY_AT_DISPATCH)
x = oh[oh.idle & oh.newer_shipped]
t = x.groupby("cnf_code").agg(lots=("val", "size"), packs=("qty", "sum"), inr=("val", "sum"))
t["share_of_cfa_stock_pct"] = (t.inr / oh.groupby("cnf_code").val.sum() * 100).round(1)
print(t.round().to_string())
k = x[x.cnf_code == "CF-E01"].sort_values("exp")
print(k.groupby("ta").agg(lots=("val", "size"), inr=("val", "sum")).round().to_string())
print(k[["batch_no", "sku_code", "ta", "exp", "block", "last_dispatch", "qty", "val"]].head(30).to_string())
for lim in ("2027-02-28", "2027-06-30", "2027-09-30"):
    q = k[k.block <= lim]; print("Kolkata idle lots reaching 60-day block by", lim, len(q), round(q.val.sum()))
OUT["stranded_by_cnf"] = {a: {"lots": int(r.lots), "inr": round(r.inr)} for a, r in t.iterrows()}
OUT["kolkata_stranded_by_ta"] = {a: round(v) for a, v in k.groupby("ta").val.sum().items()}
OUT["kolkata_block_by_feb27_inr"] = round(k[k.block <= "2027-02-28"].val.sum())
OUT["kolkata_block_by_jun27_inr"] = round(k[k.block <= "2027-06-30"].val.sum())
k.drop(columns=["rows"]).to_pickle("analysis/kolkata_stranded.pkl")

print("\n== MOQ (Annexure B: 1.5x average monthly purchase of the SKU over previous 3 months), L12M, three readings")
m = s.assign(p=s.invoice_date.dt.to_period("M")).groupby(["stockist_code", "sku_code", "p"]).invoiced_qty.sum().unstack(fill_value=0)
sc = s[(s.scheme_code != "") & (s.invoice_date >= "2025-10-01")].copy()
sc["p"] = sc.invoice_date.dt.to_period("M")
win = s[s.invoice_date.dt.day >= C.SCHEME_WINDOW_START_DAY].assign(p=lambda v: v.invoice_date.dt.to_period("M")).groupby(["stockist_code", "sku_code", "p"]).invoiced_qty.sum()
g = sc.groupby(["stockist_code", "sku_code", "p"]).agg(sch=("invoiced_qty", "sum"), biggest=("invoiced_qty", "max"), foc=("free_qty", "sum"), pts=("pts_inr", "first")).reset_index()
g["moq"] = [C.SCHEME_MOQ_MULTIPLE * sum(m.loc[(a, k), q - i] if (q - i) in m.columns else 0 for i in (1, 2, 3)) / 3 for a, k, q in zip(g.stockist_code, g.sku_code, g.p)]
g["month"] = [m.loc[(a, k), q] for a, k, q in zip(g.stockist_code, g.sku_code, g.p)]
g["window"] = [win.get((a, k, q), 0) for a, k, q in zip(g.stockist_code, g.sku_code, g.p)]
g["focv"] = g.foc * g.pts
res = {}
for n, col in (("largest single scheme line", "biggest"), ("all scheme lines in the month", "sch"), ("all purchases 22nd to month-end", "window"), ("all purchases in the month (most lenient)", "month")):
    b_ = g[g[col] < g.moq]
    res[n] = {"pairs_below": len(b_), "of": len(g), "foc_inr": round(b_.focv.sum())}
    print(n, res[n])
OUT["moq_l12m"] = res
OUT["foc_l12m_inr"] = round(g.focv.sum())

print("\n== New Enterprises STK0140, Guntur: days around quarter-end")
w = s[(s.stockist_code == "STK0140") & (s.invoice_date >= "2026-09-20")]
print((w.groupby(w.invoice_date.dt.date).gross.sum().round()).to_dict())
for a, z in (("2026-09-24", "2026-09-30"), ("2026-09-21", "2026-09-27")):
    print(a, z, round(w[(w.invoice_date >= a) & (w.invoice_date <= z)].gross.sum()))

print("\n== Gorakhpur STK0152 Amox-Clav and Azithro lines since June")
print(s[(s.stockist_code == "STK0152") & s.sku_code.isin(["PFL1001", "PFL1002"]) & (s.invoice_date >= "2026-06-01")][["src_row", "invoice_date", "sku_code", "batch_no", "ordered_qty", "invoiced_qty"]].to_string())
y = s[(s.stockist_code == "STK0152") & (s.invoice_date >= "2026-09-01") & (s.batch_no == "")]
print("Sept unsupplied:", y[["src_row", "invoice_date", "sku_code", "ordered_qty"]].to_string())
F = json.load(open("analysis/findings.json"))
F["voice_followups"] = OUT
json.dump(F, open("analysis/findings.json", "w"), indent=1, default=float)
