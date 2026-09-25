from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_serializer

from app.chain_clients.base import Chain


class TraceRequest(BaseModel):
    address: str = Field(..., description="Victim-reported wallet address")
    chain: Chain
    complaint_ref: str | None = Field(None, description="NCRP/complaint reference number, if any")
    narrative: str | None = Field(None, description="Free-text complaint description, used for typology tagging")
    hop_limit: int | None = Field(
        None, ge=1, le=8,
        description="How many hops to follow before stopping. Depth is a "
                    "judgement call per case - a direct cash-out resolves at 1-2 "
                    "hops, while a layered trail needs more - so it belongs to "
                    "the investigator, not to global configuration. Defaults to "
                    "the HOP_LIMIT setting when omitted.",
    )


class TraceAccepted(BaseModel):
    case_id: str
    status: str


class GraphNode(BaseModel):
    id: str  # f"{chain}:{address}"
    address: str
    chain: str
    node_type: str  # reported | intermediate | exchange | mixer | bridge | unresolved
    label_name: str | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    tx_hash: str
    value: float
    timestamp: int
    hop: int


class NearestExchange(BaseModel):
    name: str
    address: str
    chain: str
    hops: int


class AuditEventOut(BaseModel):
    event: str
    detail: str | None
    simulated: bool
    created_at: datetime

    class Config:
        from_attributes = True


class _UTCTimestamps(BaseModel):
    """Serialise every timestamp with its timezone.

    Everything is written in UTC, but SQLite returns it without the offset,
    and a browser reads an offset-less timestamp as local time - on an IST
    machine "checked 10 seconds ago" became "checked 5 hours ago".
    """

    @field_serializer("*", mode="wrap", when_used="json")
    def _utc(self, value, handler):
        if isinstance(value, datetime) and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return handler(value)


class CaseOut(_UTCTimestamps):
    id: str
    complaint_ref: str | None
    narrative: str | None
    created_by: str | None
    reported_address: str
    chain: str
    status: str
    hop_progress: int
    hop_limit: int
    status_message: str | None = None
    last_progress_at: datetime | None = None
    # Why a trace failed. Omitting this left the interface showing generic
    # fallback text while the backend held a specific, honest explanation -
    # losing exactly the "could not look" / "looked and found nothing"
    # distinction the rest of the system works to preserve.
    error: str | None = None
    risk_score: float | None
    risk_score_ml: float | None
    risk_breakdown: dict | None
    flags: list | None
    nearest_exchange: dict | None
    clusters: list | None
    patterns: list | None
    fraud_typology: str | None
    typology_confidence: float | None
    recommended_action: str | None
    graph: dict | None
    created_at: datetime
    completed_at: datetime | None
    # Live monitoring. What the page needs to say whether what it is showing
    # is current: whether this case is being watched in the background, when
    # its wallets were last re-read, and how much has moved since the trace.
    live_watch: bool = False
    live_checked_at: datetime | None = None
    live_event_count: int = 0
    live_last_event_at: datetime | None = None

    class Config:
        from_attributes = True


class CaseSummary(_UTCTimestamps):
    id: str
    reported_address: str
    chain: str
    status: str
    # Carried in the summary so the case list can show live progress rather
    # than an unexplained "Tracing" that looks identical to a stuck one.
    hop_progress: int = 0
    hop_limit: int = 5
    status_message: str | None = None
    risk_score: float | None
    nearest_exchange: dict | None
    fraud_typology: str | None
    created_at: datetime
    # Carried in the summary so the case list can mark a case whose wallets
    # have moved since it was traced, which is the one thing that would send
    # an investigator back to a case they had finished with.
    live_watch: bool = False
    live_event_count: int = 0
    live_last_event_at: datetime | None = None

    class Config:
        from_attributes = True
