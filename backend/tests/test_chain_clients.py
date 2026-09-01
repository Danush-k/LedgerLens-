import responses

from app.chain_clients.base import Chain
from app.chain_clients.bitcoin import BitcoinClient
from app.chain_clients.evm import EVMClient


@responses.activate
def test_evm_client_parses_outgoing_transfers_only():
    address = "0xAbC0000000000000000000000000000000000A"
    responses.add(
        responses.GET,
        "https://api.etherscan.io/api",
        json={
            "status": "1",
            "result": [
                {  # outgoing - should be included
                    "hash": "0x111",
                    "from": address.lower(),
                    "to": "0xdef0000000000000000000000000000000000b",
                    "value": str(2 * 10**18),
                    "timeStamp": "1700000000",
                    "isError": "0",
                },
                {  # incoming - should be excluded
                    "hash": "0x222",
                    "from": "0xdef0000000000000000000000000000000000b",
                    "to": address.lower(),
                    "value": str(1 * 10**18),
                    "timeStamp": "1700000100",
                    "isError": "0",
                },
                {  # failed tx - should be excluded
                    "hash": "0x333",
                    "from": address.lower(),
                    "to": "0xdef0000000000000000000000000000000000c",
                    "value": str(5 * 10**18),
                    "timeStamp": "1700000200",
                    "isError": "1",
                },
            ],
        },
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.etherscan.io/api",
        json={"status": "1", "result": []},
        status=200,
    )

    client = EVMClient(Chain.ETHEREUM)
    transfers = client.get_outgoing_transfers(address)

    assert len(transfers) == 1
    assert transfers[0].tx_hash == "0x111"
    assert transfers[0].value == 2.0
    assert transfers[0].to_address == "0xdef0000000000000000000000000000000000b"


@responses.activate
def test_bitcoin_client_skips_change_outputs():
    address = "bc1qexampleaddress"
    responses.add(
        responses.GET,
        f"https://blockstream.info/api/address/{address}/txs",
        json=[
            {
                "txid": "abc123",
                "vin": [{"prevout": {"scriptpubkey_address": address}}],
                "vout": [
                    {"scriptpubkey_address": "bc1qreceiver", "value": 50000},
                    {"scriptpubkey_address": address, "value": 10000},  # change - excluded
                ],
                "status": {"block_time": 1700000000},
            }
        ],
        status=200,
    )

    client = BitcoinClient()
    transfers = client.get_outgoing_transfers(address)

    assert len(transfers) == 1
    assert transfers[0].to_address == "bc1qreceiver"
    assert transfers[0].value == 0.0005
