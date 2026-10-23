"""Names: an app's own, read to their keys by the resolvers it gives for each category.

A :class:`~parsed.kinds.Name` declares only a category (``fleet``, ``station``); the names behind it are the app's,
and change while it runs. So an app passes its resolvers with each line it reads, by category::

    tree.read('fleet Prospector dock vesta', names={'fleet': fleets, 'station': stations})

**A resolver** is any object with :class:`Resolver`'s three methods. ``lookup`` reads a word to its key, or ``None``
for a word that names nothing; ``suggest`` gives the names close to a word, for a did-you-mean; ``options`` gives
every name it may be, for completion. Each takes the scope: the value of the field the ``Name`` is scoped by, once
that field is read (``Name('station', scope='fleet')`` looks for a station given the fleet's key), or ``None`` when
the ``Name`` has no scope or the line leaves its scope out. A scope that follows its chain (``follows=True``) is, in
a later step, where the steps before it have moved the chain: a place's key, or ``None`` where it's somewhere the
line doesn't say.

**Pairs** (:class:`~parsed.kinds.Pairs`, a keyed field's ``key value`` words, as a routine's variables) take a
:class:`PairsResolver`: a resolver for the keys, which gives each key's values a resolver of their own, since which
names a value may be depends on its key, and on the scope (the routine named).

**A category with no resolver reads as typed:** parsed never invents a key, since a normalization it guessed would
drift from the app's. So a line read with no names at all (a loose read, for a check or a render) keeps every name as
its words say it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence


class Resolver(Protocol):
    """What an app gives for a category of its names: how a word reads to a key, and what's close to it.

    ``scope`` is the value of the field the name is scoped by, as a string, or ``None``.
    """

    def lookup(self, word: str, scope: str | None) -> str | None:
        """The key ``word`` names, or ``None`` when it names nothing."""
        ...

    def suggest(self, word: str, scope: str | None) -> Sequence[str]:
        """The names close to ``word``, the closest first, for a did-you-mean."""
        ...

    def options(self, scope: str | None) -> Sequence[str]:
        """Every name it may be, for completion."""
        ...


class PairsResolver(Resolver, Protocol):
    """What an app gives for a :class:`~parsed.kinds.Pairs` category: its keys, and a resolver for each key's values.

    Its own ``lookup``, ``suggest`` and ``options`` read the keys.
    """

    def values(self, key: str, scope: str | None) -> Resolver | None:
        """The resolver for ``key``'s values, or ``None`` to keep them as typed."""
        ...
