"""Shared test fixtures for the telesoft test suite."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from telesoft.config import Settings
from telesoft.main import close_db, init_db


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
async def mock_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Initialize and tear down the app DB against a tmp path."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "telesoft.db"))
    await init_db()
    yield
    await close_db()
