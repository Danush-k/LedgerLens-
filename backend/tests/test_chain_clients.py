import pytest
import responses

from app.chain_clients.base import Chain
from app.chain_clients.bitcoin import BitcoinClient
from app.chain_clients.evm import EVMClient

# The real client calls Etherscan's V2 endpoint (one host, a chainid param
# selects the network) - a mock against the old V1 host would silently
# never match, and with the pre-fix client that produced a passing test for
# the wrong reason: a swallowed connection error and an empty transfer
# list, which is indistinguishable from "this wallet has no history".
ETHERSCAN_V2 = "https://api.etherscan.io/v2/api"


@responses.activate
def test_evm_client_parses_outgoing_transfers_only():
    address = "0xAbC0000000000000000000000000000000000A"
    responses.add(
        responses.GET,
        ETHERSCAN_V2,
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
        ETHERSCAN_V2,
        json={"status": "1", "result": []},
        status=200,
    )

    client = EVMClient(Chain.ETHEREUM)
    transfers = client.get_outgoing_transfers(address)

    assert len(transfers) == 1
    assert transfers[0].tx_hash == "0x111"
    assert transfers[0].value == 2.0
    assert transfers[0].to_address == "0xdef0000000000000000000000000000000000b"


# ── an API-level failure must never be read as "this wallet sent nothing" ──
# Etherscan reports a missing/invalid API key, a rate limit, and a wallet
# with a genuinely empty history the same way at the transport level: HTTP
# 200, `status: "0"`. The only way to tell a real failure apart from a real
# empty wallet is that a failure's `result` is an error string, not a list.
# This is precisely the bug that made an EVM trace with no working API key
# silently report every wallet as clean, regardless of its real activity.

@responses.activate
def test_an_invalid_api_key_is_raised_not_swallowed():
    address = "0xAbC0000000000000000000000000000000000A"
    responses.add(
        responses.GET, ETHERSCAN_V2,
        json={"status": "0", "message": "NOTOK", "result": "Invalid API Key (#err2)"},
        status=200,
    )

    client = EVMClient(Chain.ETHEREUM)
    with pytest.raises(RuntimeError, match="Invalid API Key"):
        client.get_outgoing_transfers(address)


@responses.activate
def test_a_missing_api_key_is_raised_not_swallowed():
    address = "0xAbC0000000000000000000000000000000000A"
    responses.add(
        responses.GET, ETHERSCAN_V2,
        json={"status": "0", "message": "NOTOK", "result": "Missing/Invalid API Key"},
        status=200,
    )

    client = EVMClient(Chain.ETHEREUM)
    with pytest.raises(RuntimeError, match="Missing/Invalid API Key"):
        client.get_outgoing_transfers(address)


@responses.activate
def test_a_rate_limit_is_still_raised_and_benches_the_key():
    address = "0xAbC0000000000000000000000000000000000A"
    responses.add(
        responses.GET, ETHERSCAN_V2,
        json={"status": "0", "message": "NOTOK", "result": "Max rate limit reached"},
        status=200,
    )

    client = EVMClient(Chain.ETHEREUM)
    with pytest.raises(RuntimeError, match="rate limit"):
        client.get_outgoing_transfers(address)


@responses.activate
def test_a_genuinely_empty_wallet_is_not_mistaken_for_a_failure():
    """The one case that must NOT raise: status "0" with an actual empty
    list is Etherscan's normal way of saying a wallet has no history."""
    address = "0xAbC0000000000000000000000000000000000A"
    responses.add(
        responses.GET, ETHERSCAN_V2,
        json={"status": "0", "message": "No transactions found", "result": []},
        status=200,
    )
    responses.add(
        responses.GET, ETHERSCAN_V2,
        json={"status": "0", "message": "No transactions found", "result": []},
        status=200,
    )

    client = EVMClient(Chain.ETHEREUM)
    assert client.get_outgoing_transfers(address) == []


@responses.activate
def test_a_token_transfer_failure_does_not_discard_native_transfers_already_found():
    """Native transfers are the primary, must-be-honest signal; a token
    fetch failing on top of a successful native fetch is a smaller,
    tolerable gap and must not throw away the native transfers in hand."""
    address = "0xAbC0000000000000000000000000000000000A"
    responses.add(
        responses.GET, ETHERSCAN_V2,
        json={"status": "1", "result": [{
            "hash": "0x111", "from": address.lower(),
            "to": "0xdef0000000000000000000000000000000000b",
            "value": str(2 * 10**18), "timeStamp": "1700000000", "isError": "0",
        }]},
        status=200,
    )
    responses.add(
        responses.GET, ETHERSCAN_V2,
        json={"status": "0", "message": "NOTOK", "result": "Invalid API Key (#err2)"},
        status=200,
    )

    client = EVMClient(Chain.ETHEREUM)
    transfers = client.get_outgoing_transfers(address)

    assert len(transfers) == 1
    assert transfers[0].tx_hash == "0x111"


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
