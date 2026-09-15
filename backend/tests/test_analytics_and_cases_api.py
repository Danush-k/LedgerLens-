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


# ── pagination ────────────────────────────────────────────────────────────

def test_case_list_paginates(client, db_session):
    for i in range(7):
        _make_case(db_session, reported_address=f"0xaaa{i:039x}")

    page_1 = client.get("/cases?limit=3&offset=0")
    page_2 = client.get("/cases?limit=3&offset=3")

    assert len(page_1.json()) == 3
    assert len(page_2.json()) == 3
    # Pages must not overlap, or a reader scrolling through sees duplicates
    # and silently misses cases.
    assert {c["id"] for c in page_1.json()}.isdisjoint({c["id"] for c in page_2.json()})


def test_case_list_reports_the_total(client, db_session):
    """Without a total, a full page is indistinguishable from a truncated
    one - the reader cannot tell whether the list ended."""
    for i in range(5):
        _make_case(db_session, reported_address=f"0xbbb{i:039x}")

    response = client.get("/cases?limit=2")

    assert response.headers["X-Total-Count"] == "5"
    assert len(response.json()) == 2


def test_case_list_pagination_respects_filters(client, db_session):
    for i in range(4):
        _make_case(db_session, chain="bitcoin", reported_address=f"bc1q{i}")
    _make_case(db_session, chain="ethereum", reported_address="0xccc")

    response = client.get("/cases?chain=bitcoin&limit=10")

    assert response.headers["X-Total-Count"] == "4"
    assert all(c["chain"] == "bitcoin" for c in response.json())


def test_case_list_rejects_an_oversized_page(client):
    assert client.get("/cases?limit=5000").status_code == 422


# ── failure reasons must survive the trip to the client ───────────────────

def test_case_detail_exposes_the_failure_reason(client, db_session):
    """The backend writes a careful explanation of *why* a trace failed -
    usually that the data provider was unreachable, which says nothing about
    the wallet. Dropping it from the response left the interface showing
    generic fallback text and lost that distinction entirely."""
    case = _make_case(db_session, status="failed",
                      error="Could not retrieve blockchain data (HTTPError 429).")

    body = client.get(f"/cases/{case.id}").json()

    assert body["error"] == "Could not retrieve blockchain data (HTTPError 429)."


def test_case_detail_exposes_live_progress(client, db_session):
    """A spinner with no progress cannot be told apart from a stalled one."""
    case = _make_case(db_session, status="tracing", hop_progress=2,
                      status_message="Reading hop 2 of 5 - 8 wallets to check")

    body = client.get(f"/cases/{case.id}").json()

    assert body["hop_progress"] == 2
    assert body["status_message"] == "Reading hop 2 of 5 - 8 wallets to check"


def test_case_list_carries_progress_for_running_traces(client, db_session):
    _make_case(db_session, status="tracing", hop_progress=3)

    row = next(c for c in client.get("/cases").json() if c["status"] == "tracing")

    assert row["hop_progress"] == 3
    assert row["hop_limit"] >= 1


# ── case links: which wallet connects which cases ─────────────────────────

def test_links_names_the_wallet_behind_a_repeat_report(client, db_session):
    """"Appears in 5 other cases" is a statistic. Which wallet created the
    link is the part an investigator can act on."""
    first = _make_case(db_session, reported_address="bc1qshared", chain="bitcoin",
                        status="complete")
    second = _make_case(db_session, reported_address="bc1qshared", chain="bitcoin",
                         status="complete")
    for case in (first, second):
        db_session.add(TracedAddress(case_id=case.id, chain="bitcoin",
                                     address="bc1qshared"))
    db_session.commit()

    links = client.get(f"/cases/{second.id}/links").json()

    assert len(links) == 1
    assert links[0]["case_id"] == first.id
    assert links[0]["relationship"] == "same_wallet"
    assert links[0]["shared_addresses"] == ["bc1qshared"]


def test_links_surfaces_shared_downstream_wallets(client, db_session):
    """Two traces meeting at a wallet neither case reported - corroboration
    from a separate victim, and previously buried inside a finding."""
    other = _make_case(db_session, reported_address="bc1qother", status="complete")
    case = _make_case(db_session, reported_address="bc1qmine", status="complete",
                      patterns=[{
                          "pattern": "shared_downstream", "severity": "high",
                          "title": "Shared wallets", "evidence": "...",
                          "transactions": [], "addresses": ["bc1qmule"],
                          "links": [{"case_id": other.id,
                                     "shared_addresses": ["bc1qmule"]}],
                      }])

    links = client.get(f"/cases/{case.id}/links").json()

    assert len(links) == 1
    assert links[0]["relationship"] == "shared_wallet"
    assert links[0]["shared_addresses"] == ["bc1qmule"]
    assert links[0]["reported_address"] == "bc1qother"


def test_a_repeat_report_outranks_a_shared_wallet(client, db_session):
    """The same address reported twice is a stronger claim than two traces
    passing through a wallet in common, and must not be downgraded to it."""
    other = _make_case(db_session, reported_address="bc1qsame", chain="bitcoin",
                        status="complete")
    case = _make_case(db_session, reported_address="bc1qsame", chain="bitcoin",
                       status="complete",
                      patterns=[{
                          "pattern": "shared_downstream", "severity": "high",
                          "title": "Shared", "evidence": "...", "transactions": [],
                          "addresses": [],
                          "links": [{"case_id": other.id,
                                     "shared_addresses": ["bc1qmule"]}],
                      }])
    for c in (other, case):
        db_session.add(TracedAddress(case_id=c.id, chain="bitcoin", address="bc1qsame"))
    db_session.commit()

    links = client.get(f"/cases/{case.id}/links").json()

    assert len(links) == 1                          # one case, not counted twice
    assert links[0]["relationship"] == "same_wallet"


def test_links_is_empty_when_nothing_connects(client, db_session):
    case = _make_case(db_session, reported_address="bc1qlonely", status="complete")
    assert client.get(f"/cases/{case.id}/links").json() == []


def test_links_404s_for_an_unknown_case(client):
    assert client.get("/cases/does-not-exist/links").status_code == 404


def test_links_shows_one_row_per_complaint_not_per_retrace(client, db_session):
    """Re-tracing a wallet produces a case row each time. Listing them all
    presents one complaint as a wall of corroboration."""
    address = "bc1qretraced"
    for _ in range(4):
        other = _make_case(db_session, reported_address=address, chain="bitcoin",
                           status="complete", created_by="investigator")
        db_session.add(TracedAddress(case_id=other.id, chain="bitcoin", address=address))
    case = _make_case(db_session, reported_address=address, chain="bitcoin",
                      status="complete", created_by="investigator")
    db_session.add(TracedAddress(case_id=case.id, chain="bitcoin", address=address))
    db_session.commit()

    links = client.get(f"/cases/{case.id}/links").json()

    assert len(links) == 1


def test_links_keeps_genuinely_separate_complainants(client, db_session):
    address = "bc1qsyndicate"
    for ref, who in (("FIR/1", "officer_a"), ("FIR/2", "officer_b")):
        other = _make_case(db_session, reported_address=address, chain="bitcoin",
                           status="complete", complaint_ref=ref, created_by=who)
        db_session.add(TracedAddress(case_id=other.id, chain="bitcoin", address=address))
    case = _make_case(db_session, reported_address=address, chain="bitcoin",
                      status="complete", created_by="officer_c")
    db_session.add(TracedAddress(case_id=case.id, chain="bitcoin", address=address))
    db_session.commit()

    links = client.get(f"/cases/{case.id}/links").json()

    assert len(links) == 2


def test_dedup_does_not_collapse_different_wallets(client, db_session):
    """The regression: keying on reference and filer alone merged every
    unreferenced case by the same investigator into one row, hiding the
    genuinely different wallets converging - the signal the panel exists
    for."""
    mine = _make_case(db_session, reported_address="bc1qmine", chain="bitcoin",
                      status="complete", created_by="investigator")
    links = []
    for addr in ("bc1qvictim1", "bc1qvictim2", "bc1qvictim3"):
        other = _make_case(db_session, reported_address=addr, chain="bitcoin",
                           status="complete", created_by="investigator")
        links.append({"case_id": other.id, "shared_addresses": ["bc1qmule"]})
    mine.patterns = [{
        "pattern": "shared_downstream", "severity": "high", "title": "Shared",
        "evidence": "...", "transactions": [], "addresses": ["bc1qmule"],
        "links": links,
    }]
    db_session.commit()

    result = client.get(f"/cases/{mine.id}/links").json()

    # Three separate victims, all unreferenced, all filed by one officer.
    assert len(result) == 3
    assert {r["reported_address"] for r in result} == {
        "bc1qvictim1", "bc1qvictim2", "bc1qvictim3"}
