"""Reading a line by a tree: its flags split off, its words walked from the root, each field's words kept.

**The flags first.** A word that begins with ``--`` outside quotes is a flag, anywhere after the line's first word:

- **its name is lowercased,** and ``--name=value`` gives its value in the same word (``--label="north dock"``);
- **whether it takes a value is the tree's to say** (:attr:`parsed.tree.Tree.flags`), since the walk doesn't know
  its command yet: a switch takes no value, and any other flag takes the word after it;
- **parsed's own** (``--help``, ``--json``, ``--yes``, ``--dry-run``) are switches every command takes;
- **``--`` ends the flags:** every word after it is a word, ``--`` and all.

**Then the words,** from the root, as :mod:`parsed.tree` describes: a word that is a literal child takes that branch
(case aside, and never a quoted word), else the node's slot takes it. A slot of several words takes them up to a
literal after them, or the end; the rest of the line takes every word left.

**Each word is read by its field's kind** (:mod:`parsed.kinds`) to the field's wire value: ``1,000`` to ``1000``,
``1h30m`` to ``5400.0`` seconds, ``Iron`` to an ``Enum``'s ``'iron'``. A name is kept as typed. A word its kind can't
read is refused here, naming the phrase or the flag.

**What a walk keeps** is a :class:`Reading`: the command, the phrase, and each field's words and value.
:meth:`Reading.load` hands the values to seared, which checks them as it checks any, bounds and all.
"""

from __future__ import annotations

import enum
from collections import defaultdict
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from parsed.errors import ReadError

from ._words import Token, split

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from seared import Field

    from parsed._phrase import Place
    from parsed.command import Command
    from parsed.kinds import Kind
    from parsed.tree import End, Flag, Node, Tree

#: Flags parsed takes for itself on every command, which no field may be named for.
RESERVED = ('help', 'json', 'yes', 'dry-run')


class SlotKind(enum.StrEnum):
    """What a slot takes."""

    ONE = 'one'  # one word
    MANY = 'many'  # one word or more, until a literal after them or the end
    REST = 'rest'  # the rest of the line


class Arity(enum.StrEnum):
    """Whether a flag takes a value."""

    SWITCH = 'switch'  # given or not: --loud
    VALUE = 'value'  # the word after it, or after `=`: --for 10m, --for=10m


@dataclass(frozen=True, slots=True)
class Given:
    """A field's words on a line.

    Attributes:
        by: The slot (a :class:`~parsed._phrase.Place`) or the flag (a :class:`~parsed.tree.Flag`) that took them.
        words: Every word that went into it, in the line's order: a slot's words, or a flag and its value.
        value: What seared loads for the field: each word read by the field's kind, a list of them for a ``many``
            field, or a switch's ``True`` or ``False``.
    """

    by: Place | Flag
    words: tuple[Token, ...]
    value: object

    @property
    def field(self) -> str:
        """The field it fills, by attribute name."""
        return self.by.field


@dataclass(frozen=True, slots=True)
class Reading:
    """A line, read: the command it says, and each field's words and wire value, before seared loads them.

    Attributes:
        end: Where the walk ended: the command, the phrase, and the slots read.
        given: Each field the line gives, by attribute name: its slots in the phrase's order, then its flags in the
            line's. A field the line leaves out isn't here, and keeps its default.
        own: parsed's own flags the line gives, by name (``yes``, ``json``, …), for whatever runs the command.
    """

    end: End
    given: Mapping[str, Given]
    own: frozenset[str]

    @property
    def command(self) -> type[Command]:
        """The command the line says."""
        return self.end.declaration.cls

    def data(self) -> dict[str, object]:
        """The fields' values by wire name, as seared's ``load`` takes them."""
        wires = {spec.attr: spec.wire for spec in self.command.__seared_fields__}
        return {wires[attr]: given.value for attr, given in self.given.items()}

    def load(self) -> Command:
        """The command, loaded by seared from :meth:`data`, any key it doesn't know refused.

        Raises:
            ValidationError: A value out of its field's bounds or pattern, or a required field the line leaves out.
        """
        return self.command.load(self.data(), unknown='raise')


#: A flag as the line gives it: its name, its own word, and its value's word, if it takes one.
type _Said = tuple[str, Token, Token | None]


def walk(tree: Tree, line: str) -> Reading:
    """Read ``line`` by ``tree``, as the module's docstring describes.

    Raises:
        ReadError: The line doesn't read: an open quote, a flag before the first word or that no command takes, a
            word no command says, a slot left empty, a line that stops short of a command, or a flag its command
            doesn't take. The message says which, with the words read up to it.
    """
    tokens = split(line)
    if tokens and _flag(tokens[0]) is not None:
        msg = f'{tokens[0].raw} comes before a command: a flag follows the first word'
        raise ReadError(msg)
    words, flags, own = _split_flags(tokens, tree.flags)
    if not words:
        msg = 'no command: the line has no words'
        raise ReadError(msg)
    end, slots = _walk_words(tree.root, words)
    given = _slots_given(end, slots)
    given.update(_flags_given(end, flags, tree.flags_of(end.declaration.cls)))
    return Reading(end=end, given=MappingProxyType(given), own=frozenset(own))


def _flag(token: Token) -> tuple[str, Token | None] | None:
    """A flag's name and the value it gives after ``=``, if ``token`` is one: ``--`` and a name, outside quotes."""
    head, eq, _ = token.raw.partition('=')
    if not head.startswith('--') or len(head) == len('--') or '"' in head:
        return None
    if not eq:
        return head[2:].lower(), None
    at = len(head) + 1  # the head has no quotes, so the text and the raw word agree up to the `=`
    return head[2:].lower(), Token(text=token.text[at:], start=token.start + at, raw=token.raw[at:])


def _split_flags(tokens: list[Token], arities: Mapping[str, Arity]) -> tuple[list[Token], list[_Said], set[str]]:
    """Split the flags off a line's words: the words left, each field's flag as given, and parsed's own given."""
    words: list[Token] = []
    flags: list[_Said] = []
    own: set[str] = set()
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
        if name in RESERVED:
            _own(name, value, own)
            continue
        if arities.get(name) is None:
            msg = f'no command takes --{name}'
            raise ReadError(msg)
        if arities[name] is Arity.SWITCH and value is not None:
            msg = f'--{name} takes nothing after it'
            raise ReadError(msg)
        if arities[name] is Arity.VALUE and value is None:
            if at == len(tokens) or tokens[at].raw == '--' or _flag(tokens[at]) is not None:
                msg = f'--{name} needs a value'
                raise ReadError(msg)
            value = tokens[at]
            at += 1
        flags.append((name, token, value))
    return words, flags, own


def _own(name: str, value: Token | None, own: set[str]) -> None:
    if value is not None:
        msg = f'--{name} takes nothing after it'
        raise ReadError(msg)
    if name in own:
        msg = f'--{name} is given twice'
        raise ReadError(msg)
    own.add(name)


def _walk_words(root: Node, words: list[Token]) -> tuple[End, list[tuple[Token, ...]]]:
    """Walk the words from the root: where they end, and each slot's words on the way, in order."""
    node, said = root, []
    slots: list[tuple[Token, ...]] = []
    at = 0
    while at < len(words):
        child = _literal(node, words[at])
        if child is not None:
            node = child
            said.append(words[at])
            at += 1
            continue
        edge = node.slot
        if edge is None:
            raise ReadError(_unknown(node, said, words[at]))
        taken = _taken(edge.kind, edge.node, words, at)
        if not taken:
            msg = f'{_said(said)}: which {edge.slot}?'
            raise ReadError(msg)
        slots.append(taken)
        said += taken
        node = edge.node
        at += len(taken)
    if node.end is None:
        raise ReadError(_unfinished(node, said))
    return node.end, slots


def _literal(node: Node, word: Token) -> Node | None:
    """The literal child a word is, if it is one: case aside, and never a quoted word."""
    return None if word.quoted else node.words.get(word.text.lower())


def _taken(kind: SlotKind, after: Node, words: list[Token], at: int) -> tuple[Token, ...]:
    """The words a slot takes, from ``at``: one, those up to a literal of the node after it, or the rest."""
    if kind is SlotKind.ONE:
        return (words[at],)
    if kind is SlotKind.REST:
        return tuple(words[at:])
    stop = at
    while stop < len(words) and _literal(after, words[stop]) is None:
        stop += 1
    return tuple(words[at:stop])


def _said(words: Sequence[Token]) -> str:
    return ' '.join(word.raw for word in words)


def _unknown(node: Node, said: list[Token], word: Token) -> str:
    if not node.words:  # where a phrase ends, with nothing after it
        return f'{_said(said)}: {word.raw!r} is left over'
    return f'no command {_said([*said, word])!r}'


def _unfinished(node: Node, said: list[Token]) -> str:
    if node.slot is not None:
        return f'{_said(said)}: which {node.slot.slot}?'
    return f'{_said(said)}: then what? {" | ".join(node.words)}'


def _slots_given(end: End, slots: list[tuple[Token, ...]]) -> dict[str, Given]:
    """Each slot's words, read by its kind: one word, a list of them, or the rest of the line, joined."""
    found = end.declaration
    fields = {spec.attr: spec.field for spec in found.cls.__seared_fields__}
    where = end.bound.phrase.text
    given: dict[str, Given] = {}
    for place, words in zip(end.places, slots, strict=True):
        kind, field = found.kind_of(place), fields[place.field]
        if place.rest and not place.many:
            value = _read(kind, ' '.join(word.text for word in words), field, where)
        else:
            values = [_read(kind, word.text, field, where) for word in words]
            value = values if place.many else values[0]
        given[place.field] = Given(by=place, words=words, value=value)
    return given


def _flags_given(end: End, flags: list[_Said], takes: Mapping[str, Flag]) -> dict[str, Given]:
    """Each flag's words, as its field's, once the command is known: a switch's ``bool``, or a value's word."""
    by_name: dict[str, list[_Said]] = defaultdict(list)
    for said in flags:
        by_name[said[0]].append(said)
    found = end.declaration
    fields = {spec.attr: spec.field for spec in found.cls.__seared_fields__}
    given: dict[str, Given] = {}
    for name, saids in by_name.items():
        flag = takes.get(name)
        if flag is None:
            named = ', '.join(f'--{taken}' for taken in takes) or 'no flags'
            msg = f'{end.bound.phrase.text} takes {named}, not --{name}'
            raise ReadError(msg)
        kind, field = found.field_kinds[flag.field], fields[flag.field]
        if len(saids) > 1 and (flag.arity is Arity.SWITCH or not field.many):
            msg = f'--{name} is given twice'
            raise ReadError(msg)
        words = tuple(word for _, token, value in saids for word in (token, value) if word is not None)
        values = [_read(kind, value.text, field, f'--{name}') for _, _, value in saids if value is not None]
        if flag.arity is Arity.SWITCH:
            given[flag.field] = Given(by=flag, words=words, value=not flag.negated)
        else:
            given[flag.field] = Given(by=flag, words=words, value=values if field.many else values[0])
    return given


def _read(kind: Kind, text: str, field: Field, where: str) -> object:
    """A word, read by its field's kind; a word it can't read is refused, saying where it stands."""
    try:
        return kind.read(text, field)
    except ValueError as e:
        msg = f'{where}: {e}'
        raise ReadError(msg) from None
