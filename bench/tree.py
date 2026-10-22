"""A command tree the size of a real one, generated: what the suites declare and read.

:func:`tree` declares :data:`COMMANDS` commands, as many as a real terminal game's command line has, in twelve
sections. Each section has a base, decorated, carrying a positional field, an effect and the kinds its commands read
by. Its commands take the shapes parsed's tests take, in proportions near that game's:

- every fourth has a twin that renames its first slot, as a game's detachment does a fleet's verb;
- one in seven has an optional last slot, and an alias that leaves it out;
- one in six takes a second positional, and one in three or five a flag;
- one in nine reads, with a typed reply; one in eleven asks first; one in twenty-three is interactive, with the
  command before it as the form an agent says instead.

Each call declares new classes, so a suite can time declaring from nothing. :func:`lines` says each command once,
for the suites that read.
"""

from __future__ import annotations

import itertools
from datetime import timedelta
from typing import TYPE_CHECKING

import parsed
from parsed._phrase import Word
from parsed.command import declaration
from parsed.tree import flag_name

if TYPE_CHECKING:
    from parsed.command import Command

#: How many commands :func:`tree` declares by default: a real terminal game's command line.
COMMANDS = 263

_NOUNS = (
    'fleet',
    'ship',
    'base',
    'station',
    'rule',
    'routine',
    'quest',
    'blueprint',
    'design',
    'system',
    'sector',
    'store',
)

_calls = itertools.count()


@parsed.parsed
class View(parsed.Parsed):
    """The reply every reading command returns."""

    key: str = parsed.Str(required=True)
    lines: list[str] = parsed.Str(many=True, default_factory=list)


def _declare(name: str, bases: tuple[type, ...], namespace: dict[str, object]) -> type[Command]:
    namespace['__qualname__'] = name
    return parsed.parsed(type(name, bases, namespace))


def _base(noun: str, tag: str) -> type[Command]:
    twin = f'{noun}_twin'
    return _declare(
        f'{noun.title()}Base{tag}',
        (parsed.Command,),
        {
            '__annotations__': {noun: str},
            'EFFECT': parsed.Effect.WRITE,
            'KINDS': {noun: parsed.Name(noun), twin: parsed.Name(twin)},
            noun: parsed.Str(required=True, doc=f'the {noun}'),
        },
    )


def _command(at: int, base: type[Command], noun: str, tag: str, before: type[Command] | None) -> type[Command]:
    verb = f'v{at}'
    words = [noun, f'{{{noun}}}', verb]
    annotations: dict[str, object] = {}
    namespace: dict[str, object] = {'__annotations__': annotations}
    if at % 6 == 3:
        words.append('{hull}')
        annotations['hull'] = str
        namespace['hull'] = parsed.Str(required=True)
    optional = at % 7 == 1
    if optional:
        words.append('{target}')
        annotations['target'] = str | None
        namespace['target'] = parsed.Str(default=None)
    if at % 3 == 0:
        annotations['for_'] = timedelta | None
        namespace['for_'] = parsed.TimeDelta(data_key='for', default=None)
    if at % 5 == 2:
        annotations['n'] = int
        namespace['n'] = parsed.Int(default=10, ge=1)
    phrase = ' '.join(words)
    extra = []
    if at % 4 == 0:
        extra.append(' '.join([f'{noun}-twin', f'{{{noun}_twin}}', *words[2:]]))
    if optional:
        extra.append(' '.join([*words[:-1], 'nearest']))
    namespace.update({'PHRASE': phrase, 'EXTRA_PHRASES': tuple(extra)})
    if at % 9 == 0:
        namespace.update({'EFFECT': parsed.Effect.READ, 'REPLY': View})
    if at % 11 == 0:
        namespace.update({'EFFECT': parsed.Effect.ACTION, 'ASKS': True})
    if at % 23 == 0 and before is not None:
        namespace.update({'INTERACTIVE': True, 'INSTEAD': before})
    return _declare(f'{noun.title()}{verb.title()}{tag}', (base,), namespace)


def tree(commands: int = COMMANDS) -> list[type[Command]]:
    """Declare ``commands`` new commands, in the shapes and proportions this module's docstring gives.

    Returns:
        The commands, in order. Their bases are declared too, but not returned.
    """
    tag = f'T{next(_calls)}'
    bases = {noun: _base(noun, tag) for noun in _NOUNS}
    found: list[type[Command]] = []
    before: type[Command] | None = None
    for at in range(commands):
        noun = _NOUNS[at % len(_NOUNS)]
        cls = _command(at, bases[noun], noun, tag, before)
        found.append(cls)
        if not cls.__dict__.get('INTERACTIVE', False):
            before = cls
    return found


#: What :func:`lines` gives each flag the tree's commands take.
_FLAG_VALUES = {'for_': '90s', 'n': '3'}


def lines(commands: list[type[Command]]) -> list[str]:
    """A line for each command: its ``PHRASE``, each slot filled with a word, and then each of its flags given."""
    found = []
    for cls in commands:
        said = declaration(cls)
        words = [part.text if isinstance(part, Word) else f'{part.name}-1' for part in said.phrases[0].phrase.parts]
        wires = {spec.attr: spec.wire for spec in cls.__seared_fields__}
        words += [f'--{flag_name(wires[attr])} {_FLAG_VALUES[attr]}' for attr in said.flags]
        found.append(' '.join(words))
    return found
