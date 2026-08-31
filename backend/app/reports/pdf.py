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
    """SHA-256 of the case's evidentiary data - lets anyone later verify
    this report wasn't altered after generation (chain-of-custody support)."""
    snapshot = {
        "case_id": case.id,
        "reported_address": case.reported_address,
        "chain": case.chain,
        "graph": case.graph,
        "risk_score": case.risk_score,
        "nearest_exchange": case.nearest_exchange,
    }
    payload = json.dumps(snapshot, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_case_report(case: Case) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Crypto Fraud Attribution — Investigation Report", styles["Title"]))
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

    story.append(Paragraph("Evidence trail (transaction hops)", styles["Heading2"]))
    graph = case.graph or {"nodes": [], "edges": []}
    edge_rows = [["Hop", "From", "To", "Amount", "Tx hash", "Timestamp"]]
    address_by_id = {n["id"]: n["address"] for n in graph.get("nodes", [])}
    for edge in sorted(graph.get("edges", []), key=lambda e: e["hop"]):
        ts = datetime.fromtimestamp(edge["timestamp"], tz=timezone.utc).isoformat() if edge["timestamp"] else "—"
        edge_rows.append([
            str(edge["hop"]),
            address_by_id.get(edge["source"], edge["source"])[:16] + "…",
            address_by_id.get(edge["target"], edge["target"])[:16] + "…",
            f"{edge['value']:.6f}",
            edge["tx_hash"][:16] + "…",
            ts,
        ])
    evidence_table = Table(edge_rows, colWidths=[1.2 * cm, 3.5 * cm, 3.5 * cm, 2.3 * cm, 3 * cm, 3.5 * cm])
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
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "This prototype traces publicly available on-chain data and flags addresses against a "
        "hand-curated seed label set. Exchange identification reflects on-chain deposit-address "
        "attribution only, not KYC identity - unmasking the account holder requires a legal "
        "request to the named exchange.",
        styles["Italic"],
    ))

    doc.build(story)
    return buffer.getvalue()
