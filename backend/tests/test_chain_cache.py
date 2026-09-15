"""Shared chain-data cache.

Convergence analysis makes repeat fetching structural: syndicate wallets
appear in many cases by definition, so the same addresses are walked again
on every complaint that touches them. The free explorers' rate limit is the
binding constraint on this system, so the behaviour that matters is not
just "it caches" but "it never fails a trace to serve a cache".
"""
from unittest.mock import MagicMock, patch

from app.chain_clients.base import Chain, ChainClient, Transfer
from app.chain_clients.cache import CachedChainClient


class CountingClient(ChainClient):
    chain = Chain.BITCOIN

    def __init__(self):
        self.calls = 0

    def get_outgoing_transfers(self, address):
        self.calls += 1
        return [Transfer(tx_hash="tx1", chain=Chain.BITCOIN, from_address=address,
                         to_address="bc1qother", value=1.5, timestamp=1_700_000_000)]

    def get_co_spent_addresses(self, address):
        return {"bc1qcosigner"}


def _fake_redis():
    store = {}
    conn = MagicMock()
    conn.get.side_effect = lambda k: store.get(k)
    conn.setex.side_effect = lambda k, ttl, v: store.__setitem__(k, v)
    return conn, store


def test_second_fetch_is_served_from_cache():
    inner = CountingClient()
    conn, _ = _fake_redis()

    with patch("app.chain_clients.cache._client", return_value=conn):
        cached = CachedChainClient(inner)
        first = cached.get_outgoing_transfers("bc1qwallet")
        second = cached.get_outgoing_transfers("bc1qwallet")

    assert inner.calls == 1                     # the explorer was hit once
    assert [t.tx_hash for t in first] == [t.tx_hash for t in second]
    assert second[0].value == 1.5


def test_cached_transfers_survive_the_round_trip_intact():
    """A cache that quietly changes values is worse than no cache - the
    amounts feed taint and every total in the report."""
    inner = CountingClient()
    conn, _ = _fake_redis()

    with patch("app.chain_clients.cache._client", return_value=conn):
        cached = CachedChainClient(inner)
        original = cached.get_outgoing_transfers("bc1qwallet")[0]
        restored = cached.get_outgoing_transfers("bc1qwallet")[0]

    assert restored == original                 # dataclass equality, field by field


def test_asset_is_preserved_through_the_cache():
    """Tron returns USDT, not the native coin. Losing the asset on a cache
    hit would make a USDT amount read as TRX."""
    class Tronish(ChainClient):
        chain = Chain.TRON

        def get_outgoing_transfers(self, address):
            return [Transfer(tx_hash="t", chain=Chain.TRON, from_address=address,
                             to_address="Tother", value=500.0,
                             timestamp=1_700_000_000, asset="USDT")]

    conn, _ = _fake_redis()
    with patch("app.chain_clients.cache._client", return_value=conn):
        cached = CachedChainClient(Tronish())
        cached.get_outgoing_transfers("Twallet")
        assert cached.get_outgoing_transfers("Twallet")[0].asset == "USDT"


def test_different_addresses_do_not_share_an_entry():
    inner = CountingClient()
    conn, _ = _fake_redis()

    with patch("app.chain_clients.cache._client", return_value=conn):
        cached = CachedChainClient(inner)
        cached.get_outgoing_transfers("bc1qone")
        cached.get_outgoing_transfers("bc1qtwo")

    assert inner.calls == 2


def test_chains_do_not_share_an_entry():
    """Two chains can hold the same address string. Colliding on it would
    return one chain's transfers for the other."""
    conn, store = _fake_redis()
    with patch("app.chain_clients.cache._client", return_value=conn):
        CachedChainClient(CountingClient()).get_outgoing_transfers("shared")
    keys = list(store)
    assert len(keys) == 1
    assert "bitcoin" in keys[0]


def test_works_with_redis_unavailable():
    """The cache is optional. If Redis is down the trace still runs."""
    inner = CountingClient()
    with patch("app.chain_clients.cache._client", return_value=None):
        cached = CachedChainClient(inner)
        assert len(cached.get_outgoing_transfers("bc1qwallet")) == 1
        assert len(cached.get_outgoing_transfers("bc1qwallet")) == 1
    assert inner.calls == 2  # no caching, but no failure either


def test_a_failing_redis_read_falls_through_to_the_explorer():
    inner = CountingClient()
    conn = MagicMock()
    conn.get.side_effect = RuntimeError("connection reset")

    with patch("app.chain_clients.cache._client", return_value=conn):
        result = CachedChainClient(inner).get_outgoing_transfers("bc1qwallet")

    assert len(result) == 1
    assert inner.calls == 1


def test_a_failing_redis_write_does_not_fail_the_trace():
    inner = CountingClient()
    conn = MagicMock()
    conn.get.return_value = None
    conn.setex.side_effect = RuntimeError("read-only replica")

    with patch("app.chain_clients.cache._client", return_value=conn):
        result = CachedChainClient(inner).get_outgoing_transfers("bc1qwallet")

    assert len(result) == 1


def test_co_spend_passes_through_to_the_wrapped_client():
    with patch("app.chain_clients.cache._client", return_value=None):
        assert CachedChainClient(CountingClient()).get_co_spent_addresses("x") == {"bc1qcosigner"}
