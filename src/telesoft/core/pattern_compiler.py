"""Pattern compiler: simple-mode wildcard expansion, full_replace tail
handling, and an orchestrator that picks the right strategy per *mode*.

Two public functions:

- :func:`compile_simple` — convert ``*`` wildcards to ``.*`` and escape the
  remaining literal pieces so a non-technical user can describe a link
  template without knowing regex syntax.
- :func:`compile_pattern` — orchestrator that selects the strategy based
  on ``mode`` (``"simple"``, ``"library"`` or ``"advanced"``) and optionally
  appends ``\\S*`` to the pattern so :func:`re.sub` replaces the whole link
  (``full_replace=True``) or leaves the tail in place
  (``full_replace=False``).
"""

from __future__ import annotations

import re


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


def compile_pattern(raw: str, mode: str, full_replace: bool = True) -> str:
    """Compile *raw* into a regex according to *mode* and *full_replace*.

    - ``mode="simple"`` → :func:`compile_simple` (``*`` → ``.*``)
    - ``mode="library"`` or ``mode="advanced"`` → *raw* is treated as a
      ready regex and returned as-is
    - ``full_replace=True`` → append ``\\S*`` to the compiled pattern if it
      does not already end with ``.*`` or ``\\S+`` so :func:`re.sub` replaces
      the whole link (default, "Полная замена") without swallowing trailing
      whitespace or text after the URL
    - ``full_replace=False`` → return the compiled pattern as-is so only
      the matched prefix is replaced and the tail stays ("Частичная")

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
    if full_replace and not compiled.endswith(".*") and not compiled.endswith(r"\S+"):
        compiled += r"\S*"
    return compiled
