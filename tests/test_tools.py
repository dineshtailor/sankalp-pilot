"""Tools and data cleaning against the real extracts. No model."""
import pandas as pd

from agent import data as d
from agent import extract as X
from agent import tools as T


def test_normalisers_handle_messy_codes_and_dates():
    assert d.norm_sku(" pfl-1001") == "PFL1001"
    assert d.norm_cnf("CFE01") == "CF-E01"
    assert d.norm_invoice("INV-S02-2510-053444") == "INV/S02/2510/053444"
    assert d.parse_date("30-Sep-2025") == pd.Timestamp("2025-09-30") == d.parse_date("2025-09-30") == d.parse_date("30-09-2025")
    assert d.parse_num("3,615.00") == 3615.0 and d.parse_num("") is None
    assert d.parse_expiry_text("Oct-26") == pd.Timestamp("2026-10-31")
    assert d.parse_expiry_text("09/2026") == pd.Timestamp("2026-09-30")
    assert d.parse_expiry_text("Mar 2027") == pd.Timestamp("2027-03-31")


def test_duplicates_removed_and_codes_join():
    d.load_all()
    assert d.QUALITY["primary_sales"]["exact_duplicates_removed"] == 745
    assert d.QUALITY["expiry_claims"]["exact_duplicates_removed"] == 23
    assert set(d.sales().stockist_code) <= set(d.stockists().index)


def test_known_batch_is_found_with_source_rows():
    rec = T.batch_record("K2300101")
    assert rec["found"] and rec["sku_code"] == "PFL1001"
    assert rec["evidence"][0]["file"] == "batch_master.csv" and rec["evidence"][0]["row"] == 2  # spreadsheet row


def test_unknown_batch_is_reported_not_invented():
    rec = T.batch_record("K23O0830")  # letter O typed for zero
    assert rec["found"] is False and "K2300830" in rec["close_matches"]


def test_supply_counts_free_packs():
    s = T.supply_of_batch_to_stockist("STK0025", "F2440122")
    assert s["found"] and s["packs_incl_free"] == 2457.0


def test_neha_duplicate_case_is_rejected():
    """Inbox 11 Aug 2026: CLM-2605-04488 repeats CLM-2603-01616 (same stockist, batch, 272 packs)."""
    r = T.check_claim_line({"claim_no": "CLM-2605-04488", "stockist_code": "STK0025", "batch_no": "F2440122", "qty": 272,
                            "claim_type": "Near expiry", "claim_date": "2026-05-12", "cnf_code": "CF-N01"})
    assert r["decision"] == "REJECT"
    assert any(c["check"] == "duplicate" and "CLM-2603-01616" in c["detail"] for c in r["checks"])


def test_clean_claim_is_approved_with_value_at_pts():
    r = T.check_claim_line({"stockist_code": "STK0117", "batch_no": "L2400579", "qty": 38, "claim_type": "Near expiry",
                            "claim_date": "2026-10-16", "invoice_ref": "INV/S01/2507/044588"})
    assert r["decision"] == "APPROVE" and r["value_inr"] == 5749.4


def test_regex_reader_reads_table_and_hinglish():
    f = X.regex_extract("Expiry return", "Pregabalin 75 | J2420408 | Aug 2026 | 142 | INV/E01/2504/035116")
    assert f.lines[0].batch_no == "J2420408" and f.lines[0].qty == 142 and f.lines[0].invoice_ref == "INV/E01/2504/035116"
    f = X.regex_extract("expiry maal wapas", "Methylcobalamin 1500 ka 147 strip expiry ke paas hai, batch E2510396. Exp Oct 2026.")
    assert f.lines[0].batch_no == "E2510396" and f.lines[0].qty == 147


def test_regex_reader_status_and_other():
    assert X.regex_extract("Status", "Status of claim CLM-2609-99999 please.").intent == "status"
    f = X.regex_extract("MRP query", "Old MRP stock of Atorva 10 can be sold at new MRP?")
    assert f.intent == "other" and f.topic == "mrp_price"
