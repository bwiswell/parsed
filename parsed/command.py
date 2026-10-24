"""``Command``: the base of every command, and what a command declares.

A command is a seared class: ``@parsed.parsed`` (seared's decorator, renamed) on a subclass of :class:`Command`. Its
fields are what it takes, and its class constants say the rest, as a zeared message's do:

=================  ===========================  ==============================================================
Constant           Default                      What it says
=================  ===========================  ==============================================================
``PHRASE``         ``None``                     the words that say it (``'fleet {fleet} mine'``); a class
                                                without one is a base, not a command
``EXTRA_PHRASES``  ``()``                       other phrases that say it too
``EFFECT``         ``None``                     what running it does (:class:`~parsed.effect.Effect`)
``ASKS``           ``False``                    whether it may ask before it acts
``INTERACTIVE``    ``False``                    whether it's only for a person at a terminal
``POLYMORPHIC``    ``None``                     whether a phrase says a slot by an alias (checked when declared)
``INSTEAD``        ``None``                     the command an agent says in place of an interactive one
``REPLY``          ``None``                     the seared class its handler returns
``KINDS``          empty                        how each field's words are read, by field name
``ALIASES``        empty                        other names a phrase's slot may fill a field by
                                                (``{'detachment': 'fleet'}``)
``SHORTS``         empty                        a flag's short form, one letter, by field name
                                                (``{'config': 'c'}`` says ``--config`` as ``-c``)
``EXAMPLES``       ``()``                       lines that say it, for help and for ``parsed check`` to read;
                                                ``<name>`` stands for any value
``STEPS``          ``False``                    on a chain's base: its commands are steps, which ``then`` joins
                                                on a line; a command beneath it that isn't one says ``False``
``MOVES``          ``False``                    on a step: the field that says where it takes its chain
                                                (``'to'``), or ``True`` for somewhere the line doesn't say
=================  ===========================  ==============================================================

Every constant but ``PHRASE`` is optional, and none is inferred. Each is inherited like any class attribute, so a base
can declare one for every command beneath it. ``KINDS``, ``ALIASES`` and ``SHORTS`` are merged along the MRO instead: a
base's entries and its subclasses' all count, a subclass's winning where they name the same key. No flag has a short
form unless ``SHORTS`` gives it one, and ``-h`` is ``--help``'s.

:func:`declaration` reads a class's constants once, checks each, and returns its :class:`Declaration`, with each
phrase bound to the fields it fills (:mod:`parsed._phrase`): a field a slot of ``PHRASE`` fills is a positional, and
every other field a flag. Every field has a kind (:mod:`parsed.kinds`): its ``KINDS`` entry, or its seared type's
default.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar

from seared import Field, Seared, field_kind
from seared.doc import is_seared_class

from ._phrase import Binding, Bound, Place, bind
from ._walk._terms import HELP_SHORT
from .effect import Effect, EffectName, effect_of
from .errors import DeclarationError
from .kinds import Kind, Named, Pairs, default_kind

_CACHE = '__parsed_declaration__'


class Command(Seared):
    """The base of every command.

    Subclass it, decorate the subclass with ``@parsed.parsed``, and give it a ``PHRASE``; the module's docstring lists
    every constant. A subclass without a ``PHRASE`` is a base: it can carry fields, ``KINDS`` and any other constant
    for the commands beneath it, and must be decorated too if it declares fields, or seared drops them.
    """

    PHRASE: ClassVar[str | None] = None
    EXTRA_PHRASES: ClassVar[tuple[str, ...]] = ()
    EFFECT: ClassVar[Effect | EffectName | None] = None
    ASKS: ClassVar[bool] = False
    INTERACTIVE: ClassVar[bool] = False
    POLYMORPHIC: ClassVar[bool | None] = None
    INSTEAD: ClassVar[type[Command] | None] = None
    REPLY: ClassVar[type[Seared] | None] = None
    KINDS: ClassVar[Mapping[str, Kind]] = MappingProxyType({})
    ALIASES: ClassVar[Mapping[str, str]] = MappingProxyType({})
    SHORTS: ClassVar[Mapping[str, str]] = MappingProxyType({})
    EXAMPLES: ClassVar[tuple[str, ...]] = ()
    STEPS: ClassVar[bool] = False
    MOVES: ClassVar[str | bool] = False


@dataclass(frozen=True, slots=True)
class Declaration:
    """What a command class declares, read and checked once by :func:`declaration`.

    Attributes:
        cls: The class.
        phrase: Its ``PHRASE``; ``None`` for a base, which isn't a command.
        extra_phrases: Its ``EXTRA_PHRASES``.
        effect: Its ``EFFECT``, an effect name normalised to its member; ``None`` when it declares none.
        asks: Whether it may ask before it acts.
        interactive: Whether it's only for a person at a terminal.
        polymorphic: ``POLYMORPHIC`` as declared: ``True``, ``False``, or ``None`` when it declares neither.
        instead: The command an agent says in its place, or ``None``.
        reply: The seared class its handler returns, or ``None``.
        examples: Its ``EXAMPLES``, lines that say it.
        chain: The chain it's a step of: the nearest base that declares ``STEPS = True``; ``None`` when it isn't a
            step, and for a base.
        moves: Where a step takes its chain: the field that says so, ``True`` for somewhere the line doesn't say,
            or ``False`` when it stays where it is.
        kinds: ``KINDS``, merged along the MRO, a subclass's entries over its bases'.
        aliases: ``ALIASES``, merged likewise: a slot's name, to the field it fills.
        shorts: ``SHORTS``, merged likewise: a flag's field, to the letter that says it short (``'c'`` for ``-c``).
        field_kinds: Each field's kind, by attribute name: its ``KINDS`` entry, or its type's default; empty for a
            base.
        phrases: ``PHRASE`` and then each of ``EXTRA_PHRASES``, bound to the fields they fill; empty for a base.
        flags: The fields no slot of ``PHRASE`` names, in their declared order; empty for a base.
    """

    cls: type[Command]
    phrase: str | None
    extra_phrases: tuple[str, ...]
    effect: Effect | None
    asks: bool
    interactive: bool
    polymorphic: bool | None
    instead: type[Command] | None
    reply: type[Seared] | None
    examples: tuple[str, ...]
    chain: type[Command] | None
    moves: str | bool
    kinds: Mapping[str, Kind]
    aliases: Mapping[str, str]
    shorts: Mapping[str, str]
    field_kinds: Mapping[str, Kind]
    phrases: tuple[Bound, ...]
    flags: tuple[str, ...]

    @property
    def is_command(self) -> bool:
        """Whether the class is a command, rather than a base: whether it has a ``PHRASE``."""
        return self.phrase is not None

    @property
    def can_wait(self) -> bool:
        """Whether a line may wait on it (``--until``): a read, with a ``REPLY`` whose values a condition reads."""
        return self.is_command and self.effect is Effect.READ and self.reply is not None

    def kind_of(self, place: Place) -> Kind:
        """The kind a slot's words are read by: a slot by an alias's own ``KINDS`` entry, else its field's kind."""
        if place.renamed and place.slot in self.kinds:
            return self.kinds[place.slot]
        return self.field_kinds[place.field]


def declaration(cls: type) -> Declaration:
    """What ``cls`` declares: read and checked on the first call, and the same :class:`Declaration` after.

    The result is kept on the class itself, so there's no registry beside it.

    Raises:
        DeclarationError: ``cls`` isn't a command class, one of its bases declares fields but isn't decorated, a
            constant is of the wrong kind, a phrase doesn't read or doesn't bind, or a field has no kind. The
            message names the class and the constant, and how to put it right.
    """
    found = cls.__dict__.get(_CACHE) if isinstance(cls, type) else None
    if found is None:
        found = _read(cls)
        setattr(cls, _CACHE, found)
    return found


def _read(cls: type) -> Declaration:
    if not (isinstance(cls, type) and issubclass(cls, Command)):
        msg = f'{cls!r} is not a command: subclass parsed.Command, and decorate it with @parsed.parsed'
        raise DeclarationError(msg)
    name = cls.__qualname__
    phrase = _phrase(cls, name)
    _check_decorated(cls, name, is_command=phrase is not None)
    extra = _extra_phrases(cls, name, phrase)
    interactive = _flag(cls, name, 'INTERACTIVE')
    polymorphic = _polymorphic(cls, name)
    kinds = _kinds(cls)
    aliases = _aliases(cls)
    binding = _bind(cls, name, phrase=phrase, extra=extra, aliases=aliases, polymorphic=polymorphic)
    chain = _chain(cls, name, phrase)
    field_kinds = _field_kinds(cls, name, kinds, binding, chain) if phrase is not None else MappingProxyType({})
    return Declaration(
        cls=cls,
        phrase=phrase,
        extra_phrases=extra,
        effect=_effect(cls),
        asks=_flag(cls, name, 'ASKS'),
        interactive=interactive,
        polymorphic=polymorphic,
        instead=_instead(cls, name, interactive=interactive),
        reply=_reply(cls, name),
        examples=_examples(cls, name, phrase),
        chain=chain,
        moves=_moves(cls, name, chain) if phrase is not None else False,
        kinds=kinds,
        aliases=aliases,
        shorts=_shorts(cls, name, binding.flags if phrase is not None else None),
        field_kinds=field_kinds,
        phrases=binding.phrases,
        flags=binding.flags,
    )


def _phrase(cls: type[Command], name: str) -> str | None:
    phrase = cls.PHRASE
    if phrase is None:
        return None
    if not isinstance(phrase, str) or not phrase.strip():
        msg = f"{name}.PHRASE = {phrase!r}: a phrase is a string of words, such as 'fleet {{fleet}} mine'"
        raise DeclarationError(msg)
    return phrase


def _check_decorated(cls: type[Command], name: str, *, is_command: bool) -> None:
    """Refuse a command that isn't decorated, and any field in its MRO that seared would drop.

    seared takes only a field it can see: one with an annotation, on a decorated class. It drops the rest without a
    word, so a command would quietly take less than it declares. After decorating, seared keeps an annotated field
    only in ``__seared_fields__``; a ``Field`` still in a decorated class's own attributes is one it left out.
    """
    if is_command and not is_seared_class(cls):
        msg = f'{name} has a PHRASE but is not decorated: decorate it with @parsed.parsed'
        raise DeclarationError(msg)
    for base in cls.__mro__:
        if base in (Command, Seared) or not issubclass(base, Seared):
            continue
        fields = [(attr, value) for attr, value in vars(base).items() if isinstance(value, Field)]
        if not fields:
            continue
        owner = base.__qualname__
        if not is_seared_class(base):
            msg = (
                f'{owner} declares fields but is not decorated, so seared would drop them from {name}: decorate '
                f'{owner} with @parsed.parsed'
            )
            raise DeclarationError(msg)
        attr, field = fields[0]
        where = '' if base is cls else f' of {name}'
        msg = (
            f'{owner}.{attr} has no annotation, so seared leaves it out{where}: add an annotation, such as '
            f'{attr}: {_type_hint(field)} = …'
        )
        raise DeclarationError(msg)


#: What an annotation names for each plain field, in a refusal's example; any other reads ``<its type>``.
_HINTS = {
    'str': 'str',
    'int': 'int',
    'float': 'float',
    'bool': 'bool',
    'timedelta': 'timedelta',
    'date': 'date',
    'datetime': 'datetime',
    'time': 'time',
    'uuid': 'UUID',
    'path': 'Path',
    'decimal': 'Decimal',
}


def _type_hint(field: Field) -> str:
    kind = field_kind(field)
    hint = _HINTS.get(kind.value, '<its type>') if kind is not None else '<its type>'
    if field.many:
        hint = f'list[{hint}]'
    if not field.required and field.default is None and field.default_factory is None:
        hint = f'{hint} | None'
    return hint


def _extra_phrases(cls: type[Command], name: str, phrase: str | None) -> tuple[str, ...]:
    extra = cls.EXTRA_PHRASES
    if isinstance(extra, str):
        msg = f"{name}.EXTRA_PHRASES = {extra!r}: a tuple of phrases; one alone needs a trailing comma: ('…',)"
        raise DeclarationError(msg)
    if not isinstance(extra, (tuple, list)) or not all(isinstance(p, str) and p.strip() for p in extra):
        msg = f'{name}.EXTRA_PHRASES = {extra!r}: a tuple of phrases, each a string of words'
        raise DeclarationError(msg)
    if extra and phrase is None:
        msg = f'{name} has EXTRA_PHRASES but no PHRASE: a base has no phrases; give it a PHRASE, or move them'
        raise DeclarationError(msg)
    return tuple(extra)


def _examples(cls: type[Command], name: str, phrase: str | None) -> tuple[str, ...]:
    examples = cls.EXAMPLES
    if isinstance(examples, str):
        msg = f"{name}.EXAMPLES = {examples!r}: a tuple of lines; one alone needs a trailing comma: ('…',)"
        raise DeclarationError(msg)
    if not isinstance(examples, (tuple, list)) or not all(isinstance(line, str) and line.strip() for line in examples):
        msg = f'{name}.EXAMPLES = {examples!r}: a tuple of lines, each a string of words'
        raise DeclarationError(msg)
    if examples and phrase is None:
        msg = f'{name} has EXAMPLES but no PHRASE: a base says nothing; give it a PHRASE, or move them'
        raise DeclarationError(msg)
    return tuple(examples)


def _effect(cls: type[Command]) -> Effect | None:
    try:
        return effect_of(cls)
    except (TypeError, ValueError) as exc:
        raise DeclarationError(str(exc)) from exc


def _flag(cls: type[Command], name: str, constant: str) -> bool:
    value = getattr(cls, constant)
    if not isinstance(value, bool):
        msg = f'{name}.{constant} = {value!r}: True or False'
        raise DeclarationError(msg)
    return value


def _chain(cls: type[Command], name: str, phrase: str | None) -> type[Command] | None:
    """The chain a command is a step of: the nearest class that declares ``STEPS = True``, which is a base."""
    if not _flag(cls, name, 'STEPS') or phrase is None:
        return None
    base = next(found for found in cls.__mro__ if 'STEPS' in vars(found))
    if issubclass(base, Command) and base is not cls and base.PHRASE is None:
        return base
    said = name if base is cls else f'{name}, through {base.__qualname__},'
    msg = (
        f"{said} declares STEPS = True on a command: it goes on a chain's base, a subclass of parsed.Command "
        f'without a PHRASE, and the commands beneath it are its steps'
    )
    raise DeclarationError(msg)


def _moves(cls: type[Command], name: str, chain: type[Command] | None) -> str | bool:
    """Where a step takes its chain: a field of its own, of one value; ``True``; or ``False``, staying put."""
    moves = cls.MOVES
    if moves is False:
        return False
    if not isinstance(moves, (str, bool)):
        msg = (
            f"{name}.MOVES = {moves!r}: the field that says where the step takes its chain ('to'), True for "
            f"somewhere the line doesn't say, or False"
        )
        raise DeclarationError(msg)
    if chain is None:
        msg = (
            f"{name}.MOVES says where a step takes its chain, and {name} is no step: declare STEPS on its chain's base"
        )
        raise DeclarationError(msg)
    if moves is True:
        return True
    fields = {spec.attr: spec.field for spec in cls.__seared_fields__}
    if moves not in fields:
        msg = f'{name}.MOVES = {moves!r} names no field of {name}'
        raise DeclarationError(msg)
    if moves in _shared(chain):
        msg = (
            f"{name}.MOVES = {moves!r} names a field of {chain.__qualname__}'s, which every step shares: name the "
            f'field that says where {name} goes'
        )
        raise DeclarationError(msg)
    if fields[moves].many or fields[moves].keyed:
        msg = f'{name}.MOVES = {moves!r}: {moves} holds several values, and a chain is in one place'
        raise DeclarationError(msg)
    return moves


def _shared(base: type[Command]) -> frozenset[str]:
    """A chain's shared fields: those its base declares, which every step has."""
    return frozenset(spec.attr for spec in getattr(base, '__seared_fields__', ()))


def is_chain_base(cls: object) -> bool:
    """Whether ``cls`` is a chain's base: a subclass of :class:`Command` without a ``PHRASE``, declaring the steps.

    It declares ``STEPS = True`` itself, so the commands beneath it are its steps.
    """
    return isinstance(cls, type) and issubclass(cls, Command) and vars(cls).get('STEPS') is True and cls.PHRASE is None


def _polymorphic(cls: type[Command], name: str) -> bool | None:
    value = cls.POLYMORPHIC
    if value is not None and not isinstance(value, bool):
        msg = f'{name}.POLYMORPHIC = {value!r}: True, False, or left out'
        raise DeclarationError(msg)
    return value


def _instead(cls: type[Command], name: str, *, interactive: bool) -> type[Command] | None:
    instead = cls.INSTEAD
    if instead is None:
        return None
    if not interactive:
        msg = f'{name}.INSTEAD: it names what an agent says in place of an interactive command, and {name} is not one'
        raise DeclarationError(msg)
    if instead is cls:
        msg = f'{name}.INSTEAD names {name} itself: name the command an agent says in its place'
        raise DeclarationError(msg)
    other = declaration(instead) if isinstance(instead, type) and issubclass(instead, Command) else None
    if other is None or not other.is_command:
        msg = f'{name}.INSTEAD = {instead!r}: a command class, with a PHRASE'
        raise DeclarationError(msg)
    if other.interactive:
        msg = f'{name}.INSTEAD names {other.cls.__qualname__}, which is interactive too: name a form an agent can use'
        raise DeclarationError(msg)
    return instead


def _reply(cls: type[Command], name: str) -> type[Seared] | None:
    reply = cls.REPLY
    if reply is None:
        return None
    if not is_seared_class(reply):
        shown = reply.__qualname__ if isinstance(reply, type) else repr(reply)
        msg = f'{name}.REPLY = {shown}: a seared class, decorated with @parsed.parsed'
        raise DeclarationError(msg)
    return reply


def _bind(  # noqa: PLR0913 -- the class, and what it declares about its phrases
    cls: type[Command],
    name: str,
    *,
    phrase: str | None,
    extra: tuple[str, ...],
    aliases: Mapping[str, str],
    polymorphic: bool | None,
) -> Binding:
    if phrase is None:
        return Binding(phrases=(), flags=())
    fields = {spec.attr: spec.field for spec in cls.__seared_fields__}
    own = vars(cls).get('KINDS', {})
    return bind(
        fields, name, phrase=phrase, extra_phrases=extra, aliases=aliases, own_kinds=own, polymorphic=polymorphic
    )


def _field_kinds(
    cls: type[Command], name: str, kinds: Mapping[str, Kind], binding: Binding, chain: type[Command] | None
) -> Mapping[str, Kind]:
    """Each field's kind, checked against its field and its phrase, and every scope against the other fields.

    A scope that follows its chain's place is a field the chain shares, on a step.
    """
    found: dict[str, Kind] = {}
    for spec in cls.__seared_fields__:
        kind = kinds.get(spec.attr) or default_kind(spec.field)
        if kind is None and spec.field.keyed:
            msg = f"{name}.{spec.attr} is keyed, so its words are pairs: give it parsed.kinds.Pairs('…') in KINDS"
            raise DeclarationError(msg)
        if kind is None:
            what = type(spec.field).__name__
            msg = (
                f'{name}.{spec.attr} is a {what} field, which has no word form: give it a kind in KINDS, or say it '
                f'another way'
            )
            raise DeclarationError(msg)
        found[spec.attr] = kind
    # What reads by a kind: each field, and each slot by an alias with an entry of its own (for the field it fills).
    read: list[tuple[str, str, Kind]] = [(attr, attr, kind) for attr, kind in found.items()]
    read += [
        (place.slot, place.field, kinds[place.slot])
        for bound in binding.phrases
        for place in bound.places
        if place.renamed and place.slot in kinds
    ]
    _check_forms(cls, name, read, binding)
    scopes: dict[str, set[str]] = {}  # each field, and the fields its names are scoped by
    for said, field, kind in read:
        if not isinstance(kind, Named) or kind.scope is None:
            continue
        if kind.scope not in found or kind.scope == field:
            msg = (
                f'{name}: {said!r} is read as a {kind.category} scoped by {kind.scope!r}, which is no other field '
                f'of {name}'
            )
            raise DeclarationError(msg)
        if kind.follows:
            _check_follows(name, said, kind, chain)
        scopes.setdefault(field, set()).add(kind.scope)
    around = _scopes_around(scopes)
    if around:
        msg = (
            f'{name}: its scopes go round, {" by ".join(around)}: a scope is read before the names it narrows, so '
            f'one of them must be read without the other'
        )
        raise DeclarationError(msg)
    return MappingProxyType(found)


def _check_follows(name: str, said: str, kind: Named, chain: type[Command] | None) -> None:
    """Refuse a scope that follows a chain's place where there's no chain, or that isn't a field the chain shares."""
    if chain is None:
        msg = (
            f"{name}: {said!r} follows its scope along a chain, and {name} is no step: declare STEPS on its chain's "
            f'base, or leave follows off'
        )
        raise DeclarationError(msg)
    if kind.scope not in _shared(chain):
        shared = ', '.join(sorted(_shared(chain))) or 'none'
        msg = (
            f'{name}: {said!r} follows its scope along a chain, so its scope is a field the chain shares, which '
            f"{kind.scope!r} isn't: {chain.__qualname__}'s are {shared}"
        )
        raise DeclarationError(msg)


def _check_forms(cls: type[Command], name: str, read: list[tuple[str, str, Kind]], binding: Binding) -> None:
    """Refuse a kind its field can't take.

    That's pairs for a field that isn't keyed or isn't the rest of the line, a keyed field read any other way, and a
    literal word for ``None`` on a field seared would drop it from.
    """
    fields = {spec.attr: spec.field for spec in cls.__seared_fields__}
    rest = {place.field for place in binding.phrases[0].places if place.rest} if binding.phrases else set()
    for said, field, kind in read:
        keyed = fields[field].keyed
        if isinstance(kind, Pairs) and not keyed:
            msg = f'{name}: {said!r} is read as Pairs, but {field} is not keyed: give it keyed=True'
            raise DeclarationError(msg)
        if keyed and not isinstance(kind, Pairs):
            msg = f"{name}.{field} is keyed, so its words are pairs: give it parsed.kinds.Pairs('…') in KINDS"
            raise DeclarationError(msg)
        if isinstance(kind, Pairs) and field not in rest:
            msg = f'{name}.{field} is read as Pairs, so PHRASE says it as the rest of the line: {{{field}**}}'
            raise DeclarationError(msg)
        nothing = [word for word, value in kind.words.items() if value is None]
        if nothing and not fields[field].nullable:
            msg = (
                f'{name}: {said!r} reads {nothing[0]!r} as None, which seared drops unless {field} is nullable: give '
                f'it nullable=True'
            )
            raise DeclarationError(msg)


def _scopes_around(scopes: Mapping[str, set[str]]) -> list[str]:
    """A round of scopes, as the fields it passes through, the first again last; empty when there's none."""

    def follow(field: str, path: list[str]) -> list[str]:
        if field in path:
            return [*path[path.index(field) :], field]
        for scope in sorted(scopes.get(field, ())):
            found = follow(scope, [*path, field])
            if found:
                return found
        return []

    for field in sorted(scopes):
        found = follow(field, [])
        if found:
            return found
    return []


def _aliases(cls: type[Command]) -> Mapping[str, str]:
    merged: dict[str, str] = {}
    for base in reversed(cls.__mro__):
        own = vars(base).get('ALIASES')
        if own is None:
            continue
        where = f'{base.__qualname__}.ALIASES'
        if not isinstance(own, Mapping):
            msg = f"{where} = {own!r}: a mapping of slot names to field names, such as {{'detachment': 'fleet'}}"
            raise DeclarationError(msg)
        for alias, field in own.items():
            if not isinstance(alias, str) or not alias.isidentifier():
                msg = f'{where}: {alias!r} is not a slot name'
                raise DeclarationError(msg)
            if not isinstance(field, str) or not field.isidentifier():
                msg = f'{where}[{alias!r}] = {field!r}: the name of the field it fills'
                raise DeclarationError(msg)
            merged[alias] = field
    return MappingProxyType(merged)


def _shorts(cls: type[Command], name: str, flags: tuple[str, ...] | None) -> Mapping[str, str]:
    """``SHORTS``, merged along the MRO; on a command (``flags`` given), each checked against its flags."""
    merged: dict[str, str] = {}
    for base in reversed(cls.__mro__):
        own = vars(base).get('SHORTS')
        if own is None:
            continue
        where = f'{base.__qualname__}.SHORTS'
        if not isinstance(own, Mapping):
            msg = f"{where} = {own!r}: a mapping of field names to short flags, such as {{'config': 'c'}}"
            raise DeclarationError(msg)
        for key, short in own.items():
            if not isinstance(key, str) or not key.isidentifier():
                msg = f'{where}: {key!r} is not a field name'
                raise DeclarationError(msg)
            if not (isinstance(short, str) and len(short) == 1 and short.isascii() and short.isalpha()):
                msg = f"{where}[{key!r}] = {short!r}: a short flag is one letter, such as 'c' for -c"
                raise DeclarationError(msg)
            if short == HELP_SHORT:
                msg = f"{where}[{key!r}]: -h is --help's, on every command"
                raise DeclarationError(msg)
            merged[key] = short
    return MappingProxyType(merged if flags is None else _used_shorts(cls, name, merged, flags))


def _used_shorts(cls: type[Command], name: str, shorts: Mapping[str, str], flags: tuple[str, ...]) -> dict[str, str]:
    """A command's shorts for its flags; a base's for none go unused, and one of its own for none is refused."""
    own = vars(cls).get('SHORTS') or {}
    fields = {spec.attr for spec in cls.__seared_fields__}
    used: dict[str, str] = {}
    letters: dict[str, str] = {}
    for key, short in shorts.items():
        if key not in flags and key not in own:
            continue  # a base's, for a field this command says otherwise or hasn't
        if key not in fields:
            msg = f'{name}.SHORTS: {key!r} is no field of {name}'
            raise DeclarationError(msg)
        if key not in flags:
            msg = f'{name}.SHORTS: {key} is said by a slot of its phrase, so it has no flag for -{short}'
            raise DeclarationError(msg)
        if short in letters:
            msg = f'{name}.SHORTS: {letters[short]} and {key} are both -{short}'
            raise DeclarationError(msg)
        used[key] = short
        letters[short] = key
    return used


def _kinds(cls: type[Command]) -> Mapping[str, Kind]:
    merged: dict[str, Kind] = {}
    for base in reversed(cls.__mro__):
        own = vars(base).get('KINDS')
        if own is None:
            continue
        where = f'{base.__qualname__}.KINDS'
        if not isinstance(own, Mapping):
            msg = f'{where} = {own!r}: a mapping of field names to kinds'
            raise DeclarationError(msg)
        for key, kind in own.items():
            if not isinstance(key, str) or not key.isidentifier():
                msg = f'{where}: {key!r} is not a field name'
                raise DeclarationError(msg)
            if not isinstance(kind, Kind):
                msg = f"{where}[{key!r}] = {kind!r}: a kind, such as parsed.Name('{key}')"
                raise DeclarationError(msg)
            merged[key] = kind
    return MappingProxyType(merged)
