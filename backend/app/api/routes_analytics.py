from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.postgres import get_db
from app.models.orm import Case
from app.risk import ml as risk_ml

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _risk_bucket(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


@router.get("/overview")
def analytics_overview(db: Session = Depends(get_db)):
    cases = db.query(Case).all()
    total = len(cases)

    by_status = dict(Counter(c.status for c in cases))
    by_chain = dict(Counter(c.chain for c in cases))

    scored = [c for c in cases if c.risk_score is not None]
    risk_buckets = dict(Counter(_risk_bucket(c.risk_score) for c in scored))
    avg_risk = round(sum(c.risk_score for c in scored) / len(scored), 1) if scored else None

    with_exchange = [c for c in cases if c.nearest_exchange]
    exchange_found_rate = round(len(with_exchange) / total * 100, 1) if total else 0.0

    flag_counter: Counter[str] = Counter()
    for c in cases:
        for flag in c.flags or []:
            flag_counter[flag] += 1

    exchange_counter: Counter[str] = Counter()
    for c in with_exchange:
        exchange_counter[c.nearest_exchange["name"]] += 1

    typology_counter: Counter[str] = Counter(c.fraud_typology for c in cases if c.fraud_typology)

    recent_high_risk = (
        db.query(Case)
        .filter(Case.risk_score >= 50)
        .order_by(Case.created_at.desc())
        .limit(5)
        .all()
    )

    return {
        "total_cases": total,
        "by_status": by_status,
        "by_chain": by_chain,
        "risk_buckets": {"low": risk_buckets.get("low", 0), "medium": risk_buckets.get("medium", 0),
                          "high": risk_buckets.get("high", 0)},
        "avg_risk_score": avg_risk,
        "exchange_found_count": len(with_exchange),
        "exchange_found_rate": exchange_found_rate,
        "flag_counts": dict(flag_counter),
        "typology_counts": dict(typology_counter),
        "top_exchanges": [{"name": name, "count": count} for name, count in exchange_counter.most_common(5)],
        "recent_high_risk": [
            {
                "id": c.id,
                "reported_address": c.reported_address,
                "chain": c.chain,
                "status": c.status,
                "risk_score": c.risk_score,
                "nearest_exchange": c.nearest_exchange,
                "created_at": c.created_at,
            }
            for c in recent_high_risk
        ],
    }


@router.get("/ml-status")
def ml_status(db: Session = Depends(get_db)):
    """Whether the v2 ML-assisted risk model is currently trainable, and
    why not if it isn't - surfaced directly rather than a silently-missing
    score, per the honest-scope framing in PLAN.md."""
    cases = db.query(Case).filter(Case.status == "complete").all()
    result = risk_ml.train(cases)
    return {
        "trained": result.model is not None,
        "trained_on": result.trained_on,
        "min_required": risk_ml.MIN_TRAINING_CASES,
        "reason_unavailable": result.reason_unavailable,
    }
