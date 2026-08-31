from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.postgres import get_db
from app.integrations.mock_lea import receive_ncrp_intake
from app.models.orm import AuditEvent, Case
from app.models.schemas import TraceAccepted
from app.worker.tasks import trace_wallet_task

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.post("/ncrp/intake", response_model=TraceAccepted, status_code=202)
def ncrp_intake(payload: dict, db: Session = Depends(get_db)):
    """Stand-in for a real NCRP push. Shaped like what NCRP would plausibly
    send; normalises it and runs it through the same pipeline as a manual
    dashboard submission. SIMULATED - not a live NCRP connection."""
    normalised = receive_ncrp_intake(payload)
    case = Case(
        reported_address=normalised["address"].lower(),
        chain=normalised["chain"],
        complaint_ref=normalised.get("complaint_ref"),
        status="queued",
        hop_limit=get_settings().hop_limit,
    )
    db.add(case)
    db.flush()
    db.add(AuditEvent(case_id=case.id, event="ncrp_intake_received",
                       detail="[SIMULATED] Received via mock NCRP intake endpoint", simulated=True))
    db.commit()
    db.refresh(case)

    trace_wallet_task.delay(case.id)
    return TraceAccepted(case_id=case.id, status=case.status)


@router.get("/log/{case_id}")
def integration_log(case_id: str, db: Session = Depends(get_db)):
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.case_id == case_id)
        .order_by(AuditEvent.created_at.asc())
        .all()
    )
    return [
        {"event": e.event, "detail": e.detail, "simulated": e.simulated, "created_at": e.created_at}
        for e in events
    ]
