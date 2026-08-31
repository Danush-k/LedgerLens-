from datetime import datetime, timezone

from app.models.orm import Case, TracedAddress


def _make_case(db, **overrides):
    defaults = dict(
        reported_address="0xaaa0000000000000000000000000000000000a",
        chain="ethereum",
        status="complete",
        risk_score=20.0,
        flags=[],
        nearest_exchange=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    case = Case(**defaults)
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def test_analytics_overview_aggregates_correctly(client, db_session):
    _make_case(db_session, risk_score=10.0, chain="ethereum", flags=["no_exchange_found"])
    _make_case(db_session, risk_score=80.0, chain="bitcoin", flags=["mixer_detected"],
               nearest_exchange={"name": "Binance", "address": "0x1", "chain": "ethereum", "hops": 1})
    _make_case(db_session, risk_score=50.0, chain="ethereum", flags=["high_fan_out"],
               nearest_exchange={"name": "Binance", "address": "0x1", "chain": "ethereum", "hops": 3})

    resp = client.get("/analytics/overview")
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_cases"] == 3
    assert body["by_chain"] == {"ethereum": 2, "bitcoin": 1}
    assert body["risk_buckets"] == {"low": 1, "medium": 1, "high": 1}
    assert body["exchange_found_count"] == 2
    assert body["top_exchanges"] == [{"name": "Binance", "count": 2}]
    assert len(body["recent_high_risk"]) == 2  # risk_score >= 50


def test_case_list_filters_by_chain_status_and_min_risk(client, db_session):
    _make_case(db_session, chain="ethereum", status="complete", risk_score=10.0)
    _make_case(db_session, chain="bitcoin", status="complete", risk_score=90.0)
    _make_case(db_session, chain="bitcoin", status="tracing", risk_score=None)

    assert len(client.get("/cases", params={"chain": "bitcoin"}).json()) == 2
    assert len(client.get("/cases", params={"status": "tracing"}).json()) == 1
    assert len(client.get("/cases", params={"min_risk": 50}).json()) == 1


def test_case_list_search_matches_address_substring(client, db_session):
    _make_case(db_session, reported_address="0xdeadbeef00000000000000000000000000000a")
    _make_case(db_session, reported_address="0xcafefeed00000000000000000000000000000b")

    results = client.get("/cases", params={"search": "deadbeef"}).json()
    assert len(results) == 1
    assert "deadbeef" in results[0]["reported_address"]


def test_related_cases_returns_other_cases_for_same_wallet(client, db_session):
    addr = "0xshared00000000000000000000000000000001"
    case_a = _make_case(db_session, reported_address=addr, chain="ethereum")
    case_b = _make_case(db_session, reported_address=addr, chain="ethereum")
    unrelated = _make_case(db_session, reported_address="0xother0000000000000000000000000000002")

    db_session.add(TracedAddress(case_id=case_a.id, chain="ethereum", address=addr))
    db_session.add(TracedAddress(case_id=case_b.id, chain="ethereum", address=addr))
    db_session.commit()

    related = client.get(f"/cases/{case_a.id}/related").json()
    related_ids = {c["id"] for c in related}

    assert related_ids == {case_b.id}
    assert unrelated.id not in related_ids


def test_related_cases_404s_for_unknown_case(client):
    resp = client.get("/cases/does-not-exist/related")
    assert resp.status_code == 404
