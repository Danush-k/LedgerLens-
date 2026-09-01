from app.risk.complaint_parser import parse_complaint_text


def test_parse_complaint_extracts_evm_wallets_and_tx():
    narrative = """
    I was defrauded of 2.5 ETH on Ethereum. The scammer asked me to send funds to
    0xeb2d2f1b8c558a40207669291fda468e50c8a0bb.
    The transaction hash is 0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d.
    Earlier I also sent INR 50,000 to UPI ID cyber_scammer@okaxis.
    Complaint reference NCRP/2026/HYD/88129.
    """
    result = parse_complaint_text(narrative)
    assert result["extracted_count"] >= 1
    addresses = [w["address"].lower() for w in result["wallets"]]
    assert "0xeb2d2f1b8c558a40207669291fda468e50c8a0bb".lower() in addresses
    assert "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d" in result["tx_hashes"]
    assert "cyber_scammer@okaxis" in result["upi_ids"]
    assert any("NCRP/2026/HYD/88129" in ref for ref in result["complaint_refs"])


def test_parse_complaint_extracts_bitcoin_and_tron():
    narrative = """
    Victim lost 0.75 BTC to wallet bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h and
    also deposited 5000 USDT on Tron address TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t.
    """
    result = parse_complaint_text(narrative)
    addresses = [w["address"] for w in result["wallets"]]
    assert "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h" in addresses
    assert "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t" in addresses
    assert any(w["chain"] == "bitcoin" for w in result["wallets"])
    assert any(w["chain"] == "tron" for w in result["wallets"])


def test_parse_empty_complaint():
    result = parse_complaint_text("")
    assert result["extracted_count"] == 0
    assert result["wallets"] == []
