"""Channels API: CRUD endpoints for managing Telegram channels.

All endpoints are mounted under ``/api/channels`` (see ``main.py``) and
require an authenticated session via ``require_auth`` applied to the whole
router via ``dependencies=[Depends(require_auth)]``.
"""

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status

from telesoft.api.auth import require_auth
from telesoft.db.connection import get_db
from telesoft.db.models import channel as channel_model
from telesoft.schemas.channel import (
    ChannelCreate,
    ChannelListResponse,
    ChannelResponse,
    ChannelUpdate,
    now_iso,
)

router = APIRouter(
    prefix="/api/channels",
    tags=["channels"],
    dependencies=[Depends(require_auth)],
)


async def _get_channel_or_404(
    db: aiosqlite.Connection, channel_id: int
) -> channel_model.ChannelRow:
    """Fetch a channel by id or raise 404."""
    row = await channel_model.get_channel(db, channel_id=channel_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel {channel_id} not found",
        )
    return row


@router.get("", response_model=ChannelListResponse)
async def list_channels_endpoint(
    active_only: bool = False,
    show_inactive: bool | None = None,
) -> ChannelListResponse:
    """List channels, optionally filtered to active ones.

    ``show_inactive`` is a convenience alias: when ``True`` it forces all
    channels (active + inactive) regardless of ``active_only``. When
    ``False`` it forces active-only. When unset (default) ``active_only``
    controls the filter.
    """
    if show_inactive is True:
        active_only = False
    elif show_inactive is False:
        active_only = True
    async with get_db() as db:
        rows = await channel_model.list_channels(db, active_only=active_only)
    channels = [ChannelResponse.from_row(row) for row in rows]
    return ChannelListResponse(channels=channels, total=len(channels))


@router.post("", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel_endpoint(payload: ChannelCreate) -> ChannelResponse:
    """Create a new channel. Returns 409 if telegram_id already exists."""
    async with get_db() as db:
        existing = await channel_model.get_channel_by_telegram_id(
            db, telegram_id=payload.telegram_id
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Channel with telegram_id {payload.telegram_id} already exists",
            )
        row = await channel_model.create_channel(
            db,
            telegram_id=payload.telegram_id,
            title=payload.title,
            username=payload.username,
            added_at=now_iso(),
        )
    return ChannelResponse.from_row(row)


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel_endpoint(channel_id: int) -> ChannelResponse:
    """Return a single channel by id."""
    async with get_db() as db:
        row = await _get_channel_or_404(db, channel_id)
    return ChannelResponse.from_row(row)


@router.patch("/{channel_id}", response_model=ChannelResponse)
async def update_channel_endpoint(
    channel_id: int,
    payload: ChannelUpdate,
) -> ChannelResponse:
    """Patch channel fields (title, username, is_active)."""
    async with get_db() as db:
        await _get_channel_or_404(db, channel_id)
        fields: dict[str, str | int | None] = {}
        if payload.title is not None:
            fields["title"] = payload.title
        if payload.username is not None:
            fields["username"] = payload.username
        if payload.is_active is not None:
            fields["is_active"] = int(payload.is_active)
        row = await channel_model.update_channel(db, channel_id=channel_id, **fields)
    assert row is not None
    return ChannelResponse.from_row(row)


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel_endpoint(channel_id: int) -> None:
    """Delete a channel by id. Cascades to edit_jobs and edit_logs."""
    async with get_db() as db:
        await _get_channel_or_404(db, channel_id)
        await channel_model.delete_channel(db, channel_id=channel_id)
