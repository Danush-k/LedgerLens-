"""Tamper-evident audit chain.

Every audit entry hashes its own content together with the hash of the
entry before it. Rewriting any entry changes its hash, which invalidates
every link after it, so a modified log cannot be made to look consistent
without recomputing the whole chain from the altered point onward.

The chain is per case, because the case is the evidentiary unit - a report
exported for one case can carry that case's chain head, and the head is
what a court would compare against later.
"""
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.orm import AuditEvent

GENESIS = "0" * 64


def canonical_timestamp(value: datetime) -> str:
    """A timestamp representation that survives a database round-trip.

    SQLite discards timezone information, so a value written as
    "...+00:00" reads back as "..." and hashing isoformat() directly would
    report tampering on every untouched log - the chain would be worse than
    useless. Postgres preserves the offset, which means the two backends
    would also disagree with each other.

    Naive values are therefore treated as UTC (which is what they are - the
    column default writes UTC), converted, and formatted without an offset
    so both backends and both directions produce one string.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")


def compute_entry_hash(sequence: int, case_id: str, event: str, detail: str | None,
                       created_at: datetime | str, simulated: bool, prev_hash: str) -> str:
    """Hash one entry.

    Fields are joined with a separator that cannot occur inside them, so
    two different entries cannot produce the same input string by shifting
    a boundary - "ab" + "c" and "a" + "bc" must not collide.
    """
    stamp = created_at if isinstance(created_at, str) else canonical_timestamp(created_at)
    payload = "\x1f".join([
        str(sequence),
        case_id,
        event,
        detail or "",
        stamp,
        "1" if simulated else "0",
        prev_hash,
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def append_audit_event(db: Session, case_id: str, event: str,
                       detail: str | None = None, simulated: bool = False) -> AuditEvent:
    """Add an entry to the end of a case's chain.

    Flushes so created_at is populated by the database default before it is
    hashed; hashing a value the database has not yet assigned would produce
    a hash of None and break verification immediately.
    """
    last = (
        db.query(AuditEvent)
        .filter(AuditEvent.case_id == case_id)
        .order_by(AuditEvent.sequence.desc())
        .first()
    )
    sequence = (last.sequence + 1) if last else 0
    prev_hash = (last.entry_hash or GENESIS) if last else GENESIS

    entry = AuditEvent(case_id=case_id, event=event, detail=detail,
                       simulated=simulated, sequence=sequence, prev_hash=prev_hash)
    db.add(entry)
    db.flush()

    entry.entry_hash = compute_entry_hash(
        sequence, case_id, event, detail,
        entry.created_at, simulated, prev_hash,
    )
    db.flush()
    return entry


@dataclass
class ChainVerification:
    case_id: str
    intact: bool
    entry_count: int
    chain_head: str | None
    first_broken_sequence: int | None
    reason: str | None

    def as_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "intact": self.intact,
            "entry_count": self.entry_count,
            "chain_head": self.chain_head,
            "first_broken_sequence": self.first_broken_sequence,
            "reason": self.reason,
        }


def verify_audit_chain(db: Session, case_id: str) -> ChainVerification:
    """Walk a case's chain and report the first inconsistency, if any."""
    entries = (
        db.query(AuditEvent)
        .filter(AuditEvent.case_id == case_id)
        .order_by(AuditEvent.sequence.asc())
        .all()
    )
    if not entries:
        return ChainVerification(case_id, True, 0, None, None,
                                 "No audit entries recorded for this case.")

    expected_prev = GENESIS
    for index, entry in enumerate(entries):
        # Entries written before chaining existed carry no hash. Say so
        # rather than reporting tampering - "unverifiable" and "altered"
        # are different findings and only one of them is an accusation.
        if entry.entry_hash is None:
            return ChainVerification(
                case_id, False, len(entries), None, entry.sequence,
                f"Entry {entry.sequence} predates hash chaining and cannot be "
                f"verified. This is missing provenance, not evidence of "
                f"alteration.",
            )
        if entry.sequence != index:
            return ChainVerification(
                case_id, False, len(entries), None, entry.sequence,
                f"Sequence gap at position {index}: expected {index}, found "
                f"{entry.sequence}. An entry was deleted or reordered.",
            )
        if (entry.prev_hash or GENESIS) != expected_prev:
            return ChainVerification(
                case_id, False, len(entries), None, entry.sequence,
                f"Entry {entry.sequence} does not link to the previous entry. "
                f"The log was reordered, or an earlier entry was removed.",
            )
        recomputed = compute_entry_hash(
            entry.sequence, entry.case_id, entry.event, entry.detail,
            entry.created_at, entry.simulated, entry.prev_hash or GENESIS,
        )
        if recomputed != entry.entry_hash:
            return ChainVerification(
                case_id, False, len(entries), None, entry.sequence,
                f"Entry {entry.sequence} does not match its recorded hash - its "
                f"contents were altered after it was written.",
            )
        expected_prev = entry.entry_hash

    return ChainVerification(
        case_id, True, len(entries), entries[-1].entry_hash, None,
        f"All {len(entries)} entries verified. Each links to the one before it "
        f"and matches its recorded hash.",
    )
