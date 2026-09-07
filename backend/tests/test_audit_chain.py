"""Tamper-evident audit chain.

The point of these tests is not that the chain verifies when untouched -
that is easy. It is that each specific way of altering the record is
actually caught, and that an unverifiable entry is reported as missing
provenance rather than as evidence of tampering.
"""
from datetime import datetime, timezone

from app.models.orm import AuditEvent, Case
from app.reports.audit_chain import GENESIS, append_audit_event, verify_audit_chain


def _case(db):
    case = Case(reported_address="bc1qroot", chain="bitcoin", status="queued",
                created_at=datetime.now(timezone.utc))
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def _chain_of(db, case, count=3):
    for i in range(count):
        append_audit_event(db, case.id, f"event_{i}", f"detail {i}")
    db.commit()


def test_intact_chain_verifies(db_session):
    case = _case(db_session)
    _chain_of(db_session, case, 4)

    result = verify_audit_chain(db_session, case.id)

    assert result.intact is True
    assert result.entry_count == 4
    assert result.chain_head is not None
    assert result.first_broken_sequence is None


def test_first_entry_links_to_genesis(db_session):
    case = _case(db_session)
    append_audit_event(db_session, case.id, "case_created", "first")
    db_session.commit()

    entry = db_session.query(AuditEvent).one()
    assert entry.sequence == 0
    assert entry.prev_hash == GENESIS


def test_each_entry_links_to_the_one_before(db_session):
    case = _case(db_session)
    _chain_of(db_session, case, 3)

    entries = db_session.query(AuditEvent).order_by(AuditEvent.sequence).all()
    for previous, current in zip(entries, entries[1:]):
        assert current.prev_hash == previous.entry_hash


def test_editing_an_entry_is_detected(db_session):
    """The core claim. Rewriting history must not go unnoticed."""
    case = _case(db_session)
    _chain_of(db_session, case, 4)

    tampered = db_session.query(AuditEvent).filter(AuditEvent.sequence == 1).one()
    tampered.detail = "a detail nobody actually recorded"
    db_session.commit()

    result = verify_audit_chain(db_session, case.id)

    assert result.intact is False
    assert result.first_broken_sequence == 1
    assert "contents were altered" in result.reason


def test_deleting_an_entry_is_detected(db_session):
    case = _case(db_session)
    _chain_of(db_session, case, 4)

    db_session.delete(db_session.query(AuditEvent).filter(AuditEvent.sequence == 2).one())
    db_session.commit()

    result = verify_audit_chain(db_session, case.id)

    assert result.intact is False
    assert "deleted or reordered" in result.reason


def test_forging_an_entry_hash_still_breaks_the_link(db_session):
    """Recomputing one entry's own hash is not enough - the next entry
    still points at the old value, so the break simply moves."""
    from app.reports.audit_chain import compute_entry_hash

    case = _case(db_session)
    _chain_of(db_session, case, 4)

    forged = db_session.query(AuditEvent).filter(AuditEvent.sequence == 1).one()
    forged.detail = "rewritten"
    forged.entry_hash = compute_entry_hash(
        forged.sequence, forged.case_id, forged.event, forged.detail,
        forged.created_at, forged.simulated, forged.prev_hash,
    )
    db_session.commit()

    result = verify_audit_chain(db_session, case.id)

    assert result.intact is False
    # Entry 1 now hashes consistently, so the failure surfaces at entry 2,
    # which still carries the pre-tamper prev_hash.
    assert result.first_broken_sequence == 2


def test_unhashed_legacy_entry_is_reported_as_unverifiable(db_session):
    """Entries written before chaining existed are missing provenance. That
    is not the same accusation as tampering and must not read like one."""
    case = _case(db_session)
    db_session.add(AuditEvent(case_id=case.id, event="old_event", detail="pre-chain",
                              sequence=0, prev_hash=None, entry_hash=None))
    db_session.commit()

    result = verify_audit_chain(db_session, case.id)

    assert result.intact is False
    assert "cannot be verified" in result.reason
    assert "not evidence of alteration" in result.reason


def test_case_with_no_entries(db_session):
    case = _case(db_session)

    result = verify_audit_chain(db_session, case.id)

    assert result.intact is True
    assert result.entry_count == 0


def test_chains_are_independent_per_case(db_session):
    """Tampering with one case must not invalidate another."""
    case_a, case_b = _case(db_session), _case(db_session)
    _chain_of(db_session, case_a, 3)
    _chain_of(db_session, case_b, 3)

    victim = (db_session.query(AuditEvent)
              .filter(AuditEvent.case_id == case_a.id, AuditEvent.sequence == 0).one())
    victim.detail = "tampered"
    db_session.commit()

    assert verify_audit_chain(db_session, case_a.id).intact is False
    assert verify_audit_chain(db_session, case_b.id).intact is True


def test_audit_endpoint_returns_entries_with_verification(client, db_session):
    case = _case(db_session)
    _chain_of(db_session, case, 2)

    body = client.get(f"/cases/{case.id}/audit").json()

    assert body["verification"]["intact"] is True
    assert len(body["entries"]) == 2
    assert body["entries"][0]["sequence"] == 0
    assert body["entries"][0]["entry_hash"]


def test_audit_endpoint_surfaces_tampering(client, db_session):
    case = _case(db_session)
    _chain_of(db_session, case, 3)
    tampered = db_session.query(AuditEvent).filter(AuditEvent.sequence == 0).one()
    tampered.event = "something_else"
    db_session.commit()

    body = client.get(f"/cases/{case.id}/audit").json()

    assert body["verification"]["intact"] is False
    assert body["verification"]["first_broken_sequence"] == 0


def test_hash_is_stable_across_a_database_round_trip(db_session):
    """The regression that made this chain unusable: SQLite drops the
    timezone offset, so hashing isoformat() directly produced one string on
    write and another on read, and every untouched log reported tampering."""
    case = _case(db_session)
    append_audit_event(db_session, case.id, "case_created", "first")
    db_session.commit()

    # Force a genuine reload rather than reading the identity-map copy.
    db_session.expire_all()

    assert verify_audit_chain(db_session, case.id).intact is True


def test_boundary_shifting_cannot_forge_a_matching_hash():
    """Fields are joined with a separator that cannot occur in them, so
    moving a character across a field boundary must change the hash."""
    from app.reports.audit_chain import compute_entry_hash

    stamp = "2026-01-01T00:00:00.000000"
    a = compute_entry_hash(0, "case", "ab", "c", stamp, False, GENESIS)
    b = compute_entry_hash(0, "case", "a", "bc", stamp, False, GENESIS)

    assert a != b
