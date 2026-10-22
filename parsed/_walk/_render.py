"""Rendering: a command's instance back to the line that says it, so the tree reads that line to the same instance.

``render(tree, command, names)`` takes the first of the command's phrases that can say it:

- **a field the phrase leaves out holds its default,** and an optional slot holding its field's default is left out
  too, as the line it reads from would have;
- **with names,** each slot read by a ``Name`` with a resolver holds a key the resolver knows (given its scope), so
  a detachment's key is said by the detachment's twin, not the fleet's phrase. Loose, any value does.

**Each value is written by its field's kind** (:meth:`parsed.kinds.Kind.write`): a literal word for a value one reads
to, else the kind's own spelling, from the field's wire value. **A word is quoted** where the line would read it
otherwise: a value spelled like a literal word that may stand there (``dock "nearest"``), one with a space, one that
begins with ``--``, or none at all. A value holding a double quote can't be said, since a line has no escapes.

**Then the flags,** in the order the command declares its fields, each not at its default: a switch alone
(``--quiet``, or ``--no-stop`` for one that defaults to ``True``), a value after its name, and a list's given once for
each of its values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from parsed._phrase import Word
from parsed.errors import RenderError
from parsed.kinds import Name, Pairs

from ._terms import Arity, SlotKind

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from seared import Field, FieldSpec

    from parsed._phrase import Bound, Place
    from parsed.command import Command, Declaration
    from parsed.kinds import Kind
    from parsed.names import Resolver
    from parsed.tree import Node, Tree


def render(tree: Tree, command: Command, names: Mapping[str, Resolver] | None = None) -> str:
    """The line that says ``command``, as the module's docstring describes.

    Raises:
        RenderError: ``command`` isn't one of the tree's commands, or no phrase of it can say it.
    """
    cls = type(command)
    found = next((d for d in tree.commands if d.cls is cls), None)
    if found is None:
        msg = f"{cls.__qualname__} is not one of the tree's commands"
        raise RenderError(msg)
    said = _Saying(tree, found, command, names or {})
    for bound in found.phrases:
        line = said.by(bound)
        if line is not None:
            return line
    msg = f'no phrase of {cls.__qualname__} says {command!r}' + (', with the names given' if names else '')
    raise RenderError(msg)


class _Saying:
    """One instance, said: its fields' values and wire values, and the phrase that can say them."""

    def __init__(self, tree: Tree, found: Declaration, command: Command, names: Mapping[str, Resolver]) -> None:
        self.tree, self.found, self.command, self.names = tree, found, command, names
        self.specs: dict[str, FieldSpec] = {spec.attr: spec for spec in found.cls.__seared_fields__}
        self.wire = found.cls.dump(command)

    def by(self, bound: Bound) -> str | None:
        """The line ``bound``'s phrase says the instance in, or ``None`` when it can't say it."""
        if any(not self._at_default(field) for field in bound.left_out):
            return None
        places = {place.slot: place for place in bound.places}
        words: list[str] = []
        node = self.tree.root
        for part in bound.phrase.parts:
            if isinstance(part, Word):
                words.append(part.text)
                node = node.words[part.text]
                continue
            place = places[part.name]
            if not place.required and self._at_default(place.field):
                continue  # left out, on the route that leaves it out
            if not self._known(place):
                return None
            edge = node.slot
            if edge is None:  # a phrase compiled into the tree has its slot's edge
                return None
            words += self._slot_words(place, edge.kind, node, edge.node)
            node = edge.node
        return ' '.join([*words, *self._flags()])

    def _at_default(self, attr: str) -> bool:
        field = self.specs[attr].field
        default = field.default_factory() if field.default_factory is not None else field.default
        return not field.required and getattr(self.command, attr) == default

    def _value(self, attr: str) -> object:
        return self.wire.get(self.specs[attr].wire)

    def _known(self, place: Place) -> bool:
        """Whether the app's names know a slot's value, where its kind is a name with a resolver."""
        kind = self.found.kind_of(place)
        resolver = self.names.get(kind.category) if isinstance(kind, Name) else None
        if not isinstance(kind, Name) or resolver is None:
            return True
        scope = self._value(kind.scope) if kind.scope is not None else None
        values = self._value(place.field)
        each = values if isinstance(values, list) else [values]
        return all(resolver.lookup(str(value), None if scope is None else str(scope)) is not None for value in each)

    def _slot_words(self, place: Place, kind: SlotKind, node: Node, after: Node) -> list[str]:
        """A slot's value as words, each quoted where the line would read it otherwise."""
        spelled = self._spelled(place.field, self.found.kind_of(place))
        if kind is SlotKind.REST and not place.many and not isinstance(self.found.kind_of(place), Pairs):
            text = spelled[0] if spelled else ''
            spelled = text.split() if text and ' '.join(text.split()) == text else [text]
        if kind is SlotKind.ONE:
            return [_quoted(word, node.words) for word in spelled]
        stops = set(after.words) if kind is SlotKind.MANY else set()
        return [_quoted(word, {*stops, *node.words} if at == 0 else stops) for at, word in enumerate(spelled)]

    def _spelled(self, attr: str, kind: Kind) -> list[str]:
        field = self.specs[attr].field
        value = self._value(attr)
        if field.many and isinstance(value, list):
            return [word for item in value for word in kind.write(item, field)]
        return kind.write(value, field)

    def _flags(self) -> list[str]:
        """The flags not at their defaults, in the order the command declares its fields."""
        words: list[str] = []
        for flag in self.tree.flags_of(self.found.cls).values():
            if self._at_default(flag.field):
                continue
            if flag.arity is Arity.SWITCH:
                if bool(getattr(self.command, flag.field)) is not flag.negated:
                    words.append(f'--{flag.name}')
                continue
            field: Field = self.specs[flag.field].field
            kind = self.found.field_kinds[flag.field]
            value = self._value(flag.field)
            for item in value if field.many and isinstance(value, list) else [value]:
                words += [f'--{flag.name}', _quoted(' '.join(kind.write(item, field)), ())]
        return words


def _quoted(word: str, literals: Collection[str]) -> str:
    """A word as a line says it: quoted where it would read as a literal, hold a space, or begin as a flag."""
    if '"' in word:
        msg = f"{word!r} can't be said on a line: a word can't hold a double quote"
        raise RenderError(msg)
    plain = word and not any(ch.isspace() for ch in word) and not word.startswith('--')
    return word if plain and word.lower() not in literals else f'"{word}"'
