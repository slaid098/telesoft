"""Bot-mode Telethon client wrapper.

Singleton TelegramClient backed by a file session (``settings.session_path``)
so the bot does not re-login between process restarts. Only by-ID message
fetch is supported — history iteration (``iter_messages`` /
``get_messages(limit=...)``) is forbidden for bot accounts (see ADR
2026-07-20-pr-14-spike-telethon).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from loguru import logger
from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.tl.types import Message

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
            settings.session_path,
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
        logger.info("Telethon client started (file session={})", settings.session_path)
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
