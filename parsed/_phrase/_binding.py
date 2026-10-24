"""How a command's phrases bind to its fields.

**Every slot fills a field, by name:** the field it's named after, or, for a slot named in ``ALIASES``, the field the
alias gives (``ALIASES = {'detachment': 'fleet'}``: ``{detachment}`` fills ``fleet``). A slot that's neither is
refused, as is a phrase with two slots for one field. A slot by an alias reads by its own ``KINDS`` entry, if it has
one, else by its field's kind.

**``PHRASE`` first.** The fields its slots fill are the positionals; every other field is a flag. A slot whose field
may be left out (it isn't ``required``) is optional, and a ``many`` field's slot takes several words; either is
followed by a word or ends the phrase, so a line reads one way.

**Then each of ``EXTRA_PHRASES``:** each slot fills one of ``PHRASE``'s positionals, in any order, and is the rest of
the line where ``PHRASE``'s is. A positional it leaves out keeps its default, so that field must have one.

**``POLYMORPHIC``,** when declared, is checked: ``True`` wants a phrase that says a slot by an alias, ``False``
refuses one. And a command's own ``KINDS`` names its fields or its aliases: an entry that names neither is a typo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from parsed.errors import DeclarationError

from ._grammar import Phrase, Slot, parse

if TYPE_CHECKING:
    from collections.abc import Mapping

    from seared import Field


@dataclass(frozen=True, slots=True)
class Place:
    """A slot, bound: the field it fills.

    Attributes:
        slot: The slot's name as the phrase writes it, which is also its ``KINDS`` key.
        field: The field it fills: the slot's own name, or the field its alias gives.
        required: Whether the field must be given, so the slot can't be left empty.
        many: Whether it takes several words.
        rest: Whether it takes the rest of the line.
    """

    slot: str
    field: str
    required: bool
    many: bool
    rest: bool

    @property
    def renamed(self) -> bool:
        """Whether the slot says its field by an alias."""
        return self.slot != self.field


@dataclass(frozen=True, slots=True)
class Bound:
    """A phrase, bound to a command's fields.

    Attributes:
        phrase: The phrase, read.
        places: Its slots, bound, in order.
        left_out: The fields ``PHRASE`` has slots for that this phrase leaves out; they keep their defaults.
    """

    phrase: Phrase
    places: tuple[Place, ...]
    left_out: tuple[str, ...] = ()

    @property
    def renames(self) -> bool:
        """Whether one of its slots says its field by an alias."""
        return any(place.renamed for place in self.places)


@dataclass(frozen=True, slots=True)
class Binding:
    """A command's phrases, bound.

    Attributes:
        phrases: ``PHRASE``, then each of ``EXTRA_PHRASES``, bound.
        flags: The fields no slot of ``PHRASE`` names, in their declared order.
    """

    phrases: tuple[Bound, ...]
    flags: tuple[str, ...]


def bind(  # noqa: PLR0913 -- a command's phrases, and what it declares about them
    fields: Mapping[str, Field],
    name: str,
    *,
    phrase: str,
    extra_phrases: tuple[str, ...],
    aliases: Mapping[str, str],
    own_kinds: Mapping[str, object],
    polymorphic: bool | None,
) -> Binding:
    """Bind a command's phrases to its fields, by the rules in this module's docstring.

    Args:
        fields: The command's fields, by attribute name.
        name: The command class's name, for messages.
        phrase: Its ``PHRASE``.
        extra_phrases: Its ``EXTRA_PHRASES``.
        aliases: Its ``ALIASES``, merged along its bases: a slot's name, to the field it fills.
        own_kinds: The ``KINDS`` it declares itself.
        polymorphic: ``POLYMORPHIC`` as declared, ``None`` if it isn't.

    Raises:
        DeclarationError: A phrase doesn't read or doesn't bind. The message names the class, the phrase, and why.
    """
    for alias, field in aliases.items():
        if alias in fields:
            msg = f'{name}.ALIASES gives {alias!r} to {field!r}, but {alias!r} is a field of {name} already'
            raise DeclarationError(msg)
    canonical = _bind_phrase(fields, name, 'PHRASE', phrase, aliases=aliases)
    slotted = {place.field: place for place in canonical.places}
    phrases = [canonical]
    phrases.extend(_bind_extra(fields, name, text, slotted=slotted, aliases=aliases) for text in extra_phrases)
    _check_polymorphic(name, phrases, polymorphic=polymorphic)
    for key in own_kinds:
        if key not in fields and key not in aliases:
            msg = f'{name}.KINDS names {key!r}, which is no field of {name} and none of its ALIASES'
            raise DeclarationError(msg)
    flags = tuple(attr for attr in fields if attr not in slotted)
    return Binding(phrases=tuple(phrases), flags=flags)


def _read(name: str, constant: str, text: str) -> Phrase:
    try:
        return parse(text)
    except ValueError as exc:
        msg = f'{name}.{constant} {text!r}: {exc}'
        raise DeclarationError(msg) from exc


def _bind_phrase(
    fields: Mapping[str, Field], name: str, constant: str, text: str, *, aliases: Mapping[str, str]
) -> Bound:
    """Bind a phrase's slots, each to the field it names or its alias gives, and check their order."""
    phrase = _read(name, constant, text)
    where = f'{name}.{constant} {phrase.text!r}'
    places: list[Place] = []
    filled: dict[str, str] = {}
    for slot in phrase.slots:
        field_name = slot.name if slot.name in fields else aliases.get(slot.name)
        if field_name is None:
            known = ', '.join(fields) or 'none'
            given = f'; its ALIASES: {", ".join(aliases)}' if aliases else ''
            msg = f'{where}: {{{slot.name}}} names no field of {name} (its fields: {known}{given})'
            raise DeclarationError(msg)
        if field_name not in fields:
            msg = f'{where}: ALIASES gives {{{slot.name}}} to {field_name!r}, which is no field of {name}'
            raise DeclarationError(msg)
        if field_name in filled:
            msg = f'{where}: {{{filled[field_name]}}} and {{{slot.name}}} both fill {field_name}'
            raise DeclarationError(msg)
        filled[field_name] = slot.name
        places.append(_place(slot, field_name, fields[field_name]))
    _check_order(name, constant, phrase, places)
    return Bound(phrase=phrase, places=tuple(places))


def _bind_extra(
    fields: Mapping[str, Field],
    name: str,
    text: str,
    *,
    slotted: Mapping[str, Place],
    aliases: Mapping[str, str],
) -> Bound:
    """Bind one of ``EXTRA_PHRASES``: its slots PHRASE's positionals, any it leaves out optional."""
    bound = _bind_phrase(fields, name, 'EXTRA_PHRASES', text, aliases=aliases)
    where = f'{name}.EXTRA_PHRASES {bound.phrase.text!r}'
    for place in bound.places:
        said = f'{{{place.slot}}}' if not place.renamed else f'{{{place.slot}}}, for {place.field},'
        if place.field not in slotted:
            msg = f"{where}: {said} is a flag in PHRASE; an extra phrase takes only PHRASE's slots"
            raise DeclarationError(msg)
        if place.rest != slotted[place.field].rest:
            written = 'the rest of the line' if slotted[place.field].rest else 'one value'
            msg = f'{where}: {said} is {written} in PHRASE, and is written alike here'
            raise DeclarationError(msg)
    named = {place.field for place in bound.places}
    left_out = tuple(field for field in slotted if field not in named)
    for field in left_out:
        if slotted[field].required:
            msg = f'{where}: it leaves out {{{field}}}, which is required; give the field a default, or keep the slot'
            raise DeclarationError(msg)
    return Bound(phrase=bound.phrase, places=bound.places, left_out=left_out)


def _place(slot: Slot, field_name: str, field: Field) -> Place:
    return Place(slot=slot.name, field=field_name, required=field.required, many=field.many, rest=slot.rest)


def _check_order(name: str, constant: str, phrase: Phrase, places: list[Place]) -> None:
    """Refuse a slot that may be empty, or takes several words, followed straight by another slot."""
    by_slot = {place.slot: place for place in places}
    parts = phrase.parts
    for at, part in enumerate(parts[:-1]):
        if not (isinstance(part, Slot) and isinstance(parts[at + 1], Slot)):
            continue
        place = by_slot[part.name]
        if not place.required or place.many:
            why = 'may be left out' if not place.required else 'takes several words'
            msg = (
                f'{name}.{constant} {phrase.text!r}: {{{part.name}}} {why}, so it is followed by a word or ends the '
                f'phrase, and a line reads one way'
            )
            raise DeclarationError(msg)


def _check_polymorphic(name: str, phrases: list[Bound], *, polymorphic: bool | None) -> None:
    aliasing = next((bound for bound in phrases if bound.renames), None)
    if polymorphic is True and aliasing is None:
        msg = f'{name}.POLYMORPHIC is True, but no phrase says a slot by an alias'
        raise DeclarationError(msg)
    if polymorphic is False and aliasing is not None:
        place = next(place for place in aliasing.places if place.renamed)
        msg = f'{name}.POLYMORPHIC is False, but {aliasing.phrase.text!r} says {{{place.field}}} as {{{place.slot}}}'
        raise DeclarationError(msg)
