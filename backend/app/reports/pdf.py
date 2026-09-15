import hashlib
import io
import json
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.orm import Case


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


def build_case_report(case: Case, audit: dict | None = None) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("LedgerLens — Investigation Report", styles["Title"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(f"Case ID: {case.id}", styles["Normal"]))
    story.append(Paragraph(f"Complaint reference: {case.complaint_ref or '—'}", styles["Normal"]))
    story.append(Paragraph(f"Generated: {datetime.now(timezone.utc).isoformat()}", styles["Normal"]))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Summary", styles["Heading2"]))
    summary_rows = [
        ["Reported wallet", case.reported_address],
        ["Chain", case.chain],
        ["Risk score", f"{case.risk_score:.0f} / 100" if case.risk_score is not None else "—"],
        ["Nearest exchange", (case.nearest_exchange or {}).get("name", "Not identified within hop limit")],
        ["Attribution basis", (case.nearest_exchange or {}).get("source")
                              or "Seed label set; source not recorded"],
        ["Hops to exchange", str((case.nearest_exchange or {}).get("hops", "—"))],
        ["Flags", ", ".join(case.flags or []) or "none"],
    ]
    table = Table(summary_rows, colWidths=[5 * cm, 10 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Recommended action", styles["Heading2"]))
    story.append(Paragraph(case.recommended_action or "—", styles["Normal"]))
    story.append(Spacer(1, 0.5 * cm))

    findings = case.patterns or []
    if findings:
        story.append(Paragraph("Findings", styles["Heading2"]))
        story.append(Paragraph(
            "Each finding below was produced by a named detector and carries the "
            "transactions it was derived from, so every statement can be checked "
            "against the public ledger independently of this system.",
            styles["Italic"],
        ))
        story.append(Spacer(1, 0.25 * cm))
        severity_order = {"high": 0, "medium": 1, "low": 2}
        finding_rows = [["Severity", "Finding", "Evidence"]]
        for finding in sorted(findings, key=lambda f: severity_order.get(f.get("severity"), 3)):
            finding_rows.append([
                (finding.get("severity") or "").upper(),
                Paragraph(finding.get("title", ""), styles["BodyText"]),
                Paragraph(finding.get("evidence", ""), styles["BodyText"]),
            ])
        findings_table = Table(finding_rows, colWidths=[1.8 * cm, 4 * cm, 11.2 * cm])
        findings_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
        ]))
        story.append(findings_table)
        story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Evidence trail (transaction hops)", styles["Heading2"]))
    graph = case.graph or {"nodes": [], "edges": []}
    story.append(Paragraph(
        "\"Victim share\" is the proportion of each transfer attributable to the "
        "reported victim, computed by the haircut method: a wallet holding funds "
        "from several sources forwards them in proportion. A share below 100% means "
        "the traced funds were mixed with money from outside this investigation.",
        styles["Italic"],
    ))
    story.append(Spacer(1, 0.25 * cm))
    edge_rows = [["Hop", "From", "To", "Amount", "Victim share", "Tx hash", "Timestamp"]]
    address_by_id = {n["id"]: n["address"] for n in graph.get("nodes", [])}
    for edge in sorted(graph.get("edges", []), key=lambda e: e["hop"]):
        ts = datetime.fromtimestamp(edge["timestamp"], tz=timezone.utc).isoformat() if edge["timestamp"] else "—"
        tainted = edge.get("tainted_value")
        share = (
            f"{(tainted / edge['value'] * 100):.1f}%"
            if tainted is not None and edge["value"] else "—"
        )
        edge_rows.append([
            str(edge["hop"]),
            address_by_id.get(edge["source"], edge["source"])[:16] + "…",
            address_by_id.get(edge["target"], edge["target"])[:16] + "…",
            f"{edge['value']:.6f}",
            share,
            edge["tx_hash"][:16] + "…",
            ts,
        ])
    evidence_table = Table(edge_rows, colWidths=[1.1 * cm, 3.1 * cm, 3.1 * cm, 2.1 * cm,
                                                  2.1 * cm, 2.7 * cm, 2.8 * cm])
    evidence_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
    ]))
    story.append(evidence_table)
    story.append(Spacer(1, 0.5 * cm))

    snapshot_hash = _snapshot_hash(case)
    story.append(Paragraph("Chain-of-custody", styles["Heading2"]))
    story.append(Paragraph(
        f"SHA-256 of this case's evidentiary data at export time: <font face='Courier'>{snapshot_hash}</font>. "
        "Recomputing this hash from the exported case data at any later point confirms the evidence "
        "trail has not been altered since this report was generated.",
        styles["Normal"],
    ))
    # The two integrity mechanisms cover different things and are stated
    # separately: the snapshot hash certifies the evidence in this document,
    # the audit chain certifies the sequence of actions that produced it.
    if audit:
        story.append(Spacer(1, 0.3 * cm))
        intact = audit.get("intact")
        head = audit.get("chain_head")
        story.append(Paragraph(
            f"Audit record: {audit.get('entry_count', 0)} action(s) recorded for this case, "
            f"hash-chained so that altering, reordering or deleting any entry is detectable. "
            f"Status at export: <b>{'verified intact' if intact else 'DOES NOT VERIFY'}</b>."
            + (f" Chain head: <font face='Courier'>{head}</font>." if head else "")
            + (f" {audit.get('reason')}" if not intact and audit.get("reason") else ""),
            styles["Normal"],
        ))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "This prototype traces publicly available on-chain data and flags addresses against a "
        "hand-curated seed label set, whose basis for each attribution is stated above. "
        "Exchange identification reflects on-chain deposit-address attribution only, not KYC "
        "identity - establishing who holds the account requires a legal request to the named "
        "exchange. Attribution should be confirmed with that exchange before it is relied on.",
        styles["Italic"],
    ))

    doc.build(story)
    return buffer.getvalue()
