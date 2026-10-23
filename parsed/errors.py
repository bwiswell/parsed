"""What can go wrong in parsed.

Every error parsed raises is a :class:`ParsedError`. A line that doesn't read is one error, a :class:`ReadError`,
whichever part refused it: the walk, a field's kind, or seared, whose ``ValidationError`` comes back as the word that
gave the value. A wait whose bound passes is a :class:`TimedOutError`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

    from seared import Seared

#: What a :class:`ReadError` is: a line that doesn't read, or a value its field refuses.
type ReadKind = Literal['usage', 'validation']


class ParsedError(Exception):
    """The base of every error parsed raises."""


class DeclarationError(ParsedError, TypeError):
    """A command, a tree or an app declared in a way parsed can't use.

    A constant of the wrong kind, a base it can't read, phrases or mounts that would read a line two ways, or a
    handler bound twice. It names the class or the mount and what's wrong, and says how to put it right. It's a
    ``TypeError`` too, as a mistake in a class's definition is in Python.
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


class TimedOutError(ParsedError, TimeoutError):
    """A wait whose bound passed before its reply met every condition: the last reply, and how long it waited.

    Its message names the command and the conditions: ``fleets show {fleet}: docked=true not met within 30s``. It's
    a ``TimeoutError`` too, as a wait that runs out is in Python.

    Args:
        message: The text for people.
        reply: The last reply read.
        waited: How long it waited, in seconds.
    """

    def __init__(self, message: str, *, reply: Seared, waited: float) -> None:
        """Hold the message, the last reply and the time waited."""
        super().__init__(message)
        self.message = message
        self.reply = reply
        self.waited = waited


class RenderError(ParsedError, ValueError):
    """An instance no phrase of its command can say: a value no line can hold, or one the app's names don't know.

    Its message names the command and why. It's a ``ValueError`` too, as a value that can't be written is.
    """
