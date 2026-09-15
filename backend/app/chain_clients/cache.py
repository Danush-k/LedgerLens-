"""Redis-backed cache for chain data, shared across traces and workers.

Each client already caches within a single trace, but that cache dies with
the object. Convergence analysis makes the repeat-fetch problem structural
rather than incidental: syndicate wallets appear in many cases by
definition, so the same addresses get walked again on every new complaint
that touches them. Re-fetching them burns the free explorers' rate limit,
which is the binding constraint on this system - traces in development
failed repeatedly because the provider stopped answering.

Degrades to a straight pass-through when Redis is unavailable. A cache that
takes the application down when it is missing is worse than no cache.
"""
import json
import logging

from app.chain_clients.base import Chain, ChainClient, Transfer
from app.config import get_settings

logger = logging.getLogger(__name__)

# An address's recent history changes slowly relative to an investigation.
# An hour keeps a multi-case tracing session off the rate limiter while
# staying short enough that a re-trace picks up same-day movement.
DEFAULT_TTL_SECONDS = 3600

_redis = None
_redis_checked = False


def _client():
    """Lazily connect, once, and remember failure so every cache miss does
    not retry a dead socket."""
    global _redis, _redis_checked
    if _redis_checked:
        return _redis
    _redis_checked = True
    try:
        import redis

        conn = redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=1,
                                    socket_timeout=1)
        conn.ping()
        _redis = conn
    except Exception as exc:  # noqa: BLE001 - caching is optional by design
        logger.info(f"Chain cache disabled, Redis unavailable: {exc}")
        _redis = None
    return _redis


def _key(chain: str, address: str) -> str:
    return f"chaincache:v1:{chain}:{address}"


def _encode(transfers: list[Transfer]) -> str:
    return json.dumps([
        {
            "tx_hash": t.tx_hash, "chain": t.chain.value,
            "from_address": t.from_address, "to_address": t.to_address,
            "value": t.value, "timestamp": t.timestamp, "asset": t.asset,
        }
        for t in transfers
    ])


def _decode(raw: str) -> list[Transfer]:
    return [
        Transfer(
            tx_hash=d["tx_hash"], chain=Chain(d["chain"]),
            from_address=d["from_address"], to_address=d["to_address"],
            value=d["value"], timestamp=d["timestamp"], asset=d.get("asset"),
        )
        for d in json.loads(raw)
    ]


class CachedChainClient(ChainClient):
    """Wraps any client, serving outgoing transfers from Redis when present.

    Only `get_outgoing_transfers` is cached. Co-spend lookups reuse the
    wrapped client's own per-trace cache and are cheap by comparison, so
    caching them across traces would add invalidation risk for little gain.
    """

    def __init__(self, inner: ChainClient, ttl: int = DEFAULT_TTL_SECONDS):
        self._inner = inner
        self._ttl = ttl
        self.chain = inner.chain

    def get_outgoing_transfers(self, address: str) -> list[Transfer]:
        conn = _client()
        key = _key(self.chain.value, address)

        if conn is not None:
            try:
                cached = conn.get(key)
                if cached is not None:
                    return _decode(cached)
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Chain cache read failed for {address}: {exc}")

        transfers = self._inner.get_outgoing_transfers(address)

        if conn is not None:
            try:
                conn.setex(key, self._ttl, _encode(transfers))
            except Exception as exc:  # noqa: BLE001 - never fail a trace to write a cache
                logger.debug(f"Chain cache write failed for {address}: {exc}")
        return transfers

    def get_co_spent_addresses(self, address: str) -> set[str]:
        return self._inner.get_co_spent_addresses(address)
