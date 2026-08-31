import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import CurrentUser, get_current_user
from app.db.postgres import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    """A fresh in-memory SQLite DB per test - fast, no live Postgres needed.

    StaticPool is required here: TestClient dispatches requests through a
    different thread, and the default SQLite pool hands out a *new*
    connection (i.e. a different, empty in-memory DB) per thread. StaticPool
    pins the whole engine to one shared connection so setup and requests see
    the same database.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine)
    session = session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    """An authenticated test client - auth itself has its own dedicated
    tests (test_auth.py), so every other endpoint test can focus on its
    own business logic instead of re-proving login works each time."""
    def override_get_db():
        yield db_session

    def override_get_current_user():
        return CurrentUser(username="test-investigator", role="investigator")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def unauthenticated_client(db_session):
    """A client with the DB overridden but auth left real - for testing
    that protected endpoints actually reject unauthenticated requests."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
