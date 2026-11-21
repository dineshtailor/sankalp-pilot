"""Business rules as plain Python. Every rule cites its clause and has tests in tests/test_rules.py.

Each check returns a dict: {check, status, detail, clause}. status is one of
PASS, FAIL (policy says reject), PERSON (a named person must decide), INFO.
No check ever calls a model.
"""
from __future__ import annotations

from datetime import date

import config as C

PASS, FAIL, PERSON, INFO = "PASS", "FAIL", "PERSON", "INFO"


def _r(check: str, status: str, detail: str, clause_key: str) -> dict:
    return {"check": check, "status": status, "detail": detail, "clause": C.CLAUSES[clause_key]}


def _d(x) -> date | None:
    if x is None:
        return None
    try:
        return x.date() if hasattr(x, "date") else x
    except (ValueError, TypeError):  # NaT
        return None


def check_window(claim_type: str, claim_date, expiry_date=None, invoice_date=None) -> dict:
    """CO-POL-014 §5.2. expiry_date must come from the batch master, never from the claimant."""
    cd = _d(claim_date)
    if claim_type in ("Near expiry", "Expired"):
        ed = _d(expiry_date)
        if ed is None or cd is None:
            return _r("window", PERSON, "Expiry date not found in the batch master; cannot test the window", "window")
        days = (cd - ed).days  # negative = before expiry
        if claim_type == "Near expiry":
            if days < -C.NEAR_EXPIRY_WINDOW_BEFORE_DAYS:
                return _r("window", FAIL, f"Filed {-days} days before expiry; near-expiry window opens {C.NEAR_EXPIRY_WINDOW_BEFORE_DAYS} days before ({ed})", "window")
            if days > 0:
                if days > C.EXPIRED_WINDOW_AFTER_DAYS:
                    return _r("window", FAIL, f"Filed {days} days after expiry ({ed}); nothing accepted beyond {C.EXPIRED_WINDOW_AFTER_DAYS} days", "window")
                return _r("window", PASS, f"Batch already expired on {ed} ({days} days ago): treat as an Expired claim, within the {C.EXPIRED_WINDOW_AFTER_DAYS}-day window", "window")
            return _r("window", PASS, f"{-days} days before expiry ({ed}); inside the {C.NEAR_EXPIRY_WINDOW_BEFORE_DAYS}-day window", "window")
        # Expired
        if days < 0:
            if -days <= C.NEAR_EXPIRY_WINDOW_BEFORE_DAYS:
                return _r("window", PASS, f"Not yet expired ({ed}, {-days} days away): treat as Near expiry, inside the window", "window")
            return _r("window", FAIL, f"Batch expires {ed}, {-days} days away: too early for any expiry claim", "window")
        if days > C.EXPIRED_WINDOW_AFTER_DAYS:
            return _r("window", FAIL, f"Filed {days} days after expiry ({ed}); limit is {C.EXPIRED_WINDOW_AFTER_DAYS} days", "window")
        return _r("window", PASS, f"{days} days after expiry ({ed}); inside the {C.EXPIRED_WINDOW_AFTER_DAYS}-day window", "window")
    if claim_type in ("Breakage in transit", "Short supply"):
        idt = _d(invoice_date)
        if idt is None or cd is None:
            return _r("window", PERSON, "Invoice date not found; cannot test the 7-day window", "window")
        days = (cd - idt).days
        if days > C.TRANSIT_CLAIM_WINDOW_DAYS:
            return _r("window", FAIL, f"Filed {days} days after invoice {idt}; limit is {C.TRANSIT_CLAIM_WINDOW_DAYS} days", "window")
        return _r("window", PASS, f"Filed {days} days after invoice {idt}", "window")
    return _r("window", PERSON, f"Unknown claim type '{claim_type}'", "window")


def check_quantity(qty_claimed: float | None, packs_invoiced_incl_free: float, prior_claimed_qty: float = 0.0) -> dict:
    """CO-POL-014 §5.5: claimed (this + earlier non-rejected claims) <= packs invoiced to this stockist, incl. free."""
    if qty_claimed is None or qty_claimed <= 0:
        return _r("quantity", PERSON, "Quantity missing or not readable", "qty")
    if packs_invoiced_incl_free <= 0:
        return _r("quantity", PERSON, "No packs of this batch were invoiced to this stockist in the extract", "qty")
    total = qty_claimed + prior_claimed_qty
    if total > packs_invoiced_incl_free:
        return _r("quantity", FAIL, f"Claimed {qty_claimed:g} + earlier {prior_claimed_qty:g} = {total:g} > {packs_invoiced_incl_free:g} packs invoiced incl. free", "qty")
    return _r("quantity", PASS, f"{total:g} of {packs_invoiced_incl_free:g} packs invoiced incl. free (incl. earlier claims {prior_claimed_qty:g})", "qty")


def check_duplicate(qty_claimed: float | None, prior_claims: list[dict]) -> dict:
    """CO-POL-014 §5.6 step 3 / SC-AGR-CF-003 Sch.2 2.6(3). prior_claims: earlier non-rejected claims, same stockist + batch."""
    if not prior_claims:
        return _r("duplicate", PASS, "No earlier claim on this stockist and batch", "duplicate")
    same = [p for p in prior_claims if qty_claimed is not None and float(p.get("qty_claimed") or -1) == float(qty_claimed)]
    if same:
        p = same[0]
        return _r("duplicate", FAIL, f"Same stockist, batch and quantity as {p['claim_no']} ({p.get('status')}, CN {p.get('credit_note_no') or 'none'}); likely resubmission", "duplicate")
    ids = ", ".join(p["claim_no"] for p in prior_claims[:5])
    return _r("duplicate", PERSON, f"{len(prior_claims)} earlier claim(s) on this batch ({ids}) with different quantities: confirm these are different goods", "duplicate")


def check_invoice_ref(ref: str, invoices_for_stockist_batch: list[str]) -> dict:
    """CO-POL-014 §5.3(2) and §5.4. The tool can find the supplying invoice from the sales extract."""
    ref = (ref or "").strip()
    if ref:
        if ref in invoices_for_stockist_batch:
            return _r("invoice_ref", PASS, f"Invoice {ref} supplied this batch to this stockist", "invoice_ref")
        if invoices_for_stockist_batch:
            return _r("invoice_ref", PERSON, f"Quoted invoice {ref} did not carry this batch to this stockist; batch was supplied on {', '.join(invoices_for_stockist_batch[:3])}", "invoice_ref")
        return _r("invoice_ref", PERSON, f"Quoted invoice {ref} not found for this stockist and batch", "invoice_ref")
    if invoices_for_stockist_batch:
        return _r("invoice_ref", PASS, f"No reference quoted; supplying invoice found in sales: {', '.join(invoices_for_stockist_batch[:3])} (attach to CN)", "invoice_ref")
    return _r("invoice_ref", PERSON, "No invoice reference and no supply found: §5.4 ledger check with written Area Manager approval", "invoice_ref")


def check_billing_cfa(claim_cfa: str, billing_cfas: list[str]) -> dict:
    """CO-POL-014 §5.1: returns only at the CFA that billed the stock."""
    if not billing_cfas:
        return _r("billing_cfa", INFO, "No billing record to compare", "billing_cfa")
    if claim_cfa and claim_cfa not in billing_cfas:
        return _r("billing_cfa", FAIL, f"Claim at {claim_cfa} but stock billed by {', '.join(billing_cfas)}", "billing_cfa")
    return _r("billing_cfa", PASS, f"Billed by {', '.join(billing_cfas)}", "billing_cfa")


def claim_value(qty: float | None, pts: float | None) -> float | None:
    """CO-POL-014 §5.7: value at PTS (sku_master)."""
    if qty is None or pts is None:
        return None
    return round(qty * pts, 2)


def rsl_share(invoice_date, expiry_date, shelf_life_months: float) -> float | None:
    """Remaining shelf life as a share of total shelf life (CO-POL-014 §7.1)."""
    i, e = _d(invoice_date), _d(expiry_date)
    if i is None or e is None or not shelf_life_months:
        return None
    return (e - i).days / (shelf_life_months * 30.44)


def rsl_ok(share: float | None) -> bool | None:
    return None if share is None else share >= C.MIN_RSL_SHARE_AT_INVOICE


def scheme_allowed(months_of_cover: float | None) -> dict:
    """CO-POL-014 §4.5: no scheme to a stockist holding > 2.5 months of the SKU."""
    if months_of_cover is None:
        return _r("stock_norm", PERSON, "Not enough purchase history to estimate stock", "stock_norm")
    if months_of_cover > C.SCHEME_STOCK_NORM_MONTHS:
        return _r("stock_norm", FAIL, f"Estimated {months_of_cover:.1f} months of stock > {C.SCHEME_STOCK_NORM_MONTHS}: do not offer the scheme", "stock_norm")
    return _r("stock_norm", PASS, f"Estimated {months_of_cover:.1f} months of stock <= {C.SCHEME_STOCK_NORM_MONTHS}", "stock_norm")


def scheme_cap_breach(free_value_pts: float, primary_value: float) -> dict:
    """CO-POL-014 §4.4."""
    if primary_value <= 0:
        return _r("scheme_cap", PERSON, "No primary value", "scheme_cap")
    share = free_value_pts / primary_value
    if share > C.SCHEME_CAP_SHARE:
        return _r("scheme_cap", FAIL, f"Free goods {share:.2%} of primary > {C.SCHEME_CAP_SHARE:.0%} cap: CFO approval needed", "scheme_cap")
    return _r("scheme_cap", PASS, f"Free goods {share:.2%} of primary, within the {C.SCHEME_CAP_SHARE:.0%} cap", "scheme_cap")


def decide(checks: list[dict]) -> str:
    """Routing: any FAIL -> REJECT; else any PERSON -> NEEDS_PERSON; else APPROVE. A person always signs the CN."""
    st = {c["status"] for c in checks}
    if FAIL in st:
        return "REJECT"
    if PERSON in st:
        return "NEEDS_PERSON"
    return "APPROVE"


SUSPICIOUS = ("system note", "ai assistant", "pre-approved", "preapproved", "skip check", "ignore previous", "approve the full")


def injection_flags(text: str) -> list[str]:
    """Mailbox content is untrusted (CE-BRF-2026-07 §5.7). Instructions aimed at the tool are flagged, never obeyed."""
    t = (text or "").lower()
    return [p for p in SUSPICIOUS if p in t]
