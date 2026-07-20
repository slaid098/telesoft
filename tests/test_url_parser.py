"""Tests for the Telegram post URL parser."""

from __future__ import annotations

import pytest

from telesoft.core.url_parser import (
    is_valid_post_url,
    parse_post_url,
    parse_post_urls,
)


def test_parse_public_channel_url() -> None:
    assert parse_post_url("https://t.me/mychannel/123") == ("mychannel", 123)


def test_parse_private_channel_url() -> None:
    assert parse_post_url("https://t.me/c/1234567890/456") == (-1001234567890, 456)


def test_parse_url_with_comment_query() -> None:
    assert parse_post_url("https://t.me/mychannel/123?comment=45") == ("mychannel", 123)


def test_parse_url_invalid_format_raises() -> None:
    with pytest.raises(ValueError):
        parse_post_url("https://google.com/abc")


def test_parse_url_non_tme_domain_raises() -> None:
    with pytest.raises(ValueError):
        parse_post_url("https://t.co/mychannel/123")


def test_parse_url_private_non_digit_raises() -> None:
    with pytest.raises(ValueError):
        parse_post_url("https://t.me/c/abc/456")


def test_parse_urls_batch() -> None:
    urls = ["https://t.me/mychannel/1", "https://t.me/c/1234567890/2"]
    assert parse_post_urls(urls) == [("mychannel", 1), (-1001234567890, 2)]


def test_parse_urls_batch_invalid_raises_with_index() -> None:
    urls = ["https://t.me/mychannel/1", "https://google.com/abc", "https://t.me/c/1/2"]
    with pytest.raises(ValueError, match="index 1"):
        parse_post_urls(urls)


def test_is_valid_post_url_true_false() -> None:
    assert is_valid_post_url("https://t.me/mychannel/123") is True
    assert is_valid_post_url("https://t.me/c/1234567890/456") is True
    assert is_valid_post_url("https://google.com/abc") is False
    assert is_valid_post_url("not a url") is False
