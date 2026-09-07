from datetime import datetime, timezone

from app.chain_clients.base import Chain
from app.config import get_settings
from app.db.neo4j_client import link_case_to_addresses, record_transfer, upsert_address
from app.db.postgres import SessionLocal
from app.models.orm import AuditEvent, Case, CaseAddress, TracedAddress
from app.reports.audit_chain import append_audit_event
from app.risk import ml as risk_ml
from app.risk.rules import recommended_action, score_case
from app.risk.typology import classify_typology
from app.tracer.bfs import trace_wallet
from app.tracer.clustering import common_input_clusters, shared_funder_clusters
from app.tracer.patterns import flags_from_patterns, run_detectors
from app.worker.celery_app import celery_app


@celery_app.task(name="trace_wallet_task")
def trace_wallet_task(case_id: str) -> None:
    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        if not case:
            return

        case.status = "tracing"
        append_audit_event(db, case_id, "trace_started",
                            f"Tracing {case.reported_address} on {case.chain}")
        db.commit()

        chain = Chain(case.chain)
        result = trace_wallet(chain, case.reported_address, hop_limit=case.hop_limit)

        # If we could not retrieve the reported wallet's history at all, we
        # have no evidence - not "no findings". Scoring an empty fetch would
        # present an API outage as an investigative conclusion.
        if result.root_fetch_failed:
            detail = result.fetch_errors[0]["error"] if result.fetch_errors else "unknown error"
            case.status = "failed"
            case.error = (
                f"Could not retrieve blockchain data for {case.reported_address} "
                f"from the {case.chain} data provider ({detail}). No trace was "
                f"performed - this is a data availability problem, not a finding "
                f"about the wallet. Retry once the provider is reachable."
            )
            case.completed_at = datetime.now(timezone.utc)
            append_audit_event(db, case_id, "trace_failed", case.error)
            db.commit()
            return

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
        link_case_to_addresses(case_id, case.chain,
                                [n["address"] for n in result.nodes.values()],
                                reported_address=case.reported_address)

        # Record the trace's full address footprint in Postgres. The per-case
        # graph JSON above is a render; this is the queryable record that lets
        # convergence analysis find wallets collecting from several separate
        # complaints. Value in is summed per address from the traced edges,
        # so an address reached by two paths in one case counts both.
        value_into: dict[str, float] = {}
        for edge in result.edges:
            target_addr = result.nodes[edge["target"]]["address"]
            value_into[target_addr] = value_into.get(target_addr, 0.0) + edge["value"]
        db.query(CaseAddress).filter(CaseAddress.case_id == case_id).delete()
        for node in result.nodes.values():
            db.add(CaseAddress(
                case_id=case_id,
                chain=node["chain"],
                address=node["address"],
                hop=node["hop"],
                value_in=value_into.get(node["address"], 0.0),
                node_type=node["node_type"],
                label_name=node["label_name"],
                tainted_value=node.get("tainted_value", 0.0),
                taint_ratio=node.get("taint_ratio", 0.0),
            ))

        # "Has this exact wallet been reported before?" - the prior-report signal.
        prior_report_count = (
            db.query(TracedAddress)
            .filter(TracedAddress.chain == case.chain,
                    TracedAddress.address == case.reported_address,  # already normalized at submission
                    TracedAddress.case_id != case_id)
            .count()
        )
        db.add(TracedAddress(case_id=case_id, chain=case.chain, address=case.reported_address))

        # Pattern detection: turn the traced subgraph into structured,
        # evidence-backed findings, then collapse those into the flat flag
        # strings the risk scorer and UI badges already understand.
        patterns = run_detectors(result.nodes, result.edges,
                                  result.nearest_exchange, case.hop_limit)
        result.flags |= flags_from_patterns(patterns)

        rapid_layering = any(p["pattern"] == "rapid_movement" for p in patterns)
        score, breakdown = score_case(result.flags, result.nearest_exchange,
                                       prior_report_count, rapid_layering)
        if prior_report_count > 0:
            result.flags.add("prior_report")
            patterns.append({
                "pattern": "prior_report",
                "severity": "high",
                "title": "Wallet reported before",
                "evidence": (
                    f"This address appears in {prior_report_count} other "
                    f"independently reported case(s) - repeat use across separate "
                    f"complaints strengthens the attribution to one actor."
                ),
                "transactions": [],
                "addresses": [case.reported_address],
                "flag": "prior_report",
            })

        # Clustering: common-input-ownership (Bitcoin, strong signal) +
        # shared-funder fan-out (any chain, weaker signal) - both explainable,
        # both computed from data already fetched during the trace.
        clusters = common_input_clusters(result.chain_client, {n["address"] for n in result.nodes.values()})
        clusters += shared_funder_clusters(result.nodes, result.edges)

        case.status = "complete"
        case.hop_progress = result.hops_reached
        case.risk_score = score
        case.risk_breakdown = breakdown
        case.flags = sorted(result.flags)
        case.nearest_exchange = result.nearest_exchange
        case.graph = {"nodes": list(result.nodes.values()), "edges": result.edges,
                       "truncated": result.truncated}
        case.clusters = clusters
        case.patterns = patterns
        case.recommended_action = recommended_action(result.nearest_exchange, score)
        case.completed_at = datetime.now(timezone.utc)
        case.fraud_typology, case.typology_confidence = classify_typology(case.narrative)

        event = "exchange_identified" if result.nearest_exchange else "trace_completed"
        append_audit_event(db, case_id, event, case.recommended_action)

        if result.nearest_exchange or score >= 50:
            from app.integrations.mock_lea import send_alert
            send_alert(db, case)

        db.commit()

        # ML-assisted risk score (v2) - retrained on every completion, which
        # is cheap at this data scale. Best-effort: never blocks the case.
        try:
            all_cases = db.query(Case).filter(Case.status == "complete").all()
            training = risk_ml.train(all_cases)
            if training.model is not None:
                case.risk_score_ml = risk_ml.predict(training.model, case)
                db.commit()
        except Exception:  # noqa: BLE001 - the rule-based score is always authoritative
            db.rollback()
    except Exception as exc:  # noqa: BLE001 - a failed trace must not crash the worker
        db.rollback()
        case = db.get(Case, case_id)
        if case:
            case.status = "failed"
            case.error = str(exc)
            append_audit_event(db, case_id, "trace_failed", str(exc))
            db.commit()
    finally:
        db.close()
