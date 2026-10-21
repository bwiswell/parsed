"""What can go wrong in parsed.

Every error parsed raises is a :class:`ParsedError`. seared's own errors (a value that fails its field) stay
seared's, and pass through as they are.
"""

from __future__ import annotations


class ParsedError(Exception):
    """The base of every error parsed raises."""


class DeclarationError(ParsedError, TypeError):
    """A command declared in a way parsed can't use: a constant of the wrong kind, or a base it can't read.

    It names the class and what's wrong, and says how to put it right. It's a ``TypeError`` too, as a mistake in a
    class's definition is in Python.
    """
