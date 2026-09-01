from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.neo4j_client import shortest_path_to_exchange
from app.db.postgres import get_db
from app.models.orm import Case, TracedAddress
from app.models.schemas import CaseOut, CaseSummary
from app.reports.legal_notice import build_legal_notice
from app.reports.pdf import _snapshot_hash, build_case_report

router = APIRouter(prefix="/cases", tags=["cases"])


class HashVerifyRequest(BaseModel):
    hash: str
    case_id: str | None = None


@router.get("", response_model=list[CaseSummary])
def list_cases(
    db: Session = Depends(get_db),
    chain: str | None = Query(None),
    status: str | None = Query(None),
    min_risk: float | None = Query(None, ge=0, le=100),
    search: str | None = Query(None, description="Substring match on the reported address"),
):
    query = db.query(Case)
    if chain:
        query = query.filter(Case.chain == chain)
    if status:
        query = query.filter(Case.status == status)
    if min_risk is not None:
        query = query.filter(Case.risk_score >= min_risk)
    if search:
        query = query.filter(Case.reported_address.ilike(f"%{search.lower()}%"))
    return query.order_by(Case.created_at.desc()).limit(200).all()


@router.post("/verify-hash")
def verify_case_hash(request: HashVerifyRequest, db: Session = Depends(get_db)):
    """Verifies whether a provided SHA-256 hash corresponds to an authentic,
    unaltered case snapshot in the database (Chain-of-Custody verification)."""
    target_hash = request.hash.strip().lower()

    if request.case_id:
        case = db.get(Case, request.case_id)
        if not case:
            raise HTTPException(404, "Case ID not found in database")
        computed = _snapshot_hash(case).lower()
        is_valid = (computed == target_hash)
        return {
            "verified": is_valid,
            "case_id": case.id,
            "reported_address": case.reported_address,
            "chain": case.chain,
            "risk_score": case.risk_score,
            "created_at": case.created_at,
            "computed_hash": computed,
            "submitted_hash": target_hash,
            "status": "AUTHENTIC_RECORD" if is_valid else "HASH_MISMATCH_POTENTIAL_TAMPERING",
        }

    # Search all completed cases if no case_id specified
    completed_cases = db.query(Case).filter(Case.status == "complete").all()
    for case in completed_cases:
        computed = _snapshot_hash(case).lower()
        if computed == target_hash:
            return {
                "verified": True,
                "case_id": case.id,
                "reported_address": case.reported_address,
                "chain": case.chain,
                "risk_score": case.risk_score,
                "created_at": case.created_at,
                "computed_hash": computed,
                "submitted_hash": target_hash,
                "status": "AUTHENTIC_RECORD",
            }

    return {
        "verified": False,
        "submitted_hash": target_hash,
        "status": "UNRECOGNIZED_HASH",
        "message": "No matching case snapshot found with this SHA-256 checksum.",
    }


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    return case


@router.get("/{case_id}/related", response_model=list[CaseSummary])
def get_related_cases(case_id: str, db: Session = Depends(get_db)):
    """Other cases that reported the *same* wallet - the 'has this exact
    address been reported before' signal, surfaced as actual linked cases
    rather than just a risk-score flag."""
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Case not found")

    related_ids = (
        db.query(TracedAddress.case_id)
        .filter(TracedAddress.chain == case.chain,
                TracedAddress.address == case.reported_address,
                TracedAddress.case_id != case_id)
        .distinct()
        .all()
    )
    ids = [row[0] for row in related_ids]
    if not ids:
        return []
    return (
        db.query(Case)
        .filter(Case.id.in_(ids))
        .order_by(Case.created_at.desc())
        .all()
    )


@router.get("/{case_id}/shortest-path")
def get_shortest_path(case_id: str, db: Session = Depends(get_db)):
    """Live Neo4j Cypher query - demonstrates the graph DB, independent of
    the cached result already stored on the case row."""
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    path = shortest_path_to_exchange(case_id, case.chain, case.reported_address)
    return {"path": path}


@router.get("/{case_id}/legal-notice")
def get_legal_notice(
    case_id: str,
    officer_name: str = Query("Investigating Officer", description="Name of Investigating Officer"),
    officer_designation: str = Query("Inspector of Police", description="Officer Rank / Designation"),
    police_station: str = Query("Cyber Crime Police Station", description="Police Station / Unit"),
    fir_number: str | None = Query(None, description="FIR / Crime Ref Number"),
    fir_date: str | None = Query(None, description="Date of FIR / Complaint"),
    victim_name: str | None = Query(None, description="Victim / Complainant Name"),
    act_section: str = Query("bnss_94", description="bnss_94 or crpc_91"),
    db: Session = Depends(get_db),
):
    """Generates an official Section 91 CrPC / Section 94 BNSS Legal Preservation
    Notice PDF addressed to the nearest identified VASP's Law Enforcement Desk."""
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    if case.status != "complete":
        raise HTTPException(409, "Case has not finished tracing yet")

    pdf_bytes = build_legal_notice(
        case=case,
        officer_name=officer_name,
        officer_designation=officer_designation,
        police_station=police_station,
        fir_number=fir_number,
        fir_date=fir_date,
        victim_name=victim_name,
        act_section=act_section,
    )
    filename = f"legal-notice-case-{case_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{case_id}/report")
def get_case_report(case_id: str, db: Session = Depends(get_db)):
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    if case.status != "complete":
        raise HTTPException(409, "Case has not finished tracing yet")
    pdf_bytes = build_case_report(case)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="case-{case_id}.pdf"'},
    )


from pydantic import BaseModel
from app.reports.evidence_package import generate_evidence_zip
from app.tracer.aggregation import aggregate_case_graphs
from app.tracer.bridge_detector import detect_cross_chain_swaps


class AggregateGraphRequest(BaseModel):
    case_ids: list[str]


@router.post("/cases/aggregate-graph")
def post_aggregate_graph(request: AggregateGraphRequest, db: Session = Depends(get_db)):
    """Merges multiple case graphs into a single multi-target aggregated visualization."""
    if not request.case_ids:
        raise HTTPException(400, "Must provide at least one case ID")
    return aggregate_case_graphs(request.case_ids, db)


@router.get("/{case_id}/swaps")
def get_case_swaps(case_id: str, db: Session = Depends(get_db)):
    """Detects cross-chain bridge and DEX swap interactions within a case graph."""
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    edges = (case.graph or {}).get("edges", [])
    swaps = detect_cross_chain_swaps(case.chain, edges)
    return {"case_id": case_id, "swaps_count": len(swaps), "swaps": swaps}


@router.get("/{case_id}/evidence-package")
def get_evidence_package(
    case_id: str,
    officer_name: str = Query("Investigating Officer"),
    officer_designation: str = Query("Inspector of Police"),
    police_station: str = Query("Cyber Crime Police Station"),
    fir_number: str | None = Query(None),
    fir_date: str | None = Query(None),
    act_section: str = Query("bnss_94"),
    db: Session = Depends(get_db),
):
    """Generates a complete tamper-evident Evidence ZIP Package containing:
    1. Statutory Sec 91/94 Legal Notice PDF
    2. Cryptographic SHA-256 JSON Manifest
    3. Forensic Summary Dossier Text File
    """
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    if case.status != "complete":
        raise HTTPException(409, "Case tracing is not complete yet")

    zip_bytes = generate_evidence_zip(
        case=case,
        officer_name=officer_name,
        officer_designation=officer_designation,
        police_station=police_station,
        fir_number=fir_number,
        fir_date=fir_date,
        act_section=act_section,
    )
    filename = f"evidence-package-{case_id[:8]}.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

