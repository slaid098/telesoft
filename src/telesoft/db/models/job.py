"""Edit job model and CRUD helpers."""

from typing import Any

import aiosqlite

from telesoft.db import base

type JobRow = dict[str, Any]

_TABLE = "edit_jobs"

_CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    pattern TEXT NOT NULL,
    new_link TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    total INTEGER NOT NULL DEFAULT 0,
    edited INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE
)
""".strip()

_CREATE_INDEXES_SQL: tuple[str, ...] = (
    f"CREATE INDEX IF NOT EXISTS idx_{_TABLE}_channel_id ON {_TABLE}(channel_id)",
    f"CREATE INDEX IF NOT EXISTS idx_{_TABLE}_status ON {_TABLE}(status)",
    f"CREATE INDEX IF NOT EXISTS idx_{_TABLE}_created_at ON {_TABLE}(created_at)",
)


async def create_job(
    db: aiosqlite.Connection,
    *,
    channel_id: int,
    pattern: str,
    new_link: str,
    created_at: str,
) -> JobRow:
    """Insert a new edit job row and return the stored row as a dict."""
    row_id = await base.insert(
        db,
        f"INSERT INTO {_TABLE} (channel_id, pattern, new_link, created_at) VALUES (?, ?, ?, ?)",
        (channel_id, pattern, new_link, created_at),
    )
    row = await get_job(db, job_id=row_id)
    assert row is not None
    return row


async def get_job(
    db: aiosqlite.Connection,
    *,
    job_id: int,
) -> JobRow | None:
    """Fetch a single job row by primary key."""
    return await base.fetchone(db, f"SELECT * FROM {_TABLE} WHERE id = ?", (job_id,))


async def list_jobs(
    db: aiosqlite.Connection,
    *,
    channel_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[JobRow]:
    """List job rows, optionally filtered by channel and/or status, newest first."""
    clauses: list[str] = []
    params: list[Any] = []
    if channel_id is not None:
        clauses.append("channel_id = ?")
        params.append(channel_id)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"SELECT * FROM {_TABLE} {where} ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    return await base.fetchall(db, query, tuple(params))


async def count_jobs(
    db: aiosqlite.Connection,
    *,
    channel_id: int | None = None,
    status: str | None = None,
) -> int:
    """Count job rows matching the same filters as :func:`list_jobs` (no LIMIT/OFFSET)."""
    clauses: list[str] = []
    params: list[Any] = []
    if channel_id is not None:
        clauses.append("channel_id = ?")
        params.append(channel_id)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"SELECT COUNT(*) AS cnt FROM {_TABLE} {where}"
    row = await base.fetchone(db, query, tuple(params))
    if row is None:
        return 0
    return int(row["cnt"])


async def update_job_status(  # noqa: PLR0913
    db: aiosqlite.Connection,
    *,
    job_id: int,
    status: str,
    total: int | None = None,
    edited: int | None = None,
    failed: int | None = None,
    completed_at: str | None = None,
) -> JobRow | None:
    """Update job status and optional progress counters / completion timestamp."""
    columns: list[str] = ["status = ?"]
    params: list[Any] = [status]
    if total is not None:
        columns.append("total = ?")
        params.append(total)
    if edited is not None:
        columns.append("edited = ?")
        params.append(edited)
    if failed is not None:
        columns.append("failed = ?")
        params.append(failed)
    if completed_at is not None:
        columns.append("completed_at = ?")
        params.append(completed_at)
    params.append(job_id)
    await base.execute(
        db,
        f"UPDATE {_TABLE} SET {', '.join(columns)} WHERE id = ?",
        tuple(params),
    )
    return await get_job(db, job_id=job_id)


async def delete_job(
    db: aiosqlite.Connection,
    *,
    job_id: int,
) -> bool:
    """Delete a job row by id. Returns True if a row was removed."""
    cursor = await db.execute(f"DELETE FROM {_TABLE} WHERE id = ?", (job_id,))
    deleted = cursor.rowcount
    await cursor.close()
    await db.commit()
    return deleted > 0
