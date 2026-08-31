from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.neo4j_client import shortest_path_to_exchange
from app.db.postgres import get_db
from app.models.orm import Case
from app.models.schemas import CaseOut, CaseSummary
from app.reports.pdf import build_case_report

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=list[CaseSummary])
def list_cases(db: Session = Depends(get_db)):
    cases = db.query(Case).order_by(Case.created_at.desc()).limit(100).all()
    return cases


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    return case


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
