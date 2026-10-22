"""What running a line comes to: one envelope, the same for every parsed app, and the exit code it answers with.

A handler returns its command's ``REPLY`` (an instance of the seared class it declares), text, or nothing. A
:class:`Result` holds what came of a line, however it went:

- ``line``, and ``command``, the phrase that said it after its mount's prefix (``'relay run'``,
  ``'fleet {fleet} mine'``); ``None`` when the line doesn't read;
- ``ok``, whether it went well, and ``done``, whether its handler ran for real: run to its end, not for a dry run
  or to answer ``--help``;
- ``reply``, the ``REPLY`` its handler returned;
- ``text``, for people: the reply's ``str()`` (a reply class may define ``__str__``; seared leaves it free), the
  text the handler returned, the command's usage for ``--help``, or the error's message;
- ``error``, what went wrong, as data, ``{'error': kind, 'message': …}``: a ``ReadError``'s own (``usage`` or
  ``validation``), or ``handler`` for a handler that raised, has no binding, or returned what it shouldn't.

``result.code`` is the exit code: ``0`` when it went well, ``2`` for a line that doesn't read, ``4`` for a value its
field refuses, ``1`` for a handler's failure, as ``tooled``'s codes are where the meanings match.
``result.to_json()`` is the envelope as ``--json`` writes it, every key always there.
"""

from __future__ import annotations

# At runtime: tooling evaluates a class's annotations (`typing.get_type_hints`), and the result's name these.
from collections.abc import Mapping  # noqa: TC003
from dataclasses import dataclass, field
from types import MappingProxyType

from seared import Seared  # noqa: TC002

#: The exit code for each kind of error; ``0`` for none.
CODES: Mapping[str, int] = MappingProxyType({'usage': 2, 'validation': 4, 'handler': 1})


@dataclass(frozen=True, slots=True)
class Result:
    """What came of a line (see the module).

    Attributes:
        line: The line run.
        command: The phrase that said it, after its mount's prefix; ``None`` when it doesn't read.
        ok: Whether it went well.
        done: Whether its handler ran for real: to its end, not for a dry run or to answer ``--help``.
        reply: The ``REPLY`` its handler returned, or ``None``.
        text: For people: the reply's ``str()``, the handler's text, the usage, or the error's message.
        error: What went wrong, as data: ``{'error': kind, 'message': …}`` and its parts; ``None`` if nothing did.
        exception: The exception behind the error, for a program that wants it; never written out.
    """

    line: str
    command: str | None = None
    ok: bool = True
    done: bool = False
    reply: Seared | None = None
    text: str | None = None
    error: Mapping[str, object] | None = None
    exception: BaseException | None = field(default=None, compare=False, repr=False)

    @property
    def code(self) -> int:
        """The exit code: ``0``, or its error kind's (``usage`` 2, ``validation`` 4, ``handler`` 1)."""
        if self.error is None:
            return 0
        return CODES.get(str(self.error.get('error')), 1)

    def to_json(self) -> dict[str, object]:
        """The envelope, as ``--json`` writes it: every key, the reply dumped as seared writes it."""
        return {
            'command': self.command,
            'line': self.line,
            'ok': self.ok,
            'done': self.done,
            'reply': None if self.reply is None else type(self.reply).dump(self.reply),
            'text': self.text,
            'error': None if self.error is None else dict(self.error),
        }
