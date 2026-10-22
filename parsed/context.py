"""What a handler is given beside its command: the app's state, and where and how the line was said.

A handler is ``handler(command, ctx)``, and ``ctx`` is a :class:`Context`, made fresh for each line a session calls
(:meth:`parsed.app.Session.call`). Nothing behind it is global: two apps, or two sessions of one, never share one.

- **The app's:** ``ctx.state``, as the session opened it (typed by the app, ``Context[Controls]``), ``ctx.session``
  and ``ctx.app``.
- **The mount's:** ``ctx.mount``, its ``ctx.params`` (a service's settings, say), and ``ctx.names``, the resolvers
  the line was read with.
- **The line's:** ``ctx.line``, ``ctx.reading`` (each field's words, and parsed's own flags), ``ctx.phrase``, the
  phrase that said it (so a handler tells a twin's wording from its command's), and ``ctx.dry_run``, whether
  ``--dry-run`` was given.
- **The session's:** ``ctx.verbosity``, how much to say: ``0`` by default, more for more.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

# At runtime: tooling evaluates a class's annotations (`typing.get_type_hints`), and the context's name these.
from ._walk import Reading  # noqa: TC001
from .app import App, Mount, Session  # noqa: TC001

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .names import Resolver


@dataclass(frozen=True, slots=True)
class Context[S]:
    """What a handler is given beside its command (see the module).

    Attributes:
        session: The session that called the line: the app, open, and its state.
        mount: The mount the line went to.
        reading: What the line was read to: each field's words and value, and parsed's own flags.
    """

    session: Session[S]
    mount: Mount
    reading: Reading

    @property
    def state(self) -> S:
        """The app's state, as the session opened it."""
        return self.session.state

    @property
    def app(self) -> App:
        """The app."""
        return self.session.app

    @property
    def params(self) -> object:
        """The mount's parameters: what the app gave it when it mounted it."""
        return self.mount.params

    @property
    def names(self) -> Mapping[str, Resolver]:
        """The resolvers the line was read with, by category: the app's, and the mount's over them."""
        return self.mount.resolvers

    @property
    def line(self) -> str:
        """The line called."""
        return self.reading.line

    @property
    def phrase(self) -> str:
        """The phrase that said the line, as its command declares it: ``'detachment {detachment} mine'``."""
        return self.reading.end.bound.phrase.text

    @property
    def dry_run(self) -> bool:
        """Whether the line asks for a dry run, ``--dry-run``: what the command would do, done by nothing."""
        return 'dry-run' in self.reading.own

    @property
    def verbosity(self) -> int:
        """How much to say: ``0`` by default, more for more, as the session was opened with."""
        return self.session.verbosity
