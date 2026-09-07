from unittest.mock import MagicMock
from app.chain_clients.base import Chain
from app.tracer.clustering import common_input_clusters, shared_funder_clusters


def test_common_input_clusters_uses_co_spent_addresses():
    client = MagicMock()
    client.chain = Chain.BITCOIN
    client.get_co_spent_addresses.side_effect = lambda addr: {"addrB", "addrC"} if addr == "addrA" else set()

    clusters = common_input_clusters(client, {"addrA", "addrB"})

    assert len(clusters) == 1
    assert clusters[0]["type"] == "common_input"
    assert clusters[0]["addresses"] == ["addrA", "addrB", "addrC"]


def test_common_input_clusters_empty_when_no_co_spends():
    client = MagicMock()
    client.chain = Chain.BITCOIN
    client.get_co_spent_addresses.return_value = set()

    assert common_input_clusters(client, {"addrA"}) == []


def test_shared_funder_clusters_groups_a_real_distribution():
    nodes = {f"eth:0x{c}": {"address": f"0x{c}"} for c in "sbcdef"}
    edges = [{"source": "eth:0xs", "target": f"eth:0x{c}"} for c in "bcde"]
    edges.append({"source": "eth:0xb", "target": "eth:0xf"})  # single recipient

    clusters = shared_funder_clusters(nodes, edges)

    assert len(clusters) == 1
    assert clusters[0]["type"] == "shared_funder"
    assert clusters[0]["addresses"] == ["0xb", "0xc", "0xd", "0xe"]


def test_a_wallet_paying_two_others_is_not_a_cluster():
    """One wallet paying two others is an ordinary transaction, not a
    discovery. At that size the "cluster" is the graph edge restated, and
    every fan-out in a trace produces one - which buried the findings that
    actually needed a decision under boxes that said nothing."""
    nodes = {
        "eth:0xsource": {"address": "0xsource"},
        "eth:0xb": {"address": "0xb"},
        "eth:0xc": {"address": "0xc"},
    }
    edges = [
        {"source": "eth:0xsource", "target": "eth:0xb"},
        {"source": "eth:0xsource", "target": "eth:0xc"},
    ]

    assert shared_funder_clusters(nodes, edges) == []


def test_shared_funder_note_does_not_claim_ownership():
    """These are shown beside common-input-ownership clusters, which do
    establish a shared key holder. Being paid by the same wallet does not,
    and the note has to say so or the two read as the same kind of claim."""
    nodes = {f"eth:0x{c}": {"address": f"0x{c}"} for c in "sbcde"}
    edges = [{"source": "eth:0xs", "target": f"eth:0x{c}"} for c in "bcde"]

    note = shared_funder_clusters(nodes, edges)[0]["note"]

    assert "does not establish" in note
    assert "owner" in note


def test_shared_funder_clusters_ignores_single_recipient_sources():
    nodes = {"a": {"address": "0xa"}, "b": {"address": "0xb"}}
    edges = [{"source": "a", "target": "b"}]

    assert shared_funder_clusters(nodes, edges) == []


def test_co_spend_failure_does_not_sink_the_trace():
    """A provider timeout during clustering must not discard a completed trace.

    Clustering makes one network call per traced address, after the trace
    itself has already succeeded. Letting one of those failures propagate
    would mark a fully-traced case as failed and persist nothing - which is
    exactly what a rate-limited provider caused before this was isolated.
    """
    class FlakyClient:
        chain = Chain.BITCOIN

        def get_co_spent_addresses(self, address):
            if address == "bc1qflaky":
                raise TimeoutError("Read timed out.")
            return {"bc1qcosigner"}

    clusters = common_input_clusters(FlakyClient(), {"bc1qflaky", "bc1qgood"})

    # The healthy address still yields its cluster; the failing one is skipped.
    assert len(clusters) == 1
    assert "bc1qgood" in clusters[0]["addresses"]


def test_consolidation_sweeps_are_not_treated_as_one_wallet_set():
    """An exchange gathering thousands of deposit addresses into one
    transaction does technically satisfy common-input-ownership - it holds
    all those keys - but the owner it identifies is the exchange. Merging on
    it chains unrelated customers into one entity, which is how this
    heuristic manufactures a syndicate out of a cold-storage routine."""
    from app.chain_clients.bitcoin import MAX_COSPEND_INPUTS, BitcoinClient

    sweep_inputs = [{"prevout": {"scriptpubkey_address": f"bc1qcustomer{i}"}}
                    for i in range(MAX_COSPEND_INPUTS + 10)]
    sweep_inputs.append({"prevout": {"scriptpubkey_address": "bc1qme"}})
    normal_inputs = [{"prevout": {"scriptpubkey_address": "bc1qme"}},
                     {"prevout": {"scriptpubkey_address": "bc1qmyother"}}]

    client = BitcoinClient()
    client._get_txs = lambda _addr: [{"vin": sweep_inputs}, {"vin": normal_inputs}]

    co_spent = client.get_co_spent_addresses("bc1qme")

    # The genuine two-input co-spend still merges.
    assert co_spent == {"bc1qmyother"}
