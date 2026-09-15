"""Recovery for traces whose worker died.

Celery acknowledges a task when it is received, not when it finishes. If the
worker process is killed mid-trace - an OOM kill, a pool recycle, a laptop
closing - the task is never requeued and the case row is left claiming to be
tracing. Nothing will ever update it again, so the interface spins forever
on work that stopped.

A stalled trace is not a slow one, and the difference is visible in the
heartbeat: a running trace writes progress at every hop. A case that has not
written one for longer than any single hop could plausibly take is not
running any more, and saying so is more honest than an indefinite spinner.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.orm import Case
from app.reports.audit_chain import append_audit_event

logger = logging.getLogger(__name__)

# Generous: a single hop against a throttled public explorer can legitimately
# take minutes. This is set to catch a dead worker, not to impose a deadline
# on a slow one - a trace killed while it was still working would be the
# same failure in the other direction.
STALL_MINUTES = 15


def reap_stale_traces(db: Session, stall_minutes: int = STALL_MINUTES) -> int:
    """Mark traces whose worker stopped reporting as failed.

    Returns how many were reaped. The case is marked failed rather than
    requeued: re-running automatically could duplicate a partially written
    graph, and an investigator deciding to retry is a smaller cost than a
    silently doubled trace.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=stall_minutes)
    stale = (
        db.query(Case)
        .filter(Case.status.in_(("tracing", "queued")))
        .filter(Case.created_at < cutoff)
        .all()
    )

    reaped = 0
    for case in stale:
        # The heartbeat wins where it exists; created_at is the fallback for
        # rows written before heartbeats, and for a task that died before it
        # ever reported a hop.
        last_seen = case.last_progress_at or case.created_at
        if last_seen and last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        if last_seen and last_seen >= cutoff:
            continue  # still reporting, just slow

        case.status = "failed"
        case.status_message = None
        case.error = (
            f"The trace stopped without completing. It last reported progress at "
            f"hop {case.hop_progress} of {case.hop_limit}, then went silent for "
            f"more than {stall_minutes} minutes, which means the worker handling "
            f"it stopped rather than that the wallet had nothing to show. No "
            f"conclusion should be drawn about this address - resubmit it to try "
            f"again."
        )
        case.completed_at = datetime.now(timezone.utc)
        try:
            append_audit_event(db, case.id, "trace_failed", case.error)
        except Exception:  # noqa: BLE001 - the recovery must not depend on the log
            logger.warning(f"Could not append audit event while reaping {case.id}")
        reaped += 1

    if reaped:
        db.commit()
        logger.info(f"Reaped {reaped} stalled trace(s)")
    return reaped
