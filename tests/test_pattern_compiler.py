"""Tests for ``src/telesoft/core/pattern_compiler.py``."""

from __future__ import annotations

import re

import pytest

from telesoft.core.pattern_compiler import (
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


def test_compile_pattern_simple_default_full_replace_appends_tail() -> None:
    """full_replace=True (default) appends \\S* to simple-mode patterns without a tail."""
    compiled = compile_pattern("https://t.me/bot?start=flow-123", "simple", True)
    assert compiled.endswith(r"\S*")
    assert re.search(compiled, "https://t.me/bot?start=flow-123-s-456")


def test_compile_pattern_simple_without_full_replace_keeps_pattern() -> None:
    """full_replace=False — the simple-mode pattern stays as-is (no .* appended)."""
    compiled = compile_pattern("https://t.me/bot?start=flow-", "simple", False)
    assert compiled == r"https://t\.me/bot\?start=flow\-"
    assert not compiled.endswith(".*")


def test_compile_pattern_simple_with_trailing_wildcard_not_duplicated() -> None:
    """full_replace=True — when the pattern already ends with .* it is not duplicated."""
    compiled = compile_pattern("https://t.me/bot?start=flow-*", "simple", True)
    assert compiled == r"https://t\.me/bot\?start=flow\-.*"
    assert not compiled.endswith(".*.*")


def test_compile_pattern_simple_with_trailing_s_plus_not_appended() -> None:
    """full_replace=True — when the pattern ends with \\S+ nothing is appended."""
    compiled = compile_pattern(r"https://t\.me/bot\?\S+", "advanced", True)
    assert compiled == r"https://t\.me/bot\?\S+"


def test_compile_pattern_advanced_passthrough_default_full_replace() -> None:
    """advanced mode with full_replace=True appends \\S* to a bare pattern."""
    compiled = compile_pattern(r"https://t\.me/bot\?start=flow-\d+", "advanced", True)
    assert compiled == r"https://t\.me/bot\?start=flow-\d+\S*"


def test_compile_pattern_advanced_without_full_replace_passthrough() -> None:
    """advanced mode with full_replace=False returns the raw pattern unchanged."""
    raw = r"https://t\.me/bot\?start=flow-\d+"
    assert compile_pattern(raw, "advanced", False) == raw


def test_compile_pattern_library_passthrough_with_full_replace() -> None:
    """library mode behaves like advanced — appends \\S* with full_replace=True."""
    compiled = compile_pattern(r"https://t\.me/bot\?start=flow-\d+", "library", True)
    assert compiled == r"https://t\.me/bot\?start=flow-\d+\S*"


def test_compile_pattern_library_without_full_replace() -> None:
    """library mode with full_replace=False returns the raw pattern unchanged."""
    raw = r"https://t\.me/bot\?start=flow-\d+"
    assert compile_pattern(raw, "library", False) == raw


def test_compile_pattern_default_full_replace_is_true() -> None:
    """The default value of full_replace is True (backward-compat with issue #63)."""
    compiled = compile_pattern(r"https://t\.me/bot\?start=flow-\d+", "advanced")
    assert compiled.endswith(r"\S*")


def test_compile_pattern_unknown_mode_raises() -> None:
    with pytest.raises(ValueError, match="unknown pattern mode"):
        compile_pattern("x", "regex", False)
