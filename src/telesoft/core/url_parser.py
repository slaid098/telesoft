"""Parse Telegram post URLs into ``(channel_identifier, message_id)`` pairs.

Supported formats:
    - ``https://t.me/<channel_username>/<message_id>`` (public channel)
    - ``https://t.me/c/<internal_id>/<message_id>`` (private channel; internal_id
      is converted to ``-100<internal_id>`` per Telegram MTProto conventions)
    - ``https://t.me/<channel_username>/<message_id>?comment=...`` (query ignored)
"""

from __future__ import annotations

import re

type ParsedPostURL = tuple[str | int, int]


_POST_URL_RE = re.compile(r"^https?://t\.me/(c/)?(\w+)/(\d+)")


def _raise_invalid(url: str) -> None:
    raise ValueError(f"invalid Telegram post URL: {url!r}")


def parse_post_url(url: str) -> ParsedPostURL:
    """Parse a single Telegram post URL into ``(channel_identifier, message_id)``."""
    match = _POST_URL_RE.match(url)
    if match is None:
        _raise_invalid(url)
        raise AssertionError

    is_private = match.group(1) is not None
    channel_part = match.group(2)
    message_id = int(match.group(3))

    if is_private:
        if not channel_part.isdigit():
            _raise_invalid(url)
            raise AssertionError
        return int(f"-100{channel_part}"), message_id

    return channel_part, message_id


def parse_post_urls(urls: list[str]) -> list[ParsedPostURL]:
    """Parse a list of post URLs; raises ValueError naming the bad URL and index."""
    parsed: list[ParsedPostURL] = []
    for index, url in enumerate(urls):
        try:
            parsed.append(parse_post_url(url))
        except ValueError as exc:
            raise ValueError(f"invalid URL at index {index}: {exc}") from exc
    return parsed


def is_valid_post_url(url: str) -> bool:
    """Return True if the URL is a parseable Telegram post URL."""
    try:
        parse_post_url(url)
    except ValueError:
        return False
    return True
