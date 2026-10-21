"""``Effect``: what running a command does.

A command declares it as ``EFFECT`` (see :class:`~parsed.command.Command`). It is optional, never inferred, and
inherited like any class attribute, so a base class can declare it for every command beneath it. The vocabulary is
zeared's, value for value and in the same order, so a command and a zeared contract are judged on one scale; parsed
keeps its own copy, since it never imports zeared.
"""

from __future__ import annotations

import enum
from typing import Literal

EffectName = Literal['read', 'write', 'action']


class Effect(enum.StrEnum):
    """What running a command does, ordered ``READ < WRITE < ACTION``.

    - ``READ``: running it changes nothing a caller could observe, so it's safe to repeat (HTTP's *safe*: ``GET``).
    - ``WRITE``: it changes state, but running it twice leaves the same state as running it once (HTTP's
      *idempotent*: ``PUT`` / ``DELETE``).
    - ``ACTION``: anything else. Repeating it repeats the effect, or the effect leaves the system (HTTP's ``POST``).

    Incidental effects (logging, metrics, caches, audit records) don't count. A command that may do several things
    declares the strongest, so the declaration is an upper bound. Asking first is a separate matter (``ASKS``): a
    command that asks may still be a ``WRITE``.

    The order ranks how much care a caller owes before running it. Comparisons use it, not string order, so
    ``max()`` of several effects is the strongest. An effect name (``'read'``) compares as its member; any other
    operand raises ``TypeError`` rather than falling back to ``str``'s lexical order, in which ``'action' < 'read'``.
    """

    READ = 'read'  # changes nothing a caller could observe
    WRITE = 'write'  # changes state; repeating it leaves the same state
    ACTION = 'action'  # anything else: not safe to repeat blindly

    def __lt__(self, other: object) -> bool:
        """Order by rank, not string order."""
        return _rank(self) < _rank(other)

    def __le__(self, other: object) -> bool:
        """Order by rank, not string order."""
        return _rank(self) <= _rank(other)

    def __gt__(self, other: object) -> bool:
        """Order by rank, not string order."""
        return _rank(self) > _rank(other)

    def __ge__(self, other: object) -> bool:
        """Order by rank, not string order."""
        return _rank(self) >= _rank(other)


# Keyed by value: a member is a ``str`` equal to its value, so members and
# effect names both look up here. Definition order is the rank.
_RANK: dict[str, int] = {member.value: rank for rank, member in enumerate(Effect)}
_NAMES = ', '.join(_RANK)


def _rank(value: object) -> int:
    """``value``'s rank: an ``Effect`` or an effect name, else ``TypeError``."""
    if isinstance(value, str) and value in _RANK:
        return _RANK[value]
    msg = f'cannot order an Effect against {value!r}: expected an Effect or one of {_NAMES}'
    raise TypeError(msg)


def effect_of(cls: type) -> Effect | None:
    """The effect ``cls`` declares, or ``None`` when it declares none.

    Reads ``cls.EFFECT``, inherited like any class attribute, so it works on any class, not only a command. An
    effect name normalises to its member. parsed never infers an effect: ``None`` means unknown, and the caller
    decides what that means.

    Raises:
        ValueError: ``EFFECT`` is a string that names no effect.
        TypeError: ``EFFECT`` is neither ``None``, an ``Effect`` nor a string.
    """
    value = getattr(cls, 'EFFECT', None)
    if value is None or isinstance(value, Effect):
        return value
    where = f'{cls.__qualname__}.EFFECT'
    if isinstance(value, str):
        if value in _RANK:
            return Effect(value)
        msg = f'{where} = {value!r}: expected one of {_NAMES}'
        raise ValueError(msg)
    msg = f'{where} must be an Effect, an effect name or None, not {type(value).__name__}'
    raise TypeError(msg)
