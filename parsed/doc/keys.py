"""A command's key, for policy: its words and its slots' values, slashed, as a message's topic is.

:func:`command_key` gives the key an instance is said by, from the phrase :meth:`~parsed.tree.Tree.render` would say
it with (with names, the twin its values belong to): ``fleet/f1/mine``, ``detachment/d2/mine``,
``fleet/f1/dock/vesta``. Each value is written as a line writes it: a name's key, a number's digits, a span of time as
``1h30m``.

**Left out:** a slot of several words, the rest of the line, an optional slot at its default, and the flags. They're
a request's body, not its address, so a rule written for ``fleet/*/sell`` holds whatever goods are sold.

**A key's safety is its reader's:** a value holding ``/``, ``*``, ``$``, ``?`` or ``#`` makes a key a pattern
can't hold. parsed writes it as it is, and ``tooled`` refuses it, naming the kind whose resolver should map it.

**A chain's steps** each keep their own key (:func:`chain_keys`), so a policy allows a chain only when it allows every
step. A step's names are known where the chain will be by then, as its line says them.

:class:`~parsed.doc.CommandDoc`'s ``keys`` are each phrase's template, a ``{slot}`` where each one-word slot stands:
``fleet/{fleet}/dock/{station}``. An optional slot is in its template, and out of an instance's key while it holds its
default.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from parsed import _walk
from parsed.command import declaration

from .introspect import is_command_class

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from parsed.command import Command
    from parsed.names import Resolver


def command_key(command: Command, names: Mapping[str, Resolver] | None = None) -> str:
    """``command``'s key, as the module's docstring describes.

    Raises:
        TypeError: ``command`` isn't a command's instance.
        RenderError: No phrase of its command can say it (with names, a value they don't know).
    """
    cls = type(command)
    if not is_command_class(cls):
        msg = f'command_key() takes an instance of a command, got {command!r}'
        raise TypeError(msg)
    return _walk.key(declaration(cls), command, names)


def chain_keys(steps: Sequence[Command], names: Mapping[str, Resolver] | None = None) -> list[str]:
    """Each of a chain's steps' keys, in order, each step's names known where the steps before it move the chain.

    Raises:
        TypeError: A step isn't a command's instance.
        RenderError: No phrase of a step can say it.
    """
    keys: list[str] = []
    moved = None
    for step in steps:
        if not is_command_class(type(step)):
            msg = f"chain_keys() takes a chain's steps, instances of commands, got {step!r}"
            raise TypeError(msg)
        found = declaration(type(step))
        keys.append(_walk.key(found, step, names, moved))
        moved = _walk.moved_by(found, step, moved)
    return keys
