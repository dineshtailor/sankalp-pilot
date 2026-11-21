"""Module B (Supply Chain) and Module C (Sales) reports. Plain pandas, no model.

There is no secondary-sales data (CE-BRF-2026-07 §3), so stockist stock is ESTIMATED from primary
purchases. The method is stated on screen and every estimate shows the rows behind it.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

import config as C
from agent import data as d
from agent import rules as R

# Our assumptions (not policy) are named here so the panel can challenge them.
ASSUMED_WORKING_STOCK_MONTHS = 1.0   # a stockist normally carries ~1 month of working stock
LOOKBACK_MONTHS = 6                  # purchases window used for the excess estimate
BASELINE_MONTHS = 12                 # window for average monthly offtake


@lru_cache(maxsize=1)
def _monthly():
    s = d.sales()
    m = s.assign(month=s.invoice_date.dt.to_period("M"), packs=s.invoiced_qty + s.free_qty)
    return m.groupby(["stockist_code", "sku_code", "month"]).agg(packs=("packs", "sum"), paid=("invoiced_qty", "sum"),
                                                                  free=("free_qty", "sum"), rows=("src_row", list))


def scheme_skus(tier: str | None = None) -> list[str]:
    s = d.sales()
    sc = s[s.scheme_code.str.startswith("QS-")]
    latest = sc.scheme_code.str[:9].max()  # e.g. QS-FY27Q2
    cur = sc[sc.scheme_code.str.startswith(latest)]
    if tier:
        cur = cur[cur.scheme_code.str.endswith("-" + tier)]
    return sorted(cur.sku_code.unique())


def stockist_cover(stockist_code: str, sku_code: str, as_of: str = C.DATA_CUTOFF) -> dict:
    """Estimated months of stock at a stockist for one SKU, from primary purchases and claims."""
    as_of_p = pd.Timestamp(as_of).to_period("M")
    m = _monthly()
    key = (d.norm_code(stockist_code), d.norm_sku(sku_code))
    try:
        g = m.loc[key]
    except KeyError:
        return {"months_of_cover": None, "reason": "No purchases of this SKU by this stockist"}
    g = g[g.index <= as_of_p]
    base_win = g[g.index > as_of_p - BASELINE_MONTHS]
    look = g[g.index > as_of_p - LOOKBACK_MONTHS]
    c = d.claims()
    cl = c[(c.stockist_code == key[0]) & (c.sku_code == key[1]) & (c.claim_date <= pd.Timestamp(as_of))
           & (c.claim_date > pd.Timestamp(as_of) - pd.DateOffset(months=BASELINE_MONTHS)) & (c.status != "Rejected")]
    returned = float(cl.qty_claimed.sum())
    baseline = max((base_win.packs.sum() - returned) / BASELINE_MONTHS, 0.0)
    if baseline <= 0:
        return {"months_of_cover": None, "reason": "No baseline offtake in the last 12 months"}
    excess = max(look.packs.sum() - LOOKBACK_MONTHS * baseline, 0.0)
    cover = ASSUMED_WORKING_STOCK_MONTHS + excess / baseline
    rows = [r for lst in look.rows for r in lst]
    return {"months_of_cover": round(cover, 2), "baseline_monthly_packs": round(baseline, 1),
            "purchases_last_6m_packs": float(look.packs.sum()), "free_last_6m_packs": float(look.free.sum()),
            "returned_last_12m_packs": returned, "excess_packs": round(excess, 1),
            "evidence_rows": {"primary_sales.csv": rows[:40], "expiry_claims.csv": [int(x) for x in cl.src_row][:20]}}


def scheme_screen(as_of: str = C.DATA_CUTOFF, cnf_code: str | None = None, stockist_code: str | None = None) -> dict:
    """For the next quarter-end circular: which stockist x SKU pairs breach the §4.5 stock norm."""
    skus = scheme_skus()
    sk = d.skus()
    st = d.stockists()
    if stockist_code:
        st = st[st.stockist_code == d.norm_code(stockist_code)]
    if cnf_code:
        st = st[st.cnf_code == d.norm_cnf(cnf_code)]
    out = []
    for stk in st.stockist_code:
        for sku in skus:
            r = stockist_cover(stk, sku, as_of)
            if r.get("months_of_cover") is None:
                continue
            chk = R.scheme_allowed(r["months_of_cover"])
            out.append({"stockist_code": stk, "stockist_name": st.loc[stk, "stockist_name"], "cnf_code": st.loc[stk, "cnf_code"],
                        "sku_code": sku, "product": sk.loc[sku, "product_description"], "decision": "WITHHOLD" if chk["status"] == R.FAIL else "OK",
                        "excess_value_inr": round(r["excess_packs"] * sk.loc[sku, "pts_inr"], 2), **r, "rule": chk})
    df = pd.DataFrame(out)
    if df.empty:
        return {"rows": [], "summary": {"pairs": 0}}
    df = df.sort_values(["decision", "excess_value_inr"], ascending=[False, False])
    w = df[df.decision == "WITHHOLD"]
    return {"as_of": as_of, "scheme_skus": skus,
            "summary": {"pairs": len(df), "withhold": len(w), "excess_value_inr": round(w.excess_value_inr.sum(), 2)},
            "method": f"Est. cover = {ASSUMED_WORKING_STOCK_MONTHS} month working stock + (purchases incl. free in last {LOOKBACK_MONTHS} months - {LOOKBACK_MONTHS} x baseline) / baseline; baseline = (last {BASELINE_MONTHS} months purchases - packs claimed back) / {BASELINE_MONTHS}. Estimate from primary only: no secondary data exists.",
            "clause": C.CLAUSES["stock_norm"], "rows": df.to_dict("records")}


@lru_cache(maxsize=1)
def _claimback():
    """Expiry claims attributed pro rata to each invoice line of the same stockist + batch (outcome known only for
    batches that have expired by the data cut-off). Returns line-level frame."""
    s, c, b = d.sales(), d.claims(), d.batches()
    s = s[s.batch_no != ""].copy()
    s["packs"] = s.invoiced_qty + s.free_qty
    tot = s.groupby(["stockist_code", "batch_no"]).packs.transform("sum")
    ex = c[c.claim_type.isin(["Near expiry", "Expired"]) & (c.status != "Rejected")].groupby(["stockist_code", "batch_no"]).qty_claimed.sum()
    s["pair_claim"] = pd.MultiIndex.from_arrays([s.stockist_code, s.batch_no]).map(ex).fillna(0).to_numpy()
    s["claimed_attr"] = s.pair_claim * s.packs / tot
    s["done"] = s.batch_no.map(b.expiry_date) <= pd.Timestamp(C.DATA_CUTOFF)
    s["on_scheme"] = s.scheme_code != ""
    return s


def circular_check(skus: list[str] | None = None) -> dict:
    """Module C for the NSM before signing a quarter-end circular (CO-POL-014 §4.3-4.5, Annexure B).
    Per SKU: scheme-lot claim-back vs non-scheme claim-back, last-12-month FOC cost and expected returns."""
    s = _claimback()
    sk = d.skus()
    skus = [d.norm_sku(x) for x in (skus or scheme_skus())]
    l12 = s.invoice_date > pd.Timestamp(C.DATA_CUTOFF) - pd.DateOffset(months=12)
    rows = []
    for sku in skus:
        if sku not in sk.index:
            rows.append({"sku_code": sku, "decision": "NOT FOUND", "reason": "SKU not in sku_master"})
            continue
        x = s[s.sku_code == sku]
        dn = x[x.done]
        sch, ns = dn[dn.on_scheme], dn[~dn.on_scheme]
        r_s = sch.claimed_attr.sum() / sch.packs.sum() * 100 if sch.packs.sum() else None
        r_n = ns.claimed_attr.sum() / ns.packs.sum() * 100 if ns.packs.sum() else None
        pts = float(sk.loc[sku, "pts_inr"])
        last = x[l12.loc[x.index] & x.on_scheme]
        foc12 = float((last.free_qty * pts).sum())
        exp_ret = ((r_s or 0) - (r_n or 0)) / 100 * float(last.packs.sum()) * pts if r_s is not None else None
        if r_s is None or sch.packs.sum() < 1000:
            dec, why = "NEEDS PERSON", "Not enough expired scheme lots to judge"
        elif r_s >= C.SCHEME_DROP_CLAIMBACK_PCT and r_s >= C.SCHEME_DROP_MULTIPLE * (r_n or 0):
            dec, why = "DROP", f"Scheme lots come back at {r_s:.1f}% vs {r_n or 0:.1f}% without scheme"
        else:
            dec, why = "KEEP", f"Scheme-lot claim-back {r_s:.1f}% (non-scheme {r_n or 0:.1f}%)"
        rows.append({"sku_code": sku, "product": sk.loc[sku, "product_description"], "therapy_area": sk.loc[sku, "therapy_area"],
                     "scheme_claimback_pct": None if r_s is None else round(r_s, 2), "non_scheme_claimback_pct": None if r_n is None else round(r_n, 2),
                     "scheme_packs_expired_batches": float(sch.packs.sum()), "foc_cost_l12m_inr": round(foc12),
                     "excess_returns_l12m_inr": None if exp_ret is None else round(max(exp_ret, 0)),
                     "decision": dec, "reason": why,
                     "evidence": {"primary_sales.csv rows (scheme lines, L12M)": len(last), "method": "expiry claims attributed pro rata to invoice lines of the same stockist and batch; batches expired by 30-09-2026 only"}})
    drop = [r for r in rows if r.get("decision") == "DROP"]
    s12 = s[l12]
    gross = float((s12.invoiced_qty * s12.pts_inr).sum())
    foc = float((s12.free_qty * s12.pts_inr).sum())
    return {"rows": rows, "clause": "CO-POL-014 §4.3 (NSM approves), §4.4 cap, §4.5 stock norm; thresholds in config.py",
            "summary": {"skus": len(rows), "drop": len(drop),
                        "saving_if_dropped_inr_per_year": round(sum((r["foc_cost_l12m_inr"] or 0) + (r["excess_returns_l12m_inr"] or 0) for r in drop)),
                        "foc_share_of_primary_l12m_pct": round(foc / gross * 100, 2), "cap_pct": C.SCHEME_CAP_SHARE * 100},
            "watchlist": stockist_watchlist()}


@lru_cache(maxsize=1)
def stockist_watchlist(top: int = 15) -> list[dict]:
    """Stockist x SKU pairs with the highest claim-back on scheme lots: RSMs check stock before accepting POB (§4.5)."""
    s = _claimback()
    dn = s[s.done & s.on_scheme]
    g = dn.groupby(["stockist_code", "sku_code"]).agg(packs=("packs", "sum"), claimed=("claimed_attr", "sum"), rows=("src_row", list))
    g = g[g.packs >= 200]
    g["claimback_pct"] = (g.claimed / g.packs * 100).round(1)
    g = g.sort_values("claimback_pct", ascending=False).head(top).reset_index()
    st = d.stockists()
    return [{"stockist_code": r.stockist_code, "name": st.loc[r.stockist_code, "stockist_name"], "cnf_code": st.loc[r.stockist_code, "cnf_code"],
             "sku_code": r.sku_code, "scheme_packs": float(r.packs), "claimback_pct": r.claimback_pct,
             "evidence_rows": {"primary_sales.csv": [int(x) for x in r.rows[:20]]}} for r in g.itertuples()]


def rebalance(as_of: str | None = None) -> dict:
    """Module B: per SKU, CFAs above 2 months cover (donors) vs CFAs short (recipients); FEFO signal by CFA."""
    st = d.stock()
    snap_date = st.snapshot_date.max() if as_of is None else pd.Timestamp(as_of)
    snap = st[st.snapshot_date == snap_date]
    sk = d.skus()
    oh = snap.groupby(["cnf_code", "sku_code"]).agg(on_hand=("qty_on_hand_packs", "sum"), rows=("src_row", list))
    outw = snap.drop_duplicates(["cnf_code", "sku_code"]).set_index(["cnf_code", "sku_code"]).avg_monthly_outward_packs
    oh["outward"] = outw.reindex(oh.index).fillna(0)
    oh["cover"] = (oh.on_hand / oh.outward.where(oh.outward > 0)).round(2)
    oh = oh.reset_index()
    moves, table = [], []
    for sku, g in oh.groupby("sku_code"):
        donors = g[g.cover > C.REPLENISH_TARGET_MONTHS].copy()
        donors["excess"] = donors.on_hand - C.REPLENISH_TARGET_MONTHS * donors.outward
        recips = g[(g.cover.fillna(0) < 1.0) & (g.outward > 0)].copy()
        recips["need"] = 1.0 * recips.outward - recips.on_hand  # bring to 1 month cover
        pool = donors.excess.sum()
        for r in recips.sort_values("cover").itertuples():
            qty = min(r.need, pool)
            if qty <= 0:
                break
            pool -= qty
            moves.append({"sku_code": sku, "product": sk.loc[sku, "product_description"], "to_cnf": r.cnf_code,
                          "to_cover_months": r.cover, "from_cnfs": ", ".join(f"{x.cnf_code} ({x.cover}m)" for x in donors.itertuples()),
                          "packs": round(qty), "value_inr": round(qty * sk.loc[sku, "pts_inr"], 2),
                          "evidence_rows": {"cnf_stock_snapshot.csv": [int(x) for x in r.rows] + [int(x) for d_ in donors.rows for x in d_]},
                          "action": "Return-to-CDC then re-dispatch (SC-AGR-CF-003 Sch.2 2.5): Head SC approves"})
    by_cnf = oh.groupby("cnf_code").agg(on_hand=("on_hand", "sum"), outward=("outward", "sum"))
    by_cnf["cover_months"] = (by_cnf.on_hand / by_cnf.outward).round(2)
    by_cnf["skus_zero_stock"] = oh[oh.on_hand == 0].groupby("cnf_code").size().reindex(by_cnf.index).fillna(0).astype(int)
    return {"snapshot_date": str(snap_date.date()), "moves": sorted(moves, key=lambda x: -x["value_inr"]),
            "total_value_inr": round(sum(m["value_inr"] for m in moves), 2),
            "cnf_cover": by_cnf.reset_index().to_dict("records"), "fefo": fefo_signal(),
            "allocation": allocation_shares(), "clause": C.CLAUSES["return_cdc"]}


@lru_cache(maxsize=1)
def fefo_signal(months: int = 3) -> list[dict]:
    """Share of packs shipped from a newer batch while an older batch of the same SKU shipped in the same month (proxy)."""
    s = d.sales()
    s = s[s.batch_no != ""].copy()
    s["exp"] = s.batch_no.map(d.batches().expiry_date)
    s["ym"] = s.invoice_date.dt.to_period("M")
    end = s.ym.max()
    s = s[s.ym > end - months]
    s["min_exp"] = s.groupby(["cnf_code", "sku_code", "ym"]).exp.transform("min")
    s["newer"] = s.exp > s.min_exp
    s["rsl"] = (s.exp - s.invoice_date).dt.days / (s.sku_code.map(d.skus().shelf_life_months) * 30.44)
    g = s.groupby("cnf_code")
    out = pd.DataFrame({"fefo_breach_proxy_pct": (s.invoiced_qty * s.newer).groupby(s.cnf_code).sum() / g.invoiced_qty.sum() * 100,
                        "low_rsl_packs_pct": (s.invoiced_qty * (s.rsl < C.MIN_RSL_SHARE_AT_INVOICE)).groupby(s.cnf_code).sum() / g.invoiced_qty.sum() * 100})
    out = out.round(1).reset_index()
    med = out.fefo_breach_proxy_pct.median()
    out["flag"] = out.fefo_breach_proxy_pct > 1.5 * med
    return out.to_dict("records")


@lru_cache(maxsize=1)
def allocation_shares() -> list[dict]:
    """Demand share (orders) vs supply share by CFA: FY25 vs last 6 months."""
    s = d.sales()
    first = s[s.ordered_qty.notna()]
    rec = s.invoice_date >= s.invoice_date.max() - pd.DateOffset(months=6)
    fy25 = s.invoice_date < "2025-04-01"
    res = []
    for cnf in sorted(s.cnf_code.unique()):
        def share(mask, col, frame):
            f = frame[mask.reindex(frame.index, fill_value=False)]
            return round(f.loc[f.cnf_code == cnf, col].sum() / f[col].sum() * 100, 1)
        res.append({"cnf_code": cnf, "demand_share_fy25": share(fy25, "ordered_qty", first), "demand_share_last6m": share(rec, "ordered_qty", first),
                    "supply_share_last6m": share(rec, "invoiced_qty", s)})
    return res
