"""Charts for the notes and deck, rebuilt from the cleaned data (reproducible). Output: ../docs/charts/*.png"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from agent import data as d
from agent import reports as rp
from analysis_helpers import fq

OUT = Path(__file__).resolve().parents[2] / "docs" / "charts"
OUT.mkdir(parents=True, exist_ok=True)
NAVY, TEAL, RED, AMBER, GREY = "#0b1f3a", "#0f766e", "#b42318", "#d97706", "#94a3b8"
plt.rcParams.update({"font.family": "Calibri", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#cbd5e1", "axes.titleweight": "bold", "axes.titlesize": 11})

s, c, sk = d.sales(), d.claims(), d.skus()
s = s.assign(q=fq(s.invoice_date), gross=s.invoiced_qty * s.pts_inr, foc=s.free_qty * s.pts_inr)
c = c.assign(q=fq(c.claim_date))
first = s[s.ordered_qty.notna()]
line = s.groupby(["invoice_no", "sku_code"]).agg(q=("q", "first"), inv=("invoiced_qty", "sum"))
line["ord"] = first.groupby(["invoice_no", "sku_code"]).ordered_qty.sum()
qs = sorted(s.q.unique())

# 1. claims % primary and fill rate
fig, ax = plt.subplots(figsize=(7.2, 3.0))
cp = c.groupby("q").claim_value_inr.sum() / s.groupby("q").gross.sum() * 100
fr = line.groupby("q").inv.sum() / line.groupby("q").ord.sum() * 100
ax.plot(qs, cp.reindex(qs), color=RED, marker="o", lw=2, label="Claims logged, % of primary")
ax.set_ylabel("Claims % of primary", color=RED); ax.tick_params(axis="x", rotation=45)
ax2 = ax.twinx(); ax2.plot(qs, fr.reindex(qs), color=NAVY, marker="s", lw=2, label="Fill rate (qty), %"); ax2.set_ylabel("Fill rate %", color=NAVY)
ax2.spines["top"].set_visible(False)
ax.set_title("Short and long at the same time (primary_sales.csv, expiry_claims.csv)")
fig.legend(loc="upper center", bbox_to_anchor=(0.5, 0.02), ncol=2, frameon=False); fig.tight_layout(); fig.savefig(OUT / "kpis.png", dpi=200, bbox_inches="tight"); plt.close(fig)

# 2. scheme phasing: share of quarter primary in 22nd-end of quarter month
lastwin = s.invoice_date.dt.month.isin([3, 6, 9, 12]) & (s.invoice_date.dt.day >= 22)
ph = s[lastwin].groupby("q").net_value_inr.sum() / s.groupby("q").net_value_inr.sum() * 100
fo = s.groupby("q").foc.sum() / s.groupby("q").gross.sum() * 100
fig, ax = plt.subplots(figsize=(7.2, 2.8))
ax.bar(qs, ph.reindex(qs), color=TEAL, label="% of quarter billed in the 9-day scheme window")
ax.plot(qs, fo.reindex(qs) * 6, color=AMBER, marker="o", lw=2, label="FOC % of primary (x6 scale; cap 3% = 18)")
ax.axhline(18, color=AMBER, ls="--", lw=1); ax.tick_params(axis="x", rotation=45)
ax.set_title("Quarter-end schemes pull primary into nine days")
ax.legend(frameon=False, fontsize=8, loc="upper left"); fig.tight_layout(); fig.savefig(OUT / "schemes.png", dpi=200); plt.close(fig)

# 3. claim-back by SKU, scheme vs non-scheme
cc = pd.DataFrame(rp.circular_check()["rows"]).dropna(subset=["scheme_claimback_pct"]).sort_values("scheme_claimback_pct")
fig, ax = plt.subplots(figsize=(7.2, 3.4))
y = range(len(cc))
ax.barh([i + 0.2 for i in y], cc.scheme_claimback_pct, height=0.4, color=[RED if x == "DROP" else GREY for x in cc.decision], label="Bought on scheme")
ax.barh([i - 0.2 for i in y], cc.non_scheme_claimback_pct, height=0.4, color=NAVY, label="Bought without scheme")
ax.set_yticks(list(y)); ax.set_yticklabels([f"{a} {b[:22]}" for a, b in zip(cc.sku_code, cc["product"])], fontsize=8)
ax.set_xlabel("% of packs that came back as expiry claims (batches expired by 30-Sep-26)")
ax.set_title("Scheme lots come back as expiry (red = recommend drop)"); ax.legend(frameon=False, fontsize=8)
fig.tight_layout(); fig.savefig(OUT / "claimback.png", dpi=200); plt.close(fig)

# 4. C&F months of cover
st = d.stock()
oh = st.groupby(["snapshot_date", "cnf_code"]).qty_on_hand_packs.sum()
ow = st.drop_duplicates(["snapshot_date", "cnf_code", "sku_code"]).groupby(["snapshot_date", "cnf_code"]).avg_monthly_outward_packs.sum()
cov = (oh / ow).unstack()
fig, ax = plt.subplots(figsize=(7.2, 2.9))
for cnf, col in zip(cov.columns, [RED, GREY, NAVY, "#64748b", "#a3a3a3", "#cbd5e1"]):
    ax.plot(cov.index, cov[cnf], marker="o", ms=3, lw=2.4 if cnf in ("CF-E01", "CF-N02") else 1.2, color={"CF-E01": AMBER, "CF-N02": RED}.get(cnf, GREY), label=cnf)
ax.axhline(2, color=TEAL, ls="--", lw=1); ax.text(cov.index[0], 2.1, "target 2 months (Sch.2 2.2)", color=TEAL, fontsize=8)
ax.set_ylabel("months of cover"); ax.set_title("Kolkata long, Lucknow short (cnf_stock_snapshot.csv)"); ax.legend(ncol=6, frameon=False, fontsize=7, loc="upper left")
fig.tight_layout(); fig.savefig(OUT / "cover.png", dpi=200); plt.close(fig)

# 5. FEFO proxy by month
x = s[(s.batch_no != "") & (s.invoice_date >= "2025-07-01")].copy()
x["exp"] = x.batch_no.map(d.batches().expiry_date); x["ym"] = x.invoice_date.dt.to_period("M")
x["minexp"] = x.groupby(["cnf_code", "sku_code", "ym"]).exp.transform("min")
fe = ((x.exp > x.minexp) * x.invoiced_qty).groupby([x.ym, x.cnf_code]).sum() / x.groupby([x.ym, x.cnf_code]).invoiced_qty.sum() * 100
fe = fe.unstack(); fe.index = fe.index.astype(str)
fig, ax = plt.subplots(figsize=(7.2, 2.7))
for cnf in fe.columns:
    ax.plot(fe.index, fe[cnf], lw=2.6 if cnf == "CF-E01" else 1, color=RED if cnf == "CF-E01" else GREY, label=cnf if cnf == "CF-E01" else None)
ax.axvline("2026-02", color=NAVY, ls=":"); ax.text("2026-02", 85, " Kolkata WMS go-live", fontsize=8, color=NAVY)
ax.set_ylabel("% packs from a newer batch"); ax.set_title("FEFO breaks at Kolkata after the WMS change (grey = other C&Fs)")
ax.tick_params(axis="x", rotation=45); ax.legend(frameon=False); fig.tight_layout(); fig.savefig(OUT / "fefo.png", dpi=200); plt.close(fig)
print("charts in", OUT)
