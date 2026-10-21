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
``INTERACTIVE``    ``False``                    whether it's only for a person at the client
``POLYMORPHIC``    ``None``                     whether its extra phrases rename a slot (checked when declared)
``INSTEAD``        ``None``                     the command an agent says in place of an interactive one
``REPLY``          ``None``                     the seared class its handler returns
``KINDS``          empty                        how each field's words are read, by field name
=================  ===========================  ==============================================================

Every constant but ``PHRASE`` is optional, and none is inferred. Each is inherited like any class attribute, so a base
can declare one for every command beneath it. ``KINDS`` is merged along the MRO instead: a base's entries and its
subclasses' all count, a subclass's winning where they name the same field.

:func:`declaration` reads a class's constants once, checks each, and returns its :class:`Declaration`, with each
phrase bound to the fields it fills (:mod:`parsed._phrase`): a field a slot of ``PHRASE`` names is a positional, and
every other field a flag. Every field has a kind (:mod:`parsed.kinds`): its ``KINDS`` entry, or its seared type's
default.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar

from seared import Field, Seared
from seared.doc import is_seared_class

from ._phrase import Binding, Bound, Place, bind
from .effect import Effect, EffectName, effect_of
from .errors import DeclarationError
from .kinds import Kind, Name, default_kind

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


@dataclass(frozen=True, slots=True)
class Declaration:
    """What a command class declares, read and checked once by :func:`declaration`.

    Attributes:
        cls: The class.
        phrase: Its ``PHRASE``; ``None`` for a base, which isn't a command.
        extra_phrases: Its ``EXTRA_PHRASES``.
        effect: Its ``EFFECT``, an effect name normalised to its member; ``None`` when it declares none.
        asks: Whether it may ask before it acts.
        interactive: Whether it's only for a person at the client.
        polymorphic: ``POLYMORPHIC`` as declared: ``True``, ``False``, or ``None`` when it declares neither.
        instead: The command an agent says in its place, or ``None``.
        reply: The seared class its handler returns, or ``None``.
        kinds: ``KINDS``, merged along the MRO, a subclass's entries over its bases'.
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
    kinds: Mapping[str, Kind]
    field_kinds: Mapping[str, Kind]
    phrases: tuple[Bound, ...]
    flags: tuple[str, ...]

    @property
    def is_command(self) -> bool:
        """Whether the class is a command, rather than a base: whether it has a ``PHRASE``."""
        return self.phrase is not None

    def kind_of(self, place: Place) -> Kind:
        """The kind a slot's words are read by: a renamed slot's own ``KINDS`` entry, else its field's kind."""
        return self.kinds[place.slot] if place.renamed else self.field_kinds[place.field]


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
    binding = _bind(cls, name, phrase=phrase, extra=extra, kinds=kinds, polymorphic=polymorphic)
    field_kinds = _field_kinds(cls, name, kinds, binding) if phrase is not None else MappingProxyType({})
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
        kinds=kinds,
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
    """Refuse a command that isn't decorated, and any base in its MRO whose fields seared would drop."""
    if is_command and not is_seared_class(cls):
        msg = f'{name} has a PHRASE but is not decorated: decorate it with @parsed.parsed'
        raise DeclarationError(msg)
    for base in cls.__mro__:
        if base in (Command, Seared) or not issubclass(base, Seared):
            continue
        declares_fields = any(isinstance(value, Field) for value in vars(base).values())
        if declares_fields and not is_seared_class(base):
            msg = (
                f'{base.__qualname__} declares fields but is not decorated, so seared would drop them from '
                f'{name}: decorate {base.__qualname__} with @parsed.parsed'
            )
            raise DeclarationError(msg)


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


def _bind(  # noqa: PLR0913 — the class, and what it declares about its phrases
    cls: type[Command],
    name: str,
    *,
    phrase: str | None,
    extra: tuple[str, ...],
    kinds: Mapping[str, object],
    polymorphic: bool | None,
) -> Binding:
    if phrase is None:
        return Binding(phrases=(), flags=())
    fields = {spec.attr: spec.field for spec in cls.__seared_fields__}
    own = vars(cls).get('KINDS', {})
    return bind(fields, name, phrase=phrase, extra_phrases=extra, kinds=kinds, own_kinds=own, polymorphic=polymorphic)


def _field_kinds(cls: type[Command], name: str, kinds: Mapping[str, Kind], binding: Binding) -> Mapping[str, Kind]:
    """Each field's kind, and a check that every ``Name`` the command reads by is scoped by another of its fields."""
    found: dict[str, Kind] = {}
    for spec in cls.__seared_fields__:
        kind = kinds.get(spec.attr) or default_kind(spec.field)
        if kind is None:
            what = type(spec.field).__name__
            msg = (
                f'{name}.{spec.attr} is a {what} field, which has no word form: give it a kind in KINDS, or say it '
                f'another way'
            )
            raise DeclarationError(msg)
        found[spec.attr] = kind
    # What reads by a kind: each field, and each renamed slot (by its own entry, for the field it fills).
    read: list[tuple[str, str, Kind]] = [(attr, attr, kind) for attr, kind in found.items()]
    read += [
        (place.slot, place.field, kinds[place.slot])
        for bound in binding.phrases
        for place in bound.places
        if place.renamed
    ]
    for said, field, kind in read:
        if isinstance(kind, Name) and kind.scope is not None and (kind.scope not in found or kind.scope == field):
            msg = (
                f'{name}: {said!r} is read as a {kind.category} scoped by {kind.scope!r}, which is no other field '
                f'of {name}'
            )
            raise DeclarationError(msg)
    return MappingProxyType(found)


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
