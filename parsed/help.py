"""Help: how a command is said and what it does, and what a line may still say, in the commands' own words.

**A command's help** (``<line> --help``, :func:`command`) is its usage by the phrase the line said, then:

- its docstring;
- a row for each of its arguments, a slot (``<fleet>``) or a flag (``-c, --config <path>``), with its field's
  ``doc=``, or else what its kind's words are (:meth:`parsed.kinds.Kind.describe`), and ``--yes`` last for one that
  asks first, which its usage ends with too;
- the other phrases that say it, and its ``EXAMPLES``;
- what it asks of the line: ``--yes`` for one that asks first, a wait's flags for one that can wait, ``then`` for a
  step, and a person at a terminal for an interactive one, with what's said in its place.

**A listing** (:func:`listing`) is what a line short of a command may still say: an :class:`Entry` a line, a
command's usage or a namespace's words, each with its summary in a column after the widest. An app gives the entries
(:mod:`parsed.app`): its namespaces' lines, each a mount's prefix and its docstring, until the line goes along a
prefix, then the commands beneath.

Docstrings are read as seared's pages read them: cleaned of their indent, an RST role's mark (``:class:``) left off,
and double backticks written single.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._walk import THEN
from ._walk._hints import plain_slot
from .command import declaration
from .tree import Arity
from .wait import FLAGS as WAIT_FLAGS
from .wait import LABELS as WAIT_LABELS
from .wait import TIMEOUT

if TYPE_CHECKING:
    from collections.abc import Iterable

    from seared import Field

    from .command import Declaration
    from .tree import Flag, Tree

#: A wait's flags, as a note says them.
_WAITS = {name: f'--{name} <{WAIT_LABELS[name]}>' if name in WAIT_LABELS else f'--{name}' for name in WAIT_FLAGS}

#: An RST role's mark before a literal: ``:class:`Tree``` is written ```Tree```.
_ROLE = re.compile(r':[a-z]+:`~?([^`]+)`')


@dataclass(frozen=True, slots=True)
class Entry:
    """A line of a listing.

    Attributes:
        said: What's said: a command's usage, or a namespace's words and ``…``.
        summary: What it's for, the first line of its docstring; ``None`` for nothing.
    """

    said: str
    summary: str | None = None


def listing(entries: Iterable[Entry]) -> str:
    """Entries, one a line, each's summary in a column after the widest that has one."""
    found = list(entries)
    width = max((len(entry.said) for entry in found if entry.summary), default=0)
    return '\n'.join(f'{entry.said.ljust(width)}  {entry.summary}' if entry.summary else entry.said for entry in found)


def rows(pairs: Iterable[tuple[str, str]]) -> list[str]:
    """Pairs as indented rows, each's text in a column after the widest: an argument and what it's for."""
    found = list(pairs)
    width = max((len(said) for said, _ in found), default=0)
    return [f'  {said.ljust(width)}  {text}'.rstrip() for said, text in found]


def command(tree: Tree, cls: type, *, phrase: int = 0, instead: str | None = None) -> str:
    """A command's help, by one of its phrases (``0``, its ``PHRASE``; then each of ``EXTRA_PHRASES``).

    Args:
        tree: The tree it's one of, for its usage and its flags.
        cls: The command.
        phrase: The phrase the help says it by: the one a line said.
        instead: For an interactive command, what's said in its place, as a usage: ``ships make <ship> add
            <part>``. An app gives it, since another mount may hold it.

    Raises:
        KeyError: ``cls`` isn't one of the tree's commands.
    """
    found = declaration(cls)
    bound = found.phrases[phrase]
    fields = {spec.attr: spec.field for spec in found.cls.__seared_fields__}
    parts = [tree.usage_of(cls, phrase)]
    said = doc(cls)
    if said:
        parts.append(said)
    arguments = [
        (plain_slot(place), _what(fields[place.field].doc, found.kind_of(place).describe(fields[place.field])))
        for place in bound.places
    ]
    arguments += [
        (_flag(flag, found.shorts.get(flag.field), many=fields[flag.field].many), _flag_what(flag, found, fields))
        for flag in tree.flags_of(cls).values()
    ]
    if found.asks:
        arguments.append(('--yes', 'answer each question it asks yes'))
    if arguments:
        parts.append('\n'.join(rows(arguments)))
    others = [tree.usage_of(cls, at) for at in range(len(found.phrases)) if at != phrase]
    if others:
        parts.append('\n'.join(['Also said:', *(f'  {other}' for other in others)]))
    if found.examples:
        parts.append('\n'.join(['Examples:', *(f'  {example}' for example in found.examples)]))
    notes = _notes(found, instead)
    if notes:
        parts.append('\n'.join(notes))
    return '\n\n'.join(parts)


def doc(obj: object) -> str | None:
    """``obj``'s docstring, read as help reads one (:func:`cleaned`); ``None`` where it has none."""
    return cleaned(getattr(obj, '__doc__', None))


def cleaned(text: str | None) -> str | None:
    """A docstring as help reads one: its indent and trailing spaces cleaned, an RST role's mark off, ``x`` as `x`."""
    if not isinstance(text, str) or not text.strip():
        return None
    lines = (line.rstrip() for line in inspect.cleandoc(text).splitlines())
    return _ROLE.sub(r'`\1`', '\n'.join(lines)).replace('``', '`')


def summary(obj: object) -> str | None:
    """The first line of ``obj``'s docstring, as help reads it; ``None`` where it has none."""
    said = doc(obj)
    return None if said is None else said.splitlines()[0]


def _what(given: str | None, described: str) -> str:
    return given.strip() if given and given.strip() else described


def _flag(flag: Flag, short: str | None, *, many: bool) -> str:
    """A flag as an argument's row says it: its short form first, then its name, and its value."""
    said = f'--{flag.name}' if flag.arity is Arity.SWITCH else f'--{flag.name} <{flag.label}>'
    if many and flag.arity is Arity.VALUE:
        said += ' …'
    return f'-{short}, {said}' if short else said


def _flag_what(flag: Flag, found: Declaration, fields: dict[str, Field]) -> str:
    """What a flag is for: its field's ``doc=``; else what its value is, or for a switch, what giving it does."""
    field = fields[flag.field]
    if flag.arity is Arity.SWITCH:
        return _what(field.doc, 'off when given' if flag.negated else 'on when given')
    return _what(field.doc, found.field_kinds[flag.field].describe(field))


def _notes(found: Declaration, instead: str | None) -> list[str]:
    """What a command asks of the line, beyond its arguments."""
    notes: list[str] = []
    if found.asks:
        notes.append('It asks before it acts, and --yes answers it.')
    if found.can_wait:
        flags = ', '.join(_WAITS[name] for name in WAIT_FLAGS)
        notes.append(f'It can wait on its reply: {flags}; {TIMEOUT:g}s at most by default.')
    if found.chain is not None:
        notes.append(f'It is a step: {THEN} joins another after it.')
    if found.interactive:
        said = f': say `{instead}` instead' if instead else ''
        notes.append(f'It is for a person at a terminal{said}.')
    return notes
