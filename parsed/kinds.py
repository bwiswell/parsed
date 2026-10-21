"""Kinds: how a field's words are read, declared as plain data.

A kind says how a field's words read on a line: what they read to, what Tab may offer, and how a value is written
back as words. Here kinds are only declared; reading them comes with the line's reader. Each is plain data, so a
module that declares commands imports nothing of an app's: a :class:`Name`'s lookups are the app's own, given at run
time by its category.

Every field of a command has a kind: its ``KINDS`` entry, or the default for its seared type (:func:`default_kind`):

=================================================  ==============  ================================================
seared field                                       default kind    its words
=================================================  ==============  ================================================
``Str``, ``Path``, ``UUID``                        :class:`Word`   a word, as written
``Int``, ``Float``, ``Decimal``                    :class:`Number` a number
``Bool``                                           :class:`Switch` ``true`` or ``false``; as a flag, given or not
``Enum``                                           :class:`Choice` one of its values
``TimeDelta``                                      :class:`Duration` ``90s``, ``10m``, ``1h30m``
``Date``, ``DateTime``, ``Time``                   :class:`Moment` ISO 8601
``T``, ``Union``, ``Tuple``, ``Bytes``, ``Dict``,  none            give it a kind in ``KINDS``
the arrays and frames, and any ``keyed`` field
=================================================  ==============  ================================================
"""

from __future__ import annotations

from dataclasses import dataclass

from seared import FieldKind, field_kind

from .errors import DeclarationError


@dataclass(frozen=True, slots=True)
class Kind:
    """The base of every kind: how a field's words are read."""


@dataclass(frozen=True, slots=True)
class Word(Kind):
    """A word, as written: a ``Str``, a ``Path`` or a ``UUID``, each checked by its field."""


@dataclass(frozen=True, slots=True)
class Number(Kind):
    """A number: an ``Int``, a ``Float`` or a ``Decimal``, its bounds checked by its field."""


@dataclass(frozen=True, slots=True)
class Switch(Kind):
    """``true`` or ``false``: a ``Bool``. As a flag, given or not."""


@dataclass(frozen=True, slots=True)
class Choice(Kind):
    """One of an ``Enum`` field's values."""


@dataclass(frozen=True, slots=True)
class Duration(Kind):
    """A span of time, ``90s``, ``10m`` or ``1h30m``: a ``TimeDelta``."""


@dataclass(frozen=True, slots=True)
class Moment(Kind):
    """A date, a time, or both, in ISO 8601: a ``Date``, a ``Time`` or a ``DateTime``."""


@dataclass(frozen=True, slots=True)
class Name(Kind):
    """One of an app's names, read to its key by what the app gives for its category.

    Attributes:
        category: What it names (``fleet``, ``station``, ``good``): the key the app's lookups are given by.
        scope: Another field of the command, whose value narrows the lookup: a station within the fleet's system,
            with ``scope='fleet'``. ``None`` looks across every name of the category.

    Raises:
        DeclarationError: The category or the scope isn't a name.
    """

    category: str
    scope: str | None = None

    def __post_init__(self) -> None:
        """Refuse a category or a scope that isn't a name."""
        if not isinstance(self.category, str) or not self.category.isidentifier():
            msg = f'Name({self.category!r}): a category is a name, such as fleet or station'
            raise DeclarationError(msg)
        if self.scope is not None and (not isinstance(self.scope, str) or not self.scope.isidentifier()):
            msg = f'Name({self.category!r}, scope={self.scope!r}): a scope is the name of another field'
            raise DeclarationError(msg)


_DEFAULTS: dict[FieldKind, Kind] = {
    FieldKind.STR: Word(),
    FieldKind.PATH: Word(),
    FieldKind.UUID: Word(),
    FieldKind.INT: Number(),
    FieldKind.FLOAT: Number(),
    FieldKind.DECIMAL: Number(),
    FieldKind.BOOL: Switch(),
    FieldKind.ENUM: Choice(),
    FieldKind.TIMEDELTA: Duration(),
    FieldKind.DATE: Moment(),
    FieldKind.DATETIME: Moment(),
    FieldKind.TIME: Moment(),
}


def default_kind(field: object) -> Kind | None:
    """The kind a field takes when ``KINDS`` gives it none, or ``None`` when its type has no word form."""
    if getattr(field, 'keyed', False):
        return None
    found = field_kind(field)
    return _DEFAULTS.get(found) if found is not None else None
