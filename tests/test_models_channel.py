"""Tests for the channel model CRUD helpers."""

from datetime import UTC, datetime

import aiosqlite
import pytest

from telesoft.db.models import channel as channel_model

_NOW = datetime.now(tz=UTC).isoformat()


def _iso(offset_seconds: int = 0) -> str:
    return datetime.now(tz=UTC).isoformat()


async def test_create_and_get_channel(mock_db: aiosqlite.Connection) -> None:
    row = await channel_model.create_channel(
        mock_db,
        telegram_id=1001,
        title="First channel",
        username="first",
        added_at=_NOW,
    )
    assert row["telegram_id"] == 1001
    assert row["title"] == "First channel"
    assert row["username"] == "first"
    assert row["added_at"] == _NOW
    assert row["is_active"] == 1
    fetched = await channel_model.get_channel(mock_db, channel_id=int(row["id"]))
    assert fetched is not None
    assert fetched["id"] == row["id"]


async def test_get_channel_by_telegram_id(mock_db: aiosqlite.Connection) -> None:
    await channel_model.create_channel(
        mock_db,
        telegram_id=2002,
        title="By tg id",
        username=None,
        added_at=_NOW,
    )
    row = await channel_model.get_channel_by_telegram_id(mock_db, telegram_id=2002)
    assert row is not None
    assert row["title"] == "By tg id"
    assert row["username"] is None


async def test_list_channels_active_only(mock_db: aiosqlite.Connection) -> None:
    a = await channel_model.create_channel(
        mock_db, telegram_id=1, title="a", username=None, added_at=_NOW
    )
    b = await channel_model.create_channel(
        mock_db, telegram_id=2, title="b", username=None, added_at=_NOW
    )
    await channel_model.update_channel(mock_db, channel_id=int(b["id"]), is_active=0)
    all_rows = await channel_model.list_channels(mock_db)
    assert len(all_rows) == 2
    active_rows = await channel_model.list_channels(mock_db, active_only=True)
    assert len(active_rows) == 1
    assert active_rows[0]["id"] == a["id"]


async def test_update_channel(mock_db: aiosqlite.Connection) -> None:
    row = await channel_model.create_channel(
        mock_db, telegram_id=3, title="old", username="old_user", added_at=_NOW
    )
    updated = await channel_model.update_channel(
        mock_db,
        channel_id=int(row["id"]),
        title="new title",
        username="new_user",
        is_active=0,
    )
    assert updated is not None
    assert updated["title"] == "new title"
    assert updated["username"] == "new_user"
    assert updated["is_active"] == 0


async def test_update_channel_rejects_unknown_field(
    mock_db: aiosqlite.Connection,
) -> None:
    row = await channel_model.create_channel(
        mock_db, telegram_id=4, title="c", username=None, added_at=_NOW
    )
    with pytest.raises(ValueError, match="Unknown channel field"):
        await channel_model.update_channel(mock_db, channel_id=int(row["id"]), bad_field="x")


async def test_delete_channel(mock_db: aiosqlite.Connection) -> None:
    row = await channel_model.create_channel(
        mock_db, telegram_id=5, title="to delete", username=None, added_at=_NOW
    )
    assert await channel_model.delete_channel(mock_db, channel_id=int(row["id"])) is True
    assert await channel_model.get_channel(mock_db, channel_id=int(row["id"])) is None
    assert await channel_model.delete_channel(mock_db, channel_id=99999) is False


async def test_unique_telegram_id_constraint(mock_db: aiosqlite.Connection) -> None:
    await channel_model.create_channel(
        mock_db, telegram_id=10, title="dup", username=None, added_at=_NOW
    )
    with pytest.raises(aiosqlite.IntegrityError):
        await channel_model.create_channel(
            mock_db, telegram_id=10, title="dup2", username=None, added_at=_iso()
        )
