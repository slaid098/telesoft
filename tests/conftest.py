"""Shared test fixtures for the telesoft test suite."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from telesoft.config import Settings
from telesoft.core import telegram as telegram_module
from telesoft.core.events import EventBus
from telesoft.core.runner import JobRunner
from telesoft.db import connection
from telesoft.db.models import channel as channel_model
from telesoft.db.models import job as job_model
from telesoft.main import app

type ChannelFactory = Callable[..., Awaitable[channel_model.ChannelRow]]
type JobFactory = Callable[..., Awaitable[job_model.JobRow]]


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """A ``Settings`` instance built from a deterministic, isolated env."""
    for var in (
        "ADMIN_USERNAME",
        "ADMIN_PASSWORD",
        "SECRET_KEY",
        "HOST",
        "PORT",
        "LOG_LEVEL",
        "DB_PATH",
        "TELEGRAM_API_ID",
        "TELEGRAM_API_HASH",
        "TELEGRAM_BOT_TOKEN",
        "SESSION_PATH",
        "JOBS_MAX_CONCURRENCY",
    ):
        monkeypatch.delenv(var, raising=False)

    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long-for-testing")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "test-hash")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    return Settings.from_env()


@pytest.fixture
async def mock_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[aiosqlite.Connection]:
    """Initialize the app DB against a tmp path, yield the connection, then close."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "telesoft.db"))
    db = await connection.init_db()
    yield db
    await connection.close_db()


@pytest.fixture
async def authed_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> AsyncIterator[TestClient]:
    """A TestClient with a logged-in admin session and an isolated temp DB."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long-for-testing")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "telesoft.db"))
    with TestClient(app) as c:
        resp = c.post("/api/auth/login", json={"username": "admin", "password": "secret"})
        assert resp.status_code == 200
        yield c


@pytest.fixture
async def create_channel(mock_db: aiosqlite.Connection) -> ChannelFactory:
    """Async factory that inserts a channel and returns the stored row."""

    async def _make(
        *,
        telegram_id: int = 100,
        title: str = "Test channel",
        username: str | None = "test_channel",
        added_at: str = "2026-07-20T00:00:00+00:00",
    ) -> channel_model.ChannelRow:
        return await channel_model.create_channel(
            mock_db,
            telegram_id=telegram_id,
            title=title,
            username=username,
            added_at=added_at,
        )

    return _make


@pytest.fixture
async def create_job(mock_db: aiosqlite.Connection, create_channel: ChannelFactory) -> JobFactory:
    """Async factory that inserts a job (creating a channel first if needed) and returns the row."""

    async def _make(
        *,
        channel_id: int | None = None,
        pattern: str = "https://old.link",
        new_link: str = "https://new.link",
        created_at: str = "2026-07-20T00:00:00+00:00",
        telegram_id: int = 100,
    ) -> job_model.JobRow:
        if channel_id is None:
            channel = await create_channel(telegram_id=telegram_id)
            channel_id = int(channel["id"])
        return await job_model.create_job(
            mock_db,
            channel_id=channel_id,
            pattern=pattern,
            new_link=new_link,
            created_at=created_at,
        )

    return _make


@dataclass
class MockMessage:
    """Minimal Message-like object for testing telegram client wrappers."""

    id: int
    text: str
    chat_id: int
    message: str = ""


@pytest.fixture
def mock_message() -> MockMessage:
    """A single Message-like object used by the telethon mock."""
    return MockMessage(id=123, text="hello", chat_id=-1001234567890, message="hello")


@pytest.fixture
async def mock_telethon_client(
    mock_message: MockMessage,
    mock_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncMock]:
    """Patch TelegramClient so real get_client/start_client exercise against a mock."""
    client = AsyncMock()
    client.get_messages.return_value = [mock_message]
    client.edit_message.return_value = mock_message
    client.get_entity.return_value = AsyncMock(id=-1001234567890, title="Test channel")
    me_mock = AsyncMock()
    me_mock.id = 6164770162
    me_mock.username = "server10bot"
    me_mock.first_name = "Tester"
    me_mock.bot = True
    client.get_me.return_value = me_mock
    client.start = AsyncMock()
    client.disconnect = AsyncMock()
    client.is_connected.return_value = True

    def _fake_constructor(*_args: object, **_kwargs: object) -> AsyncMock:
        return client

    monkeypatch.setattr(telegram_module, "TelegramClient", _fake_constructor)

    telegram_module._state.client = None
    telegram_module._state.started = False
    yield client
    telegram_module._state.client = None
    telegram_module._state.started = False


@pytest.fixture
def mock_telethon_get_message(
    monkeypatch: pytest.MonkeyPatch, mock_message: MockMessage
) -> AsyncMock:
    """Monkeypatch ``core.telegram.get_message`` to return *mock_message* by id.

    Returns the AsyncMock so individual tests can override the return value
    (e.g. to None for "not found" scenarios) or assert call args.
    """
    get_mock = AsyncMock(return_value=mock_message)
    monkeypatch.setattr(telegram_module, "get_message", get_mock)
    return get_mock


@pytest.fixture
def mock_telethon_edit_message(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Monkeypatch ``core.telegram.edit_message`` to a no-op AsyncMock."""
    edit_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(telegram_module, "edit_message", edit_mock)
    return edit_mock


def _install_runner(
    work_fn: Callable[..., Awaitable[None]] | None = None,
) -> tuple[JobRunner, EventBus]:
    """Replace ``app.state.job_runner`` and ``app.state.event_bus`` for one test."""
    bus = EventBus()
    runner = JobRunner(max_concurrency=2, event_bus=bus)
    runner.start()
    app.state.job_runner = runner
    app.state.event_bus = bus
    return runner, bus


def _restore_default_runner() -> JobRunner:
    """Rebuild a default runner so subsequent fixtures/tests still work."""
    bus = EventBus()
    runner = JobRunner(max_concurrency=3, event_bus=bus)
    runner.start()
    app.state.job_runner = runner
    app.state.event_bus = bus
    return runner


@pytest.fixture
def mock_runner() -> AsyncIterator[JobRunner]:
    """Replace ``app.state.job_runner`` with an in-memory runner + fresh EventBus.

    The runner is started; the previous state is restored after the test.
    """
    prev_runner = getattr(app.state, "job_runner", None)
    prev_bus = getattr(app.state, "event_bus", None)
    bus = EventBus()
    runner = JobRunner(max_concurrency=2, event_bus=bus)
    runner.start()
    app.state.job_runner = runner
    app.state.event_bus = bus
    yield runner
    if prev_runner is not None:
        app.state.job_runner = prev_runner
    if prev_bus is not None:
        app.state.event_bus = prev_bus
