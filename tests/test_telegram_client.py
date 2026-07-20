"""Tests for the bot-mode Telethon client wrapper."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from telethon.errors import BadRequestError, RPCError

from telesoft.core import telegram as telegram_module
from telesoft.core.telegram import (
    edit_message,
    get_bot_info,
    get_client,
    get_message,
    get_messages,
    resolve_entity,
    start_client,
    stop_client,
)
from tests.conftest import MockMessage


async def test_get_client_singleton(mock_telethon_client: AsyncMock) -> None:
    first = await get_client()
    second = await get_client()
    assert first is second


async def test_start_client_idempotent(mock_telethon_client: AsyncMock) -> None:
    await start_client()
    await start_client()
    assert mock_telethon_client.start.await_count == 1


async def test_get_message_by_id(
    mock_telethon_client: AsyncMock, mock_message: MockMessage
) -> None:
    result = await get_message(chat_id=-1001234567890, message_id=123)
    mock_telethon_client.get_messages.assert_awaited_once_with(-1001234567890, ids=[123])
    assert result is mock_message


async def test_get_message_returns_none_for_missing(mock_telethon_client: AsyncMock) -> None:
    mock_telethon_client.get_messages.return_value = []
    result = await get_message(chat_id=-1001234567890, message_id=999)
    assert result is None


async def test_get_messages_batch_filters_none(mock_telethon_client: AsyncMock) -> None:
    m1 = MockMessage(id=1, text="a", chat_id=-100)
    m2 = MockMessage(id=2, text="b", chat_id=-100)
    mock_telethon_client.get_messages.return_value = [m1, None, m2]
    result = await get_messages(chat_id=-100, message_ids=[1, 2, 3])
    assert result == [m1, m2]


async def test_edit_message_success(
    mock_telethon_client: AsyncMock, mock_message: MockMessage
) -> None:
    result = await edit_message(chat_id=-1001234567890, message_id=123, text="new text")
    mock_telethon_client.edit_message.assert_awaited_once_with(-1001234567890, 123, text="new text")
    assert result is mock_message


async def test_edit_message_propagates_error(mock_telethon_client: AsyncMock) -> None:
    mock_telethon_client.edit_message.side_effect = BadRequestError(request=None, message="boom")
    with pytest.raises(RPCError):
        await edit_message(chat_id=-1001234567890, message_id=123, text="new text")


async def test_resolve_entity(mock_telethon_client: AsyncMock) -> None:
    await resolve_entity("@mychannel")
    mock_telethon_client.get_entity.assert_awaited_once_with("@mychannel")


async def test_get_bot_info(mock_telethon_client: AsyncMock) -> None:
    info = await get_bot_info()
    assert info == {
        "id": 6164770162,
        "username": "server10bot",
        "first_name": "Tester",
        "is_bot": True,
    }


async def test_stop_client_resets_state(mock_telethon_client: AsyncMock) -> None:
    await start_client()
    await stop_client()
    assert telegram_module._state.client is None
    assert telegram_module._state.started is False
    mock_telethon_client.disconnect.assert_awaited_once()
