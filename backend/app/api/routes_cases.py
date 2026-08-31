from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.neo4j_client import shortest_path_to_exchange
from app.db.postgres import get_db
from app.models.orm import Case, TracedAddress
from app.models.schemas import CaseOut, CaseSummary
from app.reports.pdf import build_case_report

router = APIRouter(prefix="/cases", tags=["cases"])


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


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    return case


@router.get("/{case_id}/related", response_model=list[CaseSummary])
def get_related_cases(case_id: str, db: Session = Depends(get_db)):
    """Other cases that reported the *same* wallet - the "has this exact
    address been reported before" signal, surfaced as actual linked cases
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
