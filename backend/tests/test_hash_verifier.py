from app.models.orm import Case
from app.reports.pdf import _snapshot_hash


def test_verify_case_hash_endpoint(client, db_session):
    case = Case(
        id="test-hash-uuid-9999",
        complaint_ref="NCRP/2026/TEST",
        reported_address="0x1110000000000000000000000000000000000f",
        chain="ethereum",
        status="complete",
        risk_score=75.0,
        nearest_exchange={"name": "Binance", "address": "0xeb2d2f1b8c558a40207669291fda468e50c8a0bb", "hops": 1},
        graph={"nodes": [], "edges": []},
    )
    db_session.add(case)
    db_session.commit()

    correct_hash = _snapshot_hash(case)

    # 1. Valid hash with case_id
    resp = client.post(
        "/cases/verify-hash",
        json={"hash": correct_hash, "case_id": case.id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is True
    assert data["status"] == "AUTHENTIC_RECORD"

    # 2. Valid hash without case_id (lookup by hash)
    resp_lookup = client.post(
        "/cases/verify-hash",
        json={"hash": correct_hash},
    )
    assert resp_lookup.status_code == 200
    assert resp_lookup.json()["verified"] is True
    assert resp_lookup.json()["case_id"] == case.id

    # 3. Tampered hash
    resp_tampered = client.post(
        "/cases/verify-hash",
        json={"hash": "0000000000000000000000000000000000000000000000000000000000000000", "case_id": case.id},
    )
    assert resp_tampered.status_code == 200
    assert resp_tampered.json()["verified"] is False
