"""Tests for the edit_logs model CRUD helpers."""

from datetime import UTC, datetime

import aiosqlite

from telesoft.db.models import channel as channel_model
from telesoft.db.models import job as job_model
from telesoft.db.models import log as log_model

_NOW = datetime.now(tz=UTC).isoformat()


def _iso() -> str:
    return datetime.now(tz=UTC).isoformat()


async def _make_job(db: aiosqlite.Connection, telegram_id: int = 1) -> int:
    ch = await channel_model.create_channel(
        db,
        telegram_id=telegram_id,
        title=f"ch{telegram_id}",
        username=None,
        added_at=_NOW,
    )
    job = await job_model.create_job(
        db,
        channel_id=int(ch["id"]),
        pattern="p",
        new_link="l",
        created_at=_NOW,
    )
    return int(job["id"])


async def test_create_and_list_logs(mock_db: aiosqlite.Connection) -> None:
    job_id = await _make_job(mock_db, telegram_id=10)
    log = await log_model.create_log(
        mock_db,
        job_id=job_id,
        message_id=100,
        old_text="hello",
        success=True,
        error=None,
        edited_at=_NOW,
    )
    assert log["job_id"] == job_id
    assert log["message_id"] == 100
    assert log["old_text"] == "hello"
    assert log["success"] == 1
    assert log["error"] is None
    assert log["edited_at"] == _NOW
    rows = await log_model.list_logs(mock_db, job_id=job_id)
    assert len(rows) == 1
    assert rows[0]["id"] == log["id"]


async def test_list_logs_limit_offset(mock_db: aiosqlite.Connection) -> None:
    job_id = await _make_job(mock_db, telegram_id=20)
    for i in range(5):
        await log_model.create_log(
            mock_db,
            job_id=job_id,
            message_id=i,
            old_text="x",
            success=True,
            error=None,
            edited_at=_NOW,
        )
    page1 = await log_model.list_logs(mock_db, job_id=job_id, limit=2, offset=0)
    page2 = await log_model.list_logs(mock_db, job_id=job_id, limit=2, offset=2)
    page3 = await log_model.list_logs(mock_db, job_id=job_id, limit=2, offset=4)
    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1
    ids = {r["id"] for r in page1} | {r["id"] for r in page2} | {r["id"] for r in page3}
    assert len(ids) == 5


async def test_delete_logs(mock_db: aiosqlite.Connection) -> None:
    job_id = await _make_job(mock_db, telegram_id=30)
    for i in range(3):
        await log_model.create_log(
            mock_db,
            job_id=job_id,
            message_id=i,
            old_text="x",
            success=True,
            error=None,
            edited_at=_NOW,
        )
    deleted = await log_model.delete_logs(mock_db, job_id=job_id)
    assert deleted == 3
    assert await log_model.list_logs(mock_db, job_id=job_id) == []
    assert await log_model.delete_logs(mock_db, job_id=job_id) == 0


async def test_delete_channel_cascade_jobs_logs(mock_db: aiosqlite.Connection) -> None:
    ch = await channel_model.create_channel(
        mock_db,
        telegram_id=40,
        title="ch",
        username=None,
        added_at=_NOW,
    )
    job = await job_model.create_job(
        mock_db,
        channel_id=int(ch["id"]),
        pattern="p",
        new_link="l",
        created_at=_NOW,
    )
    await log_model.create_log(
        mock_db,
        job_id=int(job["id"]),
        message_id=1,
        old_text="x",
        success=True,
        error=None,
        edited_at=_NOW,
    )
    deleted = await channel_model.delete_channel(mock_db, channel_id=int(ch["id"]))
    assert deleted is True
    assert await job_model.get_job(mock_db, job_id=int(job["id"])) is None
    assert await log_model.list_logs(mock_db, job_id=int(job["id"])) == []
