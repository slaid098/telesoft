"""Spike v2: channels.GetMessagesRequest raw API for bot-admin.

Standalone async script (NOT part of src/telesoft/). Reads credentials from
os.environ directly (no Settings.from_env()) to keep the spike isolated from
the application config layer.

Goal: confirm that `channels.GetMessagesRequest` (raw API, namespace
`telethon.tl.functions.channels`) works for bot-admin to fetch channel posts
by ID, enabling auto-discovery of recent posts without manual URL input.

PR#14 limitation: `iter_messages` / `get_messages(limit=N)` fail for bots with
`BotMethodInvalidError` (caused by `messages.GetHistoryRequest`). This spike
checks the alternative raw API method `channels.GetMessagesRequest` which:
  - Accepts `id=[...]` (exact message IDs, not `limit=N`).
  - Returns N posts in ONE request (not N+1).
  - Enables binary search for `max_id` (~log2(10000) ≈ 14 probes).

Run:
    cd /root/workspace/telesoft && uv run python scripts/spike_telethon_v2.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import traceback
from pathlib import Path
from typing import Any

from telethon import TelegramClient
from telethon.errors import BotMethodInvalidError, FloodWaitError
from telethon.tl.functions.channels import GetMessagesRequest
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import Channel as TlChannel
from telethon.tl.types import InputChannel, InputPeerChannel
from telethon.tl.types import User as TlUser

SESSION_PATH = "app_data/bot.session"
TEST_CHANNEL_ID = -1003903711726
REQUEST_DELAY = 1.0
MAX_PROBE_ID = 10000
RANGE_FETCH_COUNT = 10


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"ERROR: env var {name} is not set", file=sys.stderr)
        sys.exit(1)
    return value


def _print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def _print_me(me: TlUser) -> None:
    print(f"bot id:       {me.id}")
    print(f"bot username: @{me.username}" if me.username else "bot username: (none)")
    print(f"bot first_name: {me.first_name}" if me.first_name else "bot first_name: (none)")
    print(f"bot is_bot:   {me.bot}")


def _print_entity(entity: object) -> None:
    if isinstance(entity, TlChannel):
        print("entity type:  Channel")
        print(f"channel id:   {entity.id}")
        print(f"channel title: {entity.title}")
        if entity.username:
            print(f"channel username: @{entity.username}")
        else:
            print("channel username: (none)")
        print(f"channel access_hash: {entity.access_hash}")
    else:
        print(f"entity type:  {type(entity).__name__}")
        print(f"entity:       {entity!r}")


def _text_preview(msg: Any, max_chars: int = 80) -> str:
    text = getattr(msg, "message", None) or getattr(msg, "text", None) or ""
    return (text or "").replace("\n", " ")[:max_chars]


def _print_messages(messages: list[Any], label: str = "messages") -> None:
    print(f"{label} returned: {len(messages)}")
    for msg in messages:
        if msg is None:
            print("  (None — message does not exist or deleted)")
            continue
        print(
            f"  id={getattr(msg, 'id', '?')} "
            f"date={getattr(msg, 'date', '?')} "
            f"text={_text_preview(msg)!r}"
        )


async def _delay() -> None:
    await asyncio.sleep(REQUEST_DELAY)


async def _retry_on_flood(coro_factory: Any, label: str) -> Any:
    while True:
        try:
            return await coro_factory()
        except FloodWaitError as exc:
            wait = exc.seconds + 1
            print(f"  [FloodWait] {label}: sleeping {wait}s then retry...")
            await asyncio.sleep(wait)


async def _get_messages_raw(
    client: TelegramClient, input_channel: InputChannel, ids: list[int], label: str
) -> Any:
    print(f"  [{label}] GetMessagesRequest id={ids}")
    result = await _retry_on_flood(
        lambda: client(GetMessagesRequest(channel=input_channel, id=ids)),
        label=label,
    )
    await _delay()
    return result


async def _test1_basic_fetch(client: TelegramClient, input_channel: InputChannel) -> bool:
    _print_section("TEST 1: channels.GetMessagesRequest id=[1,2,3]")
    try:
        result = await _get_messages_raw(client, input_channel, [1, 2, 3], label="test1")
        messages = list(getattr(result, "messages", []) or [])
        print(f"result type: {type(result).__name__}")
        _print_messages(messages, label="messages")
        if messages:
            print("TEST 1: OK — channels.GetMessagesRequest works for bot-admin")
            return True
        print("TEST 1: FAIL — no messages returned")
        return False
    except BotMethodInvalidError as exc:
        print(f"TEST 1: FAIL BotMethodInvalidError: {exc}")
        return False
    except Exception as exc:
        print(f"TEST 1: FAIL {type(exc).__name__}: {exc}")
        return False


async def _test2_binary_search_max_id(
    client: TelegramClient, input_channel: InputChannel
) -> int | None:
    _print_section(f"TEST 2: binary search max_id (upper bound {MAX_PROBE_ID})")
    lo = 1
    hi = MAX_PROBE_ID
    probes = 0
    last_existing_id = 0
    try:
        while lo <= hi:
            mid = (lo + hi) // 2
            probes += 1
            result = await _get_messages_raw(client, input_channel, [mid], label=f"probe#{probes}")
            messages = list(getattr(result, "messages", []) or [])
            exists = (
                bool(messages)
                and messages[0] is not None
                and getattr(messages[0], "date", None) is not None
            )
            date = getattr(messages[0], "date", None) if messages else None
            print(f"  probe #{probes}: id={mid} exists={exists} date={date} range=[{lo}, {hi}]")
            if exists:
                last_existing_id = mid
                lo = mid + 1
            else:
                hi = mid - 1
        print(f"TEST 2: max_id = {last_existing_id} (found in {probes} probes)")
        return last_existing_id if last_existing_id > 0 else None
    except Exception as exc:
        print(f"TEST 2: FAIL {type(exc).__name__}: {exc}")
        return None


async def _test3_range_fetch(
    client: TelegramClient, input_channel: InputChannel, max_id: int
) -> bool:
    _print_section(f"TEST 3: range fetch last {RANGE_FETCH_COUNT} posts")
    try:
        ids = list(range(max_id, max_id - RANGE_FETCH_COUNT, -1))
        result = await _get_messages_raw(client, input_channel, ids, label="test3-range")
        messages = list(getattr(result, "messages", []) or [])
        existing = [m for m in messages if m is not None]
        print(f"requested {len(ids)} ids, got {len(messages)} entries, {len(existing)} non-None")
        _print_messages(existing, label="existing posts")
        print(f"TEST 3: OK — {len(existing)} messages returned in one request")
        return True
    except Exception as exc:
        print(f"TEST 3: FAIL {type(exc).__name__}: {exc}")
        return False


async def _test4_get_history_control(client: TelegramClient, input_channel: InputChannel) -> bool:
    _print_section("TEST 4 (control, expected FAIL): messages.GetHistoryRequest")
    ch_id = input_channel.channel_id
    ah = input_channel.access_hash
    try:
        result = await client(
            GetHistoryRequest(
                peer=InputPeerChannel(ch_id, ah),
                offset_id=0,
                offset_date=None,
                add_offset=0,
                limit=5,
                max_id=0,
                min_id=0,
                hash=0,
            )
        )
        print(f"TEST 4: UNEXPECTED OK — result type {type(result).__name__}")
        return False
    except BotMethodInvalidError as exc:
        print(f"TEST 4: FAIL BotMethodInvalidError (expected): {exc}")
        return True
    except Exception as exc:
        print(f"TEST 4: UNEXPECTED error {type(exc).__name__}: {exc}")
        return False


async def _test5_iter_messages_control(client: TelegramClient, entity: object) -> bool:
    _print_section("TEST 5 (control, expected FAIL): client.iter_messages")
    try:
        messages = []
        async for msg in client.iter_messages(entity, limit=5):
            messages.append(msg)
        print(f"TEST 5: UNEXPECTED OK — got {len(messages)} messages")
        return False
    except BotMethodInvalidError as exc:
        print(f"TEST 5: FAIL BotMethodInvalidError (expected): {exc}")
        return True
    except Exception as exc:
        print(f"TEST 5: UNEXPECTED error {type(exc).__name__}: {exc}")
        return False


async def main() -> int:
    api_id = int(_require_env("TELEGRAM_API_ID"))
    api_hash = _require_env("TELEGRAM_API_HASH")
    bot_token = _require_env("TELEGRAM_BOT_TOKEN")

    Path(SESSION_PATH).parent.mkdir(parents=True, exist_ok=True)

    _print_section("1. connect (bot mode)")
    client = TelegramClient(SESSION_PATH, api_id, api_hash)
    await client.start(bot_token=bot_token)
    try:
        me = await client.get_me()
        _print_me(me)  # type: ignore[arg-type]

        _print_section("2. resolve channel entity")
        entity = await client.get_entity(TEST_CHANNEL_ID)
        _print_entity(entity)
        if not isinstance(entity, TlChannel):
            print(f"ERROR: expected Channel, got {type(entity).__name__}")
            return 1
        ch_id = entity.id
        ah = entity.access_hash
        input_channel = InputChannel(ch_id, ah)

        await _delay()

        ok1 = await _test1_basic_fetch(client, input_channel)
        max_id = await _test2_binary_search_max_id(client, input_channel)
        if max_id is None:
            print("\nspike result: PARTIAL — binary search failed, skipping test 3")
            await _test4_get_history_control(client, input_channel)
            await _test5_iter_messages_control(client, entity)
            return 2
        ok3 = await _test3_range_fetch(client, input_channel, max_id)
        ok4 = await _test4_get_history_control(client, input_channel)
        ok5 = await _test5_iter_messages_control(client, entity)

        _print_section("spike summary")
        print(f"TEST 1 (channels.GetMessagesRequest id=[1,2,3]): {'PASS' if ok1 else 'FAIL'}")
        print(f"TEST 2 (binary search max_id): max_id={max_id}")
        print(f"TEST 3 (range fetch last {RANGE_FETCH_COUNT}): {'PASS' if ok3 else 'FAIL'}")
        print(
            f"TEST 4 (GetHistoryRequest control, expected FAIL): "
            f"{'PASS (expected fail)' if ok4 else 'UNEXPECTED ok'}"
        )
        print(
            f"TEST 5 (iter_messages control, expected FAIL): "
            f"{'PASS (expected fail)' if ok5 else 'UNEXPECTED ok'}"
        )

        if ok1 and ok3 and ok4 and ok5:
            _print_section("spike result: SUCCESS — channels.GetMessagesRequest works")
            return 0
        print("\nspike result: PARTIAL — some tests failed (see above)")
        return 2
    except Exception as exc:
        print(f"\nspike FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1
    finally:
        await client.disconnect()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
