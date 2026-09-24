"""Shared letterhead: the visual and structural furniture every generated
document wears, so a legal notice, a case dossier and a suspect report all
read as pages from the same case file rather than three different tools.

Modelled on how an Indian police/cyber-cell document actually looks and is
actually built for evidence:

  - a crest and a formal title block, not a plain heading
  - a reference number in the Dept/Type/Serial/Year form every government
    office uses, so a document can be filed and re-found
  - numbered clauses and a proper closing, not bullet fragments
  - a signature block that says what it is: a computer-generated document,
    which is exactly what Indian evidence law requires it to say
  - a QR-verifiable hash and running page numbers on every page, so a
    photocopy or a rescanned copy still carries its own provenance

One deliberate choice: this does **not** draw the State Emblem of India.
Its use is restricted by the State Emblem of India (Prohibition of Improper
Use) Act, 2005 to authorised government bodies, and LedgerLens is a private
investigative aid, not a police system - stamping the national emblem on
its output would misrepresent where the document came from. The badge drawn
below is original, and reads as what state cyber cells and I4C actually put
on their own material: a crest, not a claim of government authorship.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

import qrcode
from reportlab.graphics.shapes import Circle, Drawing, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.colors import Color
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas as _canvas
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

# ── Palette ──────────────────────────────────────────────────────────────
# A restrained navy-and-slate scheme, deliberately closer to a statutory
# notice than to the product's own brand colours - this document has to
# look like it belongs in a case file, not in the app.
INK = colors.HexColor("#0f172a")
SLATE = colors.HexColor("#334155")
MUTED = colors.HexColor("#64748b")
RULE = colors.HexColor("#94a3b8")
HAIRLINE = colors.HexColor("#cbd5e1")
PANEL = colors.HexColor("#f1f5f9")
GOLD = colors.HexColor("#b8860b")
CRIMSON = colors.HexColor("#8a1c1c")
WATERMARK = Color(0.82, 0.85, 0.90, alpha=1)

FONT_SERIF = "Times-Roman"
FONT_SERIF_BOLD = "Times-Bold"
FONT_SERIF_ITALIC = "Times-Italic"
FONT_SANS_BOLD = "Helvetica-Bold"
FONT_MONO = "Courier"


def letter_styles() -> dict[str, ParagraphStyle]:
    """One shared style sheet so every document sets its type the same way."""
    return {
        "crest_line1": ParagraphStyle(
            "CrestLine1", fontName=FONT_SANS_BOLD, fontSize=13.5, leading=16,
            alignment=TA_CENTER, textColor=INK, tracking=0.6,
        ),
        "crest_line2": ParagraphStyle(
            "CrestLine2", fontName="Helvetica", fontSize=8.5, leading=11,
            alignment=TA_CENTER, textColor=MUTED,
        ),
        "doc_title": ParagraphStyle(
            "DocTitle", fontName=FONT_SANS_BOLD, fontSize=12.5, leading=15,
            alignment=TA_CENTER, textColor=colors.white,
        ),
        "doc_subtitle": ParagraphStyle(
            "DocSubtitle", fontName="Helvetica", fontSize=8.5, leading=11,
            alignment=TA_CENTER, textColor=colors.white,
        ),
        "meta_label": ParagraphStyle(
            "MetaLabel", fontName="Helvetica-Bold", fontSize=8, leading=10.5, textColor=MUTED,
        ),
        "meta_value": ParagraphStyle(
            "MetaValue", fontName=FONT_SERIF, fontSize=9, leading=11.5, textColor=INK,
        ),
        "salutation": ParagraphStyle(
            "Salutation", fontName=FONT_SERIF, fontSize=9.5, leading=13, textColor=INK,
        ),
        "body": ParagraphStyle(
            "Body", fontName=FONT_SERIF, fontSize=9.5, leading=14, textColor=SLATE,
            alignment=TA_JUSTIFY, spaceAfter=6,
        ),
        "clause_num": ParagraphStyle(
            "ClauseNum", fontName=FONT_SERIF_BOLD, fontSize=9.5, leading=14, textColor=INK,
        ),
        "clause": ParagraphStyle(
            "Clause", fontName=FONT_SERIF, fontSize=9.5, leading=14, textColor=SLATE,
            alignment=TA_JUSTIFY, leftIndent=14, spaceAfter=5,
        ),
        "sub_clause": ParagraphStyle(
            "SubClause", fontName=FONT_SERIF, fontSize=9.5, leading=13.5, textColor=SLATE,
            alignment=TA_JUSTIFY, leftIndent=26, spaceAfter=4,
        ),
        "section_head": ParagraphStyle(
            "SectionHead", fontName=FONT_SANS_BOLD, fontSize=9.5, leading=13,
            textColor=colors.white, spaceBefore=0, spaceAfter=0,
        ),
        "table_head": ParagraphStyle(
            "TableHead", fontName="Helvetica-Bold", fontSize=7.5, leading=9.5,
            textColor=colors.white,
        ),
        "table_cell": ParagraphStyle(
            "TableCell", fontName=FONT_SERIF, fontSize=8, leading=10.5, textColor=SLATE,
        ),
        "table_mono": ParagraphStyle(
            "TableMono", fontName=FONT_MONO, fontSize=7.3, leading=9.5, textColor=INK,
        ),
        "italic_note": ParagraphStyle(
            "ItalicNote", fontName=FONT_SERIF_ITALIC, fontSize=8.3, leading=11.5,
            textColor=MUTED, alignment=TA_JUSTIFY, spaceAfter=6,
        ),
        "sign_role": ParagraphStyle(
            "SignRole", fontName=FONT_SERIF_BOLD, fontSize=9.5, leading=12.5,
            alignment=TA_RIGHT, textColor=INK,
        ),
        "sign_sub": ParagraphStyle(
            "SignSub", fontName=FONT_SERIF, fontSize=8.5, leading=11.5,
            alignment=TA_RIGHT, textColor=SLATE,
        ),
        "copy_to": ParagraphStyle(
            "CopyTo", fontName=FONT_SERIF, fontSize=8, leading=11.5, textColor=SLATE,
        ),
        "verify_label": ParagraphStyle(
            "VerifyLabel", fontName="Helvetica-Bold", fontSize=7, leading=9,
            textColor=MUTED, alignment=TA_CENTER,
        ),
        "hash_mono": ParagraphStyle(
            "HashMono", fontName=FONT_MONO, fontSize=7, leading=9.5, textColor=INK,
        ),
    }


# ── Crest ────────────────────────────────────────────────────────────────

def crest_drawing(diameter: float = 2.05 * cm) -> Drawing:
    """An original cyber-crime-cell badge: a shield holding a padlock, ringed
    by a plain circle. Not the State Emblem - see the module docstring."""
    d = Drawing(diameter, diameter)
    cx = cy = diameter / 2
    r = diameter / 2

    d.add(Circle(cx, cy, r - 1, strokeColor=INK, strokeWidth=1.1, fillColor=None))
    d.add(Circle(cx, cy, r - 3.4, strokeColor=GOLD, strokeWidth=0.6, fillColor=None))

    sw, sh = diameter * 0.46, diameter * 0.52
    sx, sy = cx - sw / 2, cy - sh / 2 + diameter * 0.03
    shield = Polygon(
        points=[
            sx, sy + sh * 0.86,
            sx, sy + sh * 0.30,
            cx, sy - sh * 0.10,
            sx + sw, sy + sh * 0.30,
            sx + sw, sy + sh * 0.86,
            cx, sy + sh,
        ],
        strokeColor=GOLD, strokeWidth=0.9, fillColor=INK,
    )
    d.add(shield)

    body_w, body_h = diameter * 0.20, diameter * 0.16
    d.add(Rect(cx - body_w / 2, sy + sh * 0.38, body_w, body_h,
               rx=body_w * 0.22, ry=body_w * 0.22, fillColor=colors.white,
               strokeColor=None))
    d.add(Circle(cx, sy + sh * 0.38 + body_h + body_w * 0.30, body_w * 0.30,
                strokeColor=colors.white, strokeWidth=body_w * 0.34, fillColor=None))
    return d


def letterhead_banner(*, unit_name: str, unit_sub: str, styles: dict) -> Table:
    """Crest beside the issuing unit's name - the top of page one."""
    cell = Table(
        [[Paragraph(unit_name, styles["crest_line1"])],
         [Paragraph(unit_sub, styles["crest_line2"])]],
        colWidths=[13.4 * cm],
    )
    cell.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    outer = Table([[crest_drawing(), cell]], colWidths=[2.4 * cm, 13.4 * cm])
    outer.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
    ]))
    return outer


def title_banner(*, title: str, subtitle: str | None, styles: dict,
                 fill=INK) -> Table:
    """The bold statutory / document-type banner beneath the letterhead."""
    rows = [[Paragraph(title, styles["doc_title"])]]
    if subtitle:
        rows.append([Paragraph(subtitle, styles["doc_subtitle"])])
    t = Table(rows, colWidths=[17.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 7 if not subtitle else 3),
        ("TOPPADDING", (0, 1), (-1, 1), 0) if subtitle else ("TOPPADDING", (0, 0), (0, 0), 7),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 7) if subtitle else ("BOTTOMPADDING", (0, 0), (0, 0), 7),
    ]))
    return t


def ref_date_line(*, ref_no: str, date_str: str, styles: dict) -> Table:
    t = Table(
        [[Paragraph(f"<b>No.</b> {ref_no}", styles["meta_value"]),
          Paragraph(f"<b>Dated:</b> {date_str}", styles["meta_value"])]],
        colWidths=[11 * cm, 6.4 * cm],
    )
    t.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.7, INK),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def reference_number(prefix: str, case_id: str, *, when: datetime | None = None) -> str:
    """Dept/Type/Serial/Year, the way an Indian government office numbers
    its outward correspondence - so the document can be filed and re-found."""
    when = when or datetime.now(timezone.utc)
    serial = case_id.replace("-", "")[:8].upper()
    return f"LGL/{prefix}/{serial}/{when.year}"


def clause(number: int, text: str, styles: dict) -> Table:
    """A numbered paragraph, hanging-indented - the register a statutory
    notice is actually written in, not a bulleted list."""
    t = Table([[Paragraph(f"{number}.", styles["clause_num"]),
                Paragraph(text, styles["clause"])]],
              colWidths=[0.9 * cm, 16.5 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                          ("TOPPADDING", (0, 0), (-1, -1), 0),
                          ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                          ("LEFTPADDING", (0, 0), (0, 0), 0),
                          ("RIGHTPADDING", (0, 0), (0, 0), 2)]))
    return t


def lettered_sub_clause(letter: str, text: str, styles: dict) -> Table:
    t = Table([[Paragraph(f"({letter})", styles["clause_num"]),
                Paragraph(text, styles["sub_clause"])]],
              colWidths=[1.3 * cm, 16.1 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                          ("TOPPADDING", (0, 0), (-1, -1), 0),
                          ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                          ("LEFTPADDING", (0, 0), (0, 0), 0),
                          ("RIGHTPADDING", (0, 0), (0, 0), 2)]))
    return t


# ── QR verification and integrity certificate ───────────────────────────

def qr_image(data: str, *, size: float = 2.05 * cm) -> Image:
    """A scannable check on the document's own hash, the way an e-stamped
    or DigiLocker-issued Indian government document now routinely carries
    one - a photocopy of the page still carries a way to verify it."""
    qr = qrcode.QRCode(border=1, box_size=8)
    qr.add_data(data)
    qr.make(fit=True)
    pil_img = qr.make_image(fill_color="#0f172a", back_color="white").convert("RGB")
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    return Image(buf, width=size, height=size)


def verification_block(*, doc_hash: str, ref_no: str, styles: dict,
                       verify_hint: str) -> Table:
    qr = qr_image(f"LEDGERLENS-VERIFY|{ref_no}|{doc_hash}")
    text = Table(
        [[Paragraph("DOCUMENT VERIFICATION", styles["verify_label"])],
         [Paragraph(f"<font face='Courier' size=6.6>{doc_hash}</font>", styles["hash_mono"])],
         [Paragraph(verify_hint, ParagraphStyle(
             "hint", parent=styles["italic_note"], alignment=TA_LEFT, spaceAfter=0))]],
        colWidths=[12.8 * cm],
    )
    text.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 1),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    t = Table([[qr, text]], colWidths=[2.3 * cm, 13 * cm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.6, HAIRLINE),
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
    ]))
    return t


def evidence_certificate(*, officer_name: str, designation: str, system_name: str,
                         styles: dict) -> list:
    """The Section 63 (Bharatiya Sakshya Adhiniyam, 2023 - formerly Section
    65B, Indian Evidence Act, 1872) certificate that any computer-produced
    document offered as evidence in an Indian court must carry.

    This is the one addition here that is not decoration: without it, a
    printout from any system is not by itself admissible as evidence of its
    contents. Including the certificate in the correct statutory form is
    what makes the output of this tool something an officer can actually
    attach to a case file, not merely software output shaped like a form.
    """
    head = Table([[Paragraph(
        "CERTIFICATE UNDER SECTION 63, BHARATIYA SAKSHYA ADHINIYAM, 2023",
        styles["section_head"])]], colWidths=[17.4 * cm])
    head.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SLATE),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    text = Paragraph(
        f"I, {officer_name}, {designation}, do hereby certify under Section 63 of the "
        f"Bharatiya Sakshya Adhiniyam, 2023, that this document has been produced by "
        f"{system_name}, a computer system used regularly to store and process the "
        f"information contained herein in the ordinary course of investigative activity; "
        f"that the information was regularly fed into the system in the ordinary course "
        f"of the said activity; that the computer was operating properly at the material "
        f"time and, if not, that the improper operation did not affect the accuracy of "
        f"this document; and that the information reproduced herein is derived from "
        f"information so fed into the computer. This certificate is furnished for the "
        f"purpose of satisfying the conditions referred to in sub-section (4) of Section 63 "
        f"of the said Act.",
        styles["body"],
    )
    return [head, Spacer(1, 0.15 * cm), text]


def signature_block(*, officer_name: str, designation: str, unit_name: str,
                    styles: dict, place: str = "", closing: str = "Yours faithfully,") -> Table:
    seal = _seal_drawing()
    left = Paragraph(
        f"Place: {place}<br/>Date: {datetime.now(timezone.utc).strftime('%d-%m-%Y')}",
        ParagraphStyle("place", parent=styles["meta_value"], fontSize=8.3, textColor=MUTED),
    )
    right_rows = [
        [Paragraph(closing, ParagraphStyle("closing", parent=styles["sign_sub"], spaceAfter=0))],
        [Spacer(1, 1.0 * cm)],
        [Paragraph(f"({officer_name})", styles["sign_role"])],
        [Paragraph(designation, styles["sign_sub"])],
        [Paragraph(unit_name, styles["sign_sub"])],
    ]
    right = Table(right_rows, colWidths=[9.5 * cm])
    right.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 0),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    row = Table([[left, seal, right]], colWidths=[5 * cm, 2.8 * cm, 9.6 * cm])
    row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                             ("ALIGN", (1, 0), (1, 0), "CENTER")]))
    return row


def _seal_drawing(diameter: float = 2.5 * cm) -> Drawing:
    """A dashed placeholder ring rather than a forged signature or stamp -
    the honest way to show where a wet signature and station seal belong on
    a document that was, in truth, generated by software."""
    d = Drawing(diameter, diameter)
    cx = cy = diameter / 2
    r = diameter / 2 - 2
    import math
    n_dashes = 28
    for i in range(n_dashes):
        a0 = (360 / n_dashes) * i
        if i % 2:
            continue
        a1 = a0 + (360 / n_dashes) * 0.6
        x0 = cx + r * math.cos(math.radians(a0)); y0 = cy + r * math.sin(math.radians(a0))
        x1 = cx + r * math.cos(math.radians(a1)); y1 = cy + r * math.sin(math.radians(a1))
        from reportlab.graphics.shapes import Line
        d.add(Line(x0, y0, x1, y1, strokeColor=RULE, strokeWidth=1.1))
    d.add(String(cx, cy + 6, "SPACE FOR", fontName="Helvetica", fontSize=5.6,
                 fillColor=MUTED, textAnchor="middle"))
    d.add(String(cx, cy - 2, "SIGNATURE", fontName="Helvetica-Bold", fontSize=6,
                 fillColor=MUTED, textAnchor="middle"))
    d.add(String(cx, cy - 10, "& SEAL", fontName="Helvetica-Bold", fontSize=6,
                 fillColor=MUTED, textAnchor="middle"))
    return d


def copy_to_block(recipients: list[str], styles: dict) -> Table:
    rows = [[Paragraph("<b>Copy to</b> (for information and record):", styles["copy_to"])]]
    for i, r in enumerate(recipients, start=1):
        rows.append([Paragraph(f"{i}. {r}", styles["copy_to"])])
    t = Table(rows, colWidths=[17.4 * cm])
    t.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 1.5),
                          ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
    return t


def generated_notice(system_name: str, styles: dict) -> Paragraph:
    return Paragraph(
        f"This document was generated electronically by {system_name} from the case "
        f"record identified above and, where an officer's name appears against it, "
        f"reflects a decision that officer made in the system. It is issued for use in "
        f"an active investigation and is not for circulation beyond that purpose.",
        styles["italic_note"],
    )


# ── Page decoration: watermark, footer, running page numbers ─────────────

def make_canvas(*, footer_left: str, ref_no: str, watermark_text: str = "LAW ENFORCEMENT USE ONLY"):
    """A canvas class that stamps every page with a watermark, a footer and
    'Page X of Y' - so a single page photocopied out of the set, or a scan
    missing its cover, still identifies where it came from.

    'Page X of Y' needs the total page count before any page can be drawn,
    which SimpleDocTemplate does not know until the whole story is laid
    out. The standard fix is this: buffer every page as it is produced,
    and only paint the footer once the true count is known, at save().
    """

    class _NumberedCanvas(_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_states: list[dict] = []

        def showPage(self):
            self._saved_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved_states)
            for state in self._saved_states:
                self.__dict__.update(state)
                self._decorate(total)
                super().showPage()
            super().save()

        def _decorate(self, total: int) -> None:
            page_w, page_h = self._pagesize
            self.saveState()
            self.setFont(FONT_SERIF_ITALIC, 34)
            self.setFillColor(WATERMARK)
            self.translate(page_w / 2, page_h / 2)
            self.rotate(38)
            self.drawCentredString(0, 0, watermark_text)
            self.restoreState()

            self.saveState()
            self.setStrokeColor(HAIRLINE)
            self.setLineWidth(0.6)
            self.line(18 * mm, 16 * mm, page_w - 18 * mm, 16 * mm)
            self.setFont("Helvetica", 6.8)
            self.setFillColor(MUTED)
            self.drawString(18 * mm, 11.5 * mm, footer_left)
            self.drawCentredString(page_w / 2, 11.5 * mm, ref_no)
            self.drawRightString(page_w - 18 * mm, 11.5 * mm,
                                 f"Page {self._pageNumber} of {total}")
            self.restoreState()

    return _NumberedCanvas
