"""Turning a trace into a list of suspects an officer can act on.

The ranking is only useful if it is right about the obvious cases and honest
about the rest: the exchange account and the wallet still holding the money
must lead, a service must never be called a suspect, and nothing reaches a
report that an officer has not confirmed.
"""
import pytest

from app.intel.suspects import build_suspects
from app.models.orm import AuditEvent, Case, CaseAddress

ROOT, RELAY, HOLDER, VASP, MIXER, DUST, OTHER_VICTIM = (
    "bc1qroot", "bc1qrelay", "bc1qholder", "bc1qbinancedeposit", "bc1qmixer",
    "bc1qdust", "bc1qothervictim")


def _node(address, node_type, hop, tainted=0.0, label=None):
    return {"id": f"bitcoin:{address}", "address": address, "chain": "bitcoin",
            "node_type": node_type, "label_name": label, "hop": hop,
            "tainted_value": tainted, "taint_ratio": 1.0}


def _edge(src, dst, tx, value, hop, ts):
    return {"source": f"bitcoin:{src}", "target": f"bitcoin:{dst}", "tx_hash": tx,
            "value": value, "timestamp": ts, "hop": hop, "tainted_value": value}


def _case(db, **overrides):
    """Victim sent 10 BTC out: 6 via a relay to Binance, 3.9 parked, 0.1 dust."""
    fields = dict(
        reported_address=ROOT, chain="bitcoin", status="complete", hop_limit=4,
        complaint_ref="FIR/1", created_by="officer_a",
        nearest_exchange={"name": "Binance", "address": VASP, "chain": "bitcoin", "hops": 2},
        patterns=[{"pattern": "rapid_movement", "severity": "medium", "title": "Rapid",
                   "evidence": "", "transactions": [], "addresses": [RELAY],
                   "flag": "rapid_layering"}],
        clusters=[],
        graph={
            "nodes": [_node(ROOT, "reported", 0), _node(RELAY, "unresolved", 1, 6.0),
                      _node(HOLDER, "unresolved", 1, 3.9), _node(DUST, "unresolved", 1, 0.001),
                      _node(VASP, "exchange", 2, 5.9, "Binance")],
            "edges": [_edge(ROOT, RELAY, "tx_a", 6.0, 1, 1000),
                      _edge(ROOT, HOLDER, "tx_b", 3.9, 1, 1000),
                      _edge(ROOT, DUST, "tx_c", 0.001, 1, 1000),
                      _edge(RELAY, VASP, "tx_d", 5.9, 2, 1120)],
        },
    )
    case = Case(**{**fields, **overrides})
    db.add(case)
    db.commit()
    return case


def _by_address(result):
    return {s["address"]: s for s in result["suspects"]}


def test_the_obvious_suspects_lead_the_list(db_session):
    result = build_suspects(db_session, _case(db_session))
    suspects = _by_address(result)

    assert result["ready"] is True
    assert suspects[ROOT]["role"] == "reported"
    assert suspects[VASP]["role"] == "cashout"
    assert suspects[HOLDER]["role"] == "holding"
    assert suspects[RELAY]["role"] == "relay"
    for address in (ROOT, VASP):
        assert suspects[address]["priority"] == "high"
    assert [s["rank"] for s in result["suspects"]] == list(range(1, len(result["suspects"]) + 1))


def test_every_reason_is_a_sentence_with_its_transactions(db_session):
    """A reason an officer cannot repeat, or check, is not a reason."""
    cashout = _by_address(build_suspects(db_session, _case(db_session)))[VASP]
    reason = next(r for r in cashout["reasons"] if r["code"] == "cashout")
    assert "Binance" in reason["text"]
    assert reason["transactions"][0]["tx_hash"] == "tx_d"
    assert "Section 94" in cashout["recommended_action"]


def test_a_sliver_of_the_money_is_not_enough_to_be_a_suspect(db_session):
    assert DUST not in _by_address(build_suspects(db_session, _case(db_session)))


def test_a_mixer_is_a_trail_break_not_a_suspect(db_session):
    case = _case(db_session)
    graph = dict(case.graph)
    graph["nodes"] = graph["nodes"] + [_node(MIXER, "mixer", 2, 3.9, "Tornado")]
    graph["edges"] = graph["edges"] + [_edge(HOLDER, MIXER, "tx_m", 3.9, 2, 2000)]
    case.graph = graph
    db_session.commit()

    result = build_suspects(db_session, case)
    suspects = _by_address(result)
    assert MIXER not in suspects
    assert suspects[HOLDER]["role"] == "mixer_user"
    assert "trail breaks" in result["summary"]["headline"]


def test_the_summary_accounts_for_the_money_in_plain_words(db_session):
    summary = build_suspects(db_session, _case(db_session))["summary"]
    assert summary["victim_total"] == pytest.approx(9.901)
    assert summary["to_exchanges"] == pytest.approx(5.9)
    assert "reached Binance" in summary["headline"]
    assert "may still be recoverable" in summary["headline"]
    assert [s["key"] for s in summary["next_steps"]][:2] == ["legal_notice", "freeze"]


def test_another_complaint_through_the_same_wallet_raises_it(db_session):
    case = _case(db_session)
    before = _by_address(build_suspects(db_session, case))[HOLDER]["score"]

    other = Case(reported_address=OTHER_VICTIM, chain="bitcoin", status="complete",
                 complaint_ref="FIR/2", created_by="officer_b")
    db_session.add(other)
    db_session.flush()
    db_session.add(CaseAddress(case_id=other.id, chain="bitcoin", address=HOLDER, hop=1))
    db_session.commit()

    holder = _by_address(build_suspects(db_session, case))[HOLDER]
    assert holder["score"] > before
    assert holder["linked_cases"][0]["complaint_ref"] == "FIR/2"


def test_a_re_trace_of_the_same_complaint_is_not_corroboration(db_session):
    case = _case(db_session)
    retrace = Case(reported_address=ROOT, chain="bitcoin", status="complete",
                   complaint_ref="FIR/1", created_by="officer_a")
    db_session.add(retrace)
    db_session.flush()
    db_session.add(CaseAddress(case_id=retrace.id, chain="bitcoin", address=HOLDER, hop=1))
    db_session.commit()

    assert _by_address(build_suspects(db_session, case))[HOLDER]["linked_cases"] == []


def test_an_unfinished_trace_has_no_suspects_yet(db_session):
    result = build_suspects(db_session, _case(db_session, status="tracing"))
    assert result["ready"] is False
    assert result["suspects"] == []


# ── officer review and the report ─────────────────────────────────────────

def test_confirming_a_suspect_is_recorded_and_audited(client, db_session):
    case = _case(db_session)
    response = client.put(f"/cases/{case.id}/suspects/{HOLDER}",
                          json={"status": "confirmed", "note": "Matches UPI trail"})
    assert response.status_code == 200
    assert response.json()["suspect"]["decision"]["status"] == "confirmed"

    event = db_session.query(AuditEvent).filter(AuditEvent.case_id == case.id).one()
    assert event.event == "suspect_confirmed"
    assert "Matches UPI trail" in event.detail


def test_a_wallet_outside_the_case_cannot_be_ruled_on(client, db_session):
    case = _case(db_session)
    assert client.put(f"/cases/{case.id}/suspects/bc1qstranger",
                      json={"status": "confirmed"}).status_code == 404
    assert client.put(f"/cases/{case.id}/suspects/{HOLDER}",
                      json={"status": "guilty"}).status_code == 422


def test_the_report_is_refused_until_someone_is_confirmed(client, db_session):
    case = _case(db_session)
    response = client.get(f"/cases/{case.id}/suspect-report")
    assert response.status_code == 409
    assert "Confirm at least one" in response.json()["detail"]


def test_the_report_names_confirmed_suspects_only(client, db_session, monkeypatch):
    case = _case(db_session)
    client.put(f"/cases/{case.id}/suspects/{VASP}", json={"status": "confirmed"})
    client.put(f"/cases/{case.id}/suspects/{HOLDER}", json={"status": "dismissed"})

    captured = {}
    import app.api.routes_cases as routes
    real = routes.build_suspect_report

    def spy(case_, summary, confirmed, generated_by):
        captured["addresses"] = [s["address"] for s in confirmed]
        return real(case_, summary, confirmed, generated_by)

    monkeypatch.setattr(routes, "build_suspect_report", spy)
    response = client.get(f"/cases/{case.id}/suspect-report")

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert captured["addresses"] == [VASP]
    events = [e.event for e in db_session.query(AuditEvent).order_by(AuditEvent.sequence)]
    assert events[-1] == "suspect_report_generated"


def test_a_ruled_on_wallet_never_drops_off_the_list(db_session, client):
    """A confirmed suspect vanishing because the ranking shifted would
    silently remove it from the report."""
    case = _case(db_session)
    client.put(f"/cases/{case.id}/suspects/{DUST}", json={"status": "confirmed"})
    assert DUST in _by_address(build_suspects(db_session, case))


def test_the_full_report_carries_confirmed_suspects(client, db_session):
    case = _case(db_session)
    client.put(f"/cases/{case.id}/suspects/{VASP}", json={"status": "confirmed"})
    response = client.get(f"/cases/{case.id}/report")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
