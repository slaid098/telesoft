"""Tests for ``src/telesoft/core/pattern_compiler.py``."""

from __future__ import annotations

import re

import pytest

from telesoft.core.pattern_compiler import (
    apply_keep_tail,
    compile_pattern,
    compile_simple,
)


def test_compile_simple_basic() -> None:
    # Python 3.12+ re.escape() also escapes '-' — spec example omitted '\-'.
    assert compile_simple("https://t.me/bot?start=flow-*") == r"https://t\.me/bot\?start=flow\-.*"


def test_compile_simple_no_wildcard() -> None:
    assert compile_simple("https://t.me/bot") == r"https://t\.me/bot"


def test_compile_simple_multiple_wildcards() -> None:
    assert compile_simple("a*b*c") == r"a.*b.*c"


def test_compile_simple_leading_wildcard() -> None:
    assert compile_simple("*bar") == r".*bar"


def test_compile_simple_trailing_wildcard() -> None:
    assert compile_simple("foo*") == r"foo.*"


def test_compile_simple_only_wildcard() -> None:
    assert compile_simple("*") == r".*"


def test_compile_simple_empty() -> None:
    assert compile_simple("") == ""


def test_compile_simple_escapes_special_chars() -> None:
    assert compile_simple("a.c*d") == r"a\.c.*d"


def test_compile_simple_produces_compilable_regex() -> None:
    pattern = compile_simple("https://t.me/bot?start=flow-*")
    assert re.compile(pattern)
    assert re.search(pattern, "https://t.me/bot?start=flow-123")


def test_apply_keep_tail_optional_capture() -> None:
    pattern = r"https://t\.me/bot\?start=flow-\d+-\d+-\d+(-s-\d+)?"
    assert apply_keep_tail(pattern) == r"https://t\.me/bot\?start=flow-\d+-\d+-\d+"


def test_apply_keep_tail_bare_digits() -> None:
    pattern = r"https://t\.me/bot\?start=flow-\d+-s-\d+"
    assert apply_keep_tail(pattern) == r"https://t\.me/bot\?start=flow-\d+"


def test_apply_keep_tail_wildcard_tail() -> None:
    pattern = r"https://t\.me/bot\?start=foo-s-.*"
    assert apply_keep_tail(pattern) == r"https://t\.me/bot\?start=foo"


def test_apply_keep_tail_no_tail_returns_unchanged() -> None:
    pattern = r"https://t\.me/bot\?start=flow-\d+"
    assert apply_keep_tail(pattern) == pattern


def test_apply_keep_tail_empty_pattern() -> None:
    assert apply_keep_tail("") == ""


def test_compile_pattern_simple() -> None:
    assert compile_pattern("https://t.me/bot?start=flow-*", "simple", False) == (
        r"https://t\.me/bot\?start=flow\-.*"
    )


def test_compile_pattern_simple_with_keep_tail() -> None:
    compiled = compile_pattern("https://t.me/bot?start=flow-*-s-*", "simple", True)
    # After compile_simple: "https://t\.me/bot\?start=flow\-.*-s\-.*"
    # apply_keep_tail strips trailing "-s-.*" → "https://t\.me/bot\?start=flow\-.*"
    assert compiled == r"https://t\.me/bot\?start=flow\-.*"
    assert re.search(compiled, "https://t.me/bot?start=flow-abc-s-123")


def test_compile_pattern_advanced_passthrough() -> None:
    raw = r"https://t\.me/bot\?start=flow-\d+"
    assert compile_pattern(raw, "advanced", False) == raw


def test_compile_pattern_library_passthrough() -> None:
    raw = r"https://t\.me/bot\?start=flow-\d+"
    assert compile_pattern(raw, "library", False) == raw


def test_compile_pattern_advanced_with_keep_tail() -> None:
    raw = r"https://t\.me/bot\?start=flow-\d+(-s-\d+)?"
    assert compile_pattern(raw, "advanced", True) == r"https://t\.me/bot\?start=flow-\d+"


def test_compile_pattern_unknown_mode_raises() -> None:
    with pytest.raises(ValueError, match="unknown pattern mode"):
        compile_pattern("x", "regex", False)
