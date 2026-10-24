"""Completion: the words that may come next on a line being typed, as Tab offers them.

``complete(tree, text, names)`` reads the line up to the cursor loosely, as far as its words go, and offers what may
come next, each matching the word being typed, case aside:

- **a slot's values:** its kind's literal words, its own offers (an ``Enum``'s values, ``true`` and ``false``, a few
  spans of time), and for a name, the ``options`` of the resolver for its category, given its scope: in a chain's
  later step, for a scope that follows the chain, where its steps so far have moved it;
- **the literal words** that may come next;
- **the command's flags,** once the line says a whole command: those not yet given (a list's again), and ``--yes``
  for one that asks first. While a flag is being typed before then, the flags of every command the line may be;
- **a flag's values,** when the line ends at a flag waiting for one;
- **a pair's keys, then each key's values,** for a ``Pairs`` field, and the command's flags beside them, as in any
  rest of the line.

A quoted word is a value, so while one is typed, literal words and flags aren't offered. A candidate with a space in
it is offered quoted, as it would be typed. A line whose words don't read as far as they go is offered nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple, cast

from parsed._phrase import Word
from parsed.errors import ReadError
from parsed.kinds import Name, Named, Pairs
from parsed.wait import FLAGS as WAIT_FLAGS

from ._terms import RESERVED, THEN, Arity, SlotKind
from ._walker import (
    _ends,
    _flag,
    _head,
    _key,
    _Later,
    _literal,
    _Moved,
    _moved,
    _onward,
    _pieces,
    _place_of,
    _shared,
    _taken,
    _Walker,
)
from ._words import Token, split, word

if TYPE_CHECKING:
    from collections.abc import Mapping

    from seared import Field

    from parsed.kinds import Kind
    from parsed.names import PairsResolver, Resolver
    from parsed.tree import Edge, End, Node, Tree

    from ._walker import Reading

#: A candidate, and whether it's a literal word or a flag, which a quoted word never is.
type _Offer = tuple[str, bool]

#: The slots walked so far: each slot's edge, and the words it took.
type _Slots = list[tuple[Edge, tuple[Token, ...]]]


class Completion(NamedTuple):
    """What may come next on a line being typed.

    Attributes:
        words: The candidates, as they'd be typed (quoted, where one holds a space), each matching the word being
            typed.
        replace: How many characters before the cursor each replaces: the word being typed, or none.
    """

    words: list[str]
    replace: int


def complete(tree: Tree, text: str, names: Mapping[str, Resolver] | None = None) -> Completion:
    """What may come next on ``text``, a line up to the cursor, as the module's docstring describes."""
    tokens, partial = being_typed(text)
    flagging = partial is not None and not partial.quoted and partial.text.startswith('--')
    chained = _chained(tree, text, tokens, names or {}) if tree.chains else (tokens, None, [])
    if chained is None:
        return Completion(words=[], replace=0 if partial is None else len(text) - partial.start)
    tokens, later, head = chained
    moved = None if later is None else later.moved
    found = _Completer(tree, names or {}, flagging=flagging, moved=moved).offers(tokens, later, head)
    said = '' if partial is None else partial.text.lower()
    quoted = partial is not None and partial.quoted
    words: list[str] = []
    for offer, literal in found:
        typed = _typed(offer)
        if (quoted and literal) or typed in words or not offer.lower().startswith(said):
            continue
        words.append(typed)
    return Completion(words=words, replace=0 if partial is None else len(text) - partial.start)


def goes(tree: Tree, tokens: list[Token]) -> bool:
    """Whether ``tokens``, words without flags, go along ``tree`` as far as they're given.

    They're read loosely, each a literal word or a slot's, as completion reads a line.
    """
    return _Completer(tree, {}, flagging=False)._walk(tokens) is not None  # noqa: SLF001 -- the walk is this module's


def beneath(tree: Tree, tokens: list[Token]) -> list[End] | None:
    """The commands a line's words may still say in ``tree``: every one beneath where they go, in the tree's order.

    The flags are split off by the tree's arities, and the words read loosely, as completion reads a line; ``None``
    where a word goes nowhere.
    """
    completer = _Completer(tree, {}, flagging=False)
    words, _, _ = completer._flags(tokens)  # noqa: SLF001 -- the walk is this module's
    walked = completer._walk(words)  # noqa: SLF001 -- the walk is this module's
    return None if walked is None else _ends(walked[0])


def _chained(
    tree: Tree, text: str, tokens: list[Token], names: Mapping[str, Resolver]
) -> tuple[list[Token], _Later | None, _Slots] | None:
    """A chain's last step being typed: its words, where in the tree they start, and the chain's shared slots.

    Where it starts holds where the steps so far have moved the chain. The words as they are, for a line that isn't a
    chain; ``None`` for a chain whose steps so far don't read.
    """
    _, joins = _pieces(tree, tokens)
    if not joins:
        return tokens, None, []
    try:
        before = _Walker(tree, text[: joins[-1].start], names).walk()
    except ReadError:
        return None
    if before.chain is None:  # the `then` is a word of a command that isn't a step
        return tokens, None, []
    shared = _shared(before.chain)
    parts = _head(before.end, shared)[0]
    after = [token for token in tokens if token.start > joins[-1].start]
    moved = None
    for step in before.steps:
        moved = _moved(step, moved)
    later = _Later(_place_of(tree, before.end, parts), shared, before.chain, moved)
    return after, later, _shared_slots(tree, before, parts)


def _shared_slots(tree: Tree, first: Reading, parts: int) -> _Slots:
    """The slots a chain's first step read in its shared part, each with its words.

    A later step's walk holds them before its own, so a name's scope reads from them as it would on one line.
    """
    node, found = tree.top, []
    places = {place.slot: place for place in first.end.places}
    for part in first.end.bound.phrase.parts[:parts]:
        if isinstance(part, Word):
            node = node.words[part.text]
        elif part.name in places:
            edge = cast('Edge', node.slot)
            found.append((edge, first.given[places[part.name].field].words))
            node = edge.node
    return found


def being_typed(text: str) -> tuple[list[Token], Token | None]:
    """A line being typed, up to the cursor: the words before the cursor's, and the word being typed, if one is."""
    tokens = split(text, partial=True)
    typing = bool(tokens) and (text.count('"') % 2 == 1 or not text[-1].isspace())
    return tokens, tokens.pop() if typing else None


@dataclass(slots=True)
class _Completer:
    """One line's completion by a tree; ``moved``, where a chain's steps before the one being typed have moved it."""

    tree: Tree
    names: Mapping[str, Resolver]
    flagging: bool
    moved: _Moved | None = None

    def offers(self, tokens: list[Token], later: _Later | None = None, head: _Slots | None = None) -> list[_Offer]:
        """What may come after ``tokens``, the words before the one being typed.

        From the root, or a chain's place for a later step, with the slots its first step read there.
        """
        if not tokens:
            return [(word, True) for word in (self.tree.root.words if later is None else _onward(later.start, later))]
        words, given, pending = self._flags(tokens)
        walked = self._walk(words, None if later is None else later.start, head or [])
        if walked is None:
            return []
        node, slots, opened = walked
        if pending is not None:
            return self._flag_values(node, pending, slots, given)
        if (
            opened is not None and opened.kind is SlotKind.REST
        ):  # its own next word, or a flag, which may stand anywhere
            return self._rest(opened, slots, given) + self._command_flags(node, given)
        found: list[_Offer] = []
        if opened is not None:  # several words, and more may come
            found += self._values(opened, slots[:-1], given)
        if node.slot is not None:
            found += self._values(node.slot, slots, given)
        found += [(word, True) for word in node.words]
        if node.end is not None and node.end.declaration.chain is not None:
            found.append((THEN, True))  # a step: more may follow it
        return found + self._command_flags(node, given)

    def _flags(self, tokens: list[Token]) -> tuple[list[Token], dict[str, Token | None], str | None]:
        """The words, the flags given (each with its value), and a flag left waiting for its value at the end."""
        words: list[Token] = []
        given: dict[str, Token | None] = {}
        at = 0
        while at < len(tokens):
            token = tokens[at]
            at += 1
            if token.raw == '--':
                words += tokens[at:]
                break
            found = _flag(token, self.tree.shorts)
            if found is None:
                words.append(token)
                continue
            name, value = found
            arity = Arity.SWITCH if name in RESERVED else self.tree.flags.get(name)
            if arity is Arity.VALUE and value is None:
                if at == len(tokens):
                    return words, given, name
                value = tokens[at]
                at += 1
            given[name] = value
        return words, given, None

    def _walk(
        self, words: list[Token], start: Node | None = None, head: _Slots | None = None
    ) -> tuple[Node, _Slots, Edge | None] | None:
        """Where the words go, from the root or ``start``, after the slots ``head`` read before it.

        The node they reach, the slots on the way, and the slot still taking words at the end, if one is.
        """
        node, slots, opened = start or self.tree.root, list(head or []), None
        at = 0
        while at < len(words):
            child = _literal(node, words[at])
            if child is not None:
                node, opened = child, None
                at += 1
                continue
            edge = node.slot
            taken = () if edge is None else _taken(edge.kind, edge.node, words, at)
            if edge is None or not taken:
                return None
            slots.append((edge, taken))
            node = edge.node
            at += len(taken)
            opened = edge if edge.kind is not SlotKind.ONE and at == len(words) else None
        return node, slots, opened

    def _values(self, edge: Edge, before: _Slots, given: Mapping[str, Token | None]) -> list[_Offer]:
        """A slot's values, by the kind each command below it reads the slot by."""
        found: list[_Offer] = []
        for end in _ends(edge.node):
            place = end.places[len(before)]
            kind = end.declaration.kind_of(place)
            found += self._kind(end, kind, _field(end, place.field), before, given)
        return found

    def _rest(self, edge: Edge, slots: _Slots, given: Mapping[str, Token | None]) -> list[_Offer]:
        """The rest of the line's next word: for pairs, a key not yet given, or the last key's values."""
        taken = slots[-1][1]
        found: list[_Offer] = []
        for end in _ends(edge.node):
            kind = end.declaration.kind_of(end.places[len(slots) - 1])
            resolver = self.names.get(kind.category) if isinstance(kind, Pairs) else None
            if resolver is None:
                continue
            scope = self._scope(end, kind, slots, given)
            if len(taken) % 2 == 0:
                keys = {word.text.lower() for word in taken[0::2]}
                found += [(key, False) for key in resolver.options(scope) if key.lower() not in keys]
                continue
            key = _key(resolver, taken[-1].text, scope) or taken[-1].text
            values = cast('PairsResolver', resolver).values(key, scope) if hasattr(resolver, 'values') else None
            found += [] if values is None else [(value, False) for value in values.options(None)]
        return found

    def _flag_values(self, node: Node, name: str, slots: _Slots, given: Mapping[str, Token | None]) -> list[_Offer]:
        """A flag's values, by the kind each command the line may be reads it by."""
        found: list[_Offer] = []
        for end in [node.end] if node.end is not None else _ends(node):
            flag = self.tree.flags_of(end.declaration.cls).get(name)
            if flag is not None:
                kind = end.declaration.field_kinds[flag.field]
                found += self._kind(end, kind, _field(end, flag.field), slots, given)
            elif name in WAIT_FLAGS and end.declaration.can_wait:
                found += _waits(end, name)
        return found

    def _command_flags(self, node: Node, given: Mapping[str, Token | None]) -> list[_Offer]:
        """A whole command's flags not yet given; while a flag is typed, those of every command the line may be."""
        if node.end is not None:
            ends = [node.end]
        elif self.flagging:
            ends = _ends(node)
        else:
            return []
        found: list[_Offer] = []
        for end in ends:
            for name, flag in self.tree.flags_of(end.declaration.cls).items():
                if name not in given or _field(end, flag.field).many:
                    found.append((f'--{name}', True))
            if end.declaration.asks and 'yes' not in given:
                found.append(('--yes', True))
            if end.declaration.can_wait:
                found += [(f'--{name}', True) for name in WAIT_FLAGS if name == 'until' or name not in given]
        return found

    def _kind(
        self, end: End, kind: Kind, field: Field, slots: _Slots, given: Mapping[str, Token | None]
    ) -> list[_Offer]:
        """What a kind offers: its literal words, its own offers, and a named kind's resolver's options."""
        found: list[_Offer] = [(word, True) for word in kind.words]
        found += [(word, False) for word in kind.offers(field)]
        resolver = self.names.get(kind.category) if isinstance(kind, Named) else None
        if resolver is not None:
            found += [(word, False) for word in resolver.options(self._scope(end, kind, slots, given))]
        return found

    def _scope(self, end: End, kind: Kind, slots: _Slots, given: Mapping[str, Token | None]) -> str | None:
        """A named kind's scope, from the words the line gives its field so far, read by its own resolver.

        For a scope that follows its chain, once the chain has moved, where it moved to.
        """
        if not isinstance(kind, Named) or kind.scope is None:
            return None
        if kind.follows and self.moved is not None:
            return self.moved.key
        found = end.declaration
        said = {place.field: (place, words) for place, (_, words) in zip(end.places, slots, strict=False)}
        if kind.scope in said:
            place, words = said[kind.scope]
            text, scope_kind = ' '.join(word.text for word in words), found.kind_of(place)
        else:
            flag = next(
                (f for n, f in self.tree.flags_of(found.cls).items() if f.field == kind.scope and given.get(n)), None
            )
            if flag is None:
                return None
            text, scope_kind = cast('Token', given[flag.name]).text, found.field_kinds[flag.field]
        resolver = self.names.get(scope_kind.category) if isinstance(scope_kind, Name) else None
        return text if resolver is None else _key(resolver, text, None) or text


def _waits(end: End, name: str) -> list[_Offer]:
    """What a wait's flag offers: a condition on each of the reply's fields, ``docked=``; or a few bounds."""
    if name == 'timeout':
        return [(span, False) for span in ('30s', '1m', '2m', '5m')]
    if name == 'count':
        return [(count, False) for count in ('1', '5', '10')]
    reply = end.declaration.reply
    fields = [] if reply is None else reply.__seared_fields__
    return [(f'{spec.wire}=', False) for spec in fields]


def _field(end: End, attr: str) -> Field:
    return next(spec.field for spec in end.declaration.cls.__seared_fields__ if spec.attr == attr)


def _typed(text: str) -> str:
    """A candidate as it would be typed: quoted, when it's empty or holds a space; a double quote in it escaped."""
    return word(text)
