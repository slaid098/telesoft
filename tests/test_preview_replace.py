"""Tests for :func:`telesoft.core.link_replacer.preview_replace`."""

from __future__ import annotations

from unittest.mock import MagicMock

from telethon.tl.types import MessageEntityTextUrl

from telesoft.core.link_replacer import preview_replace
from tests.conftest import MockMessage

_PATTERN = r"https://old\.example\.com"
_NEW_LINK = "https://new.example.com"


async def test_preview_replace_returns_previews_and_total() -> None:
    """Three matching posts → 3 previews (default limit) + total_matches=3."""
    messages = [
        MockMessage(id=i + 1, text=f"see https://old.example.com/a{i}", chat_id=-100)
        for i in range(3)
    ]
    result = await preview_replace(messages, _PATTERN, _NEW_LINK)
    assert result["total_matches"] == 3
    assert len(result["previews"]) == 3
    for i, entry in enumerate(result["previews"]):
        assert entry["message_id"] == i + 1
        assert entry["match_source"] == "text"
        assert "https://old.example.com" in entry["before"]
        assert _NEW_LINK in entry["after"]


async def test_preview_replace_limit_caps_previews_not_total() -> None:
    """Five matches with limit=2 → 2 previews, total_matches=5."""
    messages = [MockMessage(id=i, text="https://old.example.com", chat_id=-100) for i in range(5)]
    result = await preview_replace(messages, _PATTERN, _NEW_LINK, limit=2)
    assert result["total_matches"] == 5
    assert len(result["previews"]) == 2


async def test_preview_replace_no_matches_returns_empty() -> None:
    """No matching posts → empty previews, total_matches=0."""
    messages = [
        MockMessage(id=1, text="nothing here", chat_id=-100),
        MockMessage(id=2, text="also nothing", chat_id=-100),
    ]
    result = await preview_replace(messages, _PATTERN, _NEW_LINK)
    assert result["total_matches"] == 0
    assert result["previews"] == []


async def test_preview_replace_entity_match_source() -> None:
    """URL inside a MessageEntityTextUrl entity → match_source='entity'."""
    entity = MessageEntityTextUrl(offset=0, length=4, url="https://old.example.com/path")
    msg = MockMessage(id=1, text="click here", chat_id=-100, entities=[entity])
    result = await preview_replace([msg], _PATTERN, _NEW_LINK)
    assert result["total_matches"] == 1
    assert len(result["previews"]) == 1
    entry = result["previews"][0]
    assert entry["match_source"] == "entity"
    assert entry["before"] == "https://old.example.com/path"
    assert entry["after"] == _NEW_LINK


async def test_preview_replace_prefers_text_over_entity() -> None:
    """When both text and entity url match, the text path wins."""
    entity = MessageEntityTextUrl(offset=0, length=4, url="https://old.example.com/entity")
    msg = MockMessage(id=1, text="https://old.example.com/text", chat_id=-100, entities=[entity])
    result = await preview_replace([msg], _PATTERN, _NEW_LINK)
    entry = result["previews"][0]
    assert entry["match_source"] == "text"
    assert "https://old.example.com/text" in entry["before"]


async def test_preview_replace_skips_non_matching_messages() -> None:
    """Non-matching messages are not counted and not previewed."""
    messages = [
        MockMessage(id=1, text="https://old.example.com", chat_id=-100),
        MockMessage(id=2, text="nothing here", chat_id=-100),
        MockMessage(id=3, text="https://old.example.com/again", chat_id=-100),
    ]
    result = await preview_replace(messages, _PATTERN, _NEW_LINK)
    assert result["total_matches"] == 2
    assert len(result["previews"]) == 2
    ids = [e["message_id"] for e in result["previews"]]
    assert ids == [1, 3]


async def test_preview_replace_before_after_carry_link_only_for_text() -> None:
    """For text matches, before/after carry a 50-char context window around the link."""
    msg = MockMessage(id=1, text="visit https://old.example.com today", chat_id=-100)
    result = await preview_replace([msg], _PATTERN, _NEW_LINK)
    entry = result["previews"][0]
    # Short post (< 100 chars) → context window covers the whole post
    assert entry["before"] == "visit https://old.example.com today"
    assert entry["after"] == f"visit {_NEW_LINK} today"


async def test_preview_replace_text_window_caps_at_50_chars_context() -> None:
    """Long posts show 50 chars before + matched link + 50 chars after, not the full post."""
    prefix = "x" * 80
    suffix = "y" * 80
    text = f"{prefix} https://old.example.com {suffix}"
    msg = MockMessage(id=2, text=text, chat_id=-100)
    result = await preview_replace([msg], _PATTERN, _NEW_LINK)
    entry = result["previews"][0]
    # 50 chars before + matched link + 50 chars after
    expected_len = 50 + len("https://old.example.com") + 50
    assert len(entry["before"]) == expected_len
    # context window starts 50 chars before the match — the space between the
    # prefix and the link lands at position 80, so the first 49 chars are "x"
    # and the 50th is the space.
    assert entry["before"].startswith("x" * 49 + " ")
    assert entry["before"].endswith(" " + "y" * 49)
    assert "https://old.example.com" in entry["before"]
    # after swaps in the new link
    assert _NEW_LINK in entry["after"]
    assert entry["after"].endswith(" " + "y" * 49)


async def test_preview_replace_short_post_shown_in_full() -> None:
    """Post shorter than 100 chars → before/after is the whole post (natural result)."""
    text = "see https://old.example.com here"
    msg = MockMessage(id=3, text=text, chat_id=-100)
    result = await preview_replace([msg], _PATTERN, _NEW_LINK)
    entry = result["previews"][0]
    assert entry["before"] == text
    assert entry["after"] == f"see {_NEW_LINK} here"


async def test_preview_replace_mixed_messages_preserves_order() -> None:
    """Previews appear in the same order as the input messages."""
    messages = [
        MockMessage(id=10, text="https://old.example.com/first", chat_id=-100),
        MockMessage(id=20, text="no link", chat_id=-100),
        MockMessage(id=30, text="https://old.example.com/second", chat_id=-100),
    ]
    result = await preview_replace(messages, _PATTERN, _NEW_LINK)
    ids = [e["message_id"] for e in result["previews"]]
    assert ids == [10, 30]


async def test_preview_replace_empty_input() -> None:
    """Empty message list → empty previews, total_matches=0."""
    result = await preview_replace([], _PATTERN, _NEW_LINK)
    assert result == {"previews": [], "total_matches": 0}


async def test_preview_replace_skips_none_text_and_no_entities() -> None:
    """Message with None text and no entity urls is never matched."""
    msg = MockMessage(id=1, text="", chat_id=-100, entities=None)
    msg.text = None
    result = await preview_replace([msg], _PATTERN, _NEW_LINK)
    assert result["total_matches"] == 0
    assert result["previews"] == []


async def test_preview_replace_limit_zero_returns_no_previews() -> None:
    """limit=0 → no previews but total_matches reflects all matches."""
    messages = [MockMessage(id=i, text="https://old.example.com", chat_id=-100) for i in range(2)]
    result = await preview_replace(messages, _PATTERN, _NEW_LINK, limit=0)
    assert result["total_matches"] == 2
    assert result["previews"] == []


async def test_preview_replace_does_not_call_telethon() -> None:
    """preview_replace is a pure dry-run: no Telethon edit should be invoked.

    Verifies via a sentinel entity that the url is NOT mutated in place (the
    real edit path mutates ``entity.url``; preview must leave it intact).
    """
    entity = MessageEntityTextUrl(offset=0, length=4, url="https://old.example.com/path")
    msg = MockMessage(id=1, text="click here", chat_id=-100, entities=[entity])
    await preview_replace([msg], _PATTERN, _NEW_LINK)
    assert entity.url == "https://old.example.com/path"


async def test_preview_replace_handles_mock_entity_without_url_attr() -> None:
    """MagicMock entities with .url attribute work like MessageEntityTextUrl."""
    entity = MagicMock()
    entity.url = "https://old.example.com"
    msg = MockMessage(id=1, text="click", chat_id=-100, entities=[entity])
    result = await preview_replace([msg], _PATTERN, _NEW_LINK)
    assert result["total_matches"] == 1
    assert result["previews"][0]["match_source"] == "entity"
