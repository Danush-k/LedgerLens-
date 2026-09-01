import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from app.models.orm import Case
from app.reports.legal_notice import build_legal_notice


def generate_evidence_zip(
    case: Case,
    officer_name: str = "Investigating Officer",
    officer_designation: str = "Inspector of Police",
    police_station: str = "Cyber Crime Police Station",
    fir_number: str | None = None,
    fir_date: str | None = None,
    act_section: str = "bnss_94",
) -> bytes:
    """Generates a 1-click court-ready evidence package (.ZIP archive) containing:
    1. Statutory Sec 91 CrPC / Sec 94 BNSS Legal Freeze Directive PDF
    2. SHA-256 Cryptographic Evidence Manifest JSON
    3. Forensic Metadata Summary text file
    """
    zip_buffer = io.BytesIO()

    # 1. Generate Statutory Legal Notice PDF
    pdf_bytes = build_legal_notice(
        case=case,
        officer_name=officer_name,
        officer_designation=officer_designation,
        police_station=police_station,
        fir_number=fir_number,
        fir_date=fir_date,
        act_section=act_section,
    )
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()

    # 2. Build Cryptographic Evidence Manifest JSON
    manifest_data = {
        "case_id": case.id,
        "reported_address": case.reported_address,
        "chain": case.chain,
        "complaint_ref": case.complaint_ref or fir_number,
        "risk_score": case.risk_score,
        "nearest_exchange": case.nearest_exchange,
        "flags": case.flags,
        "graph_nodes_count": len(case.graph.get("nodes", [])) if case.graph else 0,
        "graph_edges_count": len(case.graph.get("edges", [])) if case.graph else 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "officer": {
            "name": officer_name,
            "designation": officer_designation,
            "police_station": police_station,
            "act_section": "Section 94 BNSS (2023)" if act_section == "bnss_94" else "Section 91 Cr.P.C (1973)",
        },
        "pdf_notice_sha256": pdf_hash,
    }
    manifest_bytes = json.dumps(manifest_data, indent=2).encode("utf-8")
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()

    # 3. Build Summary Text Dossier
    summary_text = f"""================================================================================
LEDGERLENS CYBERCRIME FORENSIC EVIDENCE DOSSIER
================================================================================
Case ID: {case.id}
Reported Suspect Wallet: {case.reported_address}
Chain: {case.chain.upper()}
Complaint / FIR Reference: {case.complaint_ref or fir_number or 'N/A'}
Risk Score: {case.risk_score if case.risk_score is not None else 'N/A'} / 100
Fraud Typology: {case.fraud_typology or 'Unclassified'}

TARGET EXCHANGE / VASP ATTRIBUTION:
Name: {case.nearest_exchange.get('name') if case.nearest_exchange else 'No exchange identified within hop limit'}
Deposit Address: {case.nearest_exchange.get('address') if case.nearest_exchange else 'N/A'}
Hop Distance: {case.nearest_exchange.get('hops') if case.nearest_exchange else 'N/A'} hops away

RECOMMENDED LAW ENFORCEMENT ACTION:
{case.recommended_action or 'N/A'}

DETECTED FORENSIC FLAGS:
{', '.join(case.flags) if case.flags else 'None'}

CHAIN OF CUSTODY & INTEGRITY HASHES:
Notice PDF SHA-256: {pdf_hash}
Manifest JSON SHA-256: {manifest_hash}

Issued By: {officer_name} ({officer_designation}), {police_station}
Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
================================================================================
"""
    summary_bytes = summary_text.encode("utf-8")

    # Pack into ZIP Archive
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"Legal_Notice_{case.id[:8]}.pdf", pdf_bytes)
        zf.writestr(f"Evidence_Manifest_{case.id[:8]}.json", manifest_bytes)
        zf.writestr(f"Case_Summary_{case.id[:8]}.txt", summary_bytes)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()
