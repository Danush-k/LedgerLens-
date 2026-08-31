import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
