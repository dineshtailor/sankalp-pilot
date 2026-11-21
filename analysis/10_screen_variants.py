"""Find a defensible stock estimate for the §4.5 screen. Backtest as of 2025-08-31 and 2025-11-30 (pre-Dec)."""
import numpy as np
import pandas as pd

from agent import data as d
from agent import reports as rp

s, c = d.sales(), d.claims()
s = s.assign(month=s.invoice_date.dt.to_period("M"), packs=s.invoiced_qty + s.free_qty)
m = s.groupby(["stockist_code", "sku_code", "month"]).packs.sum()
skus = rp.scheme_skus()


def features(as_of):
    p = pd.Timestamp(as_of).to_period("M")
    mm = m[(m.index.get_level_values(2) <= p) & (m.index.get_level_values(2) > p - 12)].reset_index()
    mm = mm[mm.sku_code.isin(skus)]
    mm["qe"] = mm.month.dt.month.isin([3, 6, 9, 12])
    cl = c[(c.claim_date <= as_of) & (c.claim_date > pd.Timestamp(as_of) - pd.DateOffset(months=12)) & (c.status != "Rejected")
           & c.claim_type.isin(["Near expiry", "Expired"])].groupby(["stockist_code", "sku_code"]).qty_claimed.sum()
    g = mm.groupby(["stockist_code", "sku_code"])
    f = pd.DataFrame({
        "total12": g.packs.sum(),
        "nonqe_mean": mm[~mm.qe].groupby(["stockist_code", "sku_code"]).packs.sum() / 8,
        "last3": mm[mm.month > p - 3].groupby(["stockist_code", "sku_code"]).packs.sum(),
    }).fillna(0)
    f["claimed12"] = cl.reindex(f.index).fillna(0)
    # offtake = non-scheme-month run rate (what the market pulls without a scheme), net of returns
    f["offtake"] = (f.nonqe_mean - f.claimed12 / 12).clip(lower=0)
    # stock build over 12m = bought - sold - returned
    f["build12"] = (f.total12 - 12 * f.offtake - f.claimed12).clip(lower=0)
    f["cover"] = np.where(f.offtake > 0, 1.0 + f.build12 / f.offtake, np.nan)
    f["claim_rate"] = f.claimed12 / f.total12.where(f.total12 > 0)
    return f


def outcome(as_of, horizon=12):
    end = pd.Timestamp(as_of) + pd.DateOffset(months=horizon)
    n = c[(c.claim_date > as_of) & (c.claim_date <= end) & (c.status != "Rejected") & c.claim_type.isin(["Near expiry", "Expired"])]
    return n.groupby(["stockist_code", "sku_code"]).claim_value_inr.sum()


for as_of in ("2025-08-31", "2025-11-30", "2026-02-28"):
    f = features(as_of)
    y = outcome(as_of)
    f["next_claims"] = y.reindex(f.index).fillna(0)
    for rule, mask in {"cover>2.5": f.cover > 2.5, "cover>4": f.cover > 4,
                       "claim_rate>5%": f.claim_rate > 0.05, "cover>2.5 or claim_rate>5%": (f.cover > 2.5) | (f.claim_rate > 0.05)}.items():
        w = f[mask]
        print(f"{as_of} {rule:28s} flagged {len(w):4d}/{len(f)} ({len(w)/len(f):.0%})  captures {w.next_claims.sum()/f.next_claims.sum():.0%} of next-12m claims"
              f"  per-pair flagged {w.next_claims.mean():8.0f} vs rest {f[~mask].next_claims.mean():8.0f}")
