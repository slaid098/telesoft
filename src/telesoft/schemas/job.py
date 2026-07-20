"""Pydantic schemas for the Jobs / replace-link API."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from telesoft.db.models import JobRow, LogRow


def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string with trailing ``Z``."""
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class ReplaceLinkRequest(BaseModel):
    """Payload for ``POST /api/channels/{id}/replace-link``.

    The backend auto-discovers the last ``limit`` channel posts via
    :func:`telesoft.core.telegram.get_last_messages` and filters them by
    ``pattern`` — the caller no longer collects post URLs manually.
    """

    pattern: str
    new_link: str
    limit: int = Field(default=100, ge=1, le=1000)


class JobResponse(BaseModel):
    """Job representation returned by the API."""

    id: int
    channel_id: int
    pattern: str
    new_link: str
    status: str
    total: int
    edited: int
    failed: int
    created_at: str
    completed_at: str | None

    @classmethod
    def from_row(cls, row: JobRow) -> "JobResponse":
        """Build a ``JobResponse`` from a raw DB row (dict-like)."""
        return cls(
            id=int(row["id"]),
            channel_id=int(row["channel_id"]),
            pattern=str(row["pattern"]),
            new_link=str(row["new_link"]),
            status=str(row["status"]),
            total=int(row["total"]),
            edited=int(row["edited"]),
            failed=int(row["failed"]),
            created_at=str(row["created_at"]),
            completed_at=row["completed_at"],
        )


class JobListResponse(BaseModel):
    """List response with jobs and total count."""

    jobs: list[JobResponse]
    total: int


class LogResponse(BaseModel):
    """Edit log representation returned by the API."""

    id: int
    job_id: int
    message_id: int
    old_text: str | None
    success: bool
    error: str | None
    edited_at: str

    @classmethod
    def from_row(cls, row: LogRow) -> "LogResponse":
        """Build a ``LogResponse`` from a raw DB row (dict-like)."""
        return cls(
            id=int(row["id"]),
            job_id=int(row["job_id"]),
            message_id=int(row["message_id"]),
            old_text=row["old_text"],
            success=bool(row["success"]),
            error=row["error"],
            edited_at=str(row["edited_at"]),
        )


class LogListResponse(BaseModel):
    """List response with logs and total count."""

    logs: list[LogResponse]
    total: int


class WsEvent(BaseModel):
    """Schema for a single WebSocket event frame.

    The fields are all optional except ``type`` so a single model covers
    ``job_started``, ``progress``, ``completed``, ``failed`` and ``cancelled``.
    """

    type: str
    job_id: int | None = None
    edited: int | None = None
    failed: int | None = None
    total: int | None = None
    message_id: int | None = None
    error: str | None = None

    @classmethod
    def from_event(cls, event: Any) -> "WsEvent":
        """Build a ``WsEvent`` from an :class:`Event` payload."""
        data: dict[str, Any] = {"type": event.type}
        data.update(event.data)
        return cls(**data)
