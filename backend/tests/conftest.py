"""Pytest fixtures: isolated test database (never touches the real DB).

Uses TEST_DATABASE_URL if set (e.g. a midori_test PostgreSQL database);
otherwise falls back to an in-memory SQLite database so tests can run
anywhere without PostgreSQL.
"""

import os

# Point DATABASE_URL at a throwaway in-memory DB before app imports load it.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("TEST_DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app

from app.database import Base, get_db
from app.models import crop, farm, zone  # noqa: F401,E402  (register models)


@pytest.fixture()
def db_session():
    test_url = os.getenv("TEST_DATABASE_URL", "sqlite://")
    if test_url == "sqlite://":
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(test_url)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    """TestClient wired to the isolated test database."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
