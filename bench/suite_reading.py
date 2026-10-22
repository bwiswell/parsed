"""The reading suite: what a line costs, on a tree the size of a real one.

- **walk:** each line's flags split off, its words walked from the root, each field's words kept (``Tree.walk``);
- **read:** each line on to its instance, loaded by seared from its words (``Tree.read``).

Each case reads one line for each command, :data:`~bench.tree.COMMANDS` lines, on a tree built once; the docs quote
it for every line and per line.
"""

from __future__ import annotations

from parsed.tree import Tree

from .harness import Case
from .tree import COMMANDS, lines, tree

SUITE = 'reading'


def cases() -> list[Case]:
    """The reading suite's two cases."""
    commands = tree()
    built = Tree(commands)
    said = lines(commands)
    return [
        Case(suite=SUITE, name='walk', iterations=400, per=COMMANDS, run=lambda _: [built.walk(line) for line in said]),
        Case(suite=SUITE, name='read', iterations=400, per=COMMANDS, run=lambda _: [built.read(line) for line in said]),
    ]
