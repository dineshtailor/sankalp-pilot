"""Tools read the data through agent/data.py. Exact facts come from here, never from the model.

Plain functions (tested without a model) plus thin @tool wrappers for the model's lookup loop.
Every record returned carries {file, row} so the screen can cite it.
"""
from __future__ import annotations

import difflib
import re

import pandas as pd
from langchain_core.tools import tool

import config as C
from agent import data as d
from agent import rules as R


def _ev(file: str, row, **values) -> dict:
    return {"file": file, "row": int(row) if row is not None else None,
            "values": {k: (str(v.date()) if isinstance(v, pd.Timestamp) else v) for k, v in values.items()}}


def _f(x):
    try:
        return None if pd.isna(x) else float(x)
    except TypeError:
        return x


# ------------------------------------------------------------------ lookups
def batch_record(batch_no: str) -> dict:
    """Batch master joined to SKU master. found=False with close matches if missing."""
    code = d.norm_code(batch_no)
    b = d.batches()
    if code not in b.index:
        close = difflib.get_close_matches(code, list(b.index), n=3, cutoff=0.8)
        return {"found": False, "batch_no": code, "close_matches": close,
                "reason": "Not in batch master (batches made before Oct 2023 were archived at ERP migration)"}
    r = b.loc[code]
    s = d.skus().loc[r.sku_code]
    return {"found": True, "batch_no": code, "sku_code": r.sku_code, "product": s.product_description, "pack": s.pack,
            "expiry_date": r.expiry_date, "mfg_date": r.mfg_date, "pts_inr": _f(s.pts_inr),
            "shelf_life_months": _f(s.shelf_life_months),
            "evidence": [_ev("batch_master.csv", r.src_row, batch_no=code, sku_code=r.sku_code, expiry_date=r.expiry_date),
                         _ev("sku_master.csv", s.src_row, sku_code=r.sku_code, pts_inr=_f(s.pts_inr), pack=s.pack)]}


def stockist_record(code: str) -> dict:
    c = d.norm_code(code)
    st = d.stockists()
    if not c or c not in st.index:
        return {"found": False, "stockist_code": c, "reason": "Stockist not in master"}
    r = st.loc[c]
    return {"found": True, "stockist_code": c, "name": r.stockist_name, "cnf_code": r.cnf_code, "city": r.city,
            "state": r.state, "evidence": [_ev("stockist_master.csv", r.src_row, stockist_code=c, name=r.stockist_name, cnf_code=r.cnf_code)]}


def supply_of_batch_to_stockist(stockist_code: str, batch_no: str) -> dict:
    """Every invoice line that carried this batch to this stockist (CO-POL-014 §5.5)."""
    s = d.sales()
    rows = s[(s.stockist_code == d.norm_code(stockist_code)) & (s.batch_no == d.norm_code(batch_no))]
    ev = [_ev("primary_sales.csv", r.src_row, invoice_no=r.invoice_no, invoice_date=r.invoice_date, cnf_code=r.cnf_code,
              invoiced_qty=r.invoiced_qty, free_qty=r.free_qty, scheme_code=r.scheme_code) for r in rows.itertuples()]
    return {"found": len(rows) > 0, "packs_incl_free": float(rows.invoiced_qty.sum() + rows.free_qty.sum()),
            "invoices": sorted(set(rows.invoice_no)), "cnfs": sorted(set(rows.cnf_code)),
            "first_invoice_date": rows.invoice_date.min() if len(rows) else None,
            "on_scheme_packs": float(rows.loc[rows.scheme_code != "", "invoiced_qty"].sum()), "evidence": ev}


def prior_claims(stockist_code: str, batch_no: str, before=None, exclude_claim_no: str | None = None) -> list[dict]:
    c = d.claims()
    m = (c.stockist_code == d.norm_code(stockist_code)) & (c.batch_no == d.norm_code(batch_no)) & (c.status != "Rejected")
    if before is not None:
        m &= c.claim_date <= pd.Timestamp(before)
    if exclude_claim_no:
        m &= c.claim_no != d.norm_code(exclude_claim_no)
    out = []
    for r in c[m].sort_values("claim_date").itertuples():
        out.append({"claim_no": r.claim_no, "claim_date": r.claim_date, "qty_claimed": _f(r.qty_claimed), "status": r.status,
                    "credit_note_no": r.credit_note_no or None, "src_row": r.src_row})
    return out


def claim_record(claim_no: str) -> dict:
    c = d.claims()
    m = c[c.claim_no == d.norm_code(claim_no)]
    if m.empty:
        return {"found": False, "claim_no": d.norm_code(claim_no), "reason": "Claim number not in the claims register"}
    r = m.iloc[0]
    return {"found": True, "claim_no": r.claim_no, "claim_date": r.claim_date, "stockist_code": r.stockist_code,
            "cnf_code": r.cnf_code, "sku_code": r.sku_code, "batch_no": r.batch_no, "claim_type": r.claim_type,
            "qty_claimed": _f(r.qty_claimed), "claim_value_inr": _f(r.claim_value_inr),
            "expiry_date_as_claimed": r.expiry_date_as_claimed, "original_invoice_ref": r.original_invoice_ref,
            "status": r.status, "credit_note_no": r.credit_note_no, "credit_note_date": r.credit_note_date,
            "remarks": r.remarks, "src_row": int(r.src_row),
            "evidence": [_ev("expiry_claims.csv", r.src_row, claim_no=r.claim_no, claim_date=r.claim_date, stockist_code=r.stockist_code,
                             batch_no=r.batch_no, qty_claimed=_f(r.qty_claimed), claim_type=r.claim_type, status=r.status)]}


def email_record(email_id: str) -> dict:
    e = d.emails()
    k = d.norm_code(email_id)
    if k not in e.index:
        return {"found": False, "email_id": k}
    r = e.loc[k]
    return {"found": True, "email_id": k, "received_date": r.received_date, "from_name": r.from_name,
            "stockist_code": r.stockist_code_by_mailbox_rule, "subject": r.subject, "body": r.body, "src_row": int(r.src_row)}


def stockist_candidates(text: str) -> list[str]:
    """Stockists whose name and city both appear in the text (suggestion only, a person confirms)."""
    t = (text or "").lower()
    return [f"{r.stockist_code} {r.stockist_name}, {r.city}" for r in d.stockists().itertuples()
            if r.stockist_name.lower() in t and r.city and r.city.lower() in t][:5]


def claims_for_stockist_batch(stockist_code: str, batch_no: str) -> list[dict]:
    return [claim_record(p["claim_no"]) for p in prior_claims(stockist_code, batch_no)]


def sku_candidates(text: str) -> list[str]:
    """Match a trade name like 'Amlo 5' or 'Panto 40' to SKU codes by name stem and strength (used only to suggest)."""
    t = (text or "").lower()
    words = re.findall(r"[a-z]+", t)
    nums = set(re.findall(r"\d+", t))
    out = []
    for r in d.skus().itertuples():
        desc = r.product_description.lower()
        stems = [w for w in words if len(w) >= 4 and w[:4] in desc]
        if stems and (not nums or any(n in re.findall(r"\d+", desc) for n in nums)):
            out.append(r.sku_code)
    return out


# ------------------------------------------------------------------ the claim checker core (one line)
def resolve_line(line: dict) -> dict:
    """Gather every fact a claim line needs, once. Returns facts with pre-checks (stockist, batch) and a `stop`
    flag when the batch cannot be identified (no further checks are meaningful)."""
    line = dict(line)
    if line.get("claim_date") is not None and not isinstance(line["claim_date"], pd.Timestamp):
        line["claim_date"] = d.parse_date(line["claim_date"])
    if line.get("qty") is not None:
        line["qty"] = d.parse_num(line["qty"])
    pre, evidence = [], []
    stk = stockist_record(line.get("stockist_code") or "")
    if not stk["found"]:
        pre.append(R._r("stockist", R.PERSON, f"Sender not matched to a stockist in the master ('{line.get('stockist_code') or 'blank'}')", "stockist"))
    else:
        evidence += stk["evidence"]
    facts = {"line": line, "pre": pre, "evidence": evidence, "bat": None, "sup": None, "pri": [], "stop": False}
    if not line.get("batch_no"):
        cands = sku_candidates(line.get("product") or "")
        pre.append(R._r("batch", R.PERSON, "No batch number given" + (f"; product looks like {', '.join(cands)}" if cands else ""), "batch_master"))
        facts["stop"] = True
        return facts
    bat = batch_record(line["batch_no"])
    if not bat["found"]:
        hint = f"; close match: {', '.join(bat['close_matches'])}" if bat["close_matches"] else ""
        pre.append(R._r("batch", R.PERSON, f"Batch {bat['batch_no']} not found in batch master{hint}", "batch_master"))
        facts["stop"] = True
        return facts
    evidence += bat["evidence"]
    pre.append(R._r("batch", R.PASS, f"{bat['batch_no']} = {bat['sku_code']} {bat['product']}, expiry {bat['expiry_date'].date()}", "batch_master"))
    if line.get("sku_code") and d.norm_sku(line["sku_code"]) != bat["sku_code"]:
        pre.append(R._r("batch", R.FAIL, f"Claimed SKU {line['sku_code']} but batch belongs to {bat['sku_code']}", "batch_master"))
    if line.get("expiry_as_claimed") is not None and pd.notna(line.get("expiry_as_claimed")):
        if pd.Timestamp(line["expiry_as_claimed"]).to_period("M") != bat["expiry_date"].to_period("M"):
            pre.append(R._r("batch", R.PERSON, f"Expiry written by stockist {pd.Timestamp(line['expiry_as_claimed']).date()} differs from master {bat['expiry_date'].date()}", "batch_master"))
    sup = supply_of_batch_to_stockist(line.get("stockist_code") or "", bat["batch_no"]) if stk["found"] else \
        {"found": False, "packs_incl_free": 0, "invoices": [], "cnfs": [], "evidence": [], "first_invoice_date": None}
    evidence += sup["evidence"][:10]
    pri = prior_claims(line.get("stockist_code") or "", bat["batch_no"], before=line.get("claim_date"), exclude_claim_no=line.get("claim_no"))
    for p in pri:
        evidence.append(_ev("expiry_claims.csv", p["src_row"], claim_no=p["claim_no"], claim_date=p["claim_date"], qty_claimed=p["qty_claimed"], status=p["status"]))
    facts.update(bat=bat, sup=sup, pri=pri)
    return facts


# Independent checks: each reads facts and returns one check. The graph runs them as parallel nodes.
def chk_window(f: dict) -> dict:
    ln = f["line"]
    return R.check_window(ln.get("claim_type") or "Near expiry", ln.get("claim_date"), f["bat"]["expiry_date"], f["sup"].get("first_invoice_date"))


def chk_quantity(f: dict) -> dict:
    ln = f["line"]
    if ln.get("unit_ok") is False:
        return R._r("quantity", R.PERSON, f"Quantity stated in another unit ('{ln.get('unit_text')}'); confirm number of packs", "qty")
    return R.check_quantity(ln.get("qty"), f["sup"]["packs_incl_free"], sum(p["qty_claimed"] or 0 for p in f["pri"]))


def chk_duplicate(f: dict) -> dict:
    return R.check_duplicate(f["line"].get("qty"), f["pri"])


def chk_invoice(f: dict) -> list[dict]:
    ln = f["line"]
    out = [R.check_invoice_ref(d.norm_invoice(ln["invoice_ref"]) if ln.get("invoice_ref") else "", f["sup"]["invoices"])]
    if ln.get("cnf_code"):
        out.append(R.check_billing_cfa(d.norm_cnf(ln["cnf_code"]), f["sup"]["cnfs"]))
    return out


PARALLEL_CHECKS = {"window": chk_window, "quantity": chk_quantity, "duplicate": chk_duplicate, "invoice": chk_invoice}


def assemble(f: dict, results: dict | None = None) -> dict:
    """Join pre-checks and parallel check results into one decision for the line."""
    checks = list(f["pre"])
    for name in PARALLEL_CHECKS:
        r = (results or {}).get(name)
        if r is None:
            continue
        checks += r if isinstance(r, list) else [r]
    line, bat = f["line"], f["bat"]
    value = R.claim_value(line.get("qty"), bat["pts_inr"]) if bat else None
    if bat and value is not None:
        checks.append(R._r("value", R.INFO, f"{line.get('qty'):g} packs x PTS {bat['pts_inr']} = INR {value:,.2f}", "value"))
    return {"line": {k: (str(v.date()) if isinstance(v, pd.Timestamp) else v) for k, v in line.items()},
            "decision": R.decide(checks), "value_inr": value, "checks": checks, "evidence": f["evidence"],
            "sku_code": bat["sku_code"] if bat else None, "product": bat["product"] if bat else None}


def check_claim_line(line: dict) -> dict:
    """Sequential version of the same pipeline (batch mode and tests). Same functions as the graph."""
    f = resolve_line(line)
    if f["stop"]:
        return assemble(f)
    return assemble(f, {k: fn(f) for k, fn in PARALLEL_CHECKS.items()})


# ------------------------------------------------------------------ model-facing tools (lookup loop for questions)
@tool
def lookup_batch(batch_no: str) -> dict:
    """Look up a batch: SKU, product, expiry date, PTS. found=False if not in the batch master."""
    return {k: (str(v.date()) if isinstance(v, pd.Timestamp) else v) for k, v in batch_record(batch_no).items()}


@tool
def lookup_claim(claim_no: str) -> dict:
    """Look up a claim in the claims register by claim number (e.g. CLM-2605-04488)."""
    r = claim_record(claim_no)
    return {k: (str(v.date()) if isinstance(v, pd.Timestamp) else v) for k, v in r.items()}


@tool
def lookup_supply(stockist_code: str, batch_no: str) -> dict:
    """Invoices and packs (incl. free) of a batch supplied to a stockist."""
    r = supply_of_batch_to_stockist(stockist_code, batch_no)
    r.pop("evidence"); r["first_invoice_date"] = str(r["first_invoice_date"])
    return r


TOOLS = [lookup_batch, lookup_claim, lookup_supply]
