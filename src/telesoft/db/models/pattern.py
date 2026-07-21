"""Pattern library model and CRUD helpers.

Stores reusable link patterns (built-in + custom) so users can pick one
from a list instead of writing a regex by hand. Built-in patterns
(``is_builtin=1``) cannot be deleted — they are seeded in PR#3 (see
issue #55).
"""

from typing import Any

import aiosqlite

from telesoft.db import base

type PatternRow = dict[str, Any]

_TABLE = "link_patterns"

_CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    pattern TEXT NOT NULL,
    description TEXT,
    is_builtin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
)
""".strip()

_CREATE_INDEXES_SQL: tuple[str, ...] = (
    f"CREATE INDEX IF NOT EXISTS idx_{_TABLE}_name ON {_TABLE}(name)",
)


async def create_pattern(  # noqa: PLR0913
    db: aiosqlite.Connection,
    *,
    name: str,
    pattern: str,
    description: str | None,
    is_builtin: int,
    created_at: str,
) -> PatternRow:
    """Insert a new pattern row and return the stored row as a dict."""
    row_id = await base.insert(
        db,
        f"INSERT INTO {_TABLE} (name, pattern, description, is_builtin, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, pattern, description, is_builtin, created_at),
    )
    row = await get_pattern(db, pattern_id=row_id)
    assert row is not None
    return row


async def get_pattern(
    db: aiosqlite.Connection,
    *,
    pattern_id: int,
) -> PatternRow | None:
    """Fetch a single pattern row by primary key."""
    return await base.fetchone(db, f"SELECT * FROM {_TABLE} WHERE id = ?", (pattern_id,))


async def list_patterns(db: aiosqlite.Connection) -> list[PatternRow]:
    """Return all pattern rows ordered by id (built-ins first by convention)."""
    return await base.fetchall(db, f"SELECT * FROM {_TABLE} ORDER BY id")


async def delete_pattern(
    db: aiosqlite.Connection,
    *,
    pattern_id: int,
) -> bool:
    """Delete a pattern by id. Returns True if a row was removed.

    Refuses to delete a built-in pattern (``is_builtin=1``) by raising
    :class:`PermissionError`; the router maps that to HTTP 403.
    """
    row = await get_pattern(db, pattern_id=pattern_id)
    if row is None:
        return False
    if int(row["is_builtin"]) == 1:
        msg = f"cannot delete built-in pattern {pattern_id}"
        raise PermissionError(msg)
    cursor = await db.execute(f"DELETE FROM {_TABLE} WHERE id = ?", (pattern_id,))
    deleted = cursor.rowcount
    await cursor.close()
    await db.commit()
    return deleted > 0
