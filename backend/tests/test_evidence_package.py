import zipfile
import io
from unittest.mock import MagicMock
from app.models.orm import Case
from app.reports.evidence_package import generate_evidence_zip


def test_generate_evidence_zip_creates_valid_archive():
    case = MagicMock(spec=Case)
    case.id = "test-case-123"
    case.reported_address = "0xeb2d2f1b8c558a40207669291fda468e50c8a0bb"
    case.chain = "ethereum"
    case.complaint_ref = "NCRP/2026/099"
    case.narrative = "Sample investment fraud narrative"
    case.created_by = "admin"
    case.risk_score = 75.0
    case.fraud_typology = "phishing"
    case.flags = ["no_exchange_found"]
    case.nearest_exchange = None
    case.recommended_action = "Monitor for further activity"
    case.graph = {"nodes": [{"id": "eth:0xeb2d2f1b8c558a40207669291fda468e50c8a0bb"}], "edges": []}
    case.created_at = None
    case.completed_at = None

    zip_bytes = generate_evidence_zip(
        case=case,
        officer_name="Inspector V. Sharma",
        officer_designation="Senior Cyber Crime Officer",
        police_station="Cyber Police Station Central",
        fir_number="FIR No. 99/2026",
    )

    assert zip_bytes is not None
    assert len(zip_bytes) > 0

    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    file_names = zf.namelist()

    assert any(fn.endswith(".pdf") for fn in file_names)
    assert any(fn.endswith(".json") for fn in file_names)
    assert any(fn.endswith(".txt") for fn in file_names)
