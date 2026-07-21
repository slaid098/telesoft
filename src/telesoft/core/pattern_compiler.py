"""Pattern compiler: simple-mode wildcard expansion, keep_tail trimming,
and an orchestrator that picks the right strategy per *mode*.

Three public functions:

- :func:`compile_simple` — convert ``*`` wildcards to ``.*`` and escape the
  remaining literal pieces so a non-technical user can describe a link
  template without knowing regex syntax.
- :func:`apply_keep_tail` — strip an optional ``-s-<digits>`` tail off the
  end of a regex so :func:`re.sub` only replaces the prefix and the tail
  survives in the original post.
- :func:`compile_pattern` — orchestrator that selects the strategy based on
  ``mode`` (``"simple"``, ``"library"`` or ``"advanced"``) and optionally
  applies :func:`apply_keep_tail`.
"""

from __future__ import annotations

import re

_TAIL_RE = re.compile(r"(?:\(-s-\\d\+\)\?|\\-s\\-\\d\+|\\-s\\-\.\*|-s-\\d\+|-s-\.\*)\Z")


def compile_simple(raw: str) -> str:
    """Convert a simple-mode wildcard pattern to a regex.

    Splits *raw* on ``*``, escapes every piece with :func:`re.escape`, and
    rejoins them with ``.*`` so a ``*`` matches any run of characters.

    Example::

        compile_simple("https://t.me/bot?start=flow-*")
        -> "https://t\\.me/bot\\?start=flow-.*"
    """
    parts = raw.split("*")
    return ".*".join(re.escape(part) for part in parts)


def apply_keep_tail(pattern: str) -> str:
    """Strip an optional ``-s-<tail>`` segment off the end of *pattern*.

    Recognises the forms documented in issue #55:

    - ``(-s-\\d+)?`` — optional captured digits tail
    - ``-s-\\d+`` — bare digits tail
    - ``-s-.*`` — wildcard tail

    When a tail is found it is removed so :func:`re.sub` only replaces the
    prefix and leaves the tail in the original post. When no tail is present
    *pattern* is returned unchanged.

    Example::

        apply_keep_tail(r"https://t\\.me/bot\\?start=flow-\\d+-\\d+-\\d+(-s-\\d+)?")
        -> r"https://t\\.me/bot\\?start=flow-\\d+-\\d+-\\d+"
    """
    match = _TAIL_RE.search(pattern)
    if match is None:
        return pattern
    return pattern[: match.start()]


def compile_pattern(raw: str, mode: str, keep_tail: bool) -> str:
    """Compile *raw* into a regex according to *mode* and *keep_tail*.

    - ``mode="simple"`` → :func:`compile_simple` (``*`` → ``.*``)
    - ``mode="library"`` or ``mode="advanced"`` → *raw* is treated as a
      ready regex and returned as-is
    - ``keep_tail=True`` → :func:`apply_keep_tail` strips a trailing
      ``-s-*`` segment so it survives the replacement

    Raises :class:`ValueError` for an unknown *mode* so the router can map
    it to a 422 response.
    """
    if mode == "simple":
        compiled = compile_simple(raw)
    elif mode in ("library", "advanced"):
        compiled = raw
    else:
        msg = f"unknown pattern mode: {mode!r}"
        raise ValueError(msg)
    if keep_tail:
        compiled = apply_keep_tail(compiled)
    return compiled
