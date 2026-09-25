"""A Section 94 BNSS / Section 91 CrPC preservation notice, in the register
an Indian police officer actually writes one in: a reference-numbered
letter with a subject and reference line, numbered clauses, a lettered list
of directives, and a closing that names who it is from - not a form filled
in around a table of transactions.

The fund trail is still the evidentiary core of the document; it is now an
annexure the numbered clauses point to, the way a real notice attaches its
evidence rather than interleaving it with the demand.
"""
import hashlib
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from app.labels.loader import get_vasp_metadata
from app.models.orm import Case
from app.reports.letterhead import (clause, copy_to_block, crest_drawing,
                                    evidence_certificate, generated_notice,
                                    lettered_sub_clause, letter_styles,
                                    letterhead_banner, make_canvas, ref_date_line,
                                    reference_number, signature_block, title_banner,
                                    verification_block)

SYSTEM_NAME = "LedgerLens (Real-Time Crypto Fraud Forensic Attribution System)"
SYSTEM_SHORT = "LedgerLens"  # footer use only - the full name collides with the page number
UNIT_NAME = "CYBER CRIME INVESTIGATION CELL"
UNIT_SUB = "Forensic Attribution Unit — Notice generated via LedgerLens"


def _notice_hash(case: Case, *, ref_no: str, officer_name: str, effective_fir: str) -> str:
    payload = f"{case.id}:{case.reported_address}:{case.risk_score}:{ref_no}:{effective_fir}:{officer_name}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_legal_notice(
    case: Case,
    officer_name: str = "Investigating Officer",
    officer_designation: str = "Inspector of Police",
    police_station: str = "Cyber Crime Police Station",
    fir_number: str | None = None,
    fir_date: str | None = None,
    victim_name: str | None = None,
    act_section: str = "bnss_94",
) -> bytes:
    """A formal, printable Indian law-enforcement preservation notice under
    Section 94 BNSS 2023 (successor to Section 91 CrPC 1973), addressed to
    the exchange whose deposit address the traced funds reached."""
    styles = letter_styles()
    exchange = case.nearest_exchange or {}
    vasp_name = exchange.get("name", "Cryptocurrency Exchange / VASP")
    vasp_meta = get_vasp_metadata(vasp_name.split(":")[0].strip()) or {}

    effective_fir = fir_number or case.complaint_ref or "Under inquiry (pre-FIR complaint)"
    fir_dt = fir_date or datetime.now(timezone.utc).strftime("%d-%m-%Y")
    issue_date = datetime.now(timezone.utc)
    ref_no = reference_number("BNSS94" if act_section.lower() != "crpc_91" else "CRPC91",
                              case.id, when=issue_date)
    notice_hash = _notice_hash(case, ref_no=ref_no, officer_name=officer_name,
                               effective_fir=effective_fir)

    if act_section.lower() == "crpc_91":
        act_name = "Section 91 of the Code of Criminal Procedure, 1973"
        act_short = "Section 91 Cr.P.C."
    else:
        act_name = "Section 94 of the Bharatiya Nagarik Suraksha Sanhita, 2023"
        act_short = "Section 94 BNSS"

    story: list = []

    # ── Letterhead ──────────────────────────────────────────────────────
    story.append(letterhead_banner(unit_name=UNIT_NAME, unit_sub=UNIT_SUB, styles=styles))
    story.append(Spacer(1, 0.3 * cm))
    story.append(title_banner(
        title=f"LEGAL NOTICE UNDER {act_short.upper()}",
        subtitle="Demand for Preservation of Electronic Records and Account Information",
        styles=styles,
    ))
    story.append(Spacer(1, 0.25 * cm))
    story.append(ref_date_line(ref_no=ref_no, date_str=issue_date.strftime("%d-%m-%Y"), styles=styles))
    story.append(Spacer(1, 0.35 * cm))

    # ── Addressee ───────────────────────────────────────────────────────
    addressee = Table([[Paragraph(
        "To,<br/>"
        f"The Nodal Officer / Law Enforcement Liaison Officer<br/>"
        f"<b>{escape(vasp_meta.get('full_name', vasp_name))}</b><br/>"
        f"Compliance contact: {escape(vasp_meta.get('compliance_email', 'lawenforcement@vasp.internal'))}<br/>"
        f"Jurisdiction of registration: {escape(vasp_meta.get('jurisdiction', 'International VASP'))}"
        + (f"<br/>Law-enforcement portal: {escape(vasp_meta.get('portal_url'))}"
           if vasp_meta.get("portal_url") else ""),
        styles["salutation"],
    )]], colWidths=[17.4 * cm])
    story.append(addressee)
    story.append(Spacer(1, 0.3 * cm))

    subject = (
        f"Preservation of electronic records, account information and Know-Your-Customer "
        f"(KYC) details under {act_short} regarding cyber financial fraud traced to your "
        f"deposit infrastructure — Complaint/FIR Ref. {escape(effective_fir)}."
    )
    story.append(Paragraph(f"<b>Subject:</b> {subject}", styles["salutation"]))
    story.append(Spacer(1, 0.15 * cm))
    story.append(Paragraph(
        f"<b>Reference:</b> 1. Complaint/FIR No. {escape(effective_fir)} dated {escape(fir_dt)}, "
        f"{escape(police_station)}.<br/>"
        f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2. Forensic blockchain trace Case ID "
        f"<font face='Courier' size=7.5>{escape(case.id)}</font>, generated via {SYSTEM_NAME}.",
        styles["salutation"],
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Sir/Madam,", styles["salutation"]))
    story.append(Spacer(1, 0.15 * cm))

    # ── Numbered body ───────────────────────────────────────────────────
    n = 1
    story.append(clause(n,
        f"This office is investigating a case of cyber-enabled financial fraud under the "
        f"relevant provisions of the Bharatiya Nyaya Sanhita, 2023 and the Information "
        f"Technology Act, 2000, in respect of which the complainant reported the loss of "
        f"funds to the wallet address <font face='Courier' size=8>{escape(case.reported_address)}</font> "
        f"on the <b>{escape(case.chain.upper())}</b> blockchain.",
        styles)); n += 1
    story.append(Spacer(1, 0.15 * cm))

    story.append(clause(n,
        f"Automated multi-hop blockchain forensic tracing conducted through {SYSTEM_NAME} "
        f"has established that funds originating from the above wallet were transferred, "
        f"across the hops set out at Annexure-A to this notice, and reached a deposit "
        f"address under your platform's control at <b>Hop {exchange.get('hops', 1)}</b>. "
        f"The attribution of that deposit address to your platform is recorded as: "
        f"<i>{escape(exchange.get('source') or 'seed label set; source not separately recorded')}.</i>",
        styles)); n += 1
    story.append(Spacer(1, 0.15 * cm))

    story.append(clause(n,
        f"In exercise of the powers vested in the undersigned under {act_name}, you are "
        f"hereby directed to take the following action within <b>twenty-four (24) hours</b> "
        f"of receipt of this notice, and to preserve the records described below pending "
        f"a formal judicial or regulatory request for their production:",
        styles))
    story.append(Spacer(1, 0.15 * cm))

    directives = [
        ("Immediate account restriction", "Place an immediate administrative freeze or debit "
         "restriction on the internal account, wallet or sub-account associated with deposit "
         f"address <font face='Courier' size=8>{escape(exchange.get('address') or case.reported_address)}</font>, "
         "sufficient to prevent further dissipation of the traced proceeds."),
        ("KYC and beneficial-owner details", "Furnish complete Know-Your-Customer records for "
         "the account holder, including registered name, date of birth, verified address, "
         "government identity documents on file, verified mobile number and email address."),
        ("Linked fiat and payment details", "Provide all linked bank account numbers, IFSC "
         "codes, UPI virtual payment addresses and card details used for INR deposit or "
         "withdrawal against the account."),
        ("Access and device logs", "Supply IP address login history with timestamps, "
         "user-agent strings and device identifiers associated with the account for the "
         "preceding one hundred and eighty (180) days."),
        ("Downstream withdrawal trail", "Where the funds identified above have already been "
         "withdrawn or further transferred, provide the destination addresses and "
         "transaction identifiers for each such movement."),
    ]
    for i, (head, body) in enumerate(directives):
        letter = chr(ord("a") + i)
        story.append(lettered_sub_clause(letter, f"<b>{escape(head)}.</b> {body}", styles))
    story.append(Spacer(1, 0.2 * cm))
    n += 1

    story.append(clause(n,
        "You are expressly directed not to inform, alert or otherwise tip off the account "
        "holder regarding this notice or the underlying inquiry. Any such disclosure may "
        "prejudice an ongoing criminal investigation.",
        styles)); n += 1
    story.append(Spacer(1, 0.15 * cm))

    story.append(clause(n,
        "Non-compliance, or the destruction, alteration or withholding of the records "
        "sought above after receipt of this notice, may be reported to the Financial "
        "Intelligence Unit — India (FIU-IND) and may attract action under the applicable "
        "provisions of the Bharatiya Nyaya Sanhita, 2023 relating to obstruction of a "
        "criminal investigation, in addition to any regulatory consequence before the "
        "authority under which your platform is registered.",
        styles))
    story.append(Spacer(1, 0.35 * cm))

    # ── Annexure-A: fund trail ──────────────────────────────────────────
    story.append(Table([[Paragraph("ANNEXURE-A — FORENSIC FUND TRAIL", styles["section_head"])]],
                       colWidths=[17.4 * cm], style=TableStyle([
                           ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#334155")),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8),
                       ])))
    story.append(Spacer(1, 0.15 * cm))

    graph = case.graph or {"nodes": [], "edges": []}
    all_edges = sorted(graph.get("edges", []), key=lambda e: e.get("hop", 0))
    if len(all_edges) > 8:
        story.append(Paragraph(
            f"Showing the first 8 of {len(all_edges)} traced transfers, ordered by hop. "
            f"The complete fund trail is available on request from the case record.",
            styles["italic_note"]))
    address_by_id = {node["id"]: node.get("address") or node["id"].split(":")[-1] for node in graph.get("nodes", [])}
    trail_rows = [[
        Paragraph("Hop", styles["table_head"]), Paragraph("From", styles["table_head"]),
        Paragraph("To (deposit)", styles["table_head"]), Paragraph("Value", styles["table_head"]),
        Paragraph("Tx hash", styles["table_head"]), Paragraph("Time (UTC)", styles["table_head"]),
    ]]
    for edge in all_edges[:8]:
        ts = (datetime.fromtimestamp(edge["timestamp"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
              if edge.get("timestamp") else "—")
        trail_rows.append([
            Paragraph(str(edge.get("hop", 1)), styles["table_cell"]),
            Paragraph(f"{address_by_id.get(edge['source'], edge['source'])[:16]}…", styles["table_mono"]),
            Paragraph(f"{address_by_id.get(edge['target'], edge['target'])[:16]}…", styles["table_mono"]),
            Paragraph(f"{edge.get('value', 0):.6f} {case.chain.upper()}", styles["table_cell"]),
            Paragraph(f"{edge.get('tx_hash', '')[:14]}…", styles["table_mono"]),
            Paragraph(ts, styles["table_cell"]),
        ])
    trail_table = Table(trail_rows, colWidths=[1.1 * cm, 3.7 * cm, 3.7 * cm, 2.7 * cm, 3 * cm, 3.2 * cm])
    trail_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    story.append(trail_table)
    story.append(Spacer(1, 0.35 * cm))

    # ── Evidence certificate, verification, signature ───────────────────
    story.extend(evidence_certificate(officer_name=officer_name, designation=officer_designation,
                                      system_name=SYSTEM_NAME, styles=styles))
    story.append(Spacer(1, 0.3 * cm))
    story.append(verification_block(
        doc_hash=notice_hash, ref_no=ref_no, styles=styles,
        verify_hint="Scan to confirm this notice's reference number and hash against the case "
                    "record. Recomputing the hash from the case data reproduces this value only "
                    "if the notice has not been altered since it was issued.",
    ))
    story.append(Spacer(1, 0.4 * cm))
    story.append(signature_block(
        officer_name=officer_name, designation=officer_designation, unit_name=police_station,
        styles=styles, place=police_station.replace("Cyber Crime", "").replace("Police Station", "").strip(" ,") or "—",
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(copy_to_block([
        "Superintendent of Police / Deputy Commissioner of Police, Cyber Crime — for information.",
        "Financial Intelligence Unit — India (FIU-IND) — for information.",
        "Indian Cyber Crime Coordination Centre (I4C), Ministry of Home Affairs — for information.",
        "Case diary / investigation file.",
    ], styles))
    story.append(Spacer(1, 0.2 * cm))
    story.append(generated_notice(SYSTEM_NAME, styles))

    from io import BytesIO
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.5 * cm, bottomMargin=2.2 * cm,
                            title=f"Legal notice — case {case.id}")
    CanvasCls = make_canvas(footer_left=f"{SYSTEM_SHORT} — system-generated document", ref_no=ref_no)
    doc.build(story, canvasmaker=CanvasCls)
    return buffer.getvalue()
