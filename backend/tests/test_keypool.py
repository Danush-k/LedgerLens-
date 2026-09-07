"""Explorer API key rotation.

Free explorer keys allow a few requests per second each. The behaviour that
matters is that a throttled key is stepped over rather than retried, and
that a throttle is never mistaken for an empty wallet.
"""
from app.chain_clients.evm import _is_rate_limited
from app.chain_clients.keypool import APIKeyPool, pool_from_setting


def test_keys_rotate_round_robin():
    pool = APIKeyPool(["a", "b", "c"])
    assert [pool.get() for _ in range(4)] == ["a", "b", "c", "a"]


def test_a_penalised_key_is_skipped():
    pool = APIKeyPool(["a", "b"], cooldown_seconds=60)
    pool.penalise("a")
    assert {pool.get() for _ in range(4)} == {"b"}


def test_a_key_returns_after_its_cooldown():
    pool = APIKeyPool(["a", "b"], cooldown_seconds=0)
    pool.penalise("a")
    assert {pool.get() for _ in range(6)} == {"a", "b"}


def test_all_keys_penalised_still_returns_one():
    """Stalling the trace is worse than sending a request that may fail -
    the caller already handles the failure."""
    pool = APIKeyPool(["a", "b"], cooldown_seconds=60)
    pool.penalise("a")
    pool.penalise("b")
    assert pool.get() in {"a", "b"}


def test_no_configured_keys_still_works():
    """An empty key is valid for Etherscan - it just means the anonymous
    limit - so the pool must not refuse to start without one."""
    pool = pool_from_setting("")
    assert len(pool) == 1
    assert pool.get() == ""


def test_parses_a_comma_separated_setting():
    pool = pool_from_setting(" key1 , key2,key3 ")
    assert len(pool) == 3
    assert {pool.get() for _ in range(3)} == {"key1", "key2", "key3"}


def test_a_single_key_setting_still_works():
    """Existing .env files hold one key and must keep working unchanged."""
    pool = pool_from_setting("only-one")
    assert len(pool) == 1
    assert pool.get() == "only-one"


# ── recognising a throttle for what it is ─────────────────────────────────

def test_rate_limit_response_is_recognised():
    assert _is_rate_limited({"status": "0", "message": "NOTOK",
                             "result": "Max rate limit reached"})


def test_empty_but_successful_response_is_not_a_rate_limit():
    """A wallet that genuinely sent nothing must not be reported as
    throttled, or every quiet address becomes a retry."""
    assert not _is_rate_limited({"status": "1", "message": "OK", "result": []})
    assert not _is_rate_limited({"status": "0", "message": "No transactions found",
                                 "result": []})
