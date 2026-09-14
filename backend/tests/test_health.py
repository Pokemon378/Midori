"""Tests for the root and health endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_message() -> None:
    """GET / should confirm the backend is running."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Midori backend is running"}


def test_health_returns_ok() -> None:
    """GET /health should report status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
