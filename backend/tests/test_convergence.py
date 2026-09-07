"""Cross-case convergence analysis.

The behaviour under test is the one that distinguishes this system from a
block-explorer lookup: finding a wallet that collects from several
independently reported victims. The exclusion rules matter as much as the
detection - a convergence report that ranks Binance first is worse than
useless.
"""
from datetime import datetime, timezone

from app.intel.convergence import address_footprint, find_convergence_points
from app.models.orm import Case, CaseAddress


def _make_case(db, reported_address, **overrides):
    defaults = dict(
        reported_address=reported_address,
        chain="bitcoin",
        status="complete",
        risk_score=50.0,
        flags=[],
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    case = Case(**defaults)
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def _touch(db, case, address, hop=1, value_in=0.5, node_type=None, label_name=None):
    db.add(CaseAddress(
        case_id=case.id, chain=case.chain, address=address, hop=hop,
        value_in=value_in, node_type=node_type, label_name=label_name,
    ))
    db.commit()


def test_address_in_two_cases_is_a_convergence_point(db_session):
    case_a = _make_case(db_session, "bc1qvictimone")
    case_b = _make_case(db_session, "bc1qvictimtwo")
    _touch(db_session, case_a, "bc1qconsolidator", hop=2, value_in=0.4)
    _touch(db_session, case_b, "bc1qconsolidator", hop=3, value_in=0.6)

    points = find_convergence_points(db_session)

    assert len(points) == 1
    point = points[0]
    assert point.address == "bc1qconsolidator"
    assert point.case_count == 2
    assert point.total_value == 1.0
    assert point.min_hop == 2  # the closest either case got
    assert {c["case_id"] for c in point.cases} == {case_a.id, case_b.id}


def test_address_in_one_case_is_not_convergence(db_session):
    case = _make_case(db_session, "bc1qvictimone")
    _touch(db_session, case, "bc1qsomewhere")

    assert find_convergence_points(db_session) == []


def test_one_case_reaching_an_address_twice_counts_once(db_session):
    """A single trace can reach a wallet by several internal paths. That is
    one case's opinion, not corroboration from two victims."""
    case = _make_case(db_session, "bc1qvictimone")
    _touch(db_session, case, "bc1qhub", hop=2, value_in=0.3)
    _touch(db_session, case, "bc1qhub", hop=4, value_in=0.2)

    assert find_convergence_points(db_session) == []


def test_known_services_are_excluded(db_session):
    """Every victim's money reaches Binance. That is how exchanges work, and
    reporting it as a syndicate would bury the real signal."""
    case_a = _make_case(db_session, "bc1qvictimone")
    case_b = _make_case(db_session, "bc1qvictimtwo")
    for case in (case_a, case_b):
        _touch(db_session, case, "1NDyJtNTjmwk5xPNhjgAMu4HDHigtobu1s",
               node_type="exchange", label_name="Binance: Hot Wallet (BTC)")
        _touch(db_session, case, "bc1qtornado", node_type="mixer", label_name="A Mixer")
        _touch(db_session, case, "bc1qbridge", node_type="bridge", label_name="A Bridge")

    assert find_convergence_points(db_session) == []


def test_unlabeled_convergence_survives_alongside_excluded_services(db_session):
    """The NULL node_type must not be swallowed by the NOT IN filter - a SQL
    trap, since `NULL NOT IN (...)` is NULL rather than true."""
    case_a = _make_case(db_session, "bc1qvictimone")
    case_b = _make_case(db_session, "bc1qvictimtwo")
    for case in (case_a, case_b):
        _touch(db_session, case, "1NDyJtNTjmwk5xPNhjgAMu4HDHigtobu1s", node_type="exchange")
        _touch(db_session, case, "bc1qconsolidator", node_type=None)

    points = find_convergence_points(db_session)

    assert [p.address for p in points] == ["bc1qconsolidator"]


def test_ranked_by_case_count_then_value(db_session):
    cases = [_make_case(db_session, f"bc1qvictim{i}") for i in range(3)]
    for case in cases:
        _touch(db_session, case, "bc1qthreeway", value_in=0.1)
    for case in cases[:2]:
        _touch(db_session, case, "bc1qtwoway", value_in=5.0)

    points = find_convergence_points(db_session)

    assert [p.address for p in points] == ["bc1qthreeway", "bc1qtwoway"]
    assert points[0].case_count == 3


def test_min_cases_threshold_is_respected(db_session):
    cases = [_make_case(db_session, f"bc1qvictim{i}") for i in range(2)]
    for case in cases:
        _touch(db_session, case, "bc1qhub")

    assert len(find_convergence_points(db_session, min_cases=2)) == 1
    assert find_convergence_points(db_session, min_cases=3) == []


def test_chain_filter(db_session):
    btc_a = _make_case(db_session, "bc1qone", chain="bitcoin")
    btc_b = _make_case(db_session, "bc1qtwo", chain="bitcoin")
    _touch(db_session, btc_a, "bc1qhub")
    _touch(db_session, btc_b, "bc1qhub")

    assert len(find_convergence_points(db_session, chain="bitcoin")) == 1
    assert find_convergence_points(db_session, chain="ethereum") == []


def test_evidence_states_the_fact_and_its_limit(db_session):
    case_a = _make_case(db_session, "bc1qvictimone")
    case_b = _make_case(db_session, "bc1qvictimtwo")
    _touch(db_session, case_a, "bc1qconsolidator", hop=2)
    _touch(db_session, case_b, "bc1qconsolidator", hop=2)

    evidence = find_convergence_points(db_session)[0].evidence

    assert "2 independently reported cases" in evidence
    # The caveat is not optional: convergence is shared fund flow, and a
    # payment processor produces the same shape as a syndicate.
    assert "not proof of common control" in evidence


def test_address_footprint_spans_cases(db_session):
    case_a = _make_case(db_session, "bc1qhub")  # reported directly here
    case_b = _make_case(db_session, "bc1qvictimtwo")
    _touch(db_session, case_a, "bc1qhub", hop=0, value_in=0.0)
    _touch(db_session, case_b, "bc1qhub", hop=3, value_in=0.9)

    footprint = address_footprint(db_session, "bitcoin", "bc1qhub")

    assert footprint["case_count"] == 2
    assert footprint["reported_directly"] is True
    assert footprint["min_hop"] == 0
    assert footprint["total_value"] == 0.9


def test_address_footprint_unknown_address(db_session):
    assert address_footprint(db_session, "bitcoin", "bc1qnever") is None


# ── API surface ────────────────────────────────────────────────────────────

def test_convergence_endpoint(client, db_session):
    case_a = _make_case(db_session, "bc1qvictimone", fraud_typology="investment_scam")
    case_b = _make_case(db_session, "bc1qvictimtwo")
    _touch(db_session, case_a, "bc1qconsolidator", hop=2, value_in=0.4)
    _touch(db_session, case_b, "bc1qconsolidator", hop=2, value_in=0.6)

    body = client.get("/intel/convergence").json()

    assert body["count"] == 1
    point = body["convergence_points"][0]
    assert point["address"] == "bc1qconsolidator"
    assert point["case_count"] == 2
    assert len(point["cases"]) == 2
    assert {c["reported_address"] for c in point["cases"]} == {"bc1qvictimone", "bc1qvictimtwo"}


def test_convergence_endpoint_empty_explains_itself(client, db_session):
    """An empty result on a one-case database means "too few cases", and the
    response says so rather than leaving the reader to infer innocence."""
    body = client.get("/intel/convergence").json()

    assert body["count"] == 0
    assert "at least two completed traces" in body["note"]


def test_convergence_min_cases_below_two_rejected(client):
    # A threshold of 1 would report every address ever traced.
    assert client.get("/intel/convergence?min_cases=1").status_code == 422


def test_address_intel_endpoint(client, db_session):
    case = _make_case(db_session, "bc1qvictimone")
    _touch(db_session, case, "bc1qhub", hop=2, value_in=0.7)

    body = client.get("/intel/address/bitcoin/bc1qhub").json()

    assert body["case_count"] == 1
    assert body["total_value"] == 0.7
    assert body["cases"][0]["case_id"] == case.id


def test_address_intel_unknown_is_404_not_a_verdict(client, db_session):
    response = client.get("/intel/address/bitcoin/bc1qnever")

    assert response.status_code == 404
    # The wording must not imply the address is clean - only that we have
    # never traced it.
    assert "not about the address" in response.json()["detail"]


def test_intel_requires_authentication(unauthenticated_client):
    assert unauthenticated_client.get("/intel/convergence").status_code == 401


# ── shared downstream wallets, as a risk signal ───────────────────────────

def test_shared_downstream_finds_other_cases(db_session):
    from app.intel.convergence import shared_downstream_cases

    mine = _make_case(db_session, "bc1qme")
    theirs = _make_case(db_session, "bc1qthem")
    _touch(db_session, mine, "bc1qmule")
    _touch(db_session, theirs, "bc1qmule")

    shared = shared_downstream_cases(db_session, mine.id, "bitcoin")

    assert len(shared) == 1
    assert shared[0]["case_id"] == theirs.id
    assert shared[0]["shared_addresses"] == ["bc1qmule"]


def test_shared_downstream_ignores_services(db_session):
    """Every victim's money reaches an exchange, so sharing one is not
    corroboration - it would fire on essentially every pair of cases."""
    from app.intel.convergence import shared_downstream_cases

    mine = _make_case(db_session, "bc1qme")
    theirs = _make_case(db_session, "bc1qthem")
    for case in (mine, theirs):
        _touch(db_session, case, "1NDyBinanceHotWallet", node_type="exchange")

    assert shared_downstream_cases(db_session, mine.id, "bitcoin") == []


def test_shared_downstream_excludes_the_case_itself(db_session):
    from app.intel.convergence import shared_downstream_cases

    mine = _make_case(db_session, "bc1qme")
    _touch(db_session, mine, "bc1qmule", hop=1)
    _touch(db_session, mine, "bc1qmule", hop=3)  # reached twice in one trace

    assert shared_downstream_cases(db_session, mine.id, "bitcoin") == []


def test_shared_downstream_raises_the_risk_score():
    """The signal has to actually move the number, or building it changed
    nothing about how a case gets triaged."""
    from app.risk.rules import score_case

    without, _ = score_case(set(), None, 0, False, shared_downstream_count=0)
    with_shared, breakdown = score_case(set(), None, 0, False, shared_downstream_count=2)

    assert with_shared > without
    assert "shared_downstream" in breakdown
