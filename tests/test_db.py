"""Tests for the DB connection layer."""

from pathlib import Path

import aiosqlite
import pytest

from telesoft.db import connection
from telesoft.db.models import channel as channel_model
from telesoft.db.models import job as job_model
from telesoft.db.models import log as log_model


async def test_init_db_creates_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "telesoft.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    await connection.init_db()
    assert db_path.exists()
    await connection.close_db()


async def test_init_db_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "telesoft.db"))
    conn1 = await connection.init_db()
    conn2 = await connection.init_db()
    assert conn1 is conn2
    await connection.close_db()


async def test_pragmas_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "telesoft.db"))
    db = await connection.init_db()
    async with await db.execute("PRAGMA journal_mode") as cur:
        mode = await cur.fetchone()
    assert mode[0].lower() == "wal"
    async with await db.execute("PRAGMA foreign_keys") as cur:
        fk = await cur.fetchone()
    assert fk[0] == 1
    await connection.close_db()


async def test_schema_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "telesoft.db"))
    db = await connection.init_db()
    expected_tables = {channel_model._TABLE, job_model._TABLE, log_model._TABLE}
    async with await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ) as cur:
        rows = await cur.fetchall()
    tables = {row[0] for row in rows}
    assert expected_tables.issubset(tables)
    await connection.close_db()


async def test_get_db_yields_connection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "telesoft.db"))
    async with connection.get_db() as db:
        assert isinstance(db, aiosqlite.Connection)
    await connection.close_db()


async def test_close_db_noop_when_uninitialized() -> None:
    await connection.close_db()
