"""The suspect report: confirmed suspects only, each with its evidence, in
the register of a document meant to leave the investigator's desk - for a
supervising officer, a prosecutor, or an exchange's law-enforcement desk.

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
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from app.models.orm import Case
from app.reports.letterhead import (SLATE as _SLATE, copy_to_block, evidence_certificate,
                                    letter_styles, letterhead_banner, make_canvas,
                                    ref_date_line, reference_number, signature_block,
                                    title_banner, verification_block)
from app.reports.pdf import _snapshot_hash
from app.tracer.patterns import format_amount

SYSTEM_NAME = "LedgerLens (Real-Time Crypto Fraud Forensic Attribution System)"
SYSTEM_SHORT = "LedgerLens"
UNIT_NAME = "CYBER CRIME INVESTIGATION CELL"
UNIT_SUB = "Forensic Attribution Unit — Suspect Report generated via LedgerLens"
PRIORITY_COLOUR = {"high": colors.HexColor("#8a1c1c"), "medium": colors.HexColor("#92610a"),
                   "low": colors.HexColor("#1d6b47")}


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


def _section(title: str, styles: dict) -> Table:
    t = Table([[Paragraph(title, styles["section_head"])]], colWidths=[17.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _SLATE),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def build_suspect_report(case: Case, summary: dict, confirmed: list[dict],
                          generated_by: str) -> tuple[bytes, str]:
    styles = letter_styles()
    unit = summary.get("unit") or ""
    report_hash = suspect_report_hash(case, confirmed)
    issue_date = datetime.now(timezone.utc)
    ref_no = reference_number("SUSPECT", case.id, when=issue_date)

    story: list = []
    story.append(letterhead_banner(unit_name=UNIT_NAME, unit_sub=UNIT_SUB, styles=styles))
    story.append(Spacer(1, 0.3 * cm))
    story.append(title_banner(title="SUSPECT IDENTIFICATION REPORT",
                              subtitle="Officer-Confirmed Suspects and Supporting Evidence",
                              styles=styles))
    story.append(Spacer(1, 0.25 * cm))
    story.append(ref_date_line(ref_no=ref_no, date_str=issue_date.strftime("%d-%m-%Y"), styles=styles))
    story.append(Spacer(1, 0.3 * cm))

    meta = [
        [Paragraph("Case ID", styles["meta_label"]), Paragraph(escape(case.id), styles["table_mono"]),
         Paragraph("Complaint ref.", styles["meta_label"]),
         Paragraph(escape(case.complaint_ref or "—"), styles["meta_value"])],
        [Paragraph("Chain", styles["meta_label"]), Paragraph(case.chain.upper(), styles["meta_value"]),
         Paragraph("Prepared by", styles["meta_label"]), Paragraph(escape(generated_by), styles["meta_value"])],
        [Paragraph("Reported wallet", styles["meta_label"]),
         Paragraph(escape(case.reported_address), styles["table_mono"]),
         Paragraph("Confirmed suspects", styles["meta_label"]), Paragraph(str(len(confirmed)), styles["meta_value"])],
    ]
    meta_table = Table(meta, colWidths=[3.1 * cm, 5.6 * cm, 3.3 * cm, 5.4 * cm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.3 * cm))

    story.append(_section("WHAT HAPPENED", styles))
    story.append(Spacer(1, 0.1 * cm))
    story.append(Paragraph(escape(summary.get("headline") or "—"), styles["body"]))

    figures = [
        [Paragraph(h, styles["meta_label"]) for h in
         ("Victim funds traced", "Reached exchanges", "Still in wallets", "Confirmed suspects")],
        [Paragraph(f"<b>{escape(format_amount(summary.get('victim_total', 0), case.chain))}</b>",
                  styles["meta_value"]),
         Paragraph(f"<b>{escape(format_amount(summary.get('to_exchanges', 0), case.chain))}</b>",
                  styles["meta_value"]),
         Paragraph(f"<b>{escape(format_amount(summary.get('still_held', 0), case.chain))}</b>",
                  styles["meta_value"]),
         Paragraph(f"<b>{len(confirmed)}</b>", styles["meta_value"])],
    ]
    fig_table = Table(figures, colWidths=[4.35 * cm] * 4)
    fig_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
        ("LINEBEFORE", (1, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(fig_table)
    story.append(Spacer(1, 0.3 * cm))

    story.append(_section(f"CONFIRMED SUSPECTS ({len(confirmed)})", styles))
    story.append(Spacer(1, 0.1 * cm))
    rows = [[Paragraph(h, styles["table_head"]) for h in
            ("#", "Wallet", "Role", "Victim funds", "Priority")]]
    for i, s in enumerate(confirmed, start=1):
        rows.append([
            Paragraph(str(i), styles["table_cell"]),
            Paragraph(escape(s["address"]), styles["table_mono"]),
            Paragraph(escape(s["role_title"] + (f" ({s['exchange_name']})" if s.get("exchange_name") else "")),
                     styles["table_cell"]),
            Paragraph(f"{escape(format_amount(s['victim_funds'], case.chain))}"
                      f"<br/><font color='#64748b' size=7>{s['victim_share'] * 100:.0f}% of traced</font>",
                     styles["table_cell"]),
            Paragraph(f"<font color='{PRIORITY_COLOUR[s['priority']].hexval()}'><b>{s['priority'].upper()}</b></font>"
                      f"<br/><font color='#64748b' size=7>score {s['score']}</font>", styles["table_cell"]),
        ])
    list_table = Table(rows, colWidths=[0.8 * cm, 6.7 * cm, 3.8 * cm, 3.1 * cm, 3 * cm], repeatRows=1)
    list_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(list_table)
    story.append(Spacer(1, 0.3 * cm))

    story.append(_section("BASIS FOR EACH SUSPECT", styles))
    story.append(Spacer(1, 0.15 * cm))
    for i, s in enumerate(confirmed, start=1):
        head = Table([[Paragraph(f"{i}.", styles["clause_num"]),
                       Paragraph(f"<b>{escape(s['role_title'])}</b> — "
                                f"<font face='Courier' size=8>{escape(s['address'])}</font>",
                                styles["meta_value"])]],
                     colWidths=[0.8 * cm, 16.6 * cm])
        head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                  ("TOPPADDING", (0, 0), (-1, -1), 0),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                                  ("LEFTPADDING", (0, 0), (0, 0), 0),
                                  ("RIGHTPADDING", (0, 0), (0, 0), 2)]))
        block = [head, Spacer(1, 0.1 * cm),
                Paragraph(escape(s["role_description"]), styles["italic_note"])]

        signals = [r for r in s["reasons"] if r["kind"] == "signal"]
        caveats = [r for r in s["reasons"] if r["kind"] == "caveat"]
        for r in signals:
            block.append(Paragraph(f"•&nbsp;&nbsp;{escape(r['text'])}", styles["body"]))
        for r in caveats:
            block.append(Paragraph(f"•&nbsp;&nbsp;<i>Caveat:</i> {escape(r['text'])}", styles["body"]))

        txs: dict[str, dict] = {}
        for r in s["reasons"]:
            for t in r["transactions"]:
                txs.setdefault(t["tx_hash"], t)
        if txs:
            tx_rows = [[Paragraph(h, styles["table_head"]) for h in ("Transaction", "Amount", "Time")]]
            for t in list(txs.values())[:8]:
                tx_rows.append([Paragraph(escape(t["tx_hash"]), styles["table_mono"]),
                                Paragraph(format_amount(t["value"], case.chain), styles["table_cell"]),
                                Paragraph(_when(t.get("timestamp")), styles["table_cell"])])
            tx_table = Table(tx_rows, colWidths=[9.4 * cm, 3.2 * cm, 4.8 * cm])
            tx_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            block += [Spacer(1, 0.15 * cm), tx_table]

        if s["linked_cases"]:
            refs = ", ".join(escape(c["complaint_ref"] or c["case_id"][:8]) for c in s["linked_cases"][:6])
            block.append(Spacer(1, 0.12 * cm))
            block.append(Paragraph(f"<b>Linked complaints:</b> {refs}", styles["body"]))
        block.append(Spacer(1, 0.12 * cm))
        block.append(Paragraph(f"<b>Recommended action:</b> {escape(s['recommended_action'])}", styles["body"]))

        d = s["decision"]
        confirmed_at = d.get("decided_at")
        try:
            confirmed_at = datetime.fromisoformat(confirmed_at).strftime("%d %b %Y, %H:%M UTC")
        except (TypeError, ValueError):
            pass
        block.append(Paragraph(
            f"<b>Confirmed by</b> {escape(d.get('decided_by') or '—')} on {escape(str(confirmed_at or '—'))}"
            + (f". <b>Officer's note:</b> {escape(d['note'])}" if d.get("note") else "."),
            styles["body"]))
        block.append(Spacer(1, 0.35 * cm))
        # One suspect per unit: a basis split from its evidence across a page
        # break reads as two unrelated fragments.
        story.append(KeepTogether(block))

    story.append(Spacer(1, 0.15 * cm))
    story.extend(evidence_certificate(officer_name=generated_by, designation="Investigating Officer",
                                      system_name=SYSTEM_NAME, styles=styles))
    story.append(Spacer(1, 0.25 * cm))
    story.append(verification_block(
        doc_hash=report_hash, ref_no=ref_no, styles=styles,
        verify_hint="Scan to confirm this report's list of confirmed suspects and officers' "
                    "notes against the case record. Any change to either produces a different "
                    "hash."))
    story.append(Spacer(1, 0.35 * cm))
    story.append(signature_block(officer_name=generated_by, designation="Investigating Officer",
                                 unit_name=UNIT_NAME, styles=styles, place="—",
                                 closing="Compiled and confirmed by,"))
    story.append(Spacer(1, 0.25 * cm))
    story.append(copy_to_block(["Case diary / investigation file.",
                                "Supervising officer — for review."], styles))
    story.append(Spacer(1, 0.2 * cm))
    unit_label = escape(unit) or "the chain's native unit"
    story.append(Paragraph(
        "Suspects are ranked from public blockchain data and a curated label set, then "
        "reviewed and confirmed by the named officer. A wallet address is not an identity: "
        "establishing who controls a wallet requires a legal request to the exchange or "
        f"service concerned. Amounts are in {unit_label} as recorded on-chain.",
        styles["italic_note"]))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.5 * cm, bottomMargin=2.2 * cm,
                            title=f"Suspect report — case {case.id}")
    CanvasCls = make_canvas(footer_left=f"{SYSTEM_SHORT} — confirmed suspects only", ref_no=ref_no)
    doc.build(story, canvasmaker=CanvasCls)
    return buffer.getvalue(), report_hash
