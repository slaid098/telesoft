"""Jobs API: replace-link launch, list, detail, logs, cancel.

All endpoints are mounted under ``/api`` (see ``main.py``) and require an
authenticated session via ``require_auth`` applied to the whole router via
``dependencies=[Depends(require_auth)]``.

Job execution is delegated to a process-wide :class:`telesoft.core.runner.JobRunner`
instance attached to the FastAPI app state during lifespan startup. The runner
schedules an :class:`asyncio.Task` per submitted job, gated by a semaphore for
concurrency control, auto-discovers the last N channel posts via Telethon
(``get_last_messages``), regex-filters by pattern, edits each matching post,
and persists status/progress and per-post logs to the database.
"""

from __future__ import annotations

from typing import Any, cast

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi import status as http_status

from telesoft.api.auth import require_auth
from telesoft.core.link_replacer import validate_pattern
from telesoft.core.runner import JobRunner
from telesoft.db.connection import get_db
from telesoft.db.models import channel as channel_model
from telesoft.db.models import job as job_model
from telesoft.db.models import log as log_model
from telesoft.schemas.job import (
    JobListResponse,
    JobResponse,
    LogListResponse,
    LogResponse,
    ReplaceLinkRequest,
    now_iso,
)

router = APIRouter(
    tags=["jobs"],
    dependencies=[Depends(require_auth)],
)


def get_runner(request: Request) -> JobRunner:
    """Return the process-wide :class:`JobRunner` attached to app state."""
    runner: Any = getattr(request.app.state, "job_runner", None)
    if runner is None:  # pragma: no cover — runner is set during lifespan
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job runner not initialised",
        )
    return cast("JobRunner", runner)


async def _get_channel_or_404(
    db: aiosqlite.Connection, channel_id: int
) -> channel_model.ChannelRow:
    """Fetch a channel by id or raise 404."""
    row = await channel_model.get_channel(db, channel_id=channel_id)
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Channel {channel_id} not found",
        )
    return row


async def _get_job_or_404(db: aiosqlite.Connection, job_id: int) -> job_model.JobRow:
    """Fetch a job row by id or raise 404."""
    row = await job_model.get_job(db, job_id=job_id)
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    return row


@router.post(
    "/api/channels/{channel_id}/replace-link",
    status_code=http_status.HTTP_201_CREATED,
)
async def replace_link_endpoint(
    channel_id: int,
    payload: ReplaceLinkRequest,
    runner: JobRunner = Depends(get_runner),
) -> dict[str, Any]:
    """Launch a replace-link job for the given channel.

    Validates the channel (404) and the regex pattern (422). The backend auto-
    discovers the last ``payload.limit`` posts via ``get_last_messages`` and
    filters them by ``payload.pattern`` — the caller does not collect post URLs.
    Creates an ``edit_jobs`` row (``status='pending'``, ``total=0`` — updated
    by the worker once matching posts are known) and submits it to the runner.
    """
    try:
        validate_pattern(payload.pattern)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid pattern: {exc}",
        ) from exc

    async with get_db() as db:
        channel = await _get_channel_or_404(db, channel_id)
        row = await job_model.create_job(
            db,
            channel_id=channel_id,
            pattern=payload.pattern,
            new_link=payload.new_link,
            created_at=now_iso(),
        )

    runner.submit(
        job_id=int(row["id"]),
        chat_id=int(channel["telegram_id"]),
        limit=payload.limit,
        pattern=payload.pattern,
        new_link=payload.new_link,
    )
    return {"job_id": int(row["id"]), "status": "pending"}


@router.get("/api/jobs", response_model=JobListResponse)
async def list_jobs_endpoint(
    channel_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> JobListResponse:
    """List jobs, optionally filtered by channel and/or status."""
    async with get_db() as db:
        rows = await job_model.list_jobs(
            db,
            channel_id=channel_id,
            status=status_filter,
            limit=limit,
            offset=offset,
        )
    jobs = [JobResponse.from_row(row) for row in rows]
    return JobListResponse(jobs=jobs, total=len(jobs))


@router.get("/api/jobs/{job_id}", response_model=JobResponse)
async def get_job_endpoint(job_id: int) -> JobResponse:
    """Return a single job by id."""
    async with get_db() as db:
        row = await _get_job_or_404(db, job_id)
    return JobResponse.from_row(row)


@router.get("/api/jobs/{job_id}/logs", response_model=LogListResponse)
async def get_job_logs_endpoint(
    job_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> LogListResponse:
    """Return the logs for a job."""
    async with get_db() as db:
        await _get_job_or_404(db, job_id)
        rows = await log_model.list_logs(db, job_id=job_id, limit=limit, offset=offset)
    logs = [LogResponse.from_row(row) for row in rows]
    return LogListResponse(logs=logs, total=len(logs))


@router.post("/api/jobs/{job_id}/cancel")
async def cancel_job_endpoint(
    job_id: int,
    runner: JobRunner = Depends(get_runner),
) -> dict[str, Any]:
    """Cancel a running or pending job. 409 if already terminal."""
    async with get_db() as db:
        existing = await _get_job_or_404(db, job_id)
    current = str(existing["status"])
    if current in ("done", "failed", "cancelled"):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"Job {job_id} is already {current}",
        )
    runner.cancel(job_id)
    async with get_db() as db:
        await job_model.update_job_status(
            db,
            job_id=job_id,
            status="cancelled",
            completed_at=now_iso(),
        )
        row = await job_model.get_job(db, job_id=job_id)
    assert row is not None
    return {"job_id": job_id, "status": "cancelled"}
