"""Every policy number used by the pilot, with the clause it comes from.

CO-POL-014 v4.2 = Trade Terms, Schemes and Returns Policy (data-pack doc 02, effective 01 Apr 2025)
SC-AGR-CF-003   = C&F Agency Agreement, Schedule 2 and Schedule 4 (data-pack doc 03, 01 Jul 2024)
CE-BRF-2026-07  = Company and Channel Overview (data-pack doc 01)
Nothing here is invented: if a number is not in a document, it is not in this file.
"""

# ---- Claims (CO-POL-014 Section 5) -------------------------------------------------
NEAR_EXPIRY_WINDOW_BEFORE_DAYS = 90   # §5.2 near expiry: from 90 days before expiry to the expiry date
EXPIRED_WINDOW_AFTER_DAYS = 90        # §5.2 expired: expiry date to 90 days after; never accepted beyond (§5.2)
TRANSIT_CLAIM_WINDOW_DAYS = 7         # §5.2 breakage in transit / short supply: within 7 days of the invoice
CN_TARGET_DAYS = 30                   # §5.6 approve and raise CN within 30 days of receipt
VERIFY_WORKING_DAYS = 10              # §5.6 / SC-AGR-CF-003 Sch.2 2.6(4): physical verification in 10 working days
# §5.5 quantity claimed for a batch <= packs of that batch invoiced to that stockist, including free packs
# §5.4 no invoice reference -> purchase-ledger check with written Area Manager approval (needs a person)
# §5.1 claim only at the CFA that billed the stock
# §5.7 valued at PTS in force on claim date (sku_master PTS per CE-BRF-2026-07 §5.1)

CLAIM_TYPES = ("Near expiry", "Expired", "Breakage in transit", "Short supply")

# ---- Shelf life at dispatch (CO-POL-014 Section 7) --------------------------------------
MIN_RSL_SHARE_AT_INVOICE = 0.60       # §7.1 RSL >= 60% of total shelf life on invoice date
MIN_DAYS_TO_EXPIRY_AT_DISPATCH = 60   # §7.1 / Sch.2 2.3(4): never dispatch < 60 days to expiry

# ---- Schemes (CO-POL-014 Section 4) ------------------------------------------------------
SCHEME_CAP_SHARE = 0.03               # §4.4 free goods at PTS <= 3% of quarter primary value
SCHEME_STOCK_NORM_MONTHS = 2.5        # §4.5 no scheme if stockist closing stock > 2.5 months of avg secondary
SCHEME_MOQ_MULTIPLE = 1.5             # Annexure B: MOQ = 1.5x avg monthly purchase of the SKU, previous 3 months
SCHEME_WINDOW_START_DAY = 22          # Annexure B: valid from the 22nd of the last month of the quarter

# ---- Replenishment (SC-AGR-CF-003 Schedule 2.2 and 2.5) ---------------------------------
REPLENISH_TARGET_MONTHS = 2.0         # Sch.2 2.2: top up to two months of allocated volume
MAX_SHIPMENT_MONTHS = 1.2             # Sch.2 2.2: one shipment <= 1.2 months of allocated volume
RETURN_TO_CDC_LEAD_DAYS = 14          # Sch.2 2.5: return to CDC takes 10 to 14 days (upper bound used)

# ---- Fees (SC-AGR-CF-003 clause 5.1) ------------------------------------------------------
CFA_FEE_PER_CLAIM_LINE_INR = 45

# ---- Pilot settings (ours, not policy) ----------------------------------------------------
# Circular pre-check: recommend dropping an SKU from a quarter-end scheme when its scheme lots come back
# as expiry claims at >= this rate AND at >= this multiple of the SKU's non-scheme claim-back rate.
# Set from the backtest in analysis/11_scheme_sku_quarter.py; the NSM decides (CO-POL-014 §4.3).
SCHEME_DROP_CLAIMBACK_PCT = 5.0
SCHEME_DROP_MULTIPLE = 1.5
MAX_TOOL_TRIPS = 4                    # cap on any model tool loop
DATA_CUTOFF = "2026-09-30"            # extracts run 01-Apr-2024 to 30-Sep-2026 (CE-BRF-2026-07 §5)

CLAUSES = {
    "window": "CO-POL-014 §5.2 claim windows",
    "qty": "CO-POL-014 §5.5 quantity limit (invoiced incl. free packs)",
    "duplicate": "CO-POL-014 §5.6 / SC-AGR-CF-003 Sch.2 2.6(3) earlier claim on same stockist and batch",
    "invoice_ref": "CO-POL-014 §5.3(2) original invoice number; §5.4 ledger check with written AM approval",
    "billing_cfa": "CO-POL-014 §5.1 returns only at the CFA that billed the stock",
    "batch_master": "CE-BRF-2026-07 §5.2 batch master",
    "stockist": "CO-POL-014 §1 / §8.3 only the stockist to whom goods were invoiced",
    "value": "CO-POL-014 §5.7 valued at PTS (sku_master)",
    "rsl": "CO-POL-014 §7.1 RSL >= 60% of shelf life at invoice",
    "scheme_cap": "CO-POL-014 §4.4 free goods <= 3% of quarter primary",
    "stock_norm": "CO-POL-014 §4.5 no scheme above 2.5 months of stock",
    "fefo": "SC-AGR-CF-003 cl. 6.3 and Sch.2 2.3(2) FEFO picking",
    "return_cdc": "SC-AGR-CF-003 Sch.2 2.5 return to CDC (Head SC approval)",
}
