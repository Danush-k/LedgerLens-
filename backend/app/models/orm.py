import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    complaint_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    narrative: Mapped[str | None] = mapped_column(String, nullable=True)  # free-text complaint description
    reported_address: Mapped[str] = mapped_column(String, index=True)
    chain: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="queued")  # queued|tracing|complete|failed
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)  # investigator username

    hop_progress: Mapped[int] = mapped_column(Integer, default=0)
    hop_limit: Mapped[int] = mapped_column(Integer, default=5)
    status_message: Mapped[str | None] = mapped_column(String, nullable=True)
    # Heartbeat. A worker can die mid-trace - Celery acknowledges a task on
    # receipt, so nothing requeues it and the row is left claiming to be
    # tracing forever. This timestamp is what lets a stalled trace be told
    # apart from a slow one.
    last_progress_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score_ml: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    flags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    nearest_exchange: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    graph: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {nodes: [...], edges: [...]}
    clusters: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{type, addresses, note}]
    # Evidence-backed findings from tracer/patterns.py:
    # [{pattern, severity, title, evidence, transactions, addresses, flag}]
    patterns: Mapped[list | None] = mapped_column(JSON, nullable=True)
    fraud_typology: Mapped[str | None] = mapped_column(String, nullable=True)
    typology_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Live monitoring ────────────────────────────────────────────────
    # A completed trace describes the chain as it was at one moment. The
    # wallets in it keep spending afterwards, and a wallet that moves funds
    # to an exchange an hour after the report is the single most actionable
    # thing that can happen to a case - it is also the thing a static
    # snapshot can never show. These columns record what the watcher has
    # seen since, so the page can say "checked 20 seconds ago, two new
    # transfers" rather than presenting stale data as current.
    #
    # Watching costs explorer quota, so it is on only while someone is
    # looking at the case, unless live_watch is set - that is the explicit
    # "keep watching this one in the background" request.
    live_watch: Mapped[bool] = mapped_column(default=False)
    live_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    live_event_count: Mapped[int] = mapped_column(Integer, default=0)
    live_last_event_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="case")


class LiveTransfer(Base):
    """One transfer observed *after* the trace that opened the case finished.

    Kept as its own append-only table rather than only inside the case's
    graph JSON, for two reasons. It is evidence with its own timeline - when
    the money moved and when this system first saw it move are different
    facts, and both matter to an investigator arguing about how quickly a
    freeze request went out. And it survives a page reload: a feed rebuilt
    from a live stream alone would show an empty history to whoever opens
    the case next.
    """

    __tablename__ = "live_transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String, ForeignKey("cases.id"), index=True)
    chain: Mapped[str] = mapped_column(String)
    tx_hash: Mapped[str] = mapped_column(String, index=True)
    from_address: Mapped[str] = mapped_column(String, index=True)
    to_address: Mapped[str] = mapped_column(String, index=True)
    value: Mapped[float] = mapped_column(Float, default=0.0)
    # When the transfer was mined, per the explorer.
    timestamp: Mapped[int] = mapped_column(Integer, default=0)
    hop: Mapped[int] = mapped_column(Integer, default=0)
    # What the receiving wallet is, where the label set knows it. Recorded at
    # detection time so the feed can say "moved to Binance" without a join.
    to_node_type: Mapped[str | None] = mapped_column(String, nullable=True)
    to_label_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # When this system first saw it - distinct from `timestamp` above.
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SuspectDecision(Base):
    """An investigator's ruling on one wallet the system put forward as a suspect.

    The ranking is the system's inference; this row is the officer's
    judgement, and the two are kept apart on purpose. A report goes to an
    exchange or a court under an officer's name, so only wallets a person has
    reviewed and confirmed may appear in it - a wallet the algorithm ranked
    highly but nobody looked at is a lead, not an accusation.

    One row per (case, address), updated in place; every change is also
    written to the audit chain, which is where the history lives.
    """

    __tablename__ = "suspect_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String, ForeignKey("cases.id"), index=True)
    chain: Mapped[str] = mapped_column(String)
    address: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|confirmed|dismissed
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TracedAddress(Base):
    """The *reported* address of each case - one row per case.

    Powers the "has this exact wallet been reported before?" signal. For the
    full set of addresses a trace walked through, see CaseAddress below."""

    __tablename__ = "traced_addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String, ForeignKey("cases.id"), index=True)
    chain: Mapped[str] = mapped_column(String)
    address: Mapped[str] = mapped_column(String, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="investigator")  # investigator|admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditEvent(Base):
    """Every notable action on a case, in a tamper-evident chain.

    A plain audit table records what happened but proves nothing: anyone
    with database access can rewrite a row, reorder history or delete an
    inconvenient entry, and the log will look untouched. For a system whose
    output is meant to support a legal process that is a real weakness.

    Each entry therefore hashes its own contents together with the hash of
    the entry before it, so the log forms a chain per case. Altering any
    entry changes its hash, which breaks every link after it, and the break
    points at the exact entry that was touched.

    What this does and does not establish is worth being precise about.
    It detects modification, reordering and deletion of entries within a
    case. It does not stop someone who can write to the database from
    deleting a case wholesale and recomputing a fresh chain - defending
    against that needs the chain head published somewhere outside this
    system, which a production deployment should do and this prototype
    does not.
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String, ForeignKey("cases.id"), index=True)
    event: Mapped[str] = mapped_column(String)
    detail: Mapped[str | None] = mapped_column(String, nullable=True)
    simulated: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # Position in this case's chain, starting at 0. Explicit rather than
    # inferred from id, because ids are global and gaps would be ambiguous.
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    # The previous entry's hash. Null only for the first entry in a case.
    prev_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    # SHA-256 over this entry's content plus prev_hash.
    entry_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    case: Mapped[Case] = relationship(back_populates="audit_events")


class CaseAddress(Base):
    """Every address a trace walked through, one row per (case, address).

    TracedAddress records only the wallet a complainant reported. This table
    records the whole subgraph that trace touched, which is what makes
    cross-case analysis possible: when wallets from several independent
    complaints appear here against the same address, that address is a
    convergence point - a wallet collecting from multiple victims. Neither
    the per-case graph JSON nor TracedAddress can express that, because
    neither is queryable across cases.

    Kept in Postgres (not only Neo4j) so convergence analysis still works
    when the graph database is unavailable, which it routinely is in local
    development.
    """

    __tablename__ = "case_addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String, ForeignKey("cases.id"), index=True)
    chain: Mapped[str] = mapped_column(String)
    address: Mapped[str] = mapped_column(String, index=True)

    hop: Mapped[int] = mapped_column(Integer, default=0)
    # Traced value that reached this address along this case's paths. Not the
    # wallet's balance - see the commingling detector for why those differ.
    value_in: Mapped[float] = mapped_column(Float, default=0.0)
    # Denormalized from the label set so convergence queries can exclude
    # known services without a join. Exchanges collect from thousands of
    # unrelated people by design; they are noise here, not signal.
    node_type: Mapped[str | None] = mapped_column(String, nullable=True)
    label_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # Share of the value reaching this address attributable to the victim,
    # from the haircut computation in tracer/bfs.py. "Connected to the
    # victim" is weak; "holds 3.4% victim funds" is actionable.
    tainted_value: Mapped[float] = mapped_column(Float, default=0.0)
    taint_ratio: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
