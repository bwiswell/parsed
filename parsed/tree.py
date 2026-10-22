"""The tree: every command's phrases, compiled into one trie of words, checked as a whole, and the lines it reads.

A line is read by walking the tree from its root, a word at a time (:mod:`parsed._walk`):

- **a word that is a literal child** of the node takes that branch: a literal beats a slot;
- **else the node's slot** takes it: one word, several (until a word that's a literal after them, or the end), or
  the rest of the line. A node has one slot at most.

A phrase's optional slot is compiled both with it and without it, so where a walk ends, one phrase ends at most, and
which of its slots were read is known.

**Flags** are split off a line before the walk, since they may stand anywhere after the first word, and the walk
doesn't yet know its command. So a flag's name says whether it takes a value, across the whole tree. A flag is its
field's wire name, ``_`` written ``-`` (``for_`` with ``data_key='for'`` is ``--for``); a ``Bool`` flag is a switch,
written ``--no-…`` when its field defaults to ``True``.

**The build refuses** what would make a line read two ways, or a flag mean two things:

- two phrases that end at one node, so read the same lines;
- two kinds of slot at one node (one word, several, the rest of the line);
- a flag that's a switch in one command and takes a value in another;
- two flags of one command with one name, a flag name that isn't lowercase words, and a flag that's one of parsed's
  own (``--help``, ``--json``, ``--yes``, ``--dry-run``).

Every command is declared first (:func:`parsed.command.declaration`), so a tree that builds holds only commands whose
declarations check.

**A line read** (:meth:`Tree.walk`) is a :class:`~parsed._walk.Reading`: the command, and each field's words, read
by its kind to its wire value. A name is read by the resolver the app gives for its category (:mod:`parsed.names`),
or kept as typed. :meth:`Tree.read` goes on to the instance, which seared loads from those values.
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

from seared.doc import collect

from . import _walk
from ._phrase import Word
from ._walk import RESERVED, Arity, Reading, SlotKind
from .command import Command, Declaration, declaration
from .errors import DeclarationError
from .kinds import Switch

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from ._phrase import Bound, Place
    from .names import Resolver

_FLAG = re.compile(r'[a-z0-9][a-z0-9-]*')

_SAID = {SlotKind.ONE: 'one word', SlotKind.MANY: 'several words', SlotKind.REST: 'the rest of the line'}


@dataclass(frozen=True, slots=True)
class Flag:
    """A command's flag.

    Attributes:
        name: Its name on a line, without the dashes.
        field: The field it sets, by attribute name.
        arity: Whether it takes a value.
        negated: Whether it's a ``--no-…`` switch, setting its ``Bool`` field ``False``.
    """

    name: str
    field: str
    arity: Arity
    negated: bool = False


@dataclass(frozen=True, slots=True)
class End:
    """Where a phrase ends: the command, the phrase, and the slots read on the way there, in order.

    An optional slot left out on the way isn't among ``places``; its field keeps its default.
    """

    declaration: Declaration
    bound: Bound
    places: tuple[Place, ...]


@dataclass(slots=True)
class Edge:
    """A node's slot: what it takes, the node after it, and the slot, phrase and command that made it, for messages."""

    kind: SlotKind
    node: Node
    slot: str
    phrase: str
    command: str


@dataclass(slots=True)
class Node:
    """A point in the tree: its literal children, its slot, and the phrase that ends here, if one does."""

    words: dict[str, Node] = field(default_factory=dict)
    slot: Edge | None = None
    end: End | None = None


class Tree:
    """Every command's phrases, compiled into one trie and checked as a whole; the lines it reads (see the module).

    Args:
        commands: The command classes. A base, which has no ``PHRASE``, is left out, and a class given twice counts
            once.

    Raises:
        DeclarationError: A command's declaration doesn't check, two phrases would read a line two ways, or a flag
            would mean two things. The message names the commands and the phrases.
    """

    def __init__(self, commands: Iterable[type]) -> None:
        """Declare each command, compile its phrases, and check the whole."""
        found: dict[type, Declaration] = {}
        for cls in commands:
            if cls not in found:
                found[cls] = declaration(cls)
        self.commands: tuple[Declaration, ...] = tuple(d for d in found.values() if d.is_command)
        self.root = Node()
        self._flags: dict[type, Mapping[str, Flag]] = {}
        arities: dict[str, tuple[Arity, str]] = {}
        for found_declaration in self.commands:
            for bound in found_declaration.phrases:
                for places in _routes(bound):
                    self._insert(found_declaration, bound, places)
            flags = _flags_of(found_declaration)
            self._flags[found_declaration.cls] = flags
            for name, flag in flags.items():
                _check_arity(name, flag.arity, found_declaration.cls.__qualname__, arities)
        self.flags: Mapping[str, Arity] = MappingProxyType({name: arity for name, (arity, _) in arities.items()})

    @classmethod
    def collect(cls, *targets: str) -> Tree:
        """The tree of every command in ``targets``: modules or packages, by name, their submodules included.

        Raises:
            DeclarationError: As the constructor does.
        """
        classes: list[type] = []
        for target in targets:
            importlib.import_module(target)
            classes += [found for found in collect(target) if issubclass(found, Command)]
        return cls(classes)

    def flags_of(self, cls: type) -> Mapping[str, Flag]:
        """A command's flags, by name.

        Raises:
            KeyError: ``cls`` isn't one of the tree's commands.
        """
        return self._flags[cls]

    def walk(self, line: str, names: Mapping[str, Resolver] | None = None) -> Reading:
        """What ``line`` says: the command, and each field's words and wire value, before seared loads them.

        Args:
            line: The line.
            names: The app's resolvers, by category: a ``Name`` of a category with none reads as typed.

        Raises:
            ReadError: The line doesn't read, a word its kind can't read, or a name no resolver answers to; the
                message says why, with the words read up to it.
        """
        return _walk.walk(self, line, names)

    def read(self, line: str, names: Mapping[str, Resolver] | None = None) -> Command:
        """The command ``line`` says, loaded by seared from its fields' values; ``names`` as :meth:`walk` takes it.

        Raises:
            ReadError: As :meth:`walk` does, or a value seared refuses (``'validation'``, at the word that gave it).
        """
        return self.walk(line, names).load()

    def _insert(self, found: Declaration, bound: Bound, places: tuple[Place, ...]) -> None:
        name = found.cls.__qualname__
        node, said = self.root, []
        read = {place.slot: place for place in places}
        for part in bound.phrase.parts:
            if isinstance(part, Word):
                node = node.words.setdefault(part.text, Node())
                said.append(part.text)
                continue
            place = read.get(part.name)
            if place is None:
                continue  # an optional slot, left out on this route
            kind = SlotKind.REST if place.rest else SlotKind.MANY if place.many else SlotKind.ONE
            edge = node.slot
            if edge is None:
                edge = node.slot = Edge(kind=kind, node=Node(), slot=place.slot, phrase=bound.phrase.text, command=name)
            elif edge.kind is not kind:
                msg = (
                    f'after {" ".join(said)!r}, {edge.phrase!r} ({edge.command}) takes {_SAID[edge.kind]} and '
                    f'{bound.phrase.text!r} ({name}) takes {_SAID[kind]}: a line would read two ways'
                )
                raise DeclarationError(msg)
            node = edge.node
            said.append(f'{{{place.slot}}}')
        end = End(declaration=found, bound=bound, places=places)
        if node.end is not None:
            raise DeclarationError(_same_lines(node.end, end))
        node.end = end


def _routes(bound: Bound) -> list[tuple[Place, ...]]:
    """Each way a phrase can be said: every optional slot read, or left out."""
    routes: list[tuple[Place, ...]] = [()]
    for place in bound.places:
        with_it: list[tuple[Place, ...]] = [(*route, place) for route in routes]
        routes = with_it if place.required else [*with_it, *routes]
    return routes


def _same_lines(first: End, second: End) -> str:
    def said(end: End) -> str:
        left = [p.slot for p in end.bound.places if p not in end.places]
        out = ', '.join(f'{{{slot}}}' for slot in left)
        return (
            f'{end.bound.phrase.text!r} ({end.declaration.cls.__qualname__}{", left without " + out if left else ""})'
        )

    return f'{said(first)} and {said(second)} read the same lines'


def flag_name(wire: str, *, negated: bool = False) -> str:
    """A flag's name, from its field's wire name: ``_`` written ``-``, and ``no-…`` for a negated switch."""
    name = wire.replace('_', '-')
    return f'no-{name}' if negated else name


def _flags_of(found: Declaration) -> Mapping[str, Flag]:
    name = found.cls.__qualname__
    specs = {spec.attr: spec for spec in found.cls.__seared_fields__}
    flags: dict[str, Flag] = {}
    for attr in found.flags:
        spec = specs[attr]
        switch = isinstance(found.field_kinds[attr], Switch)
        negated = switch and spec.field.default is True
        flag = flag_name(spec.wire, negated=negated)
        if not _FLAG.fullmatch(flag):
            msg = f'{name}.{attr}: its flag would be --{flag}; a flag is lowercase words, so give it a data_key'
            raise DeclarationError(msg)
        if flag in RESERVED:
            msg = f'{name}.{attr}: --{flag} is a flag parsed takes for every command; give the field another name'
            raise DeclarationError(msg)
        if flag in flags:
            msg = f'{name}: {flags[flag].field} and {attr} are both --{flag}'
            raise DeclarationError(msg)
        flags[flag] = Flag(name=flag, field=attr, arity=Arity.SWITCH if switch else Arity.VALUE, negated=negated)
    return MappingProxyType(flags)


def _check_arity(name: str, arity: Arity, command: str, arities: dict[str, tuple[Arity, str]]) -> None:
    known = arities.get(name)
    if known is None:
        arities[name] = (arity, command)
        return
    if known[0] is not arity:
        said = {Arity.SWITCH: 'is a switch', Arity.VALUE: 'takes a value'}
        msg = (
            f'--{name} {said[known[0]]} in {known[1]} but {said[arity]} in {command}: flags are read before the '
            f'command is, so a name means one thing in a tree'
        )
        raise DeclarationError(msg)
