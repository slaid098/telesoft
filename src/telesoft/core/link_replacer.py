"""Regex-based link replacement utilities for Telegram channel posts.

Provides:
- :func:`replace_link` — pure regex substitution returning the new text and the
  number of replacements made.
- :func:`validate_pattern` — compiles *pattern* to fail fast on invalid regex.
- :func:`find_posts_with_pattern` — filter a list of messages returned by
  :func:`telesoft.core.telegram.get_last_messages` down to those matching
  *pattern*. Does NOT fetch from Telegram.
- :func:`replace_link_in_post` — applies the regex to an already-fetched
  message object (no re-fetch) and calls ``edit_message`` /
  ``edit_message_entities`` when at least one replacement was made.
- :func:`replace_link_in_posts` — orchestrates :func:`replace_link_in_post`
  over a pre-filtered list of messages and reports a summary dict.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from telesoft.core import telegram as telegram_module


def validate_pattern(pattern: str) -> str:
    """Return *pattern* if it compiles as a regex, else raise ``ValueError``."""
    try:
        re.compile(pattern)
    except re.error as exc:
        msg = f"invalid regex pattern: {exc}"
        raise ValueError(msg) from exc
    return pattern


def replace_link(text: str, pattern: str, new_link: str) -> tuple[str, int]:
    """Replace every match of *pattern* in *text* with *new_link*.

    Returns ``(new_text, replacement_count)``. Raises ``re.error`` if *pattern*
    is not a valid regex.
    """
    count = len(re.findall(pattern, text))
    new_text = re.sub(pattern, new_link, text)
    return new_text, count


def _entity_urls(message: Any) -> list[str]:
    """Return ``MessageEntityTextUrl`` urls carried by *message*."""
    entities = getattr(message, "entities", None) or []
    return [e.url for e in entities if hasattr(e, "url")]


async def replace_link_in_post(
    chat_id: int, message: Any, pattern: str, new_link: str
) -> dict[str, Any]:
    """Regex-replace links in an already-fetched *message* and edit it via Telethon.

    Two replacement paths are supported:
    - URL appears in the raw ``message.text`` → regex substitution is applied
      and the post is edited via ``edit_message``.
    - URL appears inside a ``MessageEntityTextUrl`` entity (formatted link) →
      matching entities have their ``url`` mutated in-place to *new_link* and
      the post is edited via ``edit_message_entities`` (which uses Telethon's
      high-level ``client.edit_message(formatting_entities=...)``).

    Returns a result dict describing the outcome:
    - ``{"success": True, "skipped": True, ...}`` when zero replacements were
      made (the post is left untouched and no edit is performed).
    - ``{"success": True, "edited": True, "replacements": N, ...}`` on a
      successful edit.
    - ``{"success": False, "error": str(exc), ...}`` if the edit call raises.
    """
    message_id = int(message.id)
    regex = re.compile(pattern)
    text = message.text or ""
    new_text, text_count = replace_link(text, pattern, new_link)

    entities = getattr(message, "entities", None) or []
    entity_matches = [e for e in entities if hasattr(e, "url") and regex.search(e.url)]
    entity_count = len(entity_matches)

    if text_count == 0 and entity_count == 0:
        logger.info(
            "replace_link_in_post: msg {} no match (text_len={}, entities={})",
            message_id,
            len(text),
            len(entities),
        )
        return {
            "success": True,
            "skipped": True,
            "message_id": message_id,
            "old_text": text,
            "new_text": text,
        }

    try:
        if text_count > 0:
            logger.info(
                "replace_link_in_post: msg {} match in text (replacements={})",
                message_id,
                text_count,
            )
            await telegram_module.edit_message(chat_id, message_id, new_text)
            return {
                "success": True,
                "edited": True,
                "message_id": message_id,
                "old_text": text,
                "new_text": new_text,
                "replacements": text_count,
                "match_source": "text",
            }
        for e in entity_matches:
            e.url = new_link
        logger.info(
            "replace_link_in_post: msg {} match in entity (replacements={})",
            message_id,
            entity_count,
        )
        await telegram_module.edit_message_entities(chat_id, message, entities)
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "message_id": message_id,
            "old_text": text,
        }

    return {
        "success": True,
        "edited": True,
        "message_id": message_id,
        "old_text": text,
        "new_text": text,
        "replacements": entity_count,
        "match_source": "entity",
    }


async def find_posts_with_pattern(messages: list[Any], pattern: str) -> list[Any]:
    """Filter *messages* down to those matching *pattern* in text or entities.

    Works against the list returned by
    :func:`telesoft.core.telegram.get_last_messages` — does NOT fetch from
    Telegram. A message matches when *pattern* matches its raw ``text`` OR any
    URL carried by a ``MessageEntityTextUrl`` entity (formatted link). Messages
    with both ``text`` falsy and no entity urls are never matched. Returns the
    matching messages in their original order.
    """
    regex = re.compile(pattern)
    matching: list[Any] = []
    for m in messages:
        text = getattr(m, "text", None) or ""
        entity_urls = _entity_urls(m)
        full_text = text + " " + " ".join(entity_urls)
        matched = bool(full_text.strip()) and bool(regex.search(full_text))
        logger.info(
            "find_posts: msg {} text_len={} entity_urls={} matched={}",
            getattr(m, "id", None),
            len(text),
            len(entity_urls),
            matched,
        )
        if matched:
            matching.append(m)
    return matching


async def replace_link_in_posts(
    chat_id: int,
    messages: list[Any],
    pattern: str,
    new_link: str,
    on_progress: Callable[[int, int, int], Awaitable[None]] | None = None,
) -> dict[str, int]:
    """Edit every message in *messages* via :func:`replace_link_in_post`.

    Returns a summary ``{"total", "edited", "failed", "skipped"}``. When
    *on_progress* is supplied it is awaited after each message with the current
    ``(edited, failed, total)`` counters — used by the runner to push progress
    events without coupling to the orchestrator's loop.
    """
    total = len(messages)
    edited = 0
    failed = 0
    skipped = 0
    for message in messages:
        result = await replace_link_in_post(chat_id, message, pattern, new_link)
        if result.get("success"):
            if result.get("edited"):
                edited += 1
            else:
                skipped += 1
        else:
            failed += 1
        if on_progress is not None:
            await on_progress(edited, failed, total)
    return {"total": total, "edited": edited, "failed": failed, "skipped": skipped}
