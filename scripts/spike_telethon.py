"""Spike: Telethon bot mode PoC on test channel.

Standalone async script (NOT part of src/telesoft/). Reads credentials from
os.environ directly (no Settings.from_env()) to keep the spike isolated from
the application config layer.

Goal: confirm that Telethon in bot mode can connect, read channel posts, and
edit a post (replace a link) on the test channel -1003903711726.

Run:
    cd /root/workspace/telesoft && uv run python scripts/spike_telethon.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import traceback
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.types import Channel as TlChannel
from telethon.tl.types import User as TlUser

SESSION_PATH = "app_data/bot.session"
TEST_CHANNEL_ID = -1003903711726
OLD_LINK = "https://old.example.com/path"
NEW_LINK = "https://new.example.com/path"
POST_TEXT = f"Test post for spike: {OLD_LINK}"


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
    else:
        print(f"entity type:  {type(entity).__name__}")
        print(f"entity:       {entity!r}")


def _print_messages(messages: list[object], limit: int = 10) -> None:
    print(f"messages returned: {len(messages)} (limit={limit})")
    for msg in messages:
        text = getattr(msg, "message", None) or getattr(msg, "text", None) or ""
        text_preview = (text or "").replace("\n", " ")[:100]
        print(
            f"  id={getattr(msg, 'id', '?')} date={getattr(msg, 'date', '?')} text={text_preview!r}"
        )


async def _step_get_messages(client: TelegramClient, entity: object) -> None:
    _print_section("3. get_messages (last 10) — known to fail for bots")
    try:
        messages = await client.get_messages(entity, limit=10)
        _print_messages(messages, limit=10)
    except Exception as exc:
        print(f"get_messages FAILED: {type(exc).__name__}: {exc}")
        print("note: bots cannot use GetHistoryRequest (MTProto) — expected limitation")


async def _step_send_test_post(client: TelegramClient, entity: object) -> tuple[object, str] | None:
    _print_section("4. create test post via send_message")
    try:
        sent = await client.send_message(entity, POST_TEXT)
        sent_text = getattr(sent, "message", None) or getattr(sent, "text", None) or ""
        print(f"send_message OK: id={getattr(sent, 'id', '?')} text={sent_text!r}")
    except Exception as exc:
        print(f"send_message FAILED: {type(exc).__name__}: {exc}")
        print("cannot proceed to edit test without a post")
        return None
    else:
        return sent, sent_text


async def _step_edit_post(
    client: TelegramClient, entity: object, post: object, old_text: str
) -> bool:
    _print_section("5. edit_message (replace link) by id")
    try:
        new_text = old_text.replace(OLD_LINK, NEW_LINK)
        print(f"editing post id={getattr(post, 'id', '?')}")
        print(f"  old text: {old_text!r}")
        edited = await client.edit_message(entity, post, text=new_text)
        edited_text = getattr(edited, "message", None) or getattr(edited, "text", None) or ""
        print(f"  new text: {edited_text!r}")
        edit_ok = NEW_LINK in edited_text
        print(f"edit_message OK: link replaced = {edit_ok}")
    except Exception as exc:
        print(f"edit_message FAILED: {type(exc).__name__}: {exc}")
        return False
    else:
        return True


def _step_session_file() -> None:
    _print_section("6. session file")
    session_file = Path(SESSION_PATH)
    if session_file.exists():
        size = session_file.stat().st_size
        print(f"session file: {session_file} ({size} bytes)")
    else:
        print(f"WARNING: session file {session_file} not found")


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

        await _step_get_messages(client, entity)

        sent = await _step_send_test_post(client, entity)
        if sent is None:
            _print_section("spike result: PARTIAL — send_message failed")
            return 2
        post, sent_text = sent

        edit_ok = await _step_edit_post(client, entity, post, sent_text)
        if not edit_ok:
            _print_section("spike result: FAILED — edit_message not permitted")
            return 3

        _step_session_file()
        _print_section("spike result: SUCCESS (edit_message works; get_messages does not)")
    except Exception as exc:
        print(f"\nspike FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1
    else:
        return 0
    finally:
        await client.disconnect()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
