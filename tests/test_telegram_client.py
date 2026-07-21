"""Tests for the bot-mode Telethon client wrapper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from telethon.errors import BadRequestError, FloodWaitError, RPCError

from telesoft.core import telegram as telegram_module
from telesoft.core.telegram import (
    _fetch_messages_by_ids,
    edit_message,
    edit_message_entities,
    get_bot_info,
    get_client,
    get_last_messages,
    get_message,
    get_messages,
    parse_post_link,
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
    mock_telethon_client.edit_message.assert_awaited_once_with(
        -1001234567890, 123, text="new text", formatting_entities=None
    )
    assert result is mock_message


async def test_edit_message_propagates_error(mock_telethon_client: AsyncMock) -> None:
    mock_telethon_client.edit_message.side_effect = BadRequestError(request=None, message="boom")
    with pytest.raises(RPCError):
        await edit_message(chat_id=-1001234567890, message_id=123, text="new text")


async def test_edit_message_retries_on_flood_wait(
    mock_telethon_client: AsyncMock,
    mock_message: MockMessage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """edit_message retries 3x on FloodWaitError, succeeds on second attempt."""
    sleep_mock = AsyncMock()
    monkeypatch.setattr(telegram_module.asyncio, "sleep", sleep_mock)
    attempts = 0

    def _side_effect(*_args: object, **_kwargs: object) -> object:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise FloodWaitError(request=None, capture=2)  # type: ignore[call-arg]
        return mock_message

    mock_telethon_client.edit_message.side_effect = _side_effect

    result = await edit_message(chat_id=-1001234567890, message_id=123, text="new text")

    assert result is mock_message
    assert attempts == 2
    flood_sleeps = [c for c in sleep_mock.await_args_list if c.args[0] == 3]
    assert len(flood_sleeps) == 1


async def test_edit_message_flood_wait_max_retries_exceeded(
    mock_telethon_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """edit_message re-raises FloodWaitError after 3 attempts."""
    sleep_mock = AsyncMock()
    monkeypatch.setattr(telegram_module.asyncio, "sleep", sleep_mock)
    mock_telethon_client.edit_message.side_effect = FloodWaitError(  # type: ignore[call-arg]
        request=None, capture=2
    )

    with pytest.raises(FloodWaitError):
        await edit_message(chat_id=-1001234567890, message_id=123, text="new text")

    assert mock_telethon_client.edit_message.await_count == 3
    flood_sleeps = [c for c in sleep_mock.await_args_list if c.args[0] == 3]
    assert len(flood_sleeps) == 2


async def test_edit_message_entities_uses_high_level_api(
    mock_telethon_client: AsyncMock,
) -> None:
    """edit_message_entities invokes ``client.edit_message(formatting_entities=...)``
    instead of the raw ``MessagesEditMessageRequest`` API.
    """
    message = MagicMock()
    message.id = 42
    message.text = "hello"
    entities = [MagicMock()]
    result_mock = MagicMock()
    mock_telethon_client.edit_message.return_value = result_mock

    result = await edit_message_entities(chat_id=-1001234567890, message=message, entities=entities)

    assert result is result_mock
    mock_telethon_client.edit_message.assert_awaited_once_with(
        -1001234567890, 42, text="hello", formatting_entities=entities
    )
    mock_telethon_client.assert_not_awaited()


async def test_edit_message_entities_retries_on_flood_wait(
    mock_telethon_client: AsyncMock,
    mock_message: MockMessage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """edit_message_entities retries 3x on FloodWaitError, succeeds on second attempt."""
    sleep_mock = AsyncMock()
    monkeypatch.setattr(telegram_module.asyncio, "sleep", sleep_mock)
    message = MagicMock()
    message.id = 42
    message.text = "hello"
    entities = [MagicMock()]
    attempts = 0

    def _side_effect(*_args: object, **_kwargs: object) -> object:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise FloodWaitError(request=None, capture=2)  # type: ignore[call-arg]
        return mock_message

    mock_telethon_client.edit_message.side_effect = _side_effect

    result = await edit_message_entities(chat_id=-1001234567890, message=message, entities=entities)

    assert result is mock_message
    assert attempts == 2
    flood_sleeps = [c for c in sleep_mock.await_args_list if c.args[0] == 3]
    assert len(flood_sleeps) == 1


async def test_edit_message_entities_flood_wait_max_retries_exceeded(
    mock_telethon_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """edit_message_entities re-raises FloodWaitError after 3 attempts."""
    sleep_mock = AsyncMock()
    monkeypatch.setattr(telegram_module.asyncio, "sleep", sleep_mock)
    mock_telethon_client.edit_message.side_effect = FloodWaitError(  # type: ignore[call-arg]
        request=None, capture=2
    )
    message = MagicMock()
    message.id = 42
    message.text = "hello"
    entities = [MagicMock()]

    with pytest.raises(FloodWaitError):
        await edit_message_entities(chat_id=-1001234567890, message=message, entities=entities)

    assert mock_telethon_client.edit_message.await_count == 3
    flood_sleeps = [c for c in sleep_mock.await_args_list if c.args[0] == 3]
    assert len(flood_sleeps) == 2


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


def _mk_msg(msg_id: int, *, date: object = "2026-07-20") -> MockMessage:
    return MockMessage(id=msg_id, text=f"text-{msg_id}", chat_id=-100, date=date)


async def test_get_last_messages_with_max_id(
    mock_telethon_client: AsyncMock,
) -> None:
    """get_last_messages(max_id=140, limit=10) fetches ids [140, 139, ..., 131]."""
    range_messages = [_mk_msg(i) for i in range(140, 130, -1)]
    mock_telethon_client.get_messages.return_value = range_messages

    result = await get_last_messages(channel_id=-1001234567890, limit=10, max_id=140)

    assert result == range_messages
    mock_telethon_client.get_messages.assert_awaited_once()
    assert mock_telethon_client.get_messages.await_args.kwargs["ids"] == list(range(140, 130, -1))


async def test_get_last_messages_max_id_zero_returns_empty(
    mock_telethon_client: AsyncMock,
) -> None:
    """max_id=0 returns an empty list without calling Telegram."""
    result = await get_last_messages(channel_id=-1001234567890, limit=10, max_id=0)

    assert result == []
    mock_telethon_client.get_messages.assert_not_awaited()


async def test_get_last_messages_limit_larger_than_max_id(
    mock_telethon_client: AsyncMock,
) -> None:
    """max_id=5, limit=10 → ids=[5, 4, 3, 2, 1] (does not go below 1)."""
    range_messages = [_mk_msg(i) for i in range(5, 0, -1)]
    mock_telethon_client.get_messages.return_value = range_messages

    result = await get_last_messages(channel_id=-1001234567890, limit=10, max_id=5)

    assert result == range_messages
    assert mock_telethon_client.get_messages.await_args.kwargs["ids"] == [
        5,
        4,
        3,
        2,
        1,
    ]


def test_parse_post_link_public_channel_url() -> None:
    """https://t.me/channelname/140 → 140."""
    assert parse_post_link("https://t.me/channelname/140") == 140


def test_parse_post_link_private_channel_url() -> None:
    """https://t.me/c/1234567890/140 → 140."""
    assert parse_post_link("https://t.me/c/1234567890/140") == 140


def test_parse_post_link_plain_number() -> None:
    """140 (plain number) → 140."""
    assert parse_post_link("140") == 140


def test_parse_post_link_invalid_raises_value_error() -> None:
    """invalid input raises ValueError."""
    with pytest.raises(ValueError, match="cannot parse post link"):
        parse_post_link("invalid")


async def test_fetch_messages_by_ids_filters_empty(
    mock_telethon_client: AsyncMock,
) -> None:
    m1 = _mk_msg(1)
    m2 = _mk_msg(2)
    msg_date_none = MockMessage(id=3, text="x", chat_id=-100, date=None)
    mock_telethon_client.get_messages.return_value = [m1, None, m2, msg_date_none]

    result = await _fetch_messages_by_ids(chat_id=-1001234567890, ids=[1, 2, 3])

    assert result == [m1, m2]


async def test_flood_wait_retry(
    mock_telethon_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    m1 = _mk_msg(1)
    attempts = 0

    def _side_effect(*_args: object, **_kwargs: object) -> list[MockMessage]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise FloodWaitError(request=None, capture=2)  # type: ignore[call-arg]
        return [m1]

    mock_telethon_client.get_messages.side_effect = _side_effect
    sleep_mock = AsyncMock()
    monkeypatch.setattr(telegram_module.asyncio, "sleep", sleep_mock)

    result = await _fetch_messages_by_ids(chat_id=-1001234567890, ids=[1])

    assert result == [m1]
    assert attempts == 2
    flood_sleeps = [c for c in sleep_mock.await_args_list if c.args[0] == 3]
    assert len(flood_sleeps) == 1


async def test_flood_wait_max_retries_exceeded(
    mock_telethon_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_telethon_client.get_messages.side_effect = FloodWaitError(  # type: ignore[call-arg]
        request=None, capture=2
    )
    sleep_mock = AsyncMock()
    monkeypatch.setattr(telegram_module.asyncio, "sleep", sleep_mock)

    with pytest.raises(FloodWaitError):
        await _fetch_messages_by_ids(chat_id=-1001234567890, ids=[1])

    assert mock_telethon_client.get_messages.await_count == 3
    flood_sleeps = [c for c in sleep_mock.await_args_list if c.args[0] == 3]
    assert len(flood_sleeps) == 2
