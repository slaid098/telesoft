"""Integration tests against a real Telegram channel.

Opt-in: run with ``pytest -m integration``. Skipped automatically when no
Telegram credentials are present (``TELEGRAM_BOT_TOKEN`` / ``TELEGRAM_API_ID`` /
``TELEGRAM_API_HASH``) so the suite stays green in CI without creds.

Each fixture sends a fresh test message and deletes it on teardown, leaving
the channel clean.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
from telethon import TelegramClient
from telethon.sessions import StringSession

from telesoft.config import Settings
from telesoft.core import telegram as telegram_module
from telesoft.core.link_replacer import find_posts_with_pattern, replace_link_in_post
from telesoft.core.telegram import get_message

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("TELEGRAM_BOT_TOKEN")
        or not os.getenv("TELEGRAM_API_ID")
        or not os.getenv("TELEGRAM_API_HASH"),
        reason="no Telegram creds (TELEGRAM_BOT_TOKEN / TELEGRAM_API_ID / TELEGRAM_API_HASH)",
    ),
]

CHANNEL_ID = int(os.getenv("TELESOFT_TEST_CHANNEL_ID", "-1003903711726"))
PATTERN = r"https://new\.example\.com/path"
NEW_LINK = "https://new.example.com/edited"


@pytest.fixture(autouse=True)
async def _reset_telegram_state() -> AsyncIterator[None]:
    """Reset the core.telegram singleton state between tests.

    Telethon forbids reusing a client across asyncio event loops; each
    pytest-asyncio test gets a fresh loop, so the shared client from a
    previous test would raise ``RuntimeError: The asyncio event loop must
    not change after connection``. Dropping the singleton before each test
    forces a fresh ``start_client()`` against the current loop.
    """
    telegram_module._state.client = None
    telegram_module._state.started = False
    yield
    if telegram_module._state.client is not None and telegram_module._state.started:
        with contextlib.suppress(Exception):
            await telegram_module._state.client.disconnect()
    telegram_module._state.client = None
    telegram_module._state.started = False


async def _client() -> TelegramClient:
    settings = Settings.from_env()
    session = (
        StringSession(settings.telegram_session_string)
        if settings.telegram_session_string
        else StringSession()
    )
    client = TelegramClient(
        session,
        settings.telegram_api_id,
        settings.telegram_api_hash,
        receive_updates=False,
    )
    await client.start(bot_token=settings.telegram_bot_token)
    return client


@pytest.fixture
async def test_text_url_msg() -> AsyncIterator[Any]:
    """Send a message with a plain URL in raw text; delete on teardown."""
    client = await _client()
    msg = await client.send_message(CHANNEL_ID, "Test post https://new.example.com/path end")
    try:
        yield msg
    finally:
        await client.delete_messages(CHANNEL_ID, [msg.id])
        await client.disconnect()


@pytest.fixture
async def test_entity_url_msg() -> AsyncIterator[Any]:
    """Send a message with a formatted link (URL hidden in an entity)."""
    client = await _client()
    msg = await client.send_message(
        CHANNEL_ID,
        "Test post [click here](https://new.example.com/path) end",
        link_preview=False,
        parse_mode="md",
    )
    try:
        yield msg
    finally:
        await client.delete_messages(CHANNEL_ID, [msg.id])
        await client.disconnect()


async def test_find_text_url(test_text_url_msg: Any) -> None:
    """URL in raw text is matched by find_posts_with_pattern."""
    messages = [test_text_url_msg]
    matching = await find_posts_with_pattern(messages, PATTERN)
    assert len(matching) == 1


async def test_find_entity_url(test_entity_url_msg: Any) -> None:
    """URL inside a MessageEntityTextUrl entity is matched (post-fix)."""
    messages = [test_entity_url_msg]
    matching = await find_posts_with_pattern(messages, PATTERN)
    assert len(matching) == 1


async def test_replace_text_url(test_text_url_msg: Any) -> None:
    """Replacing a URL in raw text edits the post in place."""
    result = await replace_link_in_post(CHANNEL_ID, test_text_url_msg, PATTERN, NEW_LINK)
    assert result.get("edited") is True
    edited = await get_message(CHANNEL_ID, test_text_url_msg.id)
    assert "https://new.example.com/edited" in (edited.text or "")


async def test_replace_entity_url(test_entity_url_msg: Any) -> None:
    """Replacing a URL in an entity edits the entity url in-place via formatting_entities."""
    result = await replace_link_in_post(CHANNEL_ID, test_entity_url_msg, PATTERN, NEW_LINK)
    assert result.get("edited") is True
    edited = await get_message(CHANNEL_ID, test_entity_url_msg.id)
    entity_urls = [e.url for e in (edited.entities or []) if hasattr(e, "url")]
    assert "https://new.example.com/edited" in entity_urls
