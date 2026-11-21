"""Loads the CSV extracts once, cleans them, and gives typed lookups.

Every cleaned row keeps `src_row`: its row number as seen when the CSV is opened in a spreadsheet
(header = row 1, first record = row 2). That is how every number on screen points back to its source.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"

# ---------------------------------------------------------------- normalisers (tested)
_MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()


def parse_date(s) -> pd.Timestamp | None:
    """Accepts 30-09-2025, 2025-09-30 and 30-Sep-2025. Returns None when blank or unreadable."""
    if s is None:
        return None
    s = str(s).strip()
    if not s or s.lower() in ("nan", "nat"):
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y", "%d/%m/%Y"):
        try:
            return pd.Timestamp(pd.to_datetime(s, format=fmt))
        except (ValueError, TypeError):
            continue
    return None


def parse_expiry_text(s) -> pd.Timestamp | None:
    """Expiry as stockists write it: 'Sep 2026', '09/2026', 'Oct-26', '31-10-2026', 'Aug-26'. Returns month-end (expiry is month-end)."""
    if not s:
        return None
    t = str(s).strip().lower().replace("exp", "").strip(" .:")
    full = parse_date(t)
    if full is not None:
        return full + pd.offsets.MonthEnd(0)
    m = re.fullmatch(r"([a-z]{3})[a-z]*[-/ ]?(\d{2}|\d{4})", t)
    if m and m.group(1) in _MONTHS:
        y = int(m.group(2)); y = y + 2000 if y < 100 else y
        return pd.Timestamp(year=y, month=_MONTHS.index(m.group(1)) + 1, day=1) + pd.offsets.MonthEnd(0)
    m = re.fullmatch(r"(\d{1,2})[-/](\d{2}|\d{4})", t)
    if m and 1 <= int(m.group(1)) <= 12:
        y = int(m.group(2)); y = y + 2000 if y < 100 else y
        return pd.Timestamp(year=y, month=int(m.group(1)), day=1) + pd.offsets.MonthEnd(0)
    return None


def parse_dates(col: pd.Series) -> pd.Series:
    """Vectorised parse_date for a whole column (same three formats)."""
    s = col.astype(str).str.strip()
    out = pd.to_datetime(s, format="%d-%m-%Y", errors="coerce")
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d/%m/%Y"):
        out = out.fillna(pd.to_datetime(s, format=fmt, errors="coerce"))
    return out


def parse_nums(col: pd.Series) -> pd.Series:
    return pd.to_numeric(col.astype(str).str.replace(",", "").str.strip(), errors="coerce")


def parse_num(s) -> float | None:
    """'3,615.00' -> 3615.0; blank -> None."""
    if s is None:
        return None
    s = str(s).strip().replace(",", "")
    if not s or s.lower() == "nan":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def norm_code(s) -> str:
    return re.sub(r"\s+", "", str(s or "")).upper()


def norm_sku(s) -> str:
    """'PFL-1001', ' pfl1001' -> 'PFL1001'."""
    return norm_code(s).replace("-", "")


def norm_cnf(s) -> str:
    """'CFE01' -> 'CF-E01'."""
    c = norm_code(s)
    m = re.fullmatch(r"CF-?([NEWS]\d\d)", c)
    return f"CF-{m.group(1)}" if m else c


def norm_invoice(s) -> str:
    """'INV-S02-2510-053444' and 'INV-S02/2510/053444' -> 'INV/S02/2510/053444'."""
    c = norm_code(s)
    m = re.fullmatch(r"INV[-/]([NEWS]\d\d)[-/](\d{4})[-/](\d{6})", c)
    return f"INV/{m.group(1)}/{m.group(2)}/{m.group(3)}" if m else c


def norm_scheme(s) -> str:
    c = norm_code(s)
    return c if c.startswith(("QS-", "SL-", "NS-")) else ""


# ---------------------------------------------------------------- loaders
def _read(name: str) -> pd.DataFrame:
    df = pd.read_csv(DATA / f"{name}.csv", dtype=str, keep_default_na=False)
    df.insert(0, "src_row", range(2, len(df) + 2))  # spreadsheet row: header is row 1, first record is row 2
    return df


def _dedupe(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    cols = [c for c in df.columns if c != "src_row"]
    dup = df.duplicated(subset=cols, keep="first")
    return df[~dup].copy(), int(dup.sum())


QUALITY: dict = {}  # filled while loading; shown in the data-quality report


@lru_cache(maxsize=1)
def skus() -> pd.DataFrame:
    df = _read("sku_master")
    df["sku_code"] = df["sku_code"].map(norm_sku)
    for c in ("pts_inr", "mrp_inr", "shelf_life_months"):
        df[c] = parse_nums(df[c])
    return df.set_index("sku_code", drop=False)


@lru_cache(maxsize=1)
def batches() -> pd.DataFrame:
    df = _read("batch_master")
    df["batch_no"] = df["batch_no"].map(norm_code)
    df["sku_code"] = df["sku_code"].map(norm_sku)
    df["mfg_date"] = parse_dates(df["mfg_date"])
    df["expiry_date"] = parse_dates(df["expiry_date"])
    df["batch_qty_packs"] = df["batch_qty_packs"].map(parse_num)
    return df.set_index("batch_no", drop=False)


@lru_cache(maxsize=1)
def stockists() -> pd.DataFrame:
    df = _read("stockist_master")
    df["stockist_code"] = df["stockist_code"].map(norm_code)
    df["cnf_code"] = df["cnf_code"].map(norm_cnf)
    df["appointed_on"] = parse_dates(df["appointed_on"])
    return df.set_index("stockist_code", drop=False)


@lru_cache(maxsize=1)
def sales() -> pd.DataFrame:
    df = _read("primary_sales")
    raw = len(df)
    df, dups = _dedupe(df)
    df["invoice_no"] = df["invoice_no"].map(norm_invoice)
    df["invoice_date"] = (parse_dates(df["invoice_date"]))
    df["cnf_code"] = df["cnf_code"].map(norm_cnf)
    df["stockist_code"] = df["stockist_code"].map(norm_code)
    df["sku_code"] = df["sku_code"].map(norm_sku)
    df["batch_no"] = df["batch_no"].map(norm_code)
    for c in ("ordered_qty", "invoiced_qty", "free_qty", "pts_inr", "net_value_inr"):
        df[c] = parse_nums(df[c])
    for c in ("invoiced_qty", "free_qty", "net_value_inr"):
        df[c] = df[c].fillna(0.0)
    df["scheme_code"] = df["scheme_code"].map(norm_scheme)
    QUALITY["primary_sales"] = {"raw_rows": raw, "exact_duplicates_removed": dups, "rows": len(df),
                                "lines_not_supplied_blank_batch": int((df["batch_no"] == "").sum())}
    return df.reset_index(drop=True)


@lru_cache(maxsize=1)
def claims() -> pd.DataFrame:
    df = _read("expiry_claims")
    raw = len(df)
    df, dups = _dedupe(df)
    df["claim_no"] = df["claim_no"].map(norm_code)
    df["claim_date"] = (parse_dates(df["claim_date"]))
    df["stockist_code"] = df["stockist_code"].map(norm_code)
    df["cnf_code"] = df["cnf_code"].map(norm_cnf)
    df["sku_code"] = df["sku_code"].map(norm_sku)
    df["batch_no"] = df["batch_no"].map(norm_code)
    df["expiry_date_as_claimed"] = (parse_dates(df["expiry_date_as_claimed"]))
    df["credit_note_date"] = (parse_dates(df["credit_note_date"]))
    for c in ("qty_claimed", "claim_value_inr", "credit_value_inr"):
        df[c] = parse_nums(df[c])
    df["original_invoice_ref"] = df["original_invoice_ref"].map(lambda s: norm_invoice(s) if str(s).strip() else "")
    df["claim_type"] = df["claim_type"].str.strip()
    df["status"] = df["status"].str.strip()
    QUALITY["expiry_claims"] = {"raw_rows": raw, "exact_duplicates_removed": dups, "rows": len(df),
                                "claim_no_repeated_after_dedupe": int(df["claim_no"].duplicated().sum())}
    return df.reset_index(drop=True)


@lru_cache(maxsize=1)
def stock() -> pd.DataFrame:
    df = _read("cnf_stock_snapshot")
    df["snapshot_date"] = (parse_dates(df["snapshot_date"]))
    df["cnf_code"] = df["cnf_code"].map(norm_cnf)
    df["sku_code"] = df["sku_code"].map(norm_sku)
    df["batch_no"] = df["batch_no"].map(norm_code)
    df["expiry_date"] = (parse_dates(df["expiry_date"]))
    df["qty_on_hand_packs"] = parse_nums(df["qty_on_hand_packs"]).fillna(0.0)
    df["avg_monthly_outward_packs"] = parse_nums(df["avg_monthly_outward_packs"])
    return df.reset_index(drop=True)


@lru_cache(maxsize=1)
def emails() -> pd.DataFrame:
    df = _read("claim_emails")
    df["received_date"] = (parse_dates(df["received_date"]))
    df["stockist_code_by_mailbox_rule"] = df["stockist_code_by_mailbox_rule"].map(norm_code)
    df["email_id"] = df["email_id"].map(norm_code)
    return df.set_index("email_id", drop=False)


@lru_cache(maxsize=1)
def sales_by_stockist_batch() -> pd.DataFrame:
    """Packs of each batch invoiced to each stockist, including free packs (CO-POL-014 Â§5.5)."""
    s = sales()
    s = s[s["batch_no"] != ""]
    g = s.groupby(["stockist_code", "batch_no"]).agg(
        invoiced=("invoiced_qty", "sum"), free=("free_qty", "sum"),
        invoices=("invoice_no", lambda x: sorted(set(x))), src_rows=("src_row", list),
        cnfs=("cnf_code", lambda x: sorted(set(x))))
    g["total_packs"] = g["invoiced"] + g["free"]
    return g


def load_all() -> None:
    for f in (skus, batches, stockists, sales, claims, stock, emails, sales_by_stockist_batch):
        f()
