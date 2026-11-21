"""P3 re-sized: Lucknow/North demand left unsupplied while the same SKU sat above 2 months cover elsewhere.
Monthly snapshots Apr-Sep 2026 (monthly granularity exists only from Mar 2026). Run after 07_sizing."""
import json

import pandas as pd

import config as C
from agent import data as d

sk = d.skus()
s = pd.read_pickle("analysis/sales.pkl")
st = pd.read_pickle("analysis/stock.pkl")
F = json.load(open("analysis/findings.json"))

snaps = sorted(st.snapshot_date[st.snapshot_date >= "2026-03-31"].unique())
oh = st.groupby(["snapshot_date", "cnf_code", "sku_code"]).qty_on_hand_packs.sum()
out = st.drop_duplicates(["snapshot_date", "cnf_code", "sku_code"]).set_index(["snapshot_date", "cnf_code", "sku_code"]).avg_monthly_outward_packs
surplus = (oh - C.REPLENISH_TARGET_MONTHS * out).clip(lower=0)

first = s[s.ordered_qty.notna()]
line = s.groupby(["invoice_no", "sku_code"]).agg(cnf=("cnf_code", "first"), month=("month", "first"), pts=("pts_inr", "first"), inv=("invoiced_qty", "sum"))
line["ord"] = first.groupby(["invoice_no", "sku_code"]).ordered_qty.sum().reindex(line.index)
line = line.reset_index()
line["unsup"] = (line.ord - line.inv).clip(lower=0)
rows = []
for snap in snaps[:-1]:
    nxt = (pd.Timestamp(snap) + pd.offsets.MonthEnd(1)).to_period("M")
    remaining = {}  # surplus is consumed once per SKU per month
    for target in ("CF-N02", "CF-N01"):
        u = line[(line.cnf == target) & (line.month == nxt)].groupby("sku_code").agg(unsup=("unsup", "sum"))
        for sku, r in u.iterrows():
            if r.unsup <= 0:
                continue
            if sku not in remaining:  # donors: non-North CFAs only
                remaining[sku] = sum(surplus.get((snap, cf, sku), 0) for cf in ("CF-E01", "CF-W01", "CF-S01", "CF-S02"))
            avail = remaining[sku]
            # conservative: 50% of unsupplied qty is genuine lost demand (rest are re-orders)
            movable = min(0.5 * r.unsup, avail)
            remaining[sku] -= movable
            rows.append({"snapshot": str(pd.Timestamp(snap).date()), "month": str(nxt), "cnf": target, "sku": sku,
                         "unsupplied_packs": r.unsup, "surplus_elsewhere_packs": avail, "movable_packs": movable,
                         "movable_inr": movable * sk.pts_inr[sku]})
R = pd.DataFrame(rows)
months = R.month.nunique()
tot = R.movable_inr.sum()
F["P3_rebalance"] = {
    "months_covered": months, "movable_inr_in_window": round(tot), "inr_per_year_revenue_protected": round(tot / months * 12),
    "by_cnf_inr_window": {k: round(v) for k, v in R.groupby("cnf").movable_inr.sum().items()},
    "method": "Per SKU-month (Apr-Sep 2026): min(50% of North unsupplied packs, stock above 2 months cover at other CFAs at prior month-end) x PTS; annualised. Revenue at PTS, not margin.",
    "caveat": "Return-to-CDC then re-dispatch takes 10-14 days (Sch.2 2.5); the gain needs Head SC to act monthly.",
}
json.dump(F, open("analysis/findings.json", "w"), indent=1, default=float)
print(json.dumps(F["P3_rebalance"], indent=1, default=float))
print(R.sort_values("movable_inr", ascending=False).head(8).to_string())
