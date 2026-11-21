"""Professional document theme for Project Sankalp deliverables (python-docx)."""
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

NAVY = RGBColor(0x0B, 0x1F, 0x3A)
TEAL = RGBColor(0x0F, 0x76, 0x6E)
INK = RGBColor(0x1B, 0x23, 0x33)
MUTE = RGBColor(0x5B, 0x64, 0x78)
RED = RGBColor(0xB4, 0x23, 0x18)
HEX = {"navy": "0B1F3A", "teal": "0F766E", "zebra": "F3F6FA", "line": "D5DBE5", "callout": "E8F3F1", "warn": "FFF4E0", "red": "FDECEA"}
FONT = "Calibri"


def _shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def _borders(table, color="D5DBE5", size=4):
    tblPr = table._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single"); e.set(qn("w:sz"), str(size)); e.set(qn("w:color"), color)
        b.append(e)
    tblPr.append(b)


def _cell_margins(table, top=40, bottom=40, left=80, right=80):
    tblPr = table._tbl.tblPr
    m = OxmlElement("w:tblCellMar")
    for k, v in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        e = OxmlElement(f"w:{k}"); e.set(qn("w:w"), str(v)); e.set(qn("w:type"), "dxa"); m.append(e)
    tblPr.append(m)


def _field(run, instr):
    for t, text in (("begin", None), (None, instr), ("end", None)):
        if t:
            f = OxmlElement("w:fldChar"); f.set(qn("w:fldCharType"), t); run._r.append(f)
        else:
            it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = text; run._r.append(it)


class Doc:
    def __init__(self, title, subtitle, doc_no, version="1.1", owner="FDE team, Project Sankalp", date="21 Nov 2026",
                 classification="Confidential, project team", base_size=10, landscape=False, margins_cm=1.7):
        self.d = Document()
        sec = self.d.sections[0]
        sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
        if landscape:
            sec.orientation = WD_ORIENT.LANDSCAPE; sec.page_width, sec.page_height = Cm(29.7), Cm(21.0)
        for side in ("left_margin", "right_margin"):
            setattr(sec, side, Cm(margins_cm))
        sec.top_margin, sec.bottom_margin = Cm(1.5), Cm(1.4)
        sec.header_distance, sec.footer_distance = Cm(0.7), Cm(0.6)
        self.width_cm = (sec.page_width - sec.left_margin - sec.right_margin) / 360000
        st = self.d.styles
        st["Normal"].font.name = FONT; st["Normal"].font.size = Pt(base_size); st["Normal"].font.color.rgb = INK
        st["Normal"].element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        st["Normal"].paragraph_format.space_after = Pt(3); st["Normal"].paragraph_format.line_spacing = 1.08
        for name, size, color, before, after in (("Heading 1", base_size + 4, NAVY, 9, 3), ("Heading 2", base_size + 1.5, TEAL, 6, 2), ("Heading 3", base_size + 0.5, NAVY, 4, 1)):
            h = st[name]; h.font.name = FONT; h.font.size = Pt(size); h.font.bold = True; h.font.color.rgb = color
            h.element.rPr.rFonts.set(qn("w:asciiTheme"), "") if False else None
            rf = h.element.rPr.rFonts; rf.set(qn("w:ascii"), FONT); rf.set(qn("w:hAnsi"), FONT)
            h.paragraph_format.space_before = Pt(before); h.paragraph_format.space_after = Pt(after); h.paragraph_format.keep_with_next = True
        for ls in ("List Bullet", "List Number"):
            st[ls].font.name = FONT; st[ls].font.size = Pt(base_size); st[ls].paragraph_format.space_after = Pt(1)
        self.base = base_size
        self._header_footer(title, doc_no, version, classification)
        self._cover(title, subtitle, doc_no, version, owner, date, classification)

    # ---------------------------------------------------------------- frame
    def _header_footer(self, title, doc_no, version, classification):
        sec = self.d.sections[0]
        hp = sec.header.paragraphs[0]
        hp.text = ""
        r = hp.add_run("PROJECT SANKALP  ·  "); r.font.size = Pt(7.5); r.font.bold = True; r.font.color.rgb = TEAL
        r = hp.add_run(f"{title}  ·  {doc_no} v{version}"); r.font.size = Pt(7.5); r.font.color.rgb = MUTE
        pPr = hp._p.get_or_add_pPr(); bdr = OxmlElement("w:pBdr"); bt = OxmlElement("w:bottom")
        bt.set(qn("w:val"), "single"); bt.set(qn("w:sz"), "6"); bt.set(qn("w:color"), HEX["teal"]); bdr.append(bt); pPr.append(bdr)
        fp = sec.footer.paragraphs[0]
        r = fp.add_run(f"{classification}. Fictional teaching case (FDE Academy); Pfizer Limited is not involved.   Page "); r.font.size = Pt(7.5); r.font.color.rgb = MUTE
        r = fp.add_run(); r.font.size = Pt(7.5); _field(r, "PAGE")
        r = fp.add_run(" of "); r.font.size = Pt(7.5); r.font.color.rgb = MUTE
        r = fp.add_run(); r.font.size = Pt(7.5); _field(r, "NUMPAGES")

    def _cover(self, title, subtitle, doc_no, version, owner, date, classification):
        t = self.d.add_table(rows=1, cols=1); t.alignment = WD_TABLE_ALIGNMENT.CENTER
        c = t.rows[0].cells[0]; _shade(c, HEX["navy"]); _cell_margins(t, 120, 120, 200, 200)
        p = c.paragraphs[0]; r = p.add_run("PROJECT SANKALP  ·  GENERAL MEDICINES TRADE CHANNEL"); r.font.size = Pt(8); r.font.bold = True; r.font.color.rgb = RGBColor(0x5E, 0xEA, 0xD4)
        p = c.add_paragraph(); r = p.add_run(title); r.font.size = Pt(self.base + 10); r.font.bold = True; r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        p = c.add_paragraph(); r = p.add_run(subtitle); r.font.size = Pt(self.base + 1); r.font.color.rgb = RGBColor(0xC9, 0xD3, 0xE3)
        meta = self.d.add_table(rows=1, cols=4); _borders(meta, HEX["line"]); _cell_margins(meta, 30, 30, 80, 80)
        for i, (k, v) in enumerate((("Document", f"{doc_no}  v{version}"), ("Owner", owner), ("Date", date), ("Classification", classification))):
            cell = meta.rows[0].cells[i]; _shade(cell, HEX["zebra"])
            p = cell.paragraphs[0]; r = p.add_run(k.upper()); r.font.size = Pt(6.5); r.font.bold = True; r.font.color.rgb = MUTE
            p = cell.add_paragraph(); r = p.add_run(v); r.font.size = Pt(8.5)
        self.d.add_paragraph().paragraph_format.space_after = Pt(0)

    # ---------------------------------------------------------------- content
    def h1(self, text): return self.d.add_heading(text, level=1)
    def h2(self, text): return self.d.add_heading(text, level=2)
    def h3(self, text): return self.d.add_heading(text, level=3)

    def p(self, text="", bold_lead=None, size=None, color=None, italic=False, align=None, after=None):
        para = self.d.add_paragraph()
        if bold_lead:
            r = para.add_run(bold_lead); r.bold = True; r.font.color.rgb = NAVY
            if size: r.font.size = Pt(size)
        self._rich(para, text, size, color, italic)
        if align == "center": para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if after is not None: para.paragraph_format.space_after = Pt(after)
        return para

    def _rich(self, para, text, size=None, color=None, italic=False):
        """**bold** markup inside text."""
        parts = text.split("**")
        for i, part in enumerate(parts):
            if not part:
                continue
            r = para.add_run(part); r.bold = i % 2 == 1; r.italic = italic
            if size: r.font.size = Pt(size)
            if color is not None: r.font.color.rgb = color

    def bullets(self, items, numbered=False, size=None):
        for it in items:
            para = self.d.add_paragraph(style="List Number" if numbered else "List Bullet")
            self._rich(para, it, size)
            para.paragraph_format.space_after = Pt(1)

    def table(self, header, rows, widths_cm=None, size=None, header_fill="teal", bold_first_col=False, align_right_cols=()):
        size = size or self.base - 1.5
        t = self.d.add_table(rows=1, cols=len(header)); t.alignment = WD_TABLE_ALIGNMENT.CENTER
        _borders(t, HEX["line"]); _cell_margins(t, 25, 25, 60, 60)
        t.autofit = False
        widths = widths_cm or [self.width_cm / len(header)] * len(header)
        for i, h in enumerate(header):
            cell = t.rows[0].cells[i]; _shade(cell, HEX[header_fill]); cell.width = Cm(widths[i])
            r = cell.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(size); r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        trPr = t.rows[0]._tr.get_or_add_trPr(); th = OxmlElement("w:tblHeader"); th.set(qn("w:val"), "true"); trPr.append(th)
        for ri, row in enumerate(rows):
            cells = t.add_row().cells
            for i, v in enumerate(row):
                cells[i].width = Cm(widths[i])
                if ri % 2 == 1: _shade(cells[i], HEX["zebra"])
                para = cells[i].paragraphs[0]; para.paragraph_format.space_after = Pt(0)
                self._rich(para, str(v), size)
                if bold_first_col and i == 0:
                    for r in para.runs: r.bold = True
                if i in align_right_cols: para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        self.d.add_paragraph().paragraph_format.space_after = Pt(0)
        return t

    def callout(self, title, text, fill="callout", size=None):
        t = self.d.add_table(rows=1, cols=1); _cell_margins(t, 70, 70, 140, 140)
        c = t.rows[0].cells[0]; _shade(c, HEX[fill])
        tcPr = c._tc.get_or_add_tcPr(); b = OxmlElement("w:tcBorders"); l = OxmlElement("w:left")
        l.set(qn("w:val"), "single"); l.set(qn("w:sz"), "24"); l.set(qn("w:color"), HEX["teal"] if fill == "callout" else "D97706"); b.append(l); tcPr.append(b)
        para = c.paragraphs[0]; r = para.add_run(title); r.bold = True; r.font.color.rgb = TEAL if fill == "callout" else RGBColor(0xB4, 0x53, 0x09); r.font.size = Pt(size or self.base)
        for line in (text if isinstance(text, list) else [text]):
            para = c.add_paragraph(); para.paragraph_format.space_after = Pt(1); self._rich(para, line, size or self.base - 0.5)
        self.d.add_paragraph().paragraph_format.space_after = Pt(0)

    def image(self, path, width_cm=None, caption=None):
        self.d.add_picture(str(path), width=Cm(width_cm or self.width_cm))
        self.d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        self.d.paragraphs[-1].paragraph_format.space_after = Pt(0)
        if caption:
            self.p(caption, size=self.base - 2, color=MUTE, italic=True, align="center", after=4)

    def page_break(self):
        self.d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def save(self, path):
        try:
            self.d.save(str(path))
        except PermissionError:  # open in Word: never force it; write a versioned copy instead
            alt = path.with_name(f"{path.stem}_v1.1{path.suffix}")
            self.d.save(str(alt))
            return alt
        return path
