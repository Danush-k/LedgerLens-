import csv
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.chain_clients.base import Chain, normalize_address
from app.config import get_settings
from app.db.postgres import get_db
from app.models.orm import AuditEvent, Case
from app.models.schemas import TraceAccepted, TraceRequest
from app.worker.tasks import trace_wallet_task

import threading

router = APIRouter(tags=["trace"])
MAX_BULK_ROWS = 200


def dispatch_trace_task(case_id: str) -> None:
    try:
        trace_wallet_task.delay(case_id)
    except Exception:
        threading.Thread(target=trace_wallet_task, args=(case_id,), daemon=True).start()


from pydantic import BaseModel
from app.risk.complaint_parser import parse_complaint_text


class ParseComplaintRequest(BaseModel):
    text: str


@router.post("/trace/parse-complaint")
def parse_complaint(request: ParseComplaintRequest, user: CurrentUser = Depends(get_current_user)):
    """Extract candidate wallets, chains, tx hashes, and UPI identifiers from raw complaint text."""
    return parse_complaint_text(request.text)


@router.post("/trace", response_model=TraceAccepted, status_code=202)
def submit_trace(request: TraceRequest, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(get_current_user)):
    case = Case(
        reported_address=normalize_address(request.address),
        chain=request.chain.value,
        complaint_ref=request.complaint_ref,
        narrative=request.narrative,
        status="queued",
        hop_limit=get_settings().hop_limit,
        created_by=user.username,
    )
    db.add(case)
    db.flush()
    db.add(AuditEvent(case_id=case.id, event="case_created",
                       detail=f"Submitted by {user.username} for {case.reported_address}"))
    db.commit()
    db.refresh(case)

    dispatch_trace_task(case.id)

    return TraceAccepted(case_id=case.id, status=case.status)


@router.post("/trace/bulk")
async def submit_trace_bulk(file: UploadFile, db: Session = Depends(get_db),
                             user: CurrentUser = Depends(get_current_user)):
    """CSV columns: address, chain, complaint_ref (optional), narrative (optional).
    Investigators routinely have a spreadsheet of wallets per case, not one
    address at a time - this runs every valid row through the same pipeline
    as a single manual submission."""
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    if reader.fieldnames is None or "address" not in reader.fieldnames or "chain" not in reader.fieldnames:
        raise HTTPException(400, "CSV must have at least 'address' and 'chain' columns")

    accepted: list[dict] = []
    rejected: list[dict] = []
    settings = get_settings()

    for i, row in enumerate(reader, start=2):  # row 1 is the header
        if len(accepted) + len(rejected) >= MAX_BULK_ROWS:
            rejected.append({"row": i, "reason": f"Exceeded the {MAX_BULK_ROWS}-row limit per upload"})
            break
        address = (row.get("address") or "").strip()
        chain_raw = (row.get("chain") or "").strip().lower()
        if not address:
            rejected.append({"row": i, "reason": "Missing address"})
            continue
        try:
            chain = Chain(chain_raw)
        except ValueError:
            rejected.append({"row": i, "reason": f"Unknown chain '{chain_raw}'"})
            continue

        case = Case(
            reported_address=normalize_address(address),
            chain=chain.value,
            complaint_ref=(row.get("complaint_ref") or "").strip() or None,
            narrative=(row.get("narrative") or "").strip() or None,
            status="queued",
            hop_limit=settings.hop_limit,
            created_by=user.username,
        )
        db.add(case)
        db.flush()
        db.add(AuditEvent(case_id=case.id, event="case_created",
                           detail=f"Submitted via bulk upload (row {i}) by {user.username}"))
        accepted.append({"row": i, "case_id": case.id, "address": address})

    db.commit()
    for entry in accepted:
        dispatch_trace_task(entry["case_id"])

    return {"accepted": accepted, "rejected": rejected}
