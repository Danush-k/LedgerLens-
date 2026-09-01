import time

import requests

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def get_with_retry(session: requests.Session, url: str, params: dict | None = None,
                    timeout: int = 5, attempts: int = 2) -> requests.Response:
    """Free public block-explorer APIs occasionally blip (rate limits,
    momentary connection resets) - a single failed request shouldn't sink
    an otherwise-good trace. Retries with a short linear backoff, then lets
    the final failure propagate so the caller's own error handling (which
    marks that branch unresolved rather than crashing the whole trace)
    still applies.
    """
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            response = session.get(url, params=params, timeout=timeout)
            if response.status_code in RETRYABLE_STATUS and attempt < attempts - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < attempts - 1:
                time.sleep(0.5 * (attempt + 1))
    raise last_exc
