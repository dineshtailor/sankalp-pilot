"""Size each problem in INR per year. Basis: last 12 months of data, 01-Oct-2025 to 30-Sep-2026.
Writes analysis/findings.json, which the discovery note and deck quote. Run after 03, 05, 06."""
import json

import numpy as np
import pandas as pd

import config as C
from agent import data as d

L12 = ("2025-10-01", "2026-09-30")
sk, b = d.skus(), d.batches()
c = pd.read_pickle("analysis/claims_flagged.pkl")
s = pd.read_pickle("analysis/sales.pkl")
st = pd.read_pickle("analysis/stock.pkl")
F = {}
in12 = lambda x, col: x[(x[col] >= L12[0]) & (x[col] <= L12[1])]

# --- context numbers
s12 = in12(s, "invoice_date")
F["primary_gross_l12m_cr"] = round((s12.invoiced_qty * s12.pts_inr).sum() / 1e7, 2)
c12 = in12(c, "claim_date")
exp12 = c12[c12.claim_type.isin(["Near expiry", "Expired"])]
F["expiry_claims_logged_l12m_cr"] = round(exp12.value.sum() / 1e7, 3)
F["claims_credited_l12m_cr"] = round(c12.credited.sum() / 1e7, 3)

# --- P1 claim leakage the checker would stop (credited or pending, last 12m)
live = c12[c12.status != "Rejected"]
dup = live[live.dup_same_qty]
over = live[live.cumulative_over_invoiced]
# excess packs over invoiced only
cum = c[c.status != "Rejected"].sort_values("claim_date").groupby(["stockist_code", "batch_no"]).qty_claimed.cumsum()
over_by_claim = np.minimum(over.qty_claimed, cum.reindex(over.index) - over.sold_packs) * over.sku_code.map(sk.pts_inr)
over_excess = over_by_claim.sum()
late = live[live.window_expired_too_late]
# one claim can fail several rules: count each claim's money once
full_reject = live[live.dup_same_qty | live.window_expired_too_late]
over_only = over_by_claim[~over_by_claim.index.isin(full_reject.index)]
p1 = {
    "duplicate_same_stockist_batch_qty": {"claims": len(dup), "inr": round(dup.value.sum())},
    "qty_above_invoiced_excess_only": {"claims": len(over), "inr": round(over_excess)},
    "expired_claim_after_90_days": {"claims": len(late), "inr": round(late.value.sum())},
}
p1_total = full_reject.value.sum() + over_only.sum()
flagged = live.index.isin(full_reject.index) | live.index.isin(over_only.index)
F["P1_claim_leakage"] = {"items": p1, "inr_per_year": round(p1_total), "unique_claims": int(flagged.sum()),
                         "overlap_removed_inr": round(sum(v["inr"] for v in p1.values()) - p1_total),
                         "repeat_claims_credited": int((dup.status == "Credited").sum()), "repeat_claims_pending": int((dup.status == "Pending").sum()),
                         "basis": "credited+pending claims in L12M failing a hard rule; each claim counted once"}
noinv = live[live.no_invoice_ref & live.claim_type.isin(["Near expiry", "Expired"])]
F["P1_no_invoice_ref_l12m"] = {"claims": len(noinv), "inr": round(noinv.value.sum()),
                              "matched_to_sales_by_stockist_batch": int((noinv.sold_packs > 0).sum())}
early = live[live.window_near_too_early]
F["P1_near_expiry_filed_too_early_l12m"] = {"claims": len(early), "inr": round(early.value.sum())}
arch = live[live.batch_not_in_master]
F["P1_batch_archived_needs_erp_check_l12m"] = {"claims": len(arch), "inr": round(arch.value.sum())}

# --- P2 scheme-driven expiry
sold = s[s.batch_no != ""]
buy = sold.groupby(["stockist_code", "batch_no"]).agg(packs=("invoiced_qty", "sum"), free=("free_qty", "sum"),
                                                     sch=("invoiced_qty", lambda x: x[sold.loc[x.index, "on_scheme"]].sum()))
buy["share"] = (buy.sch / buy.packs).fillna(0)
e = exp12[exp12.status != "Rejected"].join(buy.share, on=["stockist_code", "batch_no"])
e["share"] = e.share.fillna(0)
# baseline claim rate on non-scheme lots: 0.98% (05_supply). Excess = scheme-attributed claims minus baseline on those packs
sch_val = (e.value * e.share).sum()
sch_packs_val = (buy.sch * buy.index.get_level_values(1).map(b.sku_code).map(sk.pts_inr)).sum()
# restrict baseline to L12M scheme purchases
s12b = s12[(s12.batch_no != "") & s12.on_scheme]
sch_purch_val_l12 = ((s12b.invoiced_qty + s12b.free_qty) * s12b.pts_inr).sum()
excess = max(sch_val - 0.0098 * sch_purch_val_l12, 0)
foc12 = (s12.free_qty * s12.pts_inr).sum()
gross_q = s12.assign(gross=s12.invoiced_qty * s12.pts_inr, foc=s12.free_qty * s12.pts_inr).groupby("q")[["gross", "foc"]].sum()
foc_over_cap = (gross_q.foc - C.SCHEME_CAP_SHARE * gross_q.gross).clip(lower=0).sum()
F["P2_scheme_driven_expiry"] = {
    "expiry_claims_on_scheme_bought_packs_l12m_inr": round(sch_val),
    "baseline_rate_non_scheme_pct": 0.98, "scheme_purchases_l12m_inr": round(sch_purch_val_l12),
    "excess_claims_over_baseline_inr": round(excess),
    "foc_issued_l12m_inr": round(foc12), "foc_over_3pct_cap_l12m_inr": round(foc_over_cap),
    "screen_capture_assumption": 0.5,
    "inr_per_year": round(0.5 * excess + foc_over_cap),
    "method": "50% of excess scheme-lot claims avoided by withholding schemes from stockist-SKUs already above 2.5 months cover (§4.5), plus FOC above the 3% cap (§4.4)",
}

# --- P3 allocation: where vs how much (same national supply, reallocated to demand)
first = s12[s12.ordered_qty.notna()]
line = s12.groupby(["invoice_no", "sku_code"]).agg(cnf=("cnf_code", "first"), ym=("month", "first"), pts=("pts_inr", "first"), inv=("invoiced_qty", "sum"))
line["ord"] = first.groupby(["invoice_no", "sku_code"]).ordered_qty.sum().reindex(line.index)
cm = line.groupby(["sku_code" if False else line.index.get_level_values(1), "ym", "cnf"]).agg(ord=("ord", "sum"), inv=("inv", "sum"), pts=("pts", "first"))
cm.index.names = ["sku", "ym", "cnf"]
actual_short = ((cm.ord - cm.inv).clip(lower=0) * cm.pts).sum()
nat = cm.groupby(["sku", "ym"]).agg(ord=("ord", "sum"), inv=("inv", "sum"), pts=("pts", "first"))
national_short = ((nat.ord - nat.inv).clip(lower=0) * nat.pts).sum()
by_cnf = ((cm.ord - cm.inv).clip(lower=0) * cm.pts).groupby("cnf").sum()
F["P3_allocation"] = {
    "short_supplied_l12m_inr_actual": round(actual_short),
    "short_if_same_national_supply_allocated_to_demand_inr": round(national_short),
    "attributable_to_allocation_inr": round(actual_short - national_short),
    "short_by_cnf_l12m_inr": {k: round(v) for k, v in by_cnf.items()},
    "note": "ordered_qty includes re-orders after cancellations, so short value overstates lost sales; allocation share is the robust part",
}
# conservative lost-sales: Lucknow (CF-N02) whole lines not supplied at all
nsup = line[(line.inv == 0)]
F["P3_lucknow_lines_not_supplied_l12m_inr"] = round((nsup[nsup.cnf == "CF-N02"].ord * nsup[nsup.cnf == "CF-N02"].pts).sum())
snap = st[st.snapshot_date == st.snapshot_date.max()]
out = snap.drop_duplicates(["cnf_code", "sku_code"]).set_index(["cnf_code", "sku_code"]).avg_monthly_outward_packs
oh = snap.groupby(["cnf_code", "sku_code"]).qty_on_hand_packs.sum()
excess_k = ((oh - C.REPLENISH_TARGET_MONTHS * out).clip(lower=0) * oh.index.get_level_values(1).map(sk.pts_inr)).groupby(level=0).sum()
F["P3_stock_above_2_months_cover_30sep26_inr"] = {k: round(v) for k, v in excess_k.items()}
# protected revenue: half of Lucknow's unsupplied-line value, capped by excess elsewhere; margin not applied (revenue at PTS)
lk = F["P3_lucknow_lines_not_supplied_l12m_inr"]
F["P3_inr_per_year_revenue_protected"] = round(0.5 * min(lk, F["P3_allocation"]["attributable_to_allocation_inr"]))

# --- P4 FEFO at Kolkata: packs dispatched from newer batch while older shipping (proxy) and low-RSL
s12k = s12[(s12.batch_no != "")].copy()
s12k["exp"] = s12k.batch_no.map(b.expiry_date)
s12k["rsl"] = (s12k.exp - s12k.invoice_date).dt.days / (s12k.sku_code.map(sk.shelf_life_months) * 30.44)
low = s12k[s12k.rsl < C.MIN_RSL_SHARE_AT_INVOICE]
F["P4_low_rsl_dispatch_l12m_inr_by_cnf"] = {k: round(v) for k, v in (low.invoiced_qty * low.pts_inr).groupby(low.cnf_code).sum().items()}
# claims rate East vs rest on low-RSL lots
F["P4_note"] = "Kolkata FEFO-breach proxy 64-80% Mar-Sep 2026 vs 10-55% elsewhere (06_fefo_risk)"

# --- P5 claim settlement
cr = c12[c12.status == "Credited"]
tat = (cr.credit_note_date - cr.claim_date).dt.days
F["P5_tat"] = {"mean_days": round(tat.mean(), 1), "share_over_30d_pct": round((tat > 30).mean() * 100, 1),
               "pending_claims": int((c.status == "Pending").sum()), "pending_inr": round(c[c.status == "Pending"].value.sum())}
F["P6_breakage_l12m_inr"] = round(c12[c12.claim_type == "Breakage in transit"].value.sum())
F["P6_breakage_pct_primary"] = round(F["P6_breakage_l12m_inr"] / (F["primary_gross_l12m_cr"] * 1e7) * 100, 3)

json.dump(F, open("analysis/findings.json", "w"), indent=1, default=float)
print(json.dumps(F, indent=1, default=float))
