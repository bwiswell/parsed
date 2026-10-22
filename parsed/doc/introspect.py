"""What a command declares, as data: :class:`CommandDoc`, beside seared's ``SchemaDoc`` of its fields.

:func:`introspect_command` reads a command class's declaration into a :class:`CommandDoc`, in the shape of
``zeared.doc``'s ``MessageDoc`` where the meaning matches, so a tool reads commands and messages alike: seared's
``SchemaDoc`` for the fields, then what only a command says. Its phrases; each slot once, with the field it fills and
the kind its words read by; its flags; each field's kind; the constants; and the seared classes it takes fields from
that aren't commands (a protocol's request class it inherits), beside its ``REPLY``, so a tool can tell a command from
the contract it's built on.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, TypeGuard

from seared import Seared
from seared.doc import SchemaDoc, is_seared_class
from seared.doc import introspect as _seared_introspect

from parsed.command import Command, declaration
from parsed.tree import Arity, Tree

if TYPE_CHECKING:
    from collections.abc import Mapping

    from parsed.effect import Effect
    from parsed.kinds import Kind


@dataclass(frozen=True, slots=True)
class SlotDoc:
    """A slot of the command's phrases.

    Attributes:
        name: As a phrase writes it: the field's name, or an alias.
        field: The field it fills.
        kind: The kind its words read by: an alias's own, or its field's.
        required: Whether its field must be given, so the slot can't be left out.
        many: Whether it takes several words.
        rest: Whether it takes the rest of the line.
    """

    name: str
    field: str
    kind: Kind
    required: bool
    many: bool
    rest: bool


@dataclass(frozen=True, slots=True)
class FlagDoc:
    """A flag of the command.

    Attributes:
        name: As a line writes it, without its dashes: ``for``, ``no-stop``.
        field: The field it sets.
        kind: The kind its value reads by.
        switch: Whether it takes no value.
        negated: Whether it's a ``--no-…`` switch, setting its field ``False``.
        required: Whether the command can't go without it.
        many: Whether it may be given again, each time adding a value.
    """

    name: str
    field: str
    kind: Kind
    switch: bool
    negated: bool
    required: bool
    many: bool


@dataclass(frozen=True, slots=True)
class CommandDoc:
    """A command, as data.

    Attributes:
        schema: seared's ``SchemaDoc`` of its fields.
        phrase: Its ``PHRASE``.
        extra_phrases: Its ``EXTRA_PHRASES``.
        slots: Every slot of its phrases, each name once, in the order they first stand.
        flags: Its flags, in the order its fields are declared.
        kinds: Each field's kind, by attribute name.
        effect: Its ``EFFECT``, or ``None`` when it declares none; never inferred.
        asks: Whether it may ask before it acts.
        interactive: Whether it's only for a person at the client.
        polymorphic: ``POLYMORPHIC`` as declared, or ``None``.
        instead: The command an agent says in its place, or ``None``.
        reply: The seared class its handler returns, or ``None``.
        fields_from: The seared classes it takes fields from that aren't commands, nearest first: a protocol's
            request class it inherits.
    """

    schema: SchemaDoc
    phrase: str
    extra_phrases: tuple[str, ...]
    slots: tuple[SlotDoc, ...]
    flags: tuple[FlagDoc, ...]
    kinds: Mapping[str, Kind]
    effect: Effect | None
    asks: bool
    interactive: bool
    polymorphic: bool | None
    instead: type[Command] | None
    reply: type[Seared] | None
    fields_from: tuple[type[Seared], ...]


def is_command_class(obj: object) -> TypeGuard[type[Command]]:
    """Whether ``obj`` is a command class: a decorated subclass of ``Command`` with a ``PHRASE``, not a base."""
    return isinstance(obj, type) and issubclass(obj, Command) and obj.PHRASE is not None and is_seared_class(obj)


def introspect_command(cls: type[Command]) -> CommandDoc:
    """``cls``'s :class:`CommandDoc`.

    Raises:
        TypeError: ``cls`` isn't a command class.
        DeclarationError: Its declaration doesn't check, as ``declaration`` and a tree of it refuse it.
    """
    if not is_command_class(cls):
        msg = f'introspect_command() takes a command class, got {cls!r}'
        raise TypeError(msg)
    found = declaration(cls)
    fields = {spec.attr: spec.field for spec in cls.__seared_fields__}
    slots: dict[str, SlotDoc] = {}
    for bound in found.phrases:
        for place in bound.places:
            slots.setdefault(
                place.slot,
                SlotDoc(
                    name=place.slot,
                    field=place.field,
                    kind=found.kind_of(place),
                    required=place.required,
                    many=place.many,
                    rest=place.rest,
                ),
            )
    flags = tuple(
        FlagDoc(
            name=flag.name,
            field=flag.field,
            kind=found.field_kinds[flag.field],
            switch=flag.arity is Arity.SWITCH,
            negated=flag.negated,
            required=fields[flag.field].required,
            many=fields[flag.field].many,
        )
        for flag in Tree([cls]).flags_of(cls).values()
    )
    return CommandDoc(
        schema=_seared_introspect(cls),
        phrase=found.phrase or '',
        extra_phrases=found.extra_phrases,
        slots=tuple(slots.values()),
        flags=flags,
        kinds=MappingProxyType(dict(found.field_kinds)),
        effect=found.effect,
        asks=found.asks,
        interactive=found.interactive,
        polymorphic=found.polymorphic,
        instead=found.instead,
        reply=found.reply,
        fields_from=_fields_from(cls),
    )


def _fields_from(cls: type) -> tuple[type[Seared], ...]:
    """The seared classes in ``cls``'s MRO that aren't commands, nearest first."""
    return tuple(
        base
        for base in cls.__mro__[1:]
        if is_seared_class(base) and not issubclass(base, Command) and base is not Seared
    )
