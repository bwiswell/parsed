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
``1h30m`` to ``5400.0`` seconds, ``Iron`` to an ``Enum``'s ``'iron'``. A word its kind can't read is refused here,
naming the phrase or the flag.

**A name is read by the resolver the app gives for its category** (:mod:`parsed.names`), or kept as typed when it
gives none. A scoped name waits for its scope: the fields are read in an order that puts a scope before the names it
narrows, whatever their order on the line, and the resolver is given the scope's value. A word no name answers to is
refused with the resolver's suggestions.

**What a walk keeps** is a :class:`Reading`: the command, the phrase, and each field's words and value. A required
flag left out is refused once the command is known. :meth:`Reading.load` hands the values to seared, which checks
them as it checks any, bounds and all.

**A refusal is one** :class:`~parsed.errors.ReadError`, from the walk, a kind or seared alike: what's wrong, with the
words read up to it; where it stands (the word, its column, the field); how to say it, a usage with a ``<slot>`` for
each value (:mod:`._hints`); and what may have been meant, close words or flags, or the words that may come next.
seared's ``ValidationError`` comes back as the word that gave the value.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, NamedTuple, cast

from seared import ValidationError

from parsed._phrase import Place, Slot
from parsed.errors import ReadError
from parsed.kinds import NOT_LITERAL, Name, Named, Pairs

from ._hints import close, either, usage
from ._terms import RESERVED, Arity, SlotKind
from ._words import Token, split

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from seared import Field

    from parsed.command import Command
    from parsed.kinds import Kind
    from parsed.names import PairsResolver, Resolver
    from parsed.tree import Edge, End, Flag, Node, Tree


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
        line: The line read.
    """

    end: End
    given: Mapping[str, Given]
    own: frozenset[str]
    line: str

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
            ReadError: A value seared refuses, out of its field's bounds or pattern: a ``'validation'`` error at the
                word that gave it, with seared's ``ValidationError`` as its cause.
        """
        try:
            return self.command.load(self.data(), unknown='raise')
        except ValidationError as e:
            raise _refused(self, e) from e


#: A flag as the line gives it: its name, its own word, and its value's word, if it takes one.
type _Said = tuple[str, Token, Token | None]


#: A placeholder: ``<name>``, standing for any value in a line that's checked, not run.
_PLACEHOLDER = re.compile(r'<[^<>\s]+>')

#: A name's scope, once read: the field it is, its value as the resolver is given it, and its words as typed.
type _Scope = tuple[str, str, str]


def walk(tree: Tree, line: str, names: Mapping[str, Resolver] | None = None, *, placeholders: bool = False) -> Reading:
    """Read ``line`` by ``tree``, as the module's docstring describes, its names by ``names``' resolvers.

    With ``placeholders``, a word written ``<name>`` (unquoted) stands for any value: it fills its slot or flag as
    it is, read by no kind or resolver, so a line from help or a hint checks its shape. Its reading won't load.

    Raises:
        ReadError: The line doesn't read: an open quote, a flag before the first word or that no command takes, a
            word no command says, a slot left empty, a line that stops short of a command, a flag its command
            doesn't take or a required one it leaves out, a word its kind can't read, or a name no resolver
            answers to.
    """
    return _Walker(tree, line, names or {}, placeholders=placeholders).walk()


class _Field(NamedTuple):  # a tuple: one is made for each field of each line, and a tuple is the cheapest to make
    """A field as the line gives it, before its value is read.

    Attributes:
        by: The slot or the flag that took its words.
        words: Every word that went into it, for :class:`Given`.
        values: The words its value is read from, one for each of a list's values; none for a switch. The rest of
            the line, for a field that isn't a list, is one word.
        kind: The kind they're read by.
        field: The seared field.
        where: The phrase, or the flag, for a refusal to name.
        end: Where the walk ended, for a refusal's usage.
    """

    by: Place | Flag
    words: tuple[Token, ...]
    values: tuple[Token, ...]
    kind: Kind
    field: Field
    where: str
    end: End


@dataclass(slots=True)
class _Walker:
    """One line's walk by a tree, and the refusals it makes."""

    tree: Tree
    line: str
    names: Mapping[str, Resolver]
    placeholders: bool = False

    def walk(self) -> Reading:
        tokens = split(self.line)
        if tokens and _flag(tokens[0]) is not None:
            msg = f'{tokens[0].raw} comes before a command: a flag follows the first word'
            raise self.refuse(msg, word=tokens[0])
        words, flags, own = self._split_flags(tokens)
        if not words:
            msg = 'no command: the line has no words'
            raise self.refuse(msg, suggestions=list(self.tree.root.words))
        end, slots = self._walk_words(words)
        specs = {spec.attr: spec.field for spec in end.declaration.cls.__seared_fields__}
        fields = {**self._slot_fields(end, slots, specs), **self._flag_fields(end, flags, words, specs)}
        values = self._values(fields)
        given = {attr: Given(by=found.by, words=found.words, value=values[attr]) for attr, found in fields.items()}
        return Reading(end=end, given=MappingProxyType(given), own=frozenset(own), line=self.line)

    def refuse(  # noqa: PLR0913 -- one refusal, its parts named
        self,
        what: str,
        *,
        word: Token | None = None,
        field: str | None = None,
        hint: str | None = None,
        near: Sequence[str] = (),
        suggestions: Sequence[str] = (),
    ) -> ReadError:
        """A refusal at ``word``, or at the line's end where a word is missing.

        Its text is ``what``, then a did-you-mean for ``near``, then the hint; ``near`` is its suggestions, unless
        ``suggestions`` gives others, the words that may come next, which ``what`` says itself.
        """
        return ReadError(
            _text(what, near=near, hint=hint),
            line=self.line,
            column=len(self.line) if word is None else word.start,
            word=None if word is None else word.raw,
            field=field,
            hint=hint,
            suggestions=near or suggestions,
        )

    # --- the flags ---------------------------------------------------------------------------------------------

    def _split_flags(self, tokens: list[Token]) -> tuple[list[Token], list[_Said], set[str]]:
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
                self._own(name, token, value, own)
                continue
            arity = self._arity(name, token)
            if arity is Arity.SWITCH and value is not None:
                msg = f'--{name} takes nothing after it'
                raise self.refuse(msg, word=token)
            if arity is Arity.VALUE and value is None:
                if at == len(tokens) or tokens[at].raw == '--' or _flag(tokens[at]) is not None:
                    msg = f'--{name} needs a value'
                    raise self.refuse(msg, word=token, hint=f'--{name} <{name}>')
                value = tokens[at]
                at += 1
            flags.append((name, token, value))
        return words, flags, own

    def _arity(self, name: str, token: Token) -> Arity:
        """Whether a flag takes a value, as the tree says; a flag no command takes is refused, with those close."""
        arity = self.tree.flags.get(name)
        if arity is None:
            near = [f'--{found}' for found in close(name, [*self.tree.flags, *RESERVED])]
            msg = f'no command takes --{name}'
            raise self.refuse(msg, word=token, near=near)
        return arity

    def _own(self, name: str, token: Token, value: Token | None, own: set[str]) -> None:
        if value is not None:
            msg = f'--{name} takes nothing after it'
            raise self.refuse(msg, word=token)
        if name in own:
            msg = f'--{name} is given twice'
            raise self.refuse(msg, word=token)
        own.add(name)

    # --- the words ---------------------------------------------------------------------------------------------

    def _walk_words(self, words: list[Token]) -> tuple[End, list[tuple[Token, ...]]]:
        """Walk the words from the root: where they end, and each slot's words on the way, in order."""
        node, said = self.tree.root, []
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
                raise self._unknown(node, said, words[at])
            taken = _taken(edge.kind, edge.node, words, at)
            if not taken:
                raise self._which(edge, said, words[at], len(slots))
            slots.append(taken)
            said += taken
            node = edge.node
            at += len(taken)
        if node.end is not None:
            return node.end, slots
        if node.slot is not None:
            raise self._which(node.slot, said, None, len(slots))
        words_next = list(node.words)
        msg = f'{_said(said)}: then what? {" | ".join(words_next)}'
        raise self.refuse(msg, suggestions=words_next)

    def _unknown(self, node: Node, said: list[Token], word: Token) -> ReadError:
        """A word no command says here: one left over after a command, or one the node has no branch for."""
        if node.end is not None and not node.words:
            hint = self._usage(node.end)
            return self.refuse(f'{_said(said)}: {word.raw!r} is left over', word=word, hint=hint)
        asked = _said([*said, word])
        near = close(word.text.lower(), node.words)
        if near:
            return self.refuse(f'no command {asked!r}', word=word, near=near)
        words_next = list(node.words)
        return self.refuse(f'no command {asked!r}: {" | ".join(words_next)}', word=word, suggestions=words_next)

    def _which(self, edge: Edge, said: list[Token], word: Token | None, before: int) -> ReadError:
        """A slot left empty: which value, and the line so far with the rest of how it's said.

        Where one command lies past the slot, the hint is the rest of its usage, flags and all; where several do, the
        slot's ``<…>``, and ``…`` if more must follow. ``before`` counts the slots the line has given.
        """
        past = {(end.declaration.cls, end.bound.phrase.text): end for end in _ends(edge.node)}
        if len(past) == 1:
            end = next(iter(past.values()))
            name = end.places[before].slot
            parts = end.bound.phrase.parts
            start = next(at for at, part in enumerate(parts) if isinstance(part, Slot) and part.name == name)
            fields = {spec.attr: spec.field for spec in end.declaration.cls.__seared_fields__}
            flags = self.tree.flags_of(end.declaration.cls).values()
            rest = [usage(end.bound, flags, fields, start=start)]
        else:
            rest = [f'<{edge.slot}>', *([] if edge.node.end else ['…'])]
        hint = ' '.join([*(token.raw for token in said), *rest])
        return self.refuse(f'{_said(said)}: which {edge.slot}?', word=word, hint=hint)

    def _usage(self, end: End) -> str:
        """How the command at ``end`` is said, the tree's prefix first."""
        fields = {spec.attr: spec.field for spec in end.declaration.cls.__seared_fields__}
        said = usage(end.bound, self.tree.flags_of(end.declaration.cls).values(), fields)
        return f'{self.tree.under} {said}' if self.tree.under else said

    # --- the values --------------------------------------------------------------------------------------------

    def _slot_fields(self, end: End, slots: list[tuple[Token, ...]], fields: Mapping[str, Field]) -> dict[str, _Field]:
        """Each slot's words, as its field's: one word, several, or the rest of the line, joined."""
        found = end.declaration
        out: dict[str, _Field] = {}
        for place, words in zip(end.places, slots, strict=True):
            kind = found.kind_of(place)
            joined = place.rest and not place.many and not isinstance(kind, Pairs)
            out[place.field] = _Field(
                by=place,
                words=words,
                values=(_joined(self.line, words),) if joined else words,
                kind=kind,
                field=fields[place.field],
                where=end.bound.phrase.text,
                end=end,
            )
        return out

    def _flag_fields(
        self, end: End, flags: list[_Said], words: list[Token], fields: Mapping[str, Field]
    ) -> dict[str, _Field]:
        """Each flag's words, as its field's, once the command is known; a required flag left out is refused."""
        by_name: dict[str, list[_Said]] = defaultdict(list)
        for said in flags:
            by_name[said[0]].append(said)
        found = end.declaration
        takes = self.tree.flags_of(found.cls)
        out: dict[str, _Field] = {}
        for name, saids in by_name.items():
            flag = takes.get(name)
            if flag is None:
                raise self._not_taken(end, name, saids[0][1], words)
            field = fields[flag.field]
            if len(saids) > 1 and (flag.arity is Arity.SWITCH or not field.many):
                msg = f'--{name} is given twice'
                raise self.refuse(msg, word=saids[1][1], field=flag.field)
            out[flag.field] = _Field(
                by=flag,
                words=tuple(word for _, token, value in saids for word in (token, value) if word is not None),
                values=tuple(value for _, _, value in saids if value is not None),
                kind=found.field_kinds[flag.field],
                field=field,
                where=f'--{name}',
                end=end,
            )
        for flag in takes.values():
            if fields[flag.field].required and flag.field not in out:
                said = f'{self.line.strip()} --{flag.name}'  # the line as given, the flag added
                hint = said if flag.arity is Arity.SWITCH else f'{said} <{flag.name}>'
                msg = f'{_said(words)} needs --{flag.name}'
                raise self.refuse(msg, field=flag.field, hint=hint)
        return out

    def _not_taken(self, end: End, name: str, token: Token, words: list[Token]) -> ReadError:
        """A flag its command doesn't take, with its usage, and its own flags close to the one given."""
        hint = self._usage(end)
        near = [f'--{found}' for found in close(name, self.tree.flags_of(end.declaration.cls))]
        return self.refuse(f'{_said(words)} takes no --{name}', word=token, hint=hint, near=near)

    def _values(self, fields: Mapping[str, _Field]) -> dict[str, object]:
        """Each field's value, a name's scope read before it; a switch's is ``True``, or ``False`` for ``--no-…``."""
        values: dict[str, object] = {}

        def read(attr: str) -> None:
            found = fields[attr]
            scope = found.kind.scope if isinstance(found.kind, Named) else None
            if scope is not None and scope in fields and scope not in values:
                read(scope)  # a declaration refuses scopes that go round, so this ends
            if not isinstance(found.by, Place) and found.by.arity is Arity.SWITCH:
                values[attr] = not found.by.negated
                return
            read_scope = None if scope is None else self._scope(scope, fields, values)
            if isinstance(found.kind, Pairs):
                values[attr] = self._pairs(found, found.kind, read_scope)
            elif found.field.many:
                values[attr] = [self._read(found, word, read_scope) for word in found.values]
            else:
                values[attr] = self._read(found, found.values[0], read_scope)

        for attr in fields:
            if attr not in values:
                read(attr)
        return values

    def _scope(self, scope: str | None, fields: Mapping[str, _Field], values: Mapping[str, object]) -> _Scope | None:
        """A name's scope, once its field is read; ``None`` when it has none, or the line leaves it out."""
        value = values.get(scope) if scope is not None else None
        if scope is None or value is None or isinstance(value, list):
            return None
        return scope, str(value), _said(fields[scope].values)

    def _read(self, found: _Field, word: Token, scope: _Scope | None) -> object:
        """A word, read by its field's kind, or a name by the resolver for its category; refused where it can't be."""
        if self.placeholders and _placeholder(word):
            return word.text
        kind = found.kind
        resolver = self.names.get(kind.category) if self.names and isinstance(kind, Name) else None
        if not isinstance(kind, Name) or resolver is None:
            try:
                return kind.read(word.text, found.field, quoted=word.quoted)
            except ValueError as e:
                msg = f'{found.where}: {e}'
                raise self.refuse(msg, word=word, field=found.by.field) from None
        literal = NOT_LITERAL if word.quoted else kind.literal(word.text)
        if literal is not NOT_LITERAL:
            return literal
        return self._resolved(found, resolver, word, scope, kind.category)

    def _pairs(self, found: _Field, kind: Pairs, scope: _Scope | None) -> dict[str, object]:
        """A keyed field's pairs: each key read by its category's resolver, each value by the one it gives the key."""
        words = found.values
        if len(words) % 2:
            msg = f'{found.where}: {words[-1].raw!r} and its value? pairs come in twos'
            raise self.refuse(msg, word=words[-1], field=found.by.field, hint=self._usage(found.end))
        resolver = self.names.get(kind.category)
        if resolver is not None and not callable(getattr(resolver, 'values', None)):
            msg = f'the resolver for {kind.category} reads pairs, so it gives values(key, scope): a PairsResolver'
            raise TypeError(msg)
        given = None if scope is None else scope[1]
        out: dict[str, object] = {}
        for key_word, value_word in zip(words[0::2], words[1::2], strict=True):
            key = key_word.text if resolver is None else self._resolved(found, resolver, key_word, scope, kind.category)
            if key in out:
                msg = f'{found.where}: {key_word.raw} is given twice'
                raise self.refuse(msg, word=key_word, field=found.by.field)
            of = None if resolver is None else cast('PairsResolver', resolver).values(key, given)
            # A value's resolver is given no scope: the pairs' gave it knowing the key and the scope.
            out[key] = value_word.text if of is None else self._resolved(found, of, value_word, None, key_word.raw)
        return out

    def _resolved(self, found: _Field, resolver: Resolver, word: Token, scope: _Scope | None, what: str) -> str:
        """The key a resolver reads a word to; a word no name answers to is refused, with what's close to it."""
        if self.placeholders and _placeholder(word):
            return word.text
        given = None if scope is None else scope[1]
        key = resolver.lookup(word.text, given)
        if key is not None:
            return key
        near = list(resolver.suggest(word.text, given))
        within = '' if scope is None else f' for {scope[0]} {scope[2]!r}'
        msg = f'{found.where}: no {what} {word.text!r}{within}'  # its text: a name may be quoted for its spaces
        raise self.refuse(msg, word=word, field=found.by.field, hint=self._usage(found.end), near=near)


def _flag(token: Token) -> tuple[str, Token | None] | None:
    """A flag's name and the value it gives after ``=``, if ``token`` is one: ``--`` and a name, outside quotes."""
    head, eq, _ = token.raw.partition('=')
    if not head.startswith('--') or len(head) == len('--') or '"' in head:
        return None
    if not eq:
        return head[2:].lower(), None
    at = len(head) + 1  # the head has no quotes, so the text and the raw word agree up to the `=`
    return head[2:].lower(), Token(text=token.text[at:], start=token.start + at, raw=token.raw[at:])


def _ends(node: Node) -> list[End]:
    """Every command the walk may still end at, from ``node``: its own first, then those below it, in order."""
    found = [node.end] if node.end is not None else []
    for child in node.words.values():
        found += _ends(child)
    if node.slot is not None:
        found += _ends(node.slot.node)
    return found


def _placeholder(word: Token) -> bool:
    """Whether a word is a placeholder, ``<name>``, unquoted: one standing for any value."""
    return not word.quoted and _PLACEHOLDER.fullmatch(word.text) is not None


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


def _joined(line: str, words: Sequence[Token]) -> Token:
    """The rest of the line as one word: its words joined by single spaces, from the first one's start."""
    start, last = words[0].start, words[-1]
    raw = line[start : last.start + len(last.raw)]
    return Token(text=' '.join(word.text for word in words), start=start, raw=raw)


def _said(words: Sequence[Token]) -> str:
    return ' '.join(word.raw for word in words)


def _text(what: str, *, near: Sequence[str] = (), hint: str | None = None) -> str:
    """A refusal's text for people: what's wrong, then any did-you-mean, then the hint."""
    if near:
        what = f'{what}; did you mean {either(near)}?'
    return f'{what} `{hint}`' if hint else what


def _refused(reading: Reading, error: ValidationError) -> ReadError:
    """A value seared refused, as the word that gave it: its slot's phrase or its flag, and seared's reason."""
    wires = {spec.wire: spec.attr for spec in reading.command.__seared_fields__}
    head = error.path[0] if error.path else None
    attr = wires.get(head) if isinstance(head, str) else None
    given = reading.given.get(attr) if attr is not None else None
    if given is None:
        message = f'{reading.end.bound.phrase.text}: {error.reason}'
        return ReadError(message, kind='validation', line=reading.line, column=len(reading.line), field=attr)
    if isinstance(given.by, Place):
        where = reading.end.bound.phrase.text
        words = (_joined(reading.line, given.words),) if given.by.rest and not given.by.many else given.words
    else:
        where = f'--{given.by.name}'
        words = given.words[1::2] if given.by.arity is Arity.VALUE else given.words
    index = error.path[1] if len(error.path) > 1 and isinstance(error.path[1], int) else 0
    word = words[index] if index < len(words) else words[0]
    return ReadError(
        f'{where}: {error.reason}',
        kind='validation',
        line=reading.line,
        column=word.start,
        word=word.raw,
        field=attr,
    )
