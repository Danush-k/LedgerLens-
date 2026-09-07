"""Recovery for traces whose worker died.

Celery acknowledges a task on receipt, so a worker killed mid-trace leaves
the case row claiming to be tracing with nothing left to update it. The
interface then spins forever on work that stopped. These tests pin the one
distinction that matters: a stalled trace must be reaped, a slow one must
be left alone.
"""
from datetime import datetime, timedelta, timezone

from app.models.orm import Case
from app.worker.reaper import STALL_MINUTES, reap_stale_traces


def _case(db, status="tracing", minutes_ago=60, progress_minutes_ago=None, **kw):
    now = datetime.now(timezone.utc)
    case = Case(
        reported_address="bc1qstalled", chain="bitcoin", status=status,
        hop_progress=kw.pop("hop_progress", 2), hop_limit=5,
        created_at=now - timedelta(minutes=minutes_ago),
        last_progress_at=(now - timedelta(minutes=progress_minutes_ago))
                          if progress_minutes_ago is not None else None,
        **kw,
    )
    db.add(case)
    db.commit()
    return case


def test_a_silent_trace_is_reaped(db_session):
    case = _case(db_session, minutes_ago=60, progress_minutes_ago=45)

    assert reap_stale_traces(db_session) == 1
    db_session.refresh(case)
    assert case.status == "failed"


def test_a_trace_still_reporting_is_left_alone(db_session):
    """The whole point is to catch a dead worker, not to impose a deadline
    on a slow one. A trace killed while still working is the same failure
    in the other direction."""
    case = _case(db_session, minutes_ago=60, progress_minutes_ago=1)

    assert reap_stale_traces(db_session) == 0
    db_session.refresh(case)
    assert case.status == "tracing"


def test_a_recent_trace_is_left_alone(db_session):
    case = _case(db_session, minutes_ago=2, progress_minutes_ago=2)

    assert reap_stale_traces(db_session) == 0
    db_session.refresh(case)
    assert case.status == "tracing"


def test_a_task_that_died_before_reporting_is_still_reaped(db_session):
    """No heartbeat at all - the task was picked up and killed before its
    first hop. created_at is the fallback."""
    case = _case(db_session, minutes_ago=60, progress_minutes_ago=None,
                 hop_progress=0)

    assert reap_stale_traces(db_session) == 1
    db_session.refresh(case)
    assert case.status == "failed"


def test_a_queued_case_nothing_ever_collected_is_reaped(db_session):
    case = _case(db_session, status="queued", minutes_ago=60)

    assert reap_stale_traces(db_session) == 1
    db_session.refresh(case)
    assert case.status == "failed"


def test_finished_cases_are_never_touched(db_session):
    done = _case(db_session, status="complete", minutes_ago=600)
    failed = _case(db_session, status="failed", minutes_ago=600)

    assert reap_stale_traces(db_session) == 0
    db_session.refresh(done)
    db_session.refresh(failed)
    assert done.status == "complete"
    assert failed.status == "failed"


def test_the_error_says_the_worker_stopped_not_that_the_wallet_was_empty(db_session):
    """The distinction this codebase defends everywhere: 'we could not look'
    is not 'we looked and found nothing'. A reaped trace supports no
    conclusion about the address."""
    case = _case(db_session, minutes_ago=60, progress_minutes_ago=45)
    reap_stale_traces(db_session)
    db_session.refresh(case)

    assert "worker handling it stopped" in case.error
    assert "No conclusion should be drawn" in case.error
    assert "resubmit" in case.error.lower()


def test_the_error_records_where_it_stopped(db_session):
    case = _case(db_session, minutes_ago=60, progress_minutes_ago=45, hop_progress=3)
    reap_stale_traces(db_session)
    db_session.refresh(case)

    assert "hop 3 of 5" in case.error


def test_the_spinner_message_is_cleared(db_session):
    """A reaped case must stop advertising the hop it was on, or the UI
    keeps showing progress for a trace that is over."""
    case = _case(db_session, minutes_ago=60, progress_minutes_ago=45,
                 status_message="Reading hop 3 of 5 - 8 wallets to check")
    reap_stale_traces(db_session)
    db_session.refresh(case)

    assert case.status_message is None
    assert case.completed_at is not None


def test_reaping_is_idempotent(db_session):
    _case(db_session, minutes_ago=60, progress_minutes_ago=45)

    assert reap_stale_traces(db_session) == 1
    assert reap_stale_traces(db_session) == 0


def test_the_stall_window_is_generous_enough_for_a_throttled_hop(db_session):
    """A single hop against a rate-limited public explorer can take minutes.
    Too tight a window kills healthy traces."""
    assert STALL_MINUTES >= 10
