"""Base database access utilities."""

from collections.abc import Iterable
from typing import Any

import aiosqlite

type Row = dict[str, Any]


async def execute(db: aiosqlite.Connection, sql: str, params: tuple[Any, ...] = ()) -> None:
    """Execute a single write statement and commit."""
    await db.execute(sql, params)
    await db.commit()


async def executemany(
    db: aiosqlite.Connection,
    sql: str,
    params_seq: Iterable[tuple[Any, ...]],
) -> None:
    """Execute a statement many times and commit."""
    await db.executemany(sql, params_seq)
    await db.commit()


async def insert(db: aiosqlite.Connection, sql: str, params: tuple[Any, ...]) -> int:
    """Execute an INSERT and return the ``lastrowid`` of the new row."""
    cursor = await db.execute(sql, params)
    rowid = cursor.lastrowid
    await cursor.close()
    await db.commit()
    assert rowid is not None
    return rowid


async def fetchone(db: aiosqlite.Connection, sql: str, params: tuple[Any, ...] = ()) -> Row | None:
    """Execute a query and return the first row as a dict, or ``None``."""
    async with await db.execute(sql, params) as cur:
        row = await cur.fetchone()
    if row is None:
        return None
    return dict(row)


async def fetchall(db: aiosqlite.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[Row]:
    """Execute a query and return all rows as a list of dicts."""
    async with await db.execute(sql, params) as cur:
        rows = await cur.fetchall()
    return [dict(row) for row in rows]
