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


def test_shared_funder_clusters_groups_fan_out_recipients():
    nodes = {
        "eth:0xsource": {"address": "0xsource"},
        "eth:0xb": {"address": "0xb"},
        "eth:0xc": {"address": "0xc"},
        "eth:0xd": {"address": "0xd"},  # different funder, shouldn't cluster with b/c
    }
    edges = [
        {"source": "eth:0xsource", "target": "eth:0xb"},
        {"source": "eth:0xsource", "target": "eth:0xc"},
        {"source": "eth:0xb", "target": "eth:0xd"},  # single recipient, not a cluster
    ]

    clusters = shared_funder_clusters(nodes, edges)

    assert len(clusters) == 1
    assert clusters[0]["type"] == "shared_funder"
    assert clusters[0]["addresses"] == ["0xb", "0xc"]


def test_shared_funder_clusters_ignores_single_recipient_sources():
    nodes = {"a": {"address": "0xa"}, "b": {"address": "0xb"}}
    edges = [{"source": "a", "target": "b"}]

    assert shared_funder_clusters(nodes, edges) == []
