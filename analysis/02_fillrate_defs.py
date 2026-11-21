"""Which fill-rate definition reproduces the QBR? Run: python -m analysis.02_fillrate_defs"""
import pandas as pd

from agent import data as d
from analysis_helpers import fq

s = d.sales().copy()
s["q"] = fq(s.invoice_date)
key = ["invoice_no", "sku_code"]
lines = s.groupby(key).agg(q=("q", "first"), cnf=("cnf_code", "first"), ordered=("ordered_qty", "sum"),
                            invoiced=("invoiced_qty", "sum"), any_blank=("batch_no", lambda x: (x == "").any()),
                            n=("src_row", "size"))
supplied = lines[~lines.any_blank]
res = pd.DataFrame({
    "A_qty_all_lines": lines.groupby("q").invoiced.sum() / lines.groupby("q").ordered.sum() * 100,
    "B_qty_excl_unsupplied_lines": supplied.groupby("q").invoiced.sum() / supplied.groupby("q").ordered.sum() * 100,
    "C_lines_fully_filled": (lines.invoiced >= lines.ordered).groupby(lines.q).mean() * 100,
    "D_lines_any_supply": (lines.invoiced > 0).groupby(lines.q).mean() * 100,
})
print(res.round(1).to_string())
print("rows with blank ordered_qty that are first rows?", (s.ordered_qty.isna() & ~s.duplicated(key)).sum())
