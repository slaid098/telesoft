"""Tests for ``seed_builtin_patterns`` (issue #59).

Verifies that the 4 built-in link patterns are seeded on a fresh DB,
that re-running the seed is idempotent (no duplicates), that custom
patterns survive the seed, and that seeded built-ins cannot be deleted
through the model layer.
"""

from __future__ import annotations

import pytest

from telesoft.db.models import pattern as pattern_model

_EXPECTED_NAMES = {
    "Telegram bot links",
    "Telegram bot links (with groups)",
    "Telegram channel post links",
    "Generic URLs",
}


async def test_seed_inserts_four_builtin_patterns(mock_db) -> None:  # type: ignore[no-untyped-def]
    """On a fresh DB, ``init_db`` already seeded 4 built-in patterns."""
    rows = await pattern_model.list_patterns(mock_db)
    assert len(rows) == 4
    assert all(int(row["is_builtin"]) == 1 for row in rows)
    assert {row["name"] for row in rows} == _EXPECTED_NAMES


async def test_seed_is_idempotent(mock_db) -> None:  # type: ignore[no-untyped-def]
    """Calling ``seed_builtin_patterns`` again inserts nothing."""
    inserted = await pattern_model.seed_builtin_patterns(mock_db)
    assert inserted == 0
    rows = await pattern_model.list_patterns(mock_db)
    assert len(rows) == 4
    assert {row["name"] for row in rows} == _EXPECTED_NAMES


async def test_seed_preserves_custom_patterns(mock_db) -> None:  # type: ignore[no-untyped-def]
    """A custom pattern (``is_builtin=0``) is not wiped or duplicated by seed."""
    custom = await pattern_model.create_pattern(
        mock_db,
        name="My custom pattern",
        pattern=r"https://example\.com",
        description="User-defined",
        is_builtin=0,
        created_at="2026-07-21T00:00:00Z",
    )
    inserted = await pattern_model.seed_builtin_patterns(mock_db)
    assert inserted == 0
    rows = await pattern_model.list_patterns(mock_db)
    assert len(rows) == 5
    assert any(r["id"] == custom["id"] and int(r["is_builtin"]) == 0 for r in rows)


async def test_seed_does_not_collide_with_custom_name(mock_db) -> None:  # type: ignore[no-untyped-def]
    """A custom pattern sharing a name with a built-in does not block the seed
    nor get overwritten — the seed checks ``is_builtin=1`` too."""
    await pattern_model.create_pattern(
        mock_db,
        name="Telegram bot links",
        pattern=r"https://custom\.example",
        description=None,
        is_builtin=0,
        created_at="2026-07-21T00:00:00Z",
    )
    inserted = await pattern_model.seed_builtin_patterns(mock_db)
    assert inserted == 0  # built-in already present from init_db
    rows = await pattern_model.list_patterns(mock_db)
    assert len(rows) == 5
    builtins = [r for r in rows if int(r["is_builtin"]) == 1]
    customs = [r for r in rows if int(r["is_builtin"]) == 0]
    assert len(builtins) == 4
    assert len(customs) == 1


async def test_seeded_builtin_cannot_be_deleted(mock_db) -> None:  # type: ignore[no-untyped-def]
    """A seeded built-in pattern raises PermissionError on delete."""
    rows = await pattern_model.list_patterns(mock_db)
    builtin = rows[0]
    assert int(builtin["is_builtin"]) == 1
    with pytest.raises(PermissionError, match="built-in"):
        await pattern_model.delete_pattern(mock_db, pattern_id=int(builtin["id"]))
    assert await pattern_model.get_pattern(mock_db, pattern_id=int(builtin["id"])) is not None
