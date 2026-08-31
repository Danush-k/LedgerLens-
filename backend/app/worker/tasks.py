from datetime import datetime, timezone

from app.chain_clients.base import Chain
from app.config import get_settings
from app.db.neo4j_client import record_transfer, upsert_address
from app.db.postgres import SessionLocal
from app.models.orm import AuditEvent, Case, TracedAddress
from app.risk.rules import recommended_action, score_case
from app.tracer.bfs import trace_wallet
from app.worker.celery_app import celery_app

RAPID_LAYERING_WINDOW_SECONDS = 600


def _detect_rapid_layering(edges: list[dict]) -> bool:
    arrival_ts: dict[str, int] = {}
    for edge in edges:
        target = edge["target"]
        if target not in arrival_ts or edge["timestamp"] < arrival_ts[target]:
            arrival_ts[target] = edge["timestamp"]

    for edge in edges:
        source_arrival = arrival_ts.get(edge["source"])
        if source_arrival and 0 < edge["timestamp"] - source_arrival < RAPID_LAYERING_WINDOW_SECONDS:
            return True
    return False


@celery_app.task(name="trace_wallet_task")
def trace_wallet_task(case_id: str) -> None:
    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        if not case:
            return

        case.status = "tracing"
        db.add(AuditEvent(case_id=case_id, event="trace_started",
                           detail=f"Tracing {case.reported_address} on {case.chain}"))
        db.commit()

        chain = Chain(case.chain)
        result = trace_wallet(chain, case.reported_address, hop_limit=case.hop_limit)

        # Persist the traced subgraph into Neo4j (durable graph store, and
        # what powers the shortest-path Cypher demo query).
        for node in result.nodes.values():
            upsert_address(node["chain"], node["address"],
                            {"type": node["node_type"], "name": node["label_name"]}
                            if node["label_name"] else None)
        for edge in result.edges:
            source_addr = result.nodes[edge["source"]]["address"]
            target_addr = result.nodes[edge["target"]]["address"]
            record_transfer(case_id, case.chain, source_addr, target_addr,
                             edge["tx_hash"], edge["value"], edge["timestamp"], edge["hop"])

        # "Has this exact wallet been reported before?" - the prior-report signal.
        prior_report_count = (
            db.query(TracedAddress)
            .filter(TracedAddress.chain == case.chain,
                    TracedAddress.address == case.reported_address.lower(),
                    TracedAddress.case_id != case_id)
            .count()
        )
        db.add(TracedAddress(case_id=case_id, chain=case.chain,
                              address=case.reported_address.lower()))

        rapid_layering = _detect_rapid_layering(result.edges)
        score, breakdown = score_case(result.flags, result.nearest_exchange,
                                       prior_report_count, rapid_layering)
        if rapid_layering:
            result.flags.add("rapid_layering")
        if prior_report_count > 0:
            result.flags.add("prior_report")

        case.status = "complete"
        case.hop_progress = result.hops_reached
        case.risk_score = score
        case.risk_breakdown = breakdown
        case.flags = sorted(result.flags)
        case.nearest_exchange = result.nearest_exchange
        case.graph = {"nodes": list(result.nodes.values()), "edges": result.edges}
        case.recommended_action = recommended_action(result.nearest_exchange, score)
        case.completed_at = datetime.now(timezone.utc)

        event = "exchange_identified" if result.nearest_exchange else "trace_completed"
        db.add(AuditEvent(case_id=case_id, event=event, detail=case.recommended_action))

        if result.nearest_exchange or score >= 50:
            from app.integrations.mock_lea import send_alert
            send_alert(db, case)

        db.commit()
    except Exception as exc:  # noqa: BLE001 - a failed trace must not crash the worker
        db.rollback()
        case = db.get(Case, case_id)
        if case:
            case.status = "failed"
            case.error = str(exc)
            db.add(AuditEvent(case_id=case_id, event="trace_failed", detail=str(exc)))
            db.commit()
    finally:
        db.close()
