"""The suspect report: confirmed suspects only, each with its evidence.

The full investigation report is a record of everything the trace saw. This
document answers a narrower question - who is the officer naming, and on
what basis - and it is built for the reader of that question: a supervising
officer, a prosecutor, an exchange's law-enforcement desk.

Only wallets an officer has confirmed appear. Wallets the system ranked but
nobody reviewed, and wallets reviewed and dismissed, are left out entirely:
putting an unreviewed algorithmic ranking into a document that goes out
under an officer's name would turn a lead into an accusation.
"""
import hashlib
import io
import json
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from app.models.orm import Case
from app.reports.pdf import _snapshot_hash
from app.tracer.patterns import format_amount

INK = colors.HexColor("#182029")
MUTED = colors.HexColor("#647285")
RULE = colors.HexColor("#d3dae3")
SUNK = colors.HexColor("#f4f6f8")
HEADER = colors.HexColor("#163f7d")
PRIORITY_COLOUR = {"high": colors.HexColor("#b3261e"), "medium": colors.HexColor("#8a5a00"),
                   "low": colors.HexColor("#116446")}


def suspect_report_hash(case: Case, confirmed: list[dict]) -> str:
    """SHA-256 over the evidence snapshot and the officer's rulings.

    Binds the two together: the list of named suspects cannot be edited
    without the hash changing, and neither can the case evidence behind it.
    """
    payload = {
        "case_snapshot": _snapshot_hash(case),
        "confirmed": [
            {"address": s["address"], "role": s["role"], "score": s["score"],
             "note": s["decision"]["note"], "decided_by": s["decision"]["decided_by"],
             "decided_at": s["decision"]["decided_at"]}
            for s in sorted(confirmed, key=lambda s: s["address"])
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _when(ts: int | None) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%d %b %Y, %H:%M UTC")


def build_suspect_report(case: Case, summary: dict, confirmed: list[dict],
                          generated_by: str) -> tuple[bytes, str]:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                             leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                             title=f"Suspect report - case {case.id}")
    base = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=base["Title"], alignment=TA_LEFT, fontSize=18,
                           textColor=INK, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontSize=12, textColor=INK,
                        spaceBefore=10, spaceAfter=6)
    h3 = ParagraphStyle("h3", parent=base["Heading3"], fontSize=10.5, textColor=INK,
                        spaceBefore=2, spaceAfter=3)
    body = ParagraphStyle("b", parent=base["BodyText"], fontSize=9, leading=12.5, textColor=INK)
    small = ParagraphStyle("s", parent=body, fontSize=8, leading=11, textColor=MUTED)
    mono = ParagraphStyle("m", parent=body, fontName="Courier", fontSize=8, leading=10.5)
    cell = ParagraphStyle("c", parent=body, fontSize=8.5, leading=11)

    unit = summary.get("unit") or ""
    report_hash = suspect_report_hash(case, confirmed)
    story = []

    story.append(Paragraph("Suspect Report", title))
    story.append(Paragraph("LedgerLens crypto fraud attribution — officer-confirmed suspects", small))
    story.append(Spacer(1, 0.35 * cm))

    meta = [
        ["Case ID", case.id, "Complaint ref.", case.complaint_ref or "—"],
        ["Chain", case.chain.upper(), "Generated", datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")],
        ["Reported wallet", Paragraph(escape(case.reported_address), mono), "Prepared by", generated_by],
    ]
    meta_table = Table(meta, colWidths=[2.9 * cm, 6.4 * cm, 2.7 * cm, 5.4 * cm])
    meta_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED), ("TEXTCOLOR", (2, 0), (2, -1), MUTED),
        ("BACKGROUND", (0, 0), (-1, -1), SUNK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, -1), (-1, -1), 0.6, RULE),
    ]))
    story.append(meta_table)

    story.append(Paragraph("What happened", h2))
    story.append(Paragraph(escape(summary.get("headline") or "—"), body))
    figures = [
        ["Victim funds traced", "Reached exchanges", "Still in wallets", "Confirmed suspects"],
        [format_amount(summary.get("victim_total", 0), case.chain),
         format_amount(summary.get("to_exchanges", 0), case.chain),
         format_amount(summary.get("still_held", 0), case.chain),
         str(len(confirmed))],
    ]
    fig_table = Table(figures, colWidths=[4.35 * cm] * 4)
    fig_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, 0), 7.5), ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONTSIZE", (0, 1), (-1, 1), 12), ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 1), (-1, 1), INK),
        ("BOX", (0, 0), (-1, -1), 0.6, RULE), ("LINEBEFORE", (1, 0), (-1, -1), 0.6, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
    ]))
    story.append(Spacer(1, 0.25 * cm))
    story.append(fig_table)

    story.append(Paragraph("Confirmed suspects", h2))
    rows = [["#", "Wallet", "Role", "Victim funds", "Priority"]]
    for i, s in enumerate(confirmed, start=1):
        rows.append([
            str(i),
            Paragraph(escape(s["address"]), mono),
            Paragraph(escape(s["role_title"] + (f" ({s['exchange_name']})" if s.get("exchange_name") else "")), cell),
            Paragraph(f"{escape(format_amount(s['victim_funds'], case.chain))}"
                      f"<br/><font color='#647285'>{s['victim_share'] * 100:.0f}% of traced</font>", cell),
            Paragraph(f"<font color='{PRIORITY_COLOUR[s['priority']].hexval()}'><b>{s['priority'].upper()}</b></font>"
                      f"<br/><font color='#647285'>score {s['score']}</font>", cell),
        ])
    list_table = Table(rows, colWidths=[0.8 * cm, 6.9 * cm, 3.9 * cm, 3.1 * cm, 2.7 * cm], repeatRows=1)
    list_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 8), ("FONTSIZE", (0, 1), (0, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SUNK]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(list_table)

    story.append(Paragraph("Basis for each suspect", h2))
    for i, s in enumerate(confirmed, start=1):
        block = [Paragraph(f"{i}. {escape(s['role_title'])}", h3),
                 Paragraph(escape(s["address"]), mono),
                 Spacer(1, 0.12 * cm),
                 Paragraph(escape(s["role_description"]), small),
                 Spacer(1, 0.12 * cm)]
        signals = [r for r in s["reasons"] if r["kind"] == "signal"]
        caveats = [r for r in s["reasons"] if r["kind"] == "caveat"]
        for r in signals:
            block.append(Paragraph(f"•&nbsp;&nbsp;{escape(r['text'])}", body))
        for r in caveats:
            block.append(Paragraph(f"•&nbsp;&nbsp;<i>Caveat:</i> {escape(r['text'])}", body))

        txs = {}
        for r in s["reasons"]:
            for t in r["transactions"]:
                txs.setdefault(t["tx_hash"], t)
        if txs:
            tx_rows = [["Transaction", "Amount", "Time"]]
            for t in list(txs.values())[:8]:
                tx_rows.append([Paragraph(escape(t["tx_hash"]), mono),
                                format_amount(t["value"], case.chain), _when(t.get("timestamp"))])
            tx_table = Table(tx_rows, colWidths=[9.6 * cm, 3.2 * cm, 4.6 * cm])
            tx_table.setStyle(TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 7.5), ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            block += [Spacer(1, 0.15 * cm), tx_table]

        if s["linked_cases"]:
            refs = ", ".join(escape(c["complaint_ref"] or c["case_id"][:8]) for c in s["linked_cases"][:6])
            block.append(Spacer(1, 0.12 * cm))
            block.append(Paragraph(f"<b>Linked complaints:</b> {refs}", body))
        block.append(Spacer(1, 0.12 * cm))
        block.append(Paragraph(f"<b>Recommended action:</b> {escape(s['recommended_action'])}", body))
        d = s["decision"]
        confirmed_at = d.get("decided_at")
        try:
            confirmed_at = datetime.fromisoformat(confirmed_at).strftime("%d %b %Y, %H:%M UTC")
        except (TypeError, ValueError):
            pass
        block.append(Paragraph(
            f"<b>Confirmed by</b> {escape(d.get('decided_by') or '—')} on {escape(str(confirmed_at or '—'))}"
            + (f". <b>Officer's note:</b> {escape(d['note'])}" if d.get("note") else "."), body))
        block.append(Spacer(1, 0.4 * cm))
        # One suspect per unit: a basis split from its evidence across a page
        # break reads as two unrelated fragments.
        story.append(KeepTogether(block))

    story.append(Paragraph("Integrity", h2))
    story.append(Paragraph(
        f"SHA-256 of the case evidence and the confirmations above: "
        f"<font face='Courier'>{report_hash}</font>. Any change to the evidence, the list of "
        f"confirmed suspects or the officers' notes produces a different value. This report's "
        f"generation is recorded in the case's tamper-evident audit chain.", body))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Suspects are ranked from public blockchain data and a curated label set, then reviewed "
        "and confirmed by the named officer. A wallet address is not an identity: establishing "
        "who controls a wallet requires a legal request to the exchange or service concerned. "
        f"Amounts are in {escape(unit) or 'the chain’s native unit'} as recorded on-chain.", small))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(1.8 * cm, 1.1 * cm, f"Case {case.id} · Suspect report · confirmed suspects only")
        canvas.drawRightString(A4[0] - 1.8 * cm, 1.1 * cm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue(), report_hash
