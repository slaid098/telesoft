"""Shared test fixtures for the telesoft test suite."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import aiosqlite
import pytest

from telesoft.config import Settings
from telesoft.db import connection
from telesoft.db.models import channel as channel_model
from telesoft.db.models import job as job_model

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
    ):
        monkeypatch.delenv(var, raising=False)

    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret123")
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
