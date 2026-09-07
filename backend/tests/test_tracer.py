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


def test_exchange_attribution_carries_its_source():
    """An attribution without provenance is an assertion. The report has to
    be able to say on whose authority a wallet is called an exchange."""
    root = "0x1110000000000000000000000000000000000f"

    with patch("app.tracer.bfs.get_chain_client",
               return_value=FakeClient({root: [EXCHANGE_ADDR]})):
        result = trace_wallet(Chain.ETHEREUM, root, hop_limit=2)

    assert result.nearest_exchange is not None
    # The seed set records an origin for this label; it must survive the trace.
    assert result.nearest_exchange.get("source")

    node = next(n for n in result.nodes.values() if n["address"] == EXCHANGE_ADDR.lower())
    assert node["label_source"]


# ── concurrent level fetching ─────────────────────────────────────────────

def test_every_address_in_a_hop_is_processed():
    """The frontier is fetched concurrently but processed per address. An
    earlier version left the body outside the per-address loop, so only the
    last wallet of each hop was ever expanded - and single-address test
    graphs did not notice."""
    root = "0x1110000000000000000000000000000000000f"
    a = "0xaaa0000000000000000000000000000000000a"
    b = "0xbbb0000000000000000000000000000000000b"
    a_child = "0xccc0000000000000000000000000000000000c"
    b_child = "0xddd0000000000000000000000000000000000d"

    graph = {root: [a, b], a: [a_child], b: [b_child]}
    with patch("app.tracer.bfs.get_chain_client", return_value=FakeClient(graph)):
        result = trace_wallet(Chain.ETHEREUM, root, hop_limit=3)

    addresses = {n["address"] for n in result.nodes.values()}
    # Both branches of the fan-out must be expanded, not just one.
    assert a_child in addresses
    assert b_child in addresses


def test_concurrent_fetching_is_deterministic():
    """Two traces of the same wallet must produce the same graph. Fetching
    in parallel but mutating serially is what guarantees that."""
    root = "0x1110000000000000000000000000000000000f"
    graph = {
        root: [f"0x{i:040x}" for i in range(6)],
        "0x" + "0" * 39 + "1": [EXCHANGE_ADDR],
    }
    runs = []
    for _ in range(3):
        with patch("app.tracer.bfs.get_chain_client", return_value=FakeClient(graph)):
            r = trace_wallet(Chain.ETHEREUM, root, hop_limit=3)
        runs.append(sorted(n["address"] for n in r.nodes.values()))

    assert runs[0] == runs[1] == runs[2]


def test_a_failing_address_does_not_stop_its_siblings():
    """One dead fetch in a hop must leave the rest of that hop intact."""
    root = "0x1110000000000000000000000000000000000f"
    good = "0xaaa0000000000000000000000000000000000a"
    bad = "0xbbb0000000000000000000000000000000000b"

    class FlakyClient(FakeClient):
        def get_outgoing_transfers(self, address):
            if address == bad:
                raise TimeoutError("explorer timed out")
            return super().get_outgoing_transfers(address)

    graph = {root: [good, bad], good: [EXCHANGE_ADDR]}
    with patch("app.tracer.bfs.get_chain_client", return_value=FlakyClient(graph)):
        result = trace_wallet(Chain.ETHEREUM, root, hop_limit=3)

    assert result.nearest_exchange is not None          # the good branch resolved
    assert any(e["address"] == bad for e in result.fetch_errors)
    assert "partial_data" in result.flags               # and the gap is declared
