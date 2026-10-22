"""Completion: the words that may come next on a line being typed, as Tab offers them.

``complete(tree, text, names)`` reads the line up to the cursor loosely, as far as its words go, and offers what may
come next, each matching the word being typed, case aside:

- **a slot's values:** its kind's literal words, its own offers (an ``Enum``'s values, ``true`` and ``false``, a few
  spans of time), and for a name, the ``options`` of the resolver for its category, given its scope;
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

from parsed.kinds import Name, Named, Pairs
from parsed.wait import FLAGS as WAIT_FLAGS

from ._terms import RESERVED, Arity, SlotKind
from ._walker import _ends, _flag, _literal, _taken
from ._words import Token, split

if TYPE_CHECKING:
    from collections.abc import Mapping

    from seared import Field

    from parsed.kinds import Kind
    from parsed.names import PairsResolver, Resolver
    from parsed.tree import Edge, End, Node, Tree

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
    found = _Completer(tree, names or {}, flagging=flagging).offers(tokens)
    said = '' if partial is None else partial.text.lower()
    quoted = partial is not None and partial.quoted
    words: list[str] = []
    for word, literal in found:
        typed = _typed(word)
        if (quoted and literal) or typed in words or not word.lower().startswith(said):
            continue
        words.append(typed)
    return Completion(words=words, replace=0 if partial is None else len(text) - partial.start)


def being_typed(text: str) -> tuple[list[Token], Token | None]:
    """A line being typed, up to the cursor: the words before the cursor's, and the word being typed, if one is."""
    tokens = split(text, partial=True)
    typing = bool(tokens) and (text.count('"') % 2 == 1 or not text[-1].isspace())
    return tokens, tokens.pop() if typing else None


@dataclass(slots=True)
class _Completer:
    """One line's completion by a tree."""

    tree: Tree
    names: Mapping[str, Resolver]
    flagging: bool

    def offers(self, tokens: list[Token]) -> list[_Offer]:
        """What may come after ``tokens``, the words before the one being typed."""
        if not tokens:
            return [(word, True) for word in self.tree.root.words]
        words, given, pending = self._flags(tokens)
        walked = self._walk(words)
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
            found = _flag(token)
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

    def _walk(self, words: list[Token]) -> tuple[Node, _Slots, Edge | None] | None:
        """Where the words go: the node, the slots on the way, and the slot still taking words at the end, if one is."""
        node, slots, opened = self.tree.root, [], None
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
            key = resolver.lookup(taken[-1].text, scope) or taken[-1].text
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
        """A named kind's scope, from the words the line gives its field so far, read by its own resolver."""
        if not isinstance(kind, Named) or kind.scope is None:
            return None
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
        return text if resolver is None else resolver.lookup(text, None) or text


def _waits(end: End, name: str) -> list[_Offer]:
    """What a wait's flag offers: a condition on each of the reply's fields, ``docked=``; or a few bounds."""
    if name == 'timeout':
        return [(span, False) for span in ('30s', '1m', '2m', '5m')]
    reply = end.declaration.reply
    fields = [] if reply is None else reply.__seared_fields__
    return [(f'{spec.wire}=', False) for spec in fields]


def _field(end: End, attr: str) -> Field:
    return next(spec.field for spec in end.declaration.cls.__seared_fields__ if spec.attr == attr)


def _typed(word: str) -> str:
    """A candidate as it would be typed: quoted, when it's empty or holds a space."""
    return f'"{word}"' if not word or any(ch.isspace() for ch in word) else word
