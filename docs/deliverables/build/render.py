"""Convert docx/pptx to PDF with MS Office (COM) and render pages to PNG for review.
Usage: python render.py <file.docx|file.pptx> [out_dir]"""
import sys
from pathlib import Path

import pymupdf
import win32com.client as w32

src = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]) if len(sys.argv) > 2 else src.parent / "_render"
out.mkdir(parents=True, exist_ok=True)
pdf = src.with_suffix(".pdf")
if src.suffix == ".docx":
    app = w32.DispatchEx("Word.Application"); app.Visible = False; app.DisplayAlerts = 0
    d = app.Documents.Open(FileName=str(src), ReadOnly=True, AddToRecentFiles=False)
    d.ExportAsFixedFormat(OutputFileName=str(pdf), ExportFormat=17); d.Close(SaveChanges=0); app.Quit()
else:
    app = w32.Dispatch("PowerPoint.Application")
    p = app.Presentations.Open(str(src), True, False, False); p.SaveAs(str(pdf), 32); p.Close()
    if app.Presentations.Count == 0:  # never quit a PowerPoint the user is working in
        app.Quit()
doc = pymupdf.open(pdf)
for i, page in enumerate(doc, 1):
    page.get_pixmap(dpi=70).save(out / f"{src.stem}-p{i:02d}.png")
print(pdf, len(doc), "pages")
