"""Bot-mode Telethon client wrapper.

Singleton TelegramClient backed by an in-memory ``StringSession`` so the
bot does not touch the filesystem. Bot-token auth is instant (no phone+code
flow), so a file session brings no benefit and causes SQLite lock conflicts
when tests and the container run simultaneously. Only by-ID message fetch
is supported — history iteration (``iter_messages`` /
``get_messages(limit=...)``) is forbidden for bot accounts (see ADR
2026-07-20-pr-14-spike-telethon).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from loguru import logger
from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from telethon.sessions import StringSession
from telethon.tl.functions.channels import GetMessagesRequest as ChannelsGetMessagesRequest
from telethon.tl.functions.messages import EditMessageRequest as MessagesEditMessageRequest
from telethon.tl.types import InputChannel, InputPeerChannel, Message

from telesoft.config import Settings


@dataclass
class _State:
    client: TelegramClient | None = None
    started: bool = False


_state = _State()
_connection_lock = asyncio.Lock()


async def get_client() -> TelegramClient:
    """Return the shared TelegramClient, creating it lazily from Settings."""
    if _state.client is None:
        settings = Settings.from_env()
        _state.client = TelegramClient(
            StringSession(),
            settings.telegram_api_id,
            settings.telegram_api_hash,
            receive_updates=False,
        )
    return _state.client


async def start_client() -> TelegramClient:
    """Start the shared TelegramClient with the bot token (idempotent)."""
    if _state.started and _state.client is not None:
        return _state.client

    async with _connection_lock:
        if _state.started and _state.client is not None:
            return _state.client

        client = await get_client()
        settings = Settings.from_env()
        await client.start(bot_token=settings.telegram_bot_token)
        _state.started = True
        logger.info("Telethon client started (StringSession)")
        return client


async def stop_client() -> None:
    """Disconnect the shared TelegramClient if it was started and reset state."""
    client = _state.client
    if client is not None and _state.started:
        try:
            await client.disconnect()
        except RPCError as exc:
            logger.warning("Telethon disconnect failed: {}", exc)
    _state.client = None
    _state.started = False
    logger.info("Telethon client stopped")


async def get_message(chat_id: int, message_id: int) -> Message | None:
    """Fetch a single message by exact id, or None if not found."""
    client = await start_client()
    messages = await client.get_messages(chat_id, ids=[message_id])
    if not messages:
        return None
    return messages[0]


async def get_messages(chat_id: int, message_ids: list[int]) -> list[Message]:
    """Batch-fetch messages by exact ids, filtering out missing entries."""
    client = await start_client()
    messages = await client.get_messages(chat_id, ids=message_ids)
    return [m for m in messages if m is not None]


async def edit_message(chat_id: int, message_id: int, text: str) -> Message:
    """Edit a single message text; propagates TelethonError on failure."""
    client = await start_client()
    return await client.edit_message(chat_id, message_id, text=text)


async def edit_message_entities(
    chat_id: int, message_id: int, text: str, entities: list[Any]
) -> Any:
    """Edit message entities via raw API (messages.EditMessageRequest).

    Used when the URL lives inside a ``MessageEntityTextUrl`` entity (formatted
    link) — the regular ``client.edit_message`` only updates ``message`` text
    and would drop the URL entities. Returns the raw ``Updates`` result.
    """
    client = await start_client()
    channel_input = await _get_channel_input(chat_id)
    peer = InputPeerChannel(
        channel_id=channel_input.channel_id, access_hash=channel_input.access_hash
    )
    return await client(
        MessagesEditMessageRequest(
            peer=peer,
            id=message_id,
            message=text,
            entities=entities,
        )
    )


async def resolve_entity(identifier: str | int) -> Any:
    """Resolve a @username or numeric id to a Telegram entity."""
    client = await start_client()
    return await client.get_entity(identifier)


async def get_bot_info() -> dict[str, Any]:
    """Return bot identity dict for diagnostics."""
    client = await start_client()
    me = await client.get_me()
    return {
        "id": me.id,
        "username": me.username,
        "first_name": me.first_name,
        "is_bot": me.bot,
    }


async def _get_channel_input(channel_id: int) -> InputChannel:
    """Resolve channel id to InputChannel (id + access_hash) via get_entity."""
    client = await start_client()
    entity = await client.get_entity(channel_id)
    return InputChannel(entity.id, getattr(entity, "access_hash", 0))


async def _fetch_messages_by_ids(channel_input: InputChannel, ids: list[int]) -> list[Message]:
    """Fetch messages by exact ids via channels.GetMessagesRequest raw API.

    Retries up to 3 times on FloodWaitError, then re-raises.
    """
    client = await start_client()
    max_retries = 3
    for attempt in range(max_retries):
        try:
            result = await client(ChannelsGetMessagesRequest(channel=channel_input, id=ids))
            messages = list(getattr(result, "messages", []) or [])
            return [m for m in messages if m is not None and getattr(m, "date", None) is not None]
        except FloodWaitError as exc:
            if attempt + 1 >= max_retries:
                raise
            await asyncio.sleep(exc.seconds + 1)
    return []


async def _find_max_id(channel_input: InputChannel, max_probe_id: int, delay: float) -> int:
    """Binary search the largest existing message id in a channel.

    Probes ids in [1, max_probe_id] via channels.GetMessagesRequest; returns
    the last id whose fetch returned a non-empty list, or 0 if all empty.
    Sleeps *delay* seconds between probes except after the final one (when
    ``lo > hi`` the search is done — no further request is pending).
    """
    lo = 1
    hi = max_probe_id
    last_existing = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        logger.debug("binary search probe mid={}", mid)
        probe = await _fetch_messages_by_ids(channel_input, [mid])
        if probe:
            last_existing = mid
            lo = mid + 1
        else:
            hi = mid - 1
        if lo <= hi:
            await asyncio.sleep(delay)
    return last_existing


async def get_last_messages(channel_id: int, limit: int = 100) -> list[Message]:
    """Return up to ``limit`` most recent channel posts via raw API.

    Uses channels.GetMessagesRequest (works for bot-admin): binary search to
    find max_id, then a single range fetch for ids [max_id, start_id].
    """
    logger.info("get_last_messages: channel_id={}, limit={}", channel_id, limit)
    settings = Settings.from_env()
    channel_input = await _get_channel_input(channel_id)
    max_id = await _find_max_id(
        channel_input, settings.max_probe_id, settings.telegram_request_delay
    )
    logger.info("binary search: max_id={}", max_id)
    if max_id == 0:
        logger.warning("get_last_messages: no messages found (max_id=0)")
        return []
    start_id = max(1, max_id - limit + 1)
    ids = list(range(max_id, start_id - 1, -1))
    messages = await _fetch_messages_by_ids(channel_input, ids)
    logger.info("fetched {} messages", len(messages))
    return messages
