"""Tests for the Jobs / replace-link API (``/api/channels/{id}/replace-link``,
``/api/jobs`` and friends).

Telethon is mocked via ``mock_telethon_get_message`` / ``mock_telethon_edit_message``
/ ``mock_telethon_get_last_messages`` fixtures — no real Telegram calls are made.
The :class:`JobRunner` attached to ``app.state`` runs real code (semaphore +
status transitions + log writes), so end-to-end behaviour is exercised against
the mock Telegram layer.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from telesoft.core.runner import JobRunner
from telesoft.db import connection
from telesoft.db.models import job as job_model
from telesoft.db.models import log as log_model
from telesoft.main import app
from tests.conftest import MockMessage


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


def _matching_messages(link: str, count: int) -> list[MockMessage]:
    r"""Return ``count`` MockMessages whose text contains *link* (plus a non-match).

    *link* is the literal URL string (NOT a regex) — callers pair it with a
    pattern that matches it (e.g. ``link="https://old.example.com"`` with
    ``pattern=r"https://old\.example\.com"``).
    """
    out: list[MockMessage] = []
    for i in range(count):
        out.append(MockMessage(id=100 + i, text=f"see {link} here", chat_id=-1001234567890))
    out.append(MockMessage(id=999, text="nothing here", chat_id=-1001234567890))
    return out


def _drain_until_settled(client: TestClient, job_id: int, rounds: int = 50) -> dict[str, object]:
    """Poll the job status until it reaches a terminal state (or rounds run out).

    Each round issues a cheap ``GET /api/jobs/{id}`` plus a ``GET /health`` to
    pump the asyncio event loop so the background runner task can progress.
    """
    body: dict[str, object] = {}
    for _ in range(rounds):
        resp = client.get(f"/api/jobs/{job_id}")
        body = resp.json()
        if str(body["status"]) in ("done", "failed", "cancelled"):
            return body
        client.get("/health")
    return body


def test_replace_link_success(
    authed_client: TestClient,
    mock_runner: JobRunner,
    mock_telethon_get_message: AsyncMock,
    mock_telethon_edit_message: AsyncMock,
    mock_telethon_get_last_messages: AsyncMock,
) -> None:
    channel = _create_channel(authed_client, telegram_id=-1001234567890, username="test_channel")
    pattern = r"https://old\.example\.com"
    mock_telethon_get_last_messages.return_value = _matching_messages("https://old.example.com", 3)
    response = authed_client.post(
        f"/api/channels/{channel['id']}/replace-link",
        json={
            "pattern": pattern,
            "new_link": "https://new.example.com",
            "post_link": "https://t.me/test/140",
            "limit": 100,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["job_id"] is not None
    assert body["status"] == "pending"


def test_replace_link_invalid_channel(
    authed_client: TestClient,
    mock_telethon_get_last_messages: AsyncMock,
) -> None:
    response = authed_client.post(
        "/api/channels/9999/replace-link",
        json={
            "pattern": r"https://x",
            "new_link": "https://new.example.com",
            "post_link": "https://t.me/test/140",
        },
    )
    assert response.status_code == 404
    mock_telethon_get_last_messages.assert_not_awaited()


def test_replace_link_invalid_pattern(
    authed_client: TestClient,
    mock_telethon_get_last_messages: AsyncMock,
) -> None:
    channel = _create_channel(authed_client)
    response = authed_client.post(
        f"/api/channels/{channel['id']}/replace-link",
        json={
            "pattern": "[invalid",
            "new_link": "https://new.example.com",
            "post_link": "https://t.me/test/140",
        },
    )
    assert response.status_code == 422
    mock_telethon_get_last_messages.assert_not_awaited()


def test_replace_link_invalid_post_link_422(
    authed_client: TestClient,
    mock_telethon_get_last_messages: AsyncMock,
) -> None:
    """Invalid post_link → 422 (no Telegram fetch)."""
    channel = _create_channel(authed_client)
    response = authed_client.post(
        f"/api/channels/{channel['id']}/replace-link",
        json={
            "pattern": r"https://x",
            "new_link": "https://new.example.com",
            "post_link": "invalid",
        },
    )
    assert response.status_code == 422
    mock_telethon_get_last_messages.assert_not_awaited()


def test_replace_link_limit_validation(
    authed_client: TestClient,
    mock_runner: JobRunner,
    mock_telethon_get_last_messages: AsyncMock,
) -> None:
    channel = _create_channel(authed_client)
    endpoint = f"/api/channels/{channel['id']}/replace-link"
    base_body = {
        "pattern": r"https://x",
        "new_link": "https://new.example.com",
        "post_link": "140",
    }

    too_low = authed_client.post(endpoint, json={**base_body, "limit": 0})
    assert too_low.status_code == 422

    too_high = authed_client.post(endpoint, json={**base_body, "limit": 1001})
    assert too_high.status_code == 422

    mock_telethon_get_last_messages.return_value = _matching_messages("https://x", 1)
    ok = authed_client.post(endpoint, json={**base_body, "limit": 100})
    assert ok.status_code == 201


def test_replace_link_default_limit(
    authed_client: TestClient,
    mock_runner: JobRunner,
    mock_telethon_get_message: AsyncMock,
    mock_telethon_edit_message: AsyncMock,
    mock_telethon_get_last_messages: AsyncMock,
) -> None:
    channel = _create_channel(authed_client)
    pattern = r"https://old\.example\.com"
    mock_telethon_get_last_messages.return_value = _matching_messages("https://old.example.com", 1)
    response = authed_client.post(
        f"/api/channels/{channel['id']}/replace-link",
        json={
            "pattern": pattern,
            "new_link": "https://new.example.com",
            "post_link": "140",
        },
    )
    assert response.status_code == 201
    job_id = response.json()["job_id"]
    final = _drain_until_settled(authed_client, int(job_id))
    assert str(final["status"]) in ("done", "failed"), final
    mock_telethon_get_last_messages.assert_awaited_once()
    called_limit = mock_telethon_get_last_messages.await_args.args[1]
    assert called_limit == 100


def test_replace_link_link_preview_true_reaches_runner(
    authed_client: TestClient,
    mock_runner: JobRunner,
    mock_telethon_get_last_messages: AsyncMock,
) -> None:
    """``link_preview: true`` in the POST body is forwarded to ``runner.submit``."""
    channel = _create_channel(authed_client)
    mock_telethon_get_last_messages.return_value = []
    submit_spy = MagicMock(wraps=mock_runner.submit)
    mock_runner.submit = submit_spy  # type: ignore[method-assign]
    response = authed_client.post(
        f"/api/channels/{channel['id']}/replace-link",
        json={
            "pattern": r"https://old\.example\.com",
            "new_link": "https://new.example.com",
            "post_link": "https://t.me/test/140",
            "limit": 100,
            "link_preview": True,
        },
    )
    assert response.status_code == 201, response.text
    submit_spy.assert_called_once()
    assert submit_spy.call_args.kwargs["link_preview"] is True


def test_replace_link_link_preview_defaults_to_false(
    authed_client: TestClient,
    mock_runner: JobRunner,
    mock_telethon_get_last_messages: AsyncMock,
) -> None:
    """Omitting ``link_preview`` defaults to ``False`` in ``runner.submit``."""
    channel = _create_channel(authed_client)
    mock_telethon_get_last_messages.return_value = []
    submit_spy = MagicMock(wraps=mock_runner.submit)
    mock_runner.submit = submit_spy  # type: ignore[method-assign]
    response = authed_client.post(
        f"/api/channels/{channel['id']}/replace-link",
        json={
            "pattern": r"https://old\.example\.com",
            "new_link": "https://new.example.com",
            "post_link": "https://t.me/test/140",
            "limit": 100,
        },
    )
    assert response.status_code == 201, response.text
    submit_spy.assert_called_once()
    assert submit_spy.call_args.kwargs["link_preview"] is False


def test_replace_link_requires_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long-for-testing")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "telesoft.db"))
    with TestClient(app) as unauthed:
        response = unauthed.post(
            "/api/channels/1/replace-link",
            json={
                "pattern": r"https://x",
                "new_link": "https://new.example.com",
                "post_link": "140",
            },
        )
        assert response.status_code == 401


async def test_list_jobs(
    authed_client: TestClient,
    db_handle: aiosqlite.Connection,
    mock_telethon_get_last_messages: AsyncMock,
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


async def test_list_jobs_total_includes_all_matching(
    authed_client: TestClient,
    db_handle: aiosqlite.Connection,
) -> None:
    """``total`` is the total matching count (ignoring LIMIT/OFFSET), not len(jobs)."""
    channel = _create_channel(authed_client)
    channel_id = int(channel["id"])
    for _ in range(15):
        await job_model.create_job(
            db_handle,
            channel_id=channel_id,
            pattern="x",
            new_link="y",
            created_at="2026-07-20T00:00:00Z",
        )
    response = authed_client.get("/api/jobs", params={"limit": 10, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 15
    assert len(body["jobs"]) == 10


async def test_list_jobs_total_with_status_filter(
    authed_client: TestClient,
    db_handle: aiosqlite.Connection,
) -> None:
    """``total`` honours the status filter (matching count, not all jobs)."""
    channel = _create_channel(authed_client)
    channel_id = int(channel["id"])
    j1 = await job_model.create_job(
        db_handle,
        channel_id=channel_id,
        pattern="x",
        new_link="y",
        created_at="2026-07-20T00:00:00Z",
    )
    await job_model.create_job(
        db_handle,
        channel_id=channel_id,
        pattern="x",
        new_link="y",
        created_at="2026-07-20T00:00:00Z",
    )
    await job_model.update_job_status(db_handle, job_id=int(j1["id"]), status="done")
    response = authed_client.get("/api/jobs", params={"status": "done"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["jobs"]) == 1


async def test_get_job_logs_total_includes_all_matching(
    authed_client: TestClient,
    db_handle: aiosqlite.Connection,
) -> None:
    """``total`` for logs is the real count (ignoring LIMIT/OFFSET), not len(logs)."""
    channel = _create_channel(authed_client)
    job = await job_model.create_job(
        db_handle,
        channel_id=int(channel["id"]),
        pattern="x",
        new_link="y",
        created_at="2026-07-20T00:00:00Z",
    )
    for i in range(5):
        await log_model.create_log(
            db_handle,
            job_id=int(job["id"]),
            message_id=100 + i,
            old_text="hello",
            success=True,
            error=None,
            edited_at="2026-07-20T00:00:00Z",
        )
    response = authed_client.get(f"/api/jobs/{job['id']}/logs", params={"limit": 2, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert len(body["logs"]) == 2


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
