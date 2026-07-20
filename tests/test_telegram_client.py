"""Tests for the bot-mode Telethon client wrapper."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from telethon.errors import BadRequestError, FloodWaitError, RPCError
from telethon.tl.functions.channels import GetMessagesRequest as ChannelsGetMessagesRequest

from telesoft.config import Settings
from telesoft.core import telegram as telegram_module
from telesoft.core.telegram import (
    _fetch_messages_by_ids,
    _find_max_id,
    edit_message,
    get_bot_info,
    get_client,
    get_last_messages,
    get_message,
    get_messages,
    resolve_entity,
    start_client,
    stop_client,
)
from tests.conftest import MockMessage, mock_channel_messages


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


def _mk_msg(msg_id: int, *, date: object = "2026-07-20") -> MockMessage:
    return MockMessage(id=msg_id, text=f"text-{msg_id}", chat_id=-100, date=date)


def _probe_response(probe_id: int, exists: bool) -> object:
    if not exists:
        return mock_channel_messages([None])
    return mock_channel_messages([_mk_msg(probe_id)])


async def test_get_last_messages_success(
    mock_telethon_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel_input = object()
    monkeypatch.setattr(
        telegram_module, "_get_channel_input", AsyncMock(return_value=channel_input)
    )
    monkeypatch.setattr(telegram_module, "_find_max_id", AsyncMock(return_value=150))
    range_messages = [_mk_msg(i) for i in range(150, 50, -1)]
    mock_telethon_client.return_value = mock_channel_messages(range_messages)

    result = await get_last_messages(channel_id=-1001234567890, limit=100)

    assert result == range_messages
    assert len(result) == 100
    mock_telethon_client.assert_awaited_once()
    request = mock_telethon_client.await_args.args[0]
    assert isinstance(request, ChannelsGetMessagesRequest)
    assert request.id == list(range(150, 50, -1))


async def test_get_last_messages_empty_channel(
    mock_telethon_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(telegram_module, "_get_channel_input", AsyncMock(return_value=object()))
    monkeypatch.setattr(telegram_module, "_find_max_id", AsyncMock(return_value=0))

    result = await get_last_messages(channel_id=-1001234567890, limit=100)

    assert result == []
    mock_telethon_client.assert_not_awaited()


async def test_get_last_messages_limit_larger_than_max_id(
    mock_telethon_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel_input = object()
    monkeypatch.setattr(
        telegram_module, "_get_channel_input", AsyncMock(return_value=channel_input)
    )
    monkeypatch.setattr(telegram_module, "_find_max_id", AsyncMock(return_value=50))
    range_messages = [_mk_msg(i) for i in range(50, 0, -1)]
    mock_telethon_client.return_value = mock_channel_messages(range_messages)

    result = await get_last_messages(channel_id=-1001234567890, limit=100)

    assert result == range_messages
    assert len(result) == 50
    request = mock_telethon_client.await_args.args[0]
    assert request.id == list(range(50, 0, -1))


async def test_find_max_id_binary_search(
    mock_telethon_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = {1250, 1875}

    def _probe(request: ChannelsGetMessagesRequest) -> object:
        mid = request.id[0]
        return _probe_response(mid, exists=mid in existing)

    mock_telethon_client.side_effect = _probe
    monkeypatch.setattr(telegram_module.asyncio, "sleep", AsyncMock())

    max_id = await _find_max_id(channel_input=object(), max_probe_id=10000, delay=0.0)

    assert max_id == 1875


async def test_find_max_id_all_empty(
    mock_telethon_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_telethon_client.return_value = mock_channel_messages([None])
    monkeypatch.setattr(telegram_module.asyncio, "sleep", AsyncMock())

    max_id = await _find_max_id(channel_input=object(), max_probe_id=100, delay=0.0)

    assert max_id == 0


async def test_fetch_messages_by_ids_filters_empty(
    mock_telethon_client: AsyncMock,
) -> None:
    m1 = _mk_msg(1)
    m2 = _mk_msg(2)
    msg_date_none = MockMessage(id=3, text="x", chat_id=-100, date=None)
    mock_telethon_client.return_value = mock_channel_messages([m1, None, m2, msg_date_none])

    result = await _fetch_messages_by_ids(channel_input=object(), ids=[1, 2, 3])

    assert result == [m1, m2]


async def test_flood_wait_retry(
    mock_telethon_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    m1 = _mk_msg(1)
    attempts = 0

    def _side_effect(request: ChannelsGetMessagesRequest) -> object:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise FloodWaitError(request=None, capture=2)  # type: ignore[call-arg]
        return mock_channel_messages([m1])

    mock_telethon_client.side_effect = _side_effect
    sleep_mock = AsyncMock()
    monkeypatch.setattr(telegram_module.asyncio, "sleep", sleep_mock)

    result = await _fetch_messages_by_ids(channel_input=object(), ids=[1])

    assert result == [m1]
    assert attempts == 2
    flood_sleeps = [c for c in sleep_mock.await_args_list if c.args[0] == 3]
    assert len(flood_sleeps) == 1


async def test_flood_wait_max_retries_exceeded(
    mock_telethon_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_telethon_client.side_effect = FloodWaitError(request=None, capture=2)  # type: ignore[call-arg]
    sleep_mock = AsyncMock()
    monkeypatch.setattr(telegram_module.asyncio, "sleep", sleep_mock)

    with pytest.raises(FloodWaitError):
        await _fetch_messages_by_ids(channel_input=object(), ids=[1])

    assert mock_telethon_client.await_count == 3
    flood_sleeps = [c for c in sleep_mock.await_args_list if c.args[0] == 3]
    assert len(flood_sleeps) == 2


async def test_delay_between_requests(
    mock_telethon_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    mock_settings: Settings,
) -> None:
    """``_find_max_id`` sleeps *delay* seconds between probes (passed in
    explicitly — ``Settings.from_env`` is NOT called inside ``_find_max_id``).
    """
    mock_telethon_client.return_value = mock_channel_messages([None])
    sleep_mock = AsyncMock()
    monkeypatch.setattr(telegram_module.asyncio, "sleep", sleep_mock)

    await _find_max_id(
        channel_input=object(), max_probe_id=8, delay=mock_settings.telegram_request_delay
    )

    delay_calls = [
        c for c in sleep_mock.await_args_list if c.args[0] == mock_settings.telegram_request_delay
    ]
    assert len(delay_calls) >= 1
    assert all(c.args[0] == mock_settings.telegram_request_delay for c in delay_calls)


async def test_get_last_messages_reads_settings_once(
    mock_telethon_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    mock_settings: Settings,
) -> None:
    """``get_last_messages`` reads ``Settings.from_env`` exactly once (to thread
    the delay into ``_find_max_id``) and does NOT re-read per probe.

    ``start_client``/``_get_channel_input`` are stubbed so their own
    ``Settings.from_env`` calls (for the bot token / api id) don't pollute the
    count — the test asserts the per-probe reads were eliminated in PR#33.
    """
    monkeypatch.setattr(telegram_module, "_get_channel_input", AsyncMock(return_value=object()))
    monkeypatch.setattr(
        telegram_module, "start_client", AsyncMock(return_value=mock_telethon_client)
    )
    sleep_mock = AsyncMock()
    monkeypatch.setattr(telegram_module.asyncio, "sleep", sleep_mock)
    from_env_calls = [0]

    original_from_env = Settings.from_env

    def _counting_from_env() -> Settings:
        from_env_calls[0] += 1
        return original_from_env()

    monkeypatch.setattr(Settings, "from_env", _counting_from_env)

    mock_telethon_client.return_value = mock_channel_messages([None])

    await get_last_messages(channel_id=-1001234567890, limit=100)

    assert from_env_calls[0] == 1
    delay_sleeps = [
        c for c in sleep_mock.await_args_list if c.args[0] == mock_settings.telegram_request_delay
    ]
    assert all(c.args[0] == mock_settings.telegram_request_delay for c in delay_sleeps)
