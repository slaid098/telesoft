"""Tests for the Channels API: CRUD endpoints under ``/api/channels``."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from telesoft.db import connection
from telesoft.db.models import job as job_model
from telesoft.db.models import log as log_model
from telesoft.main import app


@pytest.fixture
async def db_handle(authed_client: TestClient) -> AsyncIterator[aiosqlite.Connection]:
    """Expose the shared DB connection used by the running app for direct queries."""
    db = connection._state.db
    assert db is not None
    yield db


def _create_channel(
    client: TestClient,
    *,
    telegram_id: int = 100,
    title: str = "Test channel",
    username: str | None = "test_channel",
) -> dict[str, object]:
    response = client.post(
        "/api/channels",
        json={"telegram_id": telegram_id, "title": title, "username": username},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_list_channels_empty(authed_client: TestClient) -> None:
    response = authed_client.get("/api/channels")
    assert response.status_code == 200
    assert response.json() == {"channels": [], "total": 0}


def test_list_channels_returns_all(authed_client: TestClient) -> None:
    for i in range(3):
        _create_channel(authed_client, telegram_id=100 + i, title=f"ch{i}")
    response = authed_client.get("/api/channels")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["channels"]) == 3


def test_list_channels_active_only(authed_client: TestClient) -> None:
    a = _create_channel(authed_client, telegram_id=1, title="active1")
    b = _create_channel(authed_client, telegram_id=2, title="active2")
    c = _create_channel(authed_client, telegram_id=3, title="inactive")
    authed_client.patch(f"/api/channels/{c['id']}", json={"is_active": False})
    response = authed_client.get("/api/channels", params={"active_only": True})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    ids = {ch["id"] for ch in body["channels"]}
    assert ids == {a["id"], b["id"]}


def test_list_channels_show_inactive_true_returns_inactive(authed_client: TestClient) -> None:
    """``?show_inactive=true`` returns both active and inactive channels."""
    a = _create_channel(authed_client, telegram_id=10, title="active")
    b = _create_channel(authed_client, telegram_id=11, title="inactive")
    authed_client.patch(f"/api/channels/{b['id']}", json={"is_active": False})
    response = authed_client.get("/api/channels", params={"show_inactive": "true"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    ids = {ch["id"] for ch in body["channels"]}
    assert ids == {a["id"], b["id"]}


def test_list_channels_show_inactive_false_excludes_inactive(
    authed_client: TestClient,
) -> None:
    """``?show_inactive=false`` returns only active channels (excludes inactive)."""
    a = _create_channel(authed_client, telegram_id=20, title="active")
    b = _create_channel(authed_client, telegram_id=21, title="inactive")
    authed_client.patch(f"/api/channels/{b['id']}", json={"is_active": False})
    response = authed_client.get("/api/channels", params={"show_inactive": "false"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    ids = {ch["id"] for ch in body["channels"]}
    assert ids == {a["id"]}


def test_create_channel_success(authed_client: TestClient) -> None:
    response = authed_client.post(
        "/api/channels",
        json={"telegram_id": 555, "title": "New channel", "username": "new_ch"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] is not None
    assert body["telegram_id"] == 555
    assert body["title"] == "New channel"
    assert body["username"] == "new_ch"
    assert body["is_active"] is True
    assert body["added_at"]


def test_create_channel_duplicate_telegram_id(authed_client: TestClient) -> None:
    _create_channel(authed_client, telegram_id=777, title="first")
    response = authed_client.post(
        "/api/channels",
        json={"telegram_id": 777, "title": "second"},
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_create_channel_requires_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long-for-testing")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "telesoft.db"))
    with TestClient(app) as unauthed:
        response = unauthed.post(
            "/api/channels",
            json={"telegram_id": 1, "title": "x"},
        )
        assert response.status_code == 401


def test_get_channel_by_id(authed_client: TestClient) -> None:
    created = _create_channel(authed_client, telegram_id=42, title="by id")
    response = authed_client.get(f"/api/channels/{created['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["telegram_id"] == 42
    assert body["title"] == "by id"


def test_get_channel_not_found(authed_client: TestClient) -> None:
    response = authed_client.get("/api/channels/9999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_update_channel_success(authed_client: TestClient) -> None:
    created = _create_channel(authed_client, telegram_id=10, title="old title")
    response = authed_client.patch(
        f"/api/channels/{created['id']}",
        json={"title": "new title"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "new title"
    assert body["id"] == created["id"]


def test_update_channel_not_found(authed_client: TestClient) -> None:
    response = authed_client.patch("/api/channels/9999", json={"title": "x"})
    assert response.status_code == 404


def test_update_channel_no_fields(authed_client: TestClient) -> None:
    created = _create_channel(authed_client, telegram_id=11, title="ch")
    response = authed_client.patch(f"/api/channels/{created['id']}", json={})
    assert response.status_code == 422


def test_delete_channel_success(authed_client: TestClient) -> None:
    created = _create_channel(authed_client, telegram_id=20, title="to delete")
    response = authed_client.delete(f"/api/channels/{created['id']}")
    assert response.status_code == 204
    assert response.content == b""
    assert authed_client.get(f"/api/channels/{created['id']}").status_code == 404


def test_delete_channel_not_found(authed_client: TestClient) -> None:
    response = authed_client.delete("/api/channels/9999")
    assert response.status_code == 404


async def test_delete_channel_cascade_jobs_logs(
    authed_client: TestClient, db_handle: aiosqlite.Connection
) -> None:
    created = _create_channel(authed_client, telegram_id=30, title="cascade")
    channel_id = int(created["id"])
    job = await job_model.create_job(
        db_handle,
        channel_id=channel_id,
        pattern="https://old.link",
        new_link="https://new.link",
        created_at="2026-07-20T00:00:00Z",
    )
    job_id = int(job["id"])
    await log_model.create_log(
        db_handle,
        job_id=job_id,
        message_id=123,
        old_text="hello",
        success=True,
        error=None,
        edited_at="2026-07-20T00:00:00Z",
    )
    response = authed_client.delete(f"/api/channels/{channel_id}")
    assert response.status_code == 204

    jobs = await job_model.list_jobs(db_handle, channel_id=channel_id)
    assert jobs == []
    logs = await log_model.list_logs(db_handle, job_id=job_id)
    assert logs == []
