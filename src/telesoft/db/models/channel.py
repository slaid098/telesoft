"""Channel model and CRUD helpers."""

from typing import Any

import aiosqlite

from telesoft.db import base

type ChannelRow = dict[str, Any]

_TABLE = "channels"

_CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL UNIQUE,
    title TEXT NOT NULL,
    username TEXT,
    added_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
)
""".strip()

_CREATE_INDEXES_SQL: tuple[str, ...] = (
    f"CREATE INDEX IF NOT EXISTS idx_{_TABLE}_telegram_id ON {_TABLE}(telegram_id)",
    f"CREATE INDEX IF NOT EXISTS idx_{_TABLE}_is_active ON {_TABLE}(is_active)",
)

_ALLOWED_UPDATE_FIELDS = ("title", "username", "is_active")


async def create_channel(
    db: aiosqlite.Connection,
    *,
    telegram_id: int,
    title: str,
    username: str | None,
    added_at: str,
) -> ChannelRow:
    """Insert a new channel and return the stored row as a dict."""
    row_id = await base.insert(
        db,
        f"INSERT INTO {_TABLE} (telegram_id, title, username, added_at) VALUES (?, ?, ?, ?)",
        (telegram_id, title, username, added_at),
    )
    row = await get_channel(db, channel_id=row_id)
    assert row is not None
    return row


async def get_channel(
    db: aiosqlite.Connection,
    *,
    channel_id: int,
) -> ChannelRow | None:
    """Fetch a single channel by primary key."""
    return await base.fetchone(db, f"SELECT * FROM {_TABLE} WHERE id = ?", (channel_id,))


async def get_channel_by_telegram_id(
    db: aiosqlite.Connection,
    *,
    telegram_id: int,
) -> ChannelRow | None:
    """Fetch a single channel by its Telegram id."""
    return await base.fetchone(
        db,
        f"SELECT * FROM {_TABLE} WHERE telegram_id = ?",
        (telegram_id,),
    )


async def list_channels(
    db: aiosqlite.Connection,
    *,
    active_only: bool = False,
) -> list[ChannelRow]:
    """Return channels ordered by id, optionally restricted to active ones."""
    if active_only:
        return await base.fetchall(
            db,
            f"SELECT * FROM {_TABLE} WHERE is_active = 1 ORDER BY id",
        )
    return await base.fetchall(db, f"SELECT * FROM {_TABLE} ORDER BY id")


async def update_channel(
    db: aiosqlite.Connection,
    *,
    channel_id: int,
    **fields: str | int | None,
) -> ChannelRow | None:
    """Patch channel fields identified by id.

    Only ``title``, ``username`` and ``is_active`` are allowed.
    """
    for key in fields:
        if key not in _ALLOWED_UPDATE_FIELDS:
            msg = f"Unknown channel field: {key}"
            raise ValueError(msg)
    columns: list[str] = []
    params: list[Any] = []
    for key, value in fields.items():
        columns.append(f"{key} = ?")
        params.append(value)
    if not columns:
        return await get_channel(db, channel_id=channel_id)
    params.append(channel_id)
    await base.execute(
        db,
        f"UPDATE {_TABLE} SET {', '.join(columns)} WHERE id = ?",
        tuple(params),
    )
    return await get_channel(db, channel_id=channel_id)


async def delete_channel(
    db: aiosqlite.Connection,
    *,
    channel_id: int,
) -> bool:
    """Delete a channel by id. Returns True if a row was removed."""
    cursor = await db.execute(f"DELETE FROM {_TABLE} WHERE id = ?", (channel_id,))
    deleted = cursor.rowcount
    await cursor.close()
    await db.commit()
    return deleted > 0
