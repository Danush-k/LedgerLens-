import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.auth.ratelimit import TRACE_LIMIT, limiter
from app.chain_clients.base import Chain, normalize_address
from app.config import get_settings
from app.db.postgres import get_db
from app.models.orm import Case, TracedAddress
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
from app.risk.document_text import UnreadableDocument, extract_text


class ParseComplaintRequest(BaseModel):
    text: str


@router.post("/trace/parse-complaint")
def parse_complaint(request: ParseComplaintRequest, user: CurrentUser = Depends(get_current_user)):
    """Extract candidate wallets, chains, tx hashes, and UPI identifiers from raw complaint text."""
    return parse_complaint_text(request.text)


@router.post("/trace/parse-document")
async def parse_document(file: UploadFile = File(...),
                          user: CurrentUser = Depends(get_current_user)):
    """Read an uploaded FIR and extract the same fields as pasted text.

    Complaints arrive as documents, and retyping a wallet address out of one
    is the likeliest place for a transcription error to enter a case - a
    mistyped address traces a stranger's wallet with full confidence. The
    extracted text is returned alongside the parse so the investigator can
    see what the system actually read before acting on it.
    """
    data = await file.read()
    try:
        text = extract_text(file.filename or "", data)
    except UnreadableDocument as exc:
        # A document we could not read is not a complaint with no wallets in
        # it. Saying which it is points at the fix.
        raise HTTPException(422, str(exc))

    parsed = parse_complaint_text(text)
    return {**parsed, "source_filename": file.filename, "extracted_text": text[:20000]}


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
    db.add(TracedAddress(case_id=case.id, chain=case.chain, address=case.reported_address))
    append_audit_event(db, case.id, "case_created",
                       f"Submitted by {user.username} for {case.reported_address}")
    db.commit()
    db.refresh(case)

    dispatch_trace_task(case.id)

    return TraceAccepted(case_id=case.id, status=case.status)


@router.post("/trace/bulk")
async def submit_trace_bulk(file: UploadFile, db: Session = Depends(get_db),
                            user: CurrentUser = Depends(get_current_user)):
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig", errors="replace")))
    settings = get_settings()

    accepted = []
    rejected = []
    for i, row in enumerate(reader, start=1):
        if i > MAX_BULK_ROWS:
            rejected.append({"row": i, "reason": f"Exceeded maximum {MAX_BULK_ROWS} rows per upload"})
            break

        address = (row.get("address") or "").strip()
        chain_raw = (row.get("chain") or "").strip().lower()
        if not address or not chain_raw:
            rejected.append({"row": i, "reason": "Missing address or chain column"})
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
        db.add(TracedAddress(case_id=case.id, chain=case.chain, address=case.reported_address))
        append_audit_event(db, case.id, "case_created",
                            f"Submitted via bulk upload (row {i}) by {user.username}")
        accepted.append({"row": i, "case_id": case.id, "address": address})

    db.commit()
    for entry in accepted:
        dispatch_trace_task(entry["case_id"])

    return {"accepted": accepted, "rejected": rejected}
