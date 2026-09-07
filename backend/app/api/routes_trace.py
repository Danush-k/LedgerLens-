import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.auth.ratelimit import TRACE_LIMIT, limiter
from app.chain_clients.base import Chain, normalize_address
from app.config import get_settings
from app.db.postgres import get_db
from app.models.orm import Case
from app.reports.audit_chain import append_audit_event
from app.models.schemas import TraceAccepted, TraceRequest
from app.worker.tasks import trace_wallet_task

import threading

router = APIRouter(tags=["trace"])
MAX_BULK_ROWS = 200


def dispatch_trace_task(case_id: str) -> None:
    """Spawns execution in background without blocking the HTTP request thread.
    This guarantees that POST /trace returns 202 Accepted instantly in < 50ms."""
    threading.Thread(target=trace_wallet_task, args=(case_id,), daemon=True).start()


from pydantic import BaseModel
from app.risk.complaint_parser import parse_complaint_text


class ParseComplaintRequest(BaseModel):
    text: str


@router.post("/trace/parse-complaint")
def parse_complaint(request: ParseComplaintRequest, user: CurrentUser = Depends(get_current_user)):
    """Extract candidate wallets, chains, tx hashes, and UPI identifiers from raw complaint text."""
    return parse_complaint_text(request.text)


from app.chain_clients.base import Chain, is_valid_address, normalize_address


@router.post("/trace", response_model=TraceAccepted, status_code=202)
@limiter.limit(TRACE_LIMIT)
def submit_trace(request: Request, body: TraceRequest, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(get_current_user)):
    if not is_valid_address(body.address, body.chain):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid wallet address format for {body.chain.value.upper()}. "
                   f"EVM addresses are 42 characters starting with '0x'. "
                   f"Bitcoin addresses start with '1', '3' or 'bc1'. "
                   f"Tron addresses are 34 characters starting with 'T'."
        )

    case = Case(
        reported_address=normalize_address(body.address),
        chain=body.chain.value,
        complaint_ref=body.complaint_ref,
        narrative=body.narrative,
        status="queued",
        hop_limit=body.hop_limit or get_settings().hop_limit,
        created_by=user.username,
    )
    db.add(case)
    db.flush()
    append_audit_event(db, case.id, "case_created",
                       f"Submitted by {user.username} for {case.reported_address}")
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

        if not is_valid_address(address, chain):
            rejected.append({"row": i, "reason": f"Invalid wallet address '{address}' format for {chain.value.upper()}"})
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
        append_audit_event(db, case.id, "case_created",
                            f"Submitted via bulk upload (row {i}) by {user.username}")
        accepted.append({"row": i, "case_id": case.id, "address": address})

    db.commit()
    for entry in accepted:
        dispatch_trace_task(entry["case_id"])

    return {"accepted": accepted, "rejected": rejected}
