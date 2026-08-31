from app.api.routes_auth import seed_default_users
from app.auth.security import create_access_token, hash_password, verify_password
from app.config import get_settings
from app.models.orm import User


def test_hash_and_verify_password_roundtrip():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)


def test_seed_default_users_creates_investigator_and_admin(db_session):
    seed_default_users(db_session)
    usernames = {u.username for u in db_session.query(User).all()}
    settings = get_settings()
    assert settings.default_investigator_username in usernames
    assert settings.default_admin_username in usernames


def test_seed_default_users_is_idempotent(db_session):
    seed_default_users(db_session)
    seed_default_users(db_session)
    assert db_session.query(User).count() == 2


def test_login_with_seeded_credentials_returns_a_valid_token(client, db_session):
    seed_default_users(db_session)
    settings = get_settings()

    resp = client.post("/auth/login", data={
        "username": settings.default_investigator_username,
        "password": settings.default_investigator_password,
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "investigator"
    assert body["access_token"]


def test_login_with_wrong_password_is_rejected(client, db_session):
    seed_default_users(db_session)
    settings = get_settings()

    resp = client.post("/auth/login", data={
        "username": settings.default_investigator_username,
        "password": "definitely-wrong",
    })
    assert resp.status_code == 401


def test_protected_endpoint_rejects_missing_token(unauthenticated_client):
    resp = unauthenticated_client.get("/cases")
    assert resp.status_code == 401


def test_protected_endpoint_accepts_valid_token(unauthenticated_client, db_session):
    token = create_access_token("someone", "investigator")
    resp = unauthenticated_client.get("/cases", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_protected_endpoint_rejects_garbage_token(unauthenticated_client):
    resp = unauthenticated_client.get("/cases", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
