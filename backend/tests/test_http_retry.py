import requests
import responses

from app.chain_clients.http import get_with_retry


@responses.activate
def test_retries_on_server_error_then_succeeds():
    url = "https://example.test/api"
    responses.add(responses.GET, url, status=503)
    responses.add(responses.GET, url, status=200, json={"ok": True})

    session = requests.Session()
    result = get_with_retry(session, url, attempts=3, timeout=5)

    assert result.status_code == 200
    assert result.json() == {"ok": True}
    assert len(responses.calls) == 2


@responses.activate
def test_gives_up_after_exhausting_attempts():
    url = "https://example.test/api"
    responses.add(responses.GET, url, status=503)
    responses.add(responses.GET, url, status=503)
    responses.add(responses.GET, url, status=503)

    session = requests.Session()
    try:
        get_with_retry(session, url, attempts=3, timeout=5)
        assert False, "expected an exception"
    except requests.RequestException:
        pass

    assert len(responses.calls) == 3


@responses.activate
def test_succeeds_immediately_without_retrying_on_first_try():
    url = "https://example.test/api"
    responses.add(responses.GET, url, status=200, json={"ok": True})

    session = requests.Session()
    result = get_with_retry(session, url, attempts=3, timeout=5)

    assert result.status_code == 200
    assert len(responses.calls) == 1
