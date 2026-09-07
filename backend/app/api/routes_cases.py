from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.neo4j_client import shortest_path_to_exchange
from app.db.postgres import get_db
from app.models.orm import AuditEvent, Case, TracedAddress
from app.models.schemas import CaseOut, CaseSummary
from app.reports.audit_chain import verify_audit_chain
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
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    response: Response = None,  # type: ignore[assignment]
):
    """List cases, newest first.

    Paginated rather than capped. The previous hard limit of 200 silently
    dropped everything beyond it, so a deployment past 200 cases would show
    an incomplete list with no indication that it was incomplete - the worst
    kind of wrong, because it looks right.
    """
    query = db.query(Case)
    if chain:
        query = query.filter(Case.chain == chain)
    if status:
        query = query.filter(Case.status == status)
    if min_risk is not None:
        query = query.filter(Case.risk_score >= min_risk)
    if search:
        query = query.filter(Case.reported_address.ilike(f"%{search.lower()}%"))

    # The total goes in a header so the client can say "50 of 312" instead of
    # leaving the reader to guess whether the list ended or was truncated.
    total = query.count()
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
        response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"

    return (
        query.order_by(Case.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


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


class CaseLink(BaseModel):
    """One other case this one is connected to, and the wallet that connects them."""

    case_id: str
    complaint_ref: str | None
    reported_address: str
    risk_score: float | None
    status: str
    created_at: datetime
    # "same_wallet" - the identical address was reported again, the strongest
    # link available. "shared_wallet" - the two traces pass through a wallet
    # in common, which is corroboration from a separate victim but not proof
    # the same person controls both.
    relationship: str
    shared_addresses: list[str]


@router.get("/{case_id}/links", response_model=list[CaseLink])
def get_case_links(case_id: str, db: Session = Depends(get_db)):
    """Every other case connected to this one, and the wallet doing the connecting.

    The two link types were previously answered in different places - repeat
    reports by /related, shared downstream wallets buried inside a finding's
    evidence - and neither named which wallet created the link. That naming
    is the part an investigator can act on: "9 wallets across 5 cases" is a
    statistic, while "this wallet also appears in case X" is a lead they can
    open. Both are returned here, strongest first.
    """
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Case not found")

    links: dict[str, dict] = {}

    # 1. The same wallet reported again - the strongest link there is.
    same_wallet_ids = [
        row[0] for row in
        db.query(TracedAddress.case_id)
        .filter(TracedAddress.chain == case.chain,
                TracedAddress.address == case.reported_address,
                TracedAddress.case_id != case_id)
        .distinct().all()
    ]
    for other_id in same_wallet_ids:
        links[other_id] = {"relationship": "same_wallet",
                            "shared_addresses": [case.reported_address]}

    # 2. Traces meeting at a wallet neither case reported. Read from the
    #    stored finding rather than recomputed, so the page agrees with the
    #    evidence report and the risk score, which were fixed at trace time.
    for pattern in (case.patterns or []):
        if pattern.get("pattern") != "shared_downstream":
            continue
        for link in pattern.get("links") or []:
            other_id = link.get("case_id")
            if not other_id or other_id in links:
                continue  # a same-wallet link already says something stronger
            links[other_id] = {"relationship": "shared_wallet",
                                "shared_addresses": link.get("shared_addresses", [])}

    if not links:
        return []

    others = db.query(Case).filter(Case.id.in_(list(links))).all()
    result = [
        CaseLink(
            case_id=other.id,
            complaint_ref=other.complaint_ref,
            reported_address=other.reported_address,
            risk_score=other.risk_score,
            status=other.status,
            created_at=other.created_at,
            relationship=links[other.id]["relationship"],
            shared_addresses=links[other.id]["shared_addresses"],
        )
        for other in others
    ]
    # Repeat reports first, then by how many wallets are shared, then risk.
    result.sort(key=lambda l: (l.relationship != "same_wallet",
                                -len(l.shared_addresses),
                                -(l.risk_score or 0)))

    # One complaint, one row. The same wallet traced repeatedly - a deeper
    # hop limit, an investigator re-checking their work - produces a case
    # row each time, and listing them all would present one complaint as a
    # wall of corroboration. Cases are distinct when they carry different
    # references or were filed by different people; otherwise the highest
    # scoring is kept, since the sort above already put it first.
    seen: set[tuple] = set()
    deduplicated = []
    for link in result:
        other = next(o for o in others if o.id == link.case_id)
        identity = (link.relationship, other.complaint_ref or "", other.created_by or "")
        if identity in seen:
            continue
        seen.add(identity)
        deduplicated.append(link)
    return deduplicated


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
    # The report carries the audit verification alongside its own snapshot
    # hash, so a reader gets the evidence and the record of how it was
    # produced in one document.
    pdf_bytes = build_case_report(case, audit=verify_audit_chain(db, case_id).as_dict())
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="case-{case_id}.pdf"'},
    )


@router.get("/{case_id}/audit")
def get_audit_chain(case_id: str, db: Session = Depends(get_db)):
    """This case's audit log together with a verification of its integrity.

    The entries alone say what happened; the verification says whether the
    record can be trusted to still be what was written. Both are returned
    together so a reader never sees the history without its provenance.
    """
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Case not found")

    verification = verify_audit_chain(db, case_id)
    entries = (
        db.query(AuditEvent)
        .filter(AuditEvent.case_id == case_id)
        .order_by(AuditEvent.sequence.asc())
        .all()
    )
    return {
        "verification": verification.as_dict(),
        "entries": [
            {
                "sequence": e.sequence,
                "event": e.event,
                "detail": e.detail,
                "simulated": e.simulated,
                "created_at": e.created_at,
                "entry_hash": e.entry_hash,
                "prev_hash": e.prev_hash,
            }
            for e in entries
        ],
    }
