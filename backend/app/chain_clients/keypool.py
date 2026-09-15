"""Rotation across several free explorer API keys.

The Etherscan family caps free keys at a few requests per second. A single
key throttles a trace to a crawl and, once the limit is hit, the explorer
answers with an error that looks like "this wallet has no transactions" -
which the tracer would otherwise be entitled to read as a finding. Rotating
across several keys raises the ceiling proportionally and, more usefully,
lets a key that is currently throttled be skipped rather than retried.

Keys are read from the environment as a comma-separated list, so a
deployment adds capacity by adding keys and changes nothing else.
"""
import threading
import time


class APIKeyPool:
    """Round-robin over keys, temporarily benching any that gets rate-limited.

    Thread-safe because Celery runs several workers in one process and they
    share a pool. Without the lock two workers can take the same index and
    hammer one key while the others sit idle.
    """

    def __init__(self, keys: list[str], cooldown_seconds: float = 2.0):
        # An empty key is valid for Etherscan - it just means the strictest
        # anonymous limit - so a pool with no configured keys still works
        # rather than refusing to start.
        self._keys = [k.strip() for k in keys if k.strip()] or [""]
        self._cooldown = cooldown_seconds
        self._index = 0
        self._benched: dict[str, float] = {}
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._keys)

    def get(self) -> str:
        """The next usable key.

        If every key is benched, the least-recently-benched one is returned
        anyway: waiting would stall the trace, and a throttled request that
        fails is still better than one never sent, because the caller's
        retry and error handling already cover it.
        """
        now = time.monotonic()
        with self._lock:
            for _ in range(len(self._keys)):
                key = self._keys[self._index % len(self._keys)]
                self._index += 1
                if self._benched.get(key, 0) <= now:
                    return key
            return min(self._benched, key=self._benched.get)

    def penalise(self, key: str) -> None:
        """Bench a key briefly after it reports a rate limit."""
        with self._lock:
            self._benched[key] = time.monotonic() + self._cooldown


def pool_from_setting(value: str) -> APIKeyPool:
    """Build a pool from a comma-separated environment value."""
    return APIKeyPool((value or "").split(","))
