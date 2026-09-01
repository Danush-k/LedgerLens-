from unittest.mock import patch, MagicMock
from app.chain_clients.base import Chain, is_valid_address
from app.chain_clients.factory import get_chain_client
from app.chain_clients.tron import TronClient


def test_tron_address_validation():
    # Valid Tron Base58 addresses
    assert is_valid_address("TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t", Chain.TRON) is True
    assert is_valid_address("TKzxdWhmptNSLxuhx12C5B655555555555", "tron") is True
    
    # Invalid addresses
    assert is_valid_address("0x7a250d5630b4cf539739df2c5dacb4c659f2488d", Chain.TRON) is False
    assert is_valid_address("TShort", Chain.TRON) is False


def test_get_chain_client_returns_tron():
    client = get_chain_client(Chain.TRON)
    assert isinstance(client, TronClient)
    assert client.chain == Chain.TRON


@patch("app.chain_clients.tron.get")
def test_tron_client_get_outgoing_transfers(mock_get):
    mock_get.side_effect = [
        # TRC-20 response
        {
            "data": [
                {
                    "transaction_id": "tx_tron_101",
                    "from": "T111111111111111111111111111111111",
                    "to": "T222222222222222222222222222222222",
                    "value": "50000000",
                    "token_info": {"decimals": 6},
                    "block_timestamp": 1700000000000,
                }
            ]
        },
        # Native TRX response
        {"data": []},
    ]

    client = TronClient()
    transfers = client.get_outgoing_transfers("T111111111111111111111111111111111")
    assert len(transfers) >= 1
    t = transfers[0]
    assert t.tx_hash == "tx_tron_101"
    assert t.chain == Chain.TRON
    assert t.value == 50.0
