from datetime import datetime

from pydantic import BaseModel, Field

from app.chain_clients.base import Chain


class TraceRequest(BaseModel):
    address: str = Field(..., description="Victim-reported wallet address")
    chain: Chain
    complaint_ref: str | None = Field(None, description="NCRP/complaint reference number, if any")


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


class CaseOut(BaseModel):
    id: str
    complaint_ref: str | None
    reported_address: str
    chain: str
    status: str
    hop_progress: int
    hop_limit: int
    risk_score: float | None
    risk_score_ml: float | None
    risk_breakdown: dict | None
    flags: list | None
    nearest_exchange: dict | None
    recommended_action: str | None
    graph: dict | None
    created_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


class CaseSummary(BaseModel):
    id: str
    reported_address: str
    chain: str
    status: str
    risk_score: float | None
    nearest_exchange: dict | None
    created_at: datetime

    class Config:
        from_attributes = True
