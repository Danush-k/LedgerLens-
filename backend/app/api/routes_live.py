"""Live case updates: a stream out, and the controls for what is watched.

The rest of the API answers "what does this case say?". These endpoints
answer "what has changed since you asked?" - a trace's progress while it
runs, and movement on its wallets after it finishes.

Delivery is Server-Sent Events rather than polling. Polling for something
that changes rarely means either a slow page or a lot of requests that
return nothing, and the choice between those is a choice about which way to
be wrong. A stream is neither: the connection stays open and the server
speaks when it has something to say.
"""
import asyncio
import json
import logging
import queue
import time

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import CurrentUser, get_current_user
from app.auth.security import decode_access_token
from app.config import get_settings
from app.db.postgres import SessionLocal, get_db
from app.live.monitor import iso_utc, live_monitor
from app.models.orm import Case, LiveTransfer
from app.reports.audit_chain import append_audit_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/live", tags=["live"])

# How often the stream re-reads the case row for progress. This covers the
# fields a running trace writes from a worker thread, which never pass
# through the monitor's event queue.
STATUS_POLL_SECONDS = 2.0
# Proxies and load balancers close a connection that has said nothing for a
# while. A comment line keeps it open without being an event.
KEEPALIVE_SECONDS = 15.0
# How long the loop naps between passes. Sets the worst-case delay between
# a detection and the browser seeing it; small enough to read as instant.
IDLE_SLEEP_SECONDS = 0.4


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _stream_user(token: str | None, authorization: str | None) -> CurrentUser:
    """Authenticate a stream, from a header or a query parameter.

    The browser's EventSource cannot set request headers, so a bearer token
    has nowhere to go but the URL. That is a real cost - URLs reach access
    logs and proxy logs in a way headers do not - and it is accepted here
    only because the alternative is worse: hand-rolling the stream over
    fetch() means reimplementing reconnection and backoff, which is exactly
    the part of EventSource worth keeping. The header path is preferred
    whenever a caller can use it.
    """
    unauthorized = HTTPException(status_code=401, detail="Not authenticated",
                                  headers={"WWW-Authenticate": "Bearer"})
    raw = token
    if not raw and authorization and authorization.lower().startswith("bearer "):
        raw = authorization[7:]
    if not raw:
        raise unauthorized
    try:
        payload = decode_access_token(raw)
    except jwt.PyJWTError:
        raise unauthorized
    username, role = payload.get("sub"), payload.get("role")
    if not username or not role:
        raise unauthorized
    return CurrentUser(username=username, role=role)


def _status_snapshot(case_id: str) -> dict | None:
    """The small, frequently-changing part of a case.

    Deliberately excludes the graph. A trace's progress changes every few
    seconds and the graph can run to hundreds of kilobytes; sending the
    whole case each time would make an update cost more than the page load
    did. When the graph does change, the stream says so and the client
    fetches it once.
    """
    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        if case is None:
            return None
        return {
            "case_id": case.id,
            "status": case.status,
            "hop_progress": case.hop_progress,
            "hop_limit": case.hop_limit,
            "status_message": case.status_message,
            "last_progress_at": iso_utc(case.last_progress_at),
            "risk_score": case.risk_score,
            "live_watch": bool(case.live_watch),
            "live_event_count": case.live_event_count or 0,
            "live_checked_at": iso_utc(case.live_checked_at),
            "live_last_event_at": iso_utc(case.live_last_event_at),
        }
    finally:
        db.close()


async def _event_stream(request: Request, case_id: str):
    channel = live_monitor.subscribe(case_id)
    settings = get_settings()
    try:
        snapshot = await run_in_threadpool(_status_snapshot, case_id)
        yield _sse("hello", {
            "case_id": case_id,
            "watching": settings.live_monitor_enabled,
            "poll_seconds": settings.live_poll_seconds,
            "watch_addresses": settings.live_watch_addresses,
            "status": snapshot,
        })

        last_snapshot = snapshot
        last_status_read = time.monotonic()
        last_write = time.monotonic()

        while True:
            if await request.is_disconnected():
                break

            wrote = False

            # Anything the monitor found goes out first - it is the reason
            # this endpoint exists.
            while True:
                try:
                    event = channel.get_nowait()
                except queue.Empty:
                    break
                yield _sse(event["type"], event["data"])
                wrote = True

            now = time.monotonic()
            if now - last_status_read >= STATUS_POLL_SECONDS:
                last_status_read = now
                live_monitor.mark_viewed(case_id)
                snapshot = await run_in_threadpool(_status_snapshot, case_id)
                if snapshot is None:
                    yield _sse("gone", {"case_id": case_id})
                    break
                if snapshot != last_snapshot:
                    yield _sse("status", snapshot)
                    wrote = True
                    # A trace that has just finished has produced a whole
                    # graph at once. Rather than push it down the stream,
                    # tell the client to fetch the case it already knows how
                    # to fetch.
                    if (last_snapshot and snapshot["status"] != last_snapshot["status"]
                            and snapshot["status"] in ("complete", "failed")):
                        yield _sse("refresh", {"reason": snapshot["status"]})
                    last_snapshot = snapshot

            if wrote:
                last_write = now
            elif now - last_write >= KEEPALIVE_SECONDS:
                yield ": keepalive\n\n"
                last_write = now

            await asyncio.sleep(IDLE_SLEEP_SECONDS)
    except asyncio.CancelledError:  # the client went away mid-write
        raise
    finally:
        live_monitor.unsubscribe(case_id, channel)


@router.get("/cases/{case_id}/stream")
async def stream_case(
    case_id: str,
    request: Request,
    token: str | None = Query(None, description="Bearer token, for EventSource clients"),
    authorization: str | None = Header(None),
):
    """Live updates for one case, as Server-Sent Events.

    Events: `hello` on connect, `status` when the trace's progress or the
    watch state changes, `refresh` when the client should re-fetch the whole
    case, `check` after each live re-read of the case's wallets, and
    `transactions` when that re-read found movement.
    """
    _stream_user(token, authorization)

    db = SessionLocal()
    try:
        if db.get(Case, case_id) is None:
            raise HTTPException(404, "Case not found")
    finally:
        db.close()

    return StreamingResponse(
        _event_stream(request, case_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # nginx buffers proxied responses by default, which holds every
            # event until the buffer fills - a live stream that arrives in
            # batches is not a live stream.
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/cases/{case_id}/status")
def live_status(case_id: str, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(get_current_user)):
    """The same snapshot the stream sends, for clients that cannot hold one open.

    Requesting it also counts as looking at the case, so a client falling
    back to polling still gets live monitoring rather than a page that has
    quietly stopped updating.
    """
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "Case not found")
    live_monitor.mark_viewed(case_id)
    settings = get_settings()
    return {
        "case_id": case.id,
        "status": case.status,
        "watching": settings.live_monitor_enabled,
        "poll_seconds": settings.live_poll_seconds,
        "viewers": live_monitor.viewer_count(case_id),
        "live_watch": bool(case.live_watch),
        "live_event_count": case.live_event_count or 0,
        "live_checked_at": iso_utc(case.live_checked_at),
        "live_last_event_at": iso_utc(case.live_last_event_at),
    }


@router.get("/cases/{case_id}/transfers")
def live_transfers(case_id: str, limit: int = Query(100, ge=1, le=500),
                    db: Session = Depends(get_db),
                    user: CurrentUser = Depends(get_current_user)):
    """Movement detected on this case since its trace completed, newest first."""
    if db.get(Case, case_id) is None:
        raise HTTPException(404, "Case not found")
    rows = (
        db.query(LiveTransfer)
        .filter(LiveTransfer.case_id == case_id)
        .order_by(LiveTransfer.detected_at.desc(), LiveTransfer.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "tx_hash": row.tx_hash,
            "chain": row.chain,
            "from_address": row.from_address,
            "to_address": row.to_address,
            "value": row.value,
            "timestamp": row.timestamp,
            "hop": row.hop,
            "to_node_type": row.to_node_type,
            "to_label_name": row.to_label_name,
            "detected_at": iso_utc(row.detected_at),
        }
        for row in rows
    ]


class WatchRequest(BaseModel):
    enabled: bool


@router.post("/cases/{case_id}/watch")
def set_watch(case_id: str, body: WatchRequest, db: Session = Depends(get_db),
               user: CurrentUser = Depends(get_current_user)):
    """Keep watching this case when nobody has it open.

    Off by default. Watching costs explorer quota whether or not anyone is
    reading the result, so leaving every case in the database permanently
    watched would spend the whole rate limit on cases nobody is working -
    and starve the one somebody is.
    """
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "Case not found")
    if case.status != "complete" and body.enabled:
        raise HTTPException(409, "The trace has not finished yet - it is already "
                                  "walking these wallets.")

    if bool(case.live_watch) != body.enabled:
        case.live_watch = body.enabled
        append_audit_event(
            db, case_id,
            "live_watch_enabled" if body.enabled else "live_watch_disabled",
            f"Background monitoring {'enabled' if body.enabled else 'disabled'} "
            f"by {user.username}.",
        )
        db.commit()
        if body.enabled:
            live_monitor.mark_viewed(case_id)  # check it now, not in a cycle's time

    return {"case_id": case_id, "live_watch": bool(case.live_watch)}
