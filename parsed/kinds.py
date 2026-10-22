"""Kinds: how a field's words are read, declared as plain data.

A kind says how a field's words read on a line: what they read to, what Tab may offer, and how a value is written
back as words. Each is plain data, so a module that declares commands imports nothing of an app's: a :class:`Name`'s
lookups are the app's own, given at run time by its category.

**Reading a word** (:meth:`Kind.read`) gives the field's wire value, what seared's ``load`` takes and a tool call
would send: seconds for a span of time, an ``Enum``'s value for one of its words. seared then checks it as it checks
any value, bounds and all. A word a kind can't read raises a ``ValueError`` saying what it should be.

Every field of a command has a kind: its ``KINDS`` entry, or the default for its seared type (:func:`default_kind`):

=================================================  ==============  ================================================
seared field                                       default kind    its words
=================================================  ==============  ================================================
``Str``, ``Path``, ``UUID``                        :class:`Word`   a word, as written; a ``UUID`` checked
``Int``, ``Float``, ``Decimal``                    :class:`Number` a number, its thousands grouped by commas or not
``Bool``                                           :class:`Switch` ``true`` or ``false``; as a flag, given or not
``Enum``                                           :class:`Choice` one of its values, case aside
``TimeDelta``                                      :class:`Duration` ``90s``, ``10m``, ``2h``, ``1h30m``
``Date``, ``DateTime``, ``Time``                   :class:`Moment` ISO 8601
``T``, ``Union``, ``Tuple``, ``Bytes``, ``Dict``,  none            give it a kind in ``KINDS``
the arrays and frames, and any ``keyed`` field
=================================================  ==============  ================================================
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import TYPE_CHECKING

from seared import FieldKind, field_kind

from .errors import DeclarationError

if TYPE_CHECKING:
    from seared import Field

#: A number with its thousands grouped by commas: ``1,000``, ``-12,500.5``.
_GROUPED = re.compile(r'[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?')
_WHOLE = re.compile(r'[+-]?\d+')
_DECIMAL = re.compile(r'[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?')
_SPAN = re.compile(r'(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m)?(?:(\d+(?:\.\d+)?)s)?')


@dataclass(frozen=True, slots=True)
class Kind:
    """The base of every kind: how a field's words are read."""

    def read(self, word: str, field: Field) -> object:  # noqa: ARG002 -- every kind reads alike
        """The field's wire value for ``word``, for seared to load: here, the word as written.

        Raises:
            ValueError: ``word`` isn't one this kind reads; its message says what one should be.
        """
        return word


@dataclass(frozen=True, slots=True)
class Word(Kind):
    """A word, as written: a ``Str``, a ``Path`` or a ``UUID``, each checked by its field."""

    def read(self, word: str, field: Field) -> object:
        """The word as written, once a ``UUID``'s is checked to be one."""
        if field_kind(field) is FieldKind.UUID:
            try:
                uuid.UUID(word)
            except ValueError:
                msg = f'{word!r} is not a UUID'
                raise ValueError(msg) from None
        return word


@dataclass(frozen=True, slots=True)
class Number(Kind):
    """A number: an ``Int``, a ``Float`` or a ``Decimal``, its bounds checked by its field."""

    def read(self, word: str, field: Field) -> object:
        """An ``int`` for an ``Int``, a ``float`` for a ``Float``, and the digits for a ``Decimal``, kept exact.

        Its thousands may be grouped by commas (``1,000``); any other comma isn't a number's.
        """
        text = word.replace(',', '') if _GROUPED.fullmatch(word) else word
        if field_kind(field) is FieldKind.INT:
            if not _WHOLE.fullmatch(text):
                msg = f'{word!r} is not a whole number'
                raise ValueError(msg)
            return int(text)
        if not _DECIMAL.fullmatch(text):
            msg = f'{word!r} is not a number'
            raise ValueError(msg)
        return text if field_kind(field) is FieldKind.DECIMAL else float(text)


@dataclass(frozen=True, slots=True)
class Switch(Kind):
    """``true`` or ``false``: a ``Bool``. As a flag, given or not."""

    def read(self, word: str, field: Field) -> object:  # noqa: ARG002 -- every kind reads alike
        """``True`` for ``true`` and ``False`` for ``false``, case aside."""
        found = {'true': True, 'false': False}.get(word.lower())
        if found is None:
            msg = f'{word!r} is not true or false'
            raise ValueError(msg)
        return found


@dataclass(frozen=True, slots=True)
class Choice(Kind):
    """One of an ``Enum`` field's values."""

    def read(self, word: str, field: Field) -> object:
        """The value of the member the word says, case aside: the member whose value is written so."""
        values = [member.value for member in getattr(field, 'enum', ())]
        exact = [value for value in values if str(value) == word]
        found = exact or [value for value in values if str(value).lower() == word.lower()]
        if len(found) != 1:
            said = [str(value) for value in values]
            listed = f'{", ".join(said[:-1])} or {said[-1]}' if len(said) > 1 else ''.join(said)
            msg = f'{word!r} is not one of {listed}'
            raise ValueError(msg)
        return found[0]


@dataclass(frozen=True, slots=True)
class Duration(Kind):
    """A span of time, ``90s``, ``10m`` or ``1h30m``: a ``TimeDelta``."""

    def read(self, word: str, field: Field) -> object:  # noqa: ARG002 -- every kind reads alike
        """The seconds the span says, as seared writes a ``TimeDelta``: hours, minutes and seconds, each optional."""
        found = _SPAN.fullmatch(word.lower())
        if found is None or not any(found.groups()):
            msg = f'{word!r} is not a span of time: say 90s, 10m, 2h or 1h30m'
            raise ValueError(msg)
        hours, minutes, seconds = (float(part or 0) for part in found.groups())
        return hours * 3600 + minutes * 60 + seconds


#: What a moment's word is read by, and what one looks like, by its field's type.
_MOMENTS = {
    FieldKind.DATE: (date.fromisoformat, 'a date: say 2026-10-21'),
    FieldKind.TIME: (time.fromisoformat, 'a time: say 14:30'),
    FieldKind.DATETIME: (datetime.fromisoformat, 'a date and time: say 2026-10-21T14:30'),
}


@dataclass(frozen=True, slots=True)
class Moment(Kind):
    """A date, a time, or both, in ISO 8601: a ``Date``, a ``Time`` or a ``DateTime``."""

    def read(self, word: str, field: Field) -> object:
        """The word as written, once it's checked to be its field's ISO 8601."""
        reads, said = _MOMENTS.get(field_kind(field) or FieldKind.DATETIME, _MOMENTS[FieldKind.DATETIME])
        try:
            reads(word)
        except ValueError:
            msg = f'{word!r} is not {said}'
            raise ValueError(msg) from None
        return word


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

    # It reads by the base's read: the word as typed.

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
