"""The evidence report.

This is the artefact that leaves the system and may end up in front of a
court, so the tests care less about layout than about two claims the
document makes: that it shows the findings, and that the hash printed
beside them actually covers them.
"""
from datetime import datetime, timezone

from app.models.orm import Case
from app.reports.pdf import _snapshot_hash, build_case_report

GRAPH = {
    "nodes": [
        {"id": "bitcoin:bc1qroot", "address": "bc1qroot", "chain": "bitcoin",
         "node_type": "reported", "label_name": None, "hop": 0},
        {"id": "bitcoin:bc1qmule", "address": "bc1qmule", "chain": "bitcoin",
         "node_type": "unresolved", "label_name": None, "hop": 1},
    ],
    "edges": [
        {"source": "bitcoin:bc1qroot", "target": "bitcoin:bc1qmule", "tx_hash": "a" * 64,
         "value": 2.0, "timestamp": 1_700_000_000, "hop": 1, "tainted_value": 0.5},
    ],
}

PATTERNS = [
    {"pattern": "fan_out", "severity": "medium", "title": "Fan-out / dispersal",
     "evidence": "Sent to 15 wallets.", "transactions": ["b" * 64],
     "addresses": ["bc1qroot"], "flag": "high_fan_out"},
]


def _case(**overrides):
    defaults = dict(
        id="case-1", reported_address="bc1qroot", chain="bitcoin", status="complete",
        risk_score=58.0, risk_breakdown={"high_fan_out": 15}, flags=["high_fan_out"],
        nearest_exchange={"name": "Binance", "address": "1NDy", "chain": "bitcoin", "hops": 2},
        graph=GRAPH, patterns=PATTERNS, clusters=[], fraud_typology="investment_scam",
        recommended_action="Serve a preservation request on Binance.",
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Case(**defaults)


def test_report_builds_a_pdf():
    pdf = build_case_report(_case())

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_snapshot_hash_covers_the_findings():
    """The regression this guards: the hash previously covered only the
    graph, score and exchange, so the findings printed beside it could be
    rewritten while the document still certified them as intact."""
    original = _case()
    tampered = _case(patterns=[{**PATTERNS[0], "evidence": "Something else entirely."}])

    assert _snapshot_hash(original) != _snapshot_hash(tampered)


def test_snapshot_hash_covers_the_recommended_action():
    assert _snapshot_hash(_case()) != _snapshot_hash(
        _case(recommended_action="Take no action."))


def test_snapshot_hash_covers_clusters():
    assert _snapshot_hash(_case()) != _snapshot_hash(
        _case(clusters=[{"type": "common_input", "addresses": ["bc1qa", "bc1qb"]}]))


def test_snapshot_hash_is_stable_for_identical_input():
    assert _snapshot_hash(_case()) == _snapshot_hash(_case())


def test_report_includes_the_audit_verification():
    intact = build_case_report(_case(), audit={
        "intact": True, "entry_count": 4, "chain_head": "c" * 64, "reason": "All verified."})
    broken = build_case_report(_case(), audit={
        "intact": False, "entry_count": 4, "chain_head": None,
        "reason": "Entry 2 was altered."})

    # A failing chain must change the document, not be quietly omitted.
    assert intact != broken
    assert broken.startswith(b"%PDF")


def test_report_survives_a_case_with_no_findings_or_graph():
    """A failed or empty trace still has to produce a valid document rather
    than crashing the export."""
    pdf = build_case_report(_case(patterns=None, graph=None, risk_score=None,
                                  nearest_exchange=None, flags=None))

    assert pdf.startswith(b"%PDF")
