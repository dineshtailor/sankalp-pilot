"""Recompute every number on the slides from the cleaned extracts and fail on any mismatch.
Also measures the 'before' state for the before-and-after report.
Run after 03-18:  python -m analysis.19_evidence_map   Writes analysis/evidence_map.json and updates findings.json."""
import json
import subprocess
import sys

import pandas as pd

import config as C
from agent import data as d
from agent import reports as rp
from agent import tools as T
from analysis_helpers import fq

s, c, st, sk = d.sales().copy(), d.claims(), d.stock(), d.skus()
f = pd.read_pickle("analysis/claims_flagged.pkl")
F = json.load(open("analysis/findings.json"))
s["gross"] = s.invoiced_qty * s.pts_inr
s["foc"] = s.free_qty * s.pts_inr
s["q"] = fq(s.invoice_date)
L0, L1 = pd.Timestamp("2025-10-01"), pd.Timestamp("2026-09-30")
s12 = s[s.invoice_date.between(L0, L1)]
f12 = f[f.claim_date.between(L0, L1)]
exp12 = f12[f12.claim_type.isin(["Near expiry", "Expired"])]
live = f12[f12.status != "Rejected"]
cr = lambda x: f"₹{x / 1e7:.2f} cr"
lk = lambda x: f"₹{x / 1e5:.1f} lakh"
rows = []


def add(slides, label, shown, actual, source, script):
    rows.append({"slides": slides, "number": label, "shown": shown, "recomputed": str(actual), "ok": shown == str(actual), "source": source, "script": script})


# ---- fill rate
line = s.groupby(["invoice_no", "sku_code"]).agg(q=("q", "first"), inv=("invoiced_qty", "sum"), ord=("ordered_qty", "sum"), blank=("batch_no", lambda x: (x == "").any()))
fill = line.groupby("q").inv.sum() / line.groupby("q").ord.sum() * 100
ok_l = line[~line.blank]
partial = ok_l.groupby("q").inv.sum() / ok_l.groupby("q").ord.sum() * 100
partial = partial[[q for q in partial.index if q >= "FY26"]]
qg, qf = s.groupby("q").gross.sum(), s.groupby("q").foc.sum()
cq = f.assign(q=fq(f.claim_date)).groupby("q").claim_value_inr.sum() / qg * 100
add("2, 3", "Fill rate Q1 FY27", "85.3%", f"{fill['FY27Q1']:.1f}%", "primary_sales: invoiced / ordered, Apr–Jun 26", "01_reconcile")
add("3", "Fill rate Q1 FY25 → Q2 FY27", "95% → 80%", f"{fill['FY25Q1']:.0f}% → {fill['FY27Q2']:.0f}%", "primary_sales: same method", "01_reconcile")
add("3", "Fill rate Q1 FY26 (QBR: 99.5%)", "91.7%", f"{fill['FY26Q1']:.1f}%", "primary_sales; QBR Doc 6 §1", "01_reconcile")
add("3", "Partly filled lines since FY26", "92–93%", f"{partial.min():.0f}–{partial.max():.0f}%", "primary_sales: lines with supply", "02_fillrate_defs")
add("3", "Claims % of primary, Q2 FY25 → Q2 FY27", "0.64% → 3.3%", f"{cq['FY25Q2']:.2f}% → {cq['FY27Q2']:.1f}%", "expiry_claims ÷ primary_sales", "01_reconcile")
add("3", "FOC % of primary, Q3 FY25", "4.95%", f"{qf['FY25Q3'] / qg['FY25Q3'] * 100:.2f}%", "primary_sales free_qty × PTS", "01_reconcile")
add("3, 12", "Sales rows, raw → clean", "93,809 → 93,064", f"{d.QUALITY['primary_sales']['raw_rows']:,} → {len(s):,}", "745 exact duplicates removed", "00_sanity")
add("3, 12", "Claim rows, raw → clean", "4,526 → 4,503", f"{d.QUALITY['expiry_claims']['raw_rows']:,} → {len(c):,}", "23 exact duplicates removed", "00_sanity")

# ---- expiry and schemes
schemes = set(rp.scheme_skus())
add("2", "Expiry claims logged, L12M", "₹5.46 cr", cr(exp12.value.sum()), "expiry_claims: NE + Expired, Oct 25–Sep 26", "07_sizing")
add("2", "Expiry claims % of primary", "2.7%", f"{exp12.value.sum() / s12.gross.sum() * 100:.1f}%", "÷ primary_sales L12M", "07_sizing")
add("2", "Scheme SKUs", "15", len(schemes), "primary_sales scheme_code; Doc 2 Annex B", "05_supply")
add("2", "Scheme SKUs' share of primary", "61%", f"{s12[s12.sku_code.isin(schemes)].gross.sum() / s12.gross.sum() * 100:.0f}%", "primary_sales L12M", "05_supply")
ex = exp12[exp12.status != "Rejected"]
add("2, 4", "Scheme SKUs' share of expiry claims", "95%", f"{ex[ex.sku_code.isin(schemes)].value.sum() / ex.value.sum() * 100:.0f}%", "expiry_claims L12M", "05_supply")
cc = rp.circular_check(); rr = pd.DataFrame(cc["rows"]).dropna(subset=["scheme_claimback_pct"]); drop = [r for r in cc["rows"] if r.get("decision") == "DROP"]
add("4", "Claim-back, scheme vs without", "3–9% vs 1–8%", f"{rr.scheme_claimback_pct.min():.0f}–{rr.scheme_claimback_pct.max():.0f}% vs {rr.non_scheme_claimback_pct.min():.0f}–{rr.non_scheme_claimback_pct.max():.0f}%", "claims pro rata to invoice lines, expired batches", "11_scheme_sku")
add("5, 9", "SKUs recommended DROP", "8", len(drop), "circular_check rule, config.py", "12_modules")
add("4, 5", "FOC below 1.5× minimum, L12M", "₹1.05 cr", cr(rp.moq_breach()["foc_inr"]), "primary_sales; Doc 2 Annex B (lenient reading)", "18_voice_followups")
fy26 = s[s.q.str.startswith("FY26")]
add("5", "Month 1 share of quarter, FY26", "23%", f"{fy26[((fy26.invoice_date.dt.month - 4) % 3) == 0].gross.sum() / fy26.gross.sum() * 100:.0f}%", "primary_sales; Doc 6 §1.1", "19_evidence_map")
win = s[s.invoice_date.dt.month.isin([3, 6, 9, 12]) & (s.invoice_date.dt.day >= 22)].groupby("q").net_value_inr.sum() / s.groupby("q").net_value_inr.sum() * 100
win = win[[q for q in win.index if q >= "FY25Q3"]]
add("7", "Quarter billed in 9-day window, since Q3 FY25", "25–35%", f"{win.min():.0f}–{win.max():.0f}%", "primary_sales, 22nd to month-end", "05_supply")

# ---- allocation and stock
snap = st[st.snapshot_date == st.snapshot_date.max()]
oh = st.groupby(["snapshot_date", "cnf_code"]).qty_on_hand_packs.sum()
ow = st.drop_duplicates(["snapshot_date", "cnf_code", "sku_code"]).groupby(["snapshot_date", "cnf_code"]).avg_monthly_outward_packs.sum()
cov = (oh / ow).unstack()
k = cov.loc["2026-04-30":, "CF-E01"]
add("2, 4", "Lucknow cover, 30-Sep-26", "0.24 months", f"{cov['CF-N02'].iloc[-1]:.2f} months", "cnf_stock_snapshot", "05_supply")
add("2", "Lucknow SKUs at zero", "23", int(((snap[snap.cnf_code == "CF-N02"].groupby("sku_code").qty_on_hand_packs.sum()) == 0).sum()), "cnf_stock_snapshot 30-Sep-26", "05_supply")
add("2, 4", "Kolkata cover Apr–Sep; 30-Sep", "3.5–6.5; 3.8", f"{k.min():.1f}–{k.max():.1f}; {k.iloc[-1]:.1f}", "cnf_stock_snapshot", "05_supply")
o = s[s.ordered_qty.notna()]
sh = lambda g: g.groupby("cnf_code").ordered_qty.sum() / g.ordered_qty.sum() * 100
a, b = sh(o[o.invoice_date < "2025-04-01"]), sh(o[o.invoice_date >= "2026-04-01"])
add("4, 6", "Lucknow demand share, FY25 → H1 FY27", "15.3 → 20.7%", f"{a['CF-N02']:.1f} → {b['CF-N02']:.1f}%", "primary_sales ordered_qty", "05_supply")
add("6", "Kolkata demand share, FY25 → H1 FY27", "17.9 → 13.0%", f"{a['CF-E01']:.1f} → {b['CF-E01']:.1f}%", "primary_sales ordered_qty", "05_supply")
add("6", "New UP stockists", "6", int(d.stockists().appointed_on.notna().sum()), "stockist_master appointed_on", "17_voice_tests")
rb = rp.rebalance()
add("6, 9", "Return-to-CDC moves; value", "26; ₹79.5 lakh", f"{len(rb['moves'])}; {lk(rb['total_value_inr'])}", "cnf_stock_snapshot 30-Sep-26", "12_modules")
add("1, 2, 4, 10", "Revenue protected a year (50% assumption)", "₹6.53 cr", cr(F["P3_rebalance"]["inr_per_year_revenue_protected"]), "Apr–Sep 26 snapshots × unsupplied North lines", "08_rebalance")
x = s[(s.batch_no != "") & (s.invoice_date >= "2026-03-01")].copy()
x["e"] = x.batch_no.map(d.batches().expiry_date); x["ym"] = x.invoice_date.dt.to_period("M")
x["m"] = x.groupby(["cnf_code", "sku_code", "ym"]).e.transform("min")
pf = (((x.e > x.m) * x.invoiced_qty).groupby([x.ym, x.cnf_code]).sum() / x.groupby([x.ym, x.cnf_code]).invoiced_qty.sum() * 100).unstack()
oth = pf.drop(columns="CF-E01")
add("4", "Newer-batch packs, Kolkata vs others, Mar–Sep", "64–79% vs 10–56%", f"{pf['CF-E01'].min():.0f}–{pf['CF-E01'].max():.0f}% vs {oth.min().min():.0f}–{oth.max().max():.0f}%", "primary_sales × batch_master", "06_fefo_risk")
sl = rp.stranded_lots(); sr = pd.DataFrame(sl["rows"])
add("4, 6, 10", "Stranded lots; value", "7; ₹11.8 lakh", f"{len(sr)}; {lk(sr.value_inr.sum())}", "cnf_stock_snapshot + primary_sales", "18_voice_followups")
add("4, 6", "Cardio and Pain share of stranded", "92%", f"{sr[sr.therapy_area.isin(['Cardio-metabolic', 'Pain and inflammation'])].value_inr.sum() / sr.value_inr.sum() * 100:.0f}%", "sku_master therapy area", "18_voice_followups")
add("6", "First stranded lot blocked", "1 Mar 2027", pd.Timestamp(sr.blocked_from.min()).strftime("%-d %b %Y").replace("-", "") if False else f"{pd.Timestamp(sr.blocked_from.min()).day} {pd.Timestamp(sr.blocked_from.min()).strftime('%b %Y')}", "batch_master expiry − 60 days (§7.2)", "18_voice_followups")

# ---- claims
dup, late, over = live[live.dup_same_qty], live[live.window_expired_too_late], live[live.cumulative_over_invoiced]
P1 = F["P1_claim_leakage"]
add("2, 4", "Repeat / late / over-quantity claims", "58 / 41 / 21", f"{len(dup)} / {len(late)} / {len(over)}", "expiry_claims × primary_sales, L12M", "03_claims")
add("4", "Unique failing claims", "109", P1["unique_claims"], "each claim counted once", "07_sizing")
add("11", "Repeat claims already credited", "46", int((dup.status == "Credited").sum()), "expiry_claims status", "07_sizing")
add("4", "Repeat claims with no invoice ref", "55%", f"{f[f.dup_same_qty].no_invoice_ref.mean() * 100:.0f}%", "expiry_claims, all periods", "17_voice_tests")
add("4, 10", "Stop bad claims", "₹21.1 lakh", lk(P1["inr_per_year"]), "§5.2, §5.5, §5.6 failures, L12M", "07_sizing")
pend = f[f.status == "Pending"]
add("4", "Pending claims; value", "360; ₹95.9 lakh", f"{len(pend)}; {lk(pend.value.sum())}", "expiry_claims status = Pending", "07_sizing")
crd = f12[f12.status == "Credited"]
tat = (crd.credit_note_date - crd.claim_date).dt.days
add("4", "Claim-to-CN days, L12M mean", "45", f"{tat.mean():.0f}", "expiry_claims dates; policy 30 (§5.6)", "07_sizing")
add("4", "Breakage a year; % of primary", "₹3.5 lakh; 0.018%", f"{lk(f12[f12.claim_type == 'Breakage in transit'].value.sum())}; {f12[f12.claim_type == 'Breakage in transit'].value.sum() / s12.gross.sum() * 100:.3f}%", "expiry_claims Breakage", "07_sizing")

# ---- money: count each rupee once
bad = f[(f.status != "Rejected") & (f.dup_same_qty | f.window_expired_too_late)]
x2 = rp._claimback().copy()
net_c = c[c.claim_type.isin(["Near expiry", "Expired"]) & (c.status != "Rejected") & ~c.claim_no.isin(bad.claim_no)].groupby(["stockist_code", "batch_no"]).qty_claimed.sum()
x2["pair_net"] = pd.MultiIndex.from_arrays([x2.stockist_code, x2.batch_no]).map(net_c).fillna(0).to_numpy()
x2["net"] = x2.pair_net * x2.packs / x2.groupby(["stockist_code", "batch_no"]).packs.transform("sum")
last12 = x2.invoice_date > L1 - pd.DateOffset(months=12)
net = 0.0
for r in drop:
    y = x2[x2.sku_code == r["sku_code"]]; dn = y[y.done]; a_, b_ = dn[dn.on_scheme], dn[~dn.on_scheme]
    net += max(a_.net.sum() / a_.packs.sum() - b_.net.sum() / b_.packs.sum(), 0) * y[last12.loc[y.index] & y.on_scheme].packs.sum() * float(sk.pts_inr[r["sku_code"]])
net = round(net)
capx = F["P2_scheme_driven_expiry"]["foc_over_3pct_cap_l12m_inr"]
dfoc = sum(r["foc_cost_l12m_inr"] for r in drop)
F["P2_returns_net_of_bad_claims_inr"] = net
add("10", "Excess returns, net of bad claims", "₹80.9 lakh", lk(net), "8 DROP SKUs; claims in lever 1 removed", "19_evidence_map")
add("10", "FOC above the 3% cap", "₹68.3 lakh", lk(capx), "primary_sales by quarter; §4.4", "07_sizing")
add("4", "Scheme saving; upper limit", "₹1.49 cr; ₹4.75 cr", f"{cr(net + capx)}; {cr(net + dfoc)}", "returns + cap; returns + all FOC on DROP SKUs", "19_evidence_map")
add("1, 2, 10", "Total saved a year", "₹1.70 cr", cr(P1["inr_per_year"] + net + capx), "₹21.1 lakh + ₹80.9 lakh + ₹68.3 lakh", "19_evidence_map")
add("1, 2, 10", "Of which refunds; free goods at PTS", "₹1.02 cr; ₹68.3 lakh", f"{cr(P1['inr_per_year'] + net)}; {lk(capx)}", "refund money; FOC at selling price", "19_evidence_map")
ex1, ex2 = T.claim_record("CLM-2605-04488"), T.claim_record("CLM-2505-00135")
add("10", "Example: repeat claim value", "₹26,846", f"₹{ex1['claim_value_inr']:,.0f}", "expiry_claims rows 3269, 3596", "19_evidence_map")
add("10", "Example: late claim", "112 days; ₹10,333", f"{(ex2['claim_date'] - T.batch_record(ex2['batch_no'])['expiry_date']).days} days; ₹{ex2['claim_value_inr']:,.0f}", "expiry_claims row 1785; batch_master", "19_evidence_map")
pf1302 = next(r for r in cc["rows"] if r["sku_code"] == "PFL1302")
add("10", "Example: PFL1302 claim-back", "6.9% vs 1.4%", f"{pf1302['scheme_claimback_pct']:.1f}% vs {pf1302['non_scheme_claimback_pct']:.1f}%", "claims pro rata to invoice lines", "11_scheme_sku")
add("10", "Upside: FOC on DROP SKUs", "₹3.94 cr", cr(dfoc), "includes the ₹68.3 lakh", "12_modules")

PB = F["P3_rebalance"]; PN = PB["by_cnf_inr_window"]
add("10", "North unsupplied, Apr–Sep; 50%", "₹12.23 cr; ₹6.12 cr", f"{cr(PB['unsupplied_inr_window'])}; {cr(PB['half_of_unsupplied_inr_window'])}", "primary_sales: ordered − invoiced × PTS", "08_rebalance")
add("10", "Coverable from surplus; Lucknow; Gurugram", "₹3.27 cr; ₹2.60 cr; ₹0.67 cr", f"{cr(PB['movable_inr_in_window'])}; {cr(PN['CF-N02'])}; {cr(PN['CF-N01'])}", "cnf_stock_snapshot above 2 months", "08_rebalance")
S = PB["sensitivity_inr_per_year"]
add("10 notes, 12", "Sales protected if 10 / 25 / 75 / 100% is real", "₹2.29 / 4.80 / 7.90 / 8.95 cr", f"₹{S['10'] / 1e7:.2f} / {S['25'] / 1e7:.2f} / {S['75'] / 1e7:.2f} / {S['100'] / 1e7:.2f} cr", "same method, changing only the 50%", "08_rebalance")
qq = s12.groupby("q")[["gross", "foc"]].sum()
add("10", "Free goods; % of sales; quarters over cap", "₹6.63 cr; 3.29%; 3 of 4", f"{cr(s12.foc.sum())}; {s12.foc.sum() / s12.gross.sum() * 100:.2f}%; {int((qq.foc > 0.03 * qq.gross).sum())} of {len(qq)}", "primary_sales L12M; §4.4", "07_sizing")
rem = exp12.value.sum() - P1["inr_per_year"] - net
add("10", "Expiry % after levers; gap to 1%", "2.21%; ₹2.43 cr", f"{rem / s12.gross.sum() * 100:.2f}%; {cr(rem - 0.01 * s12.gross.sum())}", "expiry claims less levers 1 and 2", "19_evidence_map")

# ---- pilot
chk = list(pd.read_csv("checks/check_set.csv").itertuples())
res = pd.read_csv("checks/check_results.csv")
add("9", "Check set; routed to a person", "20 / 20; 5", f"{int(res['pass'].sum())} / {len(res)}; {sum(1 for r in chk if r.expected_decision == 'NEEDS_PERSON')}", "checks/check_results.csv", "checks/run_checks")
n = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], capture_output=True, text=True, env={**__import__("os").environ, "OPENROUTER_API_KEY": ""}).stdout
tests = [ln for ln in n.splitlines() if "tests collected" in ln or " collected" in ln]
add("9", "Automated tests", "65", tests[0].split()[0] if tests else sum("::" in ln for ln in n.splitlines()), "tests/", "pytest")
e = T.check_claim_line({"stockist_code": "STK0110", "batch_no": "K2430146", "qty": 705, "claim_type": "Expired", "claim_date": "2026-10-15"})
add("9", "EML-017 claimed vs invoiced", "705 vs 441", f"705 vs {T.supply_of_batch_to_stockist('STK0110', 'K2430146')['packs_incl_free']:.0f}", "primary_sales rows 31143, 32812", "tests")
add("9", "Neha's duplicate, packs", "272", f"{T.claim_record('CLM-2605-04488')['qty_claimed']:.0f}", "expiry_claims rows 3269, 3596", "tests")

# ---- the 'before' state, measured
pending = c[c.status == "Pending"]
out = []
for r in pending.itertuples():
    q = T.check_claim_line({"claim_no": r.claim_no, "stockist_code": r.stockist_code, "batch_no": r.batch_no, "sku_code": r.sku_code, "qty": r.qty_claimed, "claim_type": r.claim_type,
                            "claim_date": r.claim_date, "invoice_ref": r.original_invoice_ref, "cnf_code": r.cnf_code, "expiry_as_claimed": r.expiry_date_as_claimed})
    out.append((q["decision"], q["value_inr"] or 0))
pp = pd.DataFrame(out, columns=["d", "v"]).groupby("d").v.agg(["size", "sum"])
noinv = F["P1_no_invoice_ref_l12m"]
remaining = exp12.value.sum() - P1["inr_per_year"] - net
ba = {"pending_triage": {k: {"claims": int(v["size"]), "inr": round(v["sum"])} for k, v in pp.iterrows()},
      "tat_mean": round(float(tat.mean()), 1), "tat_over_30_pct": round(float((tat > 30).mean() * 100), 1), "no_invoice_claims": noinv["claims"], "no_invoice_inr": noinv["inr"],
      "no_invoice_matched": noinv["matched_to_sales_by_stockist_batch"], "expiry_now_pct": round(exp12.value.sum() / s12.gross.sum() * 100, 2),
      "expiry_after_pct": round(remaining / s12.gross.sum() * 100, 2), "primary_l12m": round(s12.gross.sum()), "gap_to_1pct_inr": round(remaining - 0.01 * s12.gross.sum()),
      "foc_now_pct": round(s12.foc.sum() / s12.gross.sum() * 100, 2), "foc_after_moq_pct": round((s12.foc.sum() - rp.moq_breach()["foc_inr"]) / s12.gross.sum() * 100, 2)}
json.dump({"rows": rows, "before_after": ba}, open("analysis/evidence_map.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(F, open("analysis/findings.json", "w"), indent=1, default=float)
bad_rows = [r for r in rows if not r["ok"]]
print(f"{len(rows) - len(bad_rows)} of {len(rows)} slide numbers reproduce"); print(json.dumps(ba, indent=0))
for r in bad_rows:
    print("MISMATCH", r["slides"], r["number"], "shown", r["shown"], "actual", r["recomputed"])
sys.exit(1 if bad_rows else 0)
