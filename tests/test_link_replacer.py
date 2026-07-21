"""Tests for ``src/telesoft/core/link_replacer.py``."""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock

import pytest
from telethon.tl.types import MessageEntityTextUrl

from telesoft.core import telegram as telegram_module
from telesoft.core.link_replacer import (
    find_posts_with_pattern,
    replace_link,
    replace_link_in_post,
    replace_link_in_posts,
    validate_pattern,
)
from tests.conftest import MockMessage


def test_replace_link_basic() -> None:
    text = "Visit https://old.example.com today"
    new_text, count = replace_link(text, r"https://old\.example\.com", "https://new.example.com")
    assert new_text == "Visit https://new.example.com today"
    assert count == 1


def test_replace_link_multiple() -> None:
    text = "a https://old.example.com b https://old.example.com c"
    new_text, count = replace_link(text, r"https://old\.example\.com", "https://new.example.com")
    assert count == 2
    assert new_text == "a https://new.example.com b https://new.example.com c"


def test_replace_link_no_match() -> None:
    text = "nothing here"
    new_text, count = replace_link(text, r"https://old\.example\.com", "https://new.example.com")
    assert new_text == text
    assert count == 0


def test_replace_link_invalid_pattern_raises() -> None:
    with pytest.raises(re.error):
        replace_link("text", "[invalid", "new")


def test_validate_pattern_valid() -> None:
    pattern = r"https://old\.example\.com"
    assert validate_pattern(pattern) == pattern


def test_validate_pattern_invalid_raises() -> None:
    with pytest.raises(ValueError, match="invalid regex pattern"):
        validate_pattern("[invalid")


def _mk_msg(msg_id: int = 42, text: str = "", entities: list[object] | None = None) -> MockMessage:
    return MockMessage(id=msg_id, text=text, chat_id=-1001234567890, entities=entities)


async def test_replace_link_in_post_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful text edit: success=True, edited=True, replacements counted."""
    msg = _mk_msg(42, "visit https://old.example.com now")
    edit_mock = AsyncMock(return_value=AsyncMock())
    monkeypatch.setattr(telegram_module, "edit_message", edit_mock)

    result = await replace_link_in_post(
        -1001234567890, msg, r"https://old\.example\.com", "https://new.example.com"
    )
    assert result["success"] is True
    assert result["edited"] is True
    assert result["message_id"] == 42
    assert result["replacements"] == 1
    assert "https://new.example.com" in result["new_text"]
    edit_mock.assert_awaited_once()


async def test_replace_link_in_post_no_replacements(monkeypatch: pytest.MonkeyPatch) -> None:
    """When pattern does not match: skipped=True, edit_message NOT called."""
    msg = _mk_msg(5, "nothing to replace here")
    edit_mock = AsyncMock()
    monkeypatch.setattr(telegram_module, "edit_message", edit_mock)

    result = await replace_link_in_post(
        -1001234567890, msg, r"https://old\.example\.com", "https://new.example.com"
    )
    assert result["success"] is True
    assert result["skipped"] is True
    assert result["old_text"] == result["new_text"]
    edit_mock.assert_not_awaited()


async def test_replace_link_in_post_edit_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """When edit_message raises: success=False, error set to str(exc)."""
    msg = _mk_msg(7, "visit https://old.example.com")
    edit_mock = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(telegram_module, "edit_message", edit_mock)

    result = await replace_link_in_post(
        -1001234567890, msg, r"https://old\.example\.com", "https://new.example.com"
    )
    assert result["success"] is False
    assert "boom" in str(result["error"])
    assert result["old_text"] == msg.text
    edit_mock.assert_awaited_once()


async def test_replace_link_in_post_empty_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Media-only post (text=None) → skipped=True, edit_message NOT called."""
    msg = _mk_msg(8, "")
    msg.text = None
    edit_mock = AsyncMock()
    monkeypatch.setattr(telegram_module, "edit_message", edit_mock)

    result = await replace_link_in_post(
        -1001234567890, msg, r"https://old\.example\.com", "https://new.example.com"
    )
    assert result["success"] is True
    assert result["skipped"] is True
    edit_mock.assert_not_awaited()


async def test_replace_link_in_post_replaces_entity_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """URL inside an entity is mutated in-place and the message is edited via
    ``edit_message_entities`` with ``formatting_entities``.
    """
    entity = MessageEntityTextUrl(offset=0, length=4, url="https://old.example.com/path")
    msg = _mk_msg(42, "click here", [entity])
    edit_mock = AsyncMock()
    edit_entities_mock = AsyncMock()
    monkeypatch.setattr(telegram_module, "edit_message", edit_mock)
    monkeypatch.setattr(telegram_module, "edit_message_entities", edit_entities_mock)

    result = await replace_link_in_post(
        -1001234567890, msg, r"https://old\.example\.com/path", "https://new.example.com/edited"
    )

    assert result["success"] is True
    assert result["edited"] is True
    assert result["match_source"] == "entity"
    assert result["replacements"] == 1
    edit_mock.assert_not_awaited()
    edit_entities_mock.assert_awaited_once()
    sent_chat_id, sent_message, sent_entities = edit_entities_mock.await_args.args
    assert sent_chat_id == -1001234567890
    assert sent_message is msg
    assert sent_entities is msg.entities
    assert entity.url == "https://new.example.com/edited"


async def test_replace_link_in_post_prefers_text_match_over_entity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the pattern matches both text and entity url, text path wins."""
    entity = MessageEntityTextUrl(offset=0, length=4, url="https://old.example.com/path")
    msg = _mk_msg(42, "https://old.example.com/path here", [entity])
    edit_mock = AsyncMock()
    edit_entities_mock = AsyncMock()
    monkeypatch.setattr(telegram_module, "edit_message", edit_mock)
    monkeypatch.setattr(telegram_module, "edit_message_entities", edit_entities_mock)

    result = await replace_link_in_post(
        -1001234567890, msg, r"https://old\.example\.com", "https://new.example.com/edited"
    )

    assert result["match_source"] == "text"
    edit_mock.assert_awaited_once()
    edit_entities_mock.assert_not_awaited()
    assert entity.url == "https://old.example.com/path"


async def test_replace_link_in_post_entity_edit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When edit_message_entities raises: success=False with error set."""
    entity = MessageEntityTextUrl(offset=0, length=4, url="https://old.example.com/path")
    msg = _mk_msg(42, "click here", [entity])
    edit_entities_mock = AsyncMock(side_effect=RuntimeError("entity edit boom"))
    monkeypatch.setattr(telegram_module, "edit_message_entities", edit_entities_mock)

    result = await replace_link_in_post(
        -1001234567890, msg, r"https://old\.example\.com/path", "https://new.example.com/edited"
    )

    assert result["success"] is False
    assert "entity edit boom" in str(result["error"])
    edit_entities_mock.assert_awaited_once()


async def test_replace_link_in_post_skips_when_no_match_in_text_or_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No match in text or entity urls → skipped, no edit called."""
    entity = MessageEntityTextUrl(offset=0, length=4, url="https://other.example.com/path")
    msg = _mk_msg(42, "click here", [entity])
    edit_mock = AsyncMock()
    edit_entities_mock = AsyncMock()
    monkeypatch.setattr(telegram_module, "edit_message", edit_mock)
    monkeypatch.setattr(telegram_module, "edit_message_entities", edit_entities_mock)

    result = await replace_link_in_post(
        -1001234567890, msg, r"https://old\.example\.com", "https://new.example.com/edited"
    )

    assert result["success"] is True
    assert result["skipped"] is True
    edit_mock.assert_not_awaited()
    edit_entities_mock.assert_not_awaited()
    assert entity.url == "https://other.example.com/path"


async def test_find_posts_with_pattern_filters_matching() -> None:
    """Only messages whose text matches the pattern are returned."""
    pattern = r"https://old\.example\.com"
    matching = MockMessage(id=1, text="see https://old.example.com here", chat_id=-100)
    other = MockMessage(id=2, text="nothing here", chat_id=-100)
    empty = MockMessage(id=3, text="", chat_id=-100)
    none_text = MockMessage(id=4, text="", chat_id=-100)
    none_text.text = None

    result = await find_posts_with_pattern([matching, other, empty, none_text], pattern)

    assert result == [matching]


async def test_find_posts_with_pattern_no_matches() -> None:
    """No matches → empty list (does NOT raise)."""
    messages = [
        MockMessage(id=1, text="alpha", chat_id=-100),
        MockMessage(id=2, text="beta", chat_id=-100),
    ]
    result = await find_posts_with_pattern(messages, r"https://old\.example\.com")
    assert result == []


async def test_find_posts_with_pattern_matches_entity_url() -> None:
    """URL inside a MessageEntityTextUrl entity is matched."""
    pattern = r"https://old\.example\.com"
    entity = MagicMock()
    entity.url = "https://old.example.com"
    msg_with_entity = MockMessage(id=1, text="click here", chat_id=-100, entities=[entity])
    msg_plain = MockMessage(id=2, text="nothing", chat_id=-100, entities=None)

    result = await find_posts_with_pattern([msg_with_entity, msg_plain], pattern)

    assert result == [msg_with_entity]


async def test_find_posts_with_pattern_skips_when_text_and_entities_empty() -> None:
    """Message with no text and no entity urls is never matched."""
    pattern = r"https://old\.example\.com"
    no_text_no_entities = MockMessage(id=1, text="", chat_id=-100, entities=None)
    none_text = MockMessage(id=2, text="not empty", chat_id=-100)
    none_text.text = None
    none_text.entities = []

    result = await find_posts_with_pattern([no_text_no_entities, none_text], pattern)

    assert result == []


async def test_replace_link_in_posts_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Orchestrator returns ``{total, edited, failed, skipped}`` and calls edit per match."""
    messages = [
        MockMessage(id=10, text="https://old.example.com a", chat_id=-100),
        MockMessage(id=11, text="https://old.example.com b", chat_id=-100),
        MockMessage(id=12, text="no link here", chat_id=-100),
    ]

    edit_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(telegram_module, "edit_message", edit_mock)

    progress_calls: list[tuple[int, int, int]] = []

    async def _on_progress(edited: int, failed: int, total: int) -> None:
        progress_calls.append((edited, failed, total))

    summary = await replace_link_in_posts(
        -100, messages, r"https://old\.example\.com", "https://new.example.com", _on_progress
    )

    assert summary == {"total": 3, "edited": 2, "failed": 0, "skipped": 1}
    assert edit_mock.await_count == 2
    assert len(progress_calls) == 3
    assert progress_calls[-1] == (2, 0, 3)


async def test_replace_link_in_posts_without_progress_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Orchestrator works without an ``on_progress`` callback."""
    messages = [MockMessage(id=1, text="https://old.example.com", chat_id=-100)]
    monkeypatch.setattr(telegram_module, "edit_message", AsyncMock(return_value=None))

    summary = await replace_link_in_posts(
        -100, messages, r"https://old\.example\.com", "https://new.example.com"
    )

    assert summary == {"total": 1, "edited": 1, "failed": 0, "skipped": 0}
