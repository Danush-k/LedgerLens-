"""End-to-end wiring: worker task -> address footprint -> convergence.

The unit tests in test_convergence.py insert CaseAddress rows directly, so
they prove the analysis but not that anything ever writes those rows. This
covers the join between them: two traces run through the real worker task,
and the wallet they share has to surface as a convergence point.

The chain client is stubbed rather than live. Convergence is deterministic
logic and should not be gated on a third-party rate limit - the live
provider is exercised by running the app, not by the test suite.
"""
from unittest.mock import patch

from app.chain_clients.base import Chain, ChainClient, Transfer
from app.intel.convergence import find_convergence_points
from app.models.orm import Case, CaseAddress

EXCHANGE_ADDR = "0xeb2d2f1b8c558a40207669291fda468e50c8a0bb"  # real seed label
VICTIM_A = "0xaaa0000000000000000000000000000000000a"
VICTIM_B = "0xbbb0000000000000000000000000000000000b"
MULE = "0xccc0000000000000000000000000000000000c"        # the shared wallet
A_ONLY = "0xddd0000000000000000000000000000000000d"


class FakeClient(ChainClient):
    chain = Chain.ETHEREUM

    def __init__(self, graph):
        self.graph = graph

    def get_outgoing_transfers(self, address):
        return [
            Transfer(tx_hash=f"tx-{address}-{i}", chain=Chain.ETHEREUM,
                     from_address=address, to_address=dest, value=1.0,
                     timestamp=1_700_000_000 + i * 100)
            for i, dest in enumerate(self.graph.get(address.lower(), []))
        ]

    def get_co_spent_addresses(self, address):
        return set()


# Two unrelated complaints. Victim A's funds pass *through* the mule wallet;
# victim B pays it directly. Neither case file alone shows the connection.
SHARED_GRAPH = {
    VICTIM_A: [MULE, A_ONLY],
    VICTIM_B: [MULE],
    MULE: [EXCHANGE_ADDR],
}


def _run_case(db, reported_address, complaint_ref):
    from app.worker.tasks import trace_wallet_task

    case = Case(reported_address=reported_address, chain="ethereum",
                status="queued", hop_limit=2, complaint_ref=complaint_ref)
    db.add(case)
    db.commit()
    db.refresh(case)

    with patch("app.tracer.bfs.get_chain_client", return_value=FakeClient(SHARED_GRAPH)), \
         patch("app.worker.tasks.SessionLocal", return_value=db), \
         patch.object(db, "close", lambda: None):
        trace_wallet_task(case.id)

    db.refresh(case)
    return case


def test_worker_records_the_full_address_footprint(db_session):
    case = _run_case(db_session, VICTIM_A, "NCRP-1")

    assert case.status == "complete"
    rows = db_session.query(CaseAddress).filter(CaseAddress.case_id == case.id).all()
    addresses = {r.address for r in rows}

    # Not just the reported wallet - every address the trace walked.
    assert VICTIM_A in addresses
    assert MULE in addresses
    assert EXCHANGE_ADDR in addresses
    assert len(addresses) > 1

    root = next(r for r in rows if r.address == VICTIM_A)
    assert root.hop == 0
    exchange_row = next(r for r in rows if r.address == EXCHANGE_ADDR)
    assert exchange_row.node_type == "exchange"  # denormalized for the exclusion filter


def test_two_independent_cases_converge_on_the_shared_wallet(db_session):
    case_a = _run_case(db_session, VICTIM_A, "NCRP-1")
    case_b = _run_case(db_session, VICTIM_B, "NCRP-2")
    assert case_a.status == case_b.status == "complete"

    points = find_convergence_points(db_session)
    found = {p.address: p for p in points}

    # The mule wallet is in both traces and is not a known service.
    assert MULE in found
    assert found[MULE].case_count == 2
    assert {c["complaint_ref"] for c in found[MULE].cases} == {"NCRP-1", "NCRP-2"}

    # The exchange is in both traces too, and must NOT be reported - every
    # victim's money reaches an exchange; that is not a syndicate.
    assert EXCHANGE_ADDR not in found

    # A wallet only case A touched is not convergence.
    assert A_ONLY not in found


def test_rerunning_a_case_does_not_double_count_it(db_session):
    """A re-traced case must replace its footprint, not accumulate a second
    copy - otherwise one case re-run twice would look like two victims."""
    case_a = _run_case(db_session, VICTIM_A, "NCRP-1")
    _run_case(db_session, VICTIM_B, "NCRP-2")

    from app.worker.tasks import trace_wallet_task
    with patch("app.tracer.bfs.get_chain_client", return_value=FakeClient(SHARED_GRAPH)), \
         patch("app.worker.tasks.SessionLocal", return_value=db_session), \
         patch.object(db_session, "close", lambda: None):
        trace_wallet_task(case_a.id)  # same case, traced again

    rows = db_session.query(CaseAddress).filter(
        CaseAddress.case_id == case_a.id, CaseAddress.address == MULE).all()
    assert len(rows) == 1

    assert next(p for p in find_convergence_points(db_session)
                if p.address == MULE).case_count == 2
