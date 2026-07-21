"""Pydantic schemas for the Jobs / replace-link API."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from telesoft.db.models import JobRow, LogRow, PatternRow


def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string with trailing ``Z``."""
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class ReplaceLinkRequest(BaseModel):
    """Payload for ``POST /api/channels/{id}/replace-link``.

    The caller provides ``post_link`` (a Telegram post URL or plain message
    id) from which the backend derives ``max_id`` for
    :func:`telesoft.core.telegram.get_last_messages`. The last ``limit``
    posts ending at ``max_id`` are fetched and filtered by ``pattern``.

    ``mode`` selects how *pattern* is interpreted (``"simple"`` wildcards,
    ``"library"`` / ``"advanced"`` raw regex). ``full_replace`` appends
    ``.*`` to the compiled pattern so the whole link is replaced
    (``True``, default, "Полная замена"); when ``False`` only the matched
    prefix is replaced and the tail stays ("Частичная").
    """

    pattern: str
    new_link: str
    post_link: str
    limit: int = Field(default=100, ge=1, le=1000)
    mode: str = "advanced"
    full_replace: bool = True


class PreviewRequest(BaseModel):
    """Payload for ``POST /api/channels/{id}/preview-replace``."""

    pattern: str
    new_link: str
    post_link: str
    mode: str = "advanced"
    full_replace: bool = True
    limit: int = Field(default=100, ge=1, le=1000)


class PreviewItem(BaseModel):
    """A single ``before -> after`` preview pair."""

    message_id: int
    before: str
    after: str
    match_source: str


class PreviewResponse(BaseModel):
    """Response for ``POST /api/channels/{id}/preview-replace``."""

    previews: list[PreviewItem]
    total_matches: int
    compiled_pattern: str


class PatternCreateRequest(BaseModel):
    """Payload for ``POST /api/patterns`` (custom patterns only)."""

    name: str
    pattern: str
    description: str | None = None


class PatternResponse(BaseModel):
    """Pattern library entry returned by the API."""

    id: int
    name: str
    pattern: str
    description: str | None
    is_builtin: bool
    created_at: str

    @classmethod
    def from_row(cls, row: PatternRow) -> "PatternResponse":
        """Build a ``PatternResponse`` from a raw DB row (dict-like)."""
        return cls(
            id=int(row["id"]),
            name=str(row["name"]),
            pattern=str(row["pattern"]),
            description=row["description"],
            is_builtin=bool(row["is_builtin"]),
            created_at=str(row["created_at"]),
        )


class PatternListResponse(BaseModel):
    """List response with patterns and total count."""

    patterns: list[PatternResponse]
    total: int


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
