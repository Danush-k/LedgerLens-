"""Proportional value tracking (haircut method).

"This wallet is connected to the victim" is weak: in a fan-out, dozens of
wallets are connected and most hold almost nothing of the victim's money.
Taint answers the question that actually matters for a seizure request -
how much of *this* wallet is attributable to *this* victim.
"""
from unittest.mock import patch

from app.chain_clients.base import Chain, ChainClient, Transfer
from app.tracer.bfs import trace_wallet

ROOT = "0x1110000000000000000000000000000000000f"
MID = "0xaaa0000000000000000000000000000000000a"
LEAF_1 = "0xbbb0000000000000000000000000000000000b"
LEAF_2 = "0xccc0000000000000000000000000000000000c"


class ValuedClient(ChainClient):
    """A fake whose transfer values matter, unlike the flat-1.0 fake used
    for topology tests."""

    chain = Chain.ETHEREUM

    def __init__(self, graph: dict[str, list[tuple[str, float]]]):
        self.graph = graph

    def get_outgoing_transfers(self, address):
        return [
            Transfer(tx_hash=f"tx-{address}-{i}", chain=Chain.ETHEREUM,
                     from_address=address, to_address=dest, value=value,
                     timestamp=1_700_000_000 + i * 60)
            for i, (dest, value) in enumerate(self.graph.get(address.lower(), []))
        ]


def _trace(graph, hop_limit=5):
    with patch("app.tracer.bfs.get_chain_client", return_value=ValuedClient(graph)):
        return trace_wallet(Chain.ETHEREUM, ROOT, hop_limit=hop_limit)


def test_reported_wallet_is_fully_tainted():
    result = _trace({ROOT: [(MID, 1.0)]})
    root = next(n for n in result.nodes.values() if n["hop"] == 0)

    assert root["taint_ratio"] == 1.0


def test_direct_transfer_carries_full_taint():
    """Everything leaving the reported wallet is victim money by definition."""
    result = _trace({ROOT: [(MID, 2.0)]})
    mid = next(n for n in result.nodes.values() if n["address"] == MID)

    assert mid["tainted_value"] == 2.0
    assert mid["taint_ratio"] == 1.0


def test_taint_is_split_proportionally_across_a_fan_out():
    """Splitting funds does not launder them - it divides the taint."""
    result = _trace({ROOT: [(LEAF_1, 3.0), (LEAF_2, 1.0)]})
    by_addr = {n["address"]: n for n in result.nodes.values()}

    assert by_addr[LEAF_1]["tainted_value"] == 3.0
    assert by_addr[LEAF_2]["tainted_value"] == 1.0
    # Conservation: nothing is created or lost by splitting.
    assert by_addr[LEAF_1]["tainted_value"] + by_addr[LEAF_2]["tainted_value"] == 4.0


def test_commingling_dilutes_taint_downstream():
    """The core of the haircut method. MID receives 1.0 of victim funds but
    moves 10.0 in total, so only a tenth of what it forwards is the
    victim's - the rest came from elsewhere."""
    graph = {
        ROOT: [(MID, 1.0)],
        MID: [(LEAF_1, 10.0)],
    }
    result = _trace(graph)
    by_addr = {n["address"]: n for n in result.nodes.values()}

    assert by_addr[MID]["tainted_value"] == 1.0
    # 10.0 forwarded, only 1.0 of it the victim's -> 10%.
    assert by_addr[LEAF_1]["tainted_value"] == 1.0
    assert by_addr[LEAF_1]["taint_ratio"] == 0.1


def test_taint_never_exceeds_what_arrived():
    """A wallet cannot forward more victim funds than reached it, however
    little of its own balance it moves."""
    graph = {
        ROOT: [(MID, 5.0)],
        MID: [(LEAF_1, 0.5)],  # retains most of it
    }
    result = _trace(graph)
    by_addr = {n["address"]: n for n in result.nodes.values()}

    assert by_addr[LEAF_1]["tainted_value"] == 0.5
    assert by_addr[LEAF_1]["taint_ratio"] == 1.0  # all of what moved was tainted


def test_edges_carry_their_tainted_share():
    result = _trace({ROOT: [(LEAF_1, 3.0), (LEAF_2, 1.0)]})

    for edge in result.edges:
        assert edge["tainted_value"] == edge["value"]  # straight from the root


def test_every_node_has_a_ratio_including_untraversed_leaves():
    """Leaves are never popped from the queue, so the finalizer has to give
    them a ratio or the UI shows 0% for wallets holding victim funds."""
    result = _trace({ROOT: [(MID, 1.0)], MID: [(LEAF_1, 1.0)]}, hop_limit=1)

    for node in result.nodes.values():
        assert "taint_ratio" in node
        assert 0.0 <= node["taint_ratio"] <= 1.0
