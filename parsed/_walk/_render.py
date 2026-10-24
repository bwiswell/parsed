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

**A chain's steps** (a sequence of them, one chain's, sharing its fields' values) are said on one line, joined by
``then``: the first as a line of its own says it, and each after it in its own words, from where the first's shared
part ends, by a phrase that shares that part (a twin's after a twin's). Its flags follow each step's words. A step's
names are said where the chain will be by then, as the line is read: a name whose scope follows the chain is known
where the steps before it have moved it. In a step, a value spelled ``then`` is quoted, since the line is cut there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from parsed._phrase import Word
from parsed.errors import RenderError
from parsed.kinds import Name, Pairs

from ._terms import THEN, Arity, SlotKind
from ._walker import _key, _Moved, _shared, head_of

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from seared import Field, FieldSpec

    from parsed._phrase import Bound, Place
    from parsed.command import Command, Declaration
    from parsed.kinds import Kind
    from parsed.names import Resolver
    from parsed.tree import Node, Tree


def render(tree: Tree, command: Command | Sequence[Command], names: Mapping[str, Resolver] | None = None) -> str:
    """The line that says ``command``, or a chain's steps, as the module's docstring describes.

    Raises:
        RenderError: A command isn't one of the tree's, or no phrase of it can say it; or the steps aren't one
            chain's, or don't share its fields' values.
    """
    if isinstance(command, (list, tuple)):
        return _chain(tree, list(command), names or {})
    one = cast('Command', command)
    said = _Saying(_declared(tree, one), one, names or {})
    return said.line(tree, said.phrase())


def key(
    found: Declaration, command: Command, names: Mapping[str, Resolver] | None = None, moved: _Moved | None = None
) -> str:
    """``command``'s key, by the phrase that says it: its words and its slots' values, joined by ``/``.

    A slot of several words, the rest of the line, an optional slot at its default and the flags are left out.
    ``moved`` is where a chain's steps before it have moved it, for a name whose scope follows the chain.

    Raises:
        RenderError: No phrase of it can say it.
    """
    said = _Saying(found, command, names or {}, moved)
    return said.key(said.phrase())


def moved_by(found: Declaration, command: Command, moved: _Moved | None) -> _Moved | None:
    """Where a chain is after ``command``, a step, as its line will say it: from ``moved``, where it was before."""
    return _Saying(found, command, {}).moves(moved)


def _declared(tree: Tree, command: Command) -> Declaration:
    cls = type(command)
    found = next((d for d in tree.commands if d.cls is cls), None)
    if found is None:
        msg = f"{cls.__qualname__} is not one of the tree's commands"
        raise RenderError(msg)
    return found


def _chain(tree: Tree, steps: list[Command], names: Mapping[str, Resolver]) -> str:
    """A chain's steps on one line, joined by ``then``.

    The first is said as a line of its own says it, and each after it from the chain's place in the tree.
    """
    if not steps:
        msg = 'a chain has a step at least: no steps, no line'
        raise RenderError(msg)
    if len(steps) == 1:
        return render(tree, steps[0], names)
    founds = [_declared(tree, step) for step in steps]
    base = founds[0].chain
    if base is None:
        msg = f"{steps[0]!r} is no step: a chain's steps are the commands beneath a base that declares STEPS"
        raise RenderError(msg)
    for at, (found, step) in enumerate(zip(founds, steps, strict=True)):
        if found.chain is not base:
            msg = f"step {at + 1} of the chain, {step!r}, is not a step of {base.__qualname__}'s chain"
            raise RenderError(msg)
    shared = _shared(base)
    for attr in sorted(shared):
        first = getattr(steps[0], attr)
        for at, step in enumerate(steps[1:], start=2):
            if getattr(step, attr) != first:
                msg = (
                    f"a chain's steps share {base.__qualname__}'s fields: {attr} is {first!r} in its first step and "
                    f'{getattr(step, attr)!r} in step {at}'
                )
                raise RenderError(msg)
    said = _Saying(founds[0], steps[0], names)
    bound = said.phrase()
    head = head_of(bound, shared)
    words, start = said.said(tree.top, bound, stop=head)
    rest, _ = said.said(start, bound, start=head)
    line = [*tree.under.split(), *words, *rest, *said.flags(tree)]
    moved = said.moves(None)
    for found, step in zip(founds[1:], steps[1:], strict=True):
        said = _Saying(found, step, names, moved)
        bound = said.phrase(head=_parts(bound, head))
        line += [THEN, *said.said(start, bound, start=head_of(bound, shared))[0], *said.flags(tree)]
        moved = said.moves(moved)
    return ' '.join(line)


def _parts(bound: Bound, head: int) -> tuple[str, ...]:
    """A phrase's first ``head`` parts as it writes them (``fleet``, ``{fleet}``), to tell a chain's shared part by."""
    return tuple(part.text if isinstance(part, Word) else f'{{{part.name}}}' for part in bound.phrase.parts[:head])


class _Saying:
    """One instance, said: its fields' values and wire values, and the phrase that can say them.

    ``moved`` is where a chain's steps before it have moved the chain, for a name whose scope follows it.
    """

    def __init__(
        self, found: Declaration, command: Command, names: Mapping[str, Resolver], moved: _Moved | None = None
    ) -> None:
        self.found, self.command, self.names, self.moved = found, command, names, moved
        self.specs: dict[str, FieldSpec] = {spec.attr: spec for spec in found.cls.__seared_fields__}
        self.wire = found.cls.dump(command)
        self.then = found.chain is not None  # a step's line is cut at `then`, so a value spelled so is quoted

    def phrase(self, head: tuple[str, ...] | None = None) -> Bound:
        """The first of the command's phrases that can say the instance; in a chain, one whose shared part is ``head``.

        Raises:
            RenderError: None can.
        """
        phrases = self.found.phrases
        if head is not None:
            shared = _shared(cast('type', self.found.chain))
            phrases = tuple(bound for bound in phrases if _parts(bound, head_of(bound, shared)) == head)
        found = next((bound for bound in phrases if self._can_say(bound)), None)
        if found is None:
            cls = self.found.cls.__qualname__
            if not phrases:
                said = ' '.join(cast('tuple[str, ...]', head))
                msg = f"{cls} has no phrase under {said!r}, the chain's first step's words"
            else:
                msg = f'no phrase of {cls} says {self.command!r}' + (', with the names given' if self.names else '')
            raise RenderError(msg)
        return found

    def moves(self, before: _Moved | None) -> _Moved | None:
        """Where the chain is after this step, as its line says it: where its ``MOVES`` field says, else as before.

        Somewhere unsaid for ``MOVES = True``, a field at its default (the line leaves it out), or ``None``.
        """
        moves = self.found.moves
        if moves is False:
            return before
        value = None if moves is True or self._at_default(moves) else self._value(moves)
        return _Moved(None, None) if value is None else _Moved(str(value), None)

    def _can_say(self, bound: Bound) -> bool:
        """Whether its left-out fields are at their defaults, and the names know each value it says."""
        if any(not self._at_default(field) for field in bound.left_out):
            return False
        return all(self._known(place) for place in bound.places if not self._skipped(place))

    def _skipped(self, place: Place) -> bool:
        """Whether an optional slot is left out, holding its field's default, on the route that leaves it out."""
        return not place.required and self._at_default(place.field)

    def line(self, tree: Tree, bound: Bound) -> str:
        """The line ``bound``'s phrase says the instance in, each word quoted where the tree would read it otherwise."""
        return ' '.join([*tree.under.split(), *self.said(tree.top, bound)[0], *self.flags(tree)])

    def said(self, node: Node, bound: Bound, *, start: int = 0, stop: int | None = None) -> tuple[list[str], Node]:
        """The words ``bound``'s parts from ``start`` to ``stop`` say, walked from ``node``; and where they reach."""
        places = {place.slot: place for place in bound.places}
        words: list[str] = []
        for part in bound.phrase.parts[start:stop]:
            if isinstance(part, Word):
                words.append(part.text)
                node = node.words[part.text]
                continue
            place = places[part.name]
            edge = node.slot
            if self._skipped(place) or edge is None:  # a compiled phrase has its slot's edge
                continue
            words += self._slot_words(place, edge.kind, node, edge.node)
            node = edge.node
        return words, node

    def key(self, bound: Bound) -> str:
        """The key ``bound``'s phrase says the instance by: its words, and each one-word slot's value as written."""
        places = {place.slot: place for place in bound.places}
        segments: list[str] = []
        for part in bound.phrase.parts:
            if isinstance(part, Word):
                segments.append(part.text)
                continue
            place = places[part.name]
            if place.many or place.rest or self._skipped(place):
                continue
            segments.append(' '.join(self._spelled(place.field, self.found.kind_of(place))))
        return '/'.join(segments)

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
        if kind.follows and self.moved is not None:
            scope = self.moved.key
        else:
            scope = self._value(kind.scope) if kind.scope is not None else None
        values = self._value(place.field)
        each = values if isinstance(values, list) else [values]
        return all(_key(resolver, str(value), None if scope is None else str(scope)) is not None for value in each)

    def _slot_words(self, place: Place, kind: SlotKind, node: Node, after: Node) -> list[str]:
        """A slot's value as words, each quoted where the line would read it otherwise."""
        spelled = self._spelled(place.field, self.found.kind_of(place))
        if kind is SlotKind.REST and not place.many and not isinstance(self.found.kind_of(place), Pairs):
            text = spelled[0] if spelled else ''
            spelled = text.split() if text and ' '.join(text.split()) == text else [text]
        cut = (THEN,) if self.then else ()
        if kind is SlotKind.ONE:
            literals = {*node.words, *cut} if cut else node.words
            return [_quoted(word, literals) for word in spelled]
        stops = {*after.words, *cut} if kind is SlotKind.MANY else set(cut)
        return [_quoted(word, {*stops, *node.words} if at == 0 else stops) for at, word in enumerate(spelled)]

    def _spelled(self, attr: str, kind: Kind) -> list[str]:
        field = self.specs[attr].field
        value = self._value(attr)
        if field.many and isinstance(value, list):
            return [word for item in value for word in kind.write(item, field)]
        return kind.write(value, field)

    def flags(self, tree: Tree) -> list[str]:
        """The flags not at their defaults, in the order the command declares its fields."""
        words: list[str] = []
        for flag in tree.flags_of(self.found.cls).values():
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
