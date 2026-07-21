"""Tests for ``src/telesoft/db/models/pattern.py``."""

from __future__ import annotations

import pytest

from telesoft.db.models import pattern as pattern_model


async def test_create_pattern_returns_row(mock_db) -> None:  # type: ignore[no-untyped-def]
    row = await pattern_model.create_pattern(
        mock_db,
        name="Basic bot link",
        pattern=r"https://t\.me/bot\?start=\d+",
        description="Generic bot start link",
        is_builtin=0,
        created_at="2026-07-21T00:00:00Z",
    )
    assert row["id"] == 1
    assert row["name"] == "Basic bot link"
    assert row["pattern"] == r"https://t\.me/bot\?start=\d+"
    assert row["description"] == "Generic bot start link"
    assert row["is_builtin"] == 0
    assert row["created_at"] == "2026-07-21T00:00:00Z"


async def test_get_pattern(mock_db) -> None:  # type: ignore[no-untyped-def]
    created = await pattern_model.create_pattern(
        mock_db,
        name="P",
        pattern="x",
        description=None,
        is_builtin=0,
        created_at="2026-07-21T00:00:00Z",
    )
    fetched = await pattern_model.get_pattern(mock_db, pattern_id=int(created["id"]))
    assert fetched is not None
    assert fetched["name"] == "P"


async def test_get_pattern_not_found(mock_db) -> None:  # type: ignore[no-untyped-def]
    assert await pattern_model.get_pattern(mock_db, pattern_id=999) is None


async def test_list_patterns_ordered_by_id(mock_db) -> None:  # type: ignore[no-untyped-def]
    await pattern_model.create_pattern(
        mock_db,
        name="A",
        pattern="a",
        description=None,
        is_builtin=1,
        created_at="2026-07-21T00:00:00Z",
    )
    await pattern_model.create_pattern(
        mock_db,
        name="B",
        pattern="b",
        description=None,
        is_builtin=0,
        created_at="2026-07-21T00:00:01Z",
    )
    rows = await pattern_model.list_patterns(mock_db)
    assert len(rows) == 2
    assert rows[0]["name"] == "A"
    assert rows[1]["name"] == "B"


async def test_delete_pattern_custom(mock_db) -> None:  # type: ignore[no-untyped-def]
    created = await pattern_model.create_pattern(
        mock_db,
        name="C",
        pattern="c",
        description=None,
        is_builtin=0,
        created_at="2026-07-21T00:00:00Z",
    )
    deleted = await pattern_model.delete_pattern(mock_db, pattern_id=int(created["id"]))
    assert deleted is True
    assert await pattern_model.get_pattern(mock_db, pattern_id=int(created["id"])) is None


async def test_delete_pattern_builtin_raises(mock_db) -> None:  # type: ignore[no-untyped-def]
    created = await pattern_model.create_pattern(
        mock_db,
        name="builtin",
        pattern="x",
        description=None,
        is_builtin=1,
        created_at="2026-07-21T00:00:00Z",
    )
    with pytest.raises(PermissionError, match="built-in"):
        await pattern_model.delete_pattern(mock_db, pattern_id=int(created["id"]))
    assert await pattern_model.get_pattern(mock_db, pattern_id=int(created["id"])) is not None


async def test_delete_pattern_not_found(mock_db) -> None:  # type: ignore[no-untyped-def]
    assert await pattern_model.delete_pattern(mock_db, pattern_id=999) is False


async def test_create_pattern_default_is_builtin_zero(mock_db) -> None:  # type: ignore[no-untyped-def]
    """Explicit is_builtin=0 is stored as 0 (router always passes 0)."""
    row = await pattern_model.create_pattern(
        mock_db,
        name="X",
        pattern="x",
        description=None,
        is_builtin=0,
        created_at="2026-07-21T00:00:00Z",
    )
    assert row["is_builtin"] == 0
