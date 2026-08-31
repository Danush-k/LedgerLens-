from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.postgres import get_db
from app.models.orm import AuditEvent, Case
from app.models.schemas import TraceAccepted, TraceRequest
from app.worker.tasks import trace_wallet_task

router = APIRouter(tags=["trace"])


@router.post("/trace", response_model=TraceAccepted, status_code=202)
def submit_trace(request: TraceRequest, db: Session = Depends(get_db)):
    case = Case(
        reported_address=request.address.lower(),
        chain=request.chain.value,
        complaint_ref=request.complaint_ref,
        status="queued",
        hop_limit=get_settings().hop_limit,
    )
    db.add(case)
    db.flush()
    db.add(AuditEvent(case_id=case.id, event="case_created",
                       detail=f"Submitted via dashboard for {case.reported_address}"))
    db.commit()
    db.refresh(case)

    trace_wallet_task.delay(case.id)

    return TraceAccepted(case_id=case.id, status=case.status)
