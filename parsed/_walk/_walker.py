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

**What a walk keeps** is a :class:`Reading`: the command, the phrase, and each field's words and value. A required
flag left out is refused once the command is known. :meth:`Reading.load` hands the values to seared, which checks
them as it checks any, bounds and all.

**A refusal is one** :class:`~parsed.errors.ReadError`, from the walk, a kind or seared alike: what's wrong, with the
words read up to it; where it stands (the word, its column, the field); how to say it, a usage with a ``<slot>`` for
each value (:mod:`._hints`); and what may have been meant, close words or flags, or the words that may come next.
seared's ``ValidationError`` comes back as the word that gave the value.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from seared import ValidationError

from parsed._phrase import Place
from parsed.errors import ReadError

from ._hints import close, either, usage
from ._terms import RESERVED, Arity, SlotKind
from ._words import Token, split

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from seared import Field

    from parsed.command import Command
    from parsed.kinds import Kind
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


def walk(tree: Tree, line: str) -> Reading:
    """Read ``line`` by ``tree``, as the module's docstring describes.

    Raises:
        ReadError: The line doesn't read: an open quote, a flag before the first word or that no command takes, a
            word no command says, a slot left empty, a line that stops short of a command, a flag its command
            doesn't take or a required one it leaves out, or a word its kind can't read.
    """
    return _Walker(tree, line).walk()


@dataclass(slots=True)
class _Walker:
    """One line's walk by a tree, and the refusals it makes."""

    tree: Tree
    line: str

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
        given = self._slots_given(end, slots)
        given.update(self._flags_given(end, flags, words))
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
                raise self._which(edge, said, words[at])
            slots.append(taken)
            said += taken
            node = edge.node
            at += len(taken)
        if node.end is not None:
            return node.end, slots
        if node.slot is not None:
            raise self._which(node.slot, said, None)
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

    def _which(self, edge: Edge, said: list[Token], word: Token | None) -> ReadError:
        """A slot left empty: which value, and the line so far with a ``<slot>`` where it goes."""
        hint = ' '.join([*(token.raw for token in said), f'<{edge.slot}>', *([] if edge.node.end else ['…'])])
        return self.refuse(f'{_said(said)}: which {edge.slot}?', word=word, hint=hint)

    def _usage(self, end: End) -> str:
        fields = {spec.attr: spec.field for spec in end.declaration.cls.__seared_fields__}
        return usage(end.bound, self.tree.flags_of(end.declaration.cls).values(), fields)

    # --- the values --------------------------------------------------------------------------------------------

    def _slots_given(self, end: End, slots: list[tuple[Token, ...]]) -> dict[str, Given]:
        """Each slot's words, read by its kind: one word, a list of them, or the rest of the line, joined."""
        found = end.declaration
        fields = {spec.attr: spec.field for spec in found.cls.__seared_fields__}
        where = end.bound.phrase.text
        given: dict[str, Given] = {}
        for place, words in zip(end.places, slots, strict=True):
            kind, field = found.kind_of(place), fields[place.field]
            if place.rest and not place.many:
                value = self._read(kind, field, _joined(self.line, words), where, place.field)
            else:
                values = [self._read(kind, field, word, where, place.field) for word in words]
                value = values if place.many else values[0]
            given[place.field] = Given(by=place, words=words, value=value)
        return given

    def _flags_given(self, end: End, flags: list[_Said], words: list[Token]) -> dict[str, Given]:
        """Each flag's words, as its field's, once the command is known; a required flag left out is refused."""
        by_name: dict[str, list[_Said]] = defaultdict(list)
        for said in flags:
            by_name[said[0]].append(said)
        found = end.declaration
        takes = self.tree.flags_of(found.cls)
        fields = {spec.attr: spec.field for spec in found.cls.__seared_fields__}
        given: dict[str, Given] = {}
        for name, saids in by_name.items():
            flag = takes.get(name)
            if flag is None:
                raise self._not_taken(end, name, saids[0][1], words)
            kind, field = found.field_kinds[flag.field], fields[flag.field]
            if len(saids) > 1 and (flag.arity is Arity.SWITCH or not field.many):
                msg = f'--{name} is given twice'
                raise self.refuse(msg, word=saids[1][1], field=flag.field)
            tokens = tuple(word for _, token, value in saids for word in (token, value) if word is not None)
            values = [
                self._read(kind, field, value, f'--{name}', flag.field) for _, _, value in saids if value is not None
            ]
            value = (not flag.negated) if flag.arity is Arity.SWITCH else values if field.many else values[0]
            given[flag.field] = Given(by=flag, words=tokens, value=value)
        for flag in takes.values():
            if fields[flag.field].required and flag.field not in given:
                said = f'{self.line.strip()} --{flag.name}'  # the line as given, the flag added
                hint = said if flag.arity is Arity.SWITCH else f'{said} <{flag.name}>'
                msg = f'{_said(words)} needs --{flag.name}'
                raise self.refuse(msg, field=flag.field, hint=hint)
        return given

    def _not_taken(self, end: End, name: str, token: Token, words: list[Token]) -> ReadError:
        """A flag its command doesn't take, with its usage, and its own flags close to the one given."""
        hint = self._usage(end)
        near = [f'--{found}' for found in close(name, self.tree.flags_of(end.declaration.cls))]
        return self.refuse(f'{_said(words)} takes no --{name}', word=token, hint=hint, near=near)

    def _read(self, kind: Kind, field: Field, word: Token, where: str, attr: str) -> object:
        """A word, read by its field's kind; a word it can't read is refused, saying where it stands."""
        try:
            return kind.read(word.text, field)
        except ValueError as e:
            msg = f'{where}: {e}'
            raise self.refuse(msg, word=word, field=attr) from None


def _flag(token: Token) -> tuple[str, Token | None] | None:
    """A flag's name and the value it gives after ``=``, if ``token`` is one: ``--`` and a name, outside quotes."""
    head, eq, _ = token.raw.partition('=')
    if not head.startswith('--') or len(head) == len('--') or '"' in head:
        return None
    if not eq:
        return head[2:].lower(), None
    at = len(head) + 1  # the head has no quotes, so the text and the raw word agree up to the `=`
    return head[2:].lower(), Token(text=token.text[at:], start=token.start + at, raw=token.raw[at:])


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
