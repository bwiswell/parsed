"""Reading a line by a tree: its flags split off, its words walked from the root, each field's words kept.

**The flags first.** A word that begins with ``--`` outside quotes is a flag, anywhere after the line's first word,
and parsed's own anywhere at all:

- **its name is lowercased,** and ``--name=value`` gives its value in the same word (``--label="north dock"``);
- **a short flag** (``-c``) is one letter after ``-``, where a command's ``SHORTS`` gives it one: it says its flag,
  on the commands that declare it, and takes a value as its flag does. ``-h`` is ``--help``'s; any other ``-x`` is a
  word;
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
refused by the kind's term (its label, or else its category), with the resolver's suggestions; or with its reason,
where its ``lookup`` raises a ``ValueError`` saying why.

**A chain's place moves on** with each step that declares ``MOVES``: after ``jump sol``, the fleet will be at
``sol``. A later step's name whose scope follows the chain (``follows=True``) is given that place as its scope, or
none where a step moved it somewhere the line doesn't say.

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
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, NamedTuple, cast

from seared import ValidationError

from parsed._phrase import Place, Slot, Word
from parsed.errors import ReadError
from parsed.kinds import NOT_LITERAL, Name, Named, Pairs, span
from parsed.wait import FLAGS as WAIT_FLAGS
from parsed.wait import TIMEOUT, Condition, Wait, problem

from ._hints import close, either, plain_slot, usage
from ._terms import HELP, HELP_SHORT, RESERVED, THEN, Arity, SlotKind
from ._words import Token, split

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from seared import Field, Seared

    from parsed._phrase import Bound
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
        wait: Its wait, when it gives ``--until`` on a command that can wait: the conditions and the bound.
        then: A chain's steps after this one, each a reading of its own, in the line's order; none for a line of
            one command. Each holds the chain's shared fields too, as its first step gave them.
        words: The words the command is said in, as the line gives them, its flags aside; a chain's later step's
            with the line before it.
    """

    end: End
    given: Mapping[str, Given]
    own: frozenset[str]
    line: str
    wait: Wait | None = None
    then: tuple[Reading, ...] = ()
    words: tuple[Token, ...] = ()

    @property
    def said(self) -> str:
        """The command as the line says it, its flags aside, for a message to name it: ``fleets show f1``."""
        return _said(self.words)

    @property
    def command(self) -> type[Command]:
        """The command the line says: a chain's first step."""
        return self.end.declaration.cls

    @property
    def chain(self) -> type[Command] | None:
        """The chain's base, when the command is a step; ``None`` otherwise."""
        return self.end.declaration.chain

    @property
    def steps(self) -> tuple[Reading, ...]:
        """Every step the line says, this one first; this one alone, for a line of one command."""
        return (self, *self.then)

    @property
    def phrase(self) -> str:
        """The phrase that says the line: for a chain, its steps' joined by ``then``.

        Each step after the first says its phrase from where the chain's shared part ends:
        ``fleet {fleet} jump {system} then move {to} then mine``.
        """
        said = [self.end.bound.phrase.text]
        if self.then:
            shared = _shared(cast('type', self.chain))
            for step in self.then:
                parts = step.end.bound.phrase.parts[_head(step.end, shared)[0] :]
                said.append(' '.join(part.text if isinstance(part, Word) else _slot_text(part) for part in parts))
        return f' {THEN} '.join(said)

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

#: A name's scope, once read: the field it is, its value as the resolver is given it, and its words as typed; and,
#: where the chain's place gave the value, the words that said the place.
type _Scope = tuple[str, str, str, str | None]


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
        end: Where the walk ended, for a refusal's usage.
        said: A slot's step's words, for a refusal to say those before it (``where``); none for a flag.
    """

    by: Place | Flag
    words: tuple[Token, ...]
    values: tuple[Token, ...]
    kind: Kind
    field: Field
    end: End
    said: tuple[Token, ...] = ()

    @property
    def where(self) -> str:
        """How a refusal names it: the line's words up to its slot, then the slot; or the flag. Made when asked."""
        if isinstance(self.by, Place):
            return _slot_said(self.said, self.words, self.by)
        return f'--{self.by.name}'


@dataclass(slots=True)
class _Walker:
    """One line's walk by a tree, and the refusals it makes."""

    tree: Tree
    line: str
    names: Mapping[str, Resolver]
    placeholders: bool = False

    def walk(self) -> Reading:
        tokens = split(self.line)
        first = _flag(tokens[0], self.tree.shorts) if tokens else None
        if first is not None and first[0] not in RESERVED:
            msg = f'{tokens[0].raw} comes before a command: a flag follows the first word'
            raise self.refuse(msg, word=tokens[0])
        pieces, joins = _pieces(self.tree, tokens) if self.tree.chains else ([tokens], [])
        if not joins:
            return self._step(tokens)[0]
        return self._chain(tokens, pieces, joins)

    def _step(
        self,
        tokens: list[Token],
        *,
        said: Sequence[Token] = (),
        later: _Later | None = None,
        shared: Mapping[str, _Field] | None = None,
    ) -> tuple[Reading, dict[str, _Field]]:
        """One command's words read: from the root, or a chain's later step from the chain's place in the tree.

        A later step comes with the words said before it, for its refusals, where it starts, and the chain's shared
        fields, as its first step gave them.
        """
        words, flags, own = self._split_flags(tokens)
        if not words:
            msg = 'no command: the line has no words'
            raise self.refuse(msg, suggestions=list(self.tree.root.words))
        shared = shared or {}
        step_words = (*said, *words)
        end, slots = self._walk_words(words, said=said, later=later)
        flags, wait = self._wait(end, flags)
        specs = {spec.attr: spec.field for spec in end.declaration.cls.__seared_fields__}
        skip = 0 if not shared else _head(end, set(shared))[1]
        fields = {
            **shared,
            **self._slot_fields(end, slots, specs, said=step_words, skip=skip),
            **self._flag_fields(end, flags, words, specs, have=set(shared)),
        }
        values = self._values(fields, None if later is None else later.moved)
        given = {attr: Given(by=found.by, words=found.words, value=values[attr]) for attr, found in fields.items()}
        reading = Reading(
            end=end,
            given=MappingProxyType(given),
            own=frozenset(own),
            line=self.line,
            wait=wait,
            words=step_words,
        )
        return reading, fields

    # --- a chain ----------------------------------------------------------------------------------------------

    def _chain(self, tokens: list[Token], pieces: list[list[Token]], joins: list[Token]) -> Reading:
        """A line whose first piece is a step: each piece a step of its chain. Otherwise, the line as one command."""
        if not all(pieces):
            word = joins[0] if not pieces[0] else joins[next(at for at, piece in enumerate(pieces) if not piece) - 1]
            msg = f'`{THEN}` needs a step on each side: dock {THEN} sell'
            raise self.refuse(msg, word=word)
        try:
            first, fields = self._step(pieces[0])
        except ReadError as refused:
            return self._whole(tokens, refused)
        base = first.chain
        if base is None:
            msg = f'`{THEN}` joins steps: {_said(pieces[0])!r} is not one'
            return self._whole(tokens, self.refuse(msg, word=joins[0]))
        attrs = _shared(base)
        shared = {attr: field for attr, field in fields.items() if attr in attrs}
        start = _place_of(self.tree, first.end, _head(first.end, attrs)[0])
        moved = _moved(first, None, placeholders=self.placeholders)
        said = list(pieces[0])
        then: list[Reading] = []
        for join, piece in zip(joins, pieces[1:], strict=True):
            said.append(join)
            step, _ = self._step(piece, said=said, later=_Later(start, attrs, base, moved), shared=shared)
            if step.chain is not base:
                msg = f"`{THEN}` joins steps: {_said(piece)!r} is not one of {base.__qualname__}'s"
                raise self.refuse(msg, word=piece[0])
            then.append(step)
            moved = _moved(step, moved, placeholders=self.placeholders)
            said += piece
        if any(step.wait is not None for step in (first, *then)):
            msg = "a chain doesn't wait: --until and --watch are a read's, on a line of its own"
            raise self.refuse(msg, word=joins[0])
        own = frozenset().union(*(step.own for step in (first, *then)))
        return replace(first, own=own, then=tuple(then))

    def _whole(self, tokens: list[Token], refused: ReadError) -> Reading:
        """The line read as one command, ``then`` and all; refused as ``refused`` says, if it doesn't read so."""
        try:
            return self._step(tokens)[0]
        except ReadError:
            raise refused from None

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
            found = _flag(token, self.tree.shorts)
            if found is None:
                words.append(token)
                continue
            name, value = found
            if name in RESERVED:
                self._own(name, token, value, own)
                continue
            arity = self._arity(name, token)
            if arity is Arity.SWITCH and value is not None:
                msg = f'{_given(token, name)} takes nothing after it'
                raise self.refuse(msg, word=token)
            if arity is Arity.VALUE and value is None:
                if at == len(tokens) or tokens[at].raw == '--' or _flag(tokens[at], self.tree.shorts) is not None:
                    msg = f'{_given(token, name)} needs a value'
                    raise self.refuse(msg, word=token, hint=f'{_given(token, name)} <{self.tree.labels[name]}>')
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
            msg = f'{_given(token, name)} takes nothing after it'
            raise self.refuse(msg, word=token)
        if name in own:
            msg = f'{_given(token, name)} is given twice'
            raise self.refuse(msg, word=token)
        own.add(name)

    # --- the words ---

    def _walk_words(
        self, words: list[Token], *, said: Sequence[Token] = (), later: _Later | None = None
    ) -> tuple[End, list[tuple[Token, ...]]]:
        """Walk the words from the root, or a chain's place: where they end, and each slot's words on the way.

        ``said`` is the words before them on the line, for a refusal to say; ``later``, a chain's later step's place
        and shared fields, so a refusal offers only the chain's steps there.
        """
        node, said = self.tree.root if later is None else later.start, list(said)
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
                raise self._unknown(node, said, words[at], later)
            taken = _taken(edge.kind, edge.node, words, at)
            if not taken:
                raise self._which(edge, said, words[at], len(slots), later)
            slots.append(taken)
            said += taken
            node = edge.node
            at += len(taken)
        if node.end is not None:
            return node.end, slots
        if node.slot is not None:
            raise self._which(node.slot, said, None, len(slots), later)
        words_next = _onward(node, later)
        msg = f'{_said(said)}: then what? {" | ".join(words_next)}'
        raise self.refuse(msg, suggestions=words_next)

    def _unknown(self, node: Node, said: list[Token], word: Token, later: _Later | None = None) -> ReadError:
        """A word no command says here: one left over after a command, or one the node has no branch for."""
        if node.end is not None and not node.words:
            hint = self._usage(node.end)
            return self.refuse(f'{_said(said)}: {word.raw!r} is left over', word=word, hint=hint)
        asked = _said([*said, word])
        words_next = _onward(node, later)
        near = close(word.text.lower(), words_next)
        if near:
            return self.refuse(f'no command {asked!r}', word=word, near=near)
        return self.refuse(f'no command {asked!r}: {" | ".join(words_next)}', word=word, suggestions=words_next)

    def _which(
        self, edge: Edge, said: list[Token], word: Token | None, before: int, later: _Later | None = None
    ) -> ReadError:
        """A slot left empty: which value, and the line so far with the rest of how it's said.

        Where one command lies past the slot, the hint is the rest of its usage, flags and all; where several do, the
        slot's ``<…>``, and ``…`` if more must follow. ``before`` counts the slots the line has given.
        """
        past = {(end.declaration.cls, end.bound.phrase.text): end for end in _ends(edge.node)}
        if len(past) == 1:
            end = next(iter(past.values()))
            name = end.places[before + (0 if later is None else _head(end, later.shared)[1])].slot
            parts = end.bound.phrase.parts
            start = next(at for at, part in enumerate(parts) if isinstance(part, Slot) and part.name == name)
            fields = {spec.attr: spec.field for spec in end.declaration.cls.__seared_fields__}
            flags = self.tree.flags_of(end.declaration.cls).values()
            rest = [usage(end.bound, flags, fields, start=start, asks=end.declaration.asks)]
        else:
            rest = [f'<{edge.slot}>', *([] if edge.node.end else ['…'])]
        hint = ' '.join([*(token.raw for token in said), *rest])
        return self.refuse(f'{_said(said)}: which {edge.slot}?', word=word, hint=hint)

    def _usage(self, end: End) -> str:
        return self.tree.usage(end)

    # --- the values --------------------------------------------------------------------------------------------

    def _slot_fields(
        self,
        end: End,
        slots: list[tuple[Token, ...]],
        fields: Mapping[str, Field],
        *,
        said: tuple[Token, ...],
        skip: int = 0,
    ) -> dict[str, _Field]:
        """Each slot's words, as its field's: one word, several, or the rest of the line, joined.

        ``said`` is the line's words, its flags aside, for a refusal to say those before a slot, then the slot:
        ``fleet frigate jump <system>``. ``skip`` passes over the first slots of the phrase, a chain's that its first
        step read.
        """
        found = end.declaration
        out: dict[str, _Field] = {}
        for place, words in zip(end.places[skip:], slots, strict=True):
            kind = found.kind_of(place)
            joined = place.rest and not place.many and not isinstance(kind, Pairs)
            out[place.field] = _Field(
                by=place,
                words=words,
                values=(_joined(self.line, words),) if joined else words,
                kind=kind,
                field=fields[place.field],
                end=end,
                said=said,
            )
        return out

    def _flag_fields(
        self,
        end: End,
        flags: list[_Said],
        words: list[Token],
        fields: Mapping[str, Field],
        *,
        have: Collection[str] = (),
    ) -> dict[str, _Field]:
        """Each flag's words, as its field's, once the command is known; a required flag left out is refused.

        ``have`` are fields given already, a chain's from its first step.
        """
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
            short = next((token for _, token, _ in saids if _is_short(token)), None)
            if short is not None and found.shorts.get(flag.field) != short.raw[1]:
                raise self._not_taken(end, name, short, words)
            field = fields[flag.field]
            if len(saids) > 1 and (flag.arity is Arity.SWITCH or not field.many):
                msg = f'{_given(saids[1][1], name)} is given twice'
                raise self.refuse(msg, word=saids[1][1], field=flag.field)
            out[flag.field] = _Field(
                by=flag,
                words=tuple(word for _, token, value in saids for word in (token, value) if word is not None),
                values=tuple(value for _, _, value in saids if value is not None),
                kind=found.field_kinds[flag.field],
                field=field,
                end=end,
            )
        for flag in takes.values():
            if fields[flag.field].required and flag.field not in out and flag.field not in have:
                said = f'{self.line.strip()} --{flag.name}'  # the line as given, the flag added
                hint = said if flag.arity is Arity.SWITCH else f'{said} <{flag.label}>'
                msg = f'{_said(words)} needs --{flag.name}'
                raise self.refuse(msg, field=flag.field, hint=hint)
        return out

    # --- a wait ----------------------------------------------------------------------------------------------

    def _wait(self, end: End, flags: list[_Said]) -> tuple[list[_Said], Wait | None]:
        """A command that can wait: its wait's flags taken off the rest, read and checked, before anything runs."""
        found = end.declaration
        if not found.can_wait:
            return flags, None
        kept: list[_Said] = []
        given: dict[str, Token] = {}  # each flag's first word
        until: list[Condition] = []
        timeout: float | None = None
        count: int | None = None
        for said in flags:
            name, token, value = said
            if name not in WAIT_FLAGS:
                kept.append(said)
                continue
            if name in given and name != 'until':
                msg = f'--{name} is given twice'
                raise self.refuse(msg, word=token)
            given.setdefault(name, token)
            if name == 'until':
                condition = self._condition(found.reply, cast('Token', value))
                until += [] if condition is None else [condition]
            elif name == 'timeout':
                timeout = self._timeout(cast('Token', value))
            elif name == 'count':
                count = self._count(cast('Token', value))
        return kept, self._waiting(given, tuple(until), timeout, count)

    def _waiting(
        self, given: Mapping[str, Token], until: tuple[Condition, ...], timeout: float | None, count: int | None
    ) -> Wait | None:
        """The wait the flags make, if they make one; refused where a flag needs another the line doesn't give."""
        watch = 'watch' in given
        if 'count' in given and not watch:
            msg = '--count is how many replies a watch gives: give --watch too'
            raise self.refuse(msg, word=given['count'])
        if 'until' not in given and not watch:
            if 'timeout' in given:
                msg = '--timeout bounds a wait or a watch: give --until or --watch too'
                raise self.refuse(msg, word=given['timeout'])
            return None
        if 'timeout' not in given:
            timeout = TIMEOUT if 'until' in given else None  # a watch with no conditions has no bound of its own
        return Wait(until, timeout, watch=watch, count=count)

    def _condition(self, reply: type[Seared] | None, value: Token) -> Condition | None:
        """An ``--until``'s condition, its path checked against the reply's dump schema; ``None`` for a placeholder."""
        if self.placeholders and _placeholder(value):
            return None
        try:
            condition = Condition.parse(value.text)
        except ValueError as e:
            msg = f'--until: {e}'
            raise self.refuse(msg, word=value, hint='--until <path>=<value>') from None
        refused = None if reply is None else problem(condition, reply)
        if refused is not None:
            what, near = refused
            raise self.refuse(what, word=value, suggestions=near)
        return condition

    def _timeout(self, value: Token) -> float:
        """A ``--timeout``'s seconds, a span of time: the default, for a placeholder."""
        if self.placeholders and _placeholder(value):
            return TIMEOUT
        try:
            return span(value.text)
        except ValueError as e:
            msg = f'--timeout: {e}'
            raise self.refuse(msg, word=value) from None

    def _count(self, value: Token) -> int | None:
        """A ``--count``'s number of replies, a whole number, 1 or more: none, for a placeholder."""
        if self.placeholders and _placeholder(value):
            return None
        text = value.text.replace(',', '')
        if not text.isdigit() or int(text) < 1:
            msg = f'--count: {value.text!r} is not a number of replies: say 1 or more'
            raise self.refuse(msg, word=value)
        return int(text)

    def _not_taken(self, end: End, name: str, token: Token, words: list[Token]) -> ReadError:
        """A flag its command doesn't take, with its usage, and its own flags close to the one given."""
        if name in WAIT_FLAGS and self.tree.waits:
            msg = (
                f"{_said(words)} can't wait: --{name} is for a read, a command that declares EFFECT = READ and a REPLY"
            )
            return self.refuse(msg, word=token, hint=self._usage(end))
        hint = self._usage(end)
        near = [f'--{found}' for found in close(name, self.tree.flags_of(end.declaration.cls))]
        return self.refuse(f'{_said(words)} takes no {_given(token, name)}', word=token, hint=hint, near=near)

    def _values(self, fields: Mapping[str, _Field], moved: _Moved | None = None) -> dict[str, object]:
        """Each field's value, a name's scope read before it; a switch's is ``True``, or ``False`` for ``--no-…``.

        ``moved`` is where a chain's earlier steps have moved it, for a scope that follows the chain.
        """
        values: dict[str, object] = {}

        def read(attr: str) -> None:
            found = fields[attr]
            scope = found.kind.scope if isinstance(found.kind, Named) else None
            if scope is not None and scope in fields and scope not in values:
                read(scope)  # a declaration refuses scopes that go round, so this ends
            if not isinstance(found.by, Place) and found.by.arity is Arity.SWITCH:
                values[attr] = not found.by.negated
                return
            if scope is not None and moved is not None and cast('Named', found.kind).follows:
                read_scope = _at(scope, fields, moved)
            else:
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
        return scope, str(value), _text_of(fields[scope].values), None

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
        return self._resolved(found, resolver, word, scope, kind.term)

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
            key = key_word.text if resolver is None else self._resolved(found, resolver, key_word, scope, kind.term)
            if key in out:
                msg = f'{found.where}: {key_word.raw} is given twice'
                raise self.refuse(msg, word=key_word, field=found.by.field)
            of = None if resolver is None else cast('PairsResolver', resolver).values(key, given)
            # A value's resolver is given no scope: the pairs' gave it knowing the key and the scope.
            out[key] = value_word.text if of is None else self._resolved(found, of, value_word, None, key_word.raw)
        return out

    def _resolved(self, found: _Field, resolver: Resolver, word: Token, scope: _Scope | None, what: str) -> str:
        """The key a resolver reads a word to; a word no name answers to is refused, with what's close to it.

        A resolver that says why, by a ``ValueError``, is refused with its reason and no suggestions: the reason says
        what's near.
        """
        if self.placeholders and _placeholder(word):
            return word.text
        given = None if scope is None else scope[1]
        try:
            key = resolver.lookup(word.text, given)
        except ValueError as e:
            msg = f'{found.where}: {e}'
            raise self.refuse(msg, word=word, field=found.by.field, hint=self._usage(found.end)) from None
        if key is not None:
            return key
        near = list(resolver.suggest(word.text, given))
        within = '' if scope is None else _within(scope)
        msg = f'{found.where}: no {what} {word.text!r}{within}'  # its text: a name may be quoted for its spaces
        raise self.refuse(msg, word=word, field=found.by.field, hint=self._usage(found.end), near=near)


def _key(resolver: Resolver, word: str, scope: str | None) -> str | None:
    """The key a resolver reads ``word`` to, or ``None`` where it names nothing, whether or not it says why."""
    try:
        return resolver.lookup(word, scope)
    except ValueError:
        return None


def _within(scope: _Scope) -> str:
    """Where a refusal says a name was looked for: ``for fleet 'Prospector'``, and ``once at 'sol'`` for a place."""
    field, _, said, at = scope
    parts = [f'for {field} {said!r}'] if said else []
    parts += [] if at is None else [f'once at {at!r}']
    return f' {", ".join(parts)}' if parts else ''


def _pieces(tree: Tree, tokens: list[Token]) -> tuple[list[list[Token]], list[Token]]:
    """A line cut at each unquoted ``then``: its pieces, and the ``then`` between each two.

    A flag's value is never a cut, nor is a word after ``--``.
    """
    pieces: list[list[Token]] = [[]]
    joins: list[Token] = []
    at = 0
    while at < len(tokens):
        token = tokens[at]
        at += 1
        found = _flag(token, tree.shorts)
        if token.raw == '--':
            pieces[-1] += tokens[at - 1 :]
            break
        if found is not None:
            pieces[-1].append(token)
            if found[1] is None and tree.flags.get(found[0]) is Arity.VALUE and at < len(tokens):
                pieces[-1].append(tokens[at])
                at += 1
        elif not token.quoted and token.text.lower() == THEN:
            joins.append(token)
            pieces.append([])
        else:
            pieces[-1].append(token)
    return pieces, joins


def _place_of(tree: Tree, end: End, parts: int) -> Node:
    """Where in ``tree`` a step's first ``parts`` of its phrase lead, by the slots its line read."""
    node, read = tree.top, {place.slot for place in end.places}
    for part in end.bound.phrase.parts[:parts]:
        if isinstance(part, Word):
            node = node.words[part.text]
        elif part.name in read:
            node = cast('Edge', node.slot).node
    return node


class _Moved(NamedTuple):
    """Where a chain's steps have moved it.

    Its key is the place's, as a scope that follows the chain is given it, and ``said`` its words as typed; ``None``
    for both where a step moved it somewhere the line doesn't say.
    """

    key: str | None
    said: str | None


class _Later(NamedTuple):
    """A chain's later step, as its walk knows it: where in the tree it starts, the shared fields, and the chain.

    ``moved`` is where the steps before it have moved the chain, or ``None`` while they haven't.
    """

    start: Node
    shared: frozenset[str]
    chain: type
    moved: _Moved | None = None


def _moved(step: Reading, moved: _Moved | None, *, placeholders: bool = False) -> _Moved | None:
    """Where a chain is after ``step``, from ``moved``, where it was before it.

    Where its ``MOVES`` field says; somewhere unsaid for ``True``, or for a field the line leaves out (its default
    isn't the line's); else where it was.
    """
    moves = step.end.declaration.moves
    if moves is False:
        return moved
    given = None if moves is True else step.given.get(moves)
    words = () if given is None else given.words if isinstance(given.by, Place) else given.words[1::2]
    if given is None or given.value is None or (placeholders and any(_placeholder(word) for word in words)):
        return _Moved(None, None)
    return _Moved(str(given.value), _said(words))


def _at(scope: str, fields: Mapping[str, _Field], moved: _Moved) -> _Scope | None:
    """A scope that follows its chain, once the chain has moved: the place as its value; ``None`` where it's unsaid."""
    if moved.key is None:
        return None
    return scope, moved.key, _text_of(fields[scope].values) if scope in fields else '', moved.said


def _onward(node: Node, later: _Later | None) -> list[str]:
    """The words that may follow at ``node``: for a chain's later step, only those that lead to one of its steps."""
    if later is None:
        return list(node.words)
    return [
        word for word, child in node.words.items() if any(end.declaration.chain is later.chain for end in _ends(child))
    ]


def _slot_text(slot: Slot) -> str:
    """A slot as its phrase writes it: ``{name}``, or ``{name**}`` for the rest of the line."""
    return f'{{{slot.name}**}}' if slot.rest else f'{{{slot.name}}}'


def _shared(base: type) -> frozenset[str]:
    """A chain's shared fields: those its base declares, which its first step gives for every step."""
    return frozenset(spec.attr for spec in getattr(base, '__seared_fields__', ()))


def _head(end: End, shared: Collection[str]) -> tuple[int, int]:
    """How much of a step's phrase is its chain's: how many parts, and how many of its line's slots among them."""
    head = head_of(end.bound, shared)
    slots = {part.name for part in end.bound.phrase.parts[:head] if isinstance(part, Slot)}
    return head, sum(1 for place in end.places if place.slot in slots)


def head_of(bound: Bound, shared: Collection[str]) -> int:
    """How many parts of a step's phrase are its chain's: up to its last slot of a shared field.

    That's ``fleet {fleet}``, or a twin's ``detachment {detachment}``; none, for a phrase that says no shared field.
    """
    places = {place.slot: place for place in bound.places}
    parts = bound.phrase.parts
    return 1 + max(
        (at for at, part in enumerate(parts) if isinstance(part, Slot) and places[part.name].field in shared),
        default=-1,
    )


def _flag(token: Token, shorts: Mapping[str, str] | None = None) -> tuple[str, Token | None] | None:
    """A flag's name and the value it gives after ``=``, if ``token`` is one: ``--`` and a name, outside quotes.

    Or a short flag, ``-`` and a letter: ``-h``, ``--help``'s, or one ``shorts`` gives, to the flag it says.
    """
    raw = token.raw
    if raw[:1] != '-':  # most words: neither a flag nor a short
        return None
    if len(raw) == len('-c'):  # a short, if it's a letter one gives; `--` and `-3` are no letter's
        letter = raw[1]
        name = HELP if letter == HELP_SHORT else None if shorts is None else shorts.get(letter)
        return None if name is None else (name, None)
    head, eq, _ = raw.partition('=')
    if not head.startswith('--') or len(head) == len('--') or '"' in head:  # `--=x` names nothing
        return None
    if not eq:
        return head[2:].lower(), None
    at = len(head) + 1  # the head has no quotes, so the text and the raw word agree up to the `=`
    return head[2:].lower(), Token(text=token.text[at:], start=token.start + at, raw=token.raw[at:])


def _is_short(token: Token) -> bool:
    """Whether ``token`` is said as a short flag would be: ``-`` and one letter, unquoted."""
    raw = token.raw
    return len(raw) == 2 and raw[0] == '-' and raw[1].isascii() and raw[1].isalpha()  # noqa: PLR2004 -- `-c`


def _given(token: Token, name: str) -> str:
    """A flag as a refusal names it: as given, when it's short (``-c``); else by its name (``--config``)."""
    return token.raw if _is_short(token) else f'--{name}'


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


def _slot_said(said: Sequence[Token], words: Sequence[Token], place: Place) -> str:
    """A slot as a refusal names it: the step's words before it, as typed, then the slot as a usage writes it."""
    return ' '.join([*(word.raw for word in said if word.start < words[0].start), plain_slot(place)])


def _text_of(words: Sequence[Token]) -> str:
    """Words as a refusal quotes them: their text, a quoted name's quotes left off."""
    return ' '.join(word.text for word in words)


def _text(what: str, *, near: Sequence[str] = (), hint: str | None = None) -> str:
    """A refusal's text for people: what's wrong, then any did-you-mean, then the hint."""
    if near:
        what = f'{what}; did you mean {either(near)}?'
    return f'{what} `{hint}`' if hint else what


def _refused(reading: Reading, error: ValidationError) -> ReadError:
    """A value seared refused, as the word that gave it: its slot, said as the line's words up to it, or its flag."""
    wires = {spec.wire: spec.attr for spec in reading.command.__seared_fields__}
    head = error.path[0] if error.path else None
    attr = wires.get(head) if isinstance(head, str) else None
    given = reading.given.get(attr) if attr is not None else None
    if given is None:  # no word gave it: the instance as a whole
        message = f'{reading.line.strip()}: {error.reason}'
        return ReadError(message, kind='validation', line=reading.line, column=len(reading.line), field=attr)
    if isinstance(given.by, Place):
        where = _slot_said(reading.words, given.words, given.by)
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
