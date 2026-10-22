"""What can go wrong in parsed.

Every error parsed raises is a :class:`ParsedError`. A line that doesn't read is one error, a :class:`ReadError`,
whichever part refused it: the walk, a field's kind, or seared, whose ``ValidationError`` comes back as the word that
gave the value.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

#: What a :class:`ReadError` is: a line that doesn't read, or a value its field refuses.
type ReadKind = Literal['usage', 'validation']


class ParsedError(Exception):
    """The base of every error parsed raises."""


class DeclarationError(ParsedError, TypeError):
    """A command declared in a way parsed can't use: a constant of the wrong kind, or a base it can't read.

    It names the class and what's wrong, and says how to put it right. It's a ``TypeError`` too, as a mistake in a
    class's definition is in Python.
    """


class ReadError(ParsedError, ValueError):
    """A line that doesn't read, as one error: what's wrong, where it stands, how to say it, and what was meant.

    Its message is the text for people: what's wrong, with the words read up to it, then any did-you-mean and the
    hint. The rest is the same, as data, for a front end that renders it its own way (:meth:`to_json`). It's a
    ``ValueError`` too, as a value Python can't read is.

    Args:
        message: The text for people: ``fleet f1 jump: which system? `fleet f1 jump <system>```.
        kind: ``'usage'`` for a line that doesn't read; ``'validation'`` for a value its field refuses, once read.
        line: The line read.
        column: Where on the line it stands, from 0: the word at fault's start, or the line's end where a word is
            missing.
        word: The word at fault, as typed; ``None`` where one is missing.
        field: The field it's for, by attribute name, when the walk knows it.
        hint: How to say it, as a line with a ``<slot>`` for each value: ``fleet f1 jump <system>``.
        suggestions: What may have been meant: close matches for a word or a flag, or the words that may come next.
    """

    def __init__(  # noqa: PLR0913 -- one error, its parts named
        self,
        message: str,
        *,
        kind: ReadKind = 'usage',
        line: str = '',
        column: int = 0,
        word: str | None = None,
        field: str | None = None,
        hint: str | None = None,
        suggestions: Sequence[str] = (),
    ) -> None:
        """Hold the message and its parts."""
        super().__init__(message)
        self.message = message
        self.kind: ReadKind = kind
        self.line = line
        self.column = column
        self.word = word
        self.field = field
        self.hint = hint
        self.suggestions = tuple(suggestions)

    def to_json(self) -> dict[str, object]:
        """The error as data: ``error`` (its kind), ``message``, ``line`` and ``column``, and the parts it has."""
        out: dict[str, object] = {'error': self.kind, 'message': self.message, 'line': self.line, 'column': self.column}
        found = {'word': self.word, 'field': self.field, 'hint': self.hint}
        out.update({key: value for key, value in found.items() if value is not None})
        if self.suggestions:
            out['suggestions'] = list(self.suggestions)
        return out
