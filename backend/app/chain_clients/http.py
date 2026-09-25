"""Resilient HTTP for public block explorers.

These APIs are free, unauthenticated and shared with the whole internet, so
they throttle aggressively and drop connections without warning. Three
things keep a trace alive against them, in order of how much they matter:

1. Not tripping the limit. The tracer fetches a hop's wallets concurrently,
   which is what makes it fast, but eight simultaneous requests is exactly
   what a free explorer refuses. A token bucket paces requests per host so
   concurrency speeds up waiting rather than multiplying request rate.

2. Backing off properly when refused. A connection reset means "you are
   asking too fast"; retrying 0.5s later asks too fast again. Exponential
   backoff with jitter gives the limit time to clear and stops parallel
   workers retrying in lockstep.

3. Having somewhere else to ask. Several providers serve the identical
   Esplora API, so a host that is throttling us can be stepped over.
"""
import concurrent.futures
import random
import socket
import threading
import time

import requests
import urllib3.util.connection as _urllib3_connection

RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# DNS for a public API host often returns several candidate IPs (IPv4 and
# IPv6 both), and `socket.create_connection` - what every request here goes
# through - tries them one at a time, each paying the *full* connect
# timeout before falling to the next. A host with broken IPv6 routing (not
# rare, and true of this environment against at least one of these
# explorers) turns a "10s timeout" into 10s times however many dead
# candidates come first. Since none of these APIs need IPv6, forcing IPv4
# removes the dead candidates outright rather than hoping the timeout
# absorbs them.
_urllib3_connection.allowed_gai_family = lambda: socket.AF_INET

# A second, independent backstop for the same problem: even IPv4-only, a
# host can still hand back several unreachable IPs before a working one (or
# none at all), and each is its own full-timeout wait *inside a single
# requests.get() call* - `timeout=` bounds one connection attempt, not the
# call. Measured directly against a currently address-multiplied host, a
# `timeout=10` call took 140s to raise. Running the call on a watchdog
# thread and bounding *that* with a hard wall-clock deadline is the only
# reliable way to cap it - confirmed to actually cut the same call off at
# the deadline regardless of how many candidates were hanging underneath.
_watchdog_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=64, thread_name_prefix="chain-http-watchdog")


class RateLimiter:
    """Paces requests to one host to a minimum interval between them.

    Deliberately a plain interval rather than a token bucket. A bucket
    allows a burst, which is the exact shape of traffic a free explorer
    refuses, and the book-keeping is easy to get subtly wrong - an earlier
    version here leaked tokens on the waiting path and slowed to a halt.
    A steady floor between requests is duller and correct.
    """

    def __init__(self, rate_per_second: float):
        self._min_interval = 1.0 / rate_per_second
        self._next_free = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Claim the next slot, then wait for it.

        The slot is reserved inside the lock and slept for outside it, so
        concurrent callers queue rather than all waking at the same instant
        and firing together - which would recreate the burst this exists to
        prevent.
        """
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._next_free)
            self._next_free = slot + self._min_interval
        delay = slot - time.monotonic()
        if delay > 0:
            time.sleep(delay)


_limiters: dict[str, RateLimiter] = {}
_limiters_lock = threading.Lock()

# Deliberately below what the providers advertise. Being refused costs a
# retry and a wait, so the cheaper mistake is to ask slightly too slowly.
DEFAULT_RATE_PER_SECOND = 3.0


def limiter_for(host: str, rate: float = DEFAULT_RATE_PER_SECOND) -> RateLimiter:
    with _limiters_lock:
        if host not in _limiters:
            _limiters[host] = RateLimiter(rate)
        return _limiters[host]


def _host_of(url: str) -> str:
    without_scheme = url.split("://", 1)[-1]
    return without_scheme.split("/", 1)[0]


def get_with_retry(session: requests.Session, url: str, params: dict | None = None,
                    timeout: int = 10, attempts: int = 3,
                    rate: float = DEFAULT_RATE_PER_SECOND) -> requests.Response:
    """GET with pacing, exponential backoff and jitter.

    Raises the final failure so the caller's own handling - which marks that
    branch unresolved rather than sinking the whole trace - still applies.
    """
    limiter = limiter_for(_host_of(url), rate)
    last_exc: Exception | None = None

    # requests' own timeout only bounds a single connection attempt, not
    # this call - a wall-clock deadline a few seconds above it is the actual
    # ceiling on how long one attempt can run, no matter how many candidate
    # addresses are hanging underneath it.
    deadline = timeout + 3

    for attempt in range(attempts):
        limiter.acquire()
        try:
            future = _watchdog_pool.submit(session.get, url, params=params, timeout=timeout)
            try:
                response = future.result(timeout=deadline)
            except concurrent.futures.TimeoutError:
                raise requests.exceptions.ConnectTimeout(
                    f"{url} did not respond within {deadline}s wall-clock "
                    f"(requests' own timeout does not bound multiple candidate "
                    f"addresses; this does)")
            if response.status_code in RETRYABLE_STATUS:
                if attempt < attempts - 1:
                    time.sleep(_backoff(attempt))
                    continue
                response.raise_for_status()
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            # A reset connection, or an SSL EOF mid-handshake, is the same
            # message as a 429 delivered at a lower layer. Both clear on a
            # retry, so both are treated as throttling rather than failure.
            last_exc = exc
            if attempt < attempts - 1:
                time.sleep(_backoff(attempt))

    raise last_exc


def _backoff(attempt: int) -> float:
    """Exponential, with jitter so parallel workers do not retry together."""
    return min(8.0, (2 ** attempt) * 0.8) + random.uniform(0, 0.5)
