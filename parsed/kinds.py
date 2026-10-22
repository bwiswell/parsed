"""Kinds: how a field's words are read, declared as plain data.

A kind says how a field's words read on a line: what they read to, what Tab may offer, and how a value is written
back as words. Each is plain data, so a module that declares commands imports nothing of an app's: a :class:`Name`'s
lookups are the app's own, given at run time by its category.

**Reading a word** (:meth:`Kind.read`) gives the field's wire value, what seared's ``load`` takes and a tool call
would send: seconds for a span of time, an ``Enum``'s value for one of its words. seared then checks it as it checks
any value, bounds and all. A word a kind can't read raises a ``ValueError`` saying what it should be.

**Literal words** come first: any kind may take ``words``, each a word that reads to a value of its own, case aside
(``Number(suffix='%', words={'off': None})`` for a share that may be off). A quoted word is never one. Then the
kind's own form (:meth:`Kind.form`), which a kind of an app's own overrides.

**Writing a value back** (:meth:`Kind.write`) is the other way: a wire value as the words a line says it in, a
literal word first (``None`` back to ``off``), else the kind's own spelling (:meth:`Kind.spell`), which reads back to
the same value.

**A named kind** (:class:`Named`) is read through the app: a :class:`Name` by the resolver the app gives for its
category, and :class:`Pairs`, a keyed field's ``key value`` pairs, by one that reads each key and gives its values
their own (:mod:`parsed.names`).

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
and the arrays and frames
a ``keyed`` field                                  none            :class:`Pairs`, given in ``KINDS``
=================================================  ==============  ================================================
"""

from __future__ import annotations

import dataclasses
import re
import uuid

# At runtime: tooling evaluates a kind's annotations (`typing.get_type_hints`), `words`' among them.
from collections.abc import Mapping  # noqa: TC003
from dataclasses import dataclass
from datetime import date, datetime, time
from types import MappingProxyType
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
_LITERAL = re.compile(r'[a-z0-9][a-z0-9_-]*')

#: Below this, a whole float is spelled as an integer's digits; above it, Python's ``repr`` keeps it exact.
_WHOLE_UP_TO = 1e15

#: What :meth:`Kind.literal` gives for a word that isn't one of the kind's literal words.
NOT_LITERAL = object()


@dataclass(frozen=True, slots=True)
class Kind:
    """The base of every kind: how a field's words are read.

    Attributes:
        words: Literal words it reads before its own form, each to a wire value of its own: ``{'off': None}``. Each
            is one lowercase word, matched case aside.

    Raises:
        DeclarationError: A literal word isn't one word.
    """

    words: Mapping[str, object] = dataclasses.field(default_factory=dict, kw_only=True, hash=False)

    def __post_init__(self) -> None:
        """Refuse a literal word that isn't one word, and keep them where they can't change."""
        for word in self.words:
            if not isinstance(word, str) or not _LITERAL.fullmatch(word):
                msg = f'{type(self).__name__}(words=…): {word!r} is no literal word: one lowercase word, such as off'
                raise DeclarationError(msg)
        object.__setattr__(self, 'words', MappingProxyType(dict(self.words)))

    def read(self, word: str, field: Field, *, quoted: bool = False) -> object:
        """The field's wire value for ``word``, for seared to load: a literal word's value, else :meth:`form`'s.

        Args:
            word: The word, its quotes left off.
            field: The field it's for.
            quoted: Whether it was quoted, so it's never a literal word.

        Raises:
            ValueError: ``word`` isn't one this kind reads; its message says what one should be.
        """
        if self.words and not quoted:  # most kinds have none, so most words go straight to the form
            found = self.words.get(word.lower(), NOT_LITERAL)
            if found is not NOT_LITERAL:
                return found
        return self.form(word, field)

    def literal(self, word: str) -> object:
        """The value ``word`` reads to as one of the kind's literal words, case aside, or :data:`NOT_LITERAL`."""
        return self.words.get(word.lower(), NOT_LITERAL)

    def form(self, word: str, field: Field) -> object:  # noqa: ARG002 -- every kind reads alike
        """The kind's own form of a word, for one that isn't a literal: here, the word as written.

        Raises:
            ValueError: ``word`` isn't one this kind reads; its message says what one should be.
        """
        return word

    def offers(self, field: Field) -> tuple[str, ...]:  # noqa: ARG002 -- every kind offers alike
        """The words completion offers for the field besides the literal words: here, none, since any may do."""
        return ()

    def write(self, value: object, field: Field) -> list[str]:
        """A wire value as the words a line says it in: the literal word that reads to it, else :meth:`spell`'s."""
        for word, said in self.words.items():
            if said == value and type(said) is type(value):  # `True == 1`, but `on` isn't `1`
                return [word]
        return self.spell(value, field)

    def spell(self, value: object, field: Field) -> list[str]:  # noqa: ARG002 -- every kind spells alike
        """The kind's own words for a wire value, which :meth:`form` reads back to it: here, the value as a word."""
        return [str(value)]


@dataclass(frozen=True, slots=True)
class Word(Kind):
    """A word, as written: a ``Str``, a ``Path`` or a ``UUID``, each checked by its field."""

    def form(self, word: str, field: Field) -> object:
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
    """A number: an ``Int``, a ``Float`` or a ``Decimal``, its bounds checked by its field.

    Attributes:
        suffix: What may follow the number, and is left off: ``'%'`` reads ``30%`` as ``30``.
    """

    suffix: str = ''

    def form(self, word: str, field: Field) -> object:
        """An ``int`` for an ``Int``, a ``float`` for a ``Float``, and the digits for a ``Decimal``, kept exact.

        Its thousands may be grouped by commas (``1,000``); any other comma isn't a number's. Its suffix, if it has
        one, may follow it.
        """
        bare = word.removesuffix(self.suffix) if self.suffix else word
        text = bare.replace(',', '') if _GROUPED.fullmatch(bare) else bare
        if field_kind(field) is FieldKind.INT:
            if not _WHOLE.fullmatch(text):
                msg = f'{word!r} is not a whole number'
                raise ValueError(msg)
            return int(text)
        if not _DECIMAL.fullmatch(text):
            msg = f'{word!r} is not a number'
            raise ValueError(msg)
        return text if field_kind(field) is FieldKind.DECIMAL else float(text)

    def spell(self, value: object, field: Field) -> list[str]:  # noqa: ARG002 -- every kind spells alike
        """The number as digits: a whole float without its ``.0``, any other as Python writes it, exactly."""
        if isinstance(value, float) and value.is_integer() and abs(value) < _WHOLE_UP_TO:
            return [str(int(value))]
        return [repr(value) if isinstance(value, float) else str(value)]


@dataclass(frozen=True, slots=True)
class Switch(Kind):
    """``true`` or ``false``: a ``Bool``. As a flag, given or not."""

    def form(self, word: str, field: Field) -> object:  # noqa: ARG002 -- every kind reads alike
        """``True`` for ``true`` and ``False`` for ``false``, case aside."""
        found = {'true': True, 'false': False}.get(word.lower())
        if found is None:
            msg = f'{word!r} is not true or false'
            raise ValueError(msg)
        return found

    def offers(self, field: Field) -> tuple[str, ...]:  # noqa: ARG002 -- every kind offers alike
        """Both."""
        return ('true', 'false')

    def spell(self, value: object, field: Field) -> list[str]:  # noqa: ARG002 -- every kind spells alike
        """``true`` or ``false``."""
        return ['true' if value else 'false']


@dataclass(frozen=True, slots=True)
class Choice(Kind):
    """One of an ``Enum`` field's values."""

    def form(self, word: str, field: Field) -> object:
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

    def offers(self, field: Field) -> tuple[str, ...]:
        """The ``Enum``'s values, as they're written."""
        return tuple(str(member.value) for member in getattr(field, 'enum', ()))


@dataclass(frozen=True, slots=True)
class Duration(Kind):
    """A span of time, ``90s``, ``10m`` or ``1h30m``: a ``TimeDelta``."""

    def form(self, word: str, field: Field) -> object:  # noqa: ARG002 -- every kind reads alike
        """The seconds the span says, as seared writes a ``TimeDelta``: hours, minutes and seconds, each optional."""
        found = _SPAN.fullmatch(word.lower())
        if found is None or not any(found.groups()):
            msg = f'{word!r} is not a span of time: say 90s, 10m, 2h or 1h30m'
            raise ValueError(msg)
        hours, minutes, seconds = (float(part or 0) for part in found.groups())
        return hours * 3600 + minutes * 60 + seconds

    def offers(self, field: Field) -> tuple[str, ...]:  # noqa: ARG002 -- every kind offers alike
        """A few spans to start from."""
        return ('10m', '30m', '1h')

    def spell(self, value: object, field: Field) -> list[str]:  # noqa: ARG002 -- every kind spells alike
        """Seconds as a span: hours, minutes and seconds, those that aren't nought (``5400.0`` as ``1h30m``)."""
        total = float(value)  # ty: ignore[invalid-argument-type] -- a TimeDelta's wire value is a number
        hours, rest = divmod(total, 3600)
        minutes, seconds = divmod(rest, 60)
        seconds = round(seconds, 6)
        parts = [f'{int(hours)}h' if hours else '', f'{int(minutes)}m' if minutes else '']
        parts.append(f'{seconds:g}s' if seconds or not (hours or minutes) else '')
        return [''.join(parts)]


#: What a moment's word is read by, and what one looks like, by its field's type.
_MOMENTS = {
    FieldKind.DATE: (date.fromisoformat, 'a date: say 2026-10-21'),
    FieldKind.TIME: (time.fromisoformat, 'a time: say 14:30'),
    FieldKind.DATETIME: (datetime.fromisoformat, 'a date and time: say 2026-10-21T14:30'),
}


@dataclass(frozen=True, slots=True)
class Moment(Kind):
    """A date, a time, or both, in ISO 8601: a ``Date``, a ``Time`` or a ``DateTime``."""

    def form(self, word: str, field: Field) -> object:
        """The word as written, once it's checked to be its field's ISO 8601."""
        reads, said = _MOMENTS.get(field_kind(field) or FieldKind.DATETIME, _MOMENTS[FieldKind.DATETIME])
        try:
            reads(word)
        except ValueError:
            msg = f'{word!r} is not {said}'
            raise ValueError(msg) from None
        return word


@dataclass(frozen=True, slots=True)
class Named(Kind):
    """A kind read through the app's own resolver for its category: the base of :class:`Name` and :class:`Pairs`.

    Attributes:
        category: What it names (``fleet``, ``station``, ``good``): the key the app's resolvers are given by.
        scope: Another field of the command, whose value narrows the lookup: a station within the fleet's reach,
            with ``scope='fleet'``. ``None`` looks across every name of the category.

    Raises:
        DeclarationError: The category or the scope isn't a name.
    """

    category: str
    scope: str | None = None

    def __post_init__(self) -> None:
        """Refuse a category or a scope that isn't a name."""
        Kind.__post_init__(self)
        said = type(self).__name__
        if not isinstance(self.category, str) or not self.category.isidentifier():
            msg = f'{said}({self.category!r}): a category is a name, such as fleet or station'
            raise DeclarationError(msg)
        if self.scope is not None and (not isinstance(self.scope, str) or not self.scope.isidentifier()):
            msg = f'{said}({self.category!r}, scope={self.scope!r}): a scope is the name of another field'
            raise DeclarationError(msg)


@dataclass(frozen=True, slots=True)
class Name(Named):
    """One of an app's names, read to its key by the resolver the app gives for its category; else as typed."""


@dataclass(frozen=True, slots=True)
class Pairs(Named):
    """A keyed field's ``key value`` pairs, said as the rest of the line: a routine's variables.

    The resolver the app gives for its category reads each key, and gives each key's values a resolver of their own
    (:class:`parsed.names.PairsResolver`). With none, keys and values read as typed. A literal word or a form of its
    own isn't a pair's: :meth:`form` reads a value as typed.
    """

    def spell(self, value: object, field: Field) -> list[str]:  # noqa: ARG002 -- every kind spells alike
        """Each pair's key and its value, in turn."""
        pairs = value.items() if isinstance(value, dict) else ()
        return [str(word) for pair in pairs for word in pair]


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
