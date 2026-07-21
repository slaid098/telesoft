"""Async SQLite connection management."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

from telesoft.config import Settings
from telesoft.db.models import channel as channel_model
from telesoft.db.models import job as job_model
from telesoft.db.models import log as log_model
from telesoft.db.models import pattern as pattern_model


@dataclass
class _State:
    db: aiosqlite.Connection | None = None


_state = _State()


def get_db_path() -> str:
    """Resolve the database file path from ``Settings`` and ensure the parent dir exists."""
    db_path = Settings.from_env().db_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return db_path


async def init_db() -> aiosqlite.Connection:
    """Open the database (creating it if needed) and apply connection pragmas + schema."""
    if _state.db is not None:
        return _state.db
    db_path = get_db_path()
    connection = await aiosqlite.connect(db_path)
    connection.row_factory = aiosqlite.Row
    await connection.execute("PRAGMA journal_mode=WAL")
    await connection.execute("PRAGMA foreign_keys=ON")
    await connection.commit()
    await _create_schema(connection)
    _state.db = connection
    return connection


async def _create_schema(db: aiosqlite.Connection) -> None:
    """Create all tables and indexes (idempotent)."""
    statements: list[str] = [
        channel_model._CREATE_SQL,
        job_model._CREATE_SQL,
        log_model._CREATE_SQL,
        pattern_model._CREATE_SQL,
    ]
    indexes: list[str] = list(channel_model._CREATE_INDEXES_SQL)
    indexes.extend(job_model._CREATE_INDEXES_SQL)
    indexes.extend(log_model._CREATE_INDEXES_SQL)
    indexes.extend(pattern_model._CREATE_INDEXES_SQL)
    for statement in statements:
        await db.execute(statement)
    for index in indexes:
        await db.execute(index)
    await db.commit()
    await pattern_model.seed_builtin_patterns(db)


async def close_db() -> None:
    """Close the shared database connection if it is open."""
    db = _state.db
    if db is not None:
        await db.close()
        _state.db = None


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Yield the shared database connection, initialising it lazily."""
    db = _state.db
    if db is None:
        db = await init_db()
    yield db
