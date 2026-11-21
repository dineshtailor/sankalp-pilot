import pandas as pd


def fq(ts: pd.Series) -> pd.Series:
    """Indian financial quarter label, e.g. 2025-04-01 -> FY26Q1."""
    fy = ts.dt.year + (ts.dt.month >= 4).astype(int)
    q = ((ts.dt.month - 4) % 12) // 3 + 1
    return "FY" + (fy % 100).astype(str).str.zfill(2) + "Q" + q.astype(str)
