"""The watcher that keeps a finished case current.

What these guard is the distinction the rest of the system is built on:
"nothing has moved" and "we could not look" are different answers, and a
live feature is where they are easiest to confuse - a silent explorer looks
exactly like a quiet wallet.
"""
from datetime import datetime, timezone

import pytest

from app.chain_clients.base import Chain, Transfer
from app.live import monitor as live
from app.models.orm import AuditEvent, Case, CaseAddress, LiveTransfer

ROOT = "bc1qroot"
HOP1 = "bc1qhopone"
NEW = "bc1qbrandnew"
EXCHANGE = "bc1qexchangedeposit"


def _graph_case(db, **overrides):
    """A completed case whose money went one hop and stopped there."""
    fields = dict(
        reported_address=ROOT, chain="bitcoin", status="complete", hop_limit=3,
        risk_score=40.0, flags=["no_exchange_found"], patterns=[],
        created_by="investigator",
        graph={
            "nodes": [
                {"id": f"bitcoin:{ROOT}", "address": ROOT, "chain": "bitcoin",
                 "node_type": "reported", "label_name": None, "hop": 0,
                 "tainted_value": 0.0, "taint_ratio": 1.0},
                {"id": f"bitcoin:{HOP1}", "address": HOP1, "chain": "bitcoin",
                 "node_type": "unresolved", "label_name": None, "hop": 1,
                 "tainted_value": 2.0, "taint_ratio": 1.0},
            ],
            "edges": [
                {"source": f"bitcoin:{ROOT}", "target": f"bitcoin:{HOP1}",
                 "tx_hash": "tx_original", "value": 2.0, "timestamp": 1_700_000_000,
                 "hop": 1, "tainted_value": 2.0},
            ],
        },
    )
    case = Case(**{**fields, **overrides})
    db.add(case)
    db.commit()
    return case


class _FakeClient:
    """Returns a canned history per address, or raises for one that is
    configured to fail - the explorer being down, which must never read as
    the wallet being quiet."""

    def __init__(self, by_address: dict[str, list[Transfer]], failing: set[str] | None = None):
        self.chain = Chain.BITCOIN
        self._by_address = by_address
        self._failing = failing or set()
        self.calls: list[str] = []

    def get_outgoing_transfers(self, address: str) -> list[Transfer]:
        self.calls.append(address)
        if address in self._failing:
            raise RuntimeError("bitcoin explorer rate limit reached")
        return self._by_address.get(address, [])


def _transfer(from_address: str, to_address: str, tx_hash: str, value: float = 1.5):
    return Transfer(tx_hash=tx_hash, chain=Chain.BITCOIN, from_address=from_address,
                    to_address=to_address, value=value, timestamp=1_700_009_999)


@pytest.fixture()
def patched_client(monkeypatch):
    def install(client):
        monkeypatch.setattr(live, "get_chain_client", lambda chain, cached=True: client)
        return client
    return install


# ── detection ─────────────────────────────────────────────────────────────

def test_movement_after_the_trace_is_added_to_the_case(db_session, patched_client):
    """The point of the whole feature: a wallet spends after the trace ran,
    and the case says so without anyone re-running it."""
    case = _graph_case(db_session)
    patched_client(_FakeClient({HOP1: [_transfer(HOP1, NEW, "tx_live_1", 0.5)]}))

    result = live.check_case_for_new_transfers(db_session, case.id)

    assert len(result["new_edges"]) == 1
    assert result["new_edges"][0]["tx_hash"] == "tx_live_1"

    db_session.refresh(case)
    edges = case.graph["edges"]
    assert len(edges) == 2
    assert edges[1]["detected_live"] is True
    assert {n["address"] for n in case.graph["nodes"]} == {ROOT, HOP1, NEW}
    assert case.live_event_count == 1
    assert case.live_last_event_at is not None
    assert case.live_checked_at is not None


def test_the_same_transfer_is_not_recorded_twice(db_session, patched_client):
    """A watcher re-reads the same history every cycle. Keying on the
    transaction rather than on 'what is new since last time' is what stops
    the graph doubling every thirty seconds."""
    case = _graph_case(db_session)
    patched_client(_FakeClient({HOP1: [_transfer(HOP1, NEW, "tx_live_1", 0.5)]}))

    live.check_case_for_new_transfers(db_session, case.id)
    second = live.check_case_for_new_transfers(db_session, case.id)

    assert second["new_edges"] == []
    db_session.refresh(case)
    assert len(case.graph["edges"]) == 2
    assert case.live_event_count == 1
    assert db_session.query(LiveTransfer).count() == 1


def test_transfers_already_in_the_traced_graph_are_not_new(db_session, patched_client):
    """The first live read sees the whole history, most of which the trace
    already walked. Reporting that as new movement would announce the
    original trace back to the investigator as breaking news."""
    case = _graph_case(db_session)
    patched_client(_FakeClient({ROOT: [_transfer(ROOT, HOP1, "tx_original", 2.0)]}))

    result = live.check_case_for_new_transfers(db_session, case.id)

    assert result["new_edges"] == []
    db_session.refresh(case)
    assert len(case.graph["edges"]) == 1


def test_a_running_trace_is_left_alone(db_session, patched_client):
    """A trace already walks these wallets. Watching one mid-flight would
    race the worker writing the same graph."""
    case = _graph_case(db_session, status="tracing")
    client = patched_client(_FakeClient({}))

    assert live.check_case_for_new_transfers(db_session, case.id) is None
    assert client.calls == []


# ── an unreachable explorer is not a quiet wallet ─────────────────────────

def test_a_failed_fetch_is_reported_as_a_failure(db_session, patched_client):
    case = _graph_case(db_session)
    patched_client(_FakeClient({}, failing={ROOT, HOP1}))

    result = live.check_case_for_new_transfers(db_session, case.id)

    assert result["new_edges"] == []
    assert len(result["errors"]) == 2
    assert "rate limit" in result["errors"][0]["error"]
    db_session.refresh(case)
    # The check still happened, and saying when it happened is what stops a
    # stale page from looking current.
    assert case.live_checked_at is not None
    assert case.live_event_count == 0


# ── what a live transfer changes about the case ───────────────────────────

def test_reaching_an_exchange_live_updates_the_attribution(db_session, patched_client,
                                                            monkeypatch):
    """The single most actionable thing that can happen to a case: the money
    lands at a VASP after the report was filed."""
    case = _graph_case(db_session)
    patched_client(_FakeClient({HOP1: [_transfer(HOP1, EXCHANGE, "tx_cashout", 1.9)]}))
    monkeypatch.setattr(live, "lookup_label", lambda chain, address: (
        {"type": "exchange", "name": "Binance", "source": "seed label set"}
        if address == EXCHANGE else None))

    live.check_case_for_new_transfers(db_session, case.id)

    db_session.refresh(case)
    assert case.nearest_exchange["name"] == "Binance"
    assert case.nearest_exchange["hops"] == 2
    # The absence claim has to go the moment it stops being true.
    assert "no_exchange_found" not in case.flags
    assert "Binance" in case.recommended_action


def test_victim_attribution_carries_onto_a_live_transfer(db_session, patched_client):
    """A wallet fully attributable to the victim that sends 0.5 has sent 0.5
    of the victim's money. Without this the live edge would show as clean."""
    case = _graph_case(db_session)
    patched_client(_FakeClient({HOP1: [_transfer(HOP1, NEW, "tx_live_1", 0.5)]}))

    live.check_case_for_new_transfers(db_session, case.id)

    db_session.refresh(case)
    live_edge = case.graph["edges"][1]
    new_node = next(n for n in case.graph["nodes"] if n["address"] == NEW)
    assert live_edge["tainted_value"] == pytest.approx(0.5)
    assert new_node["tainted_value"] == pytest.approx(0.5)
    assert new_node["taint_ratio"] == pytest.approx(1.0)


def test_a_live_wallet_joins_the_cross_case_footprint(db_session, patched_client):
    """Convergence analysis reads CaseAddress, so a wallet reached live has
    to land there too - otherwise the wallet collecting from several victims
    stays invisible exactly while it is most active."""
    case = _graph_case(db_session)
    patched_client(_FakeClient({HOP1: [_transfer(HOP1, NEW, "tx_live_1", 0.5)]}))

    live.check_case_for_new_transfers(db_session, case.id)

    row = (db_session.query(CaseAddress)
           .filter(CaseAddress.case_id == case.id, CaseAddress.address == NEW).one())
    assert row.value_in == pytest.approx(0.5)
    assert row.hop == 2


def test_detection_is_written_to_the_audit_chain(db_session, patched_client):
    """When movement was first seen is evidence, so it belongs where the
    record is tamper-evident rather than only in the graph JSON."""
    case = _graph_case(db_session)
    patched_client(_FakeClient({HOP1: [_transfer(HOP1, NEW, "tx_live_1", 0.5)]}))

    live.check_case_for_new_transfers(db_session, case.id)

    events = db_session.query(AuditEvent).filter(AuditEvent.case_id == case.id).all()
    assert [e.event for e in events] == ["live_transfer_detected"]
    assert "1 new outgoing transfer" in events[0].detail
    assert events[0].entry_hash


# ── which wallets get the small budget ────────────────────────────────────

def test_watch_list_leads_with_the_reported_wallet_then_wallets_holding_funds():
    nodes = [
        {"id": "c:spent", "address": "spent", "node_type": "unresolved", "hop": 1,
         "tainted_value": 9.0},
        {"id": "c:holding", "address": "holding", "node_type": "unresolved", "hop": 1,
         "tainted_value": 3.0},
        {"id": "c:root", "address": "root", "node_type": "reported", "hop": 0,
         "tainted_value": 0.0},
    ]
    edges = [{"source": "c:spent", "target": "c:holding", "value": 1.0}]

    assert live.select_watch_addresses(nodes, edges, hop_limit=3, limit=8) == [
        "root",      # the wallet the complaint names
        "holding",   # money sitting still is money that can still move
        "spent",
    ]


def test_services_and_the_hop_limit_are_left_out_of_the_watch_list():
    """An exchange hot wallet moves money for thousands of unrelated people,
    and a wallet at the hop limit would produce nodes deeper than the
    investigator asked for."""
    nodes = [
        {"id": "c:root", "address": "root", "node_type": "reported", "hop": 0},
        {"id": "c:vasp", "address": "vasp", "node_type": "exchange", "hop": 1},
        {"id": "c:mixer", "address": "mixer", "node_type": "mixer", "hop": 1},
        {"id": "c:edge", "address": "atlimit", "node_type": "unresolved", "hop": 2},
    ]

    assert live.select_watch_addresses(nodes, [], hop_limit=2, limit=8) == ["root"]


def test_the_watch_list_is_capped():
    nodes = [{"id": f"c:{i}", "address": f"w{i}", "node_type": "unresolved", "hop": 1,
              "tainted_value": float(i)} for i in range(30)]
    assert len(live.select_watch_addresses(nodes, [], hop_limit=5, limit=8)) == 8


# ── subscribers ───────────────────────────────────────────────────────────

def test_events_reach_every_open_stream_for_that_case_only():
    monitor = live.LiveMonitor()
    watching = monitor.subscribe("case-a")
    also_watching = monitor.subscribe("case-a")
    elsewhere = monitor.subscribe("case-b")

    monitor.publish("case-a", "transactions", {"edges": [{"tx_hash": "tx1"}]})

    assert watching.get_nowait()["data"]["edges"][0]["tx_hash"] == "tx1"
    assert also_watching.get_nowait()["type"] == "transactions"
    assert elsewhere.empty()

    monitor.unsubscribe("case-a", watching)
    assert monitor.viewer_count("case-a") == 1


def test_a_case_stops_being_watched_once_nobody_is_looking(db_session, monkeypatch):
    """Watching costs explorer quota. Tying it to attention is what keeps a
    closed tab from spending it forever."""
    monitor = live.LiveMonitor()
    settings = live.get_settings()
    monkeypatch.setattr(settings, "live_viewer_ttl_seconds", 0)

    monitor.mark_viewed("case-a")
    assert monitor._due_case_ids(db_session, settings) == []


def test_an_explicitly_watched_case_is_checked_with_nobody_looking(db_session):
    monitor = live.LiveMonitor()
    case = _graph_case(db_session, live_watch=True)

    assert monitor._due_case_ids(db_session, live.get_settings()) == [case.id]


# ── the API surface ───────────────────────────────────────────────────────

def test_watch_can_be_turned_on_and_off(client, db_session):
    case = _graph_case(db_session)

    on = client.post(f"/live/cases/{case.id}/watch", json={"enabled": True})
    assert on.status_code == 200
    assert on.json()["live_watch"] is True

    off = client.post(f"/live/cases/{case.id}/watch", json={"enabled": False})
    assert off.json()["live_watch"] is False

    events = [e.event for e in db_session.query(AuditEvent).all()]
    assert events == ["live_watch_enabled", "live_watch_disabled"]


def test_watching_an_unfinished_trace_is_refused(client, db_session):
    case = _graph_case(db_session, status="tracing")
    assert client.post(f"/live/cases/{case.id}/watch", json={"enabled": True}).status_code == 409


def test_the_feed_survives_a_reload(client, db_session):
    """A feed rebuilt only from the live stream would show an empty history
    to whoever opens the case next."""
    case = _graph_case(db_session)
    db_session.add(LiveTransfer(
        case_id=case.id, chain="bitcoin", tx_hash="tx_live_1", from_address=HOP1,
        to_address=EXCHANGE, value=1.9, timestamp=1_700_009_999, hop=2,
        to_node_type="exchange", to_label_name="Binance",
        detected_at=datetime.now(timezone.utc)))
    db_session.commit()

    body = client.get(f"/live/cases/{case.id}/transfers").json()
    assert len(body) == 1
    assert body[0]["to_label_name"] == "Binance"
    assert body[0]["tx_hash"] == "tx_live_1"


def test_live_status_reports_whether_the_case_is_being_watched(client, db_session):
    case = _graph_case(db_session)
    body = client.get(f"/live/cases/{case.id}/status").json()
    assert body["status"] == "complete"
    assert body["live_event_count"] == 0
    assert "poll_seconds" in body


def test_the_stream_refuses_an_unauthenticated_client(unauthenticated_client, db_session):
    case = _graph_case(db_session)
    assert unauthenticated_client.get(f"/live/cases/{case.id}/stream").status_code == 401
