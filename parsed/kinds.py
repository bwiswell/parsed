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

**An example** (:meth:`Kind.example`), for ``parsed check``: a value the field may hold, which a kind with a form of
its own gives, since one made from the field's type alone may not read. ``None`` by default.

**Describing its words** (:meth:`Kind.describe`), for help and pages: the kind's own description (:meth:`Kind.what`,
``a span of time, such as 90s or 1h30m``), then its literal words (``, or off``).

**Labelling a value** (:meth:`Kind.usage_label`), for a usage: what a flag's value is written as between ``<`` and
``>``, ``span`` in ``--for <span>``; ``None`` leaves it to the flag's name. A usage adds the literal words after it
(``<n|off>``).

**A line passed on** (:class:`Line`) is the rest of a line as typed, from its first word: its flags, parsed's own,
``--`` and ``then`` among it, quotes kept, so a command that passes a line to another reads it there as it was said.

**A named kind** (:class:`Named`) is read through the app: a :class:`Name` by the resolver the app gives for its
category, and :class:`Pairs`, a keyed field's ``key value`` pairs, by one that reads each key and gives its values
their own (:mod:`parsed.names`). Its ``label`` is what a person calls one, where its category isn't: refusals, usages
and help say its :attr:`~Named.term`, the label or else the category.

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
    from collections.abc import Callable

    from seared import Field

#: A number with its thousands grouped by commas: ``1,000``, ``-12,500.5``.
_GROUPED = re.compile(r'[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?')
_WHOLE = re.compile(r'[+-]?\d+')
_DECIMAL = re.compile(r'[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?')
_SPAN = re.compile(r'(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m)?(?:(\d+(?:\.\d+)?)s)?')
_LITERAL = re.compile(r'[a-z0-9][a-z0-9_-]*')
_LABEL = re.compile(r'[^\s<>|]+(?: [^\s<>|]+)*')
#: A word whose ``u`` is said as *you*: a consonant, then a vowel, after it (``unit``, ``user``).
_YOU = re.compile(r'u[^aeiou][aeiou]')

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

    def example(self, field: Field) -> object:  # noqa: ARG002 -- every kind gives alike
        """A value the field may hold, as an instance holds it, for ``parsed check`` to make its examples with.

        ``None``, by default, leaves it to the field's type and constraints; a kind with a form of its own gives one
        its form reads (``'fleet=f1'``), since a value made from the type alone may not be.
        """
        return None

    def describe(self, field: Field) -> str:
        """What the field's words are, for help and pages: :meth:`what`'s, then the literal words: ``…, or off``."""
        what = self.what(field)
        return f'{what}, or {_either(list(self.words))}' if self.words else what

    def what(self, field: Field) -> str:  # noqa: ARG002 -- every kind describes alike
        """The kind's own form, described for a person: here, ``a word``."""
        return 'a word'

    def usage_label(self, field: Field) -> str | None:  # noqa: ARG002 -- every kind labels alike
        """What a usage writes a flag's value as, between ``<`` and ``>``: here, ``None``, the flag's name."""
        return None


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

    def what(self, field: Field) -> str:
        """``a word``, ``a path`` or ``a UUID``, by its field."""
        return {FieldKind.PATH: 'a path', FieldKind.UUID: 'a UUID'}.get(field_kind(field), 'a word')

    def usage_label(self, field: Field) -> str | None:
        """``path`` for a ``Path`` and ``uuid`` for a ``UUID``; ``None`` for any other, the flag's name."""
        return {FieldKind.PATH: 'path', FieldKind.UUID: 'uuid'}.get(field_kind(field))


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

    def what(self, field: Field) -> str:
        """``a whole number`` for an ``Int``, else ``a number``; and its suffix, which may follow it."""
        what = 'a whole number' if field_kind(field) is FieldKind.INT else 'a number'
        return f'{what}, {self.suffix} after it or not' if self.suffix else what

    def usage_label(self, field: Field) -> str | None:  # noqa: ARG002 -- every kind labels alike
        """``n``."""
        return 'n'

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

    def what(self, field: Field) -> str:  # noqa: ARG002 -- every kind describes alike
        """``true or false``."""
        return 'true or false'

    def usage_label(self, field: Field) -> str | None:  # noqa: ARG002 -- every kind labels alike
        """``true|false``, for a value; a flag that's a switch takes none."""
        return 'true|false'


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

    def what(self, field: Field) -> str:
        """``one of iron, coal or ice``: the ``Enum``'s values."""
        return f'one of {_either(list(self.offers(field)))}'

    def usage_label(self, field: Field) -> str | None:
        """The ``Enum``'s values: ``iron|coal|ice``."""
        return '|'.join(self.offers(field))


@dataclass(frozen=True, slots=True)
class Duration(Kind):
    """A span of time, ``90s``, ``10m`` or ``1h30m``: a ``TimeDelta``."""

    def form(self, word: str, field: Field) -> object:  # noqa: ARG002 -- every kind reads alike
        """The seconds the span says, as seared writes a ``TimeDelta``: hours, minutes and seconds, each optional."""
        return span(word)

    def offers(self, field: Field) -> tuple[str, ...]:  # noqa: ARG002 -- every kind offers alike
        """A few spans to start from."""
        return ('10m', '30m', '1h')

    def spell(self, value: object, field: Field) -> list[str]:  # noqa: ARG002 -- every kind spells alike
        """Seconds as a span: hours, minutes and seconds, those that aren't nought (``5400.0`` as ``1h30m``)."""
        return [spell_span(float(value))]  # ty: ignore[invalid-argument-type] -- a TimeDelta's wire value is a number

    def what(self, field: Field) -> str:  # noqa: ARG002 -- every kind describes alike
        """``a span of time, such as 90s, 10m or 1h30m``."""
        return 'a span of time, such as 90s, 10m or 1h30m'

    def usage_label(self, field: Field) -> str | None:  # noqa: ARG002 -- every kind labels alike
        """``span``."""
        return 'span'


#: What a moment's word is read by, what it is, and what one looks like, by its field's type.
_MOMENTS = {
    FieldKind.DATE: (date.fromisoformat, 'a date', '2026-10-21'),
    FieldKind.TIME: (time.fromisoformat, 'a time', '14:30'),
    FieldKind.DATETIME: (datetime.fromisoformat, 'a date and time', '2026-10-21T14:30'),
}


@dataclass(frozen=True, slots=True)
class Moment(Kind):
    """A date, a time, or both, in ISO 8601: a ``Date``, a ``Time`` or a ``DateTime``."""

    def form(self, word: str, field: Field) -> object:
        """The word as written, once it's checked to be its field's ISO 8601."""
        reads, what, like = _moment(field)
        try:
            reads(word)
        except ValueError:
            msg = f'{word!r} is not {what}: say {like}'
            raise ValueError(msg) from None
        return word

    def what(self, field: Field) -> str:
        """``a date, such as 2026-10-21``, a time or both, by its field."""
        _, what, like = _moment(field)
        return f'{what}, such as {like}'

    def usage_label(self, field: Field) -> str | None:
        """``date``, ``time`` or ``datetime``, by its field."""
        return {FieldKind.DATE: 'date', FieldKind.TIME: 'time'}.get(field_kind(field) or FieldKind.DATETIME, 'datetime')


@dataclass(frozen=True, slots=True)
class Named(Kind):
    """A kind read through the app's own resolver for its category: the base of :class:`Name` and :class:`Pairs`.

    Attributes:
        category: What it names (``fleet``, ``station``, ``good``): the key the app's resolvers are given by.
        scope: Another field of the command, whose value narrows the lookup: a station within the fleet's reach,
            with ``scope='fleet'``. ``None`` looks across every name of the category.
        follows: Whether the scope follows its chain's place, on a step whose scope is a field its chain shares: once
            an earlier step has moved the chain on (its ``MOVES``), the scope is where it moved to, so a station is
            looked for where the fleet will be. Keyword-only.
        label: What a person calls one, where its category isn't (``Name('good_in_deposit', label='ore')``): words,
            for refusals, usages and help to say. ``None``, by default, says its category. Keyword-only.

    Raises:
        DeclarationError: The category or the scope isn't a name, ``follows`` has no scope to follow, or the label
            isn't words.
    """

    category: str
    scope: str | None = None
    follows: bool = dataclasses.field(default=False, kw_only=True)
    label: str | None = dataclasses.field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        """Refuse a category or a scope that isn't a name, and a ``follows`` with no scope."""
        Kind.__post_init__(self)
        said = type(self).__name__
        if not isinstance(self.category, str) or not self.category.isidentifier():
            msg = f'{said}({self.category!r}): a category is a name, such as fleet or station'
            raise DeclarationError(msg)
        if self.scope is not None and (not isinstance(self.scope, str) or not self.scope.isidentifier()):
            msg = f'{said}({self.category!r}, scope={self.scope!r}): a scope is the name of another field'
            raise DeclarationError(msg)
        if not isinstance(self.follows, bool):
            msg = f'{said}({self.category!r}, follows={self.follows!r}): True or False'
            raise DeclarationError(msg)
        if self.follows and self.scope is None:
            msg = (
                f"{said}({self.category!r}, follows=True): it follows its scope's place along a chain, so it needs "
                f"a scope, the chain's field: scope='fleet'"
            )
            raise DeclarationError(msg)
        if self.label is not None and (not isinstance(self.label, str) or not _LABEL.fullmatch(self.label)):
            msg = f'{said}({self.category!r}, label={self.label!r}): a label is words a person says, such as ore'
            raise DeclarationError(msg)

    @property
    def term(self) -> str:
        """What refusals, usages and help call one: its label, or else its category."""
        return self.label or self.category

    def usage_label(self, field: Field) -> str | None:  # noqa: ARG002 -- every kind labels alike
        """Its :attr:`term`: ``fleet``, ``ore``."""
        return self.term


@dataclass(frozen=True, slots=True)
class Name(Named):
    """One of an app's names, read to its key by the resolver the app gives for its category; else as typed."""

    def what(self, field: Field) -> str:  # noqa: ARG002 -- every kind describes alike
        """``a station``, its :attr:`~Named.term`, and ``within its fleet`` where it has a scope."""
        return f'{_a(self.term)} {self.term}' + (f', within its {self.scope}' if self.scope else '')


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

    def what(self, field: Field) -> str:  # noqa: ARG002 -- every kind describes alike
        """``variable and value pairs``, by its :attr:`~Named.term`."""
        return f'{self.term} and value pairs'


@dataclass(frozen=True, slots=True)
class Line(Kind):
    """The rest of a line as typed, from its first word, its flags among it: a line passed on to another.

    A ``Str`` field, said as its phrase's rest (``{line**}``), and on no chain's step. Its flags, parsed's own among
    them, ``--`` and ``then`` are the line's, its quotes kept, so ``see fleet f1 buy ship hauler --yes`` gives
    ``'fleet f1 buy ship hauler --yes'``. A flag before its first word is the command's own (``see --pretty …``).
    """

    def what(self, field: Field) -> str:  # noqa: ARG002 -- every kind describes alike
        """``a line, as typed: its flags are its own``."""
        return 'a line, as typed: its flags are its own'

    def example(self, field: Field) -> object:  # noqa: ARG002 -- every kind gives alike
        """A line with a flag of its own, for ``parsed check`` to write back and read: ``'word --flag'``."""
        return 'word --flag'


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


def _moment(field: Field) -> tuple[Callable[[str], object], str, str]:
    """A moment field's reader, what it is, and what one looks like."""
    return _MOMENTS.get(field_kind(field) or FieldKind.DATETIME, _MOMENTS[FieldKind.DATETIME])


def _a(word: str) -> str:
    """The article before ``word``: ``an`` before a vowel's sound (``an ore``, ``an upgrade``), else ``a``."""
    said = word.lower()
    return 'an' if said[:1] in 'aeio' or (said[:1] == 'u' and not _YOU.match(said)) else 'a'


def _either(words: list[str]) -> str:
    """Words joined for a sentence: ``a``, ``a or b``, ``a, b or c``."""
    return words[0] if len(words) == 1 else f'{", ".join(words[:-1])} or {words[-1]}'


def span(word: str) -> float:
    """The seconds a span of time says (``90s``, ``10m``, ``1h30m``): hours, minutes and seconds, each optional.

    Raises:
        ValueError: The word isn't a span.
    """
    found = _SPAN.fullmatch(word.lower())
    if found is None or not any(found.groups()):
        msg = f'{word!r} is not a span of time: say 90s, 10m, 2h or 1h30m'
        raise ValueError(msg)
    hours, minutes, seconds = (float(part or 0) for part in found.groups())
    return hours * 3600 + minutes * 60 + seconds


def spell_span(seconds: float) -> str:
    """Seconds as a span of time, as :func:`span` reads one: those of hours, minutes and seconds that aren't nought."""
    hours, rest = divmod(seconds, 3600)
    minutes, left = divmod(rest, 60)
    left = round(left, 6)
    parts = [f'{int(hours)}h' if hours else '', f'{int(minutes)}m' if minutes else '']
    parts.append(f'{left:g}s' if left or not (hours or minutes) else '')
    return ''.join(parts)


def default_kind(field: object) -> Kind | None:
    """The kind a field takes when ``KINDS`` gives it none, or ``None`` when its type has no word form."""
    if getattr(field, 'keyed', False):
        return None
    found = field_kind(field)
    return _DEFAULTS.get(found) if found is not None else None
