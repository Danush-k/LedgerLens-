"""Per-IP rate limits.

Both protected endpoints are expensive in a way an attacker can exploit:
login verifies a deliberately slow bcrypt hash, and a trace fans out into
hundreds of calls against a quota the whole deployment shares.
"""
from app.auth.ratelimit import LOGIN_LIMIT, TRACE_LIMIT, limiter


def test_limits_are_configured_on_the_expensive_endpoints():
    assert LOGIN_LIMIT.endswith("/minute")
    assert TRACE_LIMIT.endswith("/minute")


def test_limits_are_above_human_working_speed():
    """A cap an investigator can hit by working quickly is a bug, not
    protection."""
    assert int(LOGIN_LIMIT.split("/")[0]) >= 5
    assert int(TRACE_LIMIT.split("/")[0]) >= 10


def test_login_is_rate_limited(unauthenticated_client):
    """Repeated wrong passwords must eventually be refused - that is the
    credential-guessing surface."""
    limiter.reset()
    statuses = []
    for _ in range(int(LOGIN_LIMIT.split("/")[0]) + 3):
        r = unauthenticated_client.post(
            "/auth/login", data={"username": "investigator", "password": "wrong"})
        statuses.append(r.status_code)

    assert 429 in statuses
    limiter.reset()


def test_rate_limit_response_explains_itself(unauthenticated_client):
    """A bare 429 reads like the system broke. It has to say this is a
    deliberate cap."""
    limiter.reset()
    detail = ""
    for _ in range(int(LOGIN_LIMIT.split("/")[0]) + 3):
        r = unauthenticated_client.post(
            "/auth/login", data={"username": "investigator", "password": "wrong"})
        if r.status_code == 429:
            detail = r.json()["detail"]
            break

    assert "deliberate cap" in detail
    assert "retry" in detail
    limiter.reset()


def test_normal_use_is_never_limited(unauthenticated_client):
    """A handful of attempts, as any real session produces, must pass."""
    limiter.reset()
    for _ in range(4):
        r = unauthenticated_client.post(
            "/auth/login", data={"username": "investigator", "password": "wrong"})
        assert r.status_code != 429
    limiter.reset()
