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
import re
from dataclasses import dataclass
from typing import Any

from loguru import logger
from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from telethon.sessions import StringSession
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
        session = (
            StringSession(settings.telegram_session_string)
            if settings.telegram_session_string
            else StringSession()
        )
        _state.client = TelegramClient(
            session,
            settings.telegram_api_id,
            settings.telegram_api_hash,
            receive_updates=False,
            flood_sleep_threshold=100,
            auto_reconnect=True,
            connection_retries=100,
            retry_delay=5,
            entity_cache_limit=1000,
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


async def edit_message(
    chat_id: int,
    message_id: int,
    text: str,
    formatting_entities: list[Any] | None = None,
) -> Message:
    """Edit a single message text; retries 3x on FloodWaitError.

    *formatting_entities* (when provided) is forwarded to Telethon's
    ``client.edit_message(formatting_entities=...)`` so bold/italic/etc
    entities survive the text substitution — see
    :func:`telesoft.core.link_replacer._adjust_entity_offsets`.
    """
    client = await start_client()
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return await client.edit_message(
                chat_id,
                message_id,
                text=text,
                formatting_entities=formatting_entities,
            )
        except FloodWaitError as exc:
            if attempt + 1 >= max_retries:
                raise
            await asyncio.sleep(exc.seconds + 1)
    raise RuntimeError("unreachable")


async def edit_message_entities(chat_id: int, message: Any, entities: list[Any]) -> Any:
    """Edit message entities via high-level ``client.edit_message``.

    Used when the URL lives inside a ``MessageEntityTextUrl`` entity (formatted
    link) — the regular text-only ``edit_message`` path would drop the URL
    entities. Mutating ``entity.url`` in-place (caller responsibility) and
    passing ``formatting_entities`` lets Telethon resolve the channel peer
    itself, eliminating the per-edit ``_get_channel_input`` / ``get_entity``
    round-trip the raw ``MessagesEditMessageRequest`` path required.
    """
    client = await start_client()
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return await client.edit_message(
                chat_id,
                message.id,
                text=message.message or "",
                formatting_entities=entities,
            )
        except FloodWaitError as exc:
            if attempt + 1 >= max_retries:
                raise
            await asyncio.sleep(exc.seconds + 1)
    raise RuntimeError("unreachable")


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


async def _fetch_messages_by_ids(chat_id: int, ids: list[int]) -> list[Message]:
    """Fetch messages by exact ids via client.get_messages (high-level API).

    Retries up to 3 times on FloodWaitError, then re-raises.
    """
    client = await start_client()
    max_retries = 3
    for attempt in range(max_retries):
        try:
            messages = await client.get_messages(chat_id, ids=ids)
            return [m for m in messages if m is not None and getattr(m, "date", None) is not None]
        except FloodWaitError as exc:
            if attempt + 1 >= max_retries:
                raise
            await asyncio.sleep(exc.seconds + 1)
    return []


def parse_post_link(link: str) -> int:
    """Extract the message id from a Telegram post link or plain id.

    Accepts:
    - ``https://t.me/channelname/140`` → 140
    - ``https://t.me/c/1234567890/140`` → 140
    - ``140`` (plain number) → 140

    Raises ``ValueError`` if *link* cannot be parsed.
    """
    stripped = link.strip()
    match = re.search(r"/(\d+)/?$", stripped)
    if match:
        return int(match.group(1))
    try:
        return int(stripped)
    except ValueError as exc:
        msg = f"cannot parse post link: {link}"
        raise ValueError(msg) from exc


async def get_last_messages(channel_id: int, limit: int = 100, max_id: int = 0) -> list[Message]:
    """Return up to ``limit`` most recent channel posts via high-level API.

    Uses ``client.get_messages(chat_id, ids=[...])`` (works for bot-admin).
    The caller supplies ``max_id`` (the id of the last known post); ids are
    fetched from ``max_id`` down to ``max(0, max_id - limit)`` (descending).
    If ``max_id`` is 0, returns an empty list with a warning — the caller
    must provide a valid post link.
    """
    logger.info(
        "get_last_messages: channel_id={}, limit={}, max_id={}",
        channel_id,
        limit,
        max_id,
    )
    if max_id <= 0:
        logger.warning("get_last_messages: max_id=0, returning empty list")
        return []
    ids = list(range(max_id, max(0, max_id - limit), -1))
    messages = await _fetch_messages_by_ids(channel_id, ids)
    logger.info("fetched {} messages", len(messages))
    return messages
