"""Pydantic schemas for the Channels API."""

from datetime import UTC, datetime

from pydantic import BaseModel, model_validator

from telesoft.db.models import ChannelRow


class ChannelCreate(BaseModel):
    """Payload for creating a channel."""

    telegram_id: int
    title: str
    username: str | None = None


class ChannelUpdate(BaseModel):
    """Partial channel payload for ``PATCH /api/channels/{id}``.

    At least one of the optional fields must be provided.
    """

    title: str | None = None
    username: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> "ChannelUpdate":
        if self.title is None and self.username is None and self.is_active is None:
            msg = "At least one field must be provided"
            raise ValueError(msg)
        return self


class ChannelResponse(BaseModel):
    """Channel representation returned by the API."""

    id: int
    telegram_id: int
    title: str
    username: str | None
    is_active: bool
    added_at: str

    @classmethod
    def from_row(cls, row: ChannelRow) -> "ChannelResponse":
        """Build a ``ChannelResponse`` from a raw DB row (dict-like)."""
        return cls(
            id=int(row["id"]),
            telegram_id=int(row["telegram_id"]),
            title=str(row["title"]),
            username=row["username"],
            is_active=bool(row["is_active"]),
            added_at=str(row["added_at"]),
        )


class ChannelListResponse(BaseModel):
    """List response with channels and total count."""

    channels: list[ChannelResponse]
    total: int


def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string with trailing ``Z``."""
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
