"""Regex-based link replacement utilities for Telegram channel posts.

Provides:
- :func:`replace_link` — pure regex substitution returning the new text and the
  number of replacements made.
- :func:`replace_link_in_post` — fetches a single message by id via the Telethon
  bot client (by-ID only — see ADR 2026-07-20-pr-14-spike-telethon), applies the
  regex, and calls ``edit_message`` when at least one replacement was made.
- :func:`validate_pattern` — compiles *pattern* to fail fast on invalid regex.
"""

from __future__ import annotations

import re
from typing import Any

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


async def replace_link_in_post(
    chat_id: int, message_id: int, pattern: str, new_link: str
) -> dict[str, Any]:
    """Fetch a post by id, regex-replace links, and edit it via Telethon.

    Returns a result dict describing the outcome:
    - ``{"success": False, "error": "Message not found", "message_id": ...}``
      when the message could not be fetched.
    - ``{"success": True, "skipped": True, ...}`` when zero replacements were
      made (the post is left untouched and ``edit_message`` is NOT called).
    - ``{"success": True, "edited": True, "replacements": N, ...}`` on a
      successful edit.
    - ``{"success": False, "error": str(exc), ...}`` if ``edit_message`` raises.
    """
    message = await telegram_module.get_message(chat_id, message_id)
    if message is None:
        return {
            "success": False,
            "error": "Message not found",
            "message_id": message_id,
        }

    text = message.text or ""
    new_text, count = replace_link(text, pattern, new_link)
    if count == 0:
        return {
            "success": True,
            "skipped": True,
            "message_id": message_id,
            "old_text": text,
            "new_text": text,
        }

    try:
        await telegram_module.edit_message(chat_id, message_id, new_text)
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
        "new_text": new_text,
        "replacements": count,
    }
