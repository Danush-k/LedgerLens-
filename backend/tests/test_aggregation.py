from unittest.mock import MagicMock
from app.models.orm import Case
from app.tracer.aggregation import aggregate_case_graphs


def test_aggregate_case_graphs_merges_nodes_and_edges():
    case1 = MagicMock(spec=Case)
    case1.id = "c1"
    case1.graph = {
        "nodes": [
            {"id": "eth:0xa", "address": "0xa", "chain": "ethereum"},
            {"id": "eth:0xb", "address": "0xb", "chain": "ethereum"},
        ],
        "edges": [
            {"source": "eth:0xa", "target": "eth:0xb", "tx_hash": "0x111", "value": 1.0, "timestamp": 100},
        ],
    }

    case2 = MagicMock(spec=Case)
    case2.id = "c2"
    case2.graph = {
        "nodes": [
            {"id": "eth:0xb", "address": "0xb", "chain": "ethereum"},
            {"id": "eth:0xc", "address": "0xc", "chain": "ethereum"},
        ],
        "edges": [
            {"source": "eth:0xb", "target": "eth:0xc", "tx_hash": "0x222", "value": 1.0, "timestamp": 200},
        ],
    }

    db = MagicMock()
    db.query().filter().all.return_value = [case1, case2]

    res = aggregate_case_graphs(["c1", "c2"], db)

    assert res["case_count"] == 2
    assert len(res["nodes"]) == 3
    assert len(res["edges"]) == 2
    
    # 0xb appears in both cases -> should be flagged as is_shared
    shared_node = next(n for n in res["nodes"] if n["id"] == "eth:0xb")
    assert shared_node["is_shared"] is True
    assert set(shared_node["case_ids"]) == {"c1", "c2"}
