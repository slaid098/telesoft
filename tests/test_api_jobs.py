"""Tests for the Jobs / replace-link API (``/api/channels/{id}/replace-link``,
``/api/jobs`` and friends).

Telethon is mocked via ``mock_telethon_get_message`` / ``mock_telethon_edit_message``
fixtures — no real Telegram calls are made. The :class:`JobRunner` attached to
``app.state`` runs real code (semaphore + status transitions + log writes), so
end-to-end behaviour is exercised against the mock Telegram layer.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock

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
    telegram_id: int = -1001234567890,
    title: str = "Test channel",
    username: str | None = "test_channel",
) -> dict[str, object]:
    response = client.post(
        "/api/channels",
        json={"telegram_id": telegram_id, "title": title, "username": username},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _url_for(channel: dict[str, object], message_id: int) -> str:
    """Build a t.me post URL matching the channel's username/telegram_id."""
    username = channel.get("username")
    if username is not None:
        return f"https://t.me/{username}/{message_id}"
    tg_id = int(channel["telegram_id"])  # type: ignore[index]
    internal = str(abs(tg_id))[len("100") :]
    return f"https://t.me/c/{internal}/{message_id}"


def test_replace_link_success(
    authed_client: TestClient,
    mock_telethon_get_message: AsyncMock,
    mock_telethon_edit_message: AsyncMock,
) -> None:
    channel = _create_channel(authed_client, telegram_id=-1001234567890, username="test_channel")
    response = authed_client.post(
        f"/api/channels/{channel['id']}/replace-link",
        json={
            "post_urls": [_url_for(channel, 123)],
            "pattern": r"https://old\.example\.com",
            "new_link": "https://new.example.com",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["job_id"] is not None
    assert body["status"] == "pending"


def test_replace_link_invalid_channel(
    authed_client: TestClient,
    mock_telethon_get_message: AsyncMock,
) -> None:
    response = authed_client.post(
        "/api/channels/9999/replace-link",
        json={
            "post_urls": ["https://t.me/test_channel/1"],
            "pattern": r"https://x",
            "new_link": "https://new.example.com",
        },
    )
    assert response.status_code == 404


def test_replace_link_invalid_pattern(
    authed_client: TestClient,
    mock_telethon_get_message: AsyncMock,
) -> None:
    channel = _create_channel(authed_client)
    response = authed_client.post(
        f"/api/channels/{channel['id']}/replace-link",
        json={
            "post_urls": [_url_for(channel, 1)],
            "pattern": "[invalid",
            "new_link": "https://new.example.com",
        },
    )
    assert response.status_code == 422


def test_replace_link_invalid_url(
    authed_client: TestClient,
    mock_telethon_get_message: AsyncMock,
) -> None:
    channel = _create_channel(authed_client)
    response = authed_client.post(
        f"/api/channels/{channel['id']}/replace-link",
        json={
            "post_urls": ["not-a-url"],
            "pattern": r"https://x",
            "new_link": "https://new.example.com",
        },
    )
    assert response.status_code == 422


def test_replace_link_url_wrong_channel(
    authed_client: TestClient,
    mock_telethon_get_message: AsyncMock,
) -> None:
    channel = _create_channel(authed_client, telegram_id=-1001234567890, username="test_channel")
    # URL references a different private channel id
    response = authed_client.post(
        f"/api/channels/{channel['id']}/replace-link",
        json={
            "post_urls": ["https://t.me/c/9999999999/1"],
            "pattern": r"https://x",
            "new_link": "https://new.example.com",
        },
    )
    assert response.status_code == 422


def test_replace_link_requires_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long-for-testing")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "telesoft.db"))
    with TestClient(app) as unauthed:
        response = unauthed.post(
            "/api/channels/1/replace-link",
            json={
                "post_urls": ["https://t.me/test_channel/1"],
                "pattern": r"https://x",
                "new_link": "https://new.example.com",
            },
        )
        assert response.status_code == 401


async def test_list_jobs(
    authed_client: TestClient,
    db_handle: aiosqlite.Connection,
    mock_telethon_get_message: AsyncMock,
) -> None:
    channel = _create_channel(authed_client)
    channel_id = int(channel["id"])
    await job_model.create_job(
        db_handle,
        channel_id=channel_id,
        pattern="https://old.link",
        new_link="https://new.link",
        created_at="2026-07-20T00:00:00Z",
    )
    await job_model.create_job(
        db_handle,
        channel_id=channel_id,
        pattern="https://old2.link",
        new_link="https://new2.link",
        created_at="2026-07-20T00:00:00Z",
    )
    response = authed_client.get("/api/jobs")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["jobs"]) == 2


async def test_list_jobs_filter_by_channel(
    authed_client: TestClient,
    db_handle: aiosqlite.Connection,
) -> None:
    ch1 = _create_channel(authed_client, telegram_id=-1001, title="ch1", username="u1")
    ch2 = _create_channel(authed_client, telegram_id=-1002, title="ch2", username="u2")
    await job_model.create_job(
        db_handle,
        channel_id=int(ch1["id"]),
        pattern="x",
        new_link="y",
        created_at="2026-07-20T00:00:00Z",
    )
    await job_model.create_job(
        db_handle,
        channel_id=int(ch2["id"]),
        pattern="x",
        new_link="y",
        created_at="2026-07-20T00:00:00Z",
    )
    response = authed_client.get("/api/jobs", params={"channel_id": int(ch1["id"])})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["jobs"][0]["channel_id"] == int(ch1["id"])


async def test_get_job_by_id(
    authed_client: TestClient,
    db_handle: aiosqlite.Connection,
) -> None:
    channel = _create_channel(authed_client)
    job = await job_model.create_job(
        db_handle,
        channel_id=int(channel["id"]),
        pattern="https://old.link",
        new_link="https://new.link",
        created_at="2026-07-20T00:00:00Z",
    )
    response = authed_client.get(f"/api/jobs/{job['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == int(job["id"])
    assert body["pattern"] == "https://old.link"


def test_get_job_not_found(authed_client: TestClient) -> None:
    response = authed_client.get("/api/jobs/9999")
    assert response.status_code == 404


async def test_get_job_logs(
    authed_client: TestClient,
    db_handle: aiosqlite.Connection,
) -> None:
    channel = _create_channel(authed_client)
    job = await job_model.create_job(
        db_handle,
        channel_id=int(channel["id"]),
        pattern="x",
        new_link="y",
        created_at="2026-07-20T00:00:00Z",
    )
    await log_model.create_log(
        db_handle,
        job_id=int(job["id"]),
        message_id=42,
        old_text="hello",
        success=True,
        error=None,
        edited_at="2026-07-20T00:00:00Z",
    )
    response = authed_client.get(f"/api/jobs/{job['id']}/logs")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["logs"][0]["message_id"] == 42
    assert body["logs"][0]["success"] is True


def test_get_job_logs_job_not_found(authed_client: TestClient) -> None:
    response = authed_client.get("/api/jobs/9999/logs")
    assert response.status_code == 404


async def test_cancel_job_success(
    authed_client: TestClient,
    db_handle: aiosqlite.Connection,
) -> None:
    channel = _create_channel(authed_client)
    job = await job_model.create_job(
        db_handle,
        channel_id=int(channel["id"]),
        pattern="x",
        new_link="y",
        created_at="2026-07-20T00:00:00Z",
    )
    response = authed_client.post(f"/api/jobs/{job['id']}/cancel")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"


async def test_cancel_job_already_done(
    authed_client: TestClient,
    db_handle: aiosqlite.Connection,
) -> None:
    channel = _create_channel(authed_client)
    job = await job_model.create_job(
        db_handle,
        channel_id=int(channel["id"]),
        pattern="x",
        new_link="y",
        created_at="2026-07-20T00:00:00Z",
    )
    await job_model.update_job_status(
        db_handle,
        job_id=int(job["id"]),
        status="done",
        completed_at="2026-07-20T00:00:00Z",
    )
    response = authed_client.post(f"/api/jobs/{job['id']}/cancel")
    assert response.status_code == 409


def test_jobs_endpoints_require_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long-for-testing")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "telesoft.db"))
    with TestClient(app) as unauthed:
        assert unauthed.get("/api/jobs").status_code == 401
        assert unauthed.get("/api/jobs/1").status_code == 401
        assert unauthed.get("/api/jobs/1/logs").status_code == 401
        assert unauthed.post("/api/jobs/1/cancel").status_code == 401
