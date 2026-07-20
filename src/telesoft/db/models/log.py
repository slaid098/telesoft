"""Edit log model and CRUD helpers."""

from typing import Any

import aiosqlite

from telesoft.db import base

type LogRow = dict[str, Any]

_TABLE = "edit_logs"

_CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES edit_jobs(id) ON DELETE CASCADE,
    message_id INTEGER NOT NULL,
    old_text TEXT,
    success INTEGER NOT NULL,
    error TEXT,
    edited_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES edit_jobs(id) ON DELETE CASCADE
)
""".strip()

_CREATE_INDEXES_SQL: tuple[str, ...] = (
    f"CREATE INDEX IF NOT EXISTS idx_{_TABLE}_job_id ON {_TABLE}(job_id)",
    f"CREATE INDEX IF NOT EXISTS idx_{_TABLE}_message_id ON {_TABLE}(message_id)",
)


async def create_log(  # noqa: PLR0913
    db: aiosqlite.Connection,
    *,
    job_id: int,
    message_id: int,
    old_text: str | None,
    success: bool,
    error: str | None,
    edited_at: str,
) -> LogRow:
    """Insert a new edit log row and return the stored row as a dict."""
    row_id = await base.insert(
        db,
        f"INSERT INTO {_TABLE} (job_id, message_id, old_text, success, error, edited_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (job_id, message_id, old_text, int(success), error, edited_at),
    )
    row = await base.fetchone(db, f"SELECT * FROM {_TABLE} WHERE id = ?", (row_id,))
    assert row is not None
    return row


async def list_logs(
    db: aiosqlite.Connection,
    *,
    job_id: int,
    limit: int = 100,
    offset: int = 0,
) -> list[LogRow]:
    """List log rows for a job ordered by id with optional pagination."""
    return await base.fetchall(
        db,
        f"SELECT * FROM {_TABLE} WHERE job_id = ? ORDER BY id LIMIT ? OFFSET ?",
        (job_id, limit, offset),
    )


async def delete_logs(
    db: aiosqlite.Connection,
    *,
    job_id: int,
) -> int:
    """Delete all log rows for a job. Returns the number of rows removed."""
    cursor = await db.execute(f"DELETE FROM {_TABLE} WHERE job_id = ?", (job_id,))
    deleted = cursor.rowcount
    await cursor.close()
    await db.commit()
    return deleted
