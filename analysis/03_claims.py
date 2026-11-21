"""H1-H3, H8: claims integrity against policy CO-POL-014 §5. Run: python -m analysis.03_claims"""
import pandas as pd

import config as C
from agent import data as d
from analysis_helpers import fq

c = d.claims().copy()
b, sk, sb = d.batches(), d.skus(), d.sales_by_stockist_batch()
c["q"] = fq(c.claim_date)
c["value"] = c.claim_value_inr.fillna(c.qty_claimed * c.sku_code.map(sk.pts_inr))
c["credited"] = c.credit_value_inr.where(c.status == "Credited", 0).fillna(0)
c["master_expiry"] = c.batch_no.map(b.expiry_date)
c["in_master"] = c.batch_no.isin(b.index)
c["batch_sku"] = c.batch_no.map(b.sku_code)
key = list(zip(c.stockist_code, c.batch_no))
c["sold_packs"] = [sb.total_packs.get(k, 0.0) for k in key]
c["sold_cnfs"] = [sb.cnfs.get(k, []) for k in key]
pd.set_option("display.width", 220)
fy = c.claim_date.dt.year + (c.claim_date.dt.month >= 4)
print("status:", c.status.value_counts().to_dict(), " credited INR cr", round(c.credited.sum() / 1e7, 3))

exp_types = c.claim_type.isin(["Near expiry", "Expired"])
flags = {}
# H1 duplicate: same stockist+batch claimed earlier (non-rejected) -> second+ claims
c = c.sort_values(["claim_date", "claim_no"])
nonrej = c.status != "Rejected"
c["prior_claims"] = c[nonrej].groupby(["stockist_code", "batch_no"]).cumcount()
c["prior_qty"] = c[nonrej].groupby(["stockist_code", "batch_no"]).qty_claimed.cumsum() - c.qty_claimed
flags["dup_same_stk_batch"] = nonrej & (c.prior_claims > 0) & exp_types
flags["dup_same_qty"] = flags["dup_same_stk_batch"] & (c.groupby(["stockist_code", "batch_no", "qty_claimed"]).cumcount() > 0)
# window, using MASTER expiry (not the expiry the stockist wrote)
days = (c.claim_date - c.master_expiry).dt.days
flags["window_near_too_early"] = (c.claim_type == "Near expiry") & (days < -C.NEAR_EXPIRY_WINDOW_BEFORE_DAYS)
flags["window_near_after_expiry"] = (c.claim_type == "Near expiry") & (days > 0)
flags["window_expired_too_late"] = (c.claim_type == "Expired") & (days > C.EXPIRED_WINDOW_AFTER_DAYS)
flags["window_expired_before_expiry"] = (c.claim_type == "Expired") & (days < 0)
flags["expiry_as_claimed_mismatch"] = c.in_master & (c.expiry_date_as_claimed != c.master_expiry)
flags["batch_not_in_master"] = ~c.in_master
flags["batch_sku_mismatch"] = c.in_master & (c.batch_sku != c.sku_code)
flags["never_invoiced_to_stockist"] = c.sold_packs == 0
flags["qty_over_invoiced"] = (c.sold_packs > 0) & (c.qty_claimed > c.sold_packs)
# cumulative over-claim across all claims on that stockist+batch
cum = c[nonrej].groupby(["stockist_code", "batch_no"]).qty_claimed.cumsum()
flags["cumulative_over_invoiced"] = nonrej & (c.sold_packs > 0) & (cum.reindex(c.index).fillna(0) > c.sold_packs)
flags["wrong_cfa"] = [(len(cf) > 0 and cn not in cf) for cn, cf in zip(c.cnf_code, c.sold_cnfs)]
flags["no_invoice_ref"] = c.original_invoice_ref == ""
flags["value_mismatch_pts"] = (c.claim_value_inr.notna()) & ((c.claim_value_inr - c.qty_claimed * c.sku_code.map(sk.pts_inr)).abs() > 1)
F = pd.DataFrame(flags).fillna(False).astype(bool)
c = c.join(F)
rows = []
for f in F.columns:
    m = c[f]
    rows.append({"flag": f, "claims": int(m.sum()), "credited_count": int((m & (c.status == "Credited")).sum()),
                 "credited_cr": round(c.loc[m, "credited"].sum() / 1e7, 3), "pending_cr": round(c.loc[m & (c.status == "Pending"), "value"].sum() / 1e7, 3)})
print(pd.DataFrame(rows).to_string())
anyf = F.drop(columns=["expiry_as_claimed_mismatch", "dup_same_qty"]).any(axis=1)
print("\nANY hard flag: claims", int(anyf.sum()), "credited cr", round(c.loc[anyf, "credited"].sum() / 1e7, 3),
      "pending cr", round(c.loc[anyf & (c.status == "Pending"), "value"].sum() / 1e7, 3))
print("by FY credited cr on flagged:", (c.loc[anyf].groupby(fy[anyf]).credited.sum() / 1e7).round(3).to_dict())
print("total credited by FY:", (c.groupby(fy).credited.sum() / 1e7).round(3).to_dict())
# TAT
cr = c[c.status == "Credited"]
tat = (cr.credit_note_date - cr.claim_date).dt.days
print("\nTAT days by quarter mean:", tat.groupby(cr.q).mean().round(1).to_dict(), " >30d share", round((tat > 30).mean() * 100, 1))
print("pending:", int((c.status == "Pending").sum()), "value cr", round(c.loc[c.status == "Pending", "value"].sum() / 1e7, 3),
      "oldest", c.loc[c.status == "Pending", "claim_date"].min())
print("remarks of 'Duplicate of earlier claim' status:", c.loc[c.remarks == "Duplicate of earlier claim", "status"].value_counts().to_dict())
print("no-inv-ref share FY27H1 expiry claims:", round(c.loc[exp_types & (c.claim_date >= "2026-04-01"), "no_invoice_ref"].mean() * 100, 1))
print("\nbatch not in master: sold? ", c.loc[c.batch_not_in_master, "sold_packs"].gt(0).sum(), " sample batches", c.loc[c.batch_not_in_master, "batch_no"].head(5).tolist())
print("\ncredited claims by verifier with any flag (share):")
print((c[c.status == "Credited"].groupby("verified_by")[F.columns].mean() * 100).round(1)[["dup_same_stk_batch", "never_invoiced_to_stockist", "qty_over_invoiced", "window_expired_too_late", "no_invoice_ref"]].to_string())
c.to_pickle("analysis/claims_flagged.pkl")
# examples for the check set
for f in ["dup_same_qty", "never_invoiced_to_stockist", "qty_over_invoiced", "window_expired_too_late", "wrong_cfa", "batch_sku_mismatch", "window_near_too_early"]:
    print(f"\n--- {f}")
    print(c.loc[c[f], ["src_row", "claim_no", "claim_date", "stockist_code", "cnf_code", "sku_code", "batch_no", "claim_type", "qty_claimed", "sold_packs", "master_expiry", "status", "original_invoice_ref"]].head(3).to_string())
