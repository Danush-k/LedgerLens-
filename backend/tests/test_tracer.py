from unittest.mock import patch

from app.chain_clients.base import Chain, ChainClient, Transfer
from app.tracer.bfs import trace_wallet

EXCHANGE_ADDR = "0xeb2d2f1b8c558a40207669291fda468e50c8a0bb"  # in the real seed set
MIXER_ADDR = "0x12d66f87a04a9e220743712ce6d9bb1b5616b8fc"  # in the real seed set
UNKNOWN_1 = "0xaaa0000000000000000000000000000000000a"
UNKNOWN_2 = "0xbbb0000000000000000000000000000000000b"


class FakeClient(ChainClient):
    """Deterministic fake standing in for a real chain API in tests."""

    chain = Chain.ETHEREUM

    def __init__(self, graph: dict[str, list[str]]):
        self.graph = graph

    def get_outgoing_transfers(self, address: str) -> list[Transfer]:
        destinations = self.graph.get(address.lower(), [])
        return [
            Transfer(
                tx_hash=f"tx-{address}-{i}",
                chain=Chain.ETHEREUM,
                from_address=address,
                to_address=dest,
                value=1.0,
                timestamp=1_700_000_000 + i * 100,
            )
            for i, dest in enumerate(destinations)
        ]


def test_trace_stops_branch_at_known_exchange():
    root = "0x1110000000000000000000000000000000000f"
    fake_graph = {root: [EXCHANGE_ADDR]}

    with patch("app.tracer.bfs.get_chain_client", return_value=FakeClient(fake_graph)):
        result = trace_wallet(Chain.ETHEREUM, root, hop_limit=5)

    assert result.nearest_exchange is not None
    assert result.nearest_exchange["address"] == EXCHANGE_ADDR
    assert result.nearest_exchange["hops"] == 1
    assert "no_exchange_found" not in result.flags

    # node/edge ids must use the plain chain value ("ethereum"), not the
    # enum's repr ("Chain.ETHEREUM") - regression check for str(enum) bugs
    root_uid = f"ethereum:{root}"
    assert root_uid in result.nodes
    assert result.nodes[root_uid]["chain"] == "ethereum"
    assert all(e["source"].startswith("ethereum:") for e in result.edges)


def test_trace_flags_mixer_and_keeps_going_via_other_branches():
    root = "0x2220000000000000000000000000000000000f"
    fake_graph = {
        root: [MIXER_ADDR, UNKNOWN_1],
        UNKNOWN_1: [EXCHANGE_ADDR],
    }

    with patch("app.tracer.bfs.get_chain_client", return_value=FakeClient(fake_graph)):
        result = trace_wallet(Chain.ETHEREUM, root, hop_limit=5)

    assert "mixer_detected" in result.flags
    assert result.nearest_exchange["hops"] == 2


def test_trace_respects_hop_limit_and_flags_unresolved():
    root = "0x3330000000000000000000000000000000000f"
    fake_graph = {root: [UNKNOWN_1], UNKNOWN_1: [UNKNOWN_2]}  # never reaches an exchange

    with patch("app.tracer.bfs.get_chain_client", return_value=FakeClient(fake_graph)):
        result = trace_wallet(Chain.ETHEREUM, root, hop_limit=1)

    assert result.nearest_exchange is None
    assert "no_exchange_found" in result.flags
    assert UNKNOWN_2 not in {n["address"] for n in result.nodes.values()}
