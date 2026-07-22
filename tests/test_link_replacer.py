"""Tests for ``src/telesoft/core/link_replacer.py``."""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock

import pytest
from telethon.tl.types import MessageEntityBold, MessageEntityItalic, MessageEntityTextUrl

from telesoft.core import telegram as telegram_module
from telesoft.core.link_replacer import (
    _adjust_entity_offsets,
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
    assert result["old_text"] == msg.message
    edit_mock.assert_awaited_once()


async def test_replace_link_in_post_empty_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Media-only post (message=None) → skipped=True, edit_message NOT called."""
    msg = _mk_msg(8, "")
    msg.message = None
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
    none_text.message = None

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
    none_text.message = None
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


async def test_replace_link_in_post_preserves_bold_entity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bold entity after the replaced link survives with shifted offset."""
    text = "https://old.example.com **bold text**"
    bold = MessageEntityBold(offset=24, length=9)
    msg = _mk_msg(11, text, [bold])
    edit_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(telegram_module, "edit_message", edit_mock)

    result = await replace_link_in_post(
        -1001234567890, msg, r"https://old\.example\.com", "https://new.io"
    )

    assert result["success"] is True
    assert result["match_source"] == "text"
    edit_mock.assert_awaited_once()
    entities = edit_mock.await_args.kwargs["formatting_entities"]
    assert entities is not None
    assert len(entities) == 1
    # new link "https://new.io" = 14 chars, old "https://old.example.com" = 23 chars
    # delta = -9 → entity.offset shifts from 24 to 15
    assert entities[0].offset == 15
    assert entities[0].length == 9
    # Original entity must NOT be mutated
    assert bold.offset == 24
    assert bold.length == 9


async def test_replace_link_in_post_preserves_italic_entity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An italic entity after the replaced link survives with shifted offset."""
    text = "see https://old.example.com *italic here*"
    italic = MessageEntityItalic(offset=28, length=11)
    msg = _mk_msg(12, text, [italic])
    edit_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(telegram_module, "edit_message", edit_mock)

    result = await replace_link_in_post(
        -1001234567890, msg, r"https://old\.example\.com", "https://new.io"
    )

    assert result["success"] is True
    edit_mock.assert_awaited_once()
    entities = edit_mock.await_args.kwargs["formatting_entities"]
    assert entities is not None
    # new link 14 chars, old 23 chars, delta -9 → offset 28 → 19
    assert entities[0].offset == 19
    assert entities[0].length == 11
    # Original not mutated
    assert italic.offset == 28


async def test_replace_link_in_post_no_entities_passes_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A post without entities → formatting_entities=None (no formatting applied)."""
    msg = _mk_msg(13, "https://old.example.com")
    edit_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(telegram_module, "edit_message", edit_mock)

    await replace_link_in_post(
        -1001234567890, msg, r"https://old\.example\.com", "https://new.example.com"
    )

    edit_mock.assert_awaited_once()
    assert edit_mock.await_args.kwargs["formatting_entities"] is None


async def test_replace_link_in_post_preserves_multiple_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multiple entities each shift by the cumulative delta of matches before them."""
    # Two links separated by spaces, two bold entities after each link.
    text = "old **one** old **two**"
    # match "old" at [0, 3] and [11, 14]
    bold1 = MessageEntityBold(offset=4, length=6)  # "**one**" at [4, 10]
    bold2 = MessageEntityBold(offset=15, length=6)  # "**two**" at [15, 21]
    msg = _mk_msg(14, text, [bold1, bold2])
    edit_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(telegram_module, "edit_message", edit_mock)

    result = await replace_link_in_post(-1001234567890, msg, "old", "REPLACEMENT")

    assert result["success"] is True
    assert result["replacements"] == 2
    entities = edit_mock.await_args.kwargs["formatting_entities"]
    assert entities is not None
    assert len(entities) == 2
    # "REPLACEMENT" is 11 chars, "old" is 3 chars → delta = +8 per match
    # bold1 after first match only → shift +8 → offset 4 → 12
    # bold2 after both matches → shift +16 → offset 15 → 31
    assert entities[0].offset == 12
    assert entities[0].length == 6
    assert entities[1].offset == 31
    assert entities[1].length == 6
    # originals untouched
    assert bold1.offset == 4
    assert bold2.offset == 15


def test_adjust_entity_offsets_no_matches_returns_copies() -> None:
    """Pattern does not match → entities returned as fresh copies, unchanged."""
    bold = MessageEntityBold(offset=3, length=8)
    adjusted = _adjust_entity_offsets([bold], "no match here", r"https://x\.com", "https://y.com")
    assert len(adjusted) == 1
    assert adjusted[0].offset == 3
    assert adjusted[0].length == 8
    assert adjusted[0] is not bold  # a copy


def test_adjust_entity_offsets_delta_positive() -> None:
    """New link longer than old → entity.offset shifts right (positive delta)."""
    text = "old link is here and more text follows after"
    # match at [0, 3] ("old"), new_link "veryold" (delta = +4)
    bold = MessageEntityBold(offset=20, length=10)
    adjusted = _adjust_entity_offsets([bold], text, "old", "veryold")
    assert adjusted[0].offset == 24
    assert adjusted[0].length == 10


def test_adjust_entity_offsets_delta_negative() -> None:
    """New link shorter than old → entity.offset shifts left (negative delta)."""
    text = "https://old.example.com is here"
    # match [0, 23], new_link "https://new.io" (14 chars, delta = -9)
    # entity at offset=25, length=6 (end=31) → shift -9 → offset=16, end=22
    # new_text = "https://new.io is here" (22 chars) → 16 + 6 = 22 ≤ 22 → valid
    bold = MessageEntityBold(offset=25, length=6)
    adjusted = _adjust_entity_offsets([bold], text, r"https://old\.example\.com", "https://new.io")
    assert adjusted[0].offset == 16
    assert adjusted[0].length == 6


def test_adjust_entity_offsets_delta_zero() -> None:
    """New link same length as old → offset/length unchanged."""
    text = "AAA is here"
    bold = MessageEntityBold(offset=7, length=4)
    adjusted = _adjust_entity_offsets([bold], text, "AAA", "BBB")
    assert adjusted[0].offset == 7
    assert adjusted[0].length == 4


def test_adjust_entity_offsets_match_inside_entity_grows_length() -> None:
    """Match strictly inside entity → entity.length grows by per-match delta."""
    text = "xxWORDyy"
    # entity covers "WORDyy" [2, 8], match "WORD" at [2, 6] inside entity
    bold = MessageEntityBold(offset=2, length=6)
    # new_link "PHRASE" (6 chars, delta = +2)
    adjusted = _adjust_entity_offsets([bold], text, "WORD", "PHRASE")
    assert adjusted[0].offset == 2
    assert adjusted[0].length == 8  # 6 + (6-4)


def test_adjust_entity_offsets_does_not_mutate_originals() -> None:
    """Returned entities are copies — original list/entities untouched."""
    bold = MessageEntityBold(offset=20, length=5)
    italic = MessageEntityItalic(offset=30, length=4)
    originals = [bold, italic]
    _adjust_entity_offsets(originals, "match at 0", "match", "REPLACEMENT")
    assert bold.offset == 20
    assert bold.length == 5
    assert italic.offset == 30
    assert italic.length == 4


def test_adjust_entity_offsets_empty_entities() -> None:
    """Empty entity list → empty result."""
    assert _adjust_entity_offsets([], "text", "t", "T") == []


def test_adjust_entity_offsets_crossing_boundary_match_starts_inside_entity() -> None:
    """Match starts inside entity, ends outside → entity length extended by delta."""
    text = "abcWORDrest"
    # entity covers "WORD" [3, 7], match "WORDr" at [3, 8] (starts inside, ends outside)
    bold = MessageEntityBold(offset=3, length=4)
    # new_link "PHRASE" (6 chars), match "WORDr" (5 chars) → delta = +1
    adjusted = _adjust_entity_offsets([bold], text, "WORDr", "PHRASE")
    assert len(adjusted) == 1
    assert adjusted[0].offset == 3
    assert adjusted[0].length == 5  # 4 + (6 - 5)
    # new_text = "abcPHRASEest" (12 chars), entity end = 3 + 5 = 8 ≤ 12 → valid
    # Original not mutated
    assert bold.offset == 3
    assert bold.length == 4


def test_adjust_entity_offsets_crossing_boundary_match_starts_outside_entity() -> None:
    """Match starts outside entity, ends inside → offset shifted to after replacement."""
    text = "abWORDyy"
    # entity covers "WORDyy" [2, 8], match "bW" at [1, 3] (starts outside, ends inside)
    bold = MessageEntityBold(offset=2, length=6)
    # new_link "ZZZ" (3 chars), match "bW" (2 chars) → delta = +1
    adjusted = _adjust_entity_offsets([bold], text, "bW", "ZZZ")
    assert len(adjusted) == 1
    # new_offset = m_start(1) + len(new_link)(3) = 4
    assert adjusted[0].offset == 4
    # e_length = 6 - (4 - 2) = 4
    assert adjusted[0].length == 4
    # new_text = "aZZZORDyy" (9 chars), entity end = 4 + 4 = 8 ≤ 9 → valid
    # Original not mutated
    assert bold.offset == 2
    assert bold.length == 6


def test_adjust_entity_offsets_drops_invalid_entities() -> None:
    """Entity with offset+length > len(new_text) after substitution → dropped."""
    text = "https://old.example.com here"
    # match [0, 23], new_link "x" (1 char, delta = -22)
    # entity at offset=28, length=6 (end=34) → shift -22 → offset=6, end=12
    # new_text = "x here" (6 chars) → 6 + 6 = 12 > 6 → dropped
    bold = MessageEntityBold(offset=28, length=6)
    adjusted = _adjust_entity_offsets([bold], text, r"https://old\.example\.com", "x")
    assert adjusted == []
    # Original not mutated
    assert bold.offset == 28
    assert bold.length == 6


async def test_replace_link_in_post_with_bold_crossing_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bold entity crossed by a match (starts inside, ends outside) is preserved + clamped."""
    text = "bold text LINK_HERE and more"
    # bold covers "bold text LINK_" [0, 15], match "LINK_HERE" at [10, 19]
    # (starts inside bold, ends outside) → case 3b: length extended by delta
    bold = MessageEntityBold(offset=0, length=15)
    msg = _mk_msg(20, text, [bold])
    edit_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(telegram_module, "edit_message", edit_mock)

    result = await replace_link_in_post(-1001234567890, msg, "LINK_HERE", "https://new.io")

    assert result["success"] is True
    assert result["match_source"] == "text"
    edit_mock.assert_awaited_once()
    entities = edit_mock.await_args.kwargs["formatting_entities"]
    assert entities is not None
    assert len(entities) == 1
    # new_link "https://new.io" (14 chars), match "LINK_HERE" (9 chars) → delta = +5
    # e_length = 15 + (14 - 9) = 20
    assert entities[0].offset == 0
    assert entities[0].length == 20
    # new_text = "bold text https://new.io and more" (33 chars), end = 0 + 20 = 20 ≤ 33 → valid
    # Original not mutated
    assert bold.offset == 0
    assert bold.length == 15


async def test_replace_link_in_post_preserves_bold_no_markdown_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bold post: raw text (message.message) used, NOT markdown (message.text).

    Simulates a real Telegram post where ``message.text`` carries markdown
    markers (``**``) but ``message.message`` is the raw plain text. The
    replacement must operate on ``message.message`` so no literal ``**`` leaks
    into the edited post.
    """
    # Raw text (what Telegram stores, entities offsets relative to this)
    raw_text = "bold text tg://resolve?domain=testbot&start=flow-123"
    # Markdown text (what message.text returns for display)
    markdown_text = "**bold text** tg://resolve?domain=testbot&start=flow-123"
    # Bold entity covers "bold text" [0, 9] in raw text
    bold = MessageEntityBold(offset=0, length=9)
    msg = MockMessage(
        id=30,
        text=markdown_text,
        chat_id=-1001234567890,
        message=raw_text,
        entities=[bold],
    )
    edit_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(telegram_module, "edit_message", edit_mock)

    result = await replace_link_in_post(
        -1001234567890, msg, r"tg://\S+", "https://new.example.com/bot-link"
    )

    assert result["success"] is True
    assert result["match_source"] == "text"
    edit_mock.assert_awaited_once()
    sent_text = edit_mock.await_args.args[2]
    # CRITICAL: no markdown markers in the edited text
    assert "**" not in sent_text
    assert "__" not in sent_text
    # Link replaced
    assert "https://new.example.com/bot-link" in sent_text
    assert "tg://resolve" not in sent_text
    # Bold entity preserved (offset relative to raw text, not markdown)
    entities = edit_mock.await_args.kwargs["formatting_entities"]
    assert entities is not None
    assert len(entities) == 1
    assert entities[0].offset == 0
    assert entities[0].length == 9
    assert entities[0].offset + entities[0].length <= len(sent_text)


async def test_replace_link_in_post_with_italic_no_markdown_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Italic post: raw text used, no ``__``/``_`` markers leak into result."""
    raw_text = "italic text https://t.me/example?start=app_789"
    markdown_text = "_italic text_ https://t.me/example?start=app_789"
    italic = MessageEntityItalic(offset=0, length=11)
    msg = MockMessage(
        id=31,
        text=markdown_text,
        chat_id=-1001234567890,
        message=raw_text,
        entities=[italic],
    )
    edit_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(telegram_module, "edit_message", edit_mock)

    result = await replace_link_in_post(
        -1001234567890, msg, r"https://t\.me/\S+", "https://new.example.com/tme"
    )

    assert result["success"] is True
    edit_mock.assert_awaited_once()
    sent_text = edit_mock.await_args.args[2]
    # CRITICAL: no markdown markers in the edited text
    assert "__" not in sent_text
    assert "**" not in sent_text
    assert "_" not in sent_text
    # Link replaced
    assert "https://new.example.com/tme" in sent_text
    entities = edit_mock.await_args.kwargs["formatting_entities"]
    assert entities is not None
    assert len(entities) == 1
    assert entities[0].offset == 0
    assert entities[0].length == 11
    assert entities[0].offset + entities[0].length <= len(sent_text)
