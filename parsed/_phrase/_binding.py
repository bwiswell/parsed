"""How a command's phrases bind to its fields.

**``PHRASE`` first.** Each of its slots names a field of the command, which the slot fills: a positional. Every
other field is a flag. A slot whose field may be left out (it isn't ``required``) is optional, and a ``many`` field's
slot takes several words; either is followed by a word or ends the phrase, so a line reads one way.

**Then each of ``EXTRA_PHRASES``:**

- **a slot named after a field** fills that field, and the field must be one of ``PHRASE``'s slots;
- **a slot named after no field renames one:** it needs a ``KINDS`` entry by its own name, and fills the field of
  ``PHRASE``'s slot at the same place. So a phrase that renames keeps ``PHRASE``'s slots, in their order;
- **a slot left out** keeps its field's default, so that field must have one.

**``POLYMORPHIC``,** when declared, is checked: ``True`` wants a phrase that renames a slot, ``False`` refuses one.
And a command's own ``KINDS`` names its fields or its renamed slots: an entry that names neither is a typo.
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
        field: The field it fills: the slot's own name, or for a renamed slot, ``PHRASE``'s slot at its place.
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
        """Whether the slot renames its field."""
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
        """Whether one of its slots renames a field."""
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


def bind(  # noqa: PLR0913 — a command's phrases, and what it declares about them
    fields: Mapping[str, Field],
    name: str,
    *,
    phrase: str,
    extra_phrases: tuple[str, ...],
    kinds: Mapping[str, object],
    own_kinds: Mapping[str, object],
    polymorphic: bool | None,
) -> Binding:
    """Bind a command's phrases to its fields, by the rules in this module's docstring.

    Args:
        fields: The command's fields, by attribute name.
        name: The command class's name, for messages.
        phrase: Its ``PHRASE``.
        extra_phrases: Its ``EXTRA_PHRASES``.
        kinds: Its ``KINDS``, merged along its bases.
        own_kinds: The ``KINDS`` it declares itself.
        polymorphic: ``POLYMORPHIC`` as declared, ``None`` if it isn't.

    Raises:
        DeclarationError: A phrase doesn't read or doesn't bind. The message names the class, the phrase, and why.
    """
    canonical = _bind_canonical(fields, name, phrase)
    slotted = {place.field: place for place in canonical.places}
    phrases = [canonical]
    phrases.extend(
        _bind_extra(fields, name, text, canonical=canonical, slotted=slotted, kinds=kinds) for text in extra_phrases
    )
    _check_polymorphic(name, phrases[1:], polymorphic=polymorphic)
    renamed = {place.slot for bound in phrases for place in bound.places if place.renamed}
    for key in own_kinds:
        if key not in fields and key not in renamed:
            msg = f'{name}.KINDS names {key!r}, which is no field of {name} and no slot its phrases rename'
            raise DeclarationError(msg)
    flags = tuple(attr for attr in fields if attr not in slotted)
    return Binding(phrases=tuple(phrases), flags=flags)


def _read(name: str, constant: str, text: str) -> Phrase:
    try:
        return parse(text)
    except ValueError as exc:
        msg = f'{name}.{constant} {text!r}: {exc}'
        raise DeclarationError(msg) from exc


def _bind_canonical(fields: Mapping[str, Field], name: str, text: str) -> Bound:
    phrase = _read(name, 'PHRASE', text)
    places: list[Place] = []
    for slot in phrase.slots:
        field = fields.get(slot.name)
        if field is None:
            known = ', '.join(fields) or 'none'
            msg = f'{name}.PHRASE {phrase.text!r}: {{{slot.name}}} names no field of {name} (its fields: {known})'
            raise DeclarationError(msg)
        places.append(_place(slot, slot.name, field))
    _check_order(name, 'PHRASE', phrase, places)
    return Bound(phrase=phrase, places=tuple(places))


def _bind_extra(  # noqa: PLR0913 — the phrase, and what it binds against
    fields: Mapping[str, Field],
    name: str,
    text: str,
    *,
    canonical: Bound,
    slotted: Mapping[str, Place],
    kinds: Mapping[str, object],
) -> Bound:
    phrase = _read(name, 'EXTRA_PHRASES', text)
    where = f'{name}.EXTRA_PHRASES {phrase.text!r}'
    if any(slot.name not in fields for slot in phrase.slots):
        places = _bind_renaming(where, phrase, canonical, kinds, fields)
        left_out: tuple[str, ...] = ()
    else:
        places = []
        for slot in phrase.slots:
            if slot.name not in slotted:
                msg = f"{where}: {{{slot.name}}} is a flag in PHRASE; an extra phrase takes only PHRASE's slots"
                raise DeclarationError(msg)
            if slot.rest != slotted[slot.name].rest:
                said = 'the rest of the line' if slotted[slot.name].rest else 'one value'
                msg = f'{where}: {{{slot.name}}} is {said} in PHRASE, and is written alike here'
                raise DeclarationError(msg)
            places.append(_place(slot, slot.name, fields[slot.name]))
        named = {place.field for place in places}
        left_out = tuple(field for field in slotted if field not in named)
        for field in left_out:
            if slotted[field].required:
                msg = (
                    f'{where}: it leaves out {{{field}}}, which is required; give the field a default, or keep the slot'
                )
                raise DeclarationError(msg)
    _check_order(name, 'EXTRA_PHRASES', phrase, places)
    return Bound(phrase=phrase, places=tuple(places), left_out=left_out)


def _bind_renaming(
    where: str,
    phrase: Phrase,
    canonical: Bound,
    kinds: Mapping[str, object],
    fields: Mapping[str, Field],
) -> list[Place]:
    """Bind a phrase that renames a slot: it keeps PHRASE's slots, in their order, renaming one or more."""
    ours, theirs = phrase.slots, canonical.places
    if len(ours) != len(theirs):
        msg = f'{where}: it renames a slot, so it keeps the {len(theirs)} slots of PHRASE, not {len(ours)}'
        raise DeclarationError(msg)
    places: list[Place] = []
    for slot, target in zip(ours, theirs, strict=True):
        if slot.name in fields and slot.name != target.field:
            msg = (
                f'{where}: {{{slot.name}}} stands where PHRASE has {{{target.field}}}; a phrase that renames a slot '
                "keeps the others in PHRASE's order"
            )
            raise DeclarationError(msg)
        if slot.name not in fields and slot.name not in kinds:
            msg = (
                f'{where}: {{{slot.name}}} names no field, so it renames {{{target.field}}}, and needs a KINDS entry '
                f'{slot.name!r} to say how its words are read'
            )
            raise DeclarationError(msg)
        if slot.rest != target.rest:
            msg = f'{where}: {{{slot.name}}} stands where PHRASE has {{{target.field}{"**" if target.rest else ""}}}'
            raise DeclarationError(msg)
        places.append(_place(slot, target.field, fields[target.field]))
    return places


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


def _check_polymorphic(name: str, extras: list[Bound], *, polymorphic: bool | None) -> None:
    renaming = next((bound for bound in extras if bound.renames), None)
    if polymorphic is True and renaming is None:
        msg = f'{name}.POLYMORPHIC is True, but no extra phrase renames a slot'
        raise DeclarationError(msg)
    if polymorphic is False and renaming is not None:
        place = next(place for place in renaming.places if place.renamed)
        msg = f'{name}.POLYMORPHIC is False, but {renaming.phrase.text!r} renames {{{place.field}}} as {{{place.slot}}}'
        raise DeclarationError(msg)
