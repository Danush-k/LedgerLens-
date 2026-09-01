import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.labels.loader import get_vasp_metadata
from app.models.orm import Case


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
    """Generates a formal, printable Indian Law Enforcement Preservation Notice
    under Section 94 BNSS 2023 / Section 91 Cr.P.C. 1973."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
    )
    styles = getSampleStyleSheet()

    # Custom styles
    header_style = ParagraphStyle(
        "NoticeHeader",
        parent=styles["Heading1"],
        fontSize=15,
        leading=18,
        alignment=1,  # Center
        textColor=colors.HexColor("#0f172a"),
        fontName="Helvetica-Bold",
    )
    sub_header_style = ParagraphStyle(
        "SubHeader",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        alignment=1,
        textColor=colors.HexColor("#b91c1c"),
        fontName="Helvetica-Bold",
    )
    section_heading = ParagraphStyle(
        "SectionHead",
        parent=styles["Heading2"],
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1e293b"),
        fontName="Helvetica-Bold",
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "NoticeBody",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#334155"),
    )
    table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1e293b"),
    )
    bold_cell = ParagraphStyle(
        "BoldCell",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0f172a"),
    )

    story = []

    # Title & Legal Section Header
    story.append(Paragraph("OFFICE OF THE INVESTIGATING OFFICER", header_style))
    story.append(Paragraph(police_station.upper(), header_style))
    story.append(Spacer(1, 0.2 * cm))

    if act_section.lower() == "crpc_91":
        legal_banner = "LEGAL NOTICE UNDER SECTION 91 OF THE CODE OF CRIMINAL PROCEDURE (Cr.P.C.), 1973"
    else:
        legal_banner = "LEGAL NOTICE UNDER SECTION 94 OF THE BHARATIYA NAGARIK SURAKSHA SANHITA (BNSS), 2023"

    story.append(Paragraph(f"<b>{legal_banner}</b>", sub_header_style))
    story.append(Paragraph("<b>(DEMAND FOR IMMEDIATE EVIDENCE PRESERVATION & ACCOUNT RESTRICTION)</b>", sub_header_style))
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0f172a"), spaceAfter=10))

    # Addressee VASP details
    exchange_info = case.nearest_exchange or {}
    vasp_name = exchange_info.get("name", "Cryptocurrency Exchange / VASP")
    vasp_meta = get_vasp_metadata(vasp_name.split(":")[0].strip()) or {}

    addressee_text = f"""
    <b>TO:</b><br/>
    <b>The Nodal Officer / Law Enforcement Liaison Officer</b><br/>
    <b>Entity Name:</b> {vasp_meta.get('full_name', vasp_name)}<br/>
    <b>Designated Compliance Email:</b> {vasp_meta.get('compliance_email', 'lawenforcement@vasp.internal')}<br/>
    <b>Jurisdiction / Registration:</b> {vasp_meta.get('jurisdiction', 'International VASP')}<br/>
    <b>Law Enforcement Portal:</b> {vasp_meta.get('portal_url', 'N/A')}
    """
    story.append(Paragraph(addressee_text, body_style))
    story.append(Spacer(1, 0.3 * cm))

    # Investigation Metadata Table
    effective_fir = fir_number or case.complaint_ref or "UNDER_INQUIRY"
    fir_dt = fir_date or datetime.now(timezone.utc).strftime("%d-%b-%Y")
    meta_rows = [
        [Paragraph("<b>Investigation / FIR Ref:</b>", bold_cell), Paragraph(effective_fir, table_cell),
         Paragraph("<b>Date of Issue:</b>", bold_cell), Paragraph(datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M UTC"), table_cell)],
        [Paragraph("<b>Investigating Officer:</b>", bold_cell), Paragraph(f"{officer_name} ({officer_designation})", table_cell),
         Paragraph("<b>Police Station:</b>", bold_cell), Paragraph(police_station, table_cell)],
        [Paragraph("<b>Victim Name / NCRP ID:</b>", bold_cell), Paragraph(victim_name or case.complaint_ref or "Victim Confidential", table_cell),
         Paragraph("<b>Fraud Typology:</b>", bold_cell), Paragraph((case.fraud_typology or "Cyber Financial Fraud").upper(), table_cell)],
    ]
    meta_table = Table(meta_rows, colWidths=[4 * cm, 4.5 * cm, 4 * cm, 4.5 * cm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.3 * cm))

    # Formal Demand Statement
    intro_p = f"""
    Whereas the undersigned is investigating a cyber-enabled fraud / financial crime under relevant provisions of the Indian Penal Code / Bharatiya Nyaya Sanhita (BNS) and the Information Technology Act, 2000. During automated blockchain forensic tracing conducted via <b>LedgerLens</b>, proceed-of-crime funds originating from victim-reported suspect wallet <code>{case.reported_address}</code> on the <b>{case.chain.upper()}</b> blockchain have been attributed directly to your exchange deposit infrastructure at <b>Hop {exchange_info.get('hops', 1)}</b>.
    """
    story.append(Paragraph(intro_p, body_style))

    # Evidence Trail Table
    story.append(Paragraph("1. Identified Target Deposit Wallet & Forensic Fund Trail", section_heading))
    graph = case.graph or {"nodes": [], "edges": []}
    address_by_id = {n["id"]: n.get("address", n["id"].split(":")[-1]) for n in graph.get("nodes", [])}

    trail_rows = [[Paragraph("<b>Hop</b>", bold_cell), Paragraph("<b>From Address</b>", bold_cell),
                   Paragraph("<b>To Address (Deposit)</b>", bold_cell), Paragraph("<b>Value</b>", bold_cell),
                   Paragraph("<b>Tx Hash</b>", bold_cell), Paragraph("<b>Timestamp (UTC)</b>", bold_cell)]]

    for edge in sorted(graph.get("edges", []), key=lambda e: e.get("hop", 0))[:6]:
        ts = datetime.fromtimestamp(edge["timestamp"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M") if edge.get("timestamp") else "—"
        trail_rows.append([
            Paragraph(str(edge.get("hop", 1)), table_cell),
            Paragraph(f"<code>{address_by_id.get(edge['source'], edge['source'])[:14]}…</code>", table_cell),
            Paragraph(f"<code>{address_by_id.get(edge['target'], edge['target'])[:14]}…</code>", table_cell),
            Paragraph(f"{edge.get('value', 0):.4f} {case.chain.upper()}", table_cell),
            Paragraph(f"<code>{edge.get('tx_hash', '')[:14]}…</code>", table_cell),
            Paragraph(ts, table_cell),
        ])

    trail_table = Table(trail_rows, colWidths=[1.2 * cm, 3.8 * cm, 3.8 * cm, 2.5 * cm, 3.2 * cm, 2.5 * cm])
    trail_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(trail_table)

    # Mandatory Legal Directives
    story.append(Paragraph("2. Mandatory Legal Directives (Action Required within 24 Hours)", section_heading))
    directives = """
    In exercise of statutory powers under the aforementioned Act, you are hereby directed to produce/furnish the following information and take immediate preservation measures:
    <br/>
    <b>A. IMMEDIATE ACCOUNT FREEZE:</b> Place an immediate administrative freeze / debit restriction on the internal account UID, wallet, or sub-account associated with deposit address <code>""" + (exchange_info.get("address") or case.reported_address) + """</code> to prevent dissipation of crime proceeds.
    <br/>
    <b>B. KYC & BENEFICIAL OWNER DETAILS:</b> Furnish complete KYC documentation including Registered Name, Father's Name, Date of Birth, Verified Physical Address, Aadhaar / PAN / Passport copies, Verified Mobile Number, and Email ID.
    <br/>
    <b>C. FIAT BANKING DETAILS:</b> Provide complete linked bank account numbers, IFSC codes, UPI VPA handles, and credit/debit card details utilized for fiat deposits / INR withdrawals.
    <br/>
    <b>D. ACCESS & TECHNICAL IP LOGS:</b> Supply complete IP login logs with timestamps (UTC/IST), User-Agent strings, IMEI/Device IDs, and MAC addresses for the past 180 days.
    <br/>
    <b>E. DOWNSTREAM WITHDRAWAL TRAIL:</b> If funds have already been liquidated or withdrawn, provide all destination addresses and TXIDs immediately.
    """
    story.append(Paragraph(directives, body_style))

    # Confidentiality and Non-Disclosure Notice
    story.append(Paragraph("3. Confidentiality & Non-Disclosure Requirement", section_heading))
    confidentiality = """
    <b>STRICT CONFIDENTIALITY:</b> You are expressly prohibited from tipping off or informing the account holder regarding this inquiry. Any disclosure may prejudice ongoing criminal proceedings and attract penal liability under applicable laws.
    """
    story.append(Paragraph(confidentiality, body_style))
    story.append(Spacer(1, 0.4 * cm))

    # Signature Block & Integrity Hash
    raw_hash_data = f"{case.id}:{case.reported_address}:{case.risk_score}:{effective_fir}:{officer_name}"
    notice_hash = hashlib.sha256(raw_hash_data.encode("utf-8")).hexdigest()

    sig_table = Table([
        [Paragraph(f"<b>Cryptographic Notice Integrity Hash:</b><br/><code>{notice_hash}</code>", body_style),
         Paragraph(f"<br/><b>({officer_name})</b><br/>{officer_designation}<br/>{police_station}<br/><i>(Authorized Digital Signature)</i>", ParagraphStyle("Sig", parent=body_style, alignment=2))]
    ], colWidths=[10 * cm, 7 * cm])
    sig_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEABOVE", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
    ]))
    story.append(sig_table)

    doc.build(story)
    return buffer.getvalue()
