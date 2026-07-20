"""Tests for the edit_jobs model CRUD helpers."""

from datetime import UTC, datetime

import aiosqlite

from telesoft.db.models import channel as channel_model
from telesoft.db.models import job as job_model
from telesoft.db.models import log as log_model

_NOW = datetime.now(tz=UTC).isoformat()


def _iso() -> str:
    return datetime.now(tz=UTC).isoformat()


async def _make_channel(db: aiosqlite.Connection, telegram_id: int = 1) -> int:
    row = await channel_model.create_channel(
        db,
        telegram_id=telegram_id,
        title=f"ch{telegram_id}",
        username=None,
        added_at=_NOW,
    )
    return int(row["id"])


async def test_create_and_get_job(mock_db: aiosqlite.Connection) -> None:
    channel_id = await _make_channel(mock_db, telegram_id=100)
    row = await job_model.create_job(
        mock_db,
        channel_id=channel_id,
        pattern="https://old.link",
        new_link="https://new.link",
        created_at=_NOW,
    )
    assert row["channel_id"] == channel_id
    assert row["pattern"] == "https://old.link"
    assert row["new_link"] == "https://new.link"
    assert row["status"] == "pending"
    assert row["total"] == 0
    assert row["edited"] == 0
    assert row["failed"] == 0
    assert row["completed_at"] is None
    fetched = await job_model.get_job(mock_db, job_id=int(row["id"]))
    assert fetched is not None
    assert fetched["id"] == row["id"]


async def test_list_jobs_filter_by_channel(mock_db: aiosqlite.Connection) -> None:
    ch_a = await _make_channel(mock_db, telegram_id=10)
    ch_b = await _make_channel(mock_db, telegram_id=20)
    j1 = await job_model.create_job(
        mock_db, channel_id=ch_a, pattern="p", new_link="l", created_at=_NOW
    )
    j2 = await job_model.create_job(
        mock_db, channel_id=ch_b, pattern="p", new_link="l", created_at=_NOW
    )
    rows = await job_model.list_jobs(mock_db, channel_id=ch_a)
    assert {r["id"] for r in rows} == {j1["id"]}
    rows_b = await job_model.list_jobs(mock_db, channel_id=ch_b)
    assert {r["id"] for r in rows_b} == {j2["id"]}


async def test_list_jobs_filter_by_status(mock_db: aiosqlite.Connection) -> None:
    channel_id = await _make_channel(mock_db, telegram_id=30)
    j1 = await job_model.create_job(
        mock_db, channel_id=channel_id, pattern="p", new_link="l", created_at=_NOW
    )
    await job_model.create_job(
        mock_db, channel_id=channel_id, pattern="p", new_link="l", created_at=_NOW
    )
    await job_model.update_job_status(mock_db, job_id=int(j1["id"]), status="completed")
    pending = await job_model.list_jobs(mock_db, status="pending")
    completed = await job_model.list_jobs(mock_db, status="completed")
    assert len(pending) == 1
    assert len(completed) == 1
    assert completed[0]["status"] == "completed"


async def test_update_job_status(mock_db: aiosqlite.Connection) -> None:
    channel_id = await _make_channel(mock_db, telegram_id=40)
    row = await job_model.create_job(
        mock_db, channel_id=channel_id, pattern="p", new_link="l", created_at=_NOW
    )
    updated = await job_model.update_job_status(
        mock_db,
        job_id=int(row["id"]),
        status="running",
        total=10,
        edited=3,
        failed=1,
    )
    assert updated is not None
    assert updated["status"] == "running"
    assert updated["total"] == 10
    assert updated["edited"] == 3
    assert updated["failed"] == 1
    finished = await job_model.update_job_status(
        mock_db,
        job_id=int(row["id"]),
        status="completed",
        completed_at=_iso(),
    )
    assert finished is not None
    assert finished["completed_at"] is not None


async def test_delete_job_cascade_logs(mock_db: aiosqlite.Connection) -> None:
    channel_id = await _make_channel(mock_db, telegram_id=50)
    job = await job_model.create_job(
        mock_db, channel_id=channel_id, pattern="p", new_link="l", created_at=_NOW
    )
    await log_model.create_log(
        mock_db,
        job_id=int(job["id"]),
        message_id=1,
        old_text="old",
        success=True,
        error=None,
        edited_at=_NOW,
    )
    await log_model.create_log(
        mock_db,
        job_id=int(job["id"]),
        message_id=2,
        old_text="old2",
        success=False,
        error="boom",
        edited_at=_NOW,
    )
    logs = await log_model.list_logs(mock_db, job_id=int(job["id"]))
    assert len(logs) == 2
    assert await job_model.delete_job(mock_db, job_id=int(job["id"])) is True
    logs_after = await log_model.list_logs(mock_db, job_id=int(job["id"]))
    assert logs_after == []
