"""Tests for the session-based auth: login/logout/me, wrong password, protected
endpoint access, session persistence, and concurrent sessions."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from telesoft.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    """A TestClient with a fixed secret key and a temp DB so lifespan runs."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long-for-testing")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "telesoft.db"))
    with TestClient(app) as c:
        yield c


def test_login_success(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "secret"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "user": "admin"}
    assert "session" in response.cookies


def test_login_invalid_credentials(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_logout_requires_auth(client: TestClient) -> None:
    response = client.post("/api/auth/logout")
    assert response.status_code == 401


def test_logout_success(client: TestClient) -> None:
    client.post("/api/auth/login", json={"username": "admin", "password": "secret"})
    assert client.get("/api/auth/me").status_code == 200
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert client.get("/api/auth/me").status_code == 401


def test_me_requires_auth(client: TestClient) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_after_login(client: TestClient) -> None:
    client.post("/api/auth/login", json={"username": "admin", "password": "secret"})
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json() == {"user": "admin"}


def test_session_persists_across_requests(client: TestClient) -> None:
    client.post("/api/auth/login", json={"username": "admin", "password": "secret"})
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json() == {"user": "admin"}


def test_concurrent_sessions_independent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long-for-testing")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "telesoft.db"))
    with TestClient(app):
        client_a = TestClient(app)
        client_b = TestClient(app)
        client_a.post("/api/auth/login", json={"username": "admin", "password": "secret"})
        client_b.post("/api/auth/login", json={"username": "admin", "password": "secret"})

        assert client_a.get("/api/auth/me").status_code == 200
        assert client_b.get("/api/auth/me").status_code == 200

        client_a.post("/api/auth/logout")
        assert client_a.get("/api/auth/me").status_code == 401
        assert client_b.get("/api/auth/me").status_code == 200
