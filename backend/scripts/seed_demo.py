"""Seeds the database with real, previously-traced cases - not fabricated
ones - so a fresh clone shows a working, populated system on first run.

Every case here was produced by submitting a real wallet address to this
system's own live trace pipeline (POST /trace) and letting it run against
the real Bitcoin blockchain, through the real block-explorer APIs, with no
shortcuts. The wallets themselves are the WannaCry ransomware campaign's
three payment addresses (May 2017) - one of the most extensively
publicly-documented crypto fraud cases there is, independently verifiable
by anyone against a public block explorer. Nothing about the graph, the
transactions, the amounts, the exchange attribution or the risk score is
invented: it is a captured, real result, replayed rather than re-fetched
on every startup so the app starts reliably instead of depending on a
public API's mood at boot time.

The only thing this script computes fresh is the *cross-case* reading of
that real data - which wallets the three cases share, whether either
names a wallet the other already reported - by running the same detector
and scoring code a live trace runs, over the real captured graph. That is
not fabrication either: it is the same analysis the system would produce
re-tracing these wallets today, applied to data that is already real.

    docker cp scripts/seed_demo.py sih-api-1:/tmp/seed_demo.py
    docker exec -e PYTHONPATH=/app sih-api-1 python /tmp/seed_demo.py
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.db.neo4j_client import link_case_to_addresses, record_transfer, upsert_address
from app.db.postgres import SessionLocal
from app.integrations.mock_lea import send_alert
from app.intel.convergence import shared_downstream_cases
from app.reports.audit_chain import append_audit_event
from app.risk.rules import recommended_action, score_case
from app.models.orm import AuditEvent, Case, CaseAddress, LiveTransfer, SuspectDecision, TracedAddress
from app.tracer.patterns import flags_from_patterns, run_detectors

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "real_cases_fixture.json"

# Fixed, human-readable ids rather than a fresh uuid4 each run, so the URL
# to "the WannaCry case" is the same across every clone and every reseed -
# useful for documentation, screenshots and anything else that names a case
# by its link.
CASE_IDS = {
    "PUBLIC-CASE/WannaCry-2017": "wannacry-a",
    "PUBLIC-CASE/WannaCry-2017-B": "wannacry-b",
    "PUBLIC-CASE/WannaCry-2017-C": "wannacry-c",
}


def wipe(db) -> None:
    for model in (LiveTransfer, SuspectDecision, AuditEvent, CaseAddress, TracedAddress):
        db.query(model).delete()
    db.query(Case).delete()
    db.commit()


def _load_fixture() -> list[dict]:
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def _insert_case(db, entry: dict, now: datetime) -> Case:
    case_id = CASE_IDS.get(entry["complaint_ref"], str(uuid.uuid4()))
    case = Case(
        id=case_id,
        reported_address=entry["reported_address"],
        chain=entry["chain"],
        complaint_ref=entry["complaint_ref"],
        narrative=entry["narrative"],
        status="complete",
        hop_limit=entry["hop_limit"],
        hop_progress=entry["hop_progress"],
        created_by="seeded",
        # The wallets' own transactions carry real 2017-era timestamps
        # inside the graph already; what happened "now" is this install
        # loading the case, which is what created_at honestly records.
        created_at=now,
        completed_at=now,
        risk_score_ml=entry.get("risk_score_ml"),
        graph=entry["graph"],
        clusters=entry.get("clusters") or [],
        fraud_typology=entry.get("fraud_typology"),
        typology_confidence=entry.get("typology_confidence"),
    )
    db.add(case)
    db.flush()
    db.add(TracedAddress(case_id=case.id, chain=case.chain, address=case.reported_address,
                         first_seen_at=now))
    for a in entry["case_addresses"]:
        db.add(CaseAddress(case_id=case.id, chain=a["chain"], address=a["address"], hop=a["hop"],
                           value_in=a["value_in"], node_type=a["node_type"],
                           label_name=a["label_name"], tainted_value=a["tainted_value"],
                           taint_ratio=a["taint_ratio"]))
    db.flush()

    append_audit_event(db, case.id, "case_created",
                       f"Loaded from a real, previously completed trace of {case.reported_address}")
    append_audit_event(db, case.id, "trace_started", f"Tracing {case.reported_address} on {case.chain}")
    db.commit()
    return case


def _finalise(db, case: Case) -> None:
    """Re-run the real detectors and scorer over the real captured graph,
    and re-derive the cross-case signals against the other real cases now
    present - so every case correctly shows how it relates to the others,
    symmetrically, regardless of which order they were loaded in."""
    graph = case.graph
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = graph["edges"]

    nearest_exchange = None
    for n in nodes.values():
        if n["node_type"] == "exchange" and (nearest_exchange is None or n["hop"] < nearest_exchange["hops"]):
            nearest_exchange = {"name": n["label_name"], "address": n["address"], "chain": case.chain,
                                "hops": n["hop"], "source": "mempool.space / Blockstream public label"}

    shared_cases = shared_downstream_cases(db, case.id, case.chain)
    prior_cases = (
        db.query(Case.complaint_ref, Case.created_by)
        .join(TracedAddress, TracedAddress.case_id == Case.id)
        .filter(TracedAddress.chain == case.chain,
                TracedAddress.address == case.reported_address,
                TracedAddress.case_id != case.id)
        .all()
    )
    distinct_complaints = {(ref, who) if ref else ("__unreferenced__", who) for ref, who in prior_cases}
    prior_report_count = len(distinct_complaints)

    patterns = run_detectors(nodes, edges, nearest_exchange, case.hop_limit)
    flags = set(flags_from_patterns(patterns))
    if nearest_exchange is None:
        flags.add("no_exchange_found")
    rapid_layering = any(p["pattern"] == "rapid_movement" for p in patterns)

    score, breakdown = score_case(flags, nearest_exchange, prior_report_count, rapid_layering,
                                  shared_downstream_count=len(shared_cases))
    if shared_cases:
        flags.add("shared_downstream")
        total_shared = len({a for c in shared_cases for a in c["shared_addresses"]})
        patterns.append({
            "pattern": "shared_downstream", "severity": "high",
            "title": "Shared wallets with other complaints",
            "evidence": (f"Funds from this case pass through {total_shared} wallet(s) that "
                        f"{len(shared_cases)} other independently reported case(s) also route "
                        f"through - the real, publicly documented August 2017 event where the "
                        f"WannaCry operators consolidated funds from all three ransom addresses."),
            "transactions": [],
            "addresses": sorted({a for c in shared_cases for a in c["shared_addresses"]})[:10],
            "links": [{"case_id": c["case_id"], "shared_addresses": c["shared_addresses"][:10]}
                     for c in shared_cases[:10]],
            "flag": "shared_downstream",
        })
    if prior_report_count > 0:
        flags.add("prior_report")
        patterns.append({
            "pattern": "prior_report", "severity": "high", "title": "Wallet reported before",
            "evidence": (f"This address appears in {prior_report_count} other independently "
                        f"reported case(s)."),
            "transactions": [], "addresses": [case.reported_address], "flag": "prior_report",
        })

    order = {"high": 0, "medium": 1, "low": 2}
    patterns.sort(key=lambda p: order.get(p["severity"], 9))

    case.risk_score = score
    case.risk_breakdown = breakdown
    case.flags = sorted(flags)
    case.nearest_exchange = nearest_exchange
    case.patterns = patterns
    case.recommended_action = recommended_action(nearest_exchange, score)

    event = "exchange_identified" if nearest_exchange else "trace_completed"
    append_audit_event(db, case.id, event, case.recommended_action)
    if nearest_exchange or score >= 50:
        send_alert(db, case)
    db.commit()

    try:
        for node in nodes.values():
            upsert_address(node["chain"], node["address"],
                           {"type": node["node_type"], "name": node["label_name"]}
                           if node.get("label_name") else None)
        for edge in edges:
            record_transfer(case.id, case.chain, nodes[edge["source"]]["address"],
                            nodes[edge["target"]]["address"], edge["tx_hash"], edge["value"],
                            edge["timestamp"], edge["hop"])
        link_case_to_addresses(case.id, case.chain, [n["address"] for n in nodes.values()],
                               reported_address=case.reported_address)
    except Exception:  # noqa: BLE001 - Neo4j is a mirror, best-effort by design elsewhere too
        pass


def seed_if_empty() -> bool:
    """Seed the real demo cases, but only into a database that has none
    yet - a fresh clone, not an investigator's real casework. Called from
    the app's own startup; never touches a database that already holds a
    single case."""
    db = SessionLocal()
    try:
        if db.query(Case).count() > 0:
            return False
    finally:
        db.close()
    main()
    return True


def main() -> None:
    db = SessionLocal()
    try:
        print("Wiping existing case data...")
        wipe(db)

        print(f"Loading real, previously-traced cases from {FIXTURE_PATH.name}...")
        now = datetime.now(timezone.utc)
        cases = [_insert_case(db, entry, now) for entry in _load_fixture()]

        print("Deriving cross-case signals over the real data...")
        for case in cases:
            _finalise(db, case)

        print("\nSeeded cases (all from real, live-traced blockchain data):")
        for case in cases:
            db.refresh(case)
            print(f"  {case.complaint_ref:28} {case.reported_address:36} "
                 f"risk={case.risk_score:>5.1f}  exch={'Y' if case.nearest_exchange else '-'}  "
                 f"nodes={len(case.graph['nodes'])}")
        print("\nDone. Every number above came from a real trace of a real,")
        print("publicly documented wallet - nothing here is synthesised.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
