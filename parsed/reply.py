"""What running a line comes to: one envelope, the same for every parsed app, and the exit code it answers with.

A handler returns its command's ``REPLY`` (an instance of the seared class it declares), text, or nothing; or, to
ask before it acts, an :class:`Ask`.

**Asking first takes two phases.** A handler that asks returns ``Ask(question, then)`` and has done nothing yet;
``then`` acts, once the question is answered yes, and returns what a handler returns, another ``Ask`` among it.
``--yes`` on the line (or ``yes=True``) answers every question yes, on any command, whether or not it declares
``ASKS``. Otherwise the session's ``answer`` is asked, if it has one (:func:`terminal` prompts a person). A question
unanswered, or answered no, leaves the line undone, its question in the result.

A :class:`Result` holds what came of a line, however it went:

- ``line``, as read (a session's subject before it, where one was tried), and ``command``, the phrase that said it
  after its mount's prefix (``'relay run'``, ``'fleet {fleet} mine'``); ``None`` when the line doesn't read;
- ``ok``, whether it went well, and ``done``, whether its handler ran for real: run to its end, not for a dry run,
  to answer ``--help``, or to stop at a question;
- ``asks``, the question it stopped at, unanswered or answered no;
- ``met``, for a line that waits (``--until``), whether its reply met every condition, and ``waited``, how long it
  waited, in seconds;
- ``reply``, the ``REPLY`` its handler returned;
- ``text``, for people: the reply's ``str()`` (a reply class may define ``__str__``; seared leaves it free), the
  text the handler returned, the command's usage for ``--help``, the question it stopped at, or the error's message;
- ``error``, what went wrong, as data, ``{'error': kind, 'message': …}``: a ``ReadError``'s own (``usage`` or
  ``validation``), ``refused`` for a command for a person at a terminal run with none (``instead``, what's said in
  its place), ``timeout`` for a wait whose bound passed (its reply the last read), or ``handler`` for a handler that
  raised, has no binding, or returned what it shouldn't.

``result.code`` is the exit code: ``0`` when it went well (a question it stopped at among it), ``2`` for a line that
doesn't read, ``3`` for a command refused before it runs, ``4`` for a value its field refuses, ``7`` for a wait whose
bound passed, ``1`` for a handler's failure, as ``tooled``'s codes are where the meanings match.
``result.to_json()`` is the envelope as ``--json`` writes it, every key always there.
"""

from __future__ import annotations

import asyncio

# At runtime: tooling evaluates a class's annotations (`typing.get_type_hints`), and the result's name these.
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

# At runtime: tooling evaluates a class's annotations (`typing.get_type_hints`), the result's reply among them.
from seared import Seared  # noqa: TC002

#: The exit code for each kind of error; ``0`` for none.
CODES: Mapping[str, int] = MappingProxyType({'usage': 2, 'refused': 3, 'validation': 4, 'timeout': 7, 'handler': 1})

#: What answers a question a line asks: yes or no, from the question, sync or async (:func:`terminal` is one).
type Answer = Callable[[str], bool | Awaitable[bool]]


@dataclass(frozen=True, slots=True)
class Ask:
    """A handler's question, asked before it acts: ``then`` acts, once the question is answered yes.

    Attributes:
        question: What's asked, for a person: ``'Buy a hauler for 1,200 credits?'``.
        then: What acts on a yes: a callable of nothing, sync or async, returning what a handler returns, its
            ``REPLY``, text, nothing, or another ``Ask``.

    Raises:
        TypeError: ``question`` isn't a sentence, or ``then`` isn't callable.
    """

    question: str
    then: Callable[[], object]

    def __post_init__(self) -> None:
        """Refuse a question that isn't one, or a ``then`` that can't be called."""
        if not isinstance(self.question, str) or not self.question.strip():
            msg = f'Ask({self.question!r}, …): a question is a sentence, for a person'
            raise TypeError(msg)
        if not callable(self.then):
            msg = f'Ask({self.question!r}, {self.then!r}): then is what acts on a yes, a callable of nothing'
            raise TypeError(msg)


async def terminal(question: str) -> bool:
    """Ask a person at a terminal: ``question [y/N]``; yes for ``y`` or ``yes``, case aside, no for anything else.

    The end of input is a no. It reads in a thread, so the session's event loop goes on meanwhile.
    """
    try:
        said = await asyncio.to_thread(input, f'{question} [y/N] ')
    except EOFError:
        return False
    return said.strip().lower() in {'y', 'yes'}


@dataclass(frozen=True, slots=True)
class Result:
    """What came of a line (see the module).

    Attributes:
        line: The line run, as read: a subject's words before it, where one was tried.
        command: The phrase that said it, after its mount's prefix; ``None`` when it doesn't read.
        ok: Whether it went well.
        done: Whether its handler ran for real: to its end, not for a dry run, to answer ``--help``, or to stop at a
            question.
        asks: The question it stopped at, unanswered or answered no; ``None`` if none.
        met: Whether its reply met every ``--until`` condition; ``None`` for a line that doesn't wait.
        waited: How long it waited, in seconds; ``None`` for a line that doesn't wait.
        reply: The ``REPLY`` its handler returned, or ``None``.
        text: For people: the reply's ``str()``, the handler's text, the usage, the question, or the error's message.
        error: What went wrong, as data: ``{'error': kind, 'message': …}`` and its parts; ``None`` if nothing did.
        exception: The exception behind the error, for a program that wants it; never written out.
    """

    line: str
    command: str | None = None
    ok: bool = True
    done: bool = False
    asks: str | None = None
    met: bool | None = None
    waited: float | None = None
    reply: Seared | None = None
    text: str | None = None
    error: Mapping[str, object] | None = None
    exception: BaseException | None = field(default=None, compare=False, repr=False)

    @property
    def code(self) -> int:
        """The exit code: ``0``, or its error kind's, as :data:`CODES` gives it (``usage`` 2, ``refused`` 3, …)."""
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
            'asks': self.asks,
            'met': self.met,
            'waited': self.waited,
            'reply': None if self.reply is None else type(self.reply).dump(self.reply),
            'text': self.text,
            'error': None if self.error is None else dict(self.error),
        }
