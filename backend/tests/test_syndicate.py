from unittest.mock import MagicMock
from app.models.orm import Case
from app.tracer.syndicate import find_syndicate_clusters


def test_find_syndicate_clusters_detects_shared_deposit_exchange():
    case1 = MagicMock(spec=Case)
    case1.id = "case-1"
    case1.status = "complete"
    case1.chain = "ethereum"
    case1.reported_address = "0xvictim1"
    case1.complaint_ref = "FIR/101"
    case1.risk_score = 80.0
    case1.created_at = None
    case1.nearest_exchange = {"name": "Binance", "address": "0xshared_deposit", "hops": 2}

    case2 = MagicMock(spec=Case)
    case2.id = "case-2"
    case2.status = "complete"
    case2.chain = "ethereum"
    case2.reported_address = "0xvictim2"
    case2.complaint_ref = "FIR/102"
    case2.risk_score = 85.0
    case2.created_at = None
    case2.nearest_exchange = {"name": "Binance", "address": "0xshared_deposit", "hops": 3}

    db = MagicMock()
    db.query().filter().all.return_value = [case1, case2]

    clusters = find_syndicate_clusters(db)

    assert len(clusters) >= 1
    deposit_cluster = next(c for c in clusters if c["target_address"] == "0xshared_deposit")
    assert deposit_cluster["linked_case_count"] == 2
    assert deposit_cluster["vasp_name"] == "Binance"
