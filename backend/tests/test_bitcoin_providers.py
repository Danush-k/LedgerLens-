"""Bitcoin provider failover.

Free explorers refuse service without warning, and being refused by one
says nothing about the others. What matters here is that a refusal becomes
a slower trace rather than a failed one, and that a provider's own response
shape is translated without changing any amount - these numbers become the
value column in an evidence report.
"""
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.chain_clients.bitcoin import (
    BitcoinClient, _read_blockchain_info, _providers,
)

ESPLORA_TX = {
    "txid": "a" * 64,
    "status": {"block_time": 1_700_000_000},
    "vin": [{"prevout": {"scriptpubkey_address": "bc1qsource", "value": 100_000}}],
    "vout": [{"scriptpubkey_address": "bc1qdest", "value": 90_000}],
}

BLOCKCHAIN_INFO_PAYLOAD = {
    "txs": [{
        "hash": "b" * 64,
        "time": 1_700_000_500,
        "inputs": [{"prev_out": {"addr": "bc1qsource", "value": 250_000}}],
        "out": [{"addr": "bc1qdest", "value": 240_000},
                {"addr": "bc1qchange", "value": 9_000}],
    }]
}


@pytest.fixture(autouse=True)
def _clear_provider_bench():
    """The bench is deliberately process-wide, so it leaks between tests
    unless cleared - one test's refusing provider would silently reorder
    the next test's providers."""
    import app.chain_clients.bitcoin as btc
    btc._benched.clear()
    yield
    btc._benched.clear()


def _response(payload):
    r = MagicMock()
    r.json.return_value = payload
    return r


# ── translation ───────────────────────────────────────────────────────────

def test_blockchain_info_is_translated_to_the_esplora_shape():
    with patch("app.chain_clients.bitcoin.get_with_retry",
               return_value=_response(BLOCKCHAIN_INFO_PAYLOAD)):
        txs = _read_blockchain_info(requests.Session(), "https://blockchain.info", "bc1qsource")

    assert len(txs) == 1
    tx = txs[0]
    assert tx["txid"] == "b" * 64
    assert tx["status"]["block_time"] == 1_700_000_500
    assert tx["vin"][0]["prevout"]["scriptpubkey_address"] == "bc1qsource"
    assert {o["scriptpubkey_address"] for o in tx["vout"]} == {"bc1qdest", "bc1qchange"}


def test_translation_preserves_satoshi_amounts_exactly():
    """Both APIs report satoshis. A unit slip here would silently rescale
    every amount in the evidence trail."""
    with patch("app.chain_clients.bitcoin.get_with_retry",
               return_value=_response(BLOCKCHAIN_INFO_PAYLOAD)):
        txs = _read_blockchain_info(requests.Session(), "https://blockchain.info", "bc1qsource")

    values = {o["scriptpubkey_address"]: o["value"] for o in txs[0]["vout"]}
    assert values["bc1qdest"] == 240_000
    assert values["bc1qchange"] == 9_000


def test_a_translated_transaction_parses_into_transfers():
    """End to end: the fallback's output must flow through the same parser
    the primary provider's does, and produce BTC-denominated values."""
    client = BitcoinClient()
    with patch("app.chain_clients.bitcoin.get_with_retry",
               return_value=_response(BLOCKCHAIN_INFO_PAYLOAD)):
        client._providers = [("blockchain.info", "https://blockchain.info",
                              _read_blockchain_info)]
        transfers = client.get_outgoing_transfers("bc1qsource")

    by_dest = {t.to_address: t for t in transfers}
    assert by_dest["bc1qdest"].value == pytest.approx(0.0024)
    assert by_dest["bc1qdest"].tx_hash == "b" * 64


# ── failover ──────────────────────────────────────────────────────────────

def test_a_refusing_provider_falls_through_to_the_next():
    calls = []

    def first(session, base, address):
        calls.append("first")
        raise requests.HTTPError("429 Too Many Requests")

    def second(session, base, address):
        calls.append("second")
        return [ESPLORA_TX]

    client = BitcoinClient()
    client._providers = [("a", "https://a", first), ("b", "https://b", second)]

    assert len(client._get_txs("bc1qsource")) == 1
    assert calls == ["first", "second"]


def test_the_working_provider_is_preferred_afterwards():
    """A provider throttling us keeps throttling us. Starting every fetch
    back at the failing one pays its timeout on every single address."""
    attempts = {"a": 0, "b": 0}

    def failing(session, base, address):
        attempts["a"] += 1
        raise requests.ConnectionError("connection reset by peer")

    def working(session, base, address):
        attempts["b"] += 1
        return [ESPLORA_TX]

    client = BitcoinClient()
    client._providers = [("a", "https://a", failing), ("b", "https://b", working)]

    client._get_txs("bc1qone")
    client._get_txs("bc1qtwo")
    client._get_txs("bc1qthree")

    assert attempts["a"] == 1        # tried once, then stepped over
    assert attempts["b"] == 3


def test_every_provider_failing_names_them_all():
    """Only when all of them refuse is this a data availability problem -
    and the error has to be specific enough to tell that apart from a
    wallet with no history."""
    def dead(session, base, address):
        raise requests.ConnectionError("reset")

    client = BitcoinClient()
    client._providers = [("alpha", "https://a", dead), ("beta", "https://b", dead)]

    with pytest.raises(RuntimeError) as exc:
        client._get_txs("bc1qsource")

    assert "alpha" in str(exc.value)
    assert "beta" in str(exc.value)


def test_a_cached_address_is_not_refetched():
    calls = []

    def counting(session, base, address):
        calls.append(address)
        return [ESPLORA_TX]

    client = BitcoinClient()
    client._providers = [("a", "https://a", counting)]
    client._get_txs("bc1qsource")
    client._get_txs("bc1qsource")

    assert len(calls) == 1


# ── configuration ─────────────────────────────────────────────────────────

def test_fallbacks_exist_beyond_the_primary():
    """The whole point is having somewhere else to ask."""
    assert len(_providers()) >= 2


def test_providers_are_distinct_hosts():
    urls = [url for _, url, _ in _providers()]
    assert len(urls) == len(set(urls))


# ── benching a refusing provider ──────────────────────────────────────────

def test_a_refusing_provider_is_benched_for_later_addresses():
    """Throttling is applied to the caller, not the query - a provider that
    just refused will refuse the next address too. Without benching, every
    address in a wide hop pays that provider's timeout again, which turns a
    slightly slower trace into one that crawls."""
    import app.chain_clients.bitcoin as btc

    attempts = {"bad": 0, "good": 0}

    def bad(session, base, address):
        attempts["bad"] += 1
        raise requests.ConnectionError("reset")

    def good(session, base, address):
        attempts["good"] += 1
        return [ESPLORA_TX]

    # Fresh clients, as separate traces would use - the bench is what has to
    # carry the knowledge across them, not the per-client preference.
    for addr in ("bc1qone", "bc1qtwo", "bc1qthree", "bc1qfour"):
        client = BitcoinClient()
        client._providers = [("bad", "https://bad", bad), ("good", "https://good", good)]
        client._get_txs(addr)

    assert attempts["bad"] == 1     # tried once, benched thereafter
    assert attempts["good"] == 4


def test_all_providers_benched_still_attempts_one():
    """If everything is benched we still have to ask somebody - benching
    reorders, it does not remove."""
    import app.chain_clients.bitcoin as btc
    btc._bench("a")
    btc._bench("b")

    calls = []

    def works(session, base, address):
        calls.append(base)
        return [ESPLORA_TX]

    client = BitcoinClient()
    client._providers = [("a", "https://a", works), ("b", "https://b", works)]

    assert len(client._get_txs("bc1qsource")) == 1
    assert len(calls) == 1


def test_bench_expires():
    import app.chain_clients.bitcoin as btc
    btc._benched["x"] = 0.0  # already in the past

    assert not btc._is_benched("x")
