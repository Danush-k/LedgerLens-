"""The investigation dossier: the whole case record in one document.

Where the legal notice is a letter to one exchange and the suspect report
names only who an officer has confirmed, this is the internal case file -
every finding the trace produced, every transfer it walked, whether the
confirmed suspects have been named yet or not. It is built to be filed, not
sent: a classification banner instead of an addressee, a case-particulars
block instead of a "To,", and a dossier's numbered sections instead of a
notice's directives.
"""
import hashlib
import io
import json
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from reportlab.platypus import SimpleDocTemplate

from app.models.orm import Case
from app.tracer.patterns import format_amount
from app.reports.letterhead import (SLATE as _SLATE, copy_to_block, evidence_certificate,
                                    letter_styles, letterhead_banner, make_canvas,
                                    ref_date_line, reference_number, signature_block,
                                    title_banner, verification_block)

SYSTEM_NAME = "LedgerLens (Real-Time Crypto Fraud Forensic Attribution System)"
SYSTEM_SHORT = "LedgerLens"
UNIT_NAME = "CYBER CRIME INVESTIGATION CELL"
UNIT_SUB = "Forensic Attribution Unit — Case Dossier generated via LedgerLens"


def _snapshot_hash(case: Case) -> str:
    """SHA-256 over everything this report asserts.

    The hash has to cover every claim the document makes, or it certifies
    less than it appears to. It previously covered only the graph, score and
    exchange, which meant the detector findings and wallet clusters could be
    rewritten without changing the "chain-of-custody" hash printed beside
    them - the reader would be told the evidence was intact while looking at
    altered evidence.
    """
    snapshot = {
        "case_id": case.id,
        "reported_address": case.reported_address,
        "chain": case.chain,
        "graph": case.graph,
        "risk_score": case.risk_score,
        "risk_breakdown": case.risk_breakdown,
        "flags": case.flags,
        "nearest_exchange": case.nearest_exchange,
        "patterns": case.patterns,
        "clusters": case.clusters,
        "fraud_typology": case.fraud_typology,
        "recommended_action": case.recommended_action,
    }
    payload = json.dumps(snapshot, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _section(title: str, styles: dict) -> Table:
    t = Table([[Paragraph(title, styles["section_head"])]], colWidths=[17.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _SLATE),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def build_case_report(case: Case, audit: dict | None = None,
                      confirmed_suspects: list[dict] | None = None,
                      prepared_by: str | None = None) -> bytes:
    styles = letter_styles()
    issue_date = datetime.now(timezone.utc)
    ref_no = reference_number("DOSSIER", case.id, when=issue_date)
    snapshot_hash = _snapshot_hash(case)

    story: list = []
    story.append(letterhead_banner(unit_name=UNIT_NAME, unit_sub=UNIT_SUB, styles=styles))
    story.append(Spacer(1, 0.3 * cm))
    story.append(title_banner(
        title="CONFIDENTIAL INVESTIGATION DOSSIER",
        subtitle="Blockchain Forensic Attribution Case File", styles=styles,
    ))
    story.append(Spacer(1, 0.25 * cm))
    story.append(ref_date_line(ref_no=ref_no, date_str=issue_date.strftime("%d-%m-%Y"), styles=styles))
    story.append(Spacer(1, 0.3 * cm))

    # ── Case particulars ────────────────────────────────────────────────
    story.append(_section("CASE PARTICULARS", styles))
    exchange = case.nearest_exchange or {}
    particulars = [
        [Paragraph("Case ID", styles["meta_label"]), Paragraph(escape(case.id), styles["table_mono"]),
         Paragraph("Complaint reference", styles["meta_label"]),
         Paragraph(escape(case.complaint_ref or "—"), styles["meta_value"])],
        [Paragraph("Reported wallet", styles["meta_label"]),
         Paragraph(escape(case.reported_address), styles["table_mono"]),
         Paragraph("Chain", styles["meta_label"]), Paragraph(case.chain.upper(), styles["meta_value"])],
        [Paragraph("Risk score", styles["meta_label"]),
         Paragraph(f"{case.risk_score:.0f} / 100" if case.risk_score is not None else "—", styles["meta_value"]),
         Paragraph("Fraud typology", styles["meta_label"]),
         Paragraph(escape((case.fraud_typology or "unclassified").replace("_", " ").title()), styles["meta_value"])],
        [Paragraph("Nearest exchange", styles["meta_label"]),
         Paragraph(escape(exchange.get("name") or "Not identified within hop limit"), styles["meta_value"]),
         Paragraph("Hops to exchange", styles["meta_label"]),
         Paragraph(str(exchange.get("hops", "—")), styles["meta_value"])],
        [Paragraph("Attribution basis", styles["meta_label"]),
         Paragraph(escape(exchange.get("source") or "Seed label set; source not recorded"), styles["meta_value"]),
         Paragraph("Prepared by", styles["meta_label"]),
         Paragraph(escape(prepared_by or "System export"), styles["meta_value"])],
        [Paragraph("Flags", styles["meta_label"]),
         Paragraph(escape(", ".join(case.flags or []) or "none"), styles["meta_value"]),
         Paragraph("Case opened", styles["meta_label"]),
         Paragraph(case.created_at.strftime("%d-%m-%Y") if case.created_at else "—", styles["meta_value"])],
    ]
    ptable = Table(particulars, colWidths=[3.1 * cm, 5.6 * cm, 3.3 * cm, 5.4 * cm])
    ptable.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(ptable)
    story.append(Spacer(1, 0.35 * cm))

    # ── Confirmed suspects ──────────────────────────────────────────────
    story.append(_section("CONFIRMED SUSPECTS", styles))
    story.append(Spacer(1, 0.1 * cm))
    if confirmed_suspects:
        story.append(Paragraph(
            "The following wallets have been reviewed and confirmed by the investigating "
            "officer. Wallets the system ranked but which have not been confirmed are "
            "omitted from this section; the full ranking with its reasoning is reproduced "
            "in the findings below.", styles["italic_note"]))
        suspect_rows = [[Paragraph("#", styles["table_head"]), Paragraph("Wallet", styles["table_head"]),
                         Paragraph("Role", styles["table_head"]), Paragraph("Victim funds", styles["table_head"]),
                         Paragraph("Confirmed by", styles["table_head"])]]
        for i, s in enumerate(confirmed_suspects, start=1):
            suspect_rows.append([
                Paragraph(str(i), styles["table_cell"]),
                Paragraph(escape(s["address"]), styles["table_mono"]),
                Paragraph(escape(s["role_title"]), styles["table_cell"]),
                Paragraph(escape(format_amount(s["victim_funds"], case.chain)), styles["table_cell"]),
                Paragraph(escape(s["decision"].get("decided_by") or "—"), styles["table_cell"]),
            ])
        suspect_table = Table(suspect_rows, colWidths=[0.8 * cm, 6.6 * cm, 3.6 * cm, 3.2 * cm, 3.2 * cm])
        suspect_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        story.append(suspect_table)
    else:
        story.append(Paragraph(
            "No suspects had been confirmed by the investigating officer at the time this "
            "dossier was exported.", styles["italic_note"]))
    story.append(Spacer(1, 0.3 * cm))

    story.append(_section("RECOMMENDED ACTION", styles))
    story.append(Spacer(1, 0.1 * cm))
    story.append(Paragraph(escape(case.recommended_action or "—"), styles["body"]))
    story.append(Spacer(1, 0.25 * cm))

    # ── Findings ────────────────────────────────────────────────────────
    findings = case.patterns or []
    if findings:
        story.append(_section("FINDINGS", styles))
        story.append(Spacer(1, 0.1 * cm))
        story.append(Paragraph(
            "Each finding below was produced by a named detector and carries the "
            "transactions it was derived from, so every statement can be checked "
            "against the public ledger independently of this system.", styles["italic_note"]))
        severity_order = {"high": 0, "medium": 1, "low": 2}
        finding_rows = [[Paragraph("Severity", styles["table_head"]), Paragraph("Finding", styles["table_head"]),
                         Paragraph("Evidence", styles["table_head"])]]
        for finding in sorted(findings, key=lambda f: severity_order.get(f.get("severity"), 3)):
            finding_rows.append([
                Paragraph((finding.get("severity") or "").upper(), styles["table_cell"]),
                Paragraph(escape(finding.get("title", "")), styles["table_cell"]),
                Paragraph(escape(finding.get("evidence", "")), styles["table_cell"]),
            ])
        findings_table = Table(finding_rows, colWidths=[1.8 * cm, 4 * cm, 11.6 * cm])
        findings_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        story.append(findings_table)
        story.append(Spacer(1, 0.3 * cm))

    # ── Evidence trail ──────────────────────────────────────────────────
    story.append(_section("EVIDENCE TRAIL — TRANSACTION HOPS", styles))
    story.append(Spacer(1, 0.1 * cm))
    graph = case.graph or {"nodes": [], "edges": []}
    story.append(Paragraph(
        "\"Victim share\" is the proportion of each transfer attributable to the reported "
        "victim, computed by the haircut method: a wallet holding funds from several "
        "sources forwards them in proportion. A share below 100% means the traced funds "
        "were mixed with money from outside this investigation.", styles["italic_note"]))
    edge_rows = [[Paragraph(h, styles["table_head"]) for h in
                 ("Hop", "From", "To", "Amount", "Victim share", "Tx hash", "Time (UTC)")]]
    address_by_id = {n["id"]: n["address"] for n in graph.get("nodes", [])}
    all_edges = sorted(graph.get("edges", []), key=lambda e: e["hop"])
    if len(all_edges) > 40:
        story.append(Paragraph(
            f"Showing the first 40 of {len(all_edges)} traced transfers, ordered by hop.",
            styles["italic_note"]))
    for edge in all_edges[:40]:
        ts = (datetime.fromtimestamp(edge["timestamp"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
              if edge["timestamp"] else "—")
        tainted = edge.get("tainted_value")
        share = f"{(tainted / edge['value'] * 100):.1f}%" if tainted is not None and edge["value"] else "—"
        edge_rows.append([
            Paragraph(str(edge["hop"]), styles["table_cell"]),
            Paragraph(f"{address_by_id.get(edge['source'], edge['source'])[:14]}…", styles["table_mono"]),
            Paragraph(f"{address_by_id.get(edge['target'], edge['target'])[:14]}…", styles["table_mono"]),
            Paragraph(f"{edge['value']:.6f}", styles["table_cell"]),
            Paragraph(share, styles["table_cell"]),
            Paragraph(f"{edge['tx_hash'][:12]}…", styles["table_mono"]),
            Paragraph(ts, styles["table_cell"]),
        ])
    evidence_table = Table(edge_rows, colWidths=[1 * cm, 2.9 * cm, 2.9 * cm, 2.2 * cm,
                                                  2.2 * cm, 2.6 * cm, 3.6 * cm])
    evidence_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(evidence_table)
    story.append(Spacer(1, 0.35 * cm))

    # ── Chain of custody ────────────────────────────────────────────────
    story.append(_section("CHAIN OF CUSTODY", styles))
    story.append(Spacer(1, 0.12 * cm))
    story.append(Paragraph(
        f"SHA-256 of this case's evidentiary data at export time: "
        f"<font face='Courier' size=7.5>{snapshot_hash}</font>. Recomputing this hash from "
        f"the exported case data at any later point confirms the evidence trail has not "
        f"been altered since this dossier was generated.", styles["body"]))
    if audit:
        intact = audit.get("intact")
        head = audit.get("chain_head")
        story.append(Paragraph(
            f"Audit record: {audit.get('entry_count', 0)} action(s) recorded for this case, "
            f"hash-chained so that altering, reordering or deleting any entry is detectable. "
            f"Status at export: <b>{'verified intact' if intact else 'DOES NOT VERIFY'}</b>."
            + (f" Chain head: <font face='Courier' size=7.5>{escape(head)}</font>." if head else "")
            + (f" {escape(audit.get('reason'))}" if not intact and audit.get("reason") else ""),
            styles["body"]))
    story.append(Spacer(1, 0.25 * cm))
    story.extend(evidence_certificate(officer_name=prepared_by or "the exporting officer",
                                      designation="Investigating Officer", system_name=SYSTEM_NAME,
                                      styles=styles))
    story.append(Spacer(1, 0.25 * cm))
    story.append(verification_block(
        doc_hash=snapshot_hash, ref_no=ref_no, styles=styles,
        verify_hint="Scan to confirm this dossier's reference number and evidentiary hash "
                    "against the case record."))
    story.append(Spacer(1, 0.35 * cm))

    if prepared_by:
        story.append(signature_block(officer_name=prepared_by, designation="Investigating Officer",
                                     unit_name=UNIT_NAME, styles=styles, place="—",
                                     closing="Prepared and exported by,"))
        story.append(Spacer(1, 0.25 * cm))

    story.append(copy_to_block(["Case diary / investigation file."], styles))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "This prototype traces publicly available on-chain data and flags addresses against a "
        "hand-curated seed label set, whose basis for each attribution is stated above. "
        "Exchange identification reflects on-chain deposit-address attribution only, not KYC "
        "identity - establishing who holds the account requires a legal request to the named "
        "exchange. Attribution should be confirmed with that exchange before it is relied on.",
        styles["italic_note"]))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.5 * cm, bottomMargin=2.2 * cm,
                            title=f"Investigation dossier — case {case.id}")
    CanvasCls = make_canvas(footer_left=f"{SYSTEM_SHORT} — system-generated document", ref_no=ref_no)
    doc.build(story, canvasmaker=CanvasCls)
    return buffer.getvalue()
