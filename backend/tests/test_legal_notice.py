from app.models.orm import Case
from app.reports.legal_notice import build_legal_notice


def test_build_legal_notice_pdf():
    case = Case(
        id="test-case-uuid-1234",
        complaint_ref="NCRP/2026/0991",
        reported_address="0x1110000000000000000000000000000000000f",
        chain="ethereum",
        status="complete",
        risk_score=85.0,
        nearest_exchange={"name": "CoinDCX: Main Hot Wallet", "address": "0x708396c00d43a6d13e37039a5f7ec912d098e217", "hops": 2},
        graph={
            "nodes": [
                {"id": "ethereum:0x1110000000000000000000000000000000000f", "address": "0x1110000000000000000000000000000000000f"},
                {"id": "ethereum:0x708396c00d43a6d13e37039a5f7ec912d098e217", "address": "0x708396c00d43a6d13e37039a5f7ec912d098e217"},
            ],
            "edges": [
                {
                    "source": "ethereum:0x1110000000000000000000000000000000000f",
                    "target": "ethereum:0x708396c00d43a6d13e37039a5f7ec912d098e217",
                    "tx_hash": "0xaaaabbbbcccc1111222233334444555566667777888899990000",
                    "value": 1.75,
                    "timestamp": 1700000000,
                    "hop": 1,
                }
            ],
        },
        fraud_typology="investment_scam",
    )

    pdf_bytes = build_legal_notice(
        case=case,
        officer_name="Inspector R. Sharma",
        officer_designation="Cyber Crime Inspector",
        police_station="Cyberabad Cyber Crime PS",
        fir_number="FIR No. 204/2026",
        act_section="bnss_94",
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF-")
